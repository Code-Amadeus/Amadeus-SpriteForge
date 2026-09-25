"use strict";
// Production page: approve pose stills, review video takes, edit prompt versions and run jobs.
const $ = (id) => document.getElementById(id);
const media = (path) => "/api/production/media?path=" + encodeURIComponent(path);
const frameUrl = (path) => "/frame?path=" + encodeURIComponent(path);
const selection = { pose: null, poseTake: null, clip: null };
let state = null;
let jobs = [];
let jobTimer = null;
let previewTimer = null;
let wasRunning = false;

function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") el.className = value;
    else if (key === "value") el.value = value;
    else if (key === "checked") el.checked = true;
    else if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else el.setAttribute(key, value === true ? "" : value);
  }
  return append(el, children);
}

function append(el, children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

// Like replaceChildren, but nested arrays are flattened and empty values skipped.
function fill(el, ...children) {
  el.replaceChildren();
  return append(el, children);
}

const badge = (text, kind) => h("span", { class: `badge ${kind || text}` }, text);
const blockVersions = (blocks) => Object.entries(blocks || {}).map(([b, v]) => `${b} v${v}`).join(", ");
const stillFile = (pose, take) => `production/poses/${pose.id}/takes/${take.id}/${take.media.still}`;
const takeFile = (clip, take, name) => `production/clips/${clip.id}/takes/${take.id}/${name}`;

async function api(path, body) {
  const options = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const response = await fetch(path, options);
  const data = await response.json();
  if (!data.ok) throw new Error(data.error || response.statusText);
  return data;
}

function toast(message, error = false) {
  const el = $("toast");
  el.textContent = message;
  el.className = error ? "error" : "";
  el.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { el.hidden = true; }, error ? 10000 : 3500);
}

async function run(action, message) {
  try {
    const result = await action();
    if (message) toast(message);
    await refresh();
    return result;
  } catch (error) {
    toast(String(error.message || error), true);
    return null;
  }
}

async function refresh() {
  state = await api("/api/production");
  render();
}

function render() {
  if (!state.initialized) {
    $("notice").hidden = false;
    $("notice").textContent = "This workspace has no production character. Run: spriteforge production init --workspace <path> --id <id> --display-name <name> --canvas <W>x<H>";
    document.querySelectorAll(".tab").forEach((tab) => { tab.hidden = true; });
    return;
  }
  const c = state.character;
  $("title").textContent = `${c.displayName} production`;
  $("canvasInfo").textContent = `canvas ${c.canvas.width}×${c.canvas.height} · base pose ${c.basePose}` +
    (c.anchors ? ` · head top ${c.anchors.headTopY}px · head centre ${c.anchors.headCenterX}px` : " · base still not approved");
  renderTools();
  renderPoses();
  renderClips();
  renderPrompts();
  renderJobs();
}

function renderTools() {
  const tools = state.tools;
  fill($("tools"),
    ...["ffmpeg", "alpha", "interpolate"].map((k) => badge(`${k} ${tools[k] ? "✓" : "✗"}`, tools[k] ? "yes" : "no")),
    ...Object.entries(tools.providers).map(([name, p]) => badge(`${name} key ${p.keySet ? "set" : "missing"}`, p.keySet ? "yes" : "missing")));
}

// ── Stills ─────────────────────────────────────────────────────────────
function acceptedStill(poseId) {
  const pose = state.poses.find((p) => p.id === poseId);
  const take = pose && pose.takes.find((t) => t.status === "accepted");
  return take ? stillFile(pose, take) : null;
}

function poseStatus(pose) {
  if (pose.needsRecheck) return ["re-check", "watch"];
  if (pose.acceptedTake) return ["approved", "accepted"];
  return [pose.takes.length ? "needs approval" : "no still", "pending"];
}

function renderPoses() {
  const poses = state.poses;
  if (!poses.some((p) => p.id === selection.pose)) selection.pose = poses.length ? poses[0].id : null;
  fill($("poseList"), ...poses.map((pose) => {
    const [text, kind] = poseStatus(pose);
    return h("div", { class: "item" + (pose.id === selection.pose ? " active" : ""), "data-pose": pose.id,
      onclick: () => { selection.pose = pose.id; selection.poseTake = null; renderPoses(); } },
    h("div", { class: "row" }, h("strong", {}, pose.id + (pose.id === state.character.basePose ? " (base)" : "")), badge(text, kind)),
    h("div", { class: "tiny" }, `${pose.takes.length} take(s)` + (pose.description ? ` · ${pose.description}` : "")));
  }));
  renderPoseDetail(poses.find((p) => p.id === selection.pose));
}

