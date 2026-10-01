"use strict";
// Production page: the canvas of poses and clips, still approval, video takes, prompt versions and jobs.
// Only the visible tab is drawn: detail views share element ids (render preview, uploads).
const $ = (id) => document.getElementById(id);
const TABS = ["canvas", "stills", "clips", "prompts", "jobs"];
let activeTab = "canvas";
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
  renderActive();
}

function renderActive() {
  if (!state || !state.initialized) return;
  clearInterval(previewTimer);
  if (activeTab !== "stills") { fill($("poseList")); fill($("poseDetail")); }
  if (activeTab !== "clips") { fill($("clipList")); fill($("clipDetail")); }
  if (activeTab !== "prompts") fill($("promptList"));
  if (activeTab !== "canvas") clearCanvas();
  if (activeTab === "canvas") renderCanvas();
  else if (activeTab === "stills") renderPoses();
  else if (activeTab === "clips") renderClips();
  else if (activeTab === "prompts") renderPrompts();
  renderJobs();
}

function renderTools() {
  const tools = state.tools;
  fill($("tools"),
    ...["ffmpeg", "alpha", "interpolate"].map((k) => badge(`${k} ${tools[k] ? "✓" : "✗"}`, tools[k] ? "yes" : "no")),
    ...Object.entries(tools.providers).map(([name, p]) => badge(p.credential === "login" ? `${name} ${p.keySet ? "logged in" : "not logged in"}`
      : `${name} key ${p.keySet ? "set" : "missing"}`, p.keySet ? "yes" : "missing")));
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

function renderPoseDetail(pose, root = $("poseDetail")) {
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
    h("div", { class: "row", style: "margin:8px 0" }, stillGenerateControl(pose),
      h("label", { class: "tiny" }, "Import a generated still ", upload), closedMouthControl(pose)),
    current ? comparePanel(pose, current) : h("p", { class: "muted" }, "No normalised still yet. Import a generated or edited image."),
    h("h3", {}, "Takes"),
    h("div", { class: "grid" }, pose.takes.slice().reverse().map((t) => poseTakeCard(pose, t, t.id === selection.poseTake))),
    h("h3", {}, pose.id === state.character.basePose ? "Prompt" : "Prompt for the still editor (input: the base still)"),
    promptView(pose.promptPreview));
}

function stillGenerateHint(pose, name) {
  const provider = state.tools.providers[name];
  if (!acceptedStill(state.character.basePose)) return `Approve the ${state.character.basePose} still first`;
  if (!pose.promptPreview.complete) return "Write the prompt placeholders first";
  if (!state.tools.alpha) return "Configure the alpha processor: provider images are opaque";
  if (!provider.keySet) return `Set the API key environment variable for ${name}`;
  return "";
}

function stillGenerateControl(pose) {
  const names = Object.keys(state.tools.providers).filter((name) => state.tools.providers[name].kind === "image");
  if (pose.id === state.character.basePose || !names.length) return null;
  const select = h("select", { id: "stillProvider" }, names.map((name) => h("option", { value: name }, name)));
  const button = h("button", { class: "primary", id: "generateStillBtn" }, "Generate still");
  const update = () => {
    const hint = stillGenerateHint(pose, select.value);
    button.disabled = Boolean(hint);
    button.title = hint || `Edit the approved ${state.character.basePose} still with ${select.value}`;
  };
  select.onchange = update;
  button.onclick = () => {
    const model = state.tools.providers[select.value].model;
    if (window.confirm(`Submit a paid image edit of the ${state.character.basePose} still into ${pose.id} ` +
      `to ${select.value} (${model})?`)) startJob("generate", { pose: pose.id }, { provider: select.value });
  };
  update();
  return h("span", { class: "row" }, h("label", { class: "tiny" }, "Image editor ", select), button);
}

function closedMouthControl(pose) {
  const character = state.character;
  const base = pose.id === character.basePose;
  const shared = character.closedMouth || character.basePose;
  const options = base ? state.poses.map((p) => p.id) : ["", ...state.poses.map((p) => p.id)];
  const select = h("select", { id: "closedMouthSelect" }, options.map((id) =>
    h("option", { value: id }, id || `shared (${shared})`)));
  select.value = base ? shared : (pose.closedMouth || "");
  select.onchange = () => run(() => api("/api/production/closed-mouth", base ? { source: select.value }
    : { pose: pose.id, source: select.value || null }), "Closed mouth updated; affected speaking loops are now stale");
  return h("label", { class: "tiny" }, base ? "Shared closed mouth for speaking loops " : "Closed mouth for this pose's speaking loops ", select);
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
      onclick: () => { selection.poseTake = take.id; renderActive(); } }) : null,
    h("div", { class: "row" }, badge(take.status), take.qa ? badge("QA " + take.qa.status, take.qa.status) : null,
      h("span", { class: "tiny" }, take.id)),
    h("div", { class: "tiny" }, [stillSource(take.source), take.normalization && take.normalization.method].filter(Boolean).join(" · ")),
    take.error ? h("div", { class: "tiny", style: "color:var(--bad)" }, take.error) : null,
    take.rejected ? h("div", { class: "tiny" }, "Rejected: " + (take.rejected.reason || "no reason given")) : null,
    h("div", { class: "row actions" }, decisionButtons("pose", pose.id, take)));
}

