"use strict";
(() => {
  // Shared production labels use the Studio dictionaries; prompts, ids and logs stay verbatim.
  const translations = { en: {
  "production.addPoseHint": "Add a pose to start.",
  "production.generateStill": "Generate still",
  "production.writePlaceholders": "Write the prompt placeholders first",
  "production.alphaRequired": "Configure the alpha processor: provider images are opaque",
  "production.importStill": "Import a generated still ",
  "production.noNormalizedStill": "No normalised still yet. Import a generated or edited image.",
  "production.takes": "Takes",
  "production.prompt": "Prompt",
  "production.stillPrompt": "Prompt for the still editor (input: the base still)",
  "production.overlay": "overlay",
  "production.difference": "difference",
  "production.takeOnly": "take only",
  "production.baseOnly": "base only",
  "production.view": "View",
  "production.opacity": "Opacity",
  "production.metric": "Metric",
  "production.thisStill": "This still",
  "production.expected": "Expected",
  "production.headTop": "head top (px)",
  "production.headCenter": "head centre (px)",
  "production.visibleArea": "visible area",
  "production.edgesTouched": "edges touched",
  "production.rejectReason": "Why is this take rejected? It stays in the archive with this note.",
  "production.approveStill": "Approve still",
  "production.useTake": "Use this take",
  "production.rejectArchive": "Reject & archive",
  "production.restore": "Restore",
  "production.manualHint": "Manual clips: copy the prompt and inputs into your generator, then import the video",
  "production.addClipHint": "Add a clip between two approved poses.",
  "production.settings": "Settings",
  "production.manualProvider": "Manual provider",
  "production.importTake": "Import a take ",
  "production.renderAccepted": "Render accepted take",
  "production.noTakes": "No takes yet.",
  "production.render": "Render",
  "production.generatorInputs": "Generator inputs:",
  "production.importInputsHint": "· import the video you make from them as a take",
  "production.stillNotApproved": "still not approved",
  "production.provider": "Provider",
  "production.duration": "Duration (s)",
  "production.resolution": "Resolution",
  "production.seed": "Seed",
  "production.inputScale": "Input scale",
  "production.register": "Register ends to the stills",
  "production.margin": "Canvas margin each side (px)",
  "production.interpolate": "Interpolate ×",
  "production.lockHead": "Lock head frames",
  "production.lockTail": "Lock tail frames",
  "production.edgeGuard": "Edge guard (px)",
  "production.playbackSpeed": "Playback speed",
  "production.playback": "Playback",
  "production.lastFrameInput": "Last frame input (none: first frame only)",
  "production.pingpong": "Pingpong loop",
  "production.mouthSet": "Mouth set (silence overlay)",
  "production.mouthSource": "Closed mouth: shared, still, frame:N or pose:ID",
  "production.settingsSaved": "Settings saved",
  "production.saveSettings": "Save settings",
  "production.settingsStale": "Changing processing or playback makes the current render stale.",
  "production.promptSnapshot": "Prompt snapshot",
  "production.firstLastInputs": "First / last frame inputs",
  "production.firstOnlyInput": "First frame input (no last frame)",
  "production.externalTool": " (handed to an external tool)",
  "production.resume": "Resume download",
  "production.previewCapped": "Preview is capped at 30 fps; runtime timing is shown above.",
  "production.simulateSilence": " Simulate silence: paste the closed mouth inside the tracked mask",
  "production.seam": "Seam",
  "production.level": "Level",
  "production.faceLightness": "Face L*",
  "production.deltaHeadTop": "Δ head top",
  "production.deltaHeadCenter": "Δ head centre",
  "production.templateError": "template error",
  "production.copyPrompt": "Copy prompt",
  "production.promptCopied": "Prompt copied",
  "production.negativePrefix": "Negative: ",
  "production.promptLibrary": "Prompt library",
  "production.template": "Template",
  "production.blocks": "Blocks",
  "production.joinedBy": "Joined by",
  "production.negative": "Negative",
  "production.blankLine": "blank line",
  "production.saveVersion": "Save as new version",
  "production.written": "written",
  "production.empty": "(empty)",
  "production.jobs": "Jobs",
  "production.noJobs": "No jobs in this session.",
  "production.newPoseId": "New pose id (lowercase letters, digits, _ or -)",
  "production.poseDescription": "Short description (optional)",
  "production.poseImportHint": "Import, generate or take a still",
  "production.poseEndPort": "Clips that end on this pose",
  "production.poseStartPort": "Drag onto a pose or empty space to make a clip from this pose",
  "production.noStill": "No still yet",
  "production.savePrompt": "Save prompt",
  "production.firstFrameOnly": "first frame only",
  "production.noTakesShort": "No takes yet",
  "production.generate": "Generate",
  "production.importTakeButton": "Import take",
  "production.importVideoHint": "Import a video made elsewhere as a new take",
  "production.poseInspector": "Pose still and takes",
  "production.clipInspector": "Clip settings, takes and render",
  "production.close": "Close",
  "production.rendered": "rendered",
  "production.notRendered": "not rendered",
  "production.noTakeChosen": "no take chosen",
  "production.approveBase": "Approve the {pose} still first",
  "production.apiKey": "Set the API key environment variable for {provider}",
  "production.editBase": "Edit the approved {pose} still with {provider}",
  "production.confirmStill": "Submit a paid image edit of the {base} still into {pose} to {provider} ({model})?",
  "production.sharedMouth": "shared ({pose})",
  "production.closedMouthChanged": "Closed mouth updated; affected speaking loops are now stale",
  "production.imageEditor": "Image editor ",
  "production.sharedClosedMouth": "Shared closed mouth for speaking loops ",
  "production.poseClosedMouth": "Closed mouth for this pose's speaking loops ",
  "production.guideLines": "Cyan: base head top and head centre. Amber: this pose's intended offset. Only the character's cut edges ({edges}) may touch the canvas.",
  "production.rejectedReason": "Rejected: {reason}",
  "production.noReason": "no reason given",
  "production.frameSource": "frame {frame} of {clip} take {take}",
  "production.decisionAccepted": "Accepted {take}",
  "production.decisionArchived": "Archived {take}",
  "production.decisionRestored": "Restored {take}",
  "production.approvePose": "Approve a still for {pose} first",
  "production.approveEnd": "Approve a still for {pose}, or set the last frame input to none and adopt a frame of a take as that still",
  "production.loginRequired": "Log in to {provider} first (wan auth login)",
  "production.firstFrame": "first frame",
  "production.lastFrame": "last frame",
  "production.lastNotSent": "last frame (not sent)",
  "production.generateWith": "Generate with {provider}",
  "production.archive": "Archive ({count} rejected)",
  "production.adoptHint": "Make the last frame of this take a candidate still for {pose}; approve it on its pose",
  "production.adopt": "Last frame → {pose} still",
  "production.renderSummary": "{count} frames · {interval} ms/frame · {mode} · take {take}",
  "production.confirmClip": "Submit a paid generation of {clip} to {provider} ({model}), {duration}s at {resolution}?",
  "production.placeholders": "{count} placeholder(s)",
  "production.promptSafety": "Saving a block adds a version; takes keep the exact text and versions they used. Prompts containing {{PLACEHOLDER: ...}} are never sent to a paid provider.",
  "production.promptSaved": "{clip}: prompt saved as a new version",
  "production.blockSaved": "{block}: new version saved",
  "production.usedAtVersion": "used by {count} take(s) at this version",
  "production.history": "History ({count} versions)",
  "production.historyUsage": "v{version} · {at} · used by {count} take(s)",
  "production.jobStarted": "{action} started for {owner}",
  "production.result": "result: {result}",
  "production.imported": "Imported {file}",
  "production.poseAdded": "Pose {pose} added",
  "production.offset": "intended offset {offset}",
  "production.anchorsChanged": "base anchors changed: approve again",
  "production.clipFrameSource": "frame {frame} of {clip}",
  "production.candidatePrefix": "candidate · ",
  "production.importedLabel": "imported",
  "production.stillAlt": "{pose} still",
  "production.startsFrom": "Starts from the {pose} still",
  "production.endsOn": "Ends on {pose}",
  "production.loopInputs": "Loop on the {pose} still (first and last frame)",
  "production.clipInputs": "First frame: {from} still · last frame: {last}",
  "production.notSentEnd": "not sent (ends on {pose})",
  "production.promptVersion": "prompt v{version}",
  "production.archivedCount": "+{count} archived",
  "production.newTakeHint": "Generate a new take with {provider}",
  "production.adoptTakeHint": "Make the last frame of take {take} a candidate still for {pose}",
  "production.newPoseFrom": "New pose reached from {pose}. Its transition is generated from the {pose} still alone, and a frame of the result becomes the new pose's still. Pose id (lowercase letters, digits, _ or -):",
  "production.loopClipId": "Loop clip on {pose}: clip id",
  "production.transitionClipId": "Transition {from} → {to}: clip id",
  "production.clipAdded": "Clip {clip} added",
  "production.poseAndClipAdded": "Pose {pose} and clip {clip} added: generate a take, then take its last frame as the {pose} still",
  "production.diffFrom": "From version",
  "production.diffTo": "To version",
  "production.compareVersions": "Compare versions",
  "production.jobFilter": "Filter jobs",
  "production.jobsall": "All jobs",
  "production.jobsrunning": "Running",
  "production.jobsfailed": "Failed",
  "production.submitted": "Submitted provider tasks",
  "production.canvasTitle": "Canvas",
  "production.fit": "Fit",
  "production.autoLayout": "Auto layout",
  "production.autoLayoutHint": "Arrange every card again from the base pose",
  "production.addPose": "+ Pose",
  "production.guide": "Guide",
  "production.wireStill": "still sent as a frame",
  "production.wireFirst": "first frame only",
  "production.wireAdopted": "still taken from a take",
  "production.canvasHelp": "Drag from a pose's right port to make a clip · drag a card's title to move it · wheel to zoom",
  "production.language": "Language",
  "production.providers": "Providers",
  "production.processors": "Local processors",
  "production.ready": "Ready",
  "production.notReady": "Not ready",
  "production.defaultConcept": "Default concept image provider",
  "production.defaultStill": "Default final still provider",
  "production.batchThreshold": "Batch confirmation threshold",
  "production.batchThresholdHint": "Ask for a second confirmation above this many requests.",
  "production.defaults": "Production defaults",
  "production.amadeusDir": "Amadeus character pack directory",
  "production.notConfigured": "Not configured",
  "production.readOnly": "Used read-only for export comparison.",
  "production.saveDefaults": "Save defaults",
  "production.defaultsSaved": "Production defaults saved",
  "production.noImageProviders": "No image providers configured.",
  "production.status.re-check": "re-check",
  "production.status.approved": "approved",
  "production.status.needs approval": "needs approval",
  "production.status.no still": "no still",
  "production.status.base": "base",
  "production.status.stale": "stale",
  "production.status.current": "current",
  "production.status.missing": "missing",
  "production.status.accepted": "accepted",
  "production.status.candidate": "candidate",
  "production.status.rejected": "rejected",
  "production.status.pass": "pass",
  "production.status.watch": "watch",
  "production.status.fix": "fix",
  "production.status.fail": "fail",
  "production.status.pending": "pending",
  "production.status.running": "running",
  "production.status.succeeded": "succeeded",
  "production.status.failed": "failed",
  "production.status.complete": "complete",
  "production.status.placeholder": "placeholder",
  "production.status.loop": "loop",
  "production.status.transition": "transition",
  "production.status.submitted": "submitted",
  "production.status.ready": "ready"
}, "zh-CN": {
  "production.addPoseHint": "添加一个姿态以开始。",
  "production.generateStill": "生成静帧",
  "production.writePlaceholders": "先填写 prompt 占位文字",
  "production.alphaRequired": "请配置抠图处理器：服务商返回的图片不透明",
  "production.importStill": "导入生成的静帧 ",
  "production.noNormalizedStill": "还没有规范化的静帧。请导入生成或编辑的图片。",
  "production.takes": "尝试",
  "production.prompt": "Prompt",
  "production.stillPrompt": "静帧编辑 prompt（输入：基准静帧）",
  "production.overlay": "叠加",
  "production.difference": "差异",
  "production.takeOnly": "只看尝试",
  "production.baseOnly": "只看基准",
  "production.view": "视图",
  "production.opacity": "透明度",
  "production.metric": "指标",
  "production.thisStill": "当前静帧",
  "production.expected": "预期",
  "production.headTop": "头顶（px）",
  "production.headCenter": "头部中心（px）",
  "production.visibleArea": "可见区域",
  "production.edgesTouched": "触边",
  "production.rejectReason": "为什么弃用这个尝试？它会带此备注保留在归档中。",
  "production.approveStill": "批准静帧",
  "production.useTake": "采用此尝试",
  "production.rejectArchive": "弃用并归档",
  "production.restore": "恢复",
  "production.manualHint": "手动片段：将 prompt 和输入图复制到生成器，再导入视频",
  "production.addClipHint": "在两个已批准的姿态之间添加片段。",
  "production.settings": "设置",
  "production.manualProvider": "手动服务商",
  "production.importTake": "导入尝试 ",
  "production.renderAccepted": "渲染已采用的尝试",
  "production.noTakes": "还没有尝试。",
  "production.render": "渲染",
  "production.generatorInputs": "生成器输入：",
  "production.importInputsHint": "· 将由这些输入生成的视频导入为尝试",
  "production.stillNotApproved": "静帧未批准",
  "production.provider": "服务商",
  "production.duration": "时长（s）",
  "production.resolution": "分辨率",
  "production.seed": "Seed",
  "production.inputScale": "输入缩放",
  "production.register": "将首尾对齐到静帧",
  "production.margin": "画布每边留白（px）",
  "production.interpolate": "插帧 ×",
  "production.lockHead": "锁定开头帧",
  "production.lockTail": "锁定结尾帧",
  "production.edgeGuard": "边缘保护（px）",
  "production.playbackSpeed": "播放速度",
  "production.playback": "播放方式",
  "production.lastFrameInput": "尾帧输入（none：只用首帧）",
  "production.pingpong": "往返循环",
  "production.mouthSet": "嘴型集（静默叠加）",
  "production.mouthSource": "闭嘴来源：shared、still、frame:N 或 pose:ID",
  "production.settingsSaved": "设置已保存",
  "production.saveSettings": "保存设置",
  "production.settingsStale": "处理或播放设置改变后，当前渲染会过期。",
  "production.promptSnapshot": "Prompt 快照",
  "production.firstLastInputs": "首帧 / 尾帧输入",
  "production.firstOnlyInput": "首帧输入（无尾帧）",
  "production.externalTool": "（交给外部工具）",
  "production.resume": "继续下载",
  "production.previewCapped": "预览上限为 30 fps；上方显示实际运行时的时间设置。",
  "production.simulateSilence": " 模拟静默：将闭嘴图像贴入跟踪遮罩",
  "production.seam": "接缝",
  "production.level": "等级",
  "production.faceLightness": "面部 L*",
  "production.deltaHeadTop": "Δ 头顶",
  "production.deltaHeadCenter": "Δ 头部中心",
  "production.templateError": "模板错误",
  "production.copyPrompt": "复制 prompt",
  "production.promptCopied": "Prompt 已复制",
  "production.negativePrefix": "负面 prompt：",
  "production.promptLibrary": "Prompt 库",
  "production.template": "模板",
  "production.blocks": "文本块",
  "production.joinedBy": "连接符",
  "production.negative": "负面 prompt",
  "production.blankLine": "空行",
  "production.saveVersion": "保存为新版本",
  "production.written": "已填写",
  "production.empty": "（空）",
  "production.jobs": "任务",
  "production.noJobs": "本次会话还没有任务。",
  "production.newPoseId": "新姿态 id（小写字母、数字、_ 或 -）",
  "production.poseDescription": "简短说明（可选）",
  "production.poseImportHint": "导入、生成或提取静帧",
  "production.poseEndPort": "以此姿态结束的片段",
  "production.poseStartPort": "拖到姿态或空白处，从此姿态建立片段",
  "production.noStill": "还没有静帧",
  "production.savePrompt": "保存 prompt",
  "production.firstFrameOnly": "只用首帧",
  "production.noTakesShort": "还没有尝试",
  "production.generate": "生成",
  "production.importTakeButton": "导入尝试",
  "production.importVideoHint": "导入其他工具生成的视频为新尝试",
  "production.poseInspector": "姿态静帧和尝试",
  "production.clipInspector": "片段设置、尝试和渲染",
  "production.close": "关闭",
  "production.rendered": "已渲染",
  "production.notRendered": "未渲染",
  "production.noTakeChosen": "未选择尝试",
  "production.approveBase": "先批准 {pose} 静帧",
  "production.apiKey": "请为 {provider} 设置 API 密钥环境变量",
  "production.editBase": "用 {provider} 编辑已批准的 {pose} 静帧",
  "production.confirmStill": "将 {base} 静帧付费编辑为 {pose}，提交到 {provider}（{model}）？",
  "production.sharedMouth": "共用（{pose}）",
  "production.closedMouthChanged": "闭嘴来源已更新；受影响的说话循环现已过期",
  "production.imageEditor": "图像编辑器 ",
  "production.sharedClosedMouth": "说话循环共用的闭嘴来源 ",
  "production.poseClosedMouth": "此姿态说话循环的闭嘴来源 ",
  "production.guideLines": "青色：基准头顶和头部中心。琥珀色：此姿态的预期偏移。只有角色允许裁切的边（{edges}）可以触碰画布。",
  "production.rejectedReason": "已弃用：{reason}",
  "production.noReason": "未提供原因",
  "production.frameSource": "{clip} 尝试 {take} 的第 {frame} 帧",
  "production.decisionAccepted": "已采用 {take}",
  "production.decisionArchived": "已归档 {take}",
  "production.decisionRestored": "已恢复 {take}",
  "production.approvePose": "先批准 {pose} 静帧",
  "production.approveEnd": "请批准 {pose} 静帧，或将尾帧输入设为 none，再从尝试中采用一帧作为该静帧",
  "production.loginRequired": "请先登录 {provider}（wan auth login）",
  "production.firstFrame": "首帧",
  "production.lastFrame": "尾帧",
  "production.lastNotSent": "尾帧（不发送）",
  "production.generateWith": "用 {provider} 生成",
  "production.archive": "归档（{count} 个弃用）",
  "production.adoptHint": "将此尝试的最后一帧变为 {pose} 的候选静帧；请在该姿态上批准",
  "production.adopt": "尾帧 → {pose} 静帧",
  "production.renderSummary": "{count} 帧 · {interval} ms/帧 · {mode} · 尝试 {take}",
  "production.confirmClip": "付费生成 {clip}，提交到 {provider}（{model}），{duration}s，{resolution}？",
  "production.placeholders": "{count} 个占位文字",
  "production.promptSafety": "保存文本块会新增版本；每个尝试保留它使用的确切文本和版本。含 {{PLACEHOLDER: ...}} 的 prompt 不会发送给付费服务商。",
  "production.promptSaved": "{clip}：prompt 已保存为新版本",
  "production.blockSaved": "{block}：新版本已保存",
  "production.usedAtVersion": "此版本被 {count} 个尝试使用",
  "production.history": "历史（{count} 个版本）",
  "production.historyUsage": "v{version} · {at} · 被 {count} 个尝试使用",
  "production.jobStarted": "已为 {owner} 开始{action}",
  "production.result": "结果：{result}",
  "production.imported": "已导入 {file}",
  "production.poseAdded": "已添加姿态 {pose}",
  "production.offset": "预期偏移 {offset}",
  "production.anchorsChanged": "基准锚点改变：请重新批准",
  "production.clipFrameSource": "{clip} 的第 {frame} 帧",
  "production.candidatePrefix": "候选 · ",
  "production.importedLabel": "已导入",
  "production.stillAlt": "{pose} 静帧",
  "production.startsFrom": "从 {pose} 静帧开始",
  "production.endsOn": "以 {pose} 结束",
  "production.loopInputs": "以 {pose} 静帧循环（首尾帧）",
  "production.clipInputs": "首帧：{from} 静帧 · 尾帧：{last}",
  "production.notSentEnd": "不发送（以 {pose} 结束）",
  "production.promptVersion": "prompt v{version}",
  "production.archivedCount": "+{count} 个归档",
  "production.newTakeHint": "用 {provider} 生成新尝试",
  "production.adoptTakeHint": "将尝试 {take} 的尾帧变为 {pose} 的候选静帧",
  "production.newPoseFrom": "从 {pose} 到达的新姿态。过渡只使用 {pose} 静帧生成，结果中的一帧将变为新姿态静帧。姿态 id（小写字母、数字、_ 或 -）：",
  "production.loopClipId": "{pose} 的循环片段：片段 id",
  "production.transitionClipId": "过渡 {from} → {to}：片段 id",
  "production.clipAdded": "已添加片段 {clip}",
  "production.poseAndClipAdded": "已添加姿态 {pose} 和片段 {clip}：生成尝试，再采用其尾帧作为 {pose} 静帧",
  "production.diffFrom": "起始版本",
  "production.diffTo": "目标版本",
  "production.compareVersions": "比较版本",
  "production.jobFilter": "筛选任务",
  "production.jobsall": "全部任务",
  "production.jobsrunning": "运行中",
  "production.jobsfailed": "失败",
  "production.submitted": "已提交的服务商任务",
  "production.canvasTitle": "画布",
  "production.fit": "适应视图",
  "production.autoLayout": "自动布局",
  "production.autoLayoutHint": "从基准姿态重新排列所有卡片",
  "production.addPose": "+ 姿态",
  "production.guide": "指南",
  "production.wireStill": "静帧作为输入帧",
  "production.wireFirst": "只用首帧",
  "production.wireAdopted": "静帧取自尝试",
  "production.canvasHelp": "从姿态右侧接口拖线建立片段 · 拖动卡片标题移动 · 滚轮缩放",
  "production.language": "语言",
  "production.providers": "服务商",
  "production.processors": "本地处理器",
  "production.ready": "就绪",
  "production.notReady": "未就绪",
  "production.defaultConcept": "默认概念图像服务商",
  "production.defaultStill": "默认正式静帧服务商",
  "production.batchThreshold": "批量确认阈值",
  "production.batchThresholdHint": "一次请求超过此数量时再次确认。",
  "production.defaults": "生产默认设置",
  "production.amadeusDir": "Amadeus 角色包目录",
  "production.notConfigured": "未配置",
  "production.readOnly": "仅用于读取导出对比。",
  "production.saveDefaults": "保存默认设置",
  "production.defaultsSaved": "生产默认设置已保存",
  "production.noImageProviders": "尚未配置图像服务商。",
  "production.status.re-check": "重新检查",
  "production.status.approved": "已批准",
  "production.status.needs approval": "待批准",
  "production.status.no still": "无静帧",
  "production.status.base": "基准",
  "production.status.stale": "已过期",
  "production.status.current": "当前",
  "production.status.missing": "缺失",
  "production.status.accepted": "已采用",
  "production.status.candidate": "候选",
  "production.status.rejected": "已弃用",
  "production.status.pass": "通过",
  "production.status.watch": "留意",
  "production.status.fix": "需修复",
  "production.status.fail": "失败",
  "production.status.pending": "待处理",
  "production.status.running": "运行中",
  "production.status.succeeded": "已完成",
  "production.status.failed": "失败",
  "production.status.complete": "完整",
  "production.status.placeholder": "占位文字",
  "production.status.loop": "循环",
  "production.status.transition": "过渡",
  "production.status.submitted": "已提交",
  "production.status.ready": "就绪"
} };
  translations.en["production.clipSummary"] = "{from} → {to} · {kind} · phase {phase}";
  translations["zh-CN"]["production.clipSummary"] = "{from} → {to} · {kind} · 阶段 {phase}";
  translations.en["production.frameCount"] = "{count} frames @ {fps} fps";
  translations["zh-CN"]["production.frameCount"] = "{count} 帧 @ {fps} fps";
  translations.en["production.outputFrame"] = "output frame {index}";
  translations["zh-CN"]["production.outputFrame"] = "输出第 {index} 帧";
  translations.en["production.mouthStill"] = "{pose} still ({kind})";
  translations["zh-CN"]["production.mouthStill"] = "{pose} 静帧（{kind}）";
  translations.en["production.mouthSummary"] = "Mouth set {set} · closed mouth from {from} · mask {width}×{height}px · tracking {mean} (min {min}) · movement {span}px · most closed frame {frame} · tone shift L*a*b* {tone}";
  translations["zh-CN"]["production.mouthSummary"] = "嘴型集 {set} · 闭嘴来源 {from} · 遮罩 {width}×{height}px · 跟踪 {mean}（最小 {min}）· 移动 {span}px · 最闭嘴帧 {frame} · 色调偏移 L*a*b* {tone}";
  translations.en["production.status.head"] = "head";
  translations["zh-CN"]["production.status.head"] = "开头";
  translations.en["production.status.tail"] = "tail";
  translations["zh-CN"]["production.status.tail"] = "结尾";
  translations.en["production.status.wrap"] = "wrap";
  translations["zh-CN"]["production.status.wrap"] = "循环衔接";
  translations.en["production.status.none"] = "none";
  translations["zh-CN"]["production.status.none"] = "无";
  translations.en["production.action.generate"] = "generate";
  translations["zh-CN"]["production.action.generate"] = "生成";
  translations.en["production.action.render"] = "render";
  translations["zh-CN"]["production.action.render"] = "渲染";
  translations.en["production.action.adopt"] = "adopt";
  translations["zh-CN"]["production.action.adopt"] = "提取帧";
  translations.en["production.action.resume"] = "resume";
  translations["zh-CN"]["production.action.resume"] = "继续下载";
  translations.en["production.kind.pose"] = "pose";
  translations["zh-CN"]["production.kind.pose"] = "姿态";
  translations.en["production.kind.clip"] = "clip";
  translations["zh-CN"]["production.kind.clip"] = "片段";
  translations.en["production.wireFrame"] = "frame {index}";
  translations["zh-CN"]["production.wireFrame"] = "第 {index} 帧";
  translations.en["production.qaStatus"] = "QA {status}";
  translations["zh-CN"]["production.qaStatus"] = "QA {status}";
  translations.en["production.configured"] = "Configured";
  translations["zh-CN"]["production.configured"] = "已配置";
  for (const [language, entries] of Object.entries(translations)) {
    const guide = window.SFProductionGuide[language === "zh-CN" ? "zh" : "en"];
    for (const key of ["title", "intro", "wires", "note", "close", "other"]) entries[`production.guide.${key}`] = guide[key];
    guide.steps.forEach(([title, body], index) => {
      entries[`production.guide.step${index}.title`] = title;
      entries[`production.guide.step${index}.body`] = body;
    });
    window.SFStudio.addTranslations(language, entries);
  }

  function mountProduction(ctx, tab) {
    const root = ctx.h("div", { id: tab === "prompts" ? "promptList" : "jobList", class: "production-tool" });
    ctx.root.replaceChildren(root);
    const runtime = window.SFProduction.create(ctx);
    runtime.mount(tab);
    return { cleanup: () => runtime.dispose(), update: (next) => runtime.update(next) };
  }

  function mountCanvas(ctx) {
    const { h, t } = ctx;
    const tr = (key) => t(`production.${key}`);
    const legend = (kind, key) => {
      const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("width", "30"); svg.setAttribute("height", "8"); svg.setAttribute("aria-hidden", "true");
      const path = document.createElementNS(svg.namespaceURI, "path");
      path.setAttribute("d", "M0 4H30"); path.setAttribute("class", `wire ${kind}`);
      svg.append(path);
      return h("span", { class: "legend" }, svg, h("span", { "data-canvas-label": key }, tr(key)));
    };
    ctx.root.replaceChildren(h("section", { class: "canvas-tab production-tool", "aria-label": tr("canvasTitle") },
      h("h1", { class: "sr-only", "data-canvas-label": "canvasTitle" }, tr("canvasTitle")),
      h("div", { class: "canvas-bar" },
        h("button", { id: "canvasFit", "data-canvas-label": "fit" }, tr("fit")),
        h("button", { id: "canvasLayout", title: tr("autoLayoutHint"), "data-canvas-label": "autoLayout" }, tr("autoLayout")),
        h("button", { id: "canvasAddPose", "data-canvas-label": "addPose" }, tr("addPose")),
        h("button", { id: "canvasGuideBtn", "aria-pressed": "false", "data-canvas-label": "guide" }, tr("guide")),
        legend("end", "wireStill"), legend("open", "wireFirst"), legend("adopted", "wireAdopted"),
        h("span", { class: "tiny", "data-canvas-label": "canvasHelp" }, tr("canvasHelp"))),
      h("div", { class: "canvas-wrap" },
        h("div", { id: "canvasViewport", class: "canvas-viewport" },
          h("div", { id: "canvasWorld", class: "canvas-world" }),
          h("div", { id: "canvasGuide", class: "guide", hidden: true })),
        h("aside", { id: "canvasInspector", class: "inspector", hidden: true }))));
    const wires = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    wires.setAttribute("id", "canvasWires"); wires.setAttribute("class", "canvas-wires");
    wires.setAttribute("width", "1"); wires.setAttribute("height", "1");
    ctx.root.querySelector("#canvasWorld").append(wires);
    const runtime = window.SFProduction.create(ctx);
    runtime.mount("canvas");
    return { cleanup: () => runtime.dispose(), update(next) {
      next.root.querySelectorAll("[data-canvas-label]").forEach((el) => { el.textContent = next.t(`production.${el.dataset.canvasLabel}`); });
      next.root.querySelector(".canvas-tab").setAttribute("aria-label", next.t("production.canvasTitle"));
      next.root.querySelector("#canvasLayout").title = next.t("production.autoLayoutHint");
      runtime.update(next);
    } };
  }

  function mountSettings(ctx) {
    let fields = null;
    let baselines = null;
    let renderedLanguage = window.SFStudio.language;
    function render(next) {
    const drafts = fields ? Object.fromEntries(Object.entries(fields).filter(([key, el]) => el.value !== baselines[key]).map(([key, el]) => [key, el.value])) : {};
    ctx = next;
    renderedLanguage = window.SFStudio.language;
    const { h, t, state } = ctx;
    const tr = (key) => t(`production.${key}`);
    const tools = state.tools;
    const providers = tools.providers;
    const status = (ready, kind = "ready") => h("span", { class: `badge ${ready ? "pass" : "fail"}` },
      tr(ready ? kind : kind === "configured" ? "notConfigured" : "notReady"));
    const defaults = tools.defaults || {};
    const names = Object.keys(providers).filter((name) => providers[name].kind === "image");
    const providerSelect = (key) => {
      const select = h("select", { id: `settings-${key}`, disabled: !names.length }, names.map((name) => h("option", { value: name }, name)));
      select.value = defaults[key] || names[0] || "";
      return select;
    };
    const concept = providerSelect("conceptProvider");
    const still = providerSelect("stillProvider");
    const threshold = h("input", { id: "settings-batchConfirmThreshold", type: "number", min: 1, step: 1, required: true, value: defaults.batchConfirmThreshold ?? 3 });
    const save = h("button", { class: "primary", disabled: !names.length }, tr("saveDefaults"));
    save.onclick = () => {
      if (!threshold.reportValidity()) return;
      ctx.run(() => ctx.api("/api/production/tools-settings", { defaults: {
        conceptProvider: concept.value, stillProvider: still.value, batchConfirmThreshold: Number(threshold.value),
      } }), tr("defaultsSaved"), save);
    };
    const language = h("div", { class: "row", role: "group", "aria-label": tr("language") },
      ...[["en", "EN"], ["zh-CN", "中文"]].map(([value, label]) => h("button", {
        "aria-pressed": String(window.SFStudio.language === value), onclick: () => window.SFStudio.setLanguage(value),
      }, label)));
    ctx.root.replaceChildren(h("div", { class: "production-tool settings-tool" },
      h("h3", {}, tr("language")), language,
      h("h3", {}, tr("providers")),
      ...Object.entries(providers).map(([name, provider]) => h("div", { class: "card item" },
        h("div", { class: "row" }, h("strong", {}, name), status(provider.keySet)),
        provider.model ? h("div", { class: "tiny mono" }, provider.model) : null)),
      h("h3", {}, tr("processors")),
      h("div", { class: "card row" }, ...["ffmpeg", "alpha", "interpolate"].map((name) => h("span", { class: "row" }, h("strong", {}, name), status(tools[name], name === "ffmpeg" ? "ready" : "configured")))),
      h("h3", {}, tr("defaults")),
      h("div", { class: "form" }, h("label", {}, tr("defaultConcept"), concept), h("label", {}, tr("defaultStill"), still),
        h("label", {}, tr("batchThreshold"), threshold)),
      h("p", { class: "tiny" }, tr("batchThresholdHint")),
      names.length ? null : h("p", { class: "muted" }, tr("noImageProviders")), save,
      h("h3", {}, tr("amadeusDir")),
      h("p", { class: "mono" }, tools.amadeus && tools.amadeus.packDir || tr("notConfigured")),
      h("p", { class: "tiny" }, tr("readOnly"))));
    fields = { conceptProvider: concept, stillProvider: still, batchConfirmThreshold: threshold };
    baselines = Object.fromEntries(Object.entries(fields).map(([key, el]) => [key, el.value]));
    for (const [key, value] of Object.entries(drafts)) fields[key].value = value;
    }
    render(ctx);
    return { cleanup() {}, update(next) {
      if (next.state !== ctx.state || renderedLanguage !== window.SFStudio.language) render(next);
    } };
  }

  window.SFStudio.registerTool("canvas", mountCanvas);
  window.SFStudio.registerTool("prompts", (ctx) => mountProduction(ctx, "prompts"));
  window.SFStudio.registerTool("jobs", (ctx) => mountProduction(ctx, "jobs"));
  window.SFStudio.registerTool("settings", mountSettings);
})();
