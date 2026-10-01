"use strict";
(() => {
  const stages = ["overview", "expressions", "clips", "workflows", "review", "behavior", "export"];
  const modeStages = { produce: ["overview", "expressions", "clips", "review"], edit: ["overview", "behavior", "review", "export"] };
  const tools = ["canvas", "prompts", "jobs", "settings"];
  const renderers = new Map();
  const toolRenderers = new Map();
  const pending = new Set();
  const docs = "https://github.com/Code-Amadeus/Amadeus-SpriteForge/blob/main/docs/production.md";
  const initCommand = "spriteforge production init --workspace <path> --id <id> --display-name <name> --canvas <W>x<H>";
  let state = null;
  let jobs = [];
  let route = readRoute();
  const lastModeRoute = { produce: null, edit: null };
  let lastGuidedRoute = null;
  let language = preference("spriteforge.lang") === "zh-CN" ? "zh-CN" : "en";
  let mainMount = null;
  let drawerMount = null;
  let mainKey = null;
  let drawerTool = null;
  let pollTimer = null;
  let refreshQueue = Promise.resolve();
  let errorMessage = null;
  let drawerOpener = null;
  let started = false;
  const byId = (id) => document.getElementById(id);

  function preference(key, value) {
    try {
      if (value === undefined) return localStorage.getItem(key);
      localStorage.setItem(key, String(value));
    } catch (_) { /* Preferences are optional when browser storage is unavailable. */ }
    return null;
  }

  function t(key, values = {}) {
    const dict = window.SF_I18N || {};
    const text = (dict[language] || {})[key] ?? (dict.en || {})[key] ?? key;
    return String(text).replace(/\{([^}]+)\}/g, (match, name) => values[name] === undefined ? match : String(values[name]));
  }

  function h(tag, attrs, ...children) {
    const el = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs || {})) {
      if (value === null || value === undefined || (value === false && !key.startsWith("aria-"))) continue;
      if (key === "class") el.className = value;
      else if (key === "value") el.value = value;
      else if (key === "checked") el.checked = true;
      else if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
      else el.setAttribute(key, value === true && !key.startsWith("aria-") ? "" : String(value));
    }
    for (const child of children.flat(Infinity)) {
      if (child !== null && child !== undefined && child !== false) el.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return el;
  }

  async function api(path, body) {
    const response = await fetch(path, body === undefined ? {} : {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
    });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || response.statusText);
    return data;
  }

  function toast(message, error = false) {
    const el = byId("studioToast");
    el.textContent = message;
    el.className = error ? "toast error" : "toast";
    el.hidden = false;
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => { el.hidden = true; }, error ? 10000 : 3500);
  }

  async function run(action, message, button) {
    const key = button || action;
    if (pending.has(key)) return null;
    pending.add(key);
    if (button) button.disabled = true;
    try {
      const result = await action();
      if (message) toast(typeof message === "function" ? message(result) : message);
      await refresh();
      return result;
    } catch (error) {
      toast(String(error.message || error), true);
      return null;
    } finally {
      pending.delete(key);
      if (button && button.isConnected) button.disabled = false;
    }
  }

  function readRoute() {
    const raw = location.hash.replace(/^#/, "") || "/overview";
    const [path, query = ""] = raw.split("?");
    const parts = path.split("/").filter(Boolean);
    let stage = [...stages, "canvas"].includes(parts[0]) ? parts[0] : "overview";
    let id = null;
    try { id = parts[1] ? decodeURIComponent(parts[1]) : null; } catch (_) { /* An invalid id selects the stage without a detail. */ }
    const parameters = new URLSearchParams(query);
    const tool = parameters.get("tool");
    // Canvas has its own full-main route so a drawer can overlay it and reload there.
    if (tool === "canvas") { stage = "canvas"; id = null; }
    const mode = ["behavior", "export"].includes(stage) || ["overview", "review"].includes(stage) && parameters.get("mode") === "edit" ? "edit" : "produce";
    return { stage, mode, select: parameters.get("select"), template: parameters.get("template"), pose: parameters.get("pose"), clip: parameters.get("clip"), sheet: parameters.get("sheet"), cell: parameters.get("cell"), id: stage === "behavior" ? (id === "stats" ? "stats" : "graph") : id, tool: tool !== "canvas" && tools.includes(tool) ? tool : null };
  }

  function routeHash(value = route, tool = value.tool) {
    const query = new URLSearchParams();
    if (["overview", "review"].includes(value.stage) && value.mode === "edit") query.set("mode", "edit");
    if (value.select) query.set("select", value.select);
    if (value.stage === "workflows") for (const key of ["template", "pose", "clip", "sheet", "cell"]) if (value[key] != null && value[key] !== "") query.set(key, value[key]);
    if (tool) query.set("tool", tool);
    return "#/" + value.stage + (value.id ? "/" + encodeURIComponent(value.id) : "") + (query.size ? "?" + query : "");
  }

  function setMode(mode) {
    if (!["produce", "edit"].includes(mode) || mode === route.mode) return;
    lastModeRoute[route.mode] = { ...route, tool: null };
    navigate(routeHash(lastModeRoute[mode] || { stage: mode === "edit" ? "behavior" : "overview", id: mode === "edit" ? "graph" : null, mode }, null));
  }

  function setGenerationView(view) {
    if (view === "workflow") {
      if (route.mode === "produce" && route.stage !== "workflows") lastGuidedRoute = { ...route, tool: null };
      navigate("#/workflows");
    } else if (view === "studio" && route.stage === "workflows") navigate(routeHash(lastGuidedRoute || { stage: "overview", mode: "produce" }, null));
  }

  function navigate(hash) {
    if (!String(hash).startsWith("#/")) return;
    if (location.hash === hash) return;
    location.hash = hash;
  }

  function setLanguage(value) {
    if (!['en', 'zh-CN'].includes(value) || value === language) return;
    language = value;
    preference("spriteforge.lang", value);
    render();
  }

  function context(root) {
    return { root, state, jobs, route: { ...route }, mode: route.mode, setMode, t, h, api, refresh, navigate, toast, run };
  }

  function unmount(mount) {
    if (mount && mount.cleanup) mount.cleanup();
  }

  function mount(renderer, root) {
    const result = renderer(context(root));
    return { root, language, cleanup: typeof result === "function" ? result : result && result.cleanup,
      update: result && typeof result.update === "function" ? result.update : null };
  }

  function badge(text, kind = "") { return h("span", { class: "badge " + kind }, text); }
  function runningJobs() { return jobs.filter((job) => job.status === "running"); }
  function blockingIssues() { return (state.issues || []).filter((issue) => issue.blocksExport); }
  function accepted(owner) { return (owner.takes || []).find((take) => take.id === owner.acceptedTake) || null; }
  function version(owner, take) { return take ? take.version || (owner.takes || []).indexOf(take) + 1 : null; }
  function undecided(owner) {
    const takes = owner.takes || [];
    // The host distinguishes undecided candidates from previously adopted versions.
    const clip = owner.kind === "transition" || owner.kind === "loop";
    return takes.filter((take) => take.needsReview && (clip || (take.qa && take.qa.status !== "fail")));
  }
  function stillUrl(pose) {
    const take = accepted(pose) || (pose.takes || []).filter((candidate) => candidate.media && candidate.media.still).at(-1);
    return take && take.media && take.media.still ? "/api/production/media?path=" + encodeURIComponent(`production/poses/${pose.id}/takes/${take.id}/${take.media.still}`) : null;
  }

  function icon(name) {
    const paths = {
      overview: '<path d="M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z"/>',
      expressions: '<circle cx="12" cy="12" r="8"/><path d="M9 10h.01M15 10h.01M9 15c1.5 1.3 4.5 1.3 6 0"/>',
      clips: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M7 5v14M17 5v14M3 9h4M17 9h4M3 15h4M17 15h4"/>',
      workflows: '<rect x="3" y="9" width="6" height="6" rx="1"/><rect x="15" y="3" width="6" height="6" rx="1"/><rect x="15" y="15" width="6" height="6" rx="1"/><path d="M9 12h3V6h3M12 12v6h3"/>',
      review: '<circle cx="12" cy="12" r="8"/><path d="M8.5 12.5l2.3 2.3 4.7-5"/>',
      behavior: '<circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="6" r="2.5"/><circle cx="18" cy="18" r="2.5"/><path d="M8.3 11l7.4-3.8M8.3 13l7.4 3.8"/>',
      export: '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9zM4 7.5l8 4.5 8-4.5M12 12v9"/>',
      canvas: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M8 3v18M3 8h18"/>',
      prompts: '<path d="M5 6h14M5 10h14M5 14h9M5 18h6"/>',
      jobs: '<circle cx="12" cy="12" r="8"/><path d="M12 8v4l3 2"/>',
      settings: '<path d="M5 7h9M18 7h1M5 17h3M12 17h7"/><circle cx="16" cy="7" r="2"/><circle cx="10" cy="17" r="2"/>'
    };
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    for (const [key, value] of Object.entries({ width: 16, height: 16, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": 2, "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true" })) svg.setAttribute(key, value);
    svg.innerHTML = paths[name];
    return svg;
  }

  function languageButtons() {
    return h("div", { class: "tabs", role: "group", "aria-label": t("shell.language") }, ['en', 'zh-CN'].map((lang) => h("button", {
      type: "button", class: language === lang ? "active" : "", "data-lang": lang,
      "aria-pressed": String(language === lang), onclick: () => setLanguage(lang)
    }, t("shell.language." + lang))));
  }

  function renderChrome() {
    const stageLabel = stage => t(stage === "review" && route.mode === "edit" ? "stage.connections" : "stage." + stage);
    const focused = document.activeElement;
    const focusData = focused instanceof HTMLElement && (byId("studioSidebar").contains(focused) || byId("studioTopbar").contains(focused))
      ? ["stage", "tool", "lang", "mode", "generationView"].map((key) => focused.dataset[key] ? [key, focused.dataset[key]] : null).find(Boolean) : null;
    document.documentElement.lang = language;
    document.title = t("shell.title");
    document.querySelector(".skip-link").textContent = t("shell.skip");
    const sidebar = byId("studioSidebar");
    sidebar.setAttribute("aria-label", t("shell.studio"));
    sidebar.replaceChildren(h("div", { class: "studio-brand" }, h("strong", {}, "SpriteForge"), h("span", { class: "tiny" }, t("shell.production"))));
    const ready = state && state.initialized;
    if (ready) {
      const character = state.character;
      const base = state.poses.find((pose) => pose.id === character.basePose);
      const src = base && stillUrl(base);
      sidebar.append(h("a", { class: "item character-card", href: routeHash({ stage: "overview", mode: route.mode }, null) }, src ? h("img", { class: "thumb checker", src, alt: "" }) : h("span", { class: "character-placeholder", "aria-hidden": "true" }),
        h("span", { class: "character-meta" }, h("strong", {}, character.displayName), h("span", { class: "tiny mono" }, `${character.canvas.width} × ${character.canvas.height}`))));
      sidebar.append(h("div", { class: "tabs mode-switch", role: "group", "aria-label": t("shell.mode") }, ["produce", "edit"].map(mode => h("button", {
        type: "button", "data-mode": mode, class: route.mode === mode ? "active" : "", "aria-pressed": String(route.mode === mode), onclick: () => setMode(mode)
      }, t("shell.mode." + mode)))));
      sidebar.append(h("div", { class: "tiny rail-label" }, t("shell.mode." + route.mode)));
      const expressionCount = state.poses.filter((pose) => undecided(pose).length).length;
      for (const stage of route.stage === "workflows" ? ["workflows"] : modeStages[route.mode]) {
        const current = route.stage === stage;
        const count = stage === "expressions" ? expressionCount : stage === "review" ? (state.issues || []).filter(issue => issue.level === "fail"
          && (route.mode === "edit" ? ["node", "edge"] : ["pose", "clip"]).includes(issue.kind)).length : 0;
        sidebar.append(h("a", { class: "rail" + (current ? " on" : ""), href: routeHash({ stage, mode: route.mode, id: stage === "behavior" ? "graph" : null }, null), "data-stage": stage, "aria-current": current ? "page" : null },
          icon(stage), stageLabel(stage), count ? badge(String(count), stage === "review" ? "fail" : "info") : null));
      }
      sidebar.append(h("div", { class: "spacer" }));
      for (const tool of route.mode === "produce" ? tools : ["jobs", "settings"]) {
        const current = tool === "canvas" ? route.stage === "canvas" : route.tool === tool;
        sidebar.append(h("a", { class: "rail" + (current ? " on" : ""), href: tool === "canvas" ? "#/canvas" : routeHash(route, tool), "data-tool": tool,
          "aria-expanded": tool === "canvas" ? null : String(current), "aria-current": tool === "canvas" && current ? "page" : null,
          onclick: () => { drawerOpener = tool; } }, icon(tool), t("tool." + tool), tool === "jobs" && runningJobs().length ? badge(String(runningJobs().length), "info") : null));
      }
    } else sidebar.append(h("div", { class: "spacer" }));
    const topbar = byId("studioTopbar");
    const crumb = h("div", { class: "breadcrumb" }, ready ? h("span", { class: "tiny" }, state.character.displayName) : null,
      ready ? h("span", { class: "tiny", "aria-hidden": "true" }, "/") : null,
      h("strong", {}, ready ? (route.stage === "canvas" ? t("tool.canvas") : stageLabel(route.stage)) : t("shell.studio")));
    topbar.replaceChildren(crumb, h("div", { class: "spacer" }));
    if (ready) {
      if (route.mode === "produce") {
        topbar.append(h("div", { class: "tabs", role: "group", "aria-label": t("shell.generationView") }, ["studio", "workflow"].map(view => h("button", {
          type: "button", "data-generation-view": view, class: (route.stage === "workflows") === (view === "workflow") ? "active" : "",
          "aria-pressed": String((route.stage === "workflows") === (view === "workflow")), onclick: () => setGenerationView(view)
        }, t("shell.generationView." + view)))));
        for (const service of activeServices()) topbar.append(badge(service));
      }
      if (runningJobs().length) topbar.append(h("a", { class: "cell-link", href: routeHash(route, "jobs") }, badge(t("shell.jobsRunning", { count: runningJobs().length }), "info")));
    }
    topbar.append(languageButtons());
    if (focusData) document.querySelector(`[data-${focusData[0].replace(/[A-Z]/g, letter => "-" + letter.toLowerCase())}="${focusData[1]}"]`)?.focus({ preventScroll: true });
  }

  function activeServices() {
    const providers = new Set();
    for (const owner of [...state.poses, ...state.clips]) for (const take of owner.takes || []) if (take.source && take.source.provider) providers.add(take.source.provider);
    for (const job of runningJobs()) if (job.provider) providers.add(job.provider);
    const result = [];
    const usage = state.usage || {};
    if (providers.has("wan") || providers.has("wan-cli")) result.push(usage.wan && usage.wan.balance != null ? t("shell.wanCredits", { balance: usage.wan.balance }) : "Wan");
    if (providers.has("gpt-image")) result.push(t("shell.codexPlan"));
    for (const provider of providers) if (!["wan", "wan-cli", "gpt-image", "import", "adopted"].includes(provider)) {
      const config = ((state.tools || {}).providers || {})[provider];
      if (config) result.push(config.model ? t("shell.provider", { provider, model: config.model }) : provider);
    }
    return result;
  }

  function render() {
    if (!started) return;
    renderChrome();
    const main = byId("studioMain");
    main.className = route.stage === "canvas" && state && state.initialized ? "canvas-main" : "";
    main.setAttribute("aria-busy", String(!state && !errorMessage));
    if (!state || !state.initialized || errorMessage) {
      unmount(mainMount); unmount(drawerMount);
      mainMount = drawerMount = null; mainKey = drawerTool = null;
      main.replaceChildren(); byId("studioDrawer").hidden = true;
    }
    if (errorMessage) {
      main.append(h("section", { class: "card empty-state" }, h("h1", {}, t("shell.loadFailed")), h("p", {}, errorMessage), h("button", { type: "button", onclick: () => refresh().catch(showLoadError) }, t("shell.retry"))));
      return;
    }
    if (!state) { main.append(h("p", { role: "status", class: "tiny" }, t("shell.loading"))); return; }
    if (!state.initialized) { renderEmpty(main); return; }
    const nextKey = route.mode + "/" + route.stage + "/" + (route.id || "");
    const changedLanguage = mainMount && mainMount.language !== language;
    if (mainMount && mainKey === nextKey && (!changedLanguage || mainMount.update)) {
      if (mainMount.update) mainMount.update(context(main));
      mainMount.language = language;
    } else {
      unmount(mainMount); mainMount = null; main.replaceChildren();
      const renderer = route.stage === "canvas" ? toolRenderers.get("canvas") : renderers.get(route.stage);
      if (renderer) mainMount = mount(renderer, main);
      else if (route.stage === "overview") { renderOverview(context(main)); mainMount = { root: main, language, update: renderOverview }; }
      else { renderPending(main); mainMount = { root: main, language, update: (ctx) => { ctx.root.replaceChildren(); renderPending(ctx.root); } }; }
      mainKey = nextKey;
    }
    if (route.tool && route.tool !== "canvas") {
      const changedDrawerLanguage = drawerMount && drawerMount.language !== language;
      if (drawerMount && drawerTool === route.tool && (!changedDrawerLanguage || drawerMount.update)) {
        if (drawerMount.update) drawerMount.update(context(drawerMount.root));
        drawerMount.language = language;
        byId("studioDrawer").setAttribute("aria-label", t("tool." + route.tool));
        byId("studioDrawer").querySelector(".drawer-head h2").textContent = t("tool." + route.tool);
        byId("studioDrawer").querySelector(".drawer-close").setAttribute("aria-label", t("shell.closeTool", { tool: t("tool." + route.tool) }));
        byId("studioDrawer").querySelector(".drawer-resizer").setAttribute("aria-label", t("shell.resizeTool"));
      } else { unmount(drawerMount); drawerMount = null; renderDrawer(); }
      drawerTool = route.tool;
    } else { unmount(drawerMount); drawerMount = null; drawerTool = null; byId("studioDrawer").hidden = true; }
  }

  function renderEmpty(root) {
    const command = h("pre", {}, h("code", {}, initCommand));
    root.append(h("section", { class: "card empty-state" }, h("h1", {}, t("empty.title")), h("p", {}, t("empty.description")), command,
      h("div", { class: "row" }, h("button", { type: "button", onclick: async () => {
        try { await navigator.clipboard.writeText(initCommand); toast(t("empty.copied")); }
        catch (_) { const range = document.createRange(); range.selectNodeContents(command); const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range); toast(t("empty.copyFailed"), true); }
      } }, t("empty.copy")), h("a", { class: "btn", href: docs, target: "_blank", rel: "noopener" }, t("empty.docs")))));
  }

  function renderPending(root) {
    const suffix = route.stage[0].toUpperCase() + route.stage.slice(1);
    const legacy = ["expressions", "clips"].includes(route.stage) ? "/production#" + (route.stage === "expressions" ? "stills" : "clips")
      : ["review", "behavior"].includes(route.stage) ? "/" : route.stage === "export" ? docs : null;
    root.append(h("section", { class: "card pending-stage" }, h("h1", {}, t("stage." + route.stage)), h("p", {}, t("stage.pending" + suffix)),
      route.id ? h("p", { class: "mono tiny" }, route.id) : null,
      legacy ? h("a", { class: "btn", href: legacy }, t(legacy === docs ? "empty.docs" : legacy.startsWith("/production") ? "stage.openProduction" : "stage.openReview")) : null));
  }

  function renderDrawer() {
    const drawer = byId("studioDrawer");
    const tool = route.tool;
    drawer.hidden = false;
    drawer.setAttribute("aria-label", t("tool." + tool));
    const close = h("button", { type: "button", class: "drawer-close", "aria-label": t("shell.closeTool", { tool: t("tool." + tool) }), onclick: closeDrawer }, "×");
    const resizer = h("div", { class: "drawer-resizer", role: "separator", tabindex: "0", "aria-orientation": "vertical", "aria-label": t("shell.resizeTool"),
      "aria-valuemin": "360", "aria-valuemax": String(drawerMax()), "aria-valuenow": String(drawerWidth()), onkeydown: (event) => {
        if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
        event.preventDefault(); resizeDrawer(drawerWidth() + (event.key === "ArrowLeft" ? 20 : -20), resizer);
      }, onpointerdown: (event) => {
        if (event.button !== 0) return;
        event.preventDefault(); resizer.setPointerCapture(event.pointerId);
        const move = (moveEvent) => resizeDrawer(byId("studioTopbar").getBoundingClientRect().right - moveEvent.clientX, resizer);
        const done = () => { resizer.removeEventListener("pointermove", move); resizer.removeEventListener("pointerup", done); resizer.removeEventListener("pointercancel", done); };
        resizer.addEventListener("pointermove", move); resizer.addEventListener("pointerup", done); resizer.addEventListener("pointercancel", done);
      } });
    const root = h("div", { id: "studioDrawerBody" });
    drawer.replaceChildren(resizer, h("div", { class: "drawer-head" }, h("h2", {}, t("tool." + tool)), close), root);
    const renderer = toolRenderers.get(tool);
    if (renderer) drawerMount = mount(renderer, root);
    else root.append(h("p", { class: "tiny" }, t("shell.toolUnavailable")));
  }

  function drawerMax() { return Math.max(360, byId("studioTopbar").clientWidth - 280); }
  function drawerWidth() { return byId("studioDrawer").getBoundingClientRect().width || 480; }
  function resizeDrawer(width, resizer) {
    const next = Math.round(Math.min(drawerMax(), Math.max(360, width)));
    document.documentElement.style.setProperty("--drawer-width", next + "px");
    preference("spriteforge.drawerWidth", next);
    resizer.setAttribute("aria-valuenow", String(next));
  }
  function closeDrawer() { navigate(routeHash(route, null)); }

  function stillStatus(pose) {
    if (pose.needsRecheck) return { label: t("status.recheck"), level: "watch" };
    const job = runningJobs().find((candidate) => candidate.kind === "pose" && candidate.owner === pose.id);
    if (job) return { label: t(job.action === "concept-reroll" ? "status.conceptReroll" : "status.generating"), level: "info" };
    const decision = undecided(pose).at(-1);
    if (decision) return { label: t("status.approveStill", { version: version(pose, decision) }), level: "watch" };
    const take = accepted(pose);
    if (take) return { label: t("status.approved", { version: version(pose, take) }), level: "pass" };
    return { label: t("status.notStarted"), level: "" };
  }

  const weight = { fail: 5, fix: 4, watch: 3, info: 2, pass: 1 };
  function clipGroup(pose, type) {
    return state.clips.filter((clip) => type === "enter" ? clip.kind === "transition" && clip.to === pose.id
      : type === "exit" ? clip.kind === "transition" && clip.from === pose.id
      : clip.kind === "loop" && clip.from === pose.id && clip.to === pose.id && (type === "speaking" ? !!clip.mouth : !clip.mouth));
  }

  function groupStatus(pose, type) {
    if (pose.id === state.character.basePose && ["enter", "exit"].includes(type)) return { label: "—", level: "", disabled: true };
    const clips = clipGroup(pose, type);
    const affects = (issue, clip) => issue.clip === clip.id || (issue.clips || []).includes(clip.id);
    const issue = (state.issues || []).filter((entry) => clips.some((clip) => affects(entry, clip))).sort((a,b) => (weight[b.level] || 0) - (weight[a.level] || 0))[0];
    const target = issue ? clips.find((clip) => affects(issue, clip)) : clips.find((clip) => undecided(clip).length || !clip.acceptedTake) || clips[0];
    const href = target ? "#/clips/" + encodeURIComponent(target.id) : "#/expressions/" + encodeURIComponent(pose.id);
    if (issue) return { label: issueLabel(issue), level: issue.level, href };
    if (!clips.length) return { label: t("status.notStarted"), level: "", href };
    if (runningJobs().some((job) => job.kind === "clip" && clips.some((clip) => clip.id === job.owner))) return { label: t("status.generating"), level: "info", href };
    const approved = clips.filter((clip) => clip.acceptedTake).length;
    const ready = clips.filter((clip) => undecided(clip).length).length;
    if (clips.length > 1) return { label: ready ? t("status.variantsReview", { count: clips.length, pending: ready }) : approved ? t("status.variantsAccepted", { count: approved }) : t("status.variants", { count: clips.length }), level: ready ? "watch" : approved === clips.length ? "pass" : "", href };
    const clip = clips[0];
    const current = accepted(clip);
    const next = undecided(clip).at(-1);
    return { label: next ? t(current ? "status.acceptedReview" : "status.reviewVersion", { accepted: version(clip, current), pending: version(clip, next), version: version(clip, next) }) : current ? t("status.accepted", { version: version(clip, current) }) : t("status.notStarted"), level: next ? "watch" : current ? "pass" : "", href };
  }

  function issueLabel(issue) {
    const reason = issue.key.split(":").at(-1);
    if (issue.kind === "edge") return t("issue.edge", { from: issue.from, to: issue.to, top: issue.dHeadTop ?? "—", center: issue.dHeadCenter ?? "—" });
    if (issue.kind === "node" && ["phase", "frameIntervalMs", "loopMode"].includes(reason)) return t("issue.node.setting", { node: issue.node, field: reason });
    const key = "issue." + issue.kind + "." + reason;
    return (window.SF_I18N.en || {})[key] ? t(key, issue) : t("issue.generic", { owner: issue.clip || issue.pose || issue.node || issue.key, check: reason });
  }

  function cell(pose, column, status) {
    const label = status.level ? badge(status.label, status.level) : h("span", { class: "tiny" }, status.label);
    return h("td", {}, status.disabled ? label : h("a", { class: "cell-link", href: status.href || "#/expressions/" + encodeURIComponent(pose.id),
      "aria-label": t("overview.openCell", { pose: pose.id, column: t("overview." + column), status: status.label }) }, label));
  }

  function renderOverview(ctx) {
    if (ctx.mode === "edit") { renderAssetOverview(ctx); return; }
    const root = ctx.root;
    const focused = document.activeElement;
    const focusHref = focused instanceof HTMLAnchorElement && root.contains(focused) ? focused.getAttribute("href") : null;
    const focusLabel = focusHref ? focused.getAttribute("aria-label") : null;
    const poses = state.poses;
    const columns = ["pose", "still", "enter", "loop", "speaking", "exit"];
    const table = h("table", { class: "progress-table", "aria-label": t("overview.progress") },
      h("thead", {}, h("tr", {}, columns.map((column) => h("th", { scope: "col" }, t("overview." + column))))),
      h("tbody", {}, poses.map((pose) => {
        const src = stillUrl(pose);
        return h("tr", { "data-pose": pose.id }, h("th", { scope: "row" }, h("a", { class: "pose-link", href: "#/expressions/" + encodeURIComponent(pose.id) },
          src ? h("img", { class: "thumb checker", src, alt: "", loading: "lazy" }) : h("span", { class: "pose-placeholder", "aria-hidden": "true" }),
          h("span", { class: "pose-label" }, h("strong", {}, pose.id), h("span", { class: "tiny" }, pose.id === state.character.basePose ? t("overview.basePose") : pose.description || "")))),
          cell(pose, "still", stillStatus(pose)), ["enter", "loop", "speaking", "exit"].map((column) => cell(pose, column, groupStatus(pose, column))));
      })));
    const next = nextSteps();
    root.replaceChildren(h("div", { class: "overview" },
      h("div", { class: "overview-heading" }, h("h1", {}, state.character.displayName),
        badge(t("overview.posesApproved", { approved: poses.filter((pose) => pose.acceptedTake).length, total: poses.length }), "pass"),
        badge(t("overview.clipsAccepted", { accepted: state.clips.filter((clip) => clip.acceptedTake).length, total: state.clips.length }), "pass"),
        blockingIssues().length ? badge(t("overview.blocking", { count: blockingIssues().length }), "fail") : null,
        h("div", { class: "spacer" }), h("a", { class: "btn", href: "#/expressions" }, t("overview.newExpression")), h("a", { class: "btn primary", href: "#/export" }, t("overview.exportCheck"))),
      h("div", { class: "overview-grid" }, h("section", { class: "card progress-card" }, poses.length ? table : h("p", { class: "tiny", style: "padding:14px" }, t("overview.noPoses"))),
        h("aside", { class: "overview-aside" }, h("section", { class: "card" }, h("div", { class: "card-heading" }, h("h2", { class: "h3" }, t("overview.nextSteps")), h("span", { class: "tiny" }, t("overview.byImpact"))),
          next.length ? next.map((step) => h("div", { class: "item next-step" }, h("div", { class: "row" }, badge(step.badge, step.level), h("span", { class: "next-title" }, step.title)),
            h("div", { class: "step-footer" }, step.hint ? h("span", { class: "tiny" }, step.hint) : h("span"), h("a", { class: "btn small", href: step.href }, step.button)))) : h("p", { class: "tiny" }, t("overview.noNextSteps"))),
          renderUsage()))));
    if (focusHref) [...root.querySelectorAll("a")].find((link) => link.getAttribute("href") === focusHref && link.getAttribute("aria-label") === focusLabel)?.focus({ preventScroll: true });
  }

  function renderAssetOverview(ctx) {
    const poses = state.poses.filter(pose => accepted(pose)?.qa && !pose.needsRecheck && accepted(pose).qa.status !== "fail");
    const clips = state.clips.filter(clip => accepted(clip) && clip.render?.state === "current" && clip.render.qa && clip.render.qa.status !== "fail");
    ctx.root.replaceChildren(h("div", { class: "page-head" }, h("h1", {}, t("assets.title")), h("div", { class: "spacer" }),
      h("a", { class: "btn primary", href: "#/behavior/graph" }, t("assets.graph"))),
    h("p", { class: "tiny" }, t("assets.hint")),
    h("h2", { class: "h3" }, t("assets.stills", { count: poses.length })),
    h("div", { class: "asset-grid" }, poses.map(pose => h("article", { class: "item", "data-library-pose": pose.id },
      h("img", { class: "checker", src: stillUrl(pose), alt: pose.id, loading: "lazy" }), h("strong", {}, pose.id),
      badge(t("status.approved", { version: version(pose, accepted(pose)) }), "pass"), h("a", { class: "btn small", href: "#/expressions/" + encodeURIComponent(pose.id) }, t("assets.returnQA"))))),
    h("h2", { class: "h3" }, t("assets.clips", { count: clips.length })),
    h("div", { class: "asset-grid" }, clips.map(clip => h("article", { class: "item", "data-library-clip": clip.id },
      h("strong", {}, clip.id), h("span", { class: "tiny" }, `${clip.from} → ${clip.to}`),
      badge("QA " + clip.render.qa.status, clip.render.qa.status),
      h("span", { class: "tiny mono" }, `${clip.render.frameCount} × ${clip.render.frameIntervalMs} ms`),
      h("a", { class: "btn small", href: "#/behavior/graph" }, t("assets.graph")),
      h("a", { class: "btn small", href: "#/clips/" + encodeURIComponent(clip.id) }, t("assets.returnQA"))))),
    !poses.length && !clips.length ? h("p", {}, t("assets.empty")) : null);
  }

  function nextSteps() {
    const issueStep = (issue) => ({ level: issue.level, badge: t(issue.blocksExport ? "status.blocksExport" : "status." + issue.level), title: issueLabel(issue), href: "#/review/" + encodeURIComponent(issue.key) + (["node", "edge"].includes(issue.kind) ? "?mode=edit" : ""), button: t("next.review") });
    const steps = blockingIssues().map(issueStep);
    for (const job of runningJobs()) steps.push({ level: "info", badge: t("status.running"), title: t("next.job", { owner: job.owner || "", action: t("job." + ((window.SF_I18N.en || {})["job." + job.action] ? job.action : "process")) }), href: routeHash(route, "jobs"), button: t("next.viewJobs") });
    for (const clip of state.clips) {
      const take = undecided(clip).at(-1);
      if (take) steps.push({ level: "watch", badge: t("status.toReview"), title: t("next.clip", { clip: clip.id, version: version(clip, take) }), hint: t("next.clipHint"), href: "#/clips/" + encodeURIComponent(clip.id), button: t("next.review") });
    }
    for (const pose of state.poses) {
      const take = undecided(pose).at(-1);
      if (take) steps.push({ level: "watch", badge: t("status.toApprove"), title: t("next.still", { pose: pose.id, version: version(pose, take) }), hint: t("next.stillHint"), href: "#/expressions/" + encodeURIComponent(pose.id), button: t("next.open") });
    }
    steps.push(...(state.issues || []).filter((issue) => !issue.blocksExport && ["fail", "fix"].includes(issue.level)).map(issueStep));
    return steps.slice(0,5);
  }

  function renderUsage() {
    const usage = state.usage || {};
    const wan = usage.wan || {};
    const known = (value) => typeof value === "number" && Number.isFinite(value);
    const amount = known(wan.usedCredits) && known(wan.balance) ? t("overview.wanUsage", { used: wan.usedCredits, balance: wan.balance })
      : known(wan.usedCredits) ? t("overview.wanUsed", { used: wan.usedCredits }) : known(wan.balance) ? t("overview.wanBalance", { balance: wan.balance }) : t("overview.unknownUsage");
    const seconds = (usage.local || {}).durationS;
    const duration = !known(seconds) ? t("overview.unknownUsage") : seconds >= 3600 ? t("overview.durationHours", { hours: (seconds / 3600).toFixed(1) }) : seconds >= 60 ? t("overview.durationMinutes", { minutes: (seconds / 60).toFixed(1) }) : t("overview.durationSeconds", { seconds: Math.round(seconds) });
    const images = (usage.gptImage || {}).images;
    return h("section", { class: "card" }, h("div", { class: "card-heading" }, h("h2", { class: "h3" }, t("overview.thisWeek")), h("span", { class: "tiny" }, t("overview.servicesInUse"))),
      h("dl", { class: "usage-grid" }, h("dt", {}, t("overview.wan")), h("dd", { class: "mono", title: !known(wan.usedCredits) ? t("overview.unknownUsageHint") : null }, amount),
        h("dt", {}, t("overview.gptImage")), h("dd", { class: "mono" }, known(images) ? t("overview.imageCount", { count: images }) : t("overview.unknownUsage")),
        h("dt", {}, t("overview.local")), h("dd", { class: "mono", title: !known(seconds) ? t("overview.unknownUsageHint") : null }, duration)));
  }

  function updateMounted() {
    renderChrome();
    if (mainMount && mainMount.update) mainMount.update(context(mainMount.root));
    if (drawerMount && drawerMount.update) drawerMount.update(context(drawerMount.root));
  }

  function refresh(options = {}) {
    // Serialize reads so a refresh requested after a mutation observes that mutation.
    const task = refreshQueue.catch(() => {}).then(async () => {
      const [overview, jobData] = await Promise.all([api("/api/production"), api("/api/production/jobs")]);
      state = overview; jobs = jobData.jobs; errorMessage = null;
      if (options.preserveModules && state.initialized) updateMounted(); else render();
      schedulePoll();
      return state;
    });
    refreshQueue = task;
    return task;
  }

  function schedulePoll() {
    clearTimeout(pollTimer);
    if (runningJobs().length) pollTimer = setTimeout(poll, 1500);
  }

  async function poll() {
    try {
      const previous = new Map(jobs.map((job) => [job.id, job.status]));
      jobs = (await api("/api/production/jobs")).jobs;
      const finished = jobs.some((job) => previous.get(job.id) === "running" && job.status !== "running");
      if (finished) await refresh({ preserveModules: true });
      else { updateMounted(); schedulePoll(); }
    } catch (error) { toast(String(error.message || error), true); }
  }

  function showLoadError(error) { errorMessage = String(error.message || error); render(); }
  window.SFStudio = {
    register(stage, renderer) { renderers.set(stage, renderer); if (started && route.stage === stage) { mainKey = null; render(); } },
    registerTool(tool, renderer) {
      toolRenderers.set(tool, renderer);
      if (started && (route.tool === tool || (tool === "canvas" && route.stage === "canvas"))) {
        if (tool === "canvas") mainKey = null; else drawerTool = null;
        render();
      }
    },
    addTranslations(lang, entries) { window.SF_I18N[lang] = Object.assign(window.SF_I18N[lang] || {}, entries); },
    setLanguage, setMode, setGenerationView, t, h, api, refresh, navigate, toast, run,
    get mode() { return route.mode; },
    get language() { return language; },
    get state() { return state; },
    get jobs() { return jobs; },
    get route() { return { ...route }; }
  };
  document.addEventListener("DOMContentLoaded", () => {
    started = true;
    const width = Number(preference("spriteforge.drawerWidth"));
    if (Number.isFinite(width) && width >= 360) document.documentElement.style.setProperty("--drawer-width", Math.min(width, drawerMax()) + "px");
    if (!location.hash) history.replaceState(null, "", "#/overview");
    else if (route.stage === "canvas" && route.tool === null && location.hash.includes("tool=canvas")) history.replaceState(null, "", "#/canvas");
    render();
    refresh().catch(showLoadError);
  });
  window.addEventListener("hashchange", () => {
    const oldTool = route.tool;
    route = readRoute();
    if (route.stage === "canvas" && route.tool === null && location.hash.includes("tool=canvas")) history.replaceState(null, "", "#/canvas");
    render();
    if (route.tool && route.tool !== "canvas" && route.tool !== oldTool) byId("studioDrawer").querySelector(".drawer-close")?.focus();
    else if (oldTool && !route.tool && drawerOpener) byId("studioSidebar").querySelector(`[data-tool="${drawerOpener}"]`)?.focus();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && route.tool && route.tool !== "canvas") { event.preventDefault(); closeDrawer(); }
  });
})();
