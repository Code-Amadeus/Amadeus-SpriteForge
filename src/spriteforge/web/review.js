
const q = (id) => document.getElementById(id);
const esc=(value)=>String(value??" ").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;", "'":"&#39;"}[c]));
let data = { layout: "", clips: {} };
let qa = null;
let queue = [];
let expanded = [];
let playIndex = 0;
let timer = null;
let previewGeneration=0;
let activeClip = "";
let allSources = [];
let currentRoot = "";
let graphReadOnly = false;

// 跨状态 clip 帧缓存：key = root + "||" + clipId（全局唯一，不同 project 不会覆盖）
let allClips = {};

// 从 root 路径提取人类可读的 project 短标签
// Example: projects/demo/frames/idle -> demo/idle
function makeRootLabel(root) {
  const parts = root.replace(/\\/g, "/").split("/").filter(Boolean);
  const projIdx = parts.indexOf("projects");
  if (projIdx >= 0 && projIdx + 1 < parts.length) {
    // workspace project：取 projectName/stateName
    const proj = parts[projIdx + 1];
    const state = parts[projIdx + 3] || parts[parts.length - 1];  // projects/{name}/frames/{state}
    return proj === state ? proj : `${proj}/${state}`;
  }
  // fallback：取最后两段路径
  return parts.slice(-2).join("/") || parts[parts.length - 1] || root;
}

// 构造队列 item（统一格式）
// uid:    allClips 的唯一 key
// clipId: 原始 clip id（用于左侧面板高亮）
// label:  队列显示用的可读标签
function makeQueueItem(clipId, c, repeat, root) {
  const r = root || currentRoot;
  const uid = r + "||" + clipId;
  const slashIdx = clipId.indexOf("/");
  const clipName = slashIdx >= 0 ? clipId.slice(slashIdx + 1) : clipId;
  const label = makeRootLabel(r) + "/" + clipName;
  return { uid, clipId, label, repeat };
}

const frameUrl = (path) => "/frame?path=" + encodeURIComponent(path);

function setNow(shortId, fullPath) {
  q("now").textContent = shortId ? `${shortId}  ${fullPath}` : "No frame loaded";
}

function stop() {
  previewGeneration++;
  if (timer) clearInterval(timer);
  timer = null;
}

function statusClass(s) {
  return s === "ok" ? "ok" : (s === "warn" ? "warn" : "fail");
}

// ── 数据源选择 ──────────────────────────────────────────────────────────────

async function loadSources() {
  const res = await fetch("/api/projects");
  const j = await res.json();
  if (!j.ok || !j.sources) return;
  allSources = j.sources;
  graphReadOnly = !!j.readOnly;
  if(graphReadOnly) q('summary').textContent='KTX2 runtime pack loaded. Preview clips or inspect the Graph tab. Image QA and edits require the PNG authoring workspace.';
  for(const id of ['qaBtn','customLoadBtn','customRoot','tabInspMouth','gModeNode','gModeEdge','gPopulate','gNormalize','gClear','gSave','gValidate','gNLabel','gNRoot','gNPhase','gNInterval','gNLoop','gNIsRoot','gNDel','gEProb','gEDel']) q(id).disabled=graphReadOnly;

  // 构建 source 下拉
  const sel = q("sourceSelect");
  sel.innerHTML = allSources.map((src, i) =>
    `<option value="${i}">${esc(src.label)}</option>`
  ).join("");

  // 添加 custom 选项
  const customOpt = document.createElement("option");
  customOpt.value = "custom";
  customOpt.textContent = "Custom Path…";
  if(!graphReadOnly) sel.appendChild(customOpt);

  sel.addEventListener("change", onSourceChange);
  onSourceChange();
}

function onSourceChange() {
  const val = q("sourceSelect").value;
  stop();

  if (val === "custom") {
    q("projectCol").style.display = "none";
    q("stateSelect").disabled = true;
    q("stateSelect").innerHTML = '<option value="">— enter path below —</option>';
    q("customCol").classList.add("show");
    return;
  }

  q("customCol").classList.remove("show");
  const idx = parseInt(val);
  if (isNaN(idx) || !allSources[idx]) return;
  const src = allSources[idx];

  // 填充 project 下拉 (如果有 projects 字段，否则直接用 states)
  const hasProjects = !!src.projects;
  q("projectCol").style.display = hasProjects ? "" : "none";

  if (hasProjects) {
    const projSel = q("projectSelect");
    projSel.innerHTML = src.projects.map((p, i) =>
      `<option value="${i}">${esc(p.label)}</option>`
    ).join("");
    projSel.onchange = () => onProjectChange(src);
    onProjectChange(src);
  } else {
    // 没有 projects，直接显示 states
    populateStateSelect(src.states || []);
  }
}

function onProjectChange(src) {
  const idx = parseInt(q("projectSelect").value);
  if (isNaN(idx) || !src.projects || !src.projects[idx]) {
    q("stateSelect").disabled = true;
    return;
  }
  const proj = src.projects[idx];
  populateStateSelect(proj.states || []);
}

function populateStateSelect(states) {
  const sel = q("stateSelect");
  sel.disabled = false;
  if (!states.length) {
    sel.innerHTML = '<option value="">— no states —</option>';
    return;
  }
  sel.innerHTML = states.map((s, i) => {
    const clips = s.clips || {};
    const parts = [];
    if (clips.in) parts.push("in:" + clips.in);
    if (clips.loop) parts.push("loop:" + clips.loop);
    if (clips.out) parts.push("out:" + clips.out);
    const info = parts.length ? ("  (" + parts.join(", ") + " frames)") : "";
    const label = s.run_label ? `${s.run_label} / ${s.label}` : s.label;
    return `<option value="${i}" data-root="${esc(s.root || '')}">${esc(label)}${info}</option>`;
  }).join("");
  sel.onchange = () => onStateChange(states);
  // 自动加载第一个
  onStateChange(states);
}

function onStateChange(states) {
  const idx = parseInt(q("stateSelect").value);
  if (isNaN(idx) || !states || !states[idx]) return;
  const st = states[idx];
  if (st.root) {
    currentRoot = st.root;
    loadClipsFromRoot(st.root);
  }
}

// ── 加载片段 ────────────────────────────────────────────────────────────────

async function loadClipsFromRoot(root) {
  stop();
  const res = await fetch("/api/clips?root=" + encodeURIComponent(root));
  data = await res.json();
  if (!data.ok) {
    setNow(data.error || "Load failed", "");
    return;
  }
  currentRoot = data.root;
  if(graphReadOnly) {const clip=Object.values(data.clips)[0];if(clip)q("fps").value=Math.round(100000/clip.frameIntervalMs)/100;}
  // 将本状态的 clips 以唯一 key (root||clipId) merge 进全局缓存
  // 不同 project 即使 state/clip 同名也不会互相覆盖
  for (const [clipId, clip] of Object.entries(data.clips || {})) {
    allClips[root + "||" + clipId] = clip;
  }
  renderClips();
  if (!queue.length) {
    // 队列为空时才自动建默认序列，否则保留用户已排好的队列
    setDefaultQueue();
    expandQueue();
    showFrame(0);
  } else {
    expandQueue();
    // 保持当前播放位置不变（帧仍有效）；若位置超界则回到 0
    showFrame(playIndex);
  }
  updateInfoBar();
  // 补全队列中来自其他 project 的 clip（模式切换后 allClips 被清空）
  await reloadQueueClips();
}