function renderPoseDetail(pose) {
  const root = $("poseDetail");
  if (!pose) { fill(root, h("p", { class: "muted" }, "Add a pose to start.")); return; }
  const ready = pose.takes.filter((t) => t.state === "ready" && t.media && t.media.still);
  const current = ready.find((t) => t.id === selection.poseTake) || ready.find((t) => t.status === "accepted") || ready[ready.length - 1];
  selection.poseTake = current ? current.id : null;
  const upload = h("input", { type: "file", accept: "image/png,image/jpeg,image/webp", id: "stillUpload",
    onchange: (e) => uploadFile("pose", pose.id, e.target.files[0]) });
  const expected = pose.expected || {};
  fill(root,
    h("div", { class: "row" }, h("h2", {}, pose.id), pose.description ? h("span", { class: "muted" }, pose.description) : null,
      Object.keys(expected).length ? badge("intended offset " + JSON.stringify(expected), "watch") : null,
      pose.needsRecheck ? badge("base anchors changed: approve again", "watch") : null),
    h("div", { class: "row", style: "margin:8px 0" }, h("label", { class: "tiny" }, "Import a generated still ", upload)),
    current ? comparePanel(pose, current) : h("p", { class: "muted" }, "No normalised still yet. Import a generated or edited image."),
    h("h3", {}, "Takes"),
    h("div", { class: "grid" }, pose.takes.slice().reverse().map((t) => poseTakeCard(pose, t, t.id === selection.poseTake))),
    h("h3", {}, pose.id === state.character.basePose ? "Prompt" : "Prompt for the still editor (input: the base still)"),
    promptView(pose.promptPreview));
}

function comparePanel(pose, take) {
  const { width, height } = state.character.canvas;
  const canvas = h("canvas", { width, height, id: "compareCanvas" });
  const mode = h("select", { id: "compareMode" }, ["overlay", "difference", "take only", "base only"].map((m) => h("option", { value: m }, m)));
  const opacity = h("input", { type: "range", min: 0, max: 100, value: 50 });
  const images = {};
  const load = (key, path) => new Promise((resolve) => {
    if (!path) { resolve(); return; }
    const img = new Image();
    img.onload = () => { images[key] = img; resolve(); };
    img.onerror = () => resolve();
    img.src = media(path);
  });
  const draw = () => {
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, width, height);
    if (images.base && mode.value !== "take only") ctx.drawImage(images.base, 0, 0);
    if (images.take && mode.value !== "base only") {
      ctx.globalCompositeOperation = mode.value === "difference" ? "difference" : "source-over";
      ctx.globalAlpha = mode.value === "overlay" && images.base ? opacity.value / 100 : 1;
      ctx.drawImage(images.take, 0, 0);
      ctx.globalCompositeOperation = "source-over";
      ctx.globalAlpha = 1;
    }
    guides(ctx, pose);
  };
  mode.onchange = draw;
  opacity.oninput = draw;
  const base = pose.id === state.character.basePose ? null : acceptedStill(state.character.basePose);
  Promise.all([load("base", base), load("take", stillFile(pose, take))]).then(draw);
  return h("div", { class: "compare" }, canvas,
    h("div", {},
      h("div", { class: "row" }, "View", mode, "Opacity", opacity),
      h("p", { class: "tiny" }, "Cyan: base head top and head centre. Amber: this pose's intended offset. " +
        "Only the character's cut edges (" + state.character.cutEdges.join(", ") + ") may touch the canvas."),
      take.qa ? metricsTable(pose, take.qa.metrics) : null,
      qaList(take.qa)));
}

function guides(ctx, pose) {
  const anchors = state.character.anchors;
  if (!anchors) return;
  const line = (color, x0, y0, x1, y1) => {
    ctx.strokeStyle = color; ctx.lineWidth = 1; ctx.setLineDash([6, 4]);
    ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke(); ctx.setLineDash([]);
  };
  const { width, height } = ctx.canvas;
  line("#39d0ff", 0, anchors.headTopY + 0.5, width, anchors.headTopY + 0.5);
  line("#39d0ff", anchors.headCenterX, 0, anchors.headCenterX, height);
  const expected = pose.expected || {};
  if (expected.headTopY !== undefined) line("#f3bb4c", 0, expected.headTopY + 0.5, width, expected.headTopY + 0.5);
  if (expected.headCenterX !== undefined) line("#f3bb4c", expected.headCenterX, 0, expected.headCenterX, height);
}