function stillSource(source) {
  if (!source) return "";
  if (source.provider === "manual") return source.note;
  if (source.provider === "clip") return `frame ${source.frame} of ${source.clip} take ${source.take}`;
  return `${source.provider} ${source.model}`;
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

function firstFrameOnly(clip) {
  return clip.generation.lastFrame === "none";
}

// What blocks generating or importing a take: a missing still at either end.
function stillsHint(clip) {
  if (!acceptedStill(clip.from)) return `Approve a still for ${clip.from} first`;
  if (!firstFrameOnly(clip) && !acceptedStill(clip.to)) {
    return `Approve a still for ${clip.to}, or set the last frame input to none and adopt a frame of a take as that still`;
  }
  return "";
}

function generateHint(clip, provider) {
  const stills = stillsHint(clip);
  if (stills) return stills;
  if (clip.generation.provider === "manual") return "Manual clips: copy the prompt and inputs into your generator, then import the video";
  if (!clip.promptPreview.complete) return "Write the prompt placeholders first";
  if (!provider || !provider.keySet) {
    return provider && provider.credential === "login" ? `Log in to ${clip.generation.provider} first (wan auth login)`
      : `Set the API key environment variable for ${clip.generation.provider}`;
  }
  return "";
}

function renderClipDetail(clip, root = $("clipDetail")) {
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
    h("div", { class: "inputs", style: "max-width:320px" }, endpoint(clip.from, "first frame"),
      endpoint(clip.to, firstFrameOnly(clip) ? "last frame (not sent)" : "last frame")),
    inputLinks(clip),
    h("h3", {}, "Settings"), settingsForm(clip),
    h("h3", {}, "Prompt"), promptView(clip.promptPreview),
    h("div", { class: "row", style: "margin-top:8px" },
      h("button", { class: "primary", id: "generateBtn", disabled: Boolean(hint), title: hint, onclick: () => generate(clip) },
        clip.generation.provider === "manual" ? "Manual provider" : `Generate with ${clip.generation.provider}`),
      h("label", { class: "tiny" }, "Import a take ", upload),
      h("button", { id: "renderBtn", disabled: !clip.acceptedTake, onclick: () => startJob("render", { clip: clip.id }) }, "Render accepted take")),
    hint ? h("div", { class: "tiny" }, hint) : null,
    h("h3", {}, "Takes"),
    active.length ? h("div", { class: "grid" }, active.map((t) => clipTakeCard(clip, t))) : h("p", { class: "muted" }, "No takes yet."),
    archived.length ? h("details", {}, h("summary", {}, `Archive (${archived.length} rejected)`),
      h("div", { class: "grid" }, archived.map((t) => clipTakeCard(clip, t)))) : null,
    h("h3", {}, "Render"), renderPanel(clip));
}

// The exact images a generator receives (flattened on the background, input scale applied), for
// generating by hand on a provider's website; import the result as a take.
function inputLinks(clip) {
  const link = (end) => h("a", { href: `/api/production/input?clip=${encodeURIComponent(clip.id)}&end=${end}`,
    download: `${clip.id}-${end}.png`, class: "input-link" }, `${end}.png`);
  const ends = [acceptedStill(clip.from) ? "first" : null, !firstFrameOnly(clip) && acceptedStill(clip.to) ? "last" : null].filter(Boolean);
  if (!ends.length) return null;
  return h("div", { class: "row tiny", style: "margin-top:6px" }, "Generator inputs:", ends.map(link),
    h("span", {}, "· import the video you make from them as a take"));
}

function endpoint(poseId, label) {
  const path = acceptedStill(poseId);
  return h("div", {}, h("div", { class: "tiny" }, `${label}: ${poseId}`),
    path ? h("img", { src: media(path) }) : badge("still not approved", "missing"));
}