// 切换 alphaMode 后，allClips 被清空，只重载了 currentRoot。
// 此函数扫描 queue，找出 uid 在 allClips 中缺失的条目，
// 将其对应 root 转换为当前模式路径后异步拉取，并更新 item.uid。
async function reloadQueueClips() {
  const toLoad = new Set();
  for (const item of queue) {
    if (allClips[item.uid]) continue;
    const sep = item.uid.indexOf("||");
    if (sep < 0) continue;
    const rawRoot = item.uid.slice(0, sep);
    // 先还原为 normal root，再应用当前模式，保证双向切换都正确
    const modeRoot = rawRoot;
    toLoad.add(modeRoot);
  }
  if (toLoad.size === 0) return;
  for (const r of toLoad) {
    try {
      const res = await fetch("/api/clips?root=" + encodeURIComponent(r));
      const data = await res.json();
      if (!data.ok) continue;
      for (const [clipId, clip] of Object.entries(data.clips || {})) {
        allClips[r + "||" + clipId] = clip;
      }
    } catch (e) { /* 路径不存在时忽略 */ }
  }
  // 更新 item.uid 到当前模式路径
  for (const item of queue) {
    if (allClips[item.uid]) continue;
    const sep = item.uid.indexOf("||");
    if (sep < 0) continue;
    const rawRoot = item.uid.slice(0, sep);
    const modeRoot = rawRoot;
    const clipId = item.uid.slice(sep + 2);
    const newUid = modeRoot + "||" + clipId;
    if (allClips[newUid]) item.uid = newUid;
  }
  renderQueue();
  expandQueue();
}

async function loadCustomPath() {
  const root = q("customRoot").value.trim();
  if (!root) return;
  loadClipsFromRoot(root);
}

function updateInfoBar() {
  const bar = q("infoBar");
  const st = data.state_label || "";
  q("infoRoot").textContent = st ? `${st}  (${esc(currentRoot)})` : currentRoot;
  const clips = data.clips || {};
  const prefix = st ? (st + "/") : "";
  const parts = Object.entries(clips).map(([id, c]) => {
    const short = id.startsWith(prefix) ? id.slice(prefix.length) : id;
    return `${esc(short)}(${esc(c.role)}, ${c.frames.length}f)`;
  });
  q("infoClips").textContent = parts.join("  ") || "no clips";
  bar.style.display = "";
}

// ── QA ──────────────────────────────────────────────────────────────────────

async function runQa() {
  if (!currentRoot) {
    q("summary").textContent = "Please select a source and state first.";
    return;
  }
  q("summary").textContent = "Running…";
  const res = await fetch("/api/report?root=" + encodeURIComponent(currentRoot) + "&state=");
  qa = await res.json();
  renderQa();
}

function renderQa() {
  if (!qa || !qa.ok) {
    q("summary").textContent = qa && qa.error ? qa.error : "QA failed";
    return;
  }
  const report = qa.report;
  q("summary").innerHTML = `Status: <strong class="${statusClass(report.summary.status)}">${report.summary.status}</strong><br>` +
    `State: ${esc(report.summary.state)}<br>Clips: ${report.summary.clip_count}, Joins: ${report.summary.join_count}`;
  q("clipQa").innerHTML = `<table><thead><tr><th>Clip</th><th>Status</th><th>Anchor Span</th><th>Warnings</th></tr></thead><tbody>` +
    Object.entries(report.clips).map(([id, c]) => `<tr>
      <td class="mono">${esc(id)}</td>
      <td class="${statusClass(c.qa.status)}">${c.qa.status}</td>
      <td>cx ${c.anchor.cx_span}<br>feet ${c.anchor.feet_y_span}</td>
      <td>${(c.qa.warnings || []).join(", ") || "-"}</td>
    </tr>`).join("") + `</tbody></table>`;
  q("joinQa").innerHTML = report.joins.length ? `<table><thead><tr><th>Join</th><th>Status</th><th>Delta</th><th>Warnings</th></tr></thead><tbody>` +
    report.joins.map(j => `<tr>
      <td class="mono">${esc(j.from)} -> ${esc(j.to)}</td>
      <td class="${statusClass(j.qa.status)}">${j.qa.status}</td>
      <td>cx ${j.anchor_delta.cx}<br>feet ${j.anchor_delta.feet_y}<br>gray ${j.visual_delta.gray_mean_abs}</td>
      <td>${(j.qa.warnings || []).join(", ") || "-"}</td>
    </tr>`).join("") + `</tbody></table>` : "<div class='tiny'>No joins detected.</div>";
}

// ── 片段列表 & 队列 ─────────────────────────────────────────────────────────

function renderClips() {
  const el = q("clips");
  const clips = data.clips || {};
  const sh = q("stateHeader");
  const stLabel = data.state_label || "";
  if (stLabel) {
    sh.style.display = "";
    sh.innerHTML = `${esc(stLabel)}<span class="path-hint">${esc(currentRoot)}</span>`;
  } else {
    sh.style.display = "none";
  }
  const prefix = stLabel ? (stLabel + "/") : "";
  el.innerHTML = Object.entries(clips).map(([id, c]) => {
    const short = id.startsWith(prefix) ? id.slice(prefix.length) : id;
    // 每个 clip 独立的默认重复次数 (loop/idle/standby 默认 2，其余 1)
    const defRepeat = (c.role === "loop" || c.role === "idle" || c.role === "standby") ? 2 : 1;
    return `
    <div class="clip ${id === activeClip ? "active" : ""}" data-id="${esc(id)}">
      <div class="clip-head">
        <strong>${esc(short)}</strong>
        <span class="pill">${esc(c.role)}</span>
      </div>
      <div class="tiny">${c.frames.length} frames  ·  repeat
        <input type="number" class="clip-repeat" data-id="${esc(id)}" value="${defRepeat}"
               min="1" max="99" style="width:46px;padding:2px 4px;font-size:12px;" />
      </div>
      <div class="row" style="margin-top:6px;">
        <button data-act="view" data-id="${esc(id)}">View</button>
        <button data-act="add" data-id="${esc(id)}">+ Queue</button>
      </div>
    </div>`;
  }).join("");
  el.querySelectorAll("button").forEach(btn => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.id;
      if (btn.dataset.act === "view") {
        // 预览：先暂停播放，再显示该 clip 第一帧；不影响已构建的队列
        stop();
        activeClip = id;
        const c = data.clips && data.clips[id];
        if (c && c.frames.length) {
          SpriteForgeMedia.show(c.frames[0]);
          const short = id.startsWith(prefix) ? id.slice(prefix.length) : id;
          setNow(`preview  ${esc(short)}`, c.frames[0]);
        }
        renderClips();
      } else {
        const rptEl = el.querySelector(`.clip-repeat[data-id="${CSS.escape(id)}"]`);
        const rpt = rptEl ? (Math.max(1, Number(rptEl.value) || 1)) : 1;
        const c = data.clips && data.clips[id];
        if (!c) return;
        const wasEmpty = !expanded.length;
        queue.push(makeQueueItem(id, c, rpt));
        renderQueue();
        expandQueue();
        // 队列从空变为非空时立刻显示第一帧，让用户看到内容
        if (wasEmpty) showFrame(0);
      }
    });
  });
}

function setDefaultQueue() {
  const clips = data.clips || {};
  const byRole = {};
  for (const [clipId, c] of Object.entries(clips)) {
    if (!byRole[c.role]) byRole[c.role] = clipId;
  }
  const clipIds = ["in", "loop", "out"].map(r => byRole[r]).filter(Boolean);
  if (!clipIds.length && Object.keys(clips).length) clipIds.push(Object.keys(clips)[0]);
  queue = clipIds.map(clipId => {
    const c = clips[clipId];
    const defRepeat = (c && (c.role === "loop" || c.role === "idle" || c.role === "standby")) ? 2 : 1;
    return makeQueueItem(clipId, c, defRepeat);
  });
  renderQueue();
}