function metricsTable(pose, metrics) {
  const anchors = state.character.anchors || {};
  const expected = { ...anchors, ...(pose.expected || {}) };
  const row = (name, value, target) => h("tr", {}, h("td", {}, name), h("td", {}, value),
    h("td", {}, target === undefined ? "—" : target), h("td", {}, target === undefined ? "—" : (value - target).toFixed(2)));
  return h("table", {}, h("tr", {}, h("th", {}, "Metric"), h("th", {}, "This still"), h("th", {}, "Expected"), h("th", {}, "Δ")),
    row("head top (px)", metrics.headTopY, expected.headTopY),
    row("head centre (px)", metrics.headCenterX, expected.headCenterX),
    row("visible area", metrics.area, anchors.area),
    h("tr", {}, h("td", {}, "edges touched"), h("td", { colspan: 3 }, metrics.edges.join(", ") || "none")));
}

function poseTakeCard(pose, take, selected) {
  return h("div", { class: "card" + (selected ? " selected" : ""), "data-take": take.id },
    take.media && take.media.still ? h("img", { class: "thumb", src: media(stillFile(pose, take)),
      onclick: () => { selection.poseTake = take.id; renderPoses(); } }) : null,
    h("div", { class: "row" }, badge(take.status), take.qa ? badge("QA " + take.qa.status, take.qa.status) : null,
      h("span", { class: "tiny" }, take.id)),
    h("div", { class: "tiny" }, [take.source && take.source.note, take.normalization && take.normalization.method].filter(Boolean).join(" · ")),
    take.error ? h("div", { class: "tiny", style: "color:var(--bad)" }, take.error) : null,
    take.rejected ? h("div", { class: "tiny" }, "Rejected: " + (take.rejected.reason || "no reason given")) : null,
    h("div", { class: "row actions" }, decisionButtons("pose", pose.id, take)));
}

function decisionButtons(kind, owner, take) {
  if (take.state !== "ready") return [];
  const decide = (action) => async () => {
    let reason = "";
    if (action === "reject") {
      reason = window.prompt("Why is this take rejected? It stays in the archive with this note.", "");
      if (reason === null) return;
    }
    await run(() => api("/api/production/decision", { kind, owner, take: take.id, action, reason }),
      `${action === "accept" ? "Accepted" : action === "reject" ? "Archived" : "Restored"} ${take.id}`);
  };
  return [
    take.status === "candidate" ? h("button", { class: "primary", onclick: decide("accept") }, kind === "pose" ? "Approve still" : "Use this take") : null,
    take.status !== "rejected" ? h("button", { class: "danger", onclick: decide("reject") }, "Reject & archive") : null,
    take.status === "rejected" ? h("button", { onclick: decide("restore") }, "Restore") : null,
  ];
}

// ── Clips ──────────────────────────────────────────────────────────────
function renderClips() {
  const clips = state.clips;
  if (!clips.some((c) => c.id === selection.clip)) selection.clip = clips.length ? clips[0].id : null;
  fill($("clipList"), ...clips.map((clip) => h("div", {
    class: "item" + (clip.id === selection.clip ? " active" : ""), "data-clip": clip.id,
    onclick: () => { selection.clip = clip.id; renderClips(); } },
  h("div", { class: "row" }, h("strong", {}, clip.id), badge(clip.render.state),
    clip.render.qa ? badge("QA " + clip.render.qa.status, clip.render.qa.status) : null),
  h("div", { class: "tiny" }, `${clip.from} → ${clip.to} · ${clip.kind} · ${clip.takes.length} take(s)` +
    (clip.acceptedTake ? "" : " · no take chosen")))));
  renderClipDetail(clips.find((c) => c.id === selection.clip));
}

function generateHint(clip, provider) {
  if (clip.generation.provider === "manual") return "Manual clips: copy the prompt and inputs into your generator, then import the video";
  if (!clip.promptPreview.complete) return "Write the prompt placeholders first";
  if (!provider || !provider.keySet) return `Set the API key environment variable for ${clip.generation.provider}`;
  return "";
}

