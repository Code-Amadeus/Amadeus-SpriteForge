"use strict";
(() => {
  const translations = {
    en: {
      "clips.processTake": "Process & QA · free", "clips.processingTake": "Candidate processing started · published material stays unchanged",
      "clips.processFirst": "Process and check this candidate before adopting it.", "clips.blockedQA": "This candidate has blocking QA findings.",
      "clips.showSource": "Show source", "clips.showProcessed": "View processed candidate",
      "clips.title": "Clip studio", "clips.none": "No clips have been created yet.", "clips.missing": "This clip does not exist.",
      "clips.choose": "Choose clip", "clips.newClip": "New clip", "clips.newVariant": "New variant", "clips.variants": "{from} → {to} · variants",
      "clips.variantHint": "Variants are named sibling clips. Each has its own versions.", "clips.variantId": "New variant id", "clips.idHint": "1–64 lowercase letters, digits, _ or -; the id must be unused.",
      "clips.variantCreated": "Variant {id} created", "clips.clipId": "Clip id", "clips.from": "Start pose", "clips.to": "End pose", "clips.phase": "Phase", "clips.clipCreated": "Clip {id} created",
      "clips.kind.transition": "transition", "clips.kind.loop": "loop", "clips.kind.speaking": "speaking loop", "clips.versions": "Versions", "clips.filter": "Filter versions",
      "clips.filter.all": "All", "clips.filter.review": "To review", "clips.filter.rejected": "Rejected", "clips.noVersions": "No versions match this filter.",
      "clips.versionStatus.accepted": "accepted", "clips.versionStatus.rejected": "rejected", "clips.versionStatus.failed": "failed", "clips.versionStatus.submitted": "submitted",
      "clips.versionStatus.generating": "generating", "clips.versionStatus.review": "to review", "clips.versionStatus.pending": "pending", "clips.reason": "Reason: {reason}",
      "clips.error": "Error: {error}", "clips.basedOn": "Based on v{version}: {note}", "clips.promptVersion": "prompt v{version}", "clips.credits": "{credits} credits",
      "clips.pinB": "Pin v{version} as B", "clips.unpinB": "Use the accepted version as B", "clips.selectVersion": "Select v{version} as A", "clips.details": "Details",
      "clips.tab.prompt": "Prompt", "clips.tab.generation": "Generation", "clips.tab.processing": "Processing", "clips.tab.playback": "Playback", "clips.tab.mouth": "Mouth", "clips.tab.qa": "QA",
      "clips.sentPrompt": "Prompt sent with v{version}", "clips.noSnapshot": "This version has no prompt snapshot.", "clips.currentPrompt": "Current prompt preview", "clips.negative": "Negative prompt",
      "clips.negativeNotSent": "This provider did not receive the negative prompt.", "clips.diffAgainst": "Word changes against B · v{version}", "clips.subject": "Current subject block · {block}",
      "clips.savePrompt": "Save as new prompt version", "clips.promptSaved": "Prompt saved as a new version", "clips.copyPrompt": "Copy prompt", "clips.copied": "Prompt copied", "clips.copyFailed": "Select the prompt and copy it manually.",
      "clips.note": "Version note", "clips.saveNote": "Save note", "clips.noteSaved": "Version note saved", "clips.accept": "Accept v{version}", "clips.accepted": "Accepted v{version}",
      "clips.reject": "Reject with a reason…", "clips.rejectTitle": "Reject v{version}", "clips.rejectReason": "Reason (required)", "clips.rejectHint": "The version stays in the archive with this reason.",
      "clips.rejected": "Version rejected and archived", "clips.restore": "Restore v{version}", "clips.restored": "Version restored", "clips.cancel": "Cancel", "clips.confirm": "Confirm", "clips.create": "Create",
      "clips.generate": "Generate version · {cost}", "clips.generateFrom": "Generate from v{version} · {cost}", "clips.generateTitle": "Generate a new version", "clips.generateFromTitle": "Generate from v{version}",
      "clips.generateSubject": "Subject prompt", "clips.generateNote": "Note (optional)", "clips.generateSettings": "Current settings: {provider} · {duration} s · {resolution}", "clips.generateHistorical": "This subject is the text recorded for v{version}. Current generation settings will be used.",
      "clips.submit": "Generate once · {cost}", "clips.started": "Generation started", "clips.cost.credits": "credits", "clips.cost.quota": "plan quota", "clips.cost.usage": "pay-as-you-go", "clips.cost.paid": "paid generation", "clips.cost.free": "free",
      "clips.costEstimate": "~{credits} credits", "clips.costManual": "manual", "clips.manualHint": "Prepare inputs and import a version made in your generator.", "clips.notReady": "Configure the provider in Settings before generating.",
      "clips.stillsRequired": "Approve the input stills before generating or importing a version.", "clips.promptIncomplete": "Complete the prompt placeholders before paid generation.", "clips.historicalMissing": "The historical subject block is unavailable. Open Prompt to inspect this version.",
      "clips.import": "Import video", "clips.importTitle": "Import a version", "clips.importVideo": "Video file", "clips.importFolder": "PNG frame folder", "clips.folder": "Workspace-relative folder", "clips.fps": "Frame folder FPS (required for folders)", "clips.importSubmit": "Import · free", "clips.importChoice": "Choose either a video file or a workspace frame folder.",
      "clips.importHint": "Imports preserve a new version; its provider inputs are recorded as assumed.", "clips.imported": "Version imported", "clips.prepare": "Prepare inputs", "clips.prepareTitle": "Generator inputs", "clips.downloadPrompt": "Download prompt.txt", "clips.downloadNegative": "Download negative.txt",
      "clips.prepareHint": "These are the current approved stills and prompt prepared for your external generator.", "clips.resume": "Resume download", "clips.resuming": "Download resumed", "clips.adopt": "Last frame → {pose} still", "clips.adoptTitle": "Adopt a clip frame as a still", "clips.frame": "Frame (last or a zero-based index)",
      "clips.adoptHint": "The frame becomes a candidate still for {pose}. It still needs QA and approval.", "clips.adopting": "Still adoption started", "clips.render": "Render", "clips.renderCheck": "Render and check", "clips.rendering": "Render started · free", "clips.renderState": "render {state}",
      "clips.qaState": "QA {state}", "clips.acceptedSummary": "v{version} accepted", "clips.noAccepted": "no version accepted", "clips.sync": "Sync graph timing", "clips.syncTitle": "Sync graph timing", "clips.syncAdd": "Also add nodes for rendered clips missing from the graph", "clips.syncHint": "Existing edges stay unchanged. Timing and render paths are synchronized.", "clips.synced": "Graph timing synchronized",
      "clips.shortcuts.versions": "switch version", "clips.shortcuts.accept": "accept", "clips.shortcuts.reject": "reject", "clips.shortcuts.compare": "compare", "clips.shortcuts.play": "play", "clips.shortcuts.loop": "loop", "clips.firstStill": "Start still: {pose}", "clips.lastStill": "End still: {pose}", "clips.lastNotSent": "last frame not sent", "clips.noStill": "not approved", "clips.free": "free",
      "clips.progress": "{percent}%", "clips.jobRunning": "A job is running for this clip.", "clips.settingsHint": "Save edited settings before generating; generation uses the current server settings."
    },
    "zh-CN": {
      "clips.processTake": "处理与 QA · 免费", "clips.processingTake": "候选处理已开始，已发布素材保持不变",
      "clips.processFirst": "先处理并检查此候选，再采纳为可用素材。", "clips.blockedQA": "此候选存在阻塞性的 QA 问题。",
      "clips.showSource": "查看原始素材", "clips.showProcessed": "查看处理后候选",
      "clips.title": "片段工作室", "clips.none": "尚未创建片段。", "clips.missing": "此片段不存在。", "clips.choose": "选择片段", "clips.newClip": "新建片段", "clips.newVariant": "新建变体", "clips.variants": "{from} → {to} · 变体", "clips.variantHint": "变体是按名字区分的兄弟片段，各有自己的版本。", "clips.variantId": "新变体 id", "clips.idHint": "1–64 个小写字母、数字、_ 或 -；id 必须尚未使用。", "clips.variantCreated": "已创建变体 {id}", "clips.clipId": "片段 id", "clips.from": "起始姿态", "clips.to": "结束姿态", "clips.phase": "阶段", "clips.clipCreated": "已创建片段 {id}",
      "clips.kind.transition": "过渡", "clips.kind.loop": "循环", "clips.kind.speaking": "说话循环", "clips.versions": "版本", "clips.filter": "筛选版本", "clips.filter.all": "全部", "clips.filter.review": "待审阅", "clips.filter.rejected": "已弃用", "clips.noVersions": "此筛选条件下没有版本。", "clips.versionStatus.accepted": "已接受", "clips.versionStatus.rejected": "已弃用", "clips.versionStatus.failed": "失败", "clips.versionStatus.submitted": "已提交", "clips.versionStatus.generating": "生成中", "clips.versionStatus.review": "待审阅", "clips.versionStatus.pending": "待处理", "clips.reason": "原因：{reason}", "clips.error": "错误：{error}", "clips.basedOn": "基于 v{version}：{note}", "clips.promptVersion": "prompt v{version}", "clips.credits": "{credits} credits", "clips.pinB": "将 v{version} 钉住为 B", "clips.unpinB": "将已接受版本用作 B", "clips.selectVersion": "选择 v{version} 作为 A", "clips.details": "详情",
      "clips.tab.prompt": "提示词", "clips.tab.generation": "生成", "clips.tab.processing": "处理", "clips.tab.playback": "播放", "clips.tab.mouth": "嘴型", "clips.tab.qa": "QA", "clips.sentPrompt": "v{version} 实际发出的 prompt", "clips.noSnapshot": "此版本没有 prompt 快照。", "clips.currentPrompt": "当前 prompt 预览", "clips.negative": "负面 prompt", "clips.negativeNotSent": "此服务商未收到负面 prompt。", "clips.diffAgainst": "与 B · v{version} 的词级差异", "clips.subject": "当前主题块 · {block}", "clips.savePrompt": "保存为新 prompt 版本", "clips.promptSaved": "prompt 已保存为新版本", "clips.copyPrompt": "复制 prompt", "clips.copied": "prompt 已复制", "clips.copyFailed": "请选中 prompt 后手动复制。", "clips.note": "版本备注", "clips.saveNote": "保存备注", "clips.noteSaved": "版本备注已保存",
      "clips.accept": "接受 v{version}", "clips.accepted": "已接受 v{version}", "clips.reject": "填写原因并弃用…", "clips.rejectTitle": "弃用 v{version}", "clips.rejectReason": "原因（必填）", "clips.rejectHint": "版本会保留在归档中，并记录此原因。", "clips.rejected": "版本已弃用并归档", "clips.restore": "恢复 v{version}", "clips.restored": "版本已恢复", "clips.cancel": "取消", "clips.confirm": "确认", "clips.create": "创建",
      "clips.generate": "生成新版本 · {cost}", "clips.generateFrom": "基于 v{version} 生成 · {cost}", "clips.generateTitle": "生成新版本", "clips.generateFromTitle": "基于 v{version} 生成", "clips.generateSubject": "主题 prompt", "clips.generateNote": "备注（可选）", "clips.generateSettings": "当前设置：{provider} · {duration} s · {resolution}", "clips.generateHistorical": "此主题文字是 v{version} 当时记录的文字，将使用当前生成设置。", "clips.submit": "生成一次 · {cost}", "clips.started": "生成已开始", "clips.cost.credits": "credits", "clips.cost.quota": "会员额度", "clips.cost.usage": "按量计费", "clips.cost.paid": "付费生成", "clips.cost.free": "免费", "clips.costEstimate": "~{credits} credits", "clips.costManual": "手动", "clips.manualHint": "准备输入后，导入在外部生成器制作的版本。", "clips.notReady": "生成前请在设置中配置服务商。", "clips.stillsRequired": "生成或导入版本前，请先批准输入静帧。", "clips.promptIncomplete": "付费生成前请填写 prompt 占位文字。", "clips.historicalMissing": "历史主题块不可用，请打开提示词检查此版本。",
      "clips.import": "导入视频", "clips.importTitle": "导入版本", "clips.importVideo": "视频文件", "clips.importFolder": "PNG 帧文件夹", "clips.folder": "工作区内的相对文件夹路径", "clips.fps": "帧文件夹 FPS（文件夹必填）", "clips.importSubmit": "导入 · 免费", "clips.importChoice": "请选择视频文件或工作区内的帧文件夹其中一种。", "clips.importHint": "导入会新增一个版本，并将服务商输入标记为推定。", "clips.imported": "版本已导入", "clips.prepare": "准备输入", "clips.prepareTitle": "生成器输入", "clips.downloadPrompt": "下载 prompt.txt", "clips.downloadNegative": "下载 negative.txt", "clips.prepareHint": "这些是为外部生成器准备的当前已批准静帧和 prompt。", "clips.resume": "继续下载", "clips.resuming": "下载已恢复", "clips.adopt": "尾帧 → {pose} 静帧", "clips.adoptTitle": "采用片段帧作为静帧", "clips.frame": "帧（last 或从零开始的序号）", "clips.adoptHint": "此帧会成为 {pose} 的候选静帧，仍须通过 QA 并批准。", "clips.adopting": "静帧采用已开始", "clips.render": "渲染", "clips.renderCheck": "渲染并检查", "clips.rendering": "渲染已开始 · 免费", "clips.renderState": "渲染：{state}", "clips.qaState": "QA：{state}", "clips.acceptedSummary": "v{version} 已接受", "clips.noAccepted": "尚无已接受版本", "clips.sync": "同步行为图时序", "clips.syncTitle": "同步行为图时序", "clips.syncAdd": "为行为图中缺失的已渲染片段添加节点", "clips.syncHint": "现有边保持不变，仅同步时序和渲染路径。", "clips.synced": "行为图时序已同步",
      "clips.shortcuts.versions": "切换版本", "clips.shortcuts.accept": "接受", "clips.shortcuts.reject": "弃用", "clips.shortcuts.compare": "对比", "clips.shortcuts.play": "播放", "clips.shortcuts.loop": "循环", "clips.firstStill": "起始静帧：{pose}", "clips.lastStill": "结束静帧：{pose}", "clips.lastNotSent": "不发送尾帧", "clips.noStill": "未批准", "clips.free": "免费", "clips.progress": "{percent}%", "clips.jobRunning": "此片段有任务正在运行。", "clips.settingsHint": "请先保存编辑后的设置；生成会使用服务端的当前设置。"
    }
  };
  for (const [language, entries] of Object.entries(translations)) window.SFStudio.addTranslations(language, entries);

  const media = (path) => "/api/production/media?path=" + encodeURIComponent(path);
  const takePath = (clip, take, file) => `production/clips/${clip.id}/takes/${take.id}/${file}`;
  const creditCost = (take) => {
    const source = take.source || {};
    const before = source.balanceBefore && source.balanceBefore.credits;
    const after = source.balanceAfter && source.balanceAfter.credits;
    return typeof before === "number" && typeof after === "number" && Number.isFinite(before - after) && before >= after ? before - after : null;
  };

  function wordDiff(before, after) {
    const a = String(before || "").match(/\s+|\S+/g) || [];
    const b = String(after || "").match(/\s+|\S+/g) || [];
    let first = 0; let endA = a.length; let endB = b.length;
    while (first < endA && first < endB && a[first] === b[first]) first++;
    while (endA > first && endB > first && a[endA - 1] === b[endB - 1]) { endA--; endB--; }
    const x = a.slice(first,endA), y = b.slice(first,endB);
    const prefix = a.slice(0,first).join("");
    const suffix = a.slice(endA).join("");
    // Bound presentation work for large edits while displaying both exact texts.
    if ((x.length + 1) * (y.length + 1) > 250000) return [["same",prefix],["removed",x.join("")],["added",y.join("")],["same",suffix]].filter(([,text])=>text);
    const widths = y.length + 1;
    const directions = new Uint8Array((x.length + 1) * widths);
    let previous = new Uint32Array(widths);
    for (let i = 1; i <= x.length; i++) {
      const next = new Uint32Array(widths);
      for (let j = 1; j <= y.length; j++) {
        if (x[i - 1] === y[j - 1]) { next[j] = previous[j - 1] + 1; directions[i * widths + j] = 1; }
        else if (previous[j] >= next[j - 1]) { next[j] = previous[j]; directions[i * widths + j] = 2; }
        else { next[j] = next[j - 1]; directions[i * widths + j] = 3; }
      }
      previous = next;
    }
    const middle = []; let i = x.length; let j = y.length;
    while (i || j) {
      const direction = directions[i * widths + j];
      if (i && j && direction === 1) { middle.push(["same",x[--i]]); j--; }
      else if (i && (!j || direction === 2)) middle.push(["removed",x[--i]]);
      else middle.push(["added",y[--j]]);
    }
    const runs = [];
    for (const [type,text] of [["same",prefix],...middle.reverse(),["same",suffix]]) {
      if(!text)continue;
      if(runs.at(-1)?.[0]===type)runs.at(-1)[1]+=text;else runs.push([type,text]);
    }
    return runs;
  }

  function mountClips(initial) {
    let ctx = initial;
    const { h } = initial;
    const tr = (key, values) => ctx.t("clips." + key, values);
    let selectedA = null; let pinnedB = null; let filter = "all"; let detailTab = "prompt"; let showProcessed = false;
    let compare = null; let details = null; let detailsKey = null; let detailsPaused = false; let disposed = false;
    let currentClip = null; let dialog = null; let dialogRefresh = null;
    let promptDraft = null; const noteDrafts = new Map();
    const root = h("section", { class: "clip-studio", "aria-label": tr("title") });
    const header = h("div", { class: "clip-heading" });
    const variants = h("div", { class: "clip-variantbar" });
    const versionHead = h("div", { class: "clip-version-head" });
    const versionList = h("div", { class: "clip-version-list" });
    const compareRoot = h("div", { class: "clip-compare-root" });
    const detailTabs = h("div", { class: "tabs clip-details-tabs", role: "group" });
    const detailBody = h("div", { class: "clip-details-body" });
    const nativeDetailsRoot = h("div", { class: "clip-native-details" });
    const actions = h("div", { class: "clip-actions" });
    const shortcuts = h("div", { class: "tiny clip-shortcuts" });
    const columns = h("div", { class: "clip-columns" }, h("section", { class: "card clip-versions" }, versionHead,versionList),
      h("section", { class: "card clip-compare-panel" },compareRoot), h("section", { class: "card clip-details" },detailTabs,detailBody,actions));
    root.append(header,variants,columns,shortcuts); ctx.root.replaceChildren(root);
    const badge = (text, level = "") => h("span", { class: "badge " + level },text);
    const version = (take) => take ? take.version : null;
    const takeA = () => currentClip && currentClip.takes.find((take) => take.id === selectedA);
    const takeB = () => currentClip && currentClip.takes.find((take) => take.id === (pinnedB || currentClip.acceptedTake));
    const running = () => ctx.jobs.some((job) => job.status === "running" && job.kind === "clip" && job.owner === currentClip.id);
    const button = (key, action, attrs = {}, values = {}) => h("button", { type: "button", "data-clip-action": key, ...attrs, onclick: action }, tr(key,values));
    const inputReady = () => {
      const from = ctx.state.poses.find((pose) => pose.id === currentClip.from);
      const to = ctx.state.poses.find((pose) => pose.id === currentClip.to);
      return !!(from && from.acceptedTake && (currentClip.generation.lastFrame === "none" || (to && to.acceptedTake)));
    };
    const subject = (take) => {
      const id = currentClip.prompt.subject;
      const block = ctx.state.prompts.blocks[id];
      if (!block) return null;
      const number = take && take.prompt && take.prompt.blocks && take.prompt.blocks[id];
      return take ? block.versions.find((entry) => entry.version === number) || null : block.versions.at(-1);
    };
    const generationHint = () => {
      if (running()) return tr("jobRunning");
      if (currentClip.generation.provider === "manual") return tr("manualHint");
      if (!inputReady()) return tr("stillsRequired");
      const provider = ctx.state.tools.providers[currentClip.generation.provider];
      return !provider || !provider.keySet ? tr("notReady") : "";
    };

    function costLabel() {
      const generation = currentClip.generation;
      const provider = generation.provider;
      if (provider === "manual") return tr("costManual");
      if (currentClip.costEstimate) return tr("costEstimate", { credits: currentClip.costEstimate.credits });
      return tr(provider === "wan-cli" ? "cost.credits" : provider === "wan" || provider === "seedance" ? "cost.usage" : "cost.paid");
    }

    function status(take) {
      const name = take.status === "accepted" ? "accepted" : take.status === "rejected" ? "rejected" : take.state === "failed" ? "failed"
        : take.state === "submitted" ? "submitted" : ["submitting","generating","running"].includes(take.state) ? "generating" : take.state === "ready" ? "review" : "pending";
      return [tr("versionStatus." + name), name === "accepted" ? "pass" : ["rejected","failed"].includes(name) ? "fail" : name === "review" ? "watch" : "info"];
    }

    function selectedClip() {
      if (ctx.route.id) return ctx.state.clips.find((clip) => clip.id === ctx.route.id) || null;
      if (currentClip && ctx.state.clips.some((clip) => clip.id === currentClip.id)) return ctx.state.clips.find((clip) => clip.id === currentClip.id);
      const stamp = (clip) => clip.takes.at(-1)?.createdAt || clip.createdAt || "";
      const ordered = [...ctx.state.clips].sort((a,b) => stamp(b).localeCompare(stamp(a)) || a.id.localeCompare(b.id));
      return ordered.find((clip) => clip.takes.some((take) => take.state === "ready" && take.status === "candidate") || clip.render.state !== "current") || ordered[0] || null;
    }

    function endpoint(poseId, label) {
      const pose = ctx.state.poses.find((entry) => entry.id === poseId);
      const take = pose && pose.takes.find((entry) => entry.id === pose.acceptedTake);
      return [take && take.media && take.media.still ? h("img", { class: "thumb checker", src: media(`production/poses/${pose.id}/takes/${take.id}/${take.media.still}`), alt: tr(label,{pose:poseId}) }) : null,
        h("span", { class: "tiny" }, take ? `${poseId} v${take.version}` : `${poseId} · ${tr("noStill")}`)];
    }

    function renderHeader() {
      const clip = currentClip;
      const accepted = clip.takes.find((take) => take.id === clip.acceptedTake);
      const kind = clip.kind === "loop" && clip.mouth ? "speaking" : clip.kind;
      const summary = [accepted ? tr("acceptedSummary",{version:version(accepted)}) : tr("noAccepted"),tr("renderState",{state:ctx.t("production.status." + clip.render.state)})];
      if (clip.render.qa) summary.push(tr("qaState",{state:ctx.t("production.status." + clip.render.qa.status)}));
      const choose = h("select", { "aria-label": tr("choose"), "data-clip-select": "clip", onchange: (event) => ctx.navigate("#/clips/" + encodeURIComponent(event.target.value)) },ctx.state.clips.map((entry) => h("option",{value:entry.id},entry.id)));
      choose.value = clip.id;
      header.replaceChildren(h("h1",{class:"mono"},clip.id),badge(tr("kind." + kind)),h("span",{class:"clip-endpoints"},endpoint(clip.from,"firstStill"),h("span",{class:"tiny","aria-hidden":"true"},"→"),
        clip.generation.lastFrame === "none" ? h("span",{class:"tiny"},tr("lastNotSent")) : endpoint(clip.to,"lastStill")),badge(summary.join(" · "),clip.render.qa?.status === "fail" ? "fail" : clip.render.state === "stale" ? "watch" : accepted ? "pass" : ""),
        h("div",{class:"spacer"}),choose,button("import",openImport,{disabled:!inputReady(),title:!inputReady()?tr("stillsRequired"):null}),
        button("generate",() => openGenerate(),{class:"primary",disabled:!!generationHint(),title:generationHint()||null},{cost:costLabel()}),
        takeA() && takeA().status !== "accepted"
          ? button("processTake", event => processTake(takeA(), event.currentTarget), {disabled:takeA().state!=="ready"||running()})
          : button(clip.render.state === "current" ? "renderCheck" : "render",(event) => startJob("render",{},tr("rendering"),event.currentTarget),{disabled:!clip.acceptedTake||running()}));
    }

    function groupKey(clip) { return `${clip.kind === "loop" && clip.mouth ? "speaking" : clip.kind}:${clip.from}:${clip.to}`; }
    function renderVariants() {
      const group = ctx.state.clips.filter((clip) => groupKey(clip) === groupKey(currentClip));
      variants.replaceChildren(h("span",{class:"tiny"},tr("variants",{from:currentClip.from,to:currentClip.to})),...group.map((clip) => {
        const accepted = clip.takes.find((take) => take.id === clip.acceptedTake);
        const review = clip.takes.filter((take) => take.state === "ready" && take.status === "candidate").length;
        return h("a",{class:"clip-variant"+(clip.id===currentClip.id?" active":""),href:"#/clips/"+encodeURIComponent(clip.id),"data-variant":clip.id,"aria-current":clip.id===currentClip.id?"true":null},h("span",{class:"mono"},clip.id),
          accepted?badge(tr("acceptedSummary",{version:version(accepted)}),"pass"):null,review?badge(ctx.t("status.variantsReview",{count:1,pending:review}),"watch"):null);
      }),button("newVariant",openVariant,{class:"small"}),button("newClip",openNewClip,{class:"small"}));
    }

    function renderVersions() {
      const list = [...currentClip.takes].reverse().filter((take) => filter === "all" || (filter === "review" ? take.state === "ready" && take.status === "candidate" : take.status === "rejected"));
      versionHead.replaceChildren(h("h2",{class:"h3"},tr("versions")," ",h("span",{class:"tiny"},String(currentClip.takes.length))),h("div",{class:"tabs",role:"group","aria-label":tr("filter")},["all","review","rejected"].map((key) => h("button",{
        type:"button",class:filter===key?"active":"","data-version-filter":key,"aria-pressed":String(filter===key),onclick:()=>{filter=key;renderVersions();}
      },tr("filter."+key)))));
      versionList.replaceChildren(...(list.length ? list.map((take) => {
        const [label,level] = status(take);
        const path = take.media?.dir ? takePath(currentClip,take,`${take.media.dir}/000000.png`) : null;
        const thumb = path ? h("img",{class:"clip-version-thumb",src:media(path),alt:"",loading:"lazy"}) : take.media?.video ? h("video",{class:"clip-version-thumb",src:media(takePath(currentClip,take,take.media.video)),muted:true,preload:"metadata","aria-hidden":"true",tabindex:"-1"}) : h("span",{class:"clip-version-thumb","aria-hidden":"true"});
        const cost = creditCost(take); const blockVersion = take.prompt?.blocks?.[currentClip.prompt.subject];
        const based = currentClip.takes.find((entry)=>entry.id===take.basedOn);
        const subtitle = [cost!==null?tr("credits",{credits:cost}):null,blockVersion?tr("promptVersion",{version:blockVersion}):null].filter(Boolean).join(" · ");
        return h("div",{class:"clip-version-row"},h("button",{type:"button",class:"clip-version"+(take.id===selectedA?" active":""),"data-version":String(take.version),"data-take":take.id,"aria-pressed":String(take.id===selectedA),"aria-label":tr("selectVersion",{version:take.version}),onclick:()=>selectA(take.id)},
          thumb,h("span",{class:"clip-version-meta"},h("span",{class:"row"},h("b",{class:"mono"},`v${take.version}`),badge(label,level),h("span",{class:"mono clip-ab"},[take.id===selectedA?"A":null,take.id===(pinnedB||currentClip.acceptedTake)?"B":null].filter(Boolean).join(" / "))),
            subtitle?h("span",{class:"tiny"},subtitle):null,take.rejected?h("span",{},tr("reason",{reason:take.rejected.reason})):take.error?h("span",{},tr("error",{error:take.error})):take.basedOn?h("span",{},tr("basedOn",{version:based?.version??take.basedOn,note:take.note||""})):take.note?h("span",{},take.note):null)),
          h("button",{type:"button",class:"clip-pin","data-pin":take.id,"aria-pressed":String(pinnedB===take.id),onclick:()=>{pinnedB=pinnedB===take.id?null:take.id;renderVersions();updateCompare();renderDetails();}},tr(pinnedB===take.id?"unpinB":"pinB",{version:take.version})));
      }) : [h("p",{class:"tiny"},tr("noVersions"))]));
    }

    function selectA(id) { selectedA=id;showProcessed=false;renderHeader();renderVersions();updateCompare();renderDetails();renderActions(); }
    function updateCompare() {
      const local={...ctx,root:compareRoot}; const options={clip:currentClip,takeA:takeA(),takeB:takeB(),candidatePreview:showProcessed};
      if (compare) compare.update(local,options);
      else compare=window.SFClipCompare.mount(local,options);
    }

    function renderDetails() {
      detailTabs.setAttribute("aria-label",tr("details"));
      detailTabs.replaceChildren(...["prompt","generation","processing","playback","mouth","qa"].map((tab)=>h("button",{type:"button",class:detailTab===tab?"active":"","data-detail-tab":tab,"aria-pressed":String(detailTab===tab),onclick:()=>{detailTab=tab;renderDetails();}},tr("tab."+tab))));
      if (detailTab==="prompt") {
        if (details&&!detailsPaused) {details.pause();detailsPaused=true;}
        renderPrompt();
      } else {
        const candidate = takeA();
        if (detailTab === "qa" && candidate && candidate.status !== "accepted" && candidate.candidateRender?.state === "missing") {
          if (details && !detailsPaused) { details.pause(); detailsPaused=true; }
          detailBody.replaceChildren(h("p", {class:"tiny"}, tr("processFirst")));
          return;
        }
        const displayed = detailTab === "qa" && candidate?.candidateRender?.state !== "missing" && candidate?.candidateRender
          ? {...currentClip,render:candidate.candidateRender,output:candidate.candidateRender.output} : currentClip;
        const key=currentClip.id;
        const local={...ctx,root:nativeDetailsRoot};
        if(nativeDetailsRoot.parentNode!==detailBody)detailBody.replaceChildren(nativeDetailsRoot);
        if (details && detailsKey===key) details.update(local,{clip:displayed,tab:detailTab});
        else {if(details)details.cleanup();details=window.SFProduction.create(local).mountClipDetails(nativeDetailsRoot,displayed,detailTab);detailsKey=key;}
        detailsPaused=false;
      }
    }

    function renderPrompt() {
      const focused=document.activeElement;
      const focusDraft=focused instanceof HTMLTextAreaElement&&detailBody.contains(focused)?focused.dataset.clipDraft:null;
      const selection=focusDraft?[focused.selectionStart,focused.selectionEnd]:null;
      const take=takeA(); const other=takeB(); const snapshot=take?.prompt || (!take?currentClip.promptPreview:null);
      const nodes=[h("h3",{},take?tr("sentPrompt",{version:take.version}):tr("currentPrompt"))];
      if (snapshot && typeof snapshot.text==="string") {
        nodes.push(h("div",{class:"clip-block-versions"},Object.entries(snapshot.blocks||{}).map(([block,number])=>h("span",{class:"clip-block"},`${block} v${number}`))),h("pre",{"data-prompt-snapshot":"true"},snapshot.text),button("copyPrompt",()=>copy(snapshot.text)));
        if(snapshot.negative)nodes.push(h("h3",{},tr("negative")),h("pre",{},snapshot.negative),snapshot.negativeSent===false?h("p",{class:"tiny"},tr("negativeNotSent")):null);
        if(take && other && other.id!==take.id && other.prompt)nodes.push(h("h3",{},tr("diffAgainst",{version:other.version})),h("pre",{class:"clip-prompt-diff","data-word-diff":"true"},wordDiff(other.prompt.text,snapshot.text).map(([type,text])=>type==="same"?text:h(type==="added"?"ins":"del",{},text))));
      } else nodes.push(h("p",{class:"tiny"},tr("noSnapshot")));
      const current=subject(null);
      if(current){
        const input=h("textarea",{"data-clip-draft":"subject",value:promptDraft??current.text,oninput:(event)=>{promptDraft=event.target.value;}});
        const save=button("savePrompt",async(event)=>{
          const result=await ctx.run(()=>ctx.api("/api/production/prompt",{block:currentClip.prompt.subject,text:input.value}),tr("promptSaved"),event.currentTarget);
          if(result){promptDraft=null;renderPrompt();}
        });
        nodes.push(h("h3",{},tr("subject",{block:currentClip.prompt.subject})),input,save);
      }
      if(take){
        const note=h("textarea",{"data-clip-draft":"note",value:noteDrafts.get(take.id)??take.note??"",oninput:(event)=>noteDrafts.set(take.id,event.target.value)});
        nodes.push(h("h3",{},tr("note")),note,button("saveNote",async(event)=>{
          const result=await ctx.run(()=>ctx.api("/api/production/take-note",{kind:"clip",owner:currentClip.id,take:take.id,note:note.value}),tr("noteSaved"),event.currentTarget);
          if(result){noteDrafts.delete(take.id);renderPrompt();}
        }));
      }
      detailBody.replaceChildren(h("div",{class:"clip-prompt"},nodes));
      if(focusDraft){const field=detailBody.querySelector(`[data-clip-draft="${focusDraft}"]`);field?.focus({preventScroll:true});if(field&&selection)field.setSelectionRange(...selection);}
    }

    function renderActions() {
      const take=takeA(); const hint=generationHint();
      actions.replaceChildren();
      if(take){
        const preview = take.candidateRender;
        const qualified = preview?.state === "current" && ["pass","watch","fix"].includes(preview.qa?.status);
        if(take.status==="rejected")actions.append(button("restore",(event)=>decision("restore",take,"",event.currentTarget),{}, {version:take.version}));
        else actions.append(button("accept",(event)=>decision("accept",take,"",event.currentTarget),{class:"primary",disabled:!qualified||take.state!=="ready"||take.status==="accepted"||running(),title:qualified?null:tr(preview?.qa?.status==="fail"?"blockedQA":"processFirst")},{version:take.version}),button("reject",()=>openReject(take),{class:"danger",disabled:take.state!=="ready"}));
        if (preview && preview.state !== "missing") actions.append(button(showProcessed?"showSource":"showProcessed",()=>{showProcessed=!showProcessed;updateCompare();renderActions();}));
        actions.append(button("generateFrom",()=>openGenerate(take),{disabled:!!hint||!subject(take),title:hint||(!subject(take)?tr("historicalMissing"):null)},{version:take.version,cost:costLabel()}));
        if(take.state==="submitted")actions.append(button("resume",(event)=>startJob("resume",{take:take.id},tr("resuming"),event.currentTarget),{disabled:running()}));
        if(take.state==="ready"&&currentClip.kind==="transition")actions.append(button("adopt",()=>openAdopt(take),{}, {pose:currentClip.to}));
      }
      actions.append(h("div",{class:"row"},button("prepare",openPrepare,{class:"small",disabled:!inputReady()}),button("sync",openSync,{class:"small"})));
    }

    async function copy(text) { try {await navigator.clipboard.writeText(text);ctx.toast(tr("copied"));}catch(_){ctx.toast(tr("copyFailed"),true);} }
    function decision(action,take,reason,buttonElement) {return ctx.run(()=>action==="accept"
      ? ctx.api("/api/production/adopt-processed",{clip:currentClip.id,take:take.id})
      : ctx.api("/api/production/decision",{kind:"clip",owner:currentClip.id,take:take.id,action,reason}),tr(action==="accept"?"accepted":action==="reject"?"rejected":"restored",{version:take.version}),buttonElement);}
    async function processTake(take, buttonElement) {
      const result = await startJob("render-take", {take:take.id}, tr("processingTake"), buttonElement);
      if (result && !disposed && selectedA===take.id) {showProcessed=true;detailTab="qa";updateCompare();renderDetails();renderActions();}
    }
    function startJob(action,extra,message,buttonElement) {return ctx.run(()=>ctx.api("/api/production/jobs",{action,clip:currentClip.id,...extra}),message,buttonElement);}

    function modal(titleKey,titleValues={}) {
      if(dialog)return null;
      const el=h("dialog",{class:"clip-dialog","data-clip-dialog":titleKey});
      const form=h("form",{onsubmit:(event)=>event.preventDefault()});
      const title=h("h2",{}); const error=h("output",{role:"alert"});
      const cancel=button("cancel",()=>el.close());
      const buttons=h("div",{class:"dialog-actions"},cancel);
      form.append(title,error,buttons);el.append(form);root.append(el);dialog=el;
      el.addEventListener("keydown",(event)=>{if(event.key==="Escape")event.stopPropagation();});
      const labels=[];
      const label=(key,input,values={})=>{const text=h("span");labels.push(()=>text.textContent=tr(key,typeof values==="function"?values():values));return h("label",{},text,input);};
      const hint=(key,values={})=>{const p=h("p",{class:"dialog-hint"});labels.push(()=>p.textContent=tr(key,typeof values==="function"?values():values));return p;};
      const valuesOf=(values)=>typeof values==="function"?values():values;
      const refresh=()=>{title.textContent=tr(titleKey,valuesOf(titleValues));cancel.textContent=tr("cancel");labels.forEach((update)=>update());};
      dialogRefresh=refresh;
      el.addEventListener("close",()=>{if(dialog===el){dialog=null;dialogRefresh=null;}el.remove();},{once:true});
      const show=()=>{refresh();el.showModal();form.querySelector("input,textarea,select")?.focus();};
      const submit=(key,action,values={},attrs={})=>{
        const submitButton=h("button",{type:"submit",class:"primary","data-dialog-submit":titleKey,...attrs});labels.push(()=>submitButton.textContent=tr(key,valuesOf(values)));buttons.append(submitButton);
        let busy=false;
        el.addEventListener("cancel",(event)=>{if(busy)event.preventDefault();});
        form.addEventListener("submit",async(event)=>{
          event.preventDefault();if(busy||!form.reportValidity())return;busy=true;submitButton.disabled=true;cancel.disabled=true;error.textContent="";
          const fields=[...form.querySelectorAll("input,textarea,select")].map((field)=>[field,field.disabled]);
          fields.forEach(([field])=>{field.disabled=true;});
          try{await action();if(!disposed&&el.open)el.close();}
          catch(failure){error.textContent=String(failure.message||failure);}
          finally{busy=false;if(el.isConnected){submitButton.disabled=false;cancel.disabled=false;fields.forEach(([field,disabled])=>{field.disabled=disabled;});}}
        });
        return submitButton;
      };
      return {el,form,error,buttons,label,hint,show,submit,insert:(...nodes)=>buttons.before(...nodes)};
    }

    function openReject(take) {
      const view=modal("rejectTitle",{version:take.version});if(!view)return;
      const reason=h("textarea",{required:true,"data-dialog-field":"reason"});
      reason.addEventListener("input",()=>reason.setCustomValidity(reason.value.trim()?"":tr("rejectReason")));
      view.insert(view.hint("rejectHint"),view.label("rejectReason",reason));
      view.submit("confirm",async()=>{if(!reason.value.trim())throw new Error(tr("rejectReason"));await ctx.api("/api/production/decision",{kind:"clip",owner:currentClip.id,take:take.id,action:"reject",reason:reason.value.trim()});await ctx.refresh();ctx.toast(tr("rejected"));});view.show();
    }

    function openVariant() {
      const view=modal("newVariant");if(!view)return;
      const base=currentClip.id.replace(/\d+$/,"");let next=Number(currentClip.id.match(/\d+$/)?.[0]||1)+1;
      while(ctx.state.clips.some((clip)=>clip.id===base+next))next++;
      const id=h("input",{required:true,pattern:"[a-z0-9][a-z0-9_-]{0,63}",maxlength:64,value:(base+next).slice(0,64),"data-dialog-field":"id"});
      view.insert(view.label("variantId",id),view.hint("idHint"),view.hint("variantHint"));
      view.submit("create",async()=>{if(ctx.state.clips.some((clip)=>clip.id===id.value))throw new Error(tr("idHint"));await ctx.api("/api/production/variant",{from:currentClip.id,id:id.value});await ctx.refresh();ctx.navigate("#/clips/"+encodeURIComponent(id.value));ctx.toast(tr("variantCreated",{id:id.value}));});view.show();
    }

    function openNewClip() {
      const view=modal("newClip");if(!view)return;
      const id=h("input",{required:true,pattern:"[a-z0-9][a-z0-9_-]{0,63}",maxlength:64,"data-dialog-field":"id"});
      const poseSelect=()=>h("select",{},ctx.state.poses.map((pose)=>h("option",{value:pose.id},pose.id)));
      const from=poseSelect(),to=poseSelect();from.value=to.value=currentClip?.to||ctx.state.character.basePose;
      const phase=h("select",{},["loop","in","out"].map((value)=>h("option",{value},value)));
      const syncPhase=()=>{
        const loop=from.value===to.value;
        for(const option of phase.options)option.disabled=loop?option.value!=="loop":option.value==="loop";
        if(phase.selectedOptions[0]?.disabled)phase.value=loop?"loop":to.value===ctx.state.character.basePose?"out":"in";
      };
      from.addEventListener("change",syncPhase);to.addEventListener("change",syncPhase);syncPhase();
      view.insert(view.label("clipId",id),view.hint("idHint"),h("div",{class:"row"},view.label("from",from),view.label("to",to)),view.label("phase",phase));
      view.submit("create",async()=>{await ctx.api("/api/production/clip",{id:id.value,from:from.value,to:to.value,phase:phase.value});await ctx.refresh();ctx.navigate("#/clips/"+encodeURIComponent(id.value));ctx.toast(tr("clipCreated",{id:id.value}));});view.show();
    }

    function openGenerate(take) {
      if(generationHint())return;
      const historical=subject(take);if(!historical){ctx.toast(tr("historicalMissing"),true);return;}
      const view=modal(take?"generateFromTitle":"generateTitle",take?{version:take.version}:{});if(!view)return;
      const prompt=h("textarea",{required:true,value:historical.text,"data-dialog-field":"subject"});
      const note=h("textarea",{"data-dialog-field":"note"});
      view.insert(view.hint("generateSettings",()=>({provider:currentClip.generation.provider,duration:currentClip.generation.durationS,resolution:currentClip.generation.resolution})),view.hint("settingsHint"),take?view.hint("generateHistorical",{version:take.version}):h("span"),view.label("generateSubject",prompt),view.label("generateNote",note));
      view.submit("submit",async()=>{
        const current=subject(null);
        if(!current||current.text!==prompt.value)await ctx.api("/api/production/prompt",{block:currentClip.prompt.subject,text:prompt.value});
        await ctx.api("/api/production/jobs",{action:"generate",clip:currentClip.id,provider:currentClip.generation.provider,...(take?{basedOn:take.id}:{}),note:note.value});
        await ctx.refresh();ctx.toast(tr("started"));
      },()=>({cost:costLabel()}));view.show();
    }

    function openImport() {
      const view=modal("importTitle");if(!view)return;
      const file=h("input",{type:"file",accept:"video/mp4,video/webm,video/quicktime","data-dialog-field":"video"});
      const folder=h("input",{type:"text","data-dialog-field":"folder"});
      const fps=h("input",{type:"number",min:0.01,step:"any",value:24,disabled:true,"data-dialog-field":"fps"});
      folder.addEventListener("input",()=>{fps.disabled=!folder.value.trim();fps.required=!!folder.value.trim();});
      const note=h("textarea",{"data-dialog-field":"note"});
      view.insert(view.hint("importHint"),view.label("importVideo",file),view.label("folder",folder),view.label("fps",fps),view.label("generateNote",note));
      view.submit("importSubmit",async()=>{
        if(file.files[0]&&folder.value.trim())throw new Error(tr("importChoice"));
        if(file.files[0]){
          const video=file.files[0];const query=new URLSearchParams({kind:"clip",owner:currentClip.id,name:video.name,note:note.value});
          const response=await fetch("/api/production/upload?"+query,{method:"POST",headers:{"Content-Type":"application/octet-stream"},body:video});
          const data=await response.json();if(!response.ok||!data.ok)throw new Error(data.error||response.statusText);selectedA=data.take.id;
        }else if(folder.value.trim()){
          const data=await ctx.api("/api/production/import-frames",{clip:currentClip.id,path:folder.value.trim(),fps:Number(fps.value),note:note.value});selectedA=data.take.id;
        }else throw new Error(tr("importVideo"));
        await ctx.refresh();ctx.toast(tr("imported"));
      });view.show();
    }

    function openPrepare() {
      const view=modal("prepareTitle");if(!view)return;
      const urls=[];
      const download=(name,text,key)=>{const url=URL.createObjectURL(new Blob([text],{type:"text/plain;charset=utf-8"}));urls.push(url);return h("a",{class:"btn",href:url,download:name},tr(key));};
      const link=(end)=>h("a",{class:"btn",href:`/api/production/input?clip=${encodeURIComponent(currentClip.id)}&end=${end}`,download:`${end}.png`},`${end}.png`);
      view.insert(view.hint("prepareHint"),h("div",{class:"row"},link("first"),currentClip.generation.lastFrame!=="none"?link("last"):null,download("prompt.txt",currentClip.promptPreview.text||"","downloadPrompt"),download("negative.txt",currentClip.promptPreview.negative||"","downloadNegative")),h("pre",{},currentClip.promptPreview.text||currentClip.promptPreview.error||""));
      view.el.addEventListener("close",()=>urls.forEach((url)=>URL.revokeObjectURL(url)),{once:true});view.show();
    }

    function openAdopt(take) {
      const view=modal("adoptTitle");if(!view)return;
      const frame=h("input",{required:true,pattern:"last|[0-9]+",value:"last","data-dialog-field":"frame"});
      view.insert(view.hint("adoptHint",{pose:currentClip.to}),view.label("frame",frame));
      view.submit("confirm",async()=>{await ctx.api("/api/production/jobs",{action:"adopt",pose:currentClip.to,clip:currentClip.id,take:take.id,frame:frame.value});await ctx.refresh();ctx.toast(tr("adopting"));});view.show();
    }

    function openSync() {
      const view=modal("syncTitle");if(!view)return;
      const add=h("input",{type:"checkbox"});view.insert(view.hint("syncHint"),view.label("syncAdd",add));
      view.submit("confirm",async()=>{await ctx.api("/api/production/graph-sync",{addMissing:add.checked});await ctx.refresh();ctx.toast(tr("synced"));});view.show();
    }

    function renderShortcuts() {
      shortcuts.replaceChildren(...[["J / K","versions"],["A","accept"],["X","reject"],["C","compare"],["Space","play"],["L","loop"]].map(([key,label])=>h("span",{},h("kbd",{},key)," ",tr("shortcuts."+label))));
    }

    function update(next) {
      ctx=next;root.setAttribute("aria-label",tr("title"));
      const previous=currentClip?.id;currentClip=selectedClip();
      if(!currentClip){header.replaceChildren(h("h1",{},tr("title")));variants.replaceChildren();columns.hidden=true;shortcuts.replaceChildren();header.append(h("p",{class:"tiny"},tr(ctx.route.id?"missing":"none")),button("newClip",openNewClip));return;}
      columns.hidden=false;
      if(previous!==currentClip.id){selectedA=null;pinnedB=null;promptDraft=null;showProcessed=false;}
      if(!currentClip.takes.some((take)=>take.id===selectedA))selectedA=[...currentClip.takes].reverse().find((take)=>take.state==="ready"&&take.status==="candidate")?.id||currentClip.acceptedTake||currentClip.takes.at(-1)?.id||null;
      if(pinnedB&&!currentClip.takes.some((take)=>take.id===pinnedB))pinnedB=null;
      renderHeader();renderVariants();renderVersions();updateCompare();renderDetails();renderActions();renderShortcuts();if(dialogRefresh)dialogRefresh();
    }

    function keydown(event) {
      if(disposed||dialog||ctx.route.tool||!currentClip||event.defaultPrevented||event.ctrlKey||event.altKey||event.metaKey||event.repeat)return;
      const target=event.target;
      if(target instanceof Element&&(target.closest("input,textarea,select,[contenteditable=true]")||target.closest("dialog")))return;
      const key=event.key.toLowerCase();
      if(!["j","k","a","x","c"," ","l"].includes(key))return;
      event.preventDefault();
      if(key==="j"||key==="k"){
        const list=[...currentClip.takes].reverse().filter((take)=>filter==="all"||(filter==="review"?take.state==="ready"&&take.status==="candidate":take.status==="rejected"));
        const index=list.findIndex((take)=>take.id===selectedA);const next=list[Math.max(0,Math.min(list.length-1,index+(key==="j"?1:-1)))];if(next)selectA(next.id);
      }else if(key==="a")actions.querySelector('[data-clip-action="accept"]')?.click();
      else if(key==="x")actions.querySelector('[data-clip-action="reject"]')?.click();
      else if(key==="c")compare?.toggleMode();else if(key===" ")compare?.togglePlay();else if(key==="l")compare?.toggleLoop();
    }
    document.addEventListener("keydown",keydown);
    update(initial);
    return {update,cleanup:()=>{disposed=true;document.removeEventListener("keydown",keydown);compare?.cleanup();details?.cleanup();if(dialog){dialog.close();dialog.remove();} }};
  }
  window.SFStudio.register("clips",mountClips);
})();