function renderQueue() {
  const el = q("queue");
  if (!queue.length) {
    el.innerHTML = '<div class="tiny" style="padding:4px;">Queue empty — use "View" or "+ Queue" on clips</div>';
    return;
  }
  el.innerHTML = queue.map((item, i) => {
    // uid 是唯一 key（含 root），查全局缓存
    const c = allClips[item.uid];
    const frameCount = c ? c.frames.length : "?";
    const role = item.role || (c ? c.role : "");
    // label 格式：projName/stateName/clipName，最后一段用高亮色
    const label = item.label || item.clipId || item.uid || "";
    const lastSlash = label.lastIndexOf("/");
    const labelPrefix = lastSlash >= 0 ? label.slice(0, lastSlash + 1) : "";
    const labelSuffix = lastSlash >= 0 ? label.slice(lastSlash + 1) : label;
    const labelHtml = labelPrefix
      ? `<span style="color:var(--muted);font-size:11px;">${esc(labelPrefix)}</span><span class="qname">${esc(labelSuffix)}</span>`
      : `<span class="qname">${esc(labelSuffix)}</span>`;
    return `
    <div class="qitem" data-i="${i}">
      <span title="${esc(label)}" style="display:inline-flex;align-items:baseline;gap:1px;min-width:110px;flex-shrink:0;">${labelHtml}</span>
      <span class="pill">${esc(role)}</span>
      <span class="tiny">${frameCount}f</span>
      <span class="tiny">×</span>
      <input type="number" class="qrepeat" data-i="${i}" value="${item.repeat}"
             min="1" max="99" style="width:42px;padding:2px 4px;font-size:12px;" />
      <button class="qact" data-act="dup" data-i="${i}" title="Duplicate">+</button>
      <button class="qact" data-act="up" data-i="${i}" title="Move up" ${i===0?'disabled':''}>▲</button>
      <button class="qact" data-act="down" data-i="${i}" title="Move down" ${i===queue.length-1?'disabled':''}>▼</button>
      <button class="qact" data-act="del" data-i="${i}" title="Remove">×</button>
    </div>`;
  }).join("");

  // 绑定队列操作
  el.querySelectorAll("button.qact").forEach(btn => {
    btn.addEventListener("click", () => {
      const i = Number(btn.dataset.i);
      if (btn.dataset.act === "del") {
        queue.splice(i, 1);
      } else if (btn.dataset.act === "dup") {
        queue.splice(i + 1, 0, { ...queue[i] });
      } else if (btn.dataset.act === "up" && i > 0) {
        [queue[i - 1], queue[i]] = [queue[i], queue[i - 1]];
      } else if (btn.dataset.act === "down" && i < queue.length - 1) {
        [queue[i], queue[i + 1]] = [queue[i + 1], queue[i]];
      }
      renderQueue();
      expandQueue();
    });
  });
  // 绑定 repeat 修改：用 input 事件实时同步，不等失焦
  el.querySelectorAll("input.qrepeat").forEach(inp => {
    inp.addEventListener("input", () => {
      const i = Number(inp.dataset.i);
      const v = Math.max(1, Number(inp.value) || 1);
      queue[i].repeat = v;
      expandQueue();
    });
  });
}

function expandQueue() {
  expanded = [];
  for (const item of queue) {
    // uid = root||clipId，全局唯一；clipId 用于左侧面板高亮
    const c = allClips[item.uid];
    if (!c) continue;
    const times = Math.max(1, item.repeat || 1);
    for (let i = 0; i < times; i++) {
      expanded.push(...c.frames.map(path => ({ clipId: item.clipId, label: item.label, path })));
    }
  }
  playIndex = Math.min(playIndex, Math.max(0, expanded.length - 1));
}

function showFrame(idx) {
  if (!expanded.length) {
    q("frame").removeAttribute("src");
    setNow("", "");
    return;
  }
  playIndex = (idx + expanded.length) % expanded.length;
  const item = expanded[playIndex];
  const prevClip = activeClip;
  // clipId 是原始 clip id（如 "idle/loop"），用于左侧面板高亮
  activeClip = item.clipId || item.id || "";
  SpriteForgeMedia.show(item.path);
  // label 包含 project 信息（如 "demo_idle/idle/loop"）
  const displayLabel = item.label || activeClip;
  setNow(`${playIndex + 1}/${expanded.length}  ${displayLabel}`, item.path);
  // 仅在 activeClip 变化时更新高亮，避免每帧重建整个 clips 列表 DOM
  if (prevClip !== activeClip) {
    document.querySelectorAll("#clips .clip").forEach(el => {
      el.classList.toggle("active", el.dataset.id === activeClip);
    });
  }
}

function play() {
  stop();
  expandQueue();
  if (!expanded.length) return;
  playIndex = 0;
  showFrame(0);  // 立即显示第一帧，不等第一个 tick
  const fps = Math.max(1, Math.min(60, Number(q("fps").value || 24)));
  timer = setInterval(() => {if(!SpriteForgeMedia.busy)showFrame(playIndex + 1);}, Math.round(1000 / fps));
}

q("customLoadBtn").addEventListener("click", loadCustomPath);
q("customRoot").addEventListener("keydown", (e) => { if (e.key === "Enter") loadCustomPath(); });
q("qaBtn").addEventListener("click", runQa);
q("defaultSeqBtn").addEventListener("click", () => { setDefaultQueue(); expandQueue(); showFrame(0); });
q("clearSeqBtn").addEventListener("click", () => { queue = []; renderQueue(); expandQueue(); showFrame(0); });
q("playBtn").addEventListener("click", play);
q("pauseBtn").addEventListener("click", stop);
q("prevBtn").addEventListener("click", () => { stop(); showFrame(playIndex - 1); });
q("nextBtn").addEventListener("click", () => { stop(); showFrame(playIndex + 1); });
q("fps").addEventListener("change", () => { if (timer) play(); });


// ── Mouth Preview ─────────────────────────────────────────────────────────────
let mouthAllConfigs  = {};    // expr → { cx, cy, width, height, openness, frameUrls }
let mouthExpr        = "normal";
let mouthValue       = 0.0;
let mouthSpeaking    = false;
let mouthAnimate     = false;
let mouthAnimTimer   = null;
let mouthDebug       = false;
let mouthPreviewActive = false;
let _mouthImgCache   = {};   // url → HTMLImageElement
let mouthPosOverride = null; // { cx, cy, width, height } — live tuning, overrides config

async function loadMouthConfigs() {
  q("mouthFrameInfo").textContent = "Loading configs…";
  try {
    const res = await fetch("/api/mouth_masks");
    const j   = await res.json();
    if (!j.ok) { q("mouthFrameInfo").textContent = "Error: " + (j.error || "failed"); return; }
    mouthAllConfigs = j.expressions || {};
    const exprs = Object.keys(mouthAllConfigs).sort();
    const sel = q("mouthExprSel");
    sel.innerHTML = exprs.map(e => {
      const isSF = e.startsWith("sf:");
      const label = isSF ? `★ ${e.slice(3)} (SF)` : e;
      return `<option value="${esc(e)}">${esc(label)}</option>`;
    }).join("");
    // 默认选 sf:neutral → sf:smile → normal → 第一个
    const preferred = ["sf:neutral", "sf:smile", "normal"];
    mouthExpr = preferred.find(k => mouthAllConfigs[k]) || (exprs[0] || "");
    if (mouthExpr) sel.value = mouthExpr;
    _updateMouthInfo();
  } catch(e) {
    q("mouthFrameInfo").textContent = "Failed: " + e;
  }
}