function renderClipDetail(clip) {
  const root = $("clipDetail");
  clearInterval(previewTimer);
  if (!clip) { fill(root, h("p", { class: "muted" }, "Add a clip between two approved poses.")); return; }
  const provider = state.tools.providers[clip.generation.provider];
  const hint = generateHint(clip, provider);
  const upload = h("input", { type: "file", accept: "video/mp4,video/webm,video/quicktime", id: "takeUpload",
    onchange: (e) => uploadFile("clip", clip.id, e.target.files[0]) });
  const active = clip.takes.filter((t) => t.status !== "rejected").reverse();
  const archived = clip.takes.filter((t) => t.status === "rejected").reverse();
  fill(root,
    h("div", { class: "row" }, h("h2", {}, clip.id), h("span", { class: "muted" }, `${clip.from} → ${clip.to} · ${clip.kind} · phase ${clip.phase}`)),
    h("div", { class: "inputs", style: "max-width:320px" }, endpoint(clip.from, "first frame"), endpoint(clip.to, "last frame")),
    h("h3", {}, "Settings"), settingsForm(clip),
    h("h3", {}, "Prompt"), promptView(clip.promptPreview),
    h("div", { class: "row", style: "margin-top:8px" },
      h("button", { class: "primary", id: "generateBtn", disabled: Boolean(hint), title: hint, onclick: () => generate(clip) },
        clip.generation.provider === "manual" ? "Manual provider" : `Generate with ${clip.generation.provider}`),
      h("label", { class: "tiny" }, "Import a take ", upload),
      h("button", { id: "renderBtn", disabled: !clip.acceptedTake, onclick: () => startJob("render", clip.id) }, "Render accepted take")),
    hint ? h("div", { class: "tiny" }, hint) : null,
    h("h3", {}, "Takes"),
    active.length ? h("div", { class: "grid" }, active.map((t) => clipTakeCard(clip, t))) : h("p", { class: "muted" }, "No takes yet."),
    archived.length ? h("details", {}, h("summary", {}, `Archive (${archived.length} rejected)`),
      h("div", { class: "grid" }, archived.map((t) => clipTakeCard(clip, t)))) : null,
    h("h3", {}, "Render"), renderPanel(clip));
}

function endpoint(poseId, label) {
  const path = acceptedStill(poseId);
  return h("div", {}, h("div", { class: "tiny" }, `${label}: ${poseId}`),
    path ? h("img", { src: media(path) }) : badge("still not approved", "missing"));
}

function settingsForm(clip) {
  const fields = [
    ["provider", "Provider", "select", clip.generation.provider, ["manual", ...Object.keys(state.tools.providers)]],
    ["duration", "Duration (s)", "number", clip.generation.durationS],
    ["resolution", "Resolution", "text", clip.generation.resolution],
    ["seed", "Seed", "number", clip.generation.seed ?? ""],
    ["input_scale", "Input scale", "number", clip.generation.inputScale],
    ["interpolate", "Interpolate ×", "number", clip.processing.interpolate],
    ["lock_head", "Lock head frames", "number", clip.processing.lockHeadFrames],
    ["lock_tail", "Lock tail frames", "number", clip.processing.lockTailFrames],
    ["edge_guard", "Edge guard (px)", "number", clip.processing.edgeGuardPx],
    ["speed", "Playback speed", "number", clip.playback.speed],
    ["loop_mode", "Playback", "select", clip.playback.loopMode, ["loop", "once_then_hold"]],
  ];
  if (clip.kind === "loop") fields.push(["pingpong", "Pingpong loop", "checkbox", clip.processing.pingpong]);
  const inputs = {};
  const form = h("div", { class: "form" }, fields.map(([key, label, type, value, options]) => {
    const input = type === "select" ? h("select", {}, options.map((o) => h("option", { value: o }, o)))
      : h("input", { type, step: "any", value: type === "checkbox" ? null : value, checked: type === "checkbox" && value });
    if (type === "select") input.value = value;
    inputs[key] = [input, type];
    return h("label", {}, label, input);
  }));
  const save = h("button", { onclick: () => {
    const changes = {};
    for (const [key, [input, type]] of Object.entries(inputs)) {
      if (type === "checkbox") changes[key] = input.checked;
      else if (type === "number") { if (input.value !== "") changes[key] = Number(input.value); }
      else changes[key] = input.value;
    }
    run(() => api("/api/production/clip-settings", { clip: clip.id, changes }), "Settings saved");
  } }, "Save settings");
  return h("div", {}, form, h("div", { class: "row actions" }, save,
    h("span", { class: "tiny" }, "Changing processing or playback makes the current render stale.")));
}

