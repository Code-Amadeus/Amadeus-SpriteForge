"use strict";
(() => {
  const strings = {
    en: { side: "Side by side", overlay: "Overlay", difference: "Difference", onion: "Onion skin", modes: "Compare mode",
      ends: "Show start/end stills", guides: "Head guides", rendered: "Render preview", raw: "Raw take", render: "Render",
      previous: "Previous frame", next: "Next frame", play: "Play", pause: "Pause", loop: "Loop", speed: "Speed",
      frame: "frame {frame} / {count}", timelineFrame: "timeline frame {frame} / {count}", seek: "Frame timeline", loading: "Loading media…", empty: "Select a version with media.",
      unavailable: "Frame unavailable", videoUnavailable: "This browser cannot decode this video format.", metadata: "This video has no recorded frame timing.", chooseB: "Select B to compare two versions.",
      start: "Approved start still", end: "Approved end still", qaUnavailable: "Frame markers require a matching render preview.",
      widest: "{pane}: widest mouth f{frame}", qaFrame: "{pane}: {level} · f{frame}", seam: "{pane}: loop seam {value} L*",
      onionHint: "Previous, current and next A frames, overlaid with B.", renderHint: "Show published output only when it belongs to the selected take.",
      statusAccepted: "accepted", statusCandidate: "to review", statusRejected: "rejected" },
    "zh-CN": { side: "并排", overlay: "叠加", difference: "差异", onion: "洋葱皮", modes: "对比模式",
      ends: "显示起止静帧", guides: "头部参考线", rendered: "渲染预览", raw: "原始尝试", render: "渲染",
      previous: "上一帧", next: "下一帧", play: "播放", pause: "暂停", loop: "循环", speed: "速度",
      frame: "第 {frame} / {count} 帧", timelineFrame: "时间轴第 {frame} / {count} 帧", seek: "帧时间轴", loading: "正在加载媒体…", empty: "请选择有媒体的版本。",
      unavailable: "无法显示此帧", videoUnavailable: "此浏览器无法解码该视频格式。", metadata: "此视频没有记录帧时间。", chooseB: "请选择 B 以比较两个版本。",
      start: "已批准的起点静帧", end: "已批准的终点静帧", qaUnavailable: "帧标记需要与该尝试匹配的渲染预览。",
      widest: "{pane}：最大张嘴 f{frame}", qaFrame: "{pane}：{level} · f{frame}", seam: "{pane}：循环接缝 {value} L*",
      onionHint: "A 的前一帧、当前帧和后一帧，与 B 叠加。", renderHint: "仅当发布的渲染属于选中的尝试时显示它。",
      statusAccepted: "已采用", statusCandidate: "待审阅", statusRejected: "已弃用" },
  };
  for (const [lang, entries] of Object.entries(strings)) window.SFStudio.addTranslations(lang,
    Object.fromEntries(Object.entries(entries).map(([key, value]) => [`compare.${key}`, value])));
  const detailStrings = {
    en: { mouthOnlyLoops: "Mouth settings belong to speaking loops.", mouthChooseSet: "Choose a mouth set and save settings to edit its mask.",
      mouthMaskPreview: "Mouth set overlay preview", mouthSetSaved: "Mouth set saved; affected renders are now stale.", saveMouthSet: "Save mouth set",
      mouthMaskTitle: "Mouth set: {name}", mouthPriorHint: "The ellipse is the expected mouth region. Render tracks the actual mouth movement.",
      renderTakeQA: "Render QA · take {take}", noRenderQA: "Render the accepted take to inspect QA.", renderTakePreview: "Render preview · take {take}",
      currentClipSettings: "Current clip settings", currentClipSettingsHint: "These settings apply to the clip. Each version retains its recorded inputs and prompt.",
      "mouthField.cx": "Horizontal centre (px)", "mouthField.cy": "Vertical centre (px)", "mouthField.width": "Width (px)", "mouthField.height": "Height (px)", "mouthField.curve": "Curve" },
    "zh-CN": { mouthOnlyLoops: "嘴型设置用于说话循环。", mouthChooseSet: "选择嘴型集并保存设置后，可编辑其遮罩。",
      mouthMaskPreview: "嘴型集叠加预览", mouthSetSaved: "嘴型集已保存；受影响的渲染现已过期。", saveMouthSet: "保存嘴型集",
      mouthMaskTitle: "嘴型集：{name}", mouthPriorHint: "椭圆表示预期的嘴部区域。渲染时会跟踪实际嘴部移动。",
      renderTakeQA: "渲染 QA · 尝试 {take}", noRenderQA: "渲染已采用的尝试后可检查 QA。", renderTakePreview: "渲染预览 · 尝试 {take}",
      currentClipSettings: "当前片段设置", currentClipSettingsHint: "这些设置用于当前片段。每个版本保留其记录的输入和 prompt。",
      "mouthField.cx": "水平中心（px）", "mouthField.cy": "垂直中心（px）", "mouthField.width": "宽度（px）", "mouthField.height": "高度（px）", "mouthField.curve": "曲率" },
  };
  for (const [lang, entries] of Object.entries(detailStrings)) window.SFStudio.addTranslations(lang,
    Object.fromEntries(Object.entries(entries).map(([key, value]) => [`production.${key}`, value])));
  const media = (path) => "/api/production/media?path=" + encodeURIComponent(path);
  const modes = ["side", "overlay", "difference", "onion"];

  function mount(context, options) {
    let ctx = context;
    let opts = options;
    let disposed = false;
    let epoch = 0;
    let request = null;
    let sources = [];
    let signature = null;
    let stills = [];
    let painting = false;
    let paintAgain = false;
    const aborts = new Set();
    const ui = { mode: "side", playing: false, loop: opts.clip.kind === "loop", speed: 1, frame: 0,
      rendered: Boolean(opts.useRender), ends: false, guides: true, lastTick: null, elapsed: 0 };
    let el = {};
    const t = (key, values) => ctx.t(`compare.${key}`, values);
    const alive = (token) => !disposed && epoch === token;
    const timelineFps = () => Math.max(0, ...sources.map((source) => source.fps || 0)) || 1;
    const duration = () => Math.max(0, ...sources.map((source) => source.duration || 0));
    const frameCount = () => Math.max(1, Math.ceil(duration() * timelineFps()));
    const frameTime = () => ui.frame / timelineFps();
    const videoError = (video) => new Error(t("videoUnavailable") + (video.error && video.error.message ? ` ${video.error.message}` : ""));

    function image(path, token) {
      return new Promise((resolve, reject) => {
        const img = new Image();
        const finish = (error) => {
          aborts.delete(cancel); img.onload = img.onerror = null;
          if (error || !alive(token)) reject(error || new Error("Preview closed")); else resolve(img);
        };
        const cancel = () => { img.onload = img.onerror = null; img.src = ""; aborts.delete(cancel); reject(new Error("Preview closed")); };
        aborts.add(cancel);
        img.onload = () => finish(); img.onerror = () => finish(new Error(t("unavailable")));
        img.src = media(path);
      });
    }

    function videoReady(video, token) {
      return new Promise((resolve, reject) => {
        let metadataReady = false, firstFrame = null, frameRequest;
        const finish = (error) => {
          video.removeEventListener("loadedmetadata", loaded); video.removeEventListener("error", failed);
          if(frameRequest !== undefined)video.cancelVideoFrameCallback(frameRequest);
          aborts.delete(cancel);
          if (error || !alive(token)) reject(error || new Error("Preview closed")); else resolve(firstFrame);
        };
        const loaded = () => { metadataReady = true; if(firstFrame)finish(); };
        const failed = () => finish(videoError(video));
        const cancel = () => finish(new Error("Preview closed"));
        aborts.add(cancel); video.addEventListener("loadedmetadata", loaded); video.addEventListener("error", failed);
        if(!video.requestVideoFrameCallback){finish(new Error(t("videoUnavailable")));return;}
        // Register before src is assigned: even a fast initial decode must be
        // snapshotted when presented, rather than inferred from readyState.
        frameRequest = video.requestVideoFrameCallback(() => {
          if(!alive(token)){finish(new Error("Preview closed"));return;}
          firstFrame = snapshotVideo(video); if(metadataReady)finish();
        });
      });
    }

    function snapshotVideo(video) {
      const canvas = document.createElement("canvas"); canvas.width = video.videoWidth; canvas.height = video.videoHeight;
      canvas.getContext("2d").drawImage(video, 0, 0); return canvas;
    }

    async function loadSource(take, pane, token) {
      const source = { take, pane, frames: [], cache: new Map(), queue: Promise.resolve(), fps: 0, count: 0, duration: 0, rendered: false, error: null };
      if (!take || !take.media || take.state !== "ready") return source;
      try {
        const record = opts.clip.render;
        const rendered = ui.rendered && record && record.take === take.id && record.frameCount;
        if (rendered || take.media.dir) {
          const directory = rendered ? opts.clip.output : `production/clips/${opts.clip.id}/takes/${take.id}/${take.media.dir}`;
          const data = await ctx.api("/api/clips?root=" + encodeURIComponent(directory));
          if (!alive(token)) return source;
          source.frames = (Object.values(data.clips)[0] || {}).frames || [];
          source.count = source.frames.length;
          source.fps = rendered ? 1000 / record.frameIntervalMs : Number(take.media.fps);
          source.rendered = Boolean(rendered);
          source.render = rendered ? record : null;
        } else if (take.media.video) {
          const video = document.createElement("video");
          source.video = video; video.muted = true; video.playsInline = true; video.preload = "auto";
          video.className = "clip-compare-video";
          ctx.root.append(video);
          const ready = videoReady(video, token);
          video.src = media(`production/clips/${opts.clip.id}/takes/${take.id}/${take.media.video}`);
          const initialFrame = await ready;
          source.presented = {index:0,frame:initialFrame}; source.cache.set(0,Promise.resolve(initialFrame));
          source.fps = Number(take.media.fps); source.count = Number(take.media.count);
        }
        if (!alive(token)) { if (source.video) releaseVideo(source.video); return source; }
        if (!source.count || !(source.fps > 0) || !Number.isFinite(source.fps)) throw new Error(t("metadata"));
        source.duration = source.count / source.fps;
      } catch (error) { if (alive(token)) source.error = String(error.message || error); }
      return source;
    }

    function releaseVideo(video) { video.pause(); video.removeAttribute("src"); video.load(); video.remove(); }

    function videoFrame(source, index, token) {
      const video = source.video;
      const frameStart = index / source.fps;
      // A seek on a quantized timestamp boundary can present the preceding
      // frame. Seek inside the requested frame, then verify its native time.
      const target = Math.min((index + 0.5) / source.fps, Math.max(0, video.duration - 0.0001));
      if(source.presented && source.presented.index === index)return Promise.resolve(source.presented.frame);
      return new Promise((resolve, reject) => {
        let frameRequest;
        const finish = (error) => {
          video.removeEventListener("error", failed);
          if(frameRequest !== undefined)video.cancelVideoFrameCallback(frameRequest);
          aborts.delete(cancel);
          if (error || !alive(token)) { reject(error || new Error("Preview closed")); return; }
          const canvas = snapshotVideo(video); source.presented = {index,frame:canvas}; resolve(canvas);
        };
        const presented = (_, metadata) => {
          if(!alive(token)){finish(new Error("Preview closed"));return;}
          if(Math.abs(metadata.mediaTime-frameStart) <= 0.5/source.fps)finish();
          else frameRequest = video.requestVideoFrameCallback(presented);
        };
        const failed = () => finish(videoError(video));
        const cancel = () => finish(new Error("Preview closed"));
        aborts.add(cancel); video.addEventListener("error", failed);
        frameRequest = video.requestVideoFrameCallback(presented);
        video.currentTime = target;
      });
    }

    async function readFrame(source, time, token) {
      if (!source.count) return null;
      const index = Math.max(0, Math.min(source.count - 1, Math.floor(time * source.fps + 0.00001)));
      try {
        let promise = source.cache.get(index);
        if (!promise) {
          if (source.video) {
            promise = source.queue.then(() => videoFrame(source, index, token));
            source.queue = promise.catch(() => null);
          } else promise = image(source.frames[index], token);
          source.cache.set(index, promise);
          while (source.cache.size > 12) source.cache.delete(source.cache.keys().next().value);
        }
        const frame = await promise;
        if (!alive(token)) return null;
        source.error = null; source.current = index; return frame;
      } catch (error) { if (alive(token)) source.error = String(error.message || error); return null; }
    }

    function drawImage(canvas, frame, alpha = 1) {
      if (!frame) return;
      const painter = canvas.getContext("2d"); painter.globalAlpha = alpha;
      const scale = canvas.height / frame.height;
      const width = frame.width * scale;
      painter.drawImage(frame, (canvas.width - width) / 2, 0, width, canvas.height);
      painter.globalAlpha = 1;
    }

    function drawGuides(canvas, frame, source) {
      const anchors = ctx.state.character.anchors;
      if (!ui.guides || !frame || !anchors) return;
      const size = ctx.state.character.canvas;
      const scaleX = source.rendered ? 1 : frame.width / size.width;
      const scaleY = frame.height / size.height;
      const displayScale = canvas.height / frame.height;
      const x = (canvas.width - frame.width * displayScale) / 2 +
        ((source.rendered ? (frame.width - size.width) / 2 : 0) + anchors.headCenterX * scaleX) * displayScale;
      const y = anchors.headTopY * scaleY * displayScale;
      const painter = canvas.getContext("2d"); painter.strokeStyle = "#63E5CA"; painter.lineWidth = 1; painter.setLineDash([6, 4]);
      painter.beginPath(); painter.moveTo(0, y + 0.5); painter.lineTo(canvas.width, y + 0.5);
      painter.moveTo(x + 0.5, 0); painter.lineTo(x + 0.5, canvas.height); painter.stroke(); painter.setLineDash([]);
    }

    function draw() {
      if (painting) { paintAgain = true; return; }
      painting = true;
      const finish = () => { painting = false; if (paintAgain && !disposed) { paintAgain = false; draw(); } };
      const pending = paintFrame();
      pending.then(finish, (error) => { finish(); if (!disposed) ctx.toast(String(error.message || error), true); });
      return pending;
    }

    async function paintFrame() {
      const token = epoch;
      const displayedFrame = ui.frame;
      const time = frameTime();
      const mode = ui.mode;
      const frames = await Promise.all(sources.map((source) => readFrame(source, time, token)));
      if (!alive(token)) return;
      let neighbors = [];
      if (mode === "onion" && sources[0] && frames[0]) {
        neighbors = [await readFrame(sources[0], Math.max(0, time - 1 / sources[0].fps), token),
          await readFrame(sources[0], time + 1 / sources[0].fps, token)];
        if (!alive(token)) return;
      }
      if (mode === "side") {
        el.views.classList.remove("composite");
        el.panels.forEach((panel, index) => {
          panel.hidden = index === 1 && !opts.takeB;
          const canvas = el.canvases[index]; const frame = frames[index];
          if (frame) { canvas.width = frame.width; canvas.height = frame.height; drawImage(canvas, frame); drawGuides(canvas, frame, sources[index]); }
          else canvas.getContext("2d").clearRect(0, 0, canvas.width, canvas.height);
          el.messages[index].hidden = Boolean(frame); el.messages[index].textContent = sources[index] && sources[index].error || t("empty");
        });
      } else {
        el.views.classList.add("composite"); el.panels[1].hidden = true;
        const canvas = el.canvases[0];
        canvas.height = Math.max(1, ...frames.filter(Boolean).map((frame) => frame.height));
        canvas.width = Math.max(1, ...frames.filter(Boolean).map((frame) => Math.ceil(frame.width * canvas.height / frame.height)));
        const painter = canvas.getContext("2d");
        drawImage(canvas, frames[0], mode === "onion" ? 0.7 : 1);
        if (mode === "difference") painter.globalCompositeOperation = "difference";
        drawImage(canvas, frames[1], mode === "difference" ? 1 : 0.5);
        painter.globalCompositeOperation = "source-over";
        if (mode === "onion") neighbors.forEach((frame) => drawImage(canvas, frame, 0.18));
        drawGuides(canvas, frames[0], sources[0]);
        el.messages[0].hidden = frames.some(Boolean); el.messages[0].textContent = t("empty");
      }
      sources.forEach((source, index) => {
        const take = source.take; const number = take ? opts.clip.takes.findIndex((entry) => entry.id === take.id) + 1 : null;
        const status = take && ({ accepted: "statusAccepted", candidate: "statusCandidate", rejected: "statusRejected" })[take.status];
        const indexFrame = Math.min(source.count - 1, Math.floor(time * source.fps + 0.00001));
        el.labels[index].textContent = `${source.pane} ${number ? `v${number}` : ""}${status ? ` · ${t(status)}` : ""} · ${t(source.rendered ? "render" : "raw")}` +
          (source.count ? ` · ${t("frame", { frame: indexFrame, count: source.count })}` : "");
        el.canvases[index].dataset.frame = String(indexFrame);
      });
      el.frame.textContent = t("timelineFrame", { frame: displayedFrame, count: frameCount() });
      el.slider.max = String(frameCount() - 1); el.slider.value = String(displayedFrame);
      el.root.dataset.frame = String(displayedFrame); el.root.dataset.mode = mode;
    }

    function markers() {
      const nodes = [];
      const { h } = ctx;
      for (const source of sources) {
        if (!source.rendered || !source.render || source.render.take !== source.take.id) continue;
        const record = source.render;
        const add = (index, label, kind, detail) => {
          if (!Number.isInteger(index) || index < 0 || index >= source.count) return;
          // A common clock uses the higher source frame rate. Choose the first tick
          // at or after this QA frame, so a lower-rate pane shows that exact frame.
          const frame = Math.min(frameCount() - 1, Math.ceil(index / source.fps * timelineFps() - 0.00001));
          nodes.push(h("button", { class: `compare-marker ${kind}`, style: `left:${frame / Math.max(1, frameCount() - 1) * 100}%`,
            title: detail || label, "aria-label": label, "data-frame": frame, onclick: () => seek(frame) }, label));
        };
        for (const check of (record.qa && record.qa.checks) || []) {
          if (check.level === "pass") continue;
          const indices = check.frames || (check.check === "head" ? [0] : check.check === "tail" ? [source.count - 1] : check.check === "wrap" ? [0, source.count - 1] : []);
          for (const index of indices) add(index, t("qaFrame", { pane: source.pane, level: ctx.t(`production.status.${check.level}`), frame: index }), check.level, check.message);
        }
        const openness = record.mouth && record.mouth.openness;
        if (Array.isArray(openness) && openness.length === source.count && openness.every(Number.isFinite)) {
          const index = openness.reduce((best, value, index) => value > openness[best] ? index : best, 0);
          add(index, t("widest", { pane: source.pane, frame: index }), "mouth");
        }
        const wrap = record.qa && record.qa.wrap;
        if (wrap && Number.isFinite(wrap.faceL)) nodes.push(h("span", { class: `badge ${wrap.level} compare-seam` }, t("seam", { pane: source.pane, value: wrap.faceL })));
      }
      el.markers.replaceChildren(...nodes);
      el.markerNote.hidden = sources.some((source) => source.rendered);
      el.markerNote.textContent = t("qaUnavailable");
    }

    function controls() {
      el.play.textContent = t(ui.playing ? "pause" : "play"); el.play.setAttribute("aria-label", el.play.textContent);
      el.play.setAttribute("aria-pressed", String(ui.playing)); el.loop.checked = ui.loop;
      el.modeButtons.forEach((button, index) => { button.classList.toggle("active", ui.mode === modes[index]);
        button.setAttribute("aria-pressed", String(ui.mode === modes[index])); });
    }

    function seek(frame) {
      if (disposed) return;
      ui.frame = Math.max(0, Math.min(frameCount() - 1, Math.round(frame))); ui.elapsed = frameTime(); ui.lastTick = null;
      draw();
    }
    function step(delta) { if (ui.playing) togglePlay(); seek(ui.frame + delta); }
    function tick(now) {
      if (!ui.playing || disposed) return;
      if (ui.lastTick !== null) ui.elapsed += (now - ui.lastTick) / 1000 * ui.speed;
      ui.lastTick = now;
      if (ui.elapsed >= duration()) {
        if (ui.loop && duration()) ui.elapsed %= duration();
        else { ui.playing = false; ui.frame = frameCount() - 1; controls(); draw(); return; }
      }
      const frame = Math.min(frameCount() - 1, Math.floor(ui.elapsed * timelineFps()));
      if (frame !== ui.frame) { ui.frame = frame; draw(); }
      request = requestAnimationFrame(tick);
    }
    function togglePlay() {
      if (!duration() || disposed) return;
      ui.playing = !ui.playing; ui.lastTick = null; cancelAnimationFrame(request);
      if (ui.playing) { if (ui.frame === frameCount() - 1) seek(0); request = requestAnimationFrame(tick); }
      controls();
    }
    function toggleMode() { const allowed = opts.takeB ? modes : ["side"]; ui.mode = allowed[(allowed.indexOf(ui.mode) + 1) % allowed.length]; controls(); draw(); }
    function toggleLoop() { ui.loop = !ui.loop; controls(); }

    function build() {
      const { h } = ctx;
      el = {};
      el.modeButtons = modes.map((mode) => h("button", { title: mode === "onion" ? t("onionHint") : !opts.takeB && mode !== "side" ? t("chooseB") : null,
        disabled: !opts.takeB && mode !== "side", onclick: () => { ui.mode = mode; controls(); draw(); } }, t(mode)));
      el.labels = [h("div", { class: "compare-source-label mono" }), h("div", { class: "compare-source-label mono" })];
      el.canvases = [h("canvas", { width: 1, height: 1, "aria-label": "A" }), h("canvas", { width: 1, height: 1, "aria-label": "B" })];
      el.messages = [h("span", { class: "compare-media-message" }, t("loading")), h("span", { class: "compare-media-message" }, t("loading"))];
      el.panels = el.canvases.map((canvas, index) => h("div", { class: "compare-pane", "data-pane": index ? "B" : "A" }, el.labels[index], h("div", { class: "compare-frame" }, canvas, el.messages[index])));
      el.views = h("div", { class: "compare-views" }, el.panels);
      el.markers = h("div", { class: "compare-markers" }); el.markerNote = h("p", { class: "tiny compare-marker-note" }, t("qaUnavailable"));
      el.slider = h("input", { class: "compare-slider", type: "range", min: 0, max: Math.max(0, frameCount() - 1), value: ui.frame,
        "aria-label": t("seek"), oninput: (event) => seek(Number(event.target.value)) });
      el.play = h("button", { class: "primary compare-play", onclick: togglePlay });
      el.frame = h("span", { class: "mono compare-frame-number" });
      el.loop = h("input", { type: "checkbox", checked: ui.loop, onchange: toggleLoop });
      const speed = h("select", { "aria-label": t("speed"), onchange: () => { ui.speed = Number(speed.value); ui.lastTick = null; } },
        [0.5, 1].map((value) => h("option", { value }, `${value}×`))); speed.value = ui.speed;
      const ends = h("input", { type: "checkbox", checked: ui.ends, onchange: () => { ui.ends = ends.checked; el.stills.hidden = !ui.ends; } });
      const guides = h("input", { type: "checkbox", checked: ui.guides, onchange: () => { ui.guides = guides.checked; draw(); } });
      const rendered = h("input", { type: "checkbox", checked: ui.rendered, onchange: () => { ui.rendered = rendered.checked; reload(); } });
      el.stills = h("div", { class: "compare-approved-stills", hidden: !ui.ends });
      el.root = h("div", { class: "clip-compare" }, h("div", { class: "compare-toolbar" },
        h("div", { class: "compare-modes", role: "group", "aria-label": t("modes") }, el.modeButtons),
        h("div", { class: "compare-options" }, h("label", {}, ends, t("ends")), h("label", {}, guides, t("guides")), h("label", { title: t("renderHint") }, rendered, t("rendered")))),
        el.views, el.stills, h("div", { class: "compare-timeline" }, el.markers, el.slider), el.markerNote,
        h("div", { class: "compare-controls" }, h("button", { "aria-label": t("previous"), onclick: () => step(-1) }, "‹"), el.play,
          h("button", { "aria-label": t("next"), onclick: () => step(1) }, "›"), el.frame,
          h("label", {}, el.loop, t("loop")), h("label", {}, t("speed"), speed)));
      ctx.root.replaceChildren(el.root); sources.forEach((source) => { if (source.video) ctx.root.append(source.video); });
      controls(); markers();
    }

    function showStills() {
      const { h } = ctx;
      stills = [opts.clip.from, opts.clip.to].map((id) => {
        const pose = ctx.state.poses.find((entry) => entry.id === id);
        const take = pose && pose.takes.find((entry) => entry.id === pose.acceptedTake);
        return take && take.media && take.media.still ? `production/poses/${id}/takes/${take.id}/${take.media.still}` : null;
      });
      el.stills.replaceChildren(...stills.map((path, index) => path ? h("figure", {}, h("img", { src: media(path), alt: t(index ? "end" : "start") }), h("figcaption", { class: "tiny" }, t(index ? "end" : "start"))) : null).filter(Boolean));
    }

    async function reload() {
      signature = mediaSignature(opts);
      const token = ++epoch;
      for (const cancel of [...aborts]) cancel();
      sources.forEach((source) => { if (source.video) releaseVideo(source.video); }); sources = [];
      build(); showStills();
      const clip = opts.clip;
      const loaded = await Promise.all([opts.takeA, opts.takeB].map((take, index) => loadSource(take, index ? "B" : "A", token)));
      if (!alive(token)) { loaded.forEach((source) => { if (source.video) releaseVideo(source.video); }); return; }
      // The loaded sources retain the exact raw-take or explicit matching-render identity.
      if (clip.id !== opts.clip.id) return;
      sources = loaded; ui.frame = Math.min(ui.frame, frameCount() - 1); ui.elapsed = frameTime(); ui.lastTick = null;
      markers(); await draw();
    }

    function mediaSignature(value) {
      return JSON.stringify([value.clip.id, value.takeA && [value.takeA.id, value.takeA.state, value.takeA.media],
        value.takeB && [value.takeB.id, value.takeB.state, value.takeB.media], ui.rendered && value.clip.render]);
    }
    function update(nextCtx, nextOptions = opts) {
      const nextSignature = mediaSignature(nextOptions);
      ctx = nextCtx; opts = nextOptions;
      if (!opts.takeB) ui.mode = "side";
      if (signature !== nextSignature) { signature = nextSignature; reload(); }
      else {
        sources.forEach((source, index) => { source.take = index ? opts.takeB : opts.takeA; });
        build(); showStills(); draw();
      }
    }
    update(ctx, opts);
    return { update, togglePlay, toggleMode, toggleLoop, step, seek, cleanup() {
      disposed = true; epoch++; cancelAnimationFrame(request);
      for (const cancel of [...aborts]) cancel();
      sources.forEach((source) => { if (source.video) releaseVideo(source.video); source.cache.clear(); });
      sources = []; ctx.root.replaceChildren();
    } };
  }
  window.SFClipCompare = { mount };
})();