function _getOrLoadImg(url, onLoad) {
  if (!url) return null;
  if (_mouthImgCache[url]) return _mouthImgCache[url];
  const img = new Image();
  img.onload = onLoad;
  img.src = url;
  _mouthImgCache[url] = img;
  return img;
}

// ── 核心合成函数（完全对应 Amadeus renderer.js _updateMouthLayer + _drawMouthMask）────
function drawMouthCanvas() {
  if (!mouthPreviewActive) return;
  const canvas  = q("mouthCanvas");
  const ctx     = canvas.getContext("2d");
  const baseImg = q("frame");

  if (!baseImg.complete || !baseImg.naturalWidth) return;

  // 同步 canvas 像素尺寸到贴图原始尺寸
  const nw = baseImg.naturalWidth, nh = baseImg.naturalHeight;
  if (canvas.width !== nw || canvas.height !== nh) {
    canvas.width  = nw;
    canvas.height = nh;
  }

  // 底层：绘制当前帧
  ctx.clearRect(0, 0, nw, nh);
  ctx.drawImage(baseImg, 0, 0);

  const cfg = mouthAllConfigs[mouthExpr];
  if (!cfg || !cfg.frameUrls || !cfg.frameUrls.length) {
    q("mouthFrameInfo").textContent = "No mouth config for: " + mouthExpr;
    return;
  }

  const v = mouthValue;
  // 完全复刻 Amadeus 逻辑：speaking 期间始终显示；否则仅 v>0.01 时显示
  const showOverlay = mouthSpeaking ? true : (v > 0.01);
  if (!showOverlay) { _updateMouthInfoText(cfg, -1, v, 0); return; }

  const amplitude = Math.max(v, 0.05);   // 最小 0.05，同 Amadeus

  // 按 openness 找最近帧（同 Amadeus _updateMouthLayer 的 bestIdx 逻辑）
  const { openness, frameUrls } = cfg;
  const n = Math.min(openness.length, frameUrls.length);
  let bestIdx = 0, bestDist = Infinity;
  for (let i = 0; i < n; i++) {
    const d = Math.abs(openness[i] - v);
    if (d < bestDist) { bestDist = d; bestIdx = i; }
  }

  const overlayUrl = frameUrls[bestIdx];
  if (!overlayUrl) { q("mouthFrameInfo").textContent = "Frame URL missing for idx " + bestIdx; return; }

  const overlayImg = _getOrLoadImg(overlayUrl, drawMouthCanvas);
  if (!overlayImg || !overlayImg.complete || !overlayImg.naturalWidth) return;

  // ── 椭圆几何 ────────────────────────────────────────────────────────────────
  // cx/cy 相对纹理中心 → 像素坐标：pixelX = cx + nw/2, pixelY = cy + nh/2
  // mouthPosOverride 优先（live tuning），否则使用 config 值
  const _ov = mouthPosOverride;
  const cx     = _ov ? _ov.cx     : cfg.cx;
  const cy     = _ov ? _ov.cy     : cfg.cy;
  const width  = _ov ? _ov.width  : cfg.width;
  const height = _ov ? _ov.height : cfg.height;
  const ellipseX = cx + nw / 2;
  const ellipseY = cy + nh / 2;
  const wHalf    = (width  / 2) * 1.35;              // 精确裁切（原 1.8× 太宽）
  const hHalf    = (height / 2) * (1.0 + 1.0 * amplitude);  // 开口垂直扩展（原 1.5× 过大）

  // overlay：在椭圆裁切内绘制 overlay 帧
  ctx.save();
  ctx.beginPath();
  ctx.ellipse(ellipseX, ellipseY, wHalf, hHalf, 0, 0, Math.PI * 2);
  ctx.clip();
  ctx.drawImage(overlayImg, 0, 0, nw, nh);
  ctx.restore();

  // Debug：画椭圆边框 + 中心十字
  if (mouthDebug) {
    const lw = Math.max(1.5, nw / 512);
    const cs = Math.max(8, nw / 80);
    ctx.save();
    ctx.strokeStyle = "rgba(255,70,70,0.9)";
    ctx.lineWidth   = lw;
    ctx.beginPath();
    ctx.ellipse(ellipseX, ellipseY, wHalf, hHalf, 0, 0, Math.PI * 2);
    ctx.stroke();
    ctx.strokeStyle = "rgba(60,240,80,0.9)";
    ctx.lineWidth   = lw * 0.8;
    ctx.beginPath();
    ctx.moveTo(ellipseX - cs, ellipseY); ctx.lineTo(ellipseX + cs, ellipseY);
    ctx.moveTo(ellipseX, ellipseY - cs); ctx.lineTo(ellipseX, ellipseY + cs);
    ctx.stroke();
    ctx.restore();
  }

  _updateMouthInfoText(cfg, bestIdx, v, amplitude);
}

function _updateMouthInfoText(cfg, bestIdx, v, amplitude) {
  const { openness, frameUrls, cx, cy, width, height } = cfg;
  const n = Math.min((openness || []).length, (frameUrls || []).length);
  const opStr   = (bestIdx >= 0 && openness[bestIdx] !== undefined)
                  ? openness[bestIdx].toFixed(3) : "—";
  const hasUrl  = bestIdx >= 0 && !!frameUrls[bestIdx];
  q("mouthFrameInfo").textContent =
    (bestIdx >= 0 ? `frame ${bestIdx + 1}/${n}  openness: ${opStr}  v: ${v.toFixed(2)}\n` : `v: ${v.toFixed(2)} (hidden)\n`) +
    `ellipse  cx=${cx.toFixed(1)}  cy=${cy.toFixed(1)}\n` +
    `         w=${width.toFixed(1)}  h=${height.toFixed(1)}  amp=${amplitude.toFixed(2)}\n` +
    (hasUrl ? "" : "⚠ frame URL not resolved");
}

function _syncPosInputs(cfg) {
  const ov = mouthPosOverride;
  q("mouthCxIn").value = (+(ov ? ov.cx     : cfg.cx    ).toFixed(1));
  q("mouthCyIn").value = (+(ov ? ov.cy     : cfg.cy    ).toFixed(1));
  q("mouthWIn").value  = (+(ov ? ov.width  : cfg.width ).toFixed(0));
  q("mouthHIn").value  = (+(ov ? ov.height : cfg.height).toFixed(0));
}

function _updateMouthInfo() {
  const cfg = mouthAllConfigs[mouthExpr];
  if (!cfg) { q("mouthFrameInfo").textContent = "No config for: " + mouthExpr; return; }
  const total  = (cfg.frameUrls || []).length;
  const avail  = (cfg.frameUrls || []).filter(Boolean).length;
  const mode   = cfg.sf ? `SpriteForge (${total} overlays: closed=idle, half, full)` : `Amadeus (${total} frames)`;
  q("mouthFrameInfo").textContent =
    `${mode}\ncx=${cfg.cx}  cy=${cfg.cy}  w=${cfg.width}  h=${cfg.height}  curve=${cfg.curve}\n` +
    (avail < total ? `⚠ ${total - avail} frames not resolved` : "✓ all frames resolved");
  // 仅 SF 表情显示位置调节面板
  const isSF = !!cfg.sf;
  q("mouthPosRow").style.display = isSF ? "" : "none";
  if (isSF) _syncPosInputs(cfg);
}