function clipTakeCard(clip, take) {
  const m = take.media || {};
  const preview = m.video ? h("video", { src: media(takeFile(clip, take, m.video)), controls: true, loop: true, muted: true, preload: "metadata" })
    : m.dir ? h("img", { class: "thumb", src: media(takeFile(clip, take, `${m.dir}/000000.png`)) })
    : h("div", { class: "tiny" }, take.state);
  const source = take.source || {};
  return h("div", { class: "card" + (take.status === "accepted" ? " selected" : ""), "data-take": take.id }, preview,
    h("div", { class: "row" }, badge(take.status), h("span", { class: "tiny" }, take.id)),
    h("div", { class: "tiny" }, [source.provider, source.model, source.taskId, m.count && `${m.count} frames @ ${m.fps} fps`,
      m.width && `${m.width}×${m.height}`, source.note].filter(Boolean).join(" · ")),
    take.error ? h("div", { class: "tiny", style: "color:var(--bad)" }, take.error) : null,
    take.rejected ? h("div", { class: "tiny" }, "Rejected: " + (take.rejected.reason || "no reason given")) : null,
    take.prompt ? h("details", {}, h("summary", {}, "Prompt snapshot"), promptView(take.prompt, true)) : null,
    take.inputs && take.inputs.first && take.inputs.first.file ? h("details", {},
      h("summary", {}, "First / last frame inputs" + (take.inputs.assumed ? " (handed to an external tool)" : "")),
      h("div", { class: "inputs" }, h("img", { src: media(takeFile(clip, take, take.inputs.first.file)) }),
        h("img", { src: media(takeFile(clip, take, take.inputs.last.file)) }))) : null,
    take.state === "submitted" ? h("button", { onclick: () => startJob("resume", clip.id, { take: take.id }) }, "Resume download") : null,
    h("div", { class: "row actions" }, decisionButtons("clip", clip.id, take)));
}

function renderPanel(clip) {
  const r = clip.render;
  const box = h("div", {}, h("div", { class: "row" }, badge(r.state),
    r.state !== "current" ? h("span", { class: "tiny" }, (r.reasons || []).join("; ")) : null,
    r.frameCount ? h("span", { class: "tiny" }, `${r.frameCount} frames · ${r.frameIntervalMs} ms/frame · ${r.loopMode} · take ${r.take}`) : null));
  if (r.frameCount) {
    const img = h("img", { class: "player", id: "renderPreview" });
    box.append(h("div", { class: "tiny" }, "Preview is capped at 30 fps; runtime timing is shown above."), img, qaList(r.qa), seamTable(r.qa));
    playOutput(clip, img, r);
  }
  return box;
}

async function playOutput(clip, img, render) {
  try {
    const data = await api("/api/clips?root=" + encodeURIComponent(clip.output));
    const frames = (Object.values(data.clips)[0] || {}).frames || [];
    let index = 0;
    let hold = 0;
    clearInterval(previewTimer);
    previewTimer = setInterval(() => {
      if (!frames.length || !document.body.contains(img)) { clearInterval(previewTimer); return; }
      img.src = frameUrl(frames[index]);
      if (index < frames.length - 1) index += 1;
      else if (render.loopMode === "loop" || ++hold > 30) { index = 0; hold = 0; }
    }, Math.max(33, render.frameIntervalMs));
  } catch (error) {
    img.replaceWith(h("div", { class: "tiny" }, String(error.message || error)));
  }
}

function qaList(qa) {
  if (!qa) return null;
  return h("div", {}, h("div", { class: "row" }, badge("QA " + qa.status, qa.status)),
    (qa.checks || []).map((c) => h("div", { class: "row tiny" }, badge(c.level), c.message)));
}