function settingsForm(clip) {
  const fields = [
    ["provider", "Provider", "select", clip.generation.provider,
      ["manual", ...Object.keys(state.tools.providers).filter((name) => state.tools.providers[name].kind === "video")]],
    ["duration", "Duration (s)", "number", clip.generation.durationS],
    ["resolution", "Resolution", "text", clip.generation.resolution],
    ["seed", "Seed", "number", clip.generation.seed ?? ""],
    ["input_scale", "Input scale", "number", clip.generation.inputScale],
    ["register", "Register ends to the stills", "checkbox", clip.processing.register !== false],
    ["margin", "Canvas margin each side (px)", "number", clip.processing.marginPx || 0],
    ["interpolate", "Interpolate ×", "number", clip.processing.interpolate],
    ["lock_head", "Lock head frames", "number", clip.processing.lockHeadFrames],
    ["lock_tail", "Lock tail frames", "number", clip.processing.lockTailFrames],
    ["edge_guard", "Edge guard (px)", "number", clip.processing.edgeGuardPx],
    ["speed", "Playback speed", "number", clip.playback.speed],
    ["loop_mode", "Playback", "select", clip.playback.loopMode, ["loop", "once_then_hold"]],
  ];
  if (clip.kind === "transition") {
    fields.splice(5, 0, ["last_frame", "Last frame input (none: first frame only)", "select", clip.generation.lastFrame || "still",
      ["still", "none"]]);
  }
  if (clip.kind === "loop") {
    fields.push(["pingpong", "Pingpong loop", "checkbox", clip.processing.pingpong]);
    fields.push(["mouth", "Mouth set (silence overlay)", "select", clip.mouth ? clip.mouth.set : "off",
      ["off", ...Object.keys(state.character.mouthSets || {})]]);
    fields.push(["mouth_source", "Closed mouth: shared, still, frame:N or pose:ID", "text", sourceText(clip.mouth)]);
  }
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
    if (changes.mouth === "off" || !changes.mouth_source) delete changes.mouth_source;
    run(() => api("/api/production/clip-settings", { clip: clip.id, changes }), "Settings saved");
  } }, "Save settings");
  return h("div", {}, form, h("div", { class: "row actions" }, save,
    h("span", { class: "tiny" }, "Changing processing or playback makes the current render stale.")));
}

function sourceText(mouth) {
  const source = mouth && mouth.closedSource;
  if (!source) return "shared";
  return source.kind === "frame" ? `frame:${source.index}` : source.kind === "pose" ? `pose:${source.pose}` : source.kind;
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
      h("summary", {}, (take.inputs.last ? "First / last frame inputs" : "First frame input (no last frame)")
        + (take.inputs.assumed ? " (handed to an external tool)" : "")),
      h("div", { class: "inputs" }, h("img", { src: media(takeFile(clip, take, take.inputs.first.file)) }),
        take.inputs.last ? h("img", { src: media(takeFile(clip, take, take.inputs.last.file)) }) : null)) : null,
    take.state === "submitted" ? h("button", { onclick: () => startJob("resume", { clip: clip.id }, { take: take.id }) }, "Resume download") : null,
    h("div", { class: "row actions" }, decisionButtons("clip", clip.id, take), adoptButton(clip, take)));
}

function adoptButton(clip, take) {
  if (clip.kind !== "transition" || take.state !== "ready" || take.status === "rejected") return null;
  return h("button", { class: "adopt", title: `Make the last frame of this take a candidate still for ${clip.to}; approve it on its pose`,
    onclick: () => startJob("adopt", { pose: clip.to }, { clip: clip.id, take: take.id, frame: "last" }) }, `Last frame → ${clip.to} still`);
}

function renderPanel(clip) {
  const r = clip.render;
  const box = h("div", {}, h("div", { class: "row" }, badge(r.state),
    r.state !== "current" ? h("span", { class: "tiny" }, (r.reasons || []).join("; ")) : null,
    r.frameCount ? h("span", { class: "tiny" }, `${r.frameCount} frames · ${r.frameIntervalMs} ms/frame · ${r.loopMode} · take ${r.take}`) : null));
  if (r.frameCount) {
    const { width, height } = state.character.canvas;
    const canvas = h("canvas", { class: "player", id: "renderPreview", width, height });
    const silence = r.mouth ? h("input", { type: "checkbox", id: "silencePreview" }) : null;
    box.append(h("div", { class: "tiny" }, "Preview is capped at 30 fps; runtime timing is shown above."),
      silence ? h("label", { class: "tiny" }, silence, " Simulate silence: paste the closed mouth inside the tracked mask") : null,
      canvas, r.mouth ? mouthSummary(r.mouth) : null, qaList(r.qa), seamTable(r.qa));
    playOutput(clip, canvas, r, silence);
  }
  return box;
}

function closedMouthUrl(clip, mouth) {
  return frameUrl(`${clip.output}/${mouth.overlay}`);
}