function setMouthPreviewActive(on) {
  mouthPreviewActive = on;
  q("frame").style.display        = on ? "none" : "";
  q("mouthCanvas").style.display  = on ? "block" : "none";
  q("mouthPreviewBtn").classList.toggle("on", on);
  q("mouthPreviewBtn").textContent = on ? "Preview ON" : "Preview OFF";
  if (on) {
    q("frame").addEventListener("load", drawMouthCanvas);
    drawMouthCanvas();
  } else {
    q("frame").removeEventListener("load", drawMouthCanvas);
    if (!mouthAnimate) stopMouthAnimate();
  }
}

function setMouthSpeaking(on) {
  mouthSpeaking = on;
  q("mouthSpeakBtn").classList.toggle("on", on);
  q("mouthSpeakBtn").textContent = on ? "Speaking ON" : "Speaking OFF";
  drawMouthCanvas();
}

function setMouthDebug(on) {
  mouthDebug = on;
  q("mouthDebugBtn").classList.toggle("on", on);
  q("mouthDebugBtn").textContent = on ? "Debug ON" : "Debug OFF";
  drawMouthCanvas();
}

function startMouthAnimate() {
  stopMouthAnimate();
  mouthAnimate = true;
  q("mouthAnimBtn").classList.add("on");
  q("mouthAnimBtn").textContent = "Animate ON";
  let t = 0;
  mouthAnimTimer = setInterval(() => {
    t += 0.08;
    // 自然口型节奏：sine 波，负值截断为 0（闭口停顿比张嘴时间长）
    mouthValue = Math.max(0, Math.sin(t));
    q("mouthValSlider").value       = mouthValue;
    q("mouthValDisplay").textContent = mouthValue.toFixed(2);
    drawMouthCanvas();
  }, 50);   // 20 fps 动画
}

function stopMouthAnimate() {
  if (mouthAnimTimer) { clearInterval(mouthAnimTimer); mouthAnimTimer = null; }
  mouthAnimate = false;
  q("mouthAnimBtn").classList.remove("on");
  q("mouthAnimBtn").textContent = "Animate OFF";
}

// ── Inspector tab 切换 ────────────────────────────────────────────────────────
function setInspTab(tab) {
  const isQA    = tab === "qa";
  const isMouth = tab === "mouth";
  const isGraph = tab === "graph";
  q("tabInspQA").classList.toggle("active",    isQA);
  q("tabInspMouth").classList.toggle("active", isMouth);
  q("tabInspGraph").classList.toggle("active", isGraph);
  q("qaPanel").style.display    = isQA    ? "" : "none";
  q("mouthPanel").style.display = isMouth ? "" : "none";
  q("graphPanel").style.display = isGraph ? "" : "none";
  if (isMouth && !Object.keys(mouthAllConfigs).length) loadMouthConfigs();
  if (isGraph) gResize();
}

q("tabInspQA").addEventListener("click",    () => setInspTab("qa"));
q("tabInspMouth").addEventListener("click", () => setInspTab("mouth"));
q("tabInspGraph").addEventListener("click", () => setInspTab("graph"));

q("mouthExprSel").addEventListener("change", () => {
  mouthExpr = q("mouthExprSel").value;
  mouthPosOverride = null;   // 切换表情时重置 override
  _updateMouthInfo();
  if (mouthPreviewActive) drawMouthCanvas();
});

q("mouthValSlider").addEventListener("input", () => {
  mouthValue = parseFloat(q("mouthValSlider").value);
  q("mouthValDisplay").textContent = mouthValue.toFixed(2);
  drawMouthCanvas();
});

q("mouthSpeakBtn").addEventListener("click",   () => setMouthSpeaking(!mouthSpeaking));
q("mouthDebugBtn").addEventListener("click",   () => setMouthDebug(!mouthDebug));
q("mouthAnimBtn").addEventListener("click",    () => { if (mouthAnimate) stopMouthAnimate(); else startMouthAnimate(); });
q("mouthPreviewBtn").addEventListener("click", () => setMouthPreviewActive(!mouthPreviewActive));

// ── Position override inputs ──────────────────────────────────────────────────
["mouthCxIn","mouthCyIn","mouthWIn","mouthHIn"].forEach(id => {
  q(id).addEventListener("input", () => {
    const cfg = mouthAllConfigs[mouthExpr] || {};
    mouthPosOverride = {
      cx:     parseFloat(q("mouthCxIn").value) || 0,
      cy:     parseFloat(q("mouthCyIn").value) || 0,
      width:  parseFloat(q("mouthWIn").value)  || cfg.width  || 36,
      height: parseFloat(q("mouthHIn").value)  || cfg.height || 15,
    };
    drawMouthCanvas();
  });
});

// 点击画布 → 设置 cx/cy（仅 SF 表情 + Preview ON）
q("mouthCanvas").addEventListener("click", (e) => {
  if (!mouthPreviewActive) return;
  const cfg = mouthAllConfigs[mouthExpr];
  if (!cfg || !cfg.sf) return;
  const canvas = q("mouthCanvas");
  const rect   = canvas.getBoundingClientRect();
  const scaleX = canvas.width  / rect.width;
  const scaleY = canvas.height / rect.height;
  const clickX = (e.clientX - rect.left) * scaleX;
  const clickY = (e.clientY - rect.top)  * scaleY;
  const newCx  = Math.round((clickX - canvas.width  / 2) * 10) / 10;
  const newCy  = Math.round((clickY - canvas.height / 2) * 10) / 10;
  mouthPosOverride = {
    cx:     newCx,
    cy:     newCy,
    width:  mouthPosOverride ? mouthPosOverride.width  : cfg.width,
    height: mouthPosOverride ? mouthPosOverride.height : cfg.height,
  };
  _syncPosInputs(cfg);
  drawMouthCanvas();
});

// Copy JSON
q("mouthCopyBtn").addEventListener("click", () => {
  const cfg = mouthAllConfigs[mouthExpr] || {};
  const ov  = mouthPosOverride;
  const obj = {
    cx:     ov ? ov.cx     : cfg.cx,
    cy:     ov ? ov.cy     : cfg.cy,
    width:  ov ? ov.width  : cfg.width,
    height: ov ? ov.height : cfg.height,
    curve:  cfg.curve,
  };
  const text = JSON.stringify(obj, null, 2);
  navigator.clipboard.writeText(text).then(
    () => { q("mouthCopyBtn").textContent = "Copied!"; setTimeout(() => q("mouthCopyBtn").textContent = "Copy JSON", 1800); },
    () => { q("mouthCopyBtn").textContent = text; }
  );
});

// ═══════════════════════════════════════════════════════════════════════════
// Graph Editor — 表演状态机可视化编辑器
// 节点 = 表情/动画状态（关联一个 frames root 路径）
// 边   = 有向转换，带概率权重（同一节点出边之和应为 1.0）
// ═══════════════════════════════════════════════════════════════════════════
let graph    = { nodes: [], edges: [] };
let gSel     = null;          // { type:'node'|'edge', id }
let gMode    = 'select';      // 'select' | 'node' | 'edge'
let gDrag    = null;          // { nodeId, offX, offY }
let gEdgeFrom = null;         // nodeId — 正在绘制边的起点
let gMouse   = { x: 0, y: 0 };
let gPan     = { x: 0, y: 0 };  // 画布平移偏移（像素）
const gZoom  = 1.0;              // 固定缩放（不再支持滚轮缩放）
let gPanning = false;            // 是否正在平移画布
let gPanStart = { x: 0, y: 0 }; // 开始平移时的鼠标位置
let gPanOrigin = { x: 0, y: 0 };// 开始平移时的 gPan 值

const GR      = 30;           // 节点圆半径
const GC      = 0.30;         // 贝塞尔曲率系数

function gUid() { return '_' + Math.random().toString(36).slice(2, 9); }
function gFindNode(id) { return graph.nodes.find(n => n.id === id); }
function gFindEdge(id) { return graph.edges.find(e => e.id === id); }