function seamTable(qa) {
  const rows = ["head", "tail", "wrap"].filter((k) => qa && qa[k]);
  if (!rows.length) return null;
  return h("table", {}, h("tr", {}, h("th", {}, "Seam"), h("th", {}, "Level"), h("th", {}, "Face L*"), h("th", {}, "Δ head top"), h("th", {}, "Δ head centre")),
    rows.map((k) => h("tr", {}, h("td", {}, k), h("td", {}, badge(qa[k].level)), h("td", {}, qa[k].faceL ?? "—"),
      h("td", {}, qa[k].dHeadTop), h("td", {}, qa[k].dHeadCenter))));
}

async function generate(clip) {
  const provider = state.tools.providers[clip.generation.provider];
  const ok = window.confirm(`Submit a paid generation of ${clip.id} to ${clip.generation.provider} (${provider.model}), ` +
    `${clip.generation.durationS}s at ${clip.generation.resolution}?`);
  if (ok) await startJob("generate", clip.id);
}

// ── Prompts ────────────────────────────────────────────────────────────
function highlighted(text) {
  const parts = [];
  const pattern = /\{\{\s*PLACEHOLDER\s*:[\s\S]*?\}\}/g;
  let last = 0;
  let match;
  while ((match = pattern.exec(text))) {
    parts.push(text.slice(last, match.index), h("mark", {}, match[0]));
    last = match.index + match[0].length;
  }
  parts.push(text.slice(last));
  return parts;
}

function promptView(p, compact = false) {
  if (p.error) return h("div", { class: "prompt" }, badge("template error", "fail"), " ", p.error);
  return h("div", { class: "prompt-view" },
    h("div", { class: "row" }, badge(p.complete ? "complete" : `${p.placeholders.length} placeholder(s)`, p.complete ? "pass" : "watch"),
      h("span", { class: "tiny" }, blockVersions(p.blocks)),
      compact ? null : h("button", { onclick: () => navigator.clipboard.writeText(p.text).then(() => toast("Prompt copied")) }, "Copy prompt")),
    h("div", { class: "prompt" }, highlighted(p.text)),
    p.negative ? h("div", { class: "prompt" }, h("span", { class: "tiny" }, "Negative: "), highlighted(p.negative)) : null);
}

function renderPrompts() {
  const library = state.prompts;
  const usage = {};
  for (const owner of [...state.poses, ...state.clips]) {
    for (const take of owner.takes) {
      for (const [block, version] of Object.entries((take.prompt && take.prompt.blocks) || {})) {
        usage[`${block}@${version}`] = (usage[`${block}@${version}`] || 0) + 1;
      }
    }
  }
  const rank = (id) => (id.startsWith("pose.") ? 1 : id.startsWith("clip.") ? 2 : 0);
  const ids = Object.keys(library.blocks).sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));
  fill($("promptList"),
    h("h2", {}, "Prompt library"),
    h("p", { class: "tiny" }, "Saving a block adds a version; takes keep the exact text and versions they used. " +
      "Prompts containing {{PLACEHOLDER: ...}} are never sent to a paid provider."),
    h("table", {}, h("tr", {}, h("th", {}, "Template"), h("th", {}, "Blocks"), h("th", {}, "Negative")),
      Object.entries(library.templates).map(([id, t]) => h("tr", {}, h("td", {}, id), h("td", {}, t.blocks.join(" + ")),
        h("td", {}, (t.negative || []).join(" + "))))),
    ids.map((id) => blockCard(id, library.blocks[id], usage)));
}