function mouthSummary(mouth) {
  const source = mouth.closedSource;
  const from = source.kind === "frame" ? `output frame ${source.index}` : `${source.pose} still (${source.kind})`;
  return h("div", { class: "tiny" }, `Mouth set ${mouth.set} · closed mouth from ${from} · mask ${mouth.roi.width}×${mouth.roi.height}px · `
    + `tracking ${mouth.qa.trackMean} (min ${mouth.qa.trackMin}) · movement ${mouth.qa.span}px · most closed frame ${mouth.closedFrame}`
    + ` · tone shift L*a*b* ${mouth.toneShift.join(" / ")}`);
}

async function playOutput(clip, canvas, render, silence) {
  try {
    const data = await api("/api/clips?root=" + encodeURIComponent(clip.output));
    const frames = (Object.values(data.clips)[0] || {}).frames || [];
    const mouth = render.mouth;
    const closed = new Image();
    if (mouth) closed.src = closedMouthUrl(clip, mouth) || "";
    const ctx = canvas.getContext("2d");
    const frame = new Image();
    let index = 0;
    let shown = 0;
    let hold = 0;
    frame.onload = () => {
      // Use the published frame's canvas, including margins. Clip settings may already
      // have changed while this older render is still being reviewed.
      if (canvas.width !== frame.naturalWidth) canvas.width = frame.naturalWidth;
      if (canvas.height !== frame.naturalHeight) canvas.height = frame.naturalHeight;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(frame, 0, 0);
      canvas.dataset.frame = String(shown);
      if (!mouth || !silence || !silence.checked) return;
      // The renderer's silence overlay: an ellipse around the tracked mouth, filled with the
      // closed-mouth image shifted so its mouth lands on the current one.
      const anchor = mouth.anchorTrack[Math.min(shown, mouth.anchorTrack.length - 1)];
      const source = mouth.sourceAnchor;
      const cx = anchor.cx + canvas.width / 2;
      const cy = anchor.cy + canvas.height / 2;
      const rx = (anchor.width / 2) * 1.8;
      const ry = (anchor.height / 2) * (1 + 1.5 * 0.75);
      ctx.save();
      ctx.beginPath();
      ctx.ellipse(cx, cy, rx, ry, 0, 0, 2 * Math.PI);
      ctx.clip();
      if (closed.complete && closed.naturalWidth) ctx.drawImage(closed, anchor.cx - source.cx, anchor.cy - source.cy);
      ctx.restore();
      ctx.strokeStyle = "#ffe066";
      ctx.beginPath();
      ctx.ellipse(cx, cy, rx, ry, 0, 0, 2 * Math.PI);
      ctx.stroke();
      canvas.dataset.silence = "1";
    };
    clearInterval(previewTimer);
    previewTimer = setInterval(() => {
      if (!frames.length || !document.body.contains(canvas)) { clearInterval(previewTimer); return; }
      shown = index;
      frame.src = frameUrl(frames[index]);
      if (index < frames.length - 1) index += 1;
      else if (render.loopMode === "loop" || ++hold > 30) { index = 0; hold = 0; }
    }, Math.max(33, render.frameIntervalMs));
  } catch (error) {
    canvas.replaceWith(h("div", { class: "tiny" }, String(error.message || error)));
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
  if (ok) await startJob("generate", { clip: clip.id });
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
    h("table", {}, h("tr", {}, h("th", {}, "Template"), h("th", {}, "Blocks"), h("th", {}, "Joined by"), h("th", {}, "Negative")),
      Object.entries(library.templates).map(([id, t]) => h("tr", {}, h("td", {}, id), h("td", {}, t.blocks.join(" + ")),
        h("td", {}, t.join ? `"${t.join}"` : "blank line"), h("td", {}, (t.negative || []).join(" + "))))),
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
async function startJob(action, owner, extra = {}) {
  await run(() => api("/api/production/jobs", { action, ...owner, ...extra }), `${action} started for ${owner.pose || owner.clip}`);
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
    h("div", { class: "row" }, h("strong", {}, `${j.action} ${j.kind} ${j.owner}`),
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
  if (!TABS.includes(name)) name = "canvas";
  activeTab = name;
  document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".tab").forEach((tab) => { tab.hidden = tab.id !== "tab-" + name; });
  history.replaceState(null, "", "#" + name);
  renderActive();
}

function addPoseInteractive() {
  const id = window.prompt("New pose id (lowercase letters, digits, _ or -)");
  if (!id) return Promise.resolve(null);
  const description = window.prompt("Short description (optional)", "") || "";
  return run(() => api("/api/production/pose", { id, description }), `Pose ${id} added`).then((result) => {
    if (result) { selection.pose = id; renderActive(); }
    return result;
  });
}

document.querySelectorAll("#tabs button").forEach((button) => button.addEventListener("click", () => showTab(button.dataset.tab)));
$("addPose").addEventListener("click", addPoseInteractive);
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

setupCanvas();
showTab((location.hash || "#canvas").slice(1));
refresh().then(pollJobs).catch((error) => toast(String(error.message || error), true));