// ── 坐标 & hit-test ──────────────────────────────────────────────────────────
// 屏幕坐标 → 世界坐标（考虑平移+缩放）
function gXY(e) {
  const r = q('graphCanvas').getBoundingClientRect();
  const sx = e.clientX - r.left, sy = e.clientY - r.top;
  return { sx, sy, x: (sx - gPan.x) / gZoom, y: (sy - gPan.y) / gZoom };
}
function gHitNode(x, y) {
  for (let i = graph.nodes.length - 1; i >= 0; i--) {
    const n = graph.nodes[i];
    if ((x-n.x)**2 + (y-n.y)**2 <= GR*GR) return n;
  }
  return null;
}
function gHitEdge(x, y) {
  for (const e of graph.edges) {
    const mp = gEdgeMid(e);
    if (mp && Math.hypot(x - mp.x, y - mp.y) < 14) return e;
  }
  return null;
}

// -- Edge geometry ------------------------------------------------------------
function gEdgeGeom(e) {
  const fn = gFindNode(e.from), tn = gFindNode(e.to);
  if (!fn || !tn) return null;
  if (e.from === e.to) {
    const loopR = 14;
    return { selfLoop:true, loopR, cx:fn.x, cy:fn.y-GR-loopR, nx:fn.x, ny:fn.y };
  }
  const cpx = (fn.x+tn.x)/2 - (tn.y-fn.y)*GC;
  const cpy = (fn.y+tn.y)/2 + (tn.x-fn.x)*GC;
  const sa  = Math.atan2(cpy-fn.y, cpx-fn.x);
  const ea  = Math.atan2(tn.y-cpy, tn.x-cpx);
  const sx  = fn.x+GR*Math.cos(sa), sy = fn.y+GR*Math.sin(sa);
  const ex  = tn.x-GR*Math.cos(ea), ey = tn.y-GR*Math.sin(ea);
  const bmx = 0.25*(sx+ex)+0.5*cpx, bmy = 0.25*(sy+ey)+0.5*cpy;
  return { sx, sy, cpx, cpy, ex, ey, ea, bmx, bmy };
}
function gEdgeMid(e) {
  const g = gEdgeGeom(e);
  if (!g) return null;
  return g.selfLoop ? {x:g.cx, y:g.cy-g.loopR-6} : {x:g.bmx, y:g.bmy};
}

// -- Drawing ------------------------------------------------------------------
function gResize() {
  const cv = q('graphCanvas'); if (!cv) return;
  const hdr = document.querySelector('header');
  const hdrH = hdr ? hdr.offsetHeight : 60;
  cv.width  = cv.parentElement.clientWidth - 6;
  cv.height = Math.max(240, Math.min(320, window.innerHeight - hdrH - 480));
  gDraw();
}
function gDraw() {
  const cv = q('graphCanvas'); if (!cv || !cv.width) return;
  const ctx = cv.getContext('2d');
  ctx.clearRect(0, 0, cv.width, cv.height);
  // 背景
  ctx.fillStyle = '#0b0e14'; ctx.fillRect(0, 0, cv.width, cv.height);
  // 网格（固定在屏幕，不随 pan 移动，给人无限画布感）
  const gs = 30;
  const ox = ((gPan.x % gs) + gs) % gs;
  const oy = ((gPan.y % gs) + gs) % gs;
  ctx.fillStyle = '#1c2435';
  for (let x = ox; x < cv.width;  x += gs)
    for (let y = oy; y < cv.height; y += gs)
      ctx.fillRect(x - 0.75, y - 0.75, 1.5, 1.5);
  // 应用 pan + zoom 变换
  ctx.save();
  ctx.translate(gPan.x, gPan.y);
  ctx.scale(gZoom, gZoom);
  for (const e of graph.edges) gDrawEdge(ctx, e);
  if (gEdgeFrom) {
    const fn = gFindNode(gEdgeFrom);
    if (fn) {
      ctx.save();
      ctx.strokeStyle='rgba(80,160,255,0.45)'; ctx.lineWidth=1.5/gZoom; ctx.setLineDash([5/gZoom,4/gZoom]);
      ctx.beginPath(); ctx.moveTo(fn.x,fn.y); ctx.lineTo(gMouse.x,gMouse.y);
      ctx.stroke(); ctx.restore();
    }
  }
  for (const n of graph.nodes) gDrawNode(ctx, n);
  ctx.restore();

}
function gDrawNode(ctx, n) {
  const sel  = gSel && gSel.type==='node' && gSel.id===n.id;
  const from = gEdgeFrom===n.id;
  ctx.save();
  if (sel||from) { ctx.shadowColor=sel?'#4a9eff':'#50ff90'; ctx.shadowBlur=12; }
  ctx.beginPath(); ctx.arc(n.x,n.y,GR,0,Math.PI*2);
  ctx.fillStyle   = sel?'#172940':from?'#172b1e':'#141928'; ctx.fill();
  ctx.strokeStyle = sel?'#4a9eff':from?'#40e080':n.isRoot?'#c8a020':'#283a5a'; ctx.lineWidth=sel?2.5:n.isRoot?2.5:1.5; ctx.stroke();
  if (n.isRoot) {
    ctx.save(); ctx.beginPath(); ctx.arc(n.x,n.y,GR+5,0,Math.PI*2);
    ctx.strokeStyle='rgba(200,160,32,0.45)'; ctx.lineWidth=1.5; ctx.setLineDash([4,4]); ctx.stroke(); ctx.restore();
  }
  ctx.restore();
  ctx.save();
  ctx.beginPath(); ctx.arc(n.x,n.y,GR-3,0,Math.PI*2); ctx.clip();
  ctx.font='bold 10px monospace'; ctx.textAlign='center'; ctx.textBaseline='middle';
  ctx.fillStyle=sel?'#8ccfff':'#6a8fba';
  const lbl=n.label||'?';
  if (lbl.length<=9) { ctx.fillText(lbl,n.x,n.y); }
  else { const h=Math.ceil(lbl.length/2); ctx.fillText(lbl.slice(0,h),n.x,n.y-6); ctx.fillText(lbl.slice(h),n.x,n.y+7); }
  ctx.restore();
}
function gDrawEdge(ctx, e) {
  const geom=gEdgeGeom(e); if (!geom) return;
  const sel=gSel&&gSel.type==='edge'&&gSel.id===e.id;
  const col=sel?'#4a9eff':'#2e5080';
  const isManual = e.prob === 0;
  ctx.save(); ctx.strokeStyle=col; ctx.fillStyle=col; ctx.lineWidth=sel?2:1.5;
  if (isManual) ctx.setLineDash([5,4]);
  if (geom.selfLoop) {
    ctx.beginPath(); ctx.arc(geom.cx,geom.cy,geom.loopR,0,Math.PI*2); ctx.stroke();
    gArrow(ctx,geom.nx,geom.ny-GR,Math.PI/2,col);
  } else {
    ctx.beginPath(); ctx.moveTo(geom.sx,geom.sy);
    ctx.quadraticCurveTo(geom.cpx,geom.cpy,geom.ex,geom.ey); ctx.stroke();
    gArrow(ctx,geom.ex,geom.ey,geom.ea,col);
  }
  const mp=gEdgeMid(e);
  if (mp) {
    const txt=isManual?'manual':'weight '+e.prob;
    ctx.font='9px monospace'; ctx.textAlign='center'; ctx.textBaseline='middle';
    const tw=ctx.measureText(txt).width;
    ctx.fillStyle='rgba(11,14,20,0.85)'; ctx.fillRect(mp.x-tw/2-3,mp.y-7,tw+6,14);
    ctx.fillStyle=isManual?(sel?'#7ab4ff':'#3a5a88'):(sel?'#6af':'#4a7aaa'); ctx.fillText(txt,mp.x,mp.y);
  }
  ctx.restore();
}
function gArrow(ctx,x,y,angle,col) {
  const len=9,w=0.42;
  ctx.save(); ctx.strokeStyle=col; ctx.lineWidth=1.5;
  ctx.beginPath();
  ctx.moveTo(x,y); ctx.lineTo(x-len*Math.cos(angle-w),y-len*Math.sin(angle-w));
  ctx.moveTo(x,y); ctx.lineTo(x-len*Math.cos(angle+w),y-len*Math.sin(angle+w));
  ctx.stroke(); ctx.restore();
}