function blockCard(id, block, usage) {
  const current = block.versions[block.versions.length - 1];
  const area = h("textarea", { value: current.text, "data-block": id });
  const save = h("button", { class: "primary", disabled: true,
    onclick: () => run(() => api("/api/production/prompt", { block: id, text: area.value }), `${id}: new version saved`) }, "Save as new version");
  area.oninput = () => { save.disabled = area.value === current.text; };
  const placeholders = (current.text.match(/\{\{\s*PLACEHOLDER\s*:/g) || []).length;
  return h("div", { class: "card", style: "margin-top:12px" },
    h("div", { class: "row" }, h("strong", {}, id), badge(`v${current.version}`, "candidate"),
      placeholders ? badge(`${placeholders} placeholder`, "watch") : badge("written", "pass"),
      h("span", { class: "tiny" }, block.description || "")),
    area,
    h("div", { class: "row actions" }, save, h("span", { class: "tiny" }, `used by ${usage[`${id}@${current.version}`] || 0} take(s) at this version`)),
    block.versions.length > 1 ? h("details", {}, h("summary", {}, `History (${block.versions.length} versions)`),
      block.versions.slice().reverse().map((v) => h("div", {},
        h("div", { class: "tiny" }, `v${v.version} · ${v.createdAt} · used by ${usage[`${id}@${v.version}`] || 0} take(s)`),
        h("pre", {}, v.text || "(empty)")))) : null);
}

// ── Jobs, uploads and planning ─────────────────────────────────────────
async function startJob(action, clip, extra = {}) {
  await run(() => api("/api/production/jobs", { action, clip, ...extra }), `${action} started for ${clip}`);
  pollJobs();
}

async function pollJobs() {
  try {
    jobs = (await api("/api/production/jobs")).jobs;
  } catch (error) {
    return;
  }
  renderJobs();
  const running = jobs.some((j) => j.status === "running");
  clearTimeout(jobTimer);
  if (running) jobTimer = setTimeout(pollJobs, 1500);
  else if (wasRunning) refresh();
  wasRunning = running;
}

function renderJobs() {
  const running = jobs.filter((j) => j.status === "running").length;
  $("jobBadge").hidden = !running;
  $("jobBadge").textContent = String(running);
  fill($("jobList"), h("h2", {}, "Jobs"), jobs.length ? jobs.map((j) => h("div", { class: "card", style: "margin-top:10px" },
    h("div", { class: "row" }, h("strong", {}, `${j.action} ${j.clip}`),
      badge(j.status, j.status === "succeeded" ? "pass" : j.status === "failed" ? "fail" : "pending"),
      h("span", { class: "tiny" }, j.startedAt), j.result ? h("span", { class: "tiny" }, "result: " + j.result) : null),
    j.error ? h("pre", {}, j.error) : null,
    j.log.length ? h("pre", {}, j.log.slice(-40).join("\n")) : null)) : h("p", { class: "muted" }, "No jobs in this session."));
}

async function uploadFile(kind, owner, file) {
  if (!file) return;
  const params = new URLSearchParams({ kind, owner, name: file.name });
  await run(async () => {
    const response = await fetch("/api/production/upload?" + params, {
      method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: file });
    const data = await response.json();
    if (!data.ok) throw new Error(data.error);
    if (kind === "pose") selection.poseTake = data.take.id;
    return data;
  }, `Imported ${file.name}`);
}

function showTab(name) {
  if (!["stills", "clips", "prompts", "jobs"].includes(name)) name = "stills";
  document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".tab").forEach((tab) => { tab.hidden = tab.id !== "tab-" + name; });
  history.replaceState(null, "", "#" + name);
}

document.querySelectorAll("#tabs button").forEach((button) => button.addEventListener("click", () => showTab(button.dataset.tab)));
$("addPose").addEventListener("click", () => {
  const id = window.prompt("New pose id (lowercase letters, digits, _ or -)");
  if (!id) return;
  const description = window.prompt("Short description (optional)", "") || "";
  run(() => api("/api/production/pose", { id, description }), `Pose ${id} added`).then(() => { selection.pose = id; renderPoses(); });
});
$("addClip").addEventListener("click", () => {
  const poses = state.poses.map((p) => p.id).join(", ");
  const from = window.prompt(`Start pose (${poses})`, state.character.basePose);
  if (!from) return;
  const to = window.prompt(`End pose (${poses}); the same pose makes a loop`, from);
  if (!to) return;
  const id = window.prompt("Clip id", from === to ? `${to}_loop` : `${from}_to_${to}`);
  if (!id) return;
  run(() => api("/api/production/clip", { id, from, to }), `Clip ${id} added`).then(() => { selection.clip = id; showTab("clips"); renderClips(); });
});
$("graphSync").addEventListener("click", () => {
  const addMissing = window.confirm("Also add graph nodes for rendered clips that are not in the graph yet? (Edges stay yours to draw.)");
  run(async () => {
    const result = await api("/api/production/graph-sync", { addMissing });
    toast([...result.changes.map((c) => "updated " + c), ...result.added.map((c) => "added " + c),
      ...result.notRendered.map((c) => "not rendered: " + c)].join("\n") || "Graph already matches the rendered clips");
  });
});

showTab((location.hash || "#stills").slice(1));
refresh().then(pollJobs).catch((error) => toast(String(error.message || error), true));
