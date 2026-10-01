"use strict";
(() => {
  const entries = {
    en: {
      title: "Behavior", graph: "Graph", stats: "Stats", unsaved: "{count} unsaved changes", select: "Select", node: "Node", edge: "Edge", populate: "Populate",
      normalize: "Normalize", fit: "Fit", expand: "Expand", collapse: "Collapse", clear: "Clear", validate: "Validate", save: "Save", load: "Load",
      canvasHint: "Scroll to zoom; drag empty space to pan", zoomOut: "Zoom out", zoomIn: "Zoom in", editorHint: "Select a node to preview its exact clip. Right click a node or edge to delete it.",
      label: "Label", frames: "Frames", phase: "Phase", interval: "Frame interval (ms)", playback: "Playback", flat: "Files directly in root", in: "in subfolder", loop: "Loop", out: "out subfolder",
      hold: "Play once, then hold", root: "Root pivot node", preview: "Preview selected clip", deleteNode: "Delete node", deleteEdge: "Delete edge",
      weight: "Traversal weight (0 = manual)", manual: "manual", manualHint: "Manual edges are triggered by Amadeus intents.", outgoing: "Outgoing weights", issues: "Issues for this selection",
      noIssues: "No recorded issues for this selection.", review: "Open Review", play: "Play", pause: "Pause", previous: "Previous frame", next: "Next frame", fps: "FPS · clip timing", emptyPlayer: "Select a node to preview its clip.",
      routePlay: "Play tested graph route", routeHint: "Each route segment plays its actual frames once. This previews graph routing; it does not simulate Amadeus speech hold/release timing.",
      clearConfirm: "Clear all nodes and edges?", chance: "Normalized chance: {value}%", edgeExists: "Edge already exists", edgeFrom: "Edge from {label} — click target", normalized: "Normalized",
      nodesAdded: "+{count} nodes added", noNewStates: "No new states (bind a production output first)", valid: "Valid topology and frame bindings", saved: "Saved", loaded: "Loaded", saveFailed: "Save failed", loadFailed: "Load failed",
      error: "Error: {error}", exactPreview: "Exact selected clip · {interval} ms · {loop}", previewFailed: "Preview failed: {error}", jump: "jump {value}px",
      minutes: "Minutes", seed: "Seed", rerun: "Run again", loading: "Calculating saved graph…", savedOnly: "Stats uses the saved graph. Save editor changes before running it.",
      canShip: "Can this graph ship?", blocking: "Blocking issues", outOfDate: "Out of date", unreachable: "Unreachable from root", deadEnds: "Dead ends", intentOnly: "Intent-only nodes", intentExitLoops: "Loops with intent exits only",
      occupancy: "Where does automatic playback spend time?", noGraph: "The saved graph has no root to simulate.", seconds: "{value} s", percentMinutes: "{percent}% · {minutes} min", visits: "{count} visits", duration: "Clip duration: {value} s", unknownDuration: "Clip duration unavailable",
      changes: "Transitions", rate: "Changes per minute", autoUsed: "Automatic edges used", seamFailures: "Visited failing seams", coverage: "Is pose coverage complete?", pose: "Pose", enter: "Enter", speaking: "Speaking", exit: "Exit", unavailable: "Unavailable", notApplicable: "N/A", inGraph: "In graph", notInGraph: "Not in graph",
      triggers: "Do intent triggers reach their targets?", triggerHint: "Events apply at the next node boundary. A manual first hop is forced; subsequent traversal follows automatic weights. This tests graph routes only, without speech hold/release timing.",
      runInfo: "{minutes} min · seed {seed}", available: "{count} available", notApplied: "Not applied in this interval", targets: "Targets", visitedTargets: "Visited targets", appliedAt: "Applied at {value} s",
      addEvent: "Add event", remove: "Remove", at: "At (seconds)", eventType: "Event type", speech: "Speech", labelEvent: "Label", eventLabel: "Target label", runTriggers: "Test triggers", reached: "Reached", reachable: "Reachable, not reached in this run", notReachable: "Unreachable", diagnosticPath: "Reachability path (diagnostic)", actualRoute: "Played route", noEvents: "Add label or speech events to test graph routing.",
      noItems: "None", stale: "Render out of date", missing: "Render missing", bound: "{clip} · {state}", noBinding: "No recorded production binding", selectNode: "Open node {label}", selectEdge: "Open edge {label}"
    },
    "zh-CN": {
      title: "行为", graph: "图", stats: "统计", unsaved: "{count} 处未保存更改", select: "选择", node: "节点", edge: "边", populate: "填入", normalize: "归一化", fit: "适应视图", expand: "展开", collapse: "收起", clear: "清空", validate: "验证", save: "保存", load: "加载",
      canvasHint: "滚轮缩放；拖动空白处平移", zoomOut: "缩小", zoomIn: "放大", editorHint: "选择节点可预览其准确片段。右键节点或边可删除。", label: "标签", frames: "帧目录", phase: "阶段", interval: "帧间隔（ms）", playback: "播放方式", flat: "根目录中的帧", in: "in 子目录", loop: "循环", out: "out 子目录", hold: "播放一次后停留", root: "根枢纽节点", preview: "预览所选片段", deleteNode: "删除节点", deleteEdge: "删除边",
      weight: "遍历权重（0 = 手动）", manual: "手动", manualHint: "手动边由 Amadeus 意图触发。", outgoing: "出边权重", issues: "所选对象的问题", noIssues: "所选对象没有已记录的问题。", review: "打开审阅", play: "播放", pause: "暂停", previous: "上一帧", next: "下一帧", fps: "FPS · 片段时序", emptyPlayer: "选择节点以预览其片段。",
      routePlay: "播放已测试的图路线", routeHint: "路线中的每段按真实帧播放一次。此功能预览图路由，不模拟 Amadeus 说话保持/释放时序。", clearConfirm: "清空所有节点和边？", chance: "归一化概率：{value}%", edgeExists: "此边已存在", edgeFrom: "从 {label} 连边 — 点击目标", normalized: "已归一化", nodesAdded: "已添加 {count} 个节点", noNewStates: "没有新状态（请先绑定生产输出）", valid: "拓扑和帧绑定有效", saved: "已保存", loaded: "已加载", saveFailed: "保存失败", loadFailed: "加载失败", error: "错误：{error}", exactPreview: "所选准确片段 · {interval} ms · {loop}", previewFailed: "预览失败：{error}", jump: "跳变 {value}px",
      minutes: "分钟", seed: "种子", rerun: "重新运行", loading: "正在计算已保存的图…", savedOnly: "统计使用已保存的图。运行前请保存编辑更改。", canShip: "此图能否发布？", blocking: "阻断问题", outOfDate: "已过期", unreachable: "从根不可达", deadEnds: "死路", intentOnly: "仅意图可达节点", intentExitLoops: "仅通过意图退出的循环", occupancy: "自动播放的时间花在哪里？", noGraph: "已保存的图没有可供模拟的根节点。", seconds: "{value} 秒", percentMinutes: "{percent}% · {minutes} 分钟", visits: "访问 {count} 次", duration: "片段时长：{value} 秒", unknownDuration: "片段时长未知", changes: "转换次数", rate: "每分钟转换", autoUsed: "已使用自动边", seamFailures: "访问过的失败接缝", coverage: "表情覆盖是否完整？", pose: "表情", enter: "进入", speaking: "说话", exit: "退出", unavailable: "不可用", notApplicable: "不适用", inGraph: "在图中", notInGraph: "不在图中",
      runInfo: "{minutes} 分钟 · 种子 {seed}", available: "可用 {count} 个", notApplied: "本时段内未应用", targets: "目标", visitedTargets: "已访问的目标", appliedAt: "在 {value} 秒应用",
      triggers: "意图触发是否到达目标？", triggerHint: "事件在下一个节点边界生效。强制执行首条手动边，随后按自动权重遍历。这里只测试图路线，不模拟说话保持/释放时序。", addEvent: "添加事件", remove: "移除", at: "时间（秒）", eventType: "事件类型", speech: "说话", labelEvent: "标签", eventLabel: "目标标签", runTriggers: "测试触发", reached: "已到达", reachable: "可达，本次尚未到达", notReachable: "不可达", diagnosticPath: "可达路径（诊断）", actualRoute: "实际播放路线", noEvents: "添加标签或说话事件来测试图路由。", noItems: "无", stale: "渲染已过期", missing: "尚未渲染", bound: "{clip} · {state}", noBinding: "没有已记录的生产绑定", selectNode: "打开节点 {label}", selectEdge: "打开边 {label}"
    }
  };
  for (const [lang, dict] of Object.entries(entries)) window.SFStudio.addTranslations(lang,
    Object.fromEntries(Object.entries(dict).map(([key, value]) => ["behavior." + key, value])));
  let testedRoute = null;
  const graphLink = (key) => "#/behavior/graph?select=" + encodeURIComponent(key);
  const issues = (ctx) => ctx.state.issues;
  const reviewLink = (issue) => "#/review/" + encodeURIComponent(issue.key) + (["node","edge"].includes(issue.kind) ? "?mode=edit" : "");
  function tabs(ctx, active) {
    return ctx.h("nav", { class: "behavior-tabs", "aria-label": ctx.t("behavior.title") }, ...["graph", "stats"].map(tab =>
      ctx.h("a", { class: "btn " + (active === tab ? "active" : ""), href: "#/behavior/" + tab }, ctx.t("behavior." + tab))));
  }
  function graphMount(context) {
    let ctx = context, disposed = false, runtime, baseline, selectedKey = null, lastSelect = null, language = window.SFStudio.language;
    const root = ctx.root, h = ctx.h, t = (key, values) => ctx.t("behavior." + key, values);
    const text = (tag, key, attrs = {}) => h(tag, { ...attrs, "data-behavior-text": key }, t(key));
    const button = (id, key, attrs = {}) => text("button", key, { id, ...attrs });
    const field = (key, control) => h("label", {}, text("span", key), control);
    const option = (value, key) => text("option", key, { value });
    const extra = h("div", { class: "behavior-selection-extra" });
    const count = text("span", "unsaved", { class: "tiny behavior-dirty" });
    const frameRoot = h("select", { id: "gNRoot" });
    const panel = h("section", { class: "behavior-graph review-inspector", id: "graphPanel" },
      h("div", { class: "behavior-toolbar" }, button("gModeSelect", "select", { class: "active" }), button("gModeNode", "node"), button("gModeEdge", "edge"),
        button("gPopulate", "populate"), button("gNormalize", "normalize"), button("gResetView", "fit"), h("button", { id: "gZoomOut", "aria-label": t("zoomOut") }, "−"),
        h("span", { id: "gZoomLabel" }, "100%"), h("button", { id: "gZoomIn", "aria-label": t("zoomIn") }, "+"), button("gExpand", "expand"), button("gClear", "clear", { class: "danger" }),
        button("gValidate", "validate"), button("gSave", "save", { class: "primary" }), button("gLoad", "load")),
      text("p", "editorHint", { class: "tiny" }), h("div", { id: "gStatus", class: "tiny", role: "status" }),
      h("div", { class: "behavior-graph-body" }, h("div", { id: "graphViewport" }, h("canvas", { id: "graphCanvas", "aria-label": t("graph") })),
        h("aside", { class: "behavior-properties" }, h("div", { id: "graphProperties", hidden: true },
          h("div", { id: "gNodeProp", style: "display:none" }, text("h2", "node"), field("label", h("input", { id: "gNLabel" })), field("frames", frameRoot),
            field("phase", h("select", { id: "gNPhase" }, option("flat", "flat"), option("in", "in"), option("loop", "loop"), option("out", "out"))),
            field("interval", h("input", { id: "gNInterval", type: "number", min: 1, step: 1 })),
            field("playback", h("select", { id: "gNLoop" }, option("loop", "loop"), option("once_then_hold", "hold"))),
            h("label", { class: "behavior-check" }, h("input", { id: "gNIsRoot", type: "checkbox" }), text("span", "root")),
            h("div", { class: "behavior-actions" }, button("gNView", "preview"), button("gNDel", "deleteNode", { class: "danger" }))),
          h("div", { id: "gEdgeProp", style: "display:none" }, text("h2", "edge"), h("div", { id: "gEFromTo", class: "tiny" }),
            field("weight", h("input", { id: "gEProb", type: "number", min: 0, step: "any" })), h("div", { id: "gEWarn", class: "tiny" }),
            text("div", "manualHint", { id: "gEManual", class: "tiny" }), button("gEDel", "deleteEdge", { class: "danger" }))),
          h("div", { class: "behavior-player" }, h("div", { class: "behavior-frame-stage" }, h("img", { id: "frame", alt: t("preview"), style:"display:none" }), h("div", { id: "ktxStage", style: "display:none" }), h("canvas", { id: "mouthCanvas", hidden: true })),
            text("div", "emptyPlayer", { id: "now", class: "tiny" }), h("div", { class: "behavior-actions" }, button("prevBtn", "previous"), button("playBtn", "play"), button("pauseBtn", "pause"), button("nextBtn", "next")),
            field("fps", h("input", { id: "fps", type: "number", readonly: true }))), extra)));
    const routeButton = text("button", "routePlay", { disabled: !testedRoute, onclick: () => runtime.previewRoute(testedRoute.route.map(segment => segment.node)) });
    root.replaceChildren(h("div", { class: "behavior-page" }, text("h1", "title", {class:"sr-only"}), h("header", { class: "behavior-heading" }, tabs(ctx, "graph"), count), panel,
      h("div", { class: "behavior-route" }, routeButton, text("p", "routeHint", { class: "tiny" }))));
    const selectionIssues = (selection, graph) => {
      if (!selection) return [];
      if (selection.type === "node") return issues(ctx).filter(issue => issue.node === selection.id);
      const edge = graph.edges.find(item => item.id === selection.id);
      return edge ? issues(ctx).filter(issue => issue.key === "edge:" + edge.from + "->" + edge.to) : [];
    };
    function roots(graph) {
      const current = frameRoot.value;
      const paths = [...new Set(["", ...ctx.state.clips.map(clip => clip.output).filter(Boolean), ...graph.nodes.map(node => node.root).filter(Boolean)])];
      frameRoot.replaceChildren(...paths.map(path => h("option", { value: path }, path || "—"))); frameRoot.value = current;
    }
    function dirty(graph) {
      if (!baseline) return 0;
      let changes = 0;
      for (const key of ["nodes", "edges"]) {
        const before = new Map(baseline[key].map(item => [item.id, JSON.stringify(item)]));
        for (const item of graph[key]) { if (before.get(item.id) !== JSON.stringify(item)) changes++; before.delete(item.id); }
        changes += before.size;
      }
      return changes;
    }
    function selected(selection, graph, force = false) {
      if (!force && extra.contains(document.activeElement)) return;
      extra.replaceChildren();
      if (!selection) return;
      const node = selection.type === "node" && graph.nodes.find(item => item.id === selection.id);
      if (node) {
        const clip = ctx.state.clips.find(item => item.output === node.root);
        extra.append(h("p", { class: "tiny" }, clip ? t("bound", { clip: clip.id, state: clip.render.state }) : t("noBinding")), text("h3", "outgoing"));
        for (const edge of graph.edges.filter(item => item.from === node.id)) {
          const target = graph.nodes.find(item => item.id === edge.to);
          const input = h("input", { type: "number", min: 0, step: "any", value: edge.prob, "aria-label": t("weight"), oninput: () => {
            const value = Number(input.value); if (input.value !== "" && Number.isFinite(value) && value >= 0) { edge.prob = value; runtime.draw(); }
          }, onblur: () => selected(runtime.selection, runtime.graph, true) });
          extra.append(h("label", {}, h("a", { href: graphLink("edge:" + edge.from + "->" + edge.to) }, target ? target.label : edge.to), input,
            edge.prob === 0 ? h("span", { class: "tiny" }, t("manualHint")) : null));
        }
        extra.append(h("button", { onclick: () => runtime.normalize() }, t("normalize")));
      }
      extra.append(text("h3", "issues"));
      const found = selectionIssues(selection, graph);
      extra.append(found.length ? h("ul", {}, ...found.map(issue => h("li", {}, h("span", { class: "pill " + issue.level }, issue.level), " ", h("a",{href:reviewLink(issue)},issue.message)))) : text("p", "noIssues", { class: "tiny" }));
      extra.append(h("a", { href: "#/review?mode=edit", class: "btn" }, t("review")), h("a", { href: "#/behavior/stats", class: "btn" }, t("stats")));
    }
    function facade() {
      return { ...ctx, root: panel,
        nodeIssue: node => { const clip = ctx.state.clips.find(item => item.output === node.root); return clip && ["missing", "stale"].includes(clip.render.state); },
        edgeIssue: edge => { const issue = issues(ctx).find(item => item.key === "edge:" + edge.from + "->" + edge.to && item.level === "fail");
          if (baseline && runtime && [edge.from,edge.to].some(id => { const original = baseline.nodes.find(item=>item.id===id), current = runtime.graph.nodes.find(item=>item.id===id);
            return !original || !current || ["root","phase","frameIntervalMs","loopMode"].some(key=>original[key]!==current[key]); })) return null;
          return issue ? t("jump", { value: Math.max(Math.abs(issue.dHeadTop || 0), Math.abs(issue.dHeadCenter || 0)).toFixed(1) }) : null; },
        onSaved: (graph, action) => { baseline = structuredClone(graph); roots(graph); if(action === "save")ctx.refresh().catch(error=>ctx.toast(String(error),"error")); },
        onChange: (graph, selection) => { count.textContent = t("unsaved", { count: dirty(graph) }); selected(selection, graph); },
        onSelection: (selection, graph) => { roots(graph); selected(selection, graph, true);
          const key = selection && selection.type + ":" + selection.id;
          if (key !== selectedKey) { selectedKey = key; if (selection && selection.type === "node") queueMicrotask(() => { if (!disposed && selectedKey === key) runtime.previewNode(graph.nodes.find(node => node.id === selection.id)); }); }
        }
      };
    }
    runtime = window.SFReview.create(facade()); runtime.setClips(ctx.state.clips);
    runtime.load().then(() => { if (!disposed && ctx.route.select) { lastSelect = ctx.route.select; runtime.select(lastSelect); } });
    return { update(next) {
      ctx = next; runtime.update(facade()); runtime.setClips(ctx.state.clips);
      if (language !== window.SFStudio.language) {
        language = window.SFStudio.language;
        for (const node of root.querySelectorAll("[data-behavior-text]")) {
          if (!node.classList.contains("behavior-dirty") && node.id !== "now") node.textContent = t(node.dataset.behaviorText);
        }
        root.querySelector(".behavior-tabs").replaceWith(tabs(ctx, "graph")); selected(runtime.selection, runtime.graph, true);
        root.querySelector("#gZoomOut").setAttribute("aria-label",t("zoomOut"));root.querySelector("#gZoomIn").setAttribute("aria-label",t("zoomIn"));
        root.querySelector("#gExpand").textContent=t(panel.classList.contains("graph-expanded")?"collapse":"expand");
        root.querySelector("#graphCanvas").setAttribute("aria-label",t("graph"));root.querySelector("#frame").setAttribute("alt",t("preview"));
      }
      if (next.route.select && next.route.select !== lastSelect) { lastSelect = next.route.select; runtime.select(lastSelect); }
    }, cleanup() { disposed = true; runtime.cleanup(); }, runtime };
  }

  function statsMount(context) {
    let ctx = context, disposed = false, epoch = 0, result = null, triggerResult = null, loading = false, language = window.SFStudio.language;
    const ui = { minutes: 10, seed: 1, events: [], expanded: new Set() };
    const t = (key, values) => ctx.t("behavior." + key, values);
    const number = (value, digits = 1) => Number(value || 0).toFixed(digits);
    const nodeLink = (item) => ctx.h("a", { href: graphLink("node:" + (item.id || item.node)) }, item.label || item.id || item.node || item.message);
    async function load() {
      const token = ++epoch; loading = true; build();
      try { const data = await ctx.api(`/api/behavior/stats?minutes=${ui.minutes}&seed=${ui.seed}`); if (disposed || token !== epoch) return; result = data; }
      catch (error) { if (!disposed && token === epoch) ctx.toast(String(error.message || error), "error"); }
      finally { if (!disposed && token === epoch) { loading = false; build(); } }
    }
    function details(key, title, children) {
      return ctx.h("details", { open: ui.expanded.has(key), ontoggle: event => event.currentTarget.open ? ui.expanded.add(key) : ui.expanded.delete(key) }, ctx.h("summary", {}, title), ...children);
    }
    function issueLink(issue) {
      const key = issue.kind === "edge" ? "edge:" + issue.from + "->" + issue.to : issue.node ? "node:" + issue.node : null;
      return key ? ctx.h("a", { href: graphLink(key) }, issue.message || key) : ctx.h("a", { href: reviewLink(issue) }, issue.message || issue.id || issue.label);
    }
    function build() {
      const { h } = ctx;
      const minutes = h("select", { value: ui.minutes, onchange: () => { ui.minutes = Number(minutes.value); triggerResult = null; load(); } }, ...[10, 30, 60].map(value => h("option", { value, selected: value === ui.minutes }, value)));
      const seed = h("input", { type: "number", min: 0, max: 4294967295, step: 1, value: ui.seed, onchange: () => { ui.seed = Number(seed.value); } });
      const header = h("header", { class: "behavior-heading" }, tabs(ctx, "stats"), h("div", { class: "behavior-actions" }, h("label", {}, t("minutes"), minutes), h("label", {}, t("seed"), seed), h("button", { disabled: loading, onclick: load }, t("rerun"))));
      const content = [h("h1", {class:"sr-only"},t("stats")), header, h("p", { class: "tiny" }, t("savedOnly"))];
      if (loading) content.push(h("p", { role: "status" }, t("loading")));
      if (result) {
        content.push(h("p", {class:"tiny"},t("runInfo",result)), h("h2", {}, t("canShip")), h("div", { class: "behavior-ship" }, ...Object.entries(result.ship).map(([key, items]) => details("ship:" + key, t(key) + " · " + items.length,
          [items.length ? h("ul", {}, ...items.map(item => h("li", {}, key === "blocking" ? issueLink(item) : nodeLink(item)))) : h("p", { class: "tiny" }, t("noItems"))]))));
        content.push(h("h2", {}, t("occupancy")));
        if (!result.root) content.push(h("p", { class: "tiny" }, t("noGraph")));
        const sim = result.simulation;
        content.push(h("div", { class: "behavior-metrics" }, ...[["changes", sim.changes], ["rate", number(sim.changesPerMinute)], ["autoUsed", sim.autoEdgesUsed.length + " / " + sim.autoEdgesTotal], ["seamFailures", sim.visitedSeamFailures.length]].map(([key, value]) => h("div", { class: "card" }, h("strong", {}, value), h("span", {}, t(key))))));
        const groupRows = result.groups.map((group, index) => {
          const title = h("span", { class: "behavior-share" }, h("span", {}, group.label), h("meter", { min: 0, max: 1, value: group.share }),
            h("span", {}, t("percentMinutes", { percent: number(group.share * 100), minutes: number(group.seconds / 60) })));
          const nodes = group.nodes.map(node => h("div", { class: "behavior-node-stat" }, nodeLink(node),
            h("span", {}, t("percentMinutes", { percent: number(node.share * 100), minutes: number(node.seconds / 60) })),
            h("span", { class: "tiny" }, t("visits", { count: node.visits }), " · ",
              node.durationKnown ? t("duration", { value: number(node.durationS, 2) }) : t("unknownDuration"))));
          return details("group:" + index, title, nodes);
        });
        content.push(h("div", { class: "behavior-groups" }, ...groupRows));
        content.push(h("h2", {}, t("coverage")), h("table", { class: "behavior-coverage" }, h("thead", {}, h("tr", {}, ...["pose", "enter", "loop", "speaking", "exit"].map(key => h("th", {}, t(key))))), h("tbody", {}, ...result.coverage.map(row => h("tr", {}, h("td", {}, row.pose, h("div", { class: "tiny" }, t(row.inGraph ? "inGraph" : "notInGraph"))), ...["enter", "loop", "speaking", "exit"].map(key => {
          const cell = row[key]; return h("td", {}, !cell.applicable ? t("notApplicable") : cell.clips.length ?
            [h("div", {class:"tiny"},t("available",{count:cell.available}),cell.level ? " · "+cell.level : ""),...cell.clips.map(id => h("a", { href: "#/clips/" + encodeURIComponent(id), class: "pill " + (cell.level || "") }, id))] : t("unavailable"));
        }))))));
      }
      const eventRows = ui.events.map((event, index) => {
        const at = h("input", { type: "number", min: 0, max: ui.minutes * 60, step: "any", value: event.atS, "aria-label": t("at"), oninput: () => event.atS = Number(at.value) });
        const kind = h("select", { "aria-label": t("eventType"), onchange: () => { event.speech = kind.value === "speech"; build(); } }, h("option", { value: "label", selected: !event.speech }, t("labelEvent")), h("option", { value: "speech", selected: event.speech }, t("speech")));
        const label = h("input", { value: event.label || "", "aria-label": t("eventLabel"), oninput: () => event.label = label.value });
        return h("div", { class: "behavior-event" }, at, kind, event.speech ? null : label, h("button", { onclick: () => { ui.events.splice(index, 1); build(); } }, t("remove")));
      });
      content.push(h("section", { class: "behavior-triggers card" }, h("h2", {}, t("triggers")), h("p", { class: "tiny" }, t("triggerHint")), ...eventRows,
        h("div", { class: "behavior-actions" }, h("button", { onclick: () => { ui.events.push({ atS: 0, label: "", speech: false }); build(); } }, t("addEvent")), h("button", { disabled: loading || !ui.events.length, onclick: async event => {
          event.currentTarget.disabled = true; const token = ++epoch;
          try { const data = await ctx.api("/api/production/behavior/trigger-test", { minutes: ui.minutes, seed: ui.seed, events: ui.events.map(item => item.speech ? { atS: item.atS, speech: true } : { atS: item.atS, label: item.label }) });
            if (!disposed && token === epoch) { triggerResult = data; testedRoute = data; build(); }
          } catch (error) { if (!disposed) { ctx.toast(String(error.message || error), "error"); build(); } }
        } }, t("runTriggers"))), !ui.events.length ? h("p", { class: "tiny" }, t("noEvents")) : null,
        triggerResult ? h("div", {}, h("p", {class:"tiny"},t("runInfo",triggerResult)), ...triggerResult.events.map(event => h("div", { class: "behavior-trigger-result" }, h("strong", {}, `${event.atS}s · ${event.speech ? t("speech") : event.label} · ${t(event.appliedAtS === null ? "notApplied" : event.reached ? "reached" : event.reachable ? "reachable" : "notReachable")}`),
          event.appliedAtS !== null ? h("div", { class: "tiny" }, t("appliedAt",{value:number(event.appliedAtS)})) : null,
          h("div", { class: "tiny" }, t("targets") + ": ", event.targets.map(id=>nodeLink({id}))),
          h("div", { class: "tiny" }, t("visitedTargets") + ": ", event.visitedTargets.map(id=>nodeLink({id}))),
          h("div", { class: "tiny" }, t("diagnosticPath") + ": ", event.path.map((id,index)=>[index ? " → " : "",nodeLink({id})])))), details("actualRoute", t("actualRoute") + " · " + triggerResult.route.length,
          [h("ol", { class: "behavior-route-list" }, ...triggerResult.route.map(segment => h("li", {}, nodeLink({ id: segment.node, label: segment.label }), ` · ${number(segment.startS)}s · ${number(segment.durationS)}s`, segment.seamFail ? h("span", { class: "pill fail" }, t("seamFailures")) : null)))]),
          h("a", { class: "btn", href: "#/behavior/graph" }, t("routePlay"))) : null));
      ctx.root.replaceChildren(h("div", { class: "behavior-page behavior-stats" }, ...content));
    }
    load();
    return { update(next) { ctx = next; if (language !== window.SFStudio.language) { language = window.SFStudio.language; build(); } }, cleanup() { disposed = true; epoch++; } };
  }
  window.SFStudio.register("behavior", ctx => ctx.route.id === "stats" ? statsMount(ctx) : graphMount(ctx));
})();