// -- Interaction --------------------------------------------------------------
function gSetMode(m) {
  gMode=m; if (m!=='edge') { gEdgeFrom=null; }
  ['Select','Node','Edge'].forEach(mm=>q('gMode'+mm).classList.toggle('active',mm.toLowerCase()===m));
  q('graphCanvas').style.cursor={select:'default',node:'cell',edge:'crosshair'}[m];
  gSetStatus(''); gDraw();
}
function gSetStatus(msg) { const el=q('gStatus'); if(el) el.textContent=msg; }

function gOnDown(e) {
  if (e.button!==0) return;
  const coords=gXY(e);
  const {x,y,sx,sy}=coords;
  const hitN=gHitNode(x,y);
  const hitE=hitN?null:gHitEdge(x,y);
  if (gMode==='node') {
    if (!hitN) {
      const defaultLabel = currentRoot
        ? currentRoot.replace(/\\/g,'/').split('/').filter(Boolean).pop()
            .replace(/^character_/,'').replace(/_saved$/,'').slice(0,18)
        : 'node';
      const n={id:gUid(),label:defaultLabel,root:currentRoot||'',x,y,isRoot:graph.nodes.length===0};
      graph.nodes.push(n); gSel={type:'node',id:n.id}; gRefreshProps(); gDraw();
      setTimeout(()=>{q('gNLabel').focus();q('gNLabel').select();},40);
    }
    return;
  }
  if (gMode==='edge') {
    if (hitN) {
      if (!gEdgeFrom) { gEdgeFrom=hitN.id; gMouse={x,y}; gSetStatus('Edge from "'+hitN.label+'" — click target'); }
      else {
        const dup=graph.edges.find(e2=>e2.from===gEdgeFrom&&e2.to===hitN.id);
        if (!dup) { const edge={id:gUid(),from:gEdgeFrom,to:hitN.id,prob:1.0}; graph.edges.push(edge); gSel={type:'edge',id:edge.id}; gRefreshProps(); }
        else gSetStatus('Edge already exists');
        gEdgeFrom=null; gDraw(); setTimeout(()=>gSetStatus(''),1500);
      }
    } else { gEdgeFrom=null; gSetStatus(''); gDraw(); }
    return;
  }
  // select mode
  if (hitN) {
    gSel={type:'node',id:hitN.id};
    gDrag={nodeId:hitN.id,offX:x-hitN.x,offY:y-hitN.y};
  } else if (hitE) {
    gSel={type:'edge',id:hitE.id}; gDrag=null;
  } else {
    // 空白处：平移画布
    gSel=null; gDrag=null;
    gPanning=true; gPanStart={x:sx,y:sy}; gPanOrigin={x:gPan.x,y:gPan.y};
  }
  gRefreshProps(); gDraw();
}
function gOnMove(e) {
  const {x,y,sx,sy}=gXY(e);
  gMouse={x,y};
  if (gPanning) {
    gPan.x=gPanOrigin.x+(sx-gPanStart.x);
    gPan.y=gPanOrigin.y+(sy-gPanStart.y);
    gDraw(); return;
  }
  if (gDrag) {
    const n=gFindNode(gDrag.nodeId);
    if (n) { n.x=x-gDrag.offX; n.y=y-gDrag.offY; }
  }
  if (gDrag||gEdgeFrom) gDraw();
}
function gOnUp()  { gDrag=null; gPanning=false; }

function gOnDbl(e) {
  const {x,y}=gXY(e); const hitN=gHitNode(x,y);
  if (hitN) { gSel={type:'node',id:hitN.id}; gRefreshProps(); setTimeout(()=>{q('gNLabel').focus();q('gNLabel').select();},30); }
}
function gOnCtx(e) {
  e.preventDefault(); const {x,y}=gXY(e);
  const hitN=gHitNode(x,y); if(hitN){gDeleteNode(hitN.id);return;}
  const hitE=gHitEdge(x,y); if(hitE) gDeleteEdge(hitE.id);
}
function gDeleteNode(id) {
  graph.nodes=graph.nodes.filter(n=>n.id!==id);
  graph.edges=graph.edges.filter(e=>e.from!==id&&e.to!==id);
  if(gSel&&gSel.id===id) gSel=null;
  gRefreshProps(); gDraw();
}
function gDeleteEdge(id) {
  graph.edges=graph.edges.filter(e=>e.id!==id);
  if(gSel&&gSel.id===id) gSel=null;
  gRefreshProps(); gDraw();
}

// -- Normalize ----------------------------------------------------------------
function gNormalize() {
  for (const n of graph.nodes) {
    const out=graph.edges.filter(e=>e.from===n.id); if(!out.length) continue;
    const auto=out.filter(e=>e.prob>0);
    const sum=auto.reduce((s,e)=>s+e.prob,0); if(!auto.length) continue;
    auto.forEach(e=>{e.prob=parseFloat((e.prob/sum).toFixed(4));});
  }
  if(gSel&&gSel.type==='edge') gRefreshEdgeProp(gFindEdge(gSel.id));
  gDraw(); gSetStatus('Normalized'); setTimeout(()=>gSetStatus(''),1800);
}

// -- Property panel -----------------------------------------------------------
function gRefreshProps() {
  const np=q('gNodeProp'),ep=q('gEdgeProp');
  if(!gSel){np.style.display='none';ep.style.display='none';return;}
  if(gSel.type==='node') {
    const n=gFindNode(gSel.id); if(!n) return;
    q('gNLabel').value=n.label||''; q('gNRoot').value=n.root||'';
    q('gNIsRoot').checked=!!n.isRoot;
    q('gNPhase').value=n.phase||'flat';
    q('gNInterval').value=n.frameIntervalMs||42;
    q('gNLoop').value=n.loopMode||'loop';
    np.style.display=''; ep.style.display='none';
  } else {
    const e=gFindEdge(gSel.id); if(!e) return;
    gRefreshEdgeProp(e); np.style.display='none'; ep.style.display='';
  }
}
let gEProbFocused = false;
function gRefreshEdgeProp(e) {
  if(!e) return;
  if(!gEProbFocused) q('gEProb').value=e.prob;
  const fn=gFindNode(e.from),tn=gFindNode(e.to);
  q('gEFromTo').textContent=(fn?fn.label:'?')+' -> '+(tn?tn.label:'?');
  const out=graph.edges.filter(e2=>e2.from===e.from);
  const autoOut=out.filter(e2=>e2.prob>0);
  const sum=autoOut.reduce((s,e2)=>s+e2.prob,0);
  const warn=q('gEWarn'); const manualHint=q('gEManual');
  manualHint.style.display = e.prob===0 ? '' : 'none';
  if(e.prob>0&&sum>0){warn.textContent='Normalized chance: '+(e.prob/sum*100).toFixed(1)+'%';warn.style.display='';}
  else warn.style.display='none';
}

