"use strict";
// Production canvas: poses and clips as cards, joined by wires that show what feeds what.
//   pose → clip   the pose's still is the clip's first frame
//   clip → pose   the clip ends on that pose: solid when that still is sent as the last frame,
//                 dotted when the clip is generated from its first frame only, dashed (with the
//                 frame number) when the pose's approved still was taken from one of its takes
// The canvas shows production records only; which clip plays when (labels, probabilities) is
// bound later on the Review & graph page. Card positions are saved in production/canvas.json.
// Uses the helpers and state of production.js (h, fill, badge, api, run, state, ...).
(() => {
  const WIDTH = { pose: 214, clip: 304 };
  const PORT_Y = 21; // ports sit on the card's title row
  const LANE = { pose: 274, clip: 388 }; // auto layout: pose and clip columns alternate
  const GAP = 34;
  const ui = { view: null, positions: {}, selected: null, drafts: {}, cards: new Map(), saveTimer: null,
    viewTimer: null, justDragged: false, loadedFor: null, lang: null };
  let viewport;
  let world;
  let wires;

  const keyOf = (kind, id) => `${kind}:${id}`;
  const ownerOf = (key) => {
    const [kind, id] = key.split(":");
    return (kind === "pose" ? state.poses : state.clips).find((o) => o.id === id) || null;
  };
  const storage = (action) => { try { return action(window.localStorage); } catch { return null; } };

  function setupCanvas() {
    viewport = $("canvasViewport");
    world = $("canvasWorld");
    wires = $("canvasWires");
    ui.lang = storage((s) => s.getItem("spriteforge.canvas.lang")) || (/^zh/i.test(navigator.language || "") ? "zh" : "en");
    $("canvasFit").onclick = fitView;
    $("canvasLayout").onclick = () => { autoLayout(true); placeCards(); drawWires(); fitView(); savePositions(); };
    $("canvasAddPose").onclick = () => addPoseInteractive();
    $("canvasGuideBtn").onclick = () => ($("canvasGuide").hidden ? showGuide() : hideGuide());
    viewport.addEventListener("wheel", onWheel, { passive: false });
    viewport.addEventListener("pointerdown", onPanStart);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && activeTab === "canvas" && !event.target.closest("textarea, input")) select(null);
    });
  }

  function renderCanvas() {
    if (!world) return;
    if (ui.loadedFor !== state.character.id) {
      ui.loadedFor = state.character.id;
      ui.positions = { ...(state.canvas || {}) };
      ui.view = storage((s) => JSON.parse(s.getItem(viewKey()) || "null"));
    }
    world.querySelectorAll(".node").forEach((el) => el.remove());
    ui.cards.clear();
    for (const pose of state.poses) addCard(keyOf("pose", pose.id), poseCard(pose));
    for (const clip of state.clips) addCard(keyOf("clip", clip.id), clipCard(clip));
    if ([...ui.cards.keys()].some((key) => !ui.positions[key])) { autoLayout(false); savePositions(); }
    placeCards();
    drawWires();
    if (ui.view) applyView(); else fitView();
    renderInspector();
    if (!state.clips.length && !storage((s) => s.getItem("spriteforge.canvas.guideSeen"))) showGuide();
  }

  function clearCanvas() {
    if (!world) return;
    world.querySelectorAll(".node").forEach((el) => el.remove());
    ui.cards.clear();
    wires.replaceChildren();
    fill($("canvasInspector"));
    $("canvasInspector").hidden = true;
  }

  // ── Cards ────────────────────────────────────────────────────────────
  function stillOrigin(take) {
    const source = take.source || {};
    if (source.provider === "clip") return `frame ${source.frame} of ${source.clip}`;
    if (source.provider === "manual") return "imported" + (source.note ? ` · ${source.note}` : "");
    return `${source.provider} ${source.model || ""}`.trim();
  }

  function poseCard(pose) {
    const [text, kind] = poseStatus(pose);
    const accepted = pose.takes.find((t) => t.status === "accepted");
    const latest = pose.takes.slice().reverse().find((t) => t.state === "ready" && t.media && t.media.still && t.status !== "rejected");
    const shown = accepted || latest;
    const origin = shown ? (accepted ? "" : "candidate · ") + stillOrigin(shown) : pose.description || "Import, generate or take a still";
    return h("div", { class: "node pose", style: `width:${WIDTH.pose}px` },
      h("div", { class: "node-head" }, h("span", { class: "port in", title: "Clips that end on this pose" }),
        h("strong", {}, pose.id), pose.id === state.character.basePose ? badge("base", "candidate") : null, badge(text, kind),
        h("span", { class: "port out", title: "Drag onto a pose or empty space to make a clip from this pose" })),
      h("div", { class: "node-thumb" }, shown
        ? h("img", { src: media(stillFile(pose, shown)), alt: `${pose.id} still`, draggable: "false" })
        : h("span", { class: "tiny" }, "No still yet")),
      h("div", { class: "node-line tiny", title: origin }, origin));
  }

  function clipCard(clip) {
    const subject = clip.prompt.subject;
    const block = state.prompts.blocks[subject];
    const current = block ? block.versions[block.versions.length - 1] : { text: "", version: 0 };
    const draft = ui.drafts[subject];
    const area = h("textarea", { class: "node-prompt", value: draft !== undefined ? draft : current.text, "data-prompt": clip.id,
      spellcheck: "false", "aria-label": `${clip.id} prompt` });
    const save = h("button", { class: "small", disabled: draft === undefined || draft === current.text }, "Save prompt");
    area.addEventListener("input", () => { ui.drafts[subject] = area.value; save.disabled = area.value === current.text; });
    save.onclick = async () => {
      const result = await run(() => api("/api/production/prompt", { block: subject, text: area.value }), `${clip.id}: prompt saved as a new version`);
      if (result) delete ui.drafts[subject];
    };
    const r = clip.render;
    const renderText = r.state === "current" ? "rendered" : r.state === "stale" ? "stale" : clip.acceptedTake ? "not rendered" : "no take chosen";
    const renderKind = r.state === "current" ? "current" : r.state === "stale" || clip.acceptedTake ? "stale" : "pending";
    const qa = r.qa ? r.qa.status : null;
    const loop = clip.kind === "loop";
    const firstOnly = firstFrameOnly(clip);
    const provider = state.tools.providers[clip.generation.provider];
    const manual = clip.generation.provider === "manual";
    const hint = generateHint(clip, provider);
    const cardHint = manual ? stillsHint(clip) : hint; // manual clips only need their stills to import a take
    const live = clip.takes.filter((t) => t.status !== "rejected");
    const archived = clip.takes.length - live.length;
    const upload = h("input", { type: "file", accept: "video/mp4,video/webm,video/quicktime", hidden: true,
      onchange: (e) => uploadFile("clip", clip.id, e.target.files[0]) });
    const flagged = qa === "fail" ? " fail" : (clip.acceptedTake && r.state !== "current") || qa === "fix" ? " warn" : "";
    return h("div", { class: "node clip" + flagged, style: `width:${WIDTH.clip}px` },
      h("div", { class: "node-head" }, h("span", { class: "port in", title: `Starts from the ${clip.from} still` }),
        h("strong", {}, clip.id), h("span", { class: "tiny" }, loop ? "loop" : "transition"),
        badge(renderText, renderKind), qa ? badge("QA " + qa, qa) : null,
        loop ? null : h("span", { class: "port out", title: `Ends on ${clip.to}` })),
      h("div", { class: "node-body" },
        h("div", { class: "tiny" }, loop ? `Loop on the ${clip.from} still (first and last frame)`
          : `First frame: ${clip.from} still · last frame: ${firstOnly ? `not sent (ends on ${clip.to})` : `${clip.to} still`}`),
        area,
        h("div", { class: "row" }, save, h("span", { class: "tiny" }, `prompt v${current.version}`),
          /\{\{\s*PLACEHOLDER/.test(current.text) ? badge("placeholder", "watch") : null),
        h("div", { class: "chips" }, [clip.generation.provider === "manual" ? "manual" : `${clip.generation.provider}${provider && provider.model ? " · " + provider.model : ""}`,
          clip.generation.resolution, `${clip.generation.durationS} s`, firstOnly ? "first frame only" : null].filter(Boolean)
          .map((text) => h("span", { class: "chip" }, text))),
        h("div", { class: "node-takes" }, live.slice(-4).reverse().map((t) => takeThumb(clip, t)),
          live.length ? null : h("span", { class: "tiny" }, "No takes yet"),
          archived ? h("span", { class: "tiny" }, `+${archived} archived`) : null),
        h("div", { class: "row" },
          manual ? null : h("button", { class: "small primary", disabled: Boolean(hint),
            title: hint || `Generate a new take with ${clip.generation.provider}`, onclick: () => generate(clip) }, "Generate"),
          h("label", { class: "button small", title: "Import a video made elsewhere as a new take" }, "Import take", upload),
          clip.acceptedTake && r.state !== "current"
            ? h("button", { class: "small", onclick: () => startJob("render", { clip: clip.id }) }, "Render") : null,
          adoptAction(clip)),
        cardHint ? h("div", { class: "tiny node-hint" }, cardHint) : null));
  }

  function takeThumb(clip, take) {
    const m = take.media || {};
    let preview;
    if (m.video) {
      preview = h("video", { src: media(takeFile(clip, take, m.video)), preload: "metadata", playsinline: true, loop: true });
      preview.muted = true;
      preview.addEventListener("pointerenter", () => preview.play().catch(() => {}));
      preview.addEventListener("pointerleave", () => { preview.pause(); preview.currentTime = 0; });
    } else if (m.dir) {
      preview = h("img", { src: media(takeFile(clip, take, `${m.dir}/000000.png`)), alt: "", draggable: "false" });
    } else {
      preview = h("span", { class: "tiny" }, take.state);
    }
    const source = take.source || {};
    return h("div", { class: "take-thumb" + (take.status === "accepted" ? " accepted" : ""),
      title: [take.id, take.status, source.provider, source.note].filter(Boolean).join(" · ") }, preview);
  }

  function adoptAction(clip) {
    if (clip.kind !== "transition") return null;
    const ready = clip.takes.filter((t) => t.state === "ready" && t.status !== "rejected");
    const take = ready.find((t) => t.status === "accepted") || ready[ready.length - 1];
    if (!take) return null;
    return h("button", { class: "small", title: `Make the last frame of take ${take.id} a candidate still for ${clip.to}`,
      onclick: () => startJob("adopt", { pose: clip.to }, { clip: clip.id, take: take.id, frame: "last" }) }, `Last frame → ${clip.to} still`);
  }

  function addCard(key, el) {
    el.dataset.card = key;
    if (ui.selected === key) el.classList.add("selected");
    el.querySelector(".node-head").addEventListener("pointerdown", (event) => startCardDrag(event, key, el));
    el.addEventListener("click", (event) => {
      if (ui.justDragged || event.target.closest("button, textarea, input, label, a, .port")) return;
      select(key);
    });
    if (key.startsWith("pose:")) el.querySelector(".port.out").addEventListener("pointerdown", (event) => startConnect(event, key));
    world.append(el);
    ui.cards.set(key, el);
  }

  function select(key) {
    ui.selected = key;
    for (const [k, el] of ui.cards) el.classList.toggle("selected", k === key);
    renderInspector();
  }

  function renderInspector() {
    const root = $("canvasInspector");
    const owner = ui.selected ? ownerOf(ui.selected) : null;
    if (!owner) { ui.selected = null; root.hidden = true; fill(root); return; }
    const kind = ui.selected.split(":")[0];
    const body = h("div", { class: "inspector-body" });
    fill(root, h("div", { class: "inspector-head" }, h("span", { class: "tiny" }, kind === "pose" ? "Pose still and takes" : "Clip settings, takes and render"),
      h("button", { class: "small", onclick: () => select(null) }, "Close")), body);
    root.hidden = false;
    if (kind === "pose") { selection.pose = owner.id; renderPoseDetail(owner, body); }
    else { selection.clip = owner.id; renderClipDetail(owner, body); }
  }

  // ── Wires ────────────────────────────────────────────────────────────
  function canvasWires() {
    const list = [];
    const adoptedFrom = (pose) => {
      const take = pose && pose.takes.find((t) => t.status === "accepted");
      return take && take.source && take.source.provider === "clip" ? take.source : null;
    };
    for (const clip of state.clips) {
      list.push({ from: keyOf("pose", clip.from), to: keyOf("clip", clip.id), kind: "start" });
      const source = adoptedFrom(state.poses.find((p) => p.id === clip.to));
      const adopted = source && source.clip === clip.id;
      if (clip.kind === "loop" && !adopted) continue; // a loop returns to the pose it starts from
      list.push({ from: keyOf("clip", clip.id), to: keyOf("pose", clip.to),
        kind: adopted ? "adopted" : firstFrameOnly(clip) ? "open" : "end", label: adopted ? `frame ${source.frame}` : null });
    }
    // A still taken from a clip that does not end on that pose still shows where it came from.
    for (const pose of state.poses) {
      const source = adoptedFrom(pose);
      if (source && !state.clips.some((c) => c.id === source.clip && c.to === pose.id)) {
        list.push({ from: keyOf("clip", source.clip), to: keyOf("pose", pose.id), kind: "adopted", label: `frame ${source.frame}` });
      }
    }
    return list;
  }

  function svgEl(tag, attrs) {
    const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, value);
    return el;
  }

  const curve = (x1, y1, x2, y2) => {
    const bend = Math.max(48, Math.abs(x2 - x1) / 2);
    return `M${x1} ${y1} C${x1 + bend} ${y1} ${x2 - bend} ${y2} ${x2} ${y2}`;
  };

  function drawWires() {
    const items = [];
    for (const wire of canvasWires()) {
      const a = ui.cards.get(wire.from);
      const b = ui.cards.get(wire.to);
      if (!a || !b) continue;
      const [ax, ay] = ui.positions[wire.from];
      const [bx, by] = ui.positions[wire.to];
      const x1 = ax + a.offsetWidth;
      const y1 = ay + PORT_Y;
      items.push(svgEl("path", { d: curve(x1, y1, bx, by + PORT_Y), class: `wire ${wire.kind}`, "data-from": wire.from, "data-to": wire.to }));
      if (wire.label) {
        const label = svgEl("text", { x: (x1 + bx) / 2, y: (y1 + by + PORT_Y) / 2 - 6, class: "wire-label", "text-anchor": "middle" });
        label.textContent = wire.label;
        items.push(label);
      }
    }
    wires.replaceChildren(...items);
  }

  // ── Layout, pan and zoom ─────────────────────────────────────────────
  function autoLayout(all) {
    const base = state.character.basePose;
    const depth = new Map([[base, 0]]);
    const queue = [base];
    while (queue.length) {
      const pose = queue.shift();
      for (const clip of state.clips) {
        if (clip.from === pose && clip.to !== pose && !depth.has(clip.to)) { depth.set(clip.to, depth.get(pose) + 1); queue.push(clip.to); }
      }
    }
    const reached = Math.max(0, ...depth.values());
    for (const pose of state.poses) if (!depth.has(pose.id)) depth.set(pose.id, reached + 1);
    const deepest = Math.max(0, ...depth.values());
    const height = (key) => (ui.cards.get(key) ? ui.cards.get(key).offsetHeight : 240);
    const top = new Map();
    const place = (key, x, y) => { top.set(key, y); if (all || !ui.positions[key]) ui.positions[key] = [x, y]; };
    for (let d = 0; d <= deepest; d++) {
      const poseX = d * (LANE.pose + LANE.clip);
      const incoming = (pose) => {
        const ys = state.clips.filter((c) => c.to === pose.id && c.from !== pose.id && top.has(keyOf("clip", c.id))).map((c) => top.get(keyOf("clip", c.id)));
        return ys.length ? Math.min(...ys) : Infinity;
      };
      const poses = state.poses.filter((p) => depth.get(p.id) === d)
        .sort((a, b) => (a.id === base ? -1 : b.id === base ? 1 : (incoming(a) - incoming(b)) || a.id.localeCompare(b.id)));
      let y = 0;
      for (const pose of poses) {
        const key = keyOf("pose", pose.id);
        const wanted = incoming(pose);
        y = Math.max(y, Number.isFinite(wanted) ? wanted : 0);
        place(key, poseX, y);
        y += height(key) + GAP;
      }
      let clipY = 0;
      for (const pose of poses) {
        clipY = Math.max(clipY, top.get(keyOf("pose", pose.id)));
        const clips = state.clips.filter((c) => c.from === pose.id)
          .sort((a, b) => (a.kind === b.kind ? a.id.localeCompare(b.id) : a.kind === "loop" ? 1 : -1));
        for (const clip of clips) {
          const key = keyOf("clip", clip.id);
          place(key, poseX + LANE.pose, clipY);
          clipY += height(key) + GAP;
        }
      }
    }
  }

  function placeCards() {
    for (const [key, el] of ui.cards) {
      const [x, y] = ui.positions[key];
      el.style.left = `${x}px`;
      el.style.top = `${y}px`;
    }
  }

  function savePositions() {
    clearTimeout(ui.saveTimer);
    ui.saveTimer = setTimeout(() => {
      api("/api/production/canvas", { positions: ui.positions }).catch((error) => toast(String(error.message || error), true));
    }, 250);
  }

  const viewKey = () => `spriteforge.canvas.view.${state.character.id}`;

  function applyView() {
    const { x, y, k } = ui.view;
    world.style.transform = `translate(${x}px, ${y}px) scale(${k})`;
    clearTimeout(ui.viewTimer);
    ui.viewTimer = setTimeout(() => storage((s) => s.setItem(viewKey(), JSON.stringify(ui.view))), 300);
  }

  function fitView() {
    const width = viewport.clientWidth;
    const height = viewport.clientHeight;
    const boxes = [...ui.cards].map(([key, el]) => {
      const [x, y] = ui.positions[key];
      return [x, y, x + el.offsetWidth, y + el.offsetHeight];
    });
    if (!width || !height || !boxes.length) { ui.view = { x: 40, y: 40, k: 1 }; applyView(); return; }
    const x0 = Math.min(...boxes.map((b) => b[0]));
    const y0 = Math.min(...boxes.map((b) => b[1]));
    const x1 = Math.max(...boxes.map((b) => b[2]));
    const y1 = Math.max(...boxes.map((b) => b[3]));
    const k = Math.max(0.25, Math.min(1, (width - 60) / (x1 - x0), (height - 60) / (y1 - y0)));
    ui.view = { k, x: (width - (x1 - x0) * k) / 2 - x0 * k, y: Math.max(30, (height - (y1 - y0) * k) / 2) - y0 * k };
    applyView();
  }

  function onWheel(event) {
    if (event.target.closest("textarea, .guide")) return;
    event.preventDefault();
    const rect = viewport.getBoundingClientRect();
    const px = event.clientX - rect.left;
    const py = event.clientY - rect.top;
    const k = Math.min(2, Math.max(0.25, ui.view.k * Math.exp(-event.deltaY * 0.0015)));
    ui.view = { k, x: px - (px - ui.view.x) * (k / ui.view.k), y: py - (py - ui.view.y) * (k / ui.view.k) };
    applyView();
  }

  function drag(event, onMove, onEnd) {
    const move = (e) => onMove(e);
    const up = (e) => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      onEnd(e);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  function onPanStart(event) {
    if (event.button !== 0 || event.target.closest(".node, .guide")) return;
    const start = { x: event.clientX, y: event.clientY, view: { ...ui.view } };
    let moved = false;
    viewport.classList.add("panning");
    drag(event, (e) => {
      if (!moved && Math.hypot(e.clientX - start.x, e.clientY - start.y) < 3) return;
      moved = true;
      ui.view = { ...start.view, x: start.view.x + e.clientX - start.x, y: start.view.y + e.clientY - start.y };
      applyView();
    }, () => {
      viewport.classList.remove("panning");
      if (!moved) select(null);
    });
  }

  function startCardDrag(event, key, el) {
    if (event.button !== 0 || event.target.closest(".port, button, input, textarea, a, label")) return;
    event.preventDefault();
    event.stopPropagation();
    const start = { x: event.clientX, y: event.clientY, pos: ui.positions[key].slice() };
    let moved = false;
    drag(event, (e) => {
      const dx = (e.clientX - start.x) / ui.view.k;
      const dy = (e.clientY - start.y) / ui.view.k;
      if (!moved && Math.hypot(dx, dy) < 3) return;
      moved = true;
      ui.positions[key] = [Math.round(start.pos[0] + dx), Math.round(start.pos[1] + dy)];
      el.style.left = `${ui.positions[key][0]}px`;
      el.style.top = `${ui.positions[key][1]}px`;
      drawWires();
    }, () => {
      if (!moved) return;
      ui.justDragged = true;
      setTimeout(() => { ui.justDragged = false; }, 0);
      savePositions();
    });
  }

  // ── Making clips by drawing a wire ───────────────────────────────────
  function toWorld(event) {
    const rect = viewport.getBoundingClientRect();
    return [(event.clientX - rect.left - ui.view.x) / ui.view.k, (event.clientY - rect.top - ui.view.y) / ui.view.k];
  }

  function startConnect(event, fromKey) {
    if (event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    const fromEl = ui.cards.get(fromKey);
    const [fx, fy] = ui.positions[fromKey];
    const x1 = fx + fromEl.offsetWidth;
    const y1 = fy + PORT_Y;
    const draft = svgEl("path", { class: "wire draft", d: curve(x1, y1, x1, y1) });
    wires.append(draft);
    drag(event, (e) => {
      const [x2, y2] = toWorld(e);
      draft.setAttribute("d", curve(x1, y1, x2, y2));
    }, (e) => {
      draft.remove();
      const [x2, y2] = toWorld(e);
      if (Math.hypot(x2 - x1, y2 - y1) < 12) return;
      const hit = document.elementFromPoint(e.clientX, e.clientY);
      const target = hit && hit.closest(".node.pose");
      if (target) connect(fromKey.slice(5), target.dataset.card.slice(5), null);
      else if (hit && hit.closest("#canvasViewport") && !hit.closest(".node, .guide")) connect(fromKey.slice(5), null, [x2, y2]);
    });
  }

  function uniqueClipId(base) {
    let id = base;
    for (let n = 2; state.clips.some((c) => c.id === id); n++) id = `${base}_${n}`;
    return id;
  }

  async function connect(from, to, drop) {
    const target = to || window.prompt(`New pose reached from ${from}. Its transition is generated from the ${from} still alone, `
      + "and a frame of the result becomes the new pose's still. Pose id (lowercase letters, digits, _ or -):");
    if (!target) return;
    const loop = target === from;
    const id = window.prompt(loop ? `Loop clip on ${target}: clip id` : `Transition ${from} → ${target}: clip id`,
      uniqueClipId(loop ? `${target}_loop` : `${from}_to_${target}`));
    if (!id) return;
    const origin = ui.positions[keyOf("pose", from)];
    await run(async () => {
      if (!to) {
        await api("/api/production/pose", { id: target, description: "" });
        ui.positions[keyOf("pose", target)] = [Math.round(drop[0]), Math.round(drop[1] - PORT_Y)];
      }
      await api("/api/production/clip", { id, from, to: target });
      if (!to) await api("/api/production/clip-settings", { clip: id, changes: { last_frame: "none" } });
      const end = ui.positions[keyOf("pose", target)] || [origin[0] + LANE.pose + LANE.clip, origin[1]];
      ui.positions[keyOf("clip", id)] = loop ? [origin[0] + LANE.pose, origin[1] + 280]
        : [Math.round((origin[0] + WIDTH.pose + end[0]) / 2 - WIDTH.clip / 2), Math.round((origin[1] + end[1]) / 2)];
      ui.selected = keyOf("clip", id);
      savePositions();
    }, to ? `Clip ${id} added` : `Pose ${target} and clip ${id} added: generate a take, then take its last frame as the ${target} still`);
  }

  // ── Guide ────────────────────────────────────────────────────────────
  const GUIDE = {
    en: {
      title: "Making clips on the canvas",
      intro: "Each pose has one approved still, and every clip starts and ends on pose stills. That is what keeps clips aligned where they meet.",
      steps: [
        ["Approve the base still", "Click the base pose card, import its reference image in the side panel and approve it. Approval measures the head top and head centre that every other still must match."],
        ["Give poses their stills", "Add a pose with + Pose. Import an image, generate one with an image editor, or take it from a transition (step 6)."],
        ["Draw clips", "Drag from a pose's right port onto another pose for a transition, back onto the same pose for a loop, or onto empty space for a new pose reached by a first-frame-only transition."],
        ["Write the clip's prompt", "Type the clip's own text on its card and save it as a new version. Shared text, such as the character and constraints like \"camera unchanged\", lives on the Prompts tab."],
        ["Make takes", "Generate sends the stills and prompt to the clip's provider after you confirm. To generate by hand on a provider's website, download the generator inputs from the clip's side panel and import the video with Import take. Click a card to use or reject takes; rejected takes stay archived with your reason."],
        ["Let a transition define the next pose", "On a first-frame-only transition, Last frame → pose still turns a take's last frame into a candidate still for the end pose. Approve it on the pose card; a dashed wire shows which clip and frame it came from. Then continue from that pose."],
        ["Render and check", "Render the accepted take. Badges show missing or stale renders and the QA level. A render goes stale when its take, its settings or one of its stills changes."],
      ],
      wires: "Wires: pose → clip means the still is the clip's first frame. Clip → pose means the clip ends on that pose: solid when the still is sent as the last frame, dotted when the clip is generated from its first frame only, dashed when the pose's still was taken from one of the clip's takes.",
      note: "Which clip plays when (labels, probabilities) is set later on the Review & graph page.",
      close: "Close",
      other: "中文",
    },
    zh: {
      title: "在画布上制作片段",
      intro: "每个姿态有一张批准的静帧，每个片段都从姿态静帧开始、在姿态静帧结束，片段相接处因此能对齐。",
      steps: [
        ["批准基准静帧", "点基准姿态的卡片，在右侧面板导入参考图并批准。批准时会测出头顶和头部中心，其他静帧都要和它对齐。"],
        ["给姿态配静帧", "用 + Pose 添加姿态，然后导入图片、用图像编辑生成，或者从过渡里取一帧（第 6 步）。"],
        ["连出片段", "从姿态卡右侧的接口拖出：拖到另一个姿态是过渡，拖回自己是循环，拖到空白处会新建一个姿态，并用只给首帧的过渡连过去。"],
        ["写片段的 prompt", "在卡片上写这个片段自己的描述，保存为新版本。共用的部分（角色描述、\"镜头不变\"这类约束）在 Prompts 页。"],
        ["生成 take", "点 Generate 并确认后，会把静帧和 prompt 发给这个片段的服务商。如果要在服务商网站上手动生成，就在片段的右侧面板下载生成器输入图，再用 Import take 导入视频。点卡片可以采用或弃用 take，弃用的会带原因存档。"],
        ["让过渡定义下一个姿态", "只给首帧的过渡上，Last frame → 姿态 still 会把 take 的最后一帧变成终点姿态的候选静帧。在姿态卡上批准后，虚线会标出它来自哪个片段的第几帧。然后从这个姿态继续。"],
        ["渲染并检查", "渲染采用的 take。徽标会显示缺渲染、已过期和 QA 等级；take、设置或任一静帧改变后，渲染会过期。"],
      ],
      wires: "连线：姿态 → 片段表示这张静帧是片段的首帧。片段 → 姿态表示片段停在这个姿态上：实线表示把它的静帧作为尾帧发送，点线表示只用首帧生成，虚线表示这个姿态的静帧取自该片段的某个 take。",
      note: "哪个片段什么时候播放（标签、概率）在之后的 Review & graph 页设置。",
      close: "关闭",
      other: "English",
    },
  };

  function showGuide() {
    const text = GUIDE[ui.lang] || GUIDE.en;
    const swap = () => {
      ui.lang = ui.lang === "zh" ? "en" : "zh";
      storage((s) => s.setItem("spriteforge.canvas.lang", ui.lang));
      showGuide();
    };
    const guide = $("canvasGuide");
    fill(guide,
      h("div", { class: "row guide-head" }, h("h2", {}, text.title), h("button", { class: "small", onclick: swap }, text.other),
        h("button", { class: "small", onclick: hideGuide }, text.close)),
      h("p", { class: "tiny" }, text.intro),
      h("ol", {}, text.steps.map(([title, body]) => h("li", {}, h("strong", {}, title), h("span", {}, body)))),
      h("p", { class: "tiny" }, text.wires),
      h("p", { class: "tiny" }, text.note));
    guide.hidden = false;
  }

  function hideGuide() {
    $("canvasGuide").hidden = true;
    storage((s) => s.setItem("spriteforge.canvas.guideSeen", "1"));
  }

  Object.assign(window, { setupCanvas, renderCanvas, clearCanvas });
})();
