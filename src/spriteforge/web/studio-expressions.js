"use strict";
(() => {
  const strings = {
    en: {
      "expressions.title":"Expressions", "expressions.steps":"Production steps", "expressions.concepts":"Concepts", "expressions.finals":"Final stills", "expressions.clips":"Clips", "expressions.conceptCount":"{cells} cells · {picked} picked", "expressions.finalCount":"{approved} / {total} approved", "expressions.clipHint":"Starts from approved stills only", "expressions.plan":"Plan clips for approved stills", "expressions.base":"Base", "expressions.baseHint":"Final stills are edited from this approved image. Dashed lines mark its head top and centre.", "expressions.noBase":"Import and approve the base still before generating concepts or expressions.", "expressions.history":"Concept sheets", "expressions.current":"current", "expressions.historical":"Historical sheet · read-only except picks", "expressions.pickedCount":"{count} picked", "expressions.sheet":"Concept sheet", "expressions.sheetSize":"1 image · {width} × {height} · {cells} cells", "expressions.cellSize":"{width} × {height}", "expressions.noSheets":"No concept sheets yet. Create or import a sheet, or work on a final still directly.", "expressions.newSheet":"New sheet · 1 image", "expressions.newExpression":"New expression", "expressions.conceptHint":"Concepts are drafts for choosing expressions. Pick a cell, then make a formal still from the approved base. A concept never becomes an approved still directly.", "expressions.draft":"draft", "expressions.picked":"picked", "expressions.approved":"approved", "expressions.attemptStatus":"final still #{number}", "expressions.unassigned":"unassigned", "expressions.selectCell":"Select cell {number}: {pose}", "expressions.assign":"Assign expression", "expressions.choosePose":"Choose expression", "expressions.conceptTab":"Concept", "expressions.finalTab":"Final still", "expressions.description":"Current expression subject prompt", "expressions.savePrompt":"Save as new prompt version", "expressions.promptSaved":"Expression prompt saved", "expressions.reroll":"Re-roll this cell · 1 image · {cost}", "expressions.provider":"Image provider", "expressions.cost.planQuota":"plan quota", "expressions.cost.metered":"pay-as-you-go", "expressions.cost.credits":"credits", "expressions.cost.paid":"paid generation", "expressions.cost.free":"free", "expressions.noProvider":"No image provider is configured.", "expressions.providerNotReady":"Configure this provider in Settings before generating.", "expressions.referenceUnsupported":"This provider does not support a concept reference. Try without the concept.", "expressions.makeStill":"Make final still · 1 image · {cost}", "expressions.tryAgain":"Try again · 1 image · {cost}", "expressions.withoutConcept":"Try without the concept · 1 image · {cost}", "expressions.batch":"Make final stills for {count} picked", "expressions.batchTitle":"Generate formal stills", "expressions.batchCount":"{count} requests · {cost} · one image per expression", "expressions.batchConfirm":"Generate {count} images · {cost}", "expressions.batchSecond":"Confirm {count} image requests ({cost})?", "expressions.batchPartial":"{submitted} of {total} requests were submitted.", "expressions.started":"Image job started", "expressions.batchStarted":"{count} image jobs submitted", "expressions.promptNext":"Prompt for the next attempt", "expressions.generateTitle":"Generate a formal still", "expressions.generateConfirm":"Generate once · 1 image · {cost}", "expressions.generateHint":"The approved base is the geometry reference. Provider output dimensions may differ; the candidate is normalized and checked by still QA.", "expressions.referenceHint":"Concept cell {number} supplies the expression reference.", "expressions.import":"Import image", "expressions.importBase":"Import base image", "expressions.importTitle":"Import a still candidate", "expressions.imageFile":"Image file", "expressions.note":"Note (optional)", "expressions.importConfirm":"Import · free", "expressions.imported":"Still candidate imported", "expressions.prepare":"Prepare inputs", "expressions.prepareTitle":"Still editor inputs", "expressions.prepareHint":"Use base.png and the current prompt in your image editor, then import its result as a candidate.", "expressions.downloadPrompt":"Download prompt.txt", "expressions.downloadNegative":"Download negative.txt", "expressions.copyPrompt":"Copy prompt", "expressions.copied":"Prompt copied", "expressions.copyFailed":"Select the prompt and copy manually.", "expressions.attempt":"Attempt #{number}", "expressions.noAttempts":"No formal still attempts yet.", "expressions.sourceSize":"Source {width} × {height} → canvas {canvasWidth} × {canvasHeight}", "expressions.normalization":"Normalization: {method}", "expressions.sourceConcept":"Concept cell {number} · sheet {sheet}", "expressions.sourceClip":"Frame {frame} from {clip}", "expressions.sourceImport":"Imported image", "expressions.sourceProvider":"{provider} · {model}", "expressions.promptVersion":"prompt v{version}", "expressions.metrics":"Head top Δ {top} px · head centre Δ {center} px · area Δ {area}%", "expressions.qa":"QA {status}", "expressions.conceptView":"With concept", "expressions.baseView":"Overlay with base", "expressions.approve":"Approve as the {pose} still", "expressions.approvedToast":"Approved the {pose} still", "expressions.approveTitle":"Review and approve the still", "expressions.watchHint":"QA requests visual review. Compare this normalized candidate with the approved base before approving it.", "expressions.watchConfirm":"I reviewed the framing and intended expression against the base.", "expressions.watchReason":"Framing reviewed and confirmed by the user", "expressions.reject":"Reject & archive", "expressions.rejectTitle":"Reject this attempt", "expressions.reason":"Reason", "expressions.rejected":"Attempt archived", "expressions.restore":"Restore attempt", "expressions.restored":"Attempt restored", "expressions.offset":"Head offset", "expressions.offsetHint":"Expected positions in normalized canvas pixels. Blank fields use the base anchors.", "expressions.headTop":"Expected head top (px)", "expressions.headCenter":"Expected head centre (px)", "expressions.saveOffset":"Save expected positions", "expressions.offsetSaved":"Expected positions saved; candidate QA refreshed", "expressions.strip":"Consistency strip", "expressions.stripHint":"{approved} / {total} approved · aligned on head top", "expressions.sideBySide":"Side by side", "expressions.overlay":"Overlay", "expressions.openEditor":"Open material editor", "expressions.cancel":"Cancel", "expressions.confirm":"Confirm", "expressions.create":"Create", "expressions.id":"Expression id", "expressions.newDescription":"Description for a new expression (required)", "expressions.idHint":"Use a unique id of 1–64 lowercase letters, digits, _ or -.", "expressions.descriptionRequired":"A new expression needs an explicit description.", "expressions.created":"Expression {pose} created", "expressions.grid":"Grid", "expressions.sheetImport":"Import image", "expressions.sheetConfirm":"Create sheet · 1 image · {cost}", "expressions.sheetImported":"Concept sheet imported", "expressions.sheetStarted":"Concept sheet generation started", "expressions.sheetPoses":"Enter expressions in cell order. Empty rows remain unassigned cells.", "expressions.tooMany":"Choose 1–{count} unique expressions.", "expressions.baseRequired":"Approve the base still first.", "expressions.assignTitle":"Assign this concept cell", "expressions.assignmentSaved":"Cell assignment saved", "expressions.historicalHint":"This sheet is historical. Picks remain editable; assignment and re-roll are locked.", "expressions.planTitle":"Plan missing clips", "expressions.planHint":"This creates clip records only. It does not generate or spend provider quota.", "expressions.planConfirm":"Create {count} clip records · free", "expressions.planEmpty":"All approved poses already have their planned clip types.", "expressions.planned":"Clip records created", "expressions.stillReady":"Formal still ready", "expressions.jobRunning":"A job is running for this expression.", "expressions.failed":"Failed: {error}", "expressions.recheck":"Re-check against the current base", "expressions.unavailable":"Select an expression to inspect its concept or formal still.", "expressions.negative":"Negative prompt"
    },
    "zh-CN": {
      "expressions.title":"表情", "expressions.steps":"生产步骤", "expressions.concepts":"概念阵列", "expressions.finals":"正式静帧", "expressions.clips":"片段", "expressions.conceptCount":"{cells} 格 · 已选 {picked} 格", "expressions.finalCount":"{approved} / {total} 已批准", "expressions.clipHint":"只从已批准静帧开始", "expressions.plan":"为已批准静帧规划片段", "expressions.base":"基准", "expressions.baseHint":"正式静帧由此已批准图像编辑而来。虚线表示头顶和头部中心。", "expressions.noBase":"生成概念和表情前，请先导入并批准基准静帧。", "expressions.history":"概念阵列", "expressions.current":"当前", "expressions.historical":"历史阵列 · 仅勾选可修改", "expressions.pickedCount":"已选 {count} 格", "expressions.sheet":"概念阵列", "expressions.sheetSize":"1 张图 · {width} × {height} · {cells} 格", "expressions.cellSize":"{width} × {height}", "expressions.noSheets":"尚无概念阵列。请创建或导入阵列，也可以直接制作正式静帧。", "expressions.newSheet":"新建阵列 · 1 张图", "expressions.newExpression":"新建表情", "expressions.conceptHint":"概念格是挑选表情的草稿。勾选后，再由已批准基准制作正式静帧。概念不会直接成为已批准静帧。", "expressions.draft":"草稿", "expressions.picked":"已选", "expressions.approved":"已批准", "expressions.attemptStatus":"正式静帧 #{number}", "expressions.unassigned":"未分配", "expressions.selectCell":"选择第 {number} 格：{pose}", "expressions.assign":"分配表情", "expressions.choosePose":"选择表情", "expressions.conceptTab":"概念", "expressions.finalTab":"正式静帧", "expressions.description":"当前表情主题 prompt", "expressions.savePrompt":"保存为新 prompt 版本", "expressions.promptSaved":"表情 prompt 已保存", "expressions.reroll":"重画此格 · 1 张图 · {cost}", "expressions.provider":"图像服务商", "expressions.cost.planQuota":"会员额度", "expressions.cost.metered":"按量计费", "expressions.cost.credits":"credits", "expressions.cost.paid":"付费生成", "expressions.cost.free":"免费", "expressions.noProvider":"尚未配置图像服务商。", "expressions.providerNotReady":"生成前请在设置中配置此服务商。", "expressions.referenceUnsupported":"此服务商不支持概念参考图，请不带概念图尝试。", "expressions.makeStill":"制作正式静帧 · 1 张图 · {cost}", "expressions.tryAgain":"再试一次 · 1 张图 · {cost}", "expressions.withoutConcept":"不带概念图尝试 · 1 张图 · {cost}", "expressions.batch":"为 {count} 个已选表情制作正式静帧", "expressions.batchTitle":"生成正式静帧", "expressions.batchCount":"{count} 次请求 · {cost} · 每个表情一张图", "expressions.batchConfirm":"生成 {count} 张图 · {cost}", "expressions.batchSecond":"确认提交 {count} 次图像请求（{cost}）？", "expressions.batchPartial":"已提交 {submitted} / {total} 次请求。", "expressions.started":"图像任务已开始", "expressions.batchStarted":"已提交 {count} 个图像任务", "expressions.promptNext":"下一次尝试的 prompt", "expressions.generateTitle":"生成正式静帧", "expressions.generateConfirm":"生成一次 · 1 张图 · {cost}", "expressions.generateHint":"已批准基准是几何参考。服务商返回尺寸可以不同；候选图会经过归一化和静帧 QA。", "expressions.referenceHint":"第 {number} 个概念格提供表情参考。", "expressions.import":"导入图像", "expressions.importBase":"导入基准图像", "expressions.importTitle":"导入静帧候选", "expressions.imageFile":"图像文件", "expressions.note":"备注（可选）", "expressions.importConfirm":"导入 · 免费", "expressions.imported":"静帧候选已导入", "expressions.prepare":"准备输入", "expressions.prepareTitle":"静帧编辑器输入", "expressions.prepareHint":"在图像编辑器中使用 base.png 和当前 prompt，再导入结果作为候选。", "expressions.downloadPrompt":"下载 prompt.txt", "expressions.downloadNegative":"下载 negative.txt", "expressions.copyPrompt":"复制 prompt", "expressions.copied":"prompt 已复制", "expressions.copyFailed":"请选中 prompt 后手动复制。", "expressions.attempt":"尝试 #{number}", "expressions.noAttempts":"尚无正式静帧尝试。", "expressions.sourceSize":"原图 {width} × {height} → 画布 {canvasWidth} × {canvasHeight}", "expressions.normalization":"归一化：{method}", "expressions.sourceConcept":"概念格 {number} · 阵列 {sheet}", "expressions.sourceClip":"{clip} 的第 {frame} 帧", "expressions.sourceImport":"导入图像", "expressions.sourceProvider":"{provider} · {model}", "expressions.promptVersion":"prompt v{version}", "expressions.metrics":"头顶 Δ {top} px · 头部中心 Δ {center} px · 面积 Δ {area}%", "expressions.qa":"QA：{status}", "expressions.conceptView":"与概念并排", "expressions.baseView":"与基准叠加", "expressions.approve":"批准为 {pose} 静帧", "expressions.approvedToast":"已批准 {pose} 静帧", "expressions.approveTitle":"审阅并批准静帧", "expressions.watchHint":"QA 需要目视检查。批准前，请将此归一化候选与已批准基准对照。", "expressions.watchConfirm":"我已对照基准检查构图和预期表情。", "expressions.watchReason":"用户已检查并确认构图", "expressions.reject":"弃用并归档", "expressions.rejectTitle":"弃用此尝试", "expressions.reason":"原因", "expressions.rejected":"尝试已归档", "expressions.restore":"恢复尝试", "expressions.restored":"尝试已恢复", "expressions.offset":"头部偏移", "expressions.offsetHint":"归一化画布中的预期像素位置。留空时使用基准锚点。", "expressions.headTop":"预期头顶位置（px）", "expressions.headCenter":"预期头部中心（px）", "expressions.saveOffset":"保存预期位置", "expressions.offsetSaved":"预期位置已保存，候选 QA 已刷新", "expressions.strip":"一致性条带", "expressions.stripHint":"{approved} / {total} 已批准 · 按头顶线对齐", "expressions.sideBySide":"并排", "expressions.overlay":"叠加", "expressions.openEditor":"打开素材编辑", "expressions.cancel":"取消", "expressions.confirm":"确认", "expressions.create":"创建", "expressions.id":"表情 id", "expressions.newDescription":"新表情描述（必填）", "expressions.idHint":"使用未占用的 1–64 个小写字母、数字、_ 或 -。", "expressions.descriptionRequired":"新表情必须由用户填写描述。", "expressions.created":"已创建表情 {pose}", "expressions.grid":"网格", "expressions.sheetImport":"导入图像", "expressions.sheetConfirm":"创建阵列 · 1 张图 · {cost}", "expressions.sheetImported":"概念阵列已导入", "expressions.sheetStarted":"概念阵列生成已开始", "expressions.sheetPoses":"按格子顺序填写表情。留空的行会成为未分配格。", "expressions.tooMany":"请选择 1–{count} 个不重复的表情。", "expressions.baseRequired":"请先批准基准静帧。", "expressions.assignTitle":"分配此概念格", "expressions.assignmentSaved":"格子分配已保存", "expressions.historicalHint":"此阵列已归档为历史。可修改勾选，不能重新分配或重画。", "expressions.planTitle":"规划缺失片段", "expressions.planHint":"此操作只创建片段记录，不生成，也不消耗服务商额度。", "expressions.planConfirm":"创建 {count} 个片段记录 · 免费", "expressions.planEmpty":"所有已批准姿态都已有规划的片段类型。", "expressions.planned":"片段记录已创建", "expressions.stillReady":"正式静帧已就绪", "expressions.jobRunning":"此表情有任务正在运行。", "expressions.failed":"失败：{error}", "expressions.recheck":"对照当前基准重新检查", "expressions.unavailable":"选择表情以检查概念或正式静帧。", "expressions.negative":"负面 prompt"
    }
  };
  for(const [lang,entries] of Object.entries(strings))window.SFStudio.addTranslations(lang,entries);
  const media=(path)=>"/api/production/media?path="+encodeURIComponent(path);
  const views=new Map();

  function mountExpressions(initial) {
    let ctx=initial;const {h}=initial;const tr=(key,values)=>ctx.t("expressions."+key,values);
    let selectedPose=ctx.route.id||null;let selectedSheet=null;let pendingSheet=null;let selectedCell=null;let selectedTake=null;let tab="final";let compareView="concept";let stripOverlay=false;
    let provider=ctx.state.tools.defaults?.stillProvider||"";let conceptProvider=ctx.state.tools.defaults?.conceptProvider||"";
    let previewRuntime=null;let dialog=null;let dialogRefresh=null;let disposed=false;const drafts=new Map();const offsetDrafts=new Map();const comparePreferences=new Map();
    const remembered=views.get(selectedPose);if(remembered){selectedSheet=remembered.sheet;selectedCell=remembered.cell;tab=remembered.tab;}
    const root=h("section",{class:"expression-studio","aria-label":tr("title")});
    const heading=h("h1",{class:"sr-only"},tr("title"));const steps=h("ol",{class:"expression-steps","aria-label":tr("steps")});
    const baseRoot=h("section",{class:"card expression-base"});const conceptRoot=h("section",{class:"card expression-concepts"});
    const detailHead=h("div",{class:"expression-detail-head"});const detailBody=h("div",{class:"expression-detail-body"});const detailActions=h("div",{class:"expression-detail-actions"});
    const detailRoot=h("section",{class:"card expression-detail"},detailHead,detailBody,detailActions);const stripRoot=h("section",{class:"card expression-consistency"});
    root.append(heading,steps,baseRoot,conceptRoot,detailRoot,stripRoot);ctx.root.replaceChildren(root);
    const badge=(text,level="")=>h("span",{class:"badge "+level},text);
    const action=(key,fn,attrs={},values={})=>h("button",{type:"button","data-expression-action":key,...attrs,onclick:fn},tr(key,values));
    const poses=()=>ctx.state.poses;
    const pose=()=>poses().find((item)=>item.id===selectedPose);
    const base=()=>poses().find((item)=>item.id===ctx.state.character.basePose);
    const sheet=()=>ctx.state.concepts.find((item)=>item.id===selectedSheet);
    const cell=()=>sheet()?.cells.find((item)=>item.index===selectedCell);
    const take=()=>pose()?.takes.find((item)=>item.id===selectedTake);
    const approved=(item)=>item?.takes.find((candidate)=>candidate.id===item.acceptedTake);
    const stillUrl=(owner,candidate)=>candidate?.media?.still?media(`production/poses/${owner.id}/takes/${candidate.id}/${candidate.media.still}`):null;
    const cellUrl=(record,item)=>media(`production/concepts/${record.id}/${item.file}`);
    const providerInfo=(name)=>ctx.state.tools.providers[name];
    const cost=(name)=>tr("cost."+(providerInfo(name)?.costType||"paid"));
    const imageProviders=()=>Object.entries(ctx.state.tools.providers).filter(([,info])=>info.kind==="image");
    const runningPose=(id)=>ctx.jobs.some((job)=>job.status==="running"&&job.kind==="pose"&&job.owner===id);
    const promptEntry=(item)=>ctx.state.prompts.blocks[item.prompt.subject]?.versions.at(-1);
    const description=(item)=>drafts.get(item.id)??promptEntry(item)?.text??"";
    const reference=()=>cell()?.pose===selectedPose&&cell().picked?{sheet:selectedSheet,cell:selectedCell}:null;
    const canGenerate=(name)=>!!approved(base())&&!!providerInfo(name)?.keySet;
    const hint=(name)=>!approved(base())?tr("baseRequired"):!providerInfo(name)?.keySet?tr("providerNotReady"):pose()&&runningPose(pose().id)?tr("jobRunning"):"";
    const providerSelect=(name,onchange)=>{
      const select=h("select",{"aria-label":tr("provider"),onchange:(event)=>onchange(event.target.value)},imageProviders().map(([id])=>h("option",{value:id},id)));
      select.value=name;if(!select.value&&select.options.length){select.value=select.options[0].value;onchange(select.value);}return select;
    };

    function choosePose(id,cellIndex=selectedCell) {
      selectedPose=id;selectedCell=cellIndex;selectedTake=null;
      views.set(id,{sheet:selectedSheet,cell:selectedCell,tab});
      if(ctx.route.id!==id){ctx.navigate("#/expressions/"+encodeURIComponent(id));return;}
      paint();
    }
    function guideLines(owner,candidate) {
      const metrics=candidate?.qa?.metrics;const anchors=ctx.state.character.anchors;if(!anchors)return [];
      const canvas=ctx.state.character.canvas;const expected={...anchors,...(owner?.expected||{})};
      return [h("span",{class:"expression-guide-y",style:`top:${100*expected.headTopY/canvas.height}%`}),h("span",{class:"expression-guide-x",style:`left:${100*expected.headCenterX/canvas.width}%`})];
    }
    function renderSteps() {
      const current=sheet();const picked=current?.cells.filter((item)=>item.picked).length||0;
      const workflowQuery=new URLSearchParams({template:tab==="concept"?"concept-still":"final-still",pose:pose()?.id||ctx.state.character.basePose});
      if(tab!=="concept"&&current&&cell()){workflowQuery.set("sheet",current.id);workflowQuery.set("cell",cell().index);}
      steps.replaceChildren(...[["concepts",tr("conceptCount",{cells:current?.cells.length||0,picked})],["finals",tr("finalCount",{approved:poses().filter((item)=>item.acceptedTake).length,total:poses().length})],["clips",tr("clipHint")]].map(([key,summary],index)=>h("li",{class:"expression-step"+((tab==="concept"?index===0:index===1)?" on":"")},h("strong",{},`${index+1} · ${tr(key)}`),h("span",{class:"tiny"},summary))),
        h("li",{class:"row"},action("plan",openPlan),h("a",{class:"btn",href:"#/workflows?"+workflowQuery,"data-open-workflow":"pose"},ctx.t("shell.openWorkflow"))));
    }
    function renderBase() {
      const owner=base(),candidate=approved(owner);const url=stillUrl(owner,candidate);
      baseRoot.replaceChildren(h("div",{class:"card-heading"},h("h2",{class:"h3"},tr("base")),candidate?badge(ctx.t("status.approved",{version:candidate.version}),"pass"):null),
        url?h("div",{class:"checker expression-base-image"},h("img",{src:url,alt:owner.id}),guideLines(owner,candidate)):h("p",{class:"tiny"},tr("noBase")),
        h("p",{class:"tiny",style:"margin:0"},tr("baseHint")),action("importBase",()=>openImport(owner)),h("h3",{},tr("history")),
        ...[...ctx.state.concepts].reverse().map((record,index)=>h("button",{type:"button",class:"item expression-history"+(record.id===selectedSheet?" active":""),"data-sheet":record.id,"aria-pressed":String(record.id===selectedSheet),onclick:()=>{pendingSheet=null;selectedSheet=record.id;selectedCell=record.cells.find((item)=>item.pose===selectedPose)?.index??record.cells[0]?.index??null;paint();}},
          h("span",{},`#${ctx.state.concepts.length-index} · ${record.grid.cols} × ${record.grid.rows}`),record.current?badge(tr("current"),"info"):record.state!=="ready"?badge(ctx.t(record.state==="failed"?"production.status.failed":"status.generating"),record.state==="failed"?"fail":"info"):h("span",{class:"tiny"},tr("pickedCount",{count:record.cells.filter((item)=>item.picked).length})))));
    }
    function pendingPicked() {
      const map=new Map();for(const item of sheet()?.cells||[]){const owner=poses().find((entry)=>entry.id===item.pose);if(item.picked&&owner&&!owner.acceptedTake)map.set(owner.id,item);}return [...map.values()];
    }
    function renderConcepts() {
      const record=sheet();const ready=record?.state==="ready"&&record.size;const can=!!approved(base());
      const header=h("div",{class:"expression-concepts-header"},h("h2",{class:"h3"},tr("sheet")),ready?h("span",{class:"tiny"},tr("sheetSize",{width:record.size.w,height:record.size.h,cells:record.cells.length})):record?badge(ctx.t(record.state==="failed"?"production.status.failed":"status.generating"),record.state==="failed"?"fail":"info"):null,h("div",{class:"spacer"}),action("newSheet",openSheet,{class:"small",disabled:!can,title:!can?tr("baseRequired"):null}),action("newExpression",()=>openNewExpression(),{class:"small"}));
      const nodes=[header];
      if(ready){
        if(!record.current)nodes.push(h("p",{class:"tiny"},tr("historicalHint")));
        if(record.error)nodes.push(h("p",{class:"tiny"},tr("failed",{error:record.error})));
        const grid=h("div",{class:"expression-grid",style:`grid-template-columns:repeat(${record.grid.cols},minmax(0,1fr))`});
        for(const item of record.cells){
          const owner=poses().find((entry)=>entry.id===item.pose);const latest=owner?.takes.at(-1);const status=owner?.acceptedTake?tr("approved"):latest?.state==="ready"?tr("attemptStatus",{number:latest.version}):item.picked?tr("picked"):tr("draft");
          const checkbox=h("input",{type:"checkbox",checked:item.picked,disabled:!owner,"data-cell-pick":String(item.index),onchange:(event)=>ctx.run(()=>ctx.api("/api/production/concept-cell",{sheet:record.id,cell:item.index,picked:event.target.checked}),null,event.target)});
          grid.append(h("div",{class:"expression-cell"+(item.index===selectedCell?" on":""),"data-concept-cell":String(item.index)},h("button",{type:"button",class:"expression-cell-select","aria-label":tr("selectCell",{number:item.index+1,pose:item.pose||tr("unassigned")}),"aria-pressed":String(item.index===selectedCell),onclick:()=>{selectedCell=item.index;if(item.pose){tab="concept";choosePose(item.pose,item.index);}else{paint();}}},h("img",{src:cellUrl(record,item),alt:"",loading:"lazy"})),
            h("div",{class:"row"},h("label",{},checkbox,item.pose||tr("unassigned")),badge(status,owner?.acceptedTake?"pass":item.picked?"info":"")),item.size?h("span",{class:"tiny mono"},tr("cellSize",{width:item.size.w,height:item.size.h})):null,
            action("assign",()=>openAssign(record,item),{class:"small",disabled:!record.current})));
        }
        nodes.push(grid,h("p",{class:"tiny",style:"margin:0"},tr("conceptHint")),action("batch",openBatch,{disabled:!pendingPicked().length||!providerInfo(provider)?.supportsReference,title:!providerInfo(provider)?.supportsReference?tr("referenceUnsupported"):null},{count:pendingPicked().length}));
      }else if(record?.error)nodes.push(h("p",{class:"tiny"},tr("failed",{error:record.error})));
      else if(!record)nodes.push(h("p",{class:"tiny"},tr("noSheets")));
      conceptRoot.replaceChildren(...nodes);
    }

    function renderDetail() {
      const oldMode=detailBody.querySelector("#compareMode");const oldOpacity=detailBody.querySelector("#compareOpacity");
      if(oldMode&&oldOpacity)comparePreferences.set(selectedPose,{mode:oldMode.selectedIndex,opacity:oldOpacity.value});
      if(previewRuntime){previewRuntime.dispose();previewRuntime=null;}
      const owner=pose();
      const choose=h("select",{"aria-label":tr("choosePose"),"data-pose-select":"pose",onchange:(event)=>{tab="final";choosePose(event.target.value);}},poses().map((item)=>h("option",{value:item.id},item.id)));choose.value=owner?.id||"";
      detailHead.replaceChildren(owner?h("h2",{},owner.id):h("h2",{},tr("title")),choose,h("div",{class:"tabs",role:"group","aria-label":tr("steps")},["concept","final"].map((key)=>h("button",{type:"button",class:tab===key?"active":"","data-expression-tab":key,"aria-pressed":String(tab===key),onclick:()=>{tab=key;paint();}},tr(key==="concept"?"conceptTab":"finalTab")))));
      detailBody.replaceChildren();detailActions.replaceChildren();if(!owner){detailBody.append(h("p",{class:"tiny"},tr("unavailable")));return;}
      if(tab==="concept")renderConceptDetail(owner);else renderFinalDetail(owner);
      const preference=comparePreferences.get(owner.id);if(preference){const mode=detailBody.querySelector("#compareMode");const opacity=detailBody.querySelector("#compareOpacity");if(mode)mode.selectedIndex=preference.mode;if(opacity)opacity.value=preference.opacity;}
    }
    function promptEditor(owner,key="description") {
      const input=h("textarea",{"data-expression-draft":"prompt",value:description(owner),oninput:(event)=>drafts.set(owner.id,event.target.value)});
      return h("div",{class:"expression-description"},h("label",{class:"tiny"},tr(key),input));
    }
    function renderConceptDetail(owner) {
      const record=sheet(),item=cell();
      if(record&&item){detailBody.append(h("img",{class:"thumb",src:cellUrl(record,item),alt:owner.id,style:"width:100%;max-height:220px;object-fit:contain"}));if(!record.current)detailBody.append(h("p",{class:"tiny"},tr("historicalHint")));}
      detailBody.append(promptEditor(owner),providerSelect(conceptProvider,(value)=>{conceptProvider=value;renderDetail();}));
      detailActions.append(action("savePrompt",(event)=>savePrompt(owner,event.currentTarget),{disabled:!!record&&!record.current}));
      if(record&&item&&item.pose)detailActions.append(action("reroll",()=>openReroll(record,item),{disabled:!record.current||!canGenerate(conceptProvider),title:hint(conceptProvider)||null},{cost:cost(conceptProvider)}));
    }
    function sourceLabel(candidate) {
      const source=candidate.source||{};
      if(source.concept)return tr("sourceConcept",{number:source.concept.cell+1,sheet:source.concept.sheet});
      if(source.provider==="clip")return tr("sourceClip",{frame:source.frame,clip:source.clip});
      if(source.provider==="manual")return tr("sourceImport");
      return tr("sourceProvider",{provider:source.provider||"",model:source.model||""});
    }
    function metricsLabel(owner,candidate) {
      const metrics=candidate.qa?.metrics;const anchors=ctx.state.character.anchors;if(!metrics||!anchors)return "";
      const expected={...anchors,...owner.expected};const number=(value)=>typeof value==="number"?Number(value.toFixed(2)):"—";
      return tr("metrics",{top:number(metrics.headTopY-expected.headTopY),center:number(metrics.headCenterX-expected.headCenterX),area:anchors.area?number(100*(metrics.area/anchors.area-1)):"—"});
    }
    function renderFinalDetail(owner) {
      const candidate=take();const local={...ctx,root:detailBody};previewRuntime=window.SFProduction.create(local);
      if(owner.needsRecheck)detailBody.append(h("p",{class:"tiny"},tr("recheck")));
      if(candidate?.media?.still){
        detailBody.append(h("div",{class:"card-heading"},h("span",{class:"tiny"},tr("attempt",{number:candidate.version})),badge(tr("qa",{status:ctx.t("production.status."+candidate.qa?.status)}),candidate.qa?.status)),h("p",{class:"tiny"},sourceLabel(candidate)));
        const record=sheet(),item=cell();
        if(record&&item&&item.pose===owner.id)detailBody.append(h("div",{class:"tabs",role:"group","aria-label":tr("finalTab")},["concept","base"].map((view)=>h("button",{type:"button",class:compareView===view?"active":"","data-still-view":view,"aria-pressed":String(compareView===view),onclick:()=>{compareView=view;renderDetail();}},tr(view==="concept"?"conceptView":"baseView")))));
        if(compareView==="concept"&&record&&item&&item.pose===owner.id)detailBody.append(h("div",{class:"expression-side-by-side"},h("div",{class:"concept-reference"},h("span",{class:"tiny"},tr("conceptTab")),h("img",{src:cellUrl(record,item),alt:owner.id})),
          h("div",{},h("span",{class:"tiny"},tr("finalTab")),h("div",{class:"checker expression-still-view"},h("img",{src:stillUrl(owner,candidate),alt:owner.id}),guideLines(owner,candidate)))),previewRuntime.poseMetrics(owner,candidate.qa?.metrics||{}));
        else detailBody.append(previewRuntime.poseCompare(owner,candidate));
        if(candidate.media.source){const label=h("p",{class:"tiny expression-source-size"});const image=h("img",{src:media(`production/poses/${owner.id}/takes/${candidate.id}/${candidate.media.source}`),alt:"",hidden:true,onload:(event)=>{label.textContent=tr("sourceSize",{width:event.target.naturalWidth,height:event.target.naturalHeight,canvasWidth:ctx.state.character.canvas.width,canvasHeight:ctx.state.character.canvas.height});}});detailBody.append(label,image);}
        detailBody.append(h("p",{class:"tiny"},tr("normalization",{method:candidate.normalization?.method||"—"})));
        if(compareView==="concept"&&candidate.qa?.checks?.length)detailBody.append(h("details",{open:candidate.qa.status==="fail"},h("summary",{},tr("qa",{status:ctx.t("production.status."+candidate.qa.status)})),candidate.qa.checks.map((check)=>h("p",{class:"tiny"},badge(ctx.t("production.status."+check.level),check.level)," ",check.message))));
      }else detailBody.append(h("p",{class:"tiny"},candidate?.error?tr("failed",{error:candidate.error}):tr("noAttempts")));
      detailBody.append(h("div",{class:"expression-attempts"},[...owner.takes].reverse().map((attempt)=>h("button",{type:"button",class:"expression-attempt"+(attempt.id===selectedTake?" on":""),"data-attempt":String(attempt.version),"data-pose-take":attempt.id,"aria-pressed":String(attempt.id===selectedTake),onclick:()=>{selectedTake=attempt.id;renderDetail();}},
        h("span",{class:"row"},h("b",{class:"mono"},`#${attempt.version}`),badge(ctx.t("production.status."+(attempt.qa?.status||attempt.state)),attempt.qa?.status||"")),h("span",{class:"tiny"},metricsLabel(owner,attempt)),h("span",{class:"tiny"},sourceLabel(attempt)),h("span",{class:"tiny"},tr("normalization",{method:attempt.normalization?.method||"—"})),attempt.prompt?.blocks?.[owner.prompt.subject]?h("span",{class:"tiny"},tr("promptVersion",{version:attempt.prompt.blocks[owner.prompt.subject]})):null))));
      if(owner.id!==ctx.state.character.basePose){
        detailBody.append(promptEditor(owner,"promptNext"),providerSelect(provider,(value)=>{provider=value;renderDetail();}));
        if(reference()&&!providerInfo(provider)?.supportsReference)detailBody.append(h("p",{class:"tiny"},tr("referenceUnsupported")));
        renderOffset(owner);
      }
      detailBody.append(h("div",{class:"expression-closed-mouth"},previewRuntime.closedMouth(owner)));
      if(candidate?.state==="ready"){
        if(candidate.status==="rejected")detailActions.append(action("restore",(event)=>decision(owner,candidate,"restore","",event.currentTarget)));
        else detailActions.append(action("approve",()=>approve(owner,candidate),{class:"primary",disabled:candidate.qa?.status==="fail"||candidate.status==="accepted"&&!owner.needsRecheck},{pose:owner.id}),action("reject",()=>openReject(owner,candidate)));
      }
      if(owner.id!==ctx.state.character.basePose){
        if(reference()&&providerInfo(provider)?.supportsReference)detailActions.append(action(owner.takes.length?"tryAgain":"makeStill",()=>openGenerate(owner,true),{disabled:!!hint(provider),title:hint(provider)||null},{cost:cost(provider)}));
        detailActions.append(action("withoutConcept",()=>openGenerate(owner,false),{disabled:!!hint(provider),title:hint(provider)||null},{cost:cost(provider)}));
      }
      detailActions.append(action("import",()=>openImport(owner)));
      if(owner.id!==ctx.state.character.basePose)detailActions.append(action("prepare",()=>openPrepare(owner),{disabled:!approved(base())}));
      if(owner.acceptedTake)detailActions.append(action("openEditor",()=>ctx.setMode("edit")));
    }
    function renderOffset(owner) {
      const draft=offsetDrafts.get(owner.id);const top=h("input",{type:"number",step:"any",value:draft?.top??owner.expected?.headTopY??"","data-expected":"headTopY"});
      const center=h("input",{type:"number",step:"any",value:draft?.center??owner.expected?.headCenterX??"","data-expected":"headCenterX"});
      const section=h("details",{class:"expression-offset",open:draft?.open});
      top.addEventListener("input",()=>offsetDrafts.set(owner.id,{...offsetDrafts.get(owner.id),top:top.value}));
      center.addEventListener("input",()=>offsetDrafts.set(owner.id,{...offsetDrafts.get(owner.id),center:center.value}));
      section.addEventListener("toggle",()=>{if(section.isConnected)offsetDrafts.set(owner.id,{...offsetDrafts.get(owner.id),open:section.open});});
      section.append(h("summary",{},tr("offset")),h("p",{class:"tiny"},tr("offsetHint")),h("div",{class:"form"},h("label",{},tr("headTop"),top),h("label",{},tr("headCenter"),center)),action("saveOffset",async(event)=>{
        if(!top.reportValidity()||!center.reportValidity())return;const result=await ctx.run(()=>ctx.api("/api/production/pose-expect",{pose:owner.id,headTopY:top.value===""?null:Number(top.value),headCenterX:center.value===""?null:Number(center.value)}),tr("offsetSaved"),event.currentTarget);if(result)offsetDrafts.delete(owner.id);
      }));detailBody.append(section);
    }
    function renderStrip() {
      const baseTake=approved(base());const count=poses().filter((item)=>item.acceptedTake).length;
      const items=h("div",{class:"expression-consistency-items"});
      for(const owner of poses()){
        const candidate=approved(owner),url=stillUrl(owner,candidate);const top=candidate?.qa?.metrics?.headTopY??ctx.state.character.anchors?.headTopY;const baseTop=ctx.state.character.anchors?.headTopY;
        const shift=typeof top==="number"&&typeof baseTop==="number"?73*(baseTop-top)/ctx.state.character.canvas.height:0;
        items.append(h("button",{type:"button",class:"expression-strip-pose checker"+(!url?" missing":""),"aria-label":owner.id,"data-strip-pose":owner.id,onclick:()=>{tab="final";choosePose(owner.id);}},url?h("img",{src:url,alt:"",style:`transform:translateY(${shift}px)`}):owner.id,stripOverlay&&url&&baseTake&&owner.id!==base().id?h("img",{class:"strip-base",src:stillUrl(base(),baseTake),alt:""}):null));
      }
      stripRoot.replaceChildren(h("div",{class:"expression-consistency-title"},h("h3",{},tr("strip")),h("span",{class:"tiny"},tr("stripHint",{approved:count,total:poses().length}))),items,h("div",{class:"tabs",role:"group","aria-label":tr("strip")},[false,true].map((value)=>h("button",{type:"button",class:stripOverlay===value?"active":"","aria-pressed":String(stripOverlay===value),onclick:()=>{stripOverlay=value;renderStrip();}},tr(value?"overlay":"sideBySide")))));
    }

    async function savePrompt(owner,button) {const text=description(owner);const result=await ctx.run(()=>ctx.api("/api/production/prompt",{block:owner.prompt.subject,text}),tr("promptSaved"),button);if(result)drafts.delete(owner.id);}
    function decision(owner,candidate,which,reason,button){return ctx.run(()=>ctx.api("/api/production/decision",{kind:"pose",owner:owner.id,take:candidate.id,action:which,reason}),tr(which==="accept"?"approvedToast":which==="reject"?"rejected":"restored",{pose:owner.id}),button);}
    function approve(owner,candidate){
      if(candidate.qa?.status==="fail")return;
      if(candidate.qa?.status!=="watch"){decision(owner,candidate,"accept","",detailActions.querySelector('[data-expression-action="approve"]'));return;}
      const view=modal("approveTitle");if(!view)return;
      const checked=h("input",{type:"checkbox",required:true,"data-expression-field":"watch-confirm"});view.insert(view.hint("watchHint"),view.label("watchConfirm",checked,{class:"inline-check"}));
      view.submit("approve",async()=>{await ctx.api("/api/production/decision",{kind:"pose",owner:owner.id,take:candidate.id,action:"accept",reason:tr("watchReason")});await ctx.refresh();ctx.toast(tr("approvedToast",{pose:owner.id}));},{pose:owner.id});view.show();
    }

    function modal(titleKey) {
      if(dialog)return null;
      const el=h("dialog",{class:"expression-dialog","data-expression-dialog":titleKey});const form=h("form");const title=h("h2");const error=h("output",{role:"alert"});const cancel=action("cancel",()=>el.close());const buttons=h("div",{class:"dialog-actions"},cancel);const labels=[];
      form.append(title,error,buttons);el.append(form);root.append(el);dialog=el;el.addEventListener("keydown",(event)=>{if(event.key==="Escape")event.stopPropagation();});
      const values=(input)=>typeof input==="function"?input():input;
      const label=(key,input,attrs={})=>{const text=h("span");labels.push(()=>text.textContent=tr(key));return h("label",attrs,text,input);};
      const hint=(key,data={})=>{const p=h("p",{class:"dialog-hint"});labels.push(()=>p.textContent=tr(key,values(data)));return p;};
      const refresh=()=>{title.textContent=tr(titleKey);cancel.textContent=tr("cancel");labels.forEach((fn)=>fn());};dialogRefresh=refresh;
      el.addEventListener("close",()=>{if(dialog===el){dialog=null;dialogRefresh=null;}el.remove();},{once:true});
      const submit=(key,fn,data={})=>{
        const button=h("button",{type:"submit",class:"primary","data-expression-submit":titleKey});labels.push(()=>button.textContent=tr(key,values(data)));buttons.append(button);let busy=false;
        el.addEventListener("cancel",(event)=>{if(busy)event.preventDefault();});
        form.addEventListener("submit",async(event)=>{event.preventDefault();if(busy||!form.reportValidity())return;busy=true;error.textContent="";button.disabled=cancel.disabled=true;const fields=[...form.querySelectorAll("input,textarea,select")].map((field)=>[field,field.disabled]);fields.forEach(([field])=>{field.disabled=true;});
          try{await fn();if(!disposed&&el.open)el.close();}catch(failure){error.textContent=String(failure.message||failure);}finally{busy=false;if(el.isConnected){button.disabled=cancel.disabled=false;fields.forEach(([field,disabled])=>{field.disabled=disabled||field.dataset.requestSubmitted==="true";});}}
        });return button;
      };
      return {el,form,label,hint,submit,insert:(...nodes)=>buttons.before(...nodes),show:()=>{refresh();el.showModal();form.querySelector("input:not(:disabled),textarea,select")?.focus();}};
    }
    function expressionFields(view,defaultId="",defaultDescription="") {
      const id=h("input",{required:true,pattern:"[a-z0-9][a-z0-9_-]{0,63}",maxlength:64,value:defaultId,"data-expression-field":"id"});
      const text=h("textarea",{value:defaultDescription,"data-expression-field":"description"});
      view.insert(view.label("id",id),view.hint("idHint"),view.label("newDescription",text));return {id,text};
    }
    async function ensureExpression(id,text) {
      if(poses().some((item)=>item.id===id))return;
      if(!text.trim())throw new Error(tr("descriptionRequired"));
      await ctx.api("/api/production/pose",{id,description:text.trim()});await ctx.api("/api/production/prompt",{block:`pose.${id}`,text:text.trim()});
    }
    function openNewExpression() {
      const view=modal("newExpression");if(!view)return;const fields=expressionFields(view);fields.text.required=true;
      view.submit("create",async()=>{if(poses().some((item)=>item.id===fields.id.value))throw new Error(tr("idHint"));await ensureExpression(fields.id.value,fields.text.value);await ctx.refresh();ctx.navigate("#/expressions/"+encodeURIComponent(fields.id.value));ctx.toast(tr("created",{pose:fields.id.value}));});view.show();
    }
    function openAssign(record,item) {
      if(!record.current)return;const view=modal("assignTitle");if(!view)return;const fields=expressionFields(view,item.pose||"");
      view.submit("confirm",async()=>{await ensureExpression(fields.id.value,fields.text.value);await ctx.api("/api/production/concept-cell",{sheet:record.id,cell:item.index,pose:fields.id.value});await ctx.refresh();ctx.toast(tr("assignmentSaved"));});view.show();
    }
    function openSheet() {
      const view=modal("newSheet");if(!view)return;
      const grid=h("select",{"data-expression-field":"grid"},h("option",{value:"3x2"},"3 × 2"),h("option",{value:"2x2"},"2 × 2"));
      const select=providerSelect(conceptProvider,(value)=>{if(providerInfo(value))conceptProvider=value;});select.dataset.expressionField="provider";select.append(h("option",{value:"import"},tr("sheetImport")));
      const file=h("input",{type:"file",accept:"image/png,image/jpeg,image/webp",disabled:true,"data-expression-field":"file"});
      const rows=[];const rowsRoot=h("div",{class:"stack"});const pending=poses().filter((item)=>!item.acceptedTake&&item.id!==base().id);
      for(let index=0;index<6;index++){
        const id=h("input",{pattern:"[a-z0-9][a-z0-9_-]{0,63}",maxlength:64,value:pending[index]?.id||"","data-sheet-pose":String(index)});
        const text=h("input",{type:"text",value:"","data-sheet-description":String(index)});
        const row=h("div",{class:"expression-sheet-row"},h("span",{class:"mono"},String(index+1)),view.label("id",id),view.label("newDescription",text));rows.push({id,text,row});rowsRoot.append(row);
      }
      const sync=()=>{const count=grid.value==="3x2"?6:4;rows.forEach((row,index)=>{row.row.hidden=index>=count;row.id.disabled=row.text.disabled=index>=count;});file.disabled=select.value!=="import";file.required=!file.disabled;};grid.addEventListener("change",sync);select.addEventListener("change",sync);sync();
      view.insert(h("div",{class:"row"},view.label("grid",grid),view.label("provider",select)),view.label("imageFile",file),view.hint("sheetPoses"),rowsRoot);
      view.submit("sheetConfirm",async()=>{
        const selected=rows.filter((row)=>!row.row.hidden&&row.id.value.trim()).map((row)=>({id:row.id.value.trim(),description:row.text.value}));const capacity=grid.value==="3x2"?6:4;
        if(!selected.length||selected.length>capacity||new Set(selected.map((row)=>row.id)).size!==selected.length)throw new Error(tr("tooMany",{count:capacity}));
        for(const item of selected)if(!poses().some((owner)=>owner.id===item.id)&&!item.description.trim())throw new Error(tr("descriptionRequired"));
        for(const item of selected)await ensureExpression(item.id,item.description);
        if(select.value==="import"){
          const image=file.files[0];const query=new URLSearchParams({name:image.name,grid:grid.value,poses:selected.map((item)=>item.id).join(",")});const response=await fetch("/api/production/concepts/import?"+query,{method:"POST",headers:{"Content-Type":"application/octet-stream"},body:image});const data=await response.json();if(!response.ok||!data.ok)throw new Error(data.error||response.statusText);selectedSheet=data.sheet.id;selectedCell=data.sheet.cells[0]?.index??null;
        }else {const data=await ctx.api("/api/production/concepts",{poses:selected.map((item)=>item.id),grid:grid.value,provider:select.value});pendingSheet=data.job.sheet;}
        await ctx.refresh();ctx.toast(tr(select.value==="import"?"sheetImported":"sheetStarted"));
      },()=>({cost:select.value==="import"?tr("cost.free"):cost(select.value)}));view.show();
    }
    function openReroll(record,item) {
      if(record.state!=="ready"||!record.current||!canGenerate(conceptProvider))return;const view=modal("concepts");if(!view)return;const owner=poses().find((entry)=>entry.id===item.pose);const text=h("textarea",{value:description(owner),"data-expression-field":"prompt"});
      view.insert(view.label("description",text));view.submit("reroll",async()=>{if(promptEntry(owner)?.text!==text.value)await ctx.api("/api/production/prompt",{block:owner.prompt.subject,text:text.value});await ctx.api("/api/production/jobs",{action:"concept-reroll",sheet:record.id,cell:item.index,provider:conceptProvider});drafts.delete(owner.id);await ctx.refresh();ctx.toast(tr("started"));},{cost:cost(conceptProvider)});view.show();
    }
    function openGenerate(owner,useConcept) {
      if(hint(provider))return;const view=modal("generateTitle");if(!view)return;const ref=useConcept?reference():null;const text=h("textarea",{required:true,value:description(owner),"data-expression-field":"prompt"});
      view.insert(view.hint("generateHint"),ref?view.hint("referenceHint",{number:ref.cell+1}):h("span"),view.label("promptNext",text));view.submit("generateConfirm",async()=>{if(promptEntry(owner)?.text!==text.value)await ctx.api("/api/production/prompt",{block:owner.prompt.subject,text:text.value});await ctx.api("/api/production/jobs",{action:"generate",pose:owner.id,provider,...(ref?{concept:ref}:{})});drafts.delete(owner.id);await ctx.refresh();ctx.toast(tr("started"));},{cost:cost(provider)});view.show();
    }
    function openBatch() {
      const candidates=pendingPicked();if(!candidates.length)return;const view=modal("batchTitle");if(!view)return;
      const select=providerSelect(provider,(value)=>{provider=value;});const rows=candidates.map((item)=>({item,input:h("input",{type:"checkbox",checked:true})}));const count=()=>rows.filter((row)=>row.input.checked).length;
      rows.forEach((row)=>{row.label=h("label",{class:"inline-check"},row.input,row.item.pose);});
      view.insert(view.label("provider",select),view.hint("batchCount",()=>({count:count(),cost:cost(select.value)})),...rows.map((row)=>row.label));
      rows.forEach((row)=>row.input.addEventListener("change",()=>dialogRefresh?.()));select.addEventListener("change",()=>dialogRefresh?.());
      view.submit("batchConfirm",async()=>{
        const selected=rows.filter((row)=>row.input.checked);if(!selected.length)throw new Error(tr("tooMany",{count:rows.length}));if(!canGenerate(select.value))throw new Error(hint(select.value));if(!providerInfo(select.value)?.supportsReference)throw new Error(tr("referenceUnsupported"));
        const threshold=ctx.state.tools.defaults?.batchConfirmThreshold??3;if(selected.length>threshold&&!window.confirm(tr("batchSecond",{count:selected.length,cost:cost(select.value)})))throw new Error(tr("cancel"));
        let submitted=0;try{for(const row of selected){await ctx.api("/api/production/jobs",{action:"generate",pose:row.item.pose,provider:select.value,concept:{sheet:selectedSheet,cell:row.item.index}});submitted++;row.input.checked=false;row.input.dataset.requestSubmitted="true";row.label.append(badge(ctx.t("production.status.submitted"),"info"));}}catch(error){throw new Error(tr("batchPartial",{submitted,total:selected.length})+"\n"+String(error.message||error));}finally{await ctx.refresh();}ctx.toast(tr("batchStarted",{count:submitted}));
      },()=>({count:count(),cost:cost(select.value)}));view.show();
    }
    function openImport(owner) {
      const view=modal("importTitle");if(!view)return;const file=h("input",{type:"file",accept:"image/png,image/jpeg,image/webp",required:true,"data-expression-field":"file"});const note=h("textarea",{"data-expression-field":"note"});view.insert(view.hint("generateHint"),view.label("imageFile",file),view.label("note",note));
      view.submit("importConfirm",async()=>{const image=file.files[0];const query=new URLSearchParams({kind:"pose",owner:owner.id,name:image.name,note:note.value});const response=await fetch("/api/production/upload?"+query,{method:"POST",headers:{"Content-Type":"application/octet-stream"},body:image});const data=await response.json();if(!response.ok||!data.ok)throw new Error(data.error||response.statusText);selectedPose=owner.id;selectedTake=data.take.id;tab="final";await ctx.refresh();ctx.toast(tr("imported"));});view.show();
    }
    function openPrepare(owner) {
      const view=modal("prepareTitle");if(!view)return;const urls=[];const download=(name,text,key)=>{const url=URL.createObjectURL(new Blob([text],{type:"text/plain;charset=utf-8"}));urls.push(url);return h("a",{class:"btn",href:url,download:name},tr(key));};const preview=owner.promptPreview;
      view.insert(view.hint("prepareHint"),h("div",{class:"row"},h("a",{class:"btn",href:`/api/production/input?pose=${encodeURIComponent(owner.id)}`,download:"base.png"},"base.png"),download("prompt.txt",preview.text||"","downloadPrompt"),download("negative.txt",preview.negative||"","downloadNegative")),h("pre",{},preview.text||preview.error||""));view.el.addEventListener("close",()=>urls.forEach((url)=>URL.revokeObjectURL(url)),{once:true});view.show();
    }
    function openReject(owner,candidate) {
      const view=modal("rejectTitle");if(!view)return;const reason=h("textarea",{"data-expression-field":"reason"});view.insert(view.label("reason",reason));view.submit("confirm",async()=>{await ctx.api("/api/production/decision",{kind:"pose",owner:owner.id,take:candidate.id,action:"reject",reason:reason.value});await ctx.refresh();ctx.toast(tr("rejected"));});view.show();
    }
    function openPlan() {
      const view=modal("planTitle");if(!view)return;const baseId=ctx.state.character.basePose;const planned=[];
      for(const owner of poses().filter((item)=>item.acceptedTake)){
        const types=owner.id===baseId?["loop"]:["in","loop","out"];
        for(const type of types){const exists=ctx.state.clips.some((clip)=>type==="loop"?clip.kind==="loop"&&clip.from===owner.id&&clip.to===owner.id&&!clip.mouth:type==="in"?clip.kind==="transition"&&clip.to===owner.id:clip.kind==="transition"&&clip.from===owner.id);if(exists)continue;
          const checkbox=h("input",{type:"checkbox",checked:true});const id=h("input",{required:true,pattern:"[a-z0-9][a-z0-9_-]{0,63}",maxlength:64,value:`${owner.id}_${type}`,"data-plan-id":`${owner.id}:${type}`});const record={from:type==="in"?baseId:owner.id,to:type==="out"?baseId:owner.id,phase:type};planned.push({record,checkbox,id,owner,type});
        }
      }
      const count=()=>planned.filter((row)=>row.checkbox.checked).length;view.insert(view.hint("planHint"),...(planned.length?planned.map((row)=>h("div",{class:"expression-plan-row"},row.checkbox,h("span",{class:"mono"},`${row.record.from} → ${row.record.to} · ${row.type}`),row.id)):[view.hint("planEmpty")]));planned.forEach((row)=>row.checkbox.addEventListener("change",()=>{row.id.disabled=!row.checkbox.checked;dialogRefresh?.();}));
      view.submit("planConfirm",async()=>{const chosen=planned.filter((row)=>row.checkbox.checked);if(!chosen.length)throw new Error(tr("planEmpty"));await ctx.api("/api/production/plan-clips",{clips:chosen.map((row)=>({id:row.id.value,...row.record}))});await ctx.refresh();ctx.toast(tr("planned"));},()=>({count:count()}));view.show();
    }

    function paint() {
      const focused=document.activeElement;const focusKey=focused instanceof HTMLTextAreaElement&&root.contains(focused)?focused.dataset.expressionDraft:null;const expectedKey=focused instanceof HTMLInputElement&&root.contains(focused)?focused.dataset.expected:null;const selection=focusKey?[focused.selectionStart,focused.selectionEnd]:null;
      heading.textContent=tr("title");root.setAttribute("aria-label",tr("title"));
      if(!poses().some((item)=>item.id===selectedPose))selectedPose=poses().find((item)=>item.id!==ctx.state.character.basePose&&!item.acceptedTake)?.id||base()?.id||poses()[0]?.id;
      const requested=ctx.state.concepts.find((item)=>item.id===pendingSheet);
      if(requested?.state==="ready"){selectedSheet=requested.id;selectedCell=requested.cells.find((item)=>item.pose===selectedPose)?.index??requested.cells[0]?.index??null;pendingSheet=null;}
      else if(requested?.state==="failed")pendingSheet=null;
      if(!ctx.state.concepts.some((item)=>item.id===selectedSheet))selectedSheet=ctx.state.concepts.find((item)=>item.current)?.id||ctx.state.concepts.at(-1)?.id||null;
      const current=sheet();if(!current?.cells.some((item)=>item.index===selectedCell))selectedCell=current?.cells.find((item)=>item.pose===selectedPose)?.index??current?.cells[0]?.index??null;
      const owner=pose();if(owner&&!owner.takes.some((item)=>item.id===selectedTake))selectedTake=[...owner.takes].reverse().find((item)=>item.needsReview)?.id||owner.acceptedTake||owner.takes.at(-1)?.id||null;
      renderSteps();renderBase();renderConcepts();renderDetail();renderStrip();if(dialogRefresh)dialogRefresh();
      if(focusKey){const field=root.querySelector(`[data-expression-draft="${focusKey}"]`);field?.focus({preventScroll:true});if(field&&selection)field.setSelectionRange(...selection);}
      else if(expectedKey)root.querySelector(`[data-expected="${expectedKey}"]`)?.focus({preventScroll:true});
    }
    paint();
    return {update:(next)=>{ctx=next;paint();},cleanup:()=>{disposed=true;previewRuntime?.dispose();if(dialog){dialog.close();dialog.remove();}}};
  }
  window.SFStudio.register("expressions",mountExpressions);
})();