// -- Populate from allClips ---------------------------------------------------
function gPopulate() {
  const seen=new Set(graph.nodes.map(n=>n.root).filter(Boolean));
  let added=0;
  for (const uid of Object.keys(allClips)) {
    const sep=uid.indexOf('||'); if(sep<0) continue;
    const root=uid.slice(0,sep);
    if(seen.has(root)) continue; seen.add(root);
    const parts=root.replace(/\\/g,'/').split('/');
    const pi=parts.findIndex(p=>p==='projects');
    let lbl=pi>=0?parts[pi+1]:parts[parts.length-1];
    lbl=parts.slice(-2).join("_");
    if(graph.nodes.some(n=>n.label===lbl)) lbl += "_" + graph.nodes.length;
    const i=graph.nodes.length;
    graph.nodes.push({id:gUid(),label:lbl,root,isRoot:graph.nodes.length===0,x:70+(i%3)*155,y:70+Math.floor(i/3)*110});
    added++;
  }
  if(added){gSetStatus('+'+added+' nodes added');setTimeout(()=>gSetStatus(''),2000);}
  else gSetStatus('No new states (load a project first)');
  gDraw();
}

// -- Save / Load --------------------------------------------------------------
async function gSaveGraph() {
  try {
    const r=await fetch('/api/graph',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(graph)});
    const d=await r.json();
    if(d.ok){graph=d.graph;gRefreshProps();gDraw();} gSetStatus(d.ok?'Saved':'Error: '+d.error);
  } catch(ex){gSetStatus('Save failed');}
}
async function gLoadGraph() {
  try {
    const r=await fetch('/api/graph'),d=await r.json();
    if(d.ok&&d.graph){graph=d.graph;gSel=null;gRefreshProps();gDraw();gSetStatus(graphReadOnly?'Runtime pack · read only':'Loaded');}else gSetStatus('Error: '+d.error);
  } catch(ex){gSetStatus('Load failed');}
}


async function previewNode(node) {
  stop();
  const generation=previewGeneration;
  try {
    const response=await fetch('/api/preview-node',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({graph,nodeId:node.id})});
    const result=await response.json();
    if(generation!==previewGeneration)return;
    if(!result.ok){gSetStatus('Error: '+result.error);return;}
    const frames=result.frames;
    let index=0;
    const show=()=>{SpriteForgeMedia.show(frames[index]);setNow(`${result.node.label} ${index+1}/${frames.length}`,frames[index]);};
    show();
    timer=setInterval(()=>{
      if(SpriteForgeMedia.busy)return;
      if(index===frames.length-1 && result.node.loopMode==='once_then_hold'){stop();return;}
      index=(index+1)%frames.length;show();
    }, result.node.frameIntervalMs);
    gSetStatus('Exact selected clip · '+result.node.frameIntervalMs+' ms · '+result.node.loopMode);
  }catch(e){gSetStatus('Preview failed: '+e);}
}

// -- Init ---------------------------------------------------------------------
function gInitGraph() {
  const cv=q('graphCanvas'); if(!cv) return;
  cv.addEventListener('mousedown',  gOnDown);
  cv.addEventListener('mousemove',  gOnMove);
  cv.addEventListener('mouseup',    gOnUp);
  cv.addEventListener('dblclick',   gOnDbl);
  cv.addEventListener('contextmenu',gOnCtx);
  window.addEventListener('resize',()=>{if(q('graphPanel').style.display!=='none')gResize();});
  q('gModeSelect').addEventListener('click',()=>gSetMode('select'));
  q('gModeNode').addEventListener('click',  ()=>gSetMode('node'));
  q('gModeEdge').addEventListener('click',  ()=>gSetMode('edge'));
  q('gNormalize').addEventListener('click', gNormalize);
  q('gPopulate').addEventListener('click',  gPopulate);
  q('gResetView').addEventListener('click', ()=>{ gPan={x:0,y:0}; gDraw(); });
  q('gSave').addEventListener('click',      gSaveGraph);
  q('gLoad').addEventListener('click',      gLoadGraph);
  q('gValidate').addEventListener('click', async()=>{try {const res=await fetch('/api/validate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(graph)});const d=await res.json();gSetStatus(d.ok?'Valid topology and frame bindings':'Error: '+d.error);}catch(e){gSetStatus(String(e));}});
  q('gClear').addEventListener('click',()=>{
    if(!confirm('Clear all nodes and edges?')) return;
    graph={nodes:[],edges:[]};gSel=null;gRefreshProps();gDraw();
  });
  q('gNLabel').addEventListener('input',()=>{
    const n=gSel&&gSel.type==='node'&&gFindNode(gSel.id);
    if(n){n.label=q('gNLabel').value;gDraw();}
  });
  q('gNIsRoot').addEventListener('change',()=>{
    const n=gSel&&gSel.type==='node'&&gFindNode(gSel.id);
    if(n){if(q('gNIsRoot').checked) graph.nodes.forEach(other=>other.isRoot=false); n.isRoot=q('gNIsRoot').checked;gDraw();}
  });
  q('gNRoot').addEventListener('change',()=>{
    const n=gSel&&gSel.type==='node'&&gFindNode(gSel.id);
    if(n) n.root=q('gNRoot').value;
  });
  q('gNView').addEventListener('click',()=>{
    const n=gSel&&gSel.type==='node'&&gFindNode(gSel.id);
    if(n&&n.root) previewNode(n);
  });
  for(const [id,key] of [['gNPhase','phase'],['gNInterval','frameIntervalMs'],['gNLoop','loopMode']]) {
    q(id).addEventListener('change',()=>{const n=gSel&&gFindNode(gSel.id);if(n)n[key]=key==='frameIntervalMs'?Number(q(id).value):q(id).value;});
  }
  q('gNDel').addEventListener('click',()=>{if(gSel&&gSel.type==='node')gDeleteNode(gSel.id);});
  q('gEProb').addEventListener('focus', ()=>{ gEProbFocused=true; });
  q('gEProb').addEventListener('blur',  ()=>{ gEProbFocused=false; });
  q('gEProb').addEventListener('input',()=>{
    const e=gSel&&gSel.type==='edge'&&gFindEdge(gSel.id);
    if(e){const v=parseFloat(q('gEProb').value);if(!isNaN(v)){e.prob=v;gRefreshEdgeProp(e);gDraw();}}
  });
  q('gEDel').addEventListener('click',()=>{if(gSel&&gSel.type==='edge')gDeleteEdge(gSel.id);});
}

// ── Inspector 拖拽调宽 ────────────────────────────────────────────────────────
(function() {
  const handle = q('inspResizeHandle');
  const insp   = document.querySelector('section.inspector');
  let dragging = false, startX = 0, startW = 0;
  handle.addEventListener('mousedown', e => {
    dragging = true; startX = e.clientX;
    const cols = getComputedStyle(document.querySelector('main')).gridTemplateColumns.split(' ');
    startW = parseInt(cols[2]) || insp.offsetWidth;
    handle.classList.add('dragging');
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    e.preventDefault();
  });
  document.addEventListener('mousemove', e => {
    if (!dragging) return;
    const dx  = startX - e.clientX;          // 向左拖 → dx 正 → 变宽
    const newW = Math.max(280, Math.min(window.innerWidth * 0.85, startW + dx));
    document.querySelector('main').style.gridTemplateColumns = `310px 1fr ${newW}px`;
    if (q('graphPanel').style.display !== 'none') gResize();
  });
  document.addEventListener('mouseup', () => {
    if (!dragging) return;
    dragging = false;
    handle.classList.remove('dragging');
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  });
})();

gInitGraph();
gLoadGraph();

// 启动
loadSources();
