"use strict";
(() => {
  const strings={
    en:{
      "export.title":"Export the {character} pack", "export.version":"Version", "export.installedPath":"Installed pack for comparison: {path}", "export.checks":"Export check", "export.checkHint":"Recomputed whenever this page opens", "export.loading":"Checking export readiness…", "export.failed":"Could not load export checks", "export.retry":"Refresh checks", "export.start":"Start export · free", "export.starting":"Export job started", "export.blocked":"Fix {count} blocking issues first.", "export.fix":"Fix", "export.progress":"Progress", "export.graph":"Open graph", "export.settings":"Settings", "export.level.pass":"pass", "export.level.watch":"note", "export.level.fix":"fix", "export.level.fail":"blocks", "export.level.info":"info", "export.check.qa":"QA blocking", "export.detail.qa":"{count} QA issues block this export.", "export.check.poses":"Unfinished expressions", "export.detail.poses":"Approved poses without graph-bound clips stay out of this export: {poses}", "export.detail.posesEmpty":"All approved poses are represented in the graph.", "export.check.mouth":"Mouth overlays", "export.detail.mouth":"{count} speaking loops checked. Missing or invalid: {missing}", "export.detail.mouthPass":"All {count} speaking loops have closed-mouth overlays and tracks.", "export.check.canvas":"Canvas size is written", "export.detail.canvas":"{width} × {height}; frame padding preserves the character's scale.", "export.check.encoding":"Encoding", "export.detail.encoding":"UASTC level {uastc} · zstd {zstd}", "export.check.labels":"New labels", "export.detail.labels":"New labels compared with the installed pack: {labels}", "export.detail.labelsEmpty":"No new labels compared with the installed pack.", "export.detail.labelsUnknown":"Configure an installed pack in Settings to compare labels.", "export.check.duration":"Export estimate", "export.detail.duration":"{frames} frames · about {hours} h based on recorded exports", "export.detail.frames":"{frames} frames; no measured duration history is available.", "export.check.generic":"Check {id}", "export.againstInstalled":"Against the installed pack", "export.noInstalled":"No installed pack is configured. Export still writes only to this workspace.", "export.added":"added", "export.updated":"updated", "export.removed":"removed", "export.unknown":"Awaiting encoding or comparison unavailable", "export.unknownHint":"Source PNG and installed texture hashes are different representations. These entries cannot be called updated before a valid comparison.", "export.notes":"Release notes", "export.notesHint":"Drafted from the recorded differences; edit as you like.", "export.log":"Export log", "export.noLog":"No exports have been recorded yet.", "export.installed":"installed", "export.historyFacts":"{frames} frames · {seconds} s", "export.unknownDuration":"{frames} frames · duration unrecorded", "export.output":"Output: {path}", "export.workspaceOnly":"Exports create a new package in this workspace. SpriteForge does not install it or start Amadeus.", "export.job":"Export job", "export.viewJobs":"View jobs", "export.running":"running", "export.complete":"complete", "export.jobFailed":"failed", "export.noChanges":"No comparable differences were found.", "export.empty":"—"
    },
    "zh-CN":{
      "export.title":"导出 {character} 角色包", "export.version":"版本", "export.installedPath":"用于对比的已装包：{path}", "export.checks":"导出检查", "export.checkHint":"每次打开此页都重新计算", "export.loading":"正在检查导出条件…", "export.failed":"无法加载导出检查", "export.retry":"刷新检查", "export.start":"开始导出 · 免费", "export.starting":"导出任务已开始", "export.blocked":"请先修复 {count} 个阻塞问题。", "export.fix":"修复", "export.progress":"进度", "export.graph":"打开行为图", "export.settings":"设置", "export.level.pass":"通过", "export.level.watch":"提示", "export.level.fix":"需修复", "export.level.fail":"阻塞", "export.level.info":"信息", "export.check.qa":"QA 阻塞问题", "export.detail.qa":"{count} 个 QA 问题阻塞此导出。", "export.check.poses":"未完成的表情", "export.detail.poses":"下列已批准姿态没有绑定到行为图的片段，不会进入此导出：{poses}", "export.detail.posesEmpty":"所有已批准姿态都已在行为图中使用。", "export.check.mouth":"嘴型叠加", "export.detail.mouth":"已检查 {count} 个说话循环。缺失或无效：{missing}", "export.detail.mouthPass":"全部 {count} 个说话循环都有闭嘴叠加和轨迹。", "export.check.canvas":"写入画布尺寸", "export.detail.canvas":"{width} × {height}；帧留边会保留角色比例。", "export.check.encoding":"编码", "export.detail.encoding":"UASTC level {uastc} · zstd {zstd}", "export.check.labels":"新增标签", "export.detail.labels":"相对已装包新增的标签：{labels}", "export.detail.labelsEmpty":"相对已装包没有新增标签。", "export.detail.labelsUnknown":"请在设置中配置已装包以对比标签。", "export.check.duration":"导出估时", "export.detail.duration":"{frames} 帧 · 根据已记录导出估计约 {hours} h", "export.detail.frames":"{frames} 帧；尚无实测耗时记录。", "export.check.generic":"检查 {id}", "export.againstInstalled":"与已装包对比", "export.noInstalled":"尚未配置已装包。导出仍只写入当前工作区。", "export.added":"新增", "export.updated":"更新", "export.removed":"移除", "export.unknown":"待编码或暂时无法比较", "export.unknownHint":"源 PNG 和已装纹理的哈希来自不同表示。有效比较完成前，不能将这些条目标为更新。", "export.notes":"发布说明", "export.notesHint":"根据已记录的差异起草，可自行编辑。", "export.log":"导出记录", "export.noLog":"尚无已记录的导出。", "export.installed":"已安装", "export.historyFacts":"{frames} 帧 · {seconds} s", "export.unknownDuration":"{frames} 帧 · 耗时未记录", "export.output":"输出：{path}", "export.workspaceOnly":"导出会在当前工作区创建新包。SpriteForge 不安装角色包，也不启动 Amadeus。", "export.job":"导出任务", "export.viewJobs":"查看任务", "export.running":"运行中", "export.complete":"已完成", "export.jobFailed":"失败", "export.noChanges":"未发现可比较的差异。", "export.empty":"—"
    }
  };
  strings.en["export.encodingMissing"]="The texture encoder is unavailable. Configure toktx before exporting.";
  strings["zh-CN"]["export.encodingMissing"]="纹理编码器不可用，请先配置 toktx 再导出。";
  strings.en["export.detail.duration"]="{frames} frames · about {duration} based on recorded exports";
  strings["zh-CN"]["export.detail.duration"]="{frames} 帧 · 根据已记录导出估计约 {duration}";
  for(const [lang,entries] of Object.entries(strings))window.SFStudio.addTranslations(lang,entries);
  function mountExport(initial){
    let ctx=initial;const {h}=initial;const tr=(key,values)=>ctx.t("export."+key,values);
    let preflight=null,diff=null,error=null,disposed=false,revision=0;let versionDraft=null,notesDraft=null;let lastState=ctx.state;
    const root=h("section",{class:"export-studio"});const main=h("div",{class:"export-main"});const aside=h("aside",{class:"export-aside"});root.append(main,aside);ctx.root.replaceChildren(root);
    const badge=(label,level)=>h("span",{class:"badge "+level},label);
    const dateVersion=()=>{const now=new Date();return `${now.getFullYear()}.${String(now.getMonth()+1).padStart(2,"0")}.${String(now.getDate()).padStart(2,"0")}`;};
    function detail(check){
      const facts=check.facts||{};
      if(check.id==="qa")return tr("detail.qa",{count:facts.count});
      if(check.id==="poses")return facts.poses?.length?tr("detail.poses",{poses:facts.poses.join(", ")}):tr("detail.posesEmpty");
      if(check.id==="mouth")return facts.error|| (facts.missing?.length?tr("detail.mouth",{count:facts.count,missing:facts.missing.join(", ")}):tr("detail.mouthPass",{count:facts.count}));
      if(check.id==="canvas")return tr("detail.canvas",facts);
      if(check.id==="encoding")return (facts.ready===false?tr("encodingMissing")+" ":"")+tr("detail.encoding",facts);
      if(check.id==="labels")return !diff?.configured?tr("detail.labelsUnknown"):facts.labels?.length?tr("detail.labels",{labels:facts.labels.join(", ")}):tr("detail.labelsEmpty");
      if(check.id==="duration"){
        if(typeof facts.seconds!=="number")return tr("detail.frames",{frames:facts.frames});
        const seconds=facts.seconds;const duration=seconds>=3600?ctx.t("overview.durationHours",{hours:(seconds/3600).toFixed(1)}):seconds>=60?ctx.t("overview.durationMinutes",{minutes:(seconds/60).toFixed(1)}):ctx.t("overview.durationSeconds",{seconds:Number(seconds.toFixed(1))});
        return tr("detail.duration",{frames:facts.frames,duration});
      }
      return JSON.stringify(facts);
    }
    function destination(check){
      if(check.id==="qa")return {label:tr("fix"),hash:"#/review?mode=edit"};
      if(check.id==="poses")return {label:tr("progress"),hash:"#/overview"};
      if(check.id==="mouth")return {label:tr("graph"),hash:"#/behavior/graph"};
      if(check.id==="labels")return {label:tr("settings"),hash:"#/export?tool=settings"};
      return null;
    }
    function render(){
      const active=document.activeElement;const focused=active instanceof HTMLInputElement&&root.contains(active)?active.dataset.exportField:active instanceof HTMLTextAreaElement&&root.contains(active)?active.dataset.exportField:null;
      const selection=focused&&active instanceof HTMLTextAreaElement?[active.selectionStart,active.selectionEnd]:null;
      const version=h("input",{class:"mono",required:true,"data-export-field":"version",value:versionDraft??preflight?.suggestedVersion??dateVersion(),oninput:(event)=>{versionDraft=event.target.value;}});
      const header=h("div",{class:"export-heading"},h("div",{class:"export-heading-title"},h("h1",{},tr("title",{character:ctx.state.character.displayName})),preflight?.installed?.configured&&preflight.installed.path?h("span",{class:"tiny"},tr("installedPath",{path:preflight.installed.path})):null),h("div",{class:"spacer"}),h("label",{class:"tiny export-version-label"},tr("version"),version));
      main.replaceChildren(header);
      if(error)main.append(h("section",{class:"card export-job"},h("h2",{},tr("failed")),h("p",{class:"tiny"},error),h("button",{type:"button","data-export-action":"retry",onclick:load},tr("retry"))));
      else if(!preflight)main.append(h("p",{class:"tiny",role:"status"},tr("loading")));
      else{
        const checks=h("section",{class:"card export-checklist","aria-label":tr("checks")},h("div",{class:"export-checklist-head"},h("h2",{class:"h3"},tr("checks")),h("span",{class:"tiny"},tr("checkHint"))));
        for(const check of preflight.checks){const target=destination(check);const known=strings.en["export.check."+check.id];checks.append(h("div",{class:"export-check","data-export-check":check.id},badge(tr("level."+check.level),check.level),h("span",{class:"export-check-content"},h("span",{},known?tr("check."+check.id):tr("check.generic",{id:check.id})),h("span",{class:"tiny"},detail(check))),target?h("a",{class:"btn small",href:target.hash},target.label):h("span")));}
        const busy=ctx.jobs.some((job)=>job.status==="running"&&job.action==="export");
        const start=h("button",{type:"button",class:"primary","data-export-action":"start",disabled:preflight.blockingCount>0||busy,onclick:async(event)=>{if(!version.reportValidity())return;const name=version.value;const notes=notesDraft??diff?.draftNotes??"";await ctx.run(()=>ctx.api("/api/production/export",{version:name,notes}),tr("starting"),event.currentTarget);await load();}},tr("start"));
        main.append(checks,h("div",{class:"export-actions"},start,preflight.blockingCount?h("span",{class:"tiny"},tr("blocked",{count:preflight.blockingCount})):null,h("div",{class:"spacer"}),h("button",{type:"button","data-export-action":"retry",onclick:load},tr("retry"))),h("p",{class:"tiny"},tr("workspaceOnly")));
        const job=ctx.jobs.find((item)=>item.action==="export");
        if(job)main.append(h("section",{class:"card export-job"},h("div",{class:"card-heading"},h("h2",{class:"h3"},tr("job")),badge(ctx.t("production.status."+job.status),job.status==="failed"?"fail":job.status==="running"?"info":"pass")),job.error?h("p",{class:"tiny"},job.error):null,job.log?.length?h("pre",{},job.log.slice(-20).join("\n")):null));
      }
      renderAside();
      if(focused){const field=root.querySelector(`[data-export-field="${focused}"]`);field?.focus({preventScroll:true});if(selection&&field instanceof HTMLTextAreaElement)field.setSelectionRange(...selection);}
    }
    function renderAside(){
      const comparison=h("section",{class:"card"},h("div",{class:"card-heading"},h("h2",{class:"h3"},tr("againstInstalled")),diff?.installedVersion?h("span",{class:"tiny mono"},diff.installedVersion):null));
      if(diff?.error)comparison.append(h("p",{class:"tiny",role:"alert"},diff.error));
      if(!diff)comparison.append(h("p",{class:"tiny"},tr("loading")));
      else if(!diff.configured){if(!diff.error)comparison.append(h("p",{class:"tiny"},tr("noInstalled")));}
      else{
        if(!diff.error)comparison.append(h("div",{class:"export-diff-counts"},["added","updated","removed"].map((key)=>h("div",{class:"item"},h("b",{class:"mono","data-diff-count":key},String(diff[key].length)),h("div",{class:"tiny"},tr(key))))));
        for(const key of ["added","updated","removed"])for(const item of diff[key])comparison.append(h("div",{class:"export-diff-row"},h("span",{class:"mono"},item.label),h("span",{class:"export-diff-"+key},item.reason||tr(key))));
        if(diff.unknown?.length){
          const unknown=h("details",{open:true},h("summary",{},tr("unknown")),h("p",{class:"tiny"},tr("unknownHint")));
          for(const item of diff.unknown)unknown.append(h("div",{class:"export-diff-row","data-diff-unknown":item.label},h("span",{class:"mono"},item.label),h("span",{class:"tiny"},item.reason||tr("unknown"))));
          comparison.append(unknown);
        }
        if(!diff.error&&!diff.added.length&&!diff.updated.length&&!diff.removed.length&&!diff.unknown?.length)comparison.append(h("p",{class:"tiny"},tr("noChanges")));
      }
      const notes=h("textarea",{class:"export-notes",rows:4,"data-export-field":"notes",value:notesDraft??diff?.draftNotes??"",oninput:(event)=>{notesDraft=event.target.value;}});
      const log=h("section",{class:"card"},h("h2",{class:"h3"},tr("log")));
      for(const item of preflight?.history||[])log.append(h("div",{class:"export-log-item","data-export-version":item.version},h("div",{class:"card-heading"},h("span",{class:"mono"},item.version),item.installed?badge(tr("installed"),"pass"):null),h("div",{class:"tiny"},item.createdAt),h("div",{class:"tiny"},tr(typeof item.durationS==="number"?"historyFacts":"unknownDuration",{frames:item.frames,seconds:typeof item.durationS==="number"?Number(item.durationS.toFixed(2)):null})),h("div",{class:"tiny mono export-output"},tr("output",{path:item.output}))));
      if(!preflight?.history?.length)log.append(h("p",{class:"tiny"},tr("noLog")));
      aside.replaceChildren(comparison,h("section",{class:"card"},h("label",{class:"h3"},tr("notes"),notes),h("span",{class:"tiny"},tr("notesHint"))),log);
    }
    async function load(){
      const requested=++revision;error=null;
      try{const [next,difference]=await Promise.all([ctx.api("/api/export/preflight"),ctx.api("/api/export/diff")]);if(disposed||requested!==revision)return;preflight=next;diff=difference;render();}
      catch(failure){if(disposed||requested!==revision)return;error=String(failure.message||failure);render();}
    }
    render();load();
    return {update:(next)=>{const changed=next.state!==lastState;ctx=next;lastState=next.state;render();if(changed)load();},cleanup:()=>{disposed=true;revision++;}};
  }
  window.SFStudio.register("export",mountExport);
})();
