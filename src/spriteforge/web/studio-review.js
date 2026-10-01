"use strict";
(() => {
  const strings={en:{
    "review.title":"Review", "review.todo":"To do", "review.productionScope":"Candidate and still QA", "review.assemblyScope":"Graph assembly checks", "review.filter":"Filter issues", "review.all":"All", "review.fail":"Fail {count}", "review.fix":"Fix {count}", "review.watch":"Watch {count}", "review.group.fail":"FAIL", "review.group.fix":"FIX", "review.group.watch":"WATCH", "review.group.known":"WATCH · KNOWN", "review.level.fail":"fail", "review.level.fix":"fix", "review.level.watch":"watch", "review.blocks":"blocks export", "review.empty":"No issues in this group.", "review.noSelection":"Select an issue or start the review queue.", "review.queue":"Review queue", "review.queueCount":"{count} waiting", "review.noQueue":"No candidates are waiting for a decision.", "review.start":"Start the queue", "review.next":"Next", "review.accept":"Adopt", "review.reject":"Reject with a reason…", "review.processing":"Process and run QA · free", "review.processingStarted":"Candidate processing started", "review.qaMissing":"Processing and QA are required before adoption.", "review.qaStale":"This processed candidate is out of date. Run QA again.", "review.qaFailed":"QA failed. This candidate cannot be adopted.", "review.still":"{pose} still · attempt #{version}", "review.clip":"{clip} · v{version}", "review.recheck":"Approved still needs re-checking", "review.adopted":"Candidate adopted", "review.archived":"Candidate archived", "review.shortcut.accept":"adopt", "review.shortcut.reject":"reject", "review.shortcut.next":"next", "review.openClip":"Open clip studio", "review.openPose":"Open expression", "review.openGraph":"Open graph and player", "review.markKnown":"Mark known…", "review.clearKnown":"Clear known mark", "review.knownTitle":"Mark this watch issue known", "review.knownNote":"Note (required)", "review.knownSaved":"Watch issue marked known", "review.knownCleared":"Known mark cleared", "review.known":"Known: {note}", "review.issueRecord":"Recorded diagnostic", "review.qa":"QA {status}", "review.sourceVersion":"Recorded version v{version}", "review.seamTitle":"Seam: {from} → {to}", "review.seamLoading":"Loading the recorded seam…", "review.seamError":"Could not load this seam", "review.side":"Side by side", "review.flicker":"Flicker · 2 Hz", "review.difference":"Difference", "review.mode":"Seam comparison mode", "review.tail":"Last frame of the previous clip", "review.head":"First frame of the next clip", "review.headTop":"Head top", "review.headCenter":"Head centre", "review.faceL":"Face L*", "review.guideHint":"Dashed cyan: expected head position. Solid red: measured position.", "review.ways":"Ways to fix", "review.graphHint":"Inspect this edge in the graph, remove it if it is unintended, or return to generation to make the missing transition.", "review.generateTransition":"Open clip studio to make a transition", "review.selectEdge":"Select this edge in the graph", "review.frameUnavailable":"Frame unavailable", "review.overall":"Recorded result: {level}", "review.cancel":"Cancel", "review.confirm":"Confirm", "review.rejectTitle":"Reject this candidate", "review.reason":"Reason (required)", "review.watchTitle":"Confirm the still review", "review.watchHint":"Compare the normalized still with the approved base before adopting it.", "review.watchConfirm":"I reviewed the framing and intended expression.", "review.watchReason":"Framing reviewed and confirmed by the user", "review.error":"Could not complete this action", "review.retry":"Try again", "review.raw":"Raw candidate", "review.current":"Processed candidate · current", "review.stale":"Processed candidate · stale", "review.missing":"No processed candidate", "review.unknown":"—"
  },"zh-CN":{
    "review.title":"审阅", "review.todo":"待办", "review.productionScope":"候选素材与静帧 QA", "review.assemblyScope":"行为图组装检查", "review.filter":"筛选问题", "review.all":"全部", "review.fail":"失败 {count}", "review.fix":"需修复 {count}", "review.watch":"需关注 {count}", "review.group.fail":"失败", "review.group.fix":"需修复", "review.group.watch":"需关注", "review.group.known":"需关注 · 已知", "review.level.fail":"失败", "review.level.fix":"需修复", "review.level.watch":"需关注", "review.blocks":"阻塞导出", "review.empty":"此组没有问题。", "review.noSelection":"选择问题，或开始审阅队列。", "review.queue":"审阅队列", "review.queueCount":"{count} 个待决定", "review.noQueue":"没有等待决定的候选素材。", "review.start":"开始队列", "review.next":"下一个", "review.accept":"采纳", "review.reject":"填写原因并弃用…", "review.processing":"处理并运行 QA · 免费", "review.processingStarted":"候选素材处理已开始", "review.qaMissing":"采纳前须完成处理与 QA。", "review.qaStale":"处理后的候选已过期，请重新运行 QA。", "review.qaFailed":"QA 失败，不能采纳此候选。", "review.still":"{pose} 静帧 · 尝试 #{version}", "review.clip":"{clip} · v{version}", "review.recheck":"已批准静帧需要复查", "review.adopted":"候选已采纳", "review.archived":"候选已归档", "review.shortcut.accept":"采纳", "review.shortcut.reject":"弃用", "review.shortcut.next":"下一个", "review.openClip":"打开片段工作室", "review.openPose":"打开表情", "review.openGraph":"打开行为图与播放器", "review.markKnown":"标为已知…", "review.clearKnown":"取消已知标记", "review.knownTitle":"将此 watch 问题标为已知", "review.knownNote":"备注（必填）", "review.knownSaved":"watch 问题已标为已知", "review.knownCleared":"已知标记已取消", "review.known":"已知：{note}", "review.issueRecord":"已记录诊断", "review.qa":"QA：{status}", "review.sourceVersion":"已记录版本 v{version}", "review.seamTitle":"接缝：{from} → {to}", "review.seamLoading":"正在加载已记录接缝…", "review.seamError":"无法加载此接缝", "review.side":"并排", "review.flicker":"闪烁 · 2 Hz", "review.difference":"差异", "review.mode":"接缝对比模式", "review.tail":"前一片段的末帧", "review.head":"后一片段的首帧", "review.headTop":"头顶", "review.headCenter":"头部中心", "review.faceL":"面部 L*", "review.guideHint":"青色虚线：预期头部位置。红色实线：实测位置。", "review.ways":"修复方式", "review.graphHint":"在行为图中检查此边；若不符合预期，可移除它，或返回生成界面制作缺失过渡。", "review.generateTransition":"打开片段工作室制作过渡", "review.selectEdge":"在行为图中选中此边", "review.frameUnavailable":"帧不可用", "review.overall":"已记录结论：{level}", "review.cancel":"取消", "review.confirm":"确认", "review.rejectTitle":"弃用此候选", "review.reason":"原因（必填）", "review.watchTitle":"确认静帧审阅", "review.watchHint":"采纳前，请将归一化静帧与已批准基准对照。", "review.watchConfirm":"我已检查构图和预期表情。", "review.watchReason":"用户已检查并确认构图", "review.error":"无法完成此操作", "review.retry":"重试", "review.raw":"原始候选", "review.current":"已处理候选 · 当前", "review.stale":"已处理候选 · 过期", "review.missing":"尚无已处理候选", "review.unknown":"—"
  }};
  strings.en["review.cropHint"]="Flicker and Difference compare native pixels after removing the recorded horizontal margins.";
  strings["zh-CN"]["review.cropHint"]="闪烁和差异模式会去掉已记录的水平留边，以原生像素比较。";
  strings.en["review.published"]="Published render · {state}";
  strings["zh-CN"]["review.published"]="已发布渲染 · {state}";
  for(const [lang,entries] of Object.entries(strings))window.SFStudio.addTranslations(lang,entries);
  const media=(path)=>"/api/production/media?path="+encodeURIComponent(path);
  const frame=(path)=>"/frame?path="+encodeURIComponent(path);
  const graphLink=(key)=>"#/behavior/graph?select="+encodeURIComponent(key);
  function mountReview(initial){
    let ctx=initial;const {h}=initial;const tr=(key,values)=>ctx.t("review."+key,values);
    let filter="all",issueKey=ctx.route.id||null,queueKey=null,focusedQueue=false,disposed=false,preview=null,poseRuntime=null,seamCleanup=null,dialog=null,revision=0;
    let detailKey=null;let lastLanguage=window.SFStudio.language;let lastState=ctx.state;
    const root=h("section",{class:"review-studio","aria-label":tr("title")});const heading=h("h1",{class:"sr-only"},tr("title"));
    const inboxHead=h("div",{class:"card-heading"});const filters=h("div",{class:"tabs review-filter",role:"group"});const list=h("div",{class:"review-list"});
    const detailHead=h("div",{class:"card-heading"});const body=h("div",{class:"review-detail-body"});const actions=h("div",{class:"review-detail-actions"});
    const queueHead=h("div",{class:"card-heading"});const queueList=h("div",{class:"review-queue-list"});const queueFooter=h("div",{class:"stack"});
    const queueRoot=h("aside",{class:"card review-queue"},queueHead,queueList,queueFooter);
    root.append(heading,h("section",{class:"card review-inbox"},inboxHead,filters,list),h("section",{class:"card review-detail"},detailHead,body,actions),queueRoot);ctx.root.replaceChildren(root);
    const badge=(text,level)=>h("span",{class:"badge "+level},text);
    const button=(key,fn,attrs={})=>h("button",{type:"button","data-review-action":key,...attrs,onclick:fn},tr(key));
    const assembly=()=>ctx.mode==="edit";
    const issues=()=>ctx.state.issues.filter((item)=>assembly()?["node","edge"].includes(item.kind):["pose","clip"].includes(item.kind));
    const issue=()=>issues().find((item)=>item.key===issueKey);
    function label(item){
      if(item.kind==="edge")return tr("seamTitle",{from:item.from,to:item.to});
      const reason=item.key.split(":").at(-1);const key="issue."+item.kind+"."+reason;
      return window.SF_I18N.en[key]?ctx.t(key,item):ctx.t("issue.generic",{owner:item.clip||item.pose||item.node||item.key,check:reason});
    }
    function queue(){
      if(assembly())return [];
      const result=[];
      for(const owner of ctx.state.poses)for(const take of owner.takes){if(take.state!=="ready"||take.status==="rejected")continue;if(take.needsReview||(owner.needsRecheck&&take.id===owner.acceptedTake))result.push({key:`pose:${owner.id}:${take.id}`,kind:"pose",owner,take});}
      for(const owner of ctx.state.clips)for(const take of owner.takes){if(take.state!=="ready"||take.status==="rejected")continue;if(take.needsReview||(take.id===owner.acceptedTake&&(owner.render.state!=="current"||owner.render.qa?.status==="fail")))result.push({key:`clip:${owner.id}:${take.id}`,kind:"clip",owner,take});}
      return result;
    }
    const selectedQueue=()=>queue().find((item)=>item.key===queueKey);
    const ready=(item)=>item.kind==="pose"?!!item.take.qa&&item.take.qa.status!=="fail":item.take.candidateRender?.state==="current"&&!!item.take.candidateRender.qa&&item.take.candidateRender.qa.status!=="fail";
    const qa=(item)=>item.kind==="pose"?item.take.qa:item.take.candidateRender?.qa;
    function chooseIssue(key){focusedQueue=false;issueKey=key;ctx.navigate("#/review/"+encodeURIComponent(key)+(assembly()?"?mode=edit":""));render();}
    function chooseQueue(key){focusedQueue=true;queueKey=key;render(true);}
    function renderInbox(){
      const all=issues();inboxHead.replaceChildren(h("h2",{class:"h3"},tr("todo")," ",h("span",{class:"tiny"},String(all.length))),h("span",{class:"tiny"},tr(assembly()?"assemblyScope":"productionScope")));
      filters.setAttribute("aria-label",tr("filter"));filters.replaceChildren(...["all","fail","fix","watch"].map((key)=>h("button",{type:"button",class:filter===key?"active":"","data-review-filter":key,"aria-pressed":String(filter===key),onclick:()=>{filter=key;renderInbox();}},tr(key,{count:all.filter((item)=>item.level===key&&!item.known).length}))));
      list.replaceChildren();
      for(const group of ["fail","fix","watch","known"]){const rows=all.filter((item)=>(group==="known"?item.level==="watch"&&item.known:item.level===group&&!item.known)&&(filter==="all"||item.level===filter));if(!rows.length)continue;
        list.append(h("div",{class:"tiny review-group"},tr("group."+group)));
        for(const item of rows)list.append(h("button",{type:"button",class:"review-issue"+(!focusedQueue&&issueKey===item.key?" active":""),"data-review-issue":item.key,"aria-pressed":String(!focusedQueue&&issueKey===item.key),onclick:()=>chooseIssue(item.key)},h("span",{class:"row"},badge(tr(item.blocksExport?"blocks":"level."+item.level),item.level),h("span",{class:"review-issue-title"},label(item))),h("span",{class:"tiny review-record"},item.take?item.take:item.message||item.key),item.known?h("span",{class:"tiny"},tr("known",{note:item.known.note})):null));
      }
      if(!list.childNodes.length)list.append(h("p",{class:"tiny"},tr("empty")));
    }
    function renderQueue(){
      if(assembly()){queueRoot.hidden=true;queueHead.replaceChildren();queueList.replaceChildren();queueFooter.replaceChildren();return;}
      queueRoot.hidden=false;
      const rows=queue();queueHead.replaceChildren(h("h2",{class:"h3"},tr("queue")),h("span",{class:"tiny"},tr("queueCount",{count:rows.length})));
      queueList.replaceChildren(...rows.map((item)=>{
        const path=item.kind==="pose"?item.take.media?.still?`production/poses/${item.owner.id}/takes/${item.take.id}/${item.take.media.still}`:null:item.take.inputs?.first?.file?`production/clips/${item.owner.id}/takes/${item.take.id}/${item.take.inputs.first.file}`:null;
        const status=qa(item)?.status;return h("button",{type:"button",class:"item review-queue-entry"+(focusedQueue&&queueKey===item.key?" active":""),"data-review-queue":item.key,onclick:()=>chooseQueue(item.key)},path?h("img",{class:"thumb",src:media(path),alt:""}):null,h("span",{class:"review-queue-meta"},h("span",{class:"mono"},tr(item.kind==="pose"?"still":"clip",{pose:item.owner.id,clip:item.owner.id,version:item.take.version})),h("span",{class:"tiny"},item.kind==="pose"&&item.owner.needsRecheck?tr("recheck"):status?tr("qa",{status:ctx.t("production.status."+status)}):tr("qaMissing"))));
      }));
      if(!rows.length)queueList.append(h("p",{class:"tiny"},tr("noQueue")));
      queueFooter.replaceChildren(button("start",()=>{queueKey=rows[0]?.key||null;focusedQueue=!!queueKey;render(true);},{class:"primary review-queue-start",disabled:!rows.length}),h("div",{class:"tiny review-queue-shortcuts"},[["A","accept"],["X","reject"],["N","next"]].map(([key,name])=>h("span",{},h("kbd",{},key)," ",tr("shortcut."+name)))));
    }
    function clearPreview(){revision++;preview?.cleanup();preview=null;poseRuntime?.dispose();poseRuntime=null;seamCleanup?.();seamCleanup=null;}
    function renderDetail(force=false){
      const entry=focusedQueue?selectedQueue():null;const selected=focusedQueue?null:issue();
      const key=entry?entry.key:selected?.key||"empty";const identity=key+":"+window.SFStudio.language;
      actions.replaceChildren();
      if(!force&&detailKey===identity&&lastState===ctx.state){renderActions(entry,selected);return;}
      clearPreview();detailKey=identity;body.replaceChildren();detailHead.replaceChildren();
      if(entry){renderCandidate(entry);renderActions(entry,null);return;}
      if(!selected){body.append(h("p",{class:"tiny"},tr("noSelection")));return;}
      detailHead.append(h("h2",{},label(selected)),badge(tr(selected.blocksExport?"blocks":"level."+selected.level),selected.level));
      if(selected.kind==="edge")renderSeam(selected);
      else{
        body.append(h("h3",{},tr("issueRecord")),h("p",{class:"tiny review-record"},selected.message||selected.key));
        const owner=selected.pose?ctx.state.poses.find((item)=>item.id===selected.pose):selected.clip?ctx.state.clips.find((item)=>item.id===selected.clip):null;
        const sourceId=selected.pose?selected.take||owner?.acceptedTake:selected.candidate?selected.take:owner?.render.take;
        const candidate=owner?.takes.find((item)=>item.id===sourceId);
        if(owner&&candidate)renderCandidate({key:`${selected.pose?"pose":"clip"}:${owner.id}:${candidate.id}`,kind:selected.pose?"pose":"clip",owner,take:candidate},false,selected.candidate?"candidate":"published");
      }
      renderActions(null,selected);
    }
    function renderCandidate(item,heading=true,provenance="candidate"){
      if(heading)detailHead.append(h("h2",{},tr(item.kind==="pose"?"still":"clip",{pose:item.owner.id,clip:item.owner.id,version:item.take.version})));
      if(item.kind==="pose"){
        if(item.owner.needsRecheck)body.append(h("p",{class:"tiny"},tr("recheck")));
        poseRuntime=window.SFProduction.create({...ctx,root:body});if(item.take.media?.still)body.append(poseRuntime.poseCompare(item.owner,item.take));
      }else{
        const published=provenance==="published";const target=h("div",{class:"review-candidate-root"});body.append(target);preview=window.SFClipCompare.mount({...ctx,root:target},{clip:item.owner,takeA:item.take,takeB:published?null:item.owner.takes.find((candidate)=>candidate.id===item.owner.acceptedTake),candidatePreview:!published,useRender:published});
        const state=(published?item.owner.render:item.take.candidateRender)?.state||"missing";body.append(h("p",{class:"tiny"},published?tr("published",{state:ctx.t("production.status."+state)}):tr(state==="current"?"current":state==="stale"?"stale":"missing")));
      }
      const report=item.kind==="clip"&&provenance==="published"?item.owner.render.qa:qa(item);if(report)body.append(h("section",{class:"review-production-qa"},h("h3",{},tr("qa",{status:ctx.t("production.status."+report.status)})),(report.checks||[]).map((check)=>h("p",{class:"tiny"},badge(ctx.t("production.status."+check.level),check.level)," ",check.message))));
    }
    function renderActions(entry,selected){
      if(entry){
        const why=entry.kind==="clip"?entry.take.candidateRender?.state!=="current"?tr(entry.take.candidateRender?.state==="stale"?"qaStale":"qaMissing"):qa(entry)?.status==="fail"?tr("qaFailed"):"":qa(entry)?.status==="fail"?tr("qaFailed"):"";
        actions.append(button("accept",()=>adopt(entry),{class:"primary",disabled:!ready(entry),title:why||null}),button("reject",()=>reject(entry)),button("next",advance));
        if(entry.kind==="clip")actions.append(button("processing",(event)=>ctx.run(()=>ctx.api("/api/production/jobs",{action:"render-take",clip:entry.owner.id,take:entry.take.id}),tr("processingStarted"),event.currentTarget),{disabled:ctx.jobs.some((job)=>job.status==="running"&&job.kind==="clip"&&job.owner===entry.owner.id)}));
        actions.append(h("a",{class:"btn",href:"#/"+(entry.kind==="pose"?"expressions":"clips")+"/"+encodeURIComponent(entry.owner.id)},tr(entry.kind==="pose"?"openPose":"openClip")));
      }
      if(selected){
        if(selected.level==="watch")actions.append(selected.known?button("clearKnown",(event)=>ctx.run(()=>ctx.api("/api/production/review-known",{key:selected.key,clear:true}),tr("knownCleared"),event.currentTarget)):button("markKnown",()=>known(selected)));
        if(selected.kind==="node")actions.append(h("a",{class:"btn",href:graphLink("node:"+selected.node)},tr("openGraph")));
        if(selected.kind==="edge")actions.append(h("a",{class:"btn",href:graphLink("edge:"+selected.from+"->"+selected.to)},tr("selectEdge")));
        if(selected.pose)actions.append(h("a",{class:"btn",href:"#/expressions/"+encodeURIComponent(selected.pose)},tr("openPose")));
        if(selected.clip)actions.append(h("a",{class:"btn",href:"#/clips/"+encodeURIComponent(selected.clip)},tr("openClip")));
      }
    }
    function advance(){const rows=queue();const index=rows.findIndex((item)=>item.key===queueKey);queueKey=rows[(index+1)%rows.length]?.key||null;focusedQueue=!!queueKey;render(true);}
    function nextKey(item){const rows=queue();const index=rows.findIndex((entry)=>entry.key===item.key);return rows[index+1]?.key||rows[0]?.key||null;}
    async function adoptNow(item,reason=""){
      const next=nextKey(item);
      if(item.kind==="clip")await ctx.api("/api/production/adopt-processed",{clip:item.owner.id,take:item.take.id});
      else await ctx.api("/api/production/decision",{kind:"pose",owner:item.owner.id,take:item.take.id,action:"accept",reason});
      queueKey=next;
    }
    function adopt(item){
      if(!ready(item))return;
      if(item.kind==="pose"&&(item.take.qa.status==="watch"||item.owner.needsRecheck)){
        const view=modal("watchTitle");if(!view)return;const check=h("input",{type:"checkbox",required:true,"data-review-field":"watch-confirm"});view.insert(h("p",{class:"tiny"},tr("watchHint")),view.label("watchConfirm",check,"inline-check"));view.submit(async()=>{await adoptNow(item,tr("watchReason"));await ctx.refresh();ctx.toast(tr("adopted"));});view.show();
      }else ctx.run(()=>adoptNow(item),tr("adopted"),actions.querySelector('[data-review-action="accept"]'));
    }
    function reject(item){const view=modal("rejectTitle");if(!view)return;const reason=h("textarea",{required:true,"data-review-field":"reason"});view.insert(view.label("reason",reason));view.submit(async()=>{if(!reason.value.trim())throw new Error(tr("reason"));const next=nextKey(item);await ctx.api("/api/production/decision",{kind:item.kind,owner:item.owner.id,take:item.take.id,action:"reject",reason:reason.value.trim()});queueKey=next;await ctx.refresh();ctx.toast(tr("archived"));});view.show();}
    function known(item){const view=modal("knownTitle");if(!view)return;const note=h("textarea",{required:true,"data-review-field":"note"});view.insert(view.label("knownNote",note));view.submit(async()=>{if(!note.value.trim())throw new Error(tr("knownNote"));await ctx.api("/api/production/review-known",{key:item.key,note:note.value.trim()});await ctx.refresh();ctx.toast(tr("knownSaved"));});view.show();}
    function modal(titleKey){
      if(dialog)return null;const el=h("dialog",{class:"review-dialog","data-review-dialog":titleKey});const form=h("form");const title=h("h2",{},tr(titleKey));const error=h("output",{role:"alert"});const cancel=button("cancel",()=>el.close());const confirm=h("button",{type:"submit",class:"primary","data-review-submit":titleKey},tr("confirm"));const footer=h("div",{class:"dialog-actions"},cancel,confirm);form.append(title,error,footer);el.append(form);root.append(el);dialog=el;let busy=false;
      el.addEventListener("keydown",(event)=>{if(event.key==="Escape")event.stopPropagation();});el.addEventListener("cancel",(event)=>{if(busy)event.preventDefault();});el.addEventListener("close",()=>{if(dialog===el)dialog=null;el.remove();},{once:true});
      return {label:(key,input,cls="")=>h("label",{class:cls},tr(key),input),insert:(...nodes)=>footer.before(...nodes),submit:(fn)=>form.addEventListener("submit",async(event)=>{event.preventDefault();if(busy||!form.reportValidity())return;busy=true;confirm.disabled=cancel.disabled=true;error.textContent="";const fields=[...form.querySelectorAll("input,textarea,select")];fields.forEach((field)=>{field.disabled=true;});try{await fn();if(el.open)el.close();}catch(failure){error.textContent=String(failure.message||failure);}finally{busy=false;if(el.isConnected){confirm.disabled=cancel.disabled=false;fields.forEach((field)=>{field.disabled=false;});}}}),show:()=>{el.showModal();form.querySelector("textarea,input")?.focus();}};
    }
    async function renderSeam(selected){
      const request=revision;body.append(h("p",{class:"tiny",role:"status"},tr("seamLoading")));
      try{const data=await ctx.api("/api/review/seam?key="+encodeURIComponent(selected.key));if(disposed||request!==revision)return;body.replaceChildren();mountSeam(data,request);}
      catch(error){if(disposed||request!==revision)return;body.replaceChildren(h("p",{class:"tiny"},tr("seamError")),h("p",{class:"tiny"},String(error.message||error)),button("retry",()=>renderDetail(true)));}
    }
    function mountSeam(data,request){
      let mode="side",timer=null,showTail=true;const images={};const controls=h("div",{class:"tabs",role:"group","aria-label":tr("mode")});const panes=h("div",{class:"review-seam-panes"});const tail=h("canvas",{width:data.tail.size.w,height:data.tail.size.h,class:"checker"});const head=h("canvas",{width:data.head.size.w,height:data.head.size.h,class:"checker"});
      const commonWidth=Math.max(data.tail.size.w-2*data.tail.marginPx,data.head.size.w-2*data.head.marginPx);const commonHeight=Math.max(data.tail.size.h,data.head.size.h);
      const colors=getComputedStyle(root);
      function imagePixels(painter,image,point,crop){if(!image)return;if(crop){const width=point.size.w-2*point.marginPx;painter.drawImage(image,point.marginPx,0,width,point.size.h,0,0,width,point.size.h);}else painter.drawImage(image,0,0);}
      function draw(canvas,image,point,overlay=true,crop=false){canvas.width=crop?commonWidth:point.size.w;canvas.height=crop?commonHeight:point.size.h;const painter=canvas.getContext("2d");imagePixels(painter,image,point,crop);if(!overlay)return;const line=(color,dashed,x,y,vertical)=>{painter.strokeStyle=color;painter.lineWidth=1;painter.setLineDash(dashed?[6,4]:[]);painter.beginPath();if(vertical){painter.moveTo(x,0);painter.lineTo(x,canvas.height);}else{painter.moveTo(0,y);painter.lineTo(canvas.width,y);}painter.stroke();};for(const [name,token,dashed] of [["expected","--info",true],["actual","--danger",false]]){const color=colors.getPropertyValue(token).trim();line(color,dashed,point[name].headCenterX+(crop?0:point.marginPx),0,true);line(color,dashed,0,point[name].headTopY,false);}}
      function paint(){if(disposed||request!==revision)return;panes.classList.toggle("single",mode!=="side");head.parentElement.hidden=mode!=="side";tail.parentElement.querySelector(".tiny").textContent=tr(mode==="difference"?"difference":mode==="flicker"&&!showTail?"head":"tail");if(mode==="side"){draw(tail,images.tail,data.tail);draw(head,images.head,data.head);tail.hidden=false;head.hidden=false;}else if(mode==="flicker"){draw(tail,showTail?images.tail:images.head,showTail?data.tail:data.head,true,true);tail.hidden=false;head.hidden=true;}else{draw(tail,images.tail,data.tail,false,true);const painter=tail.getContext("2d");painter.globalCompositeOperation="difference";imagePixels(painter,images.head,data.head,true);painter.globalCompositeOperation="source-over";tail.hidden=false;head.hidden=true;}}
      function change(next){mode=next;clearInterval(timer);timer=null;controls.replaceChildren(...["side","flicker","difference"].map((value)=>h("button",{type:"button",class:mode===value?"active":"","data-seam-mode":value,"aria-pressed":String(mode===value),onclick:()=>change(value)},tr(value))));if(mode==="flicker")timer=setInterval(()=>{showTail=!showTail;paint();},500);paint();}
      panes.append(h("div",{class:"review-seam-pane"},h("span",{class:"tiny"},tr("tail")),tail),h("div",{class:"review-seam-pane"},h("span",{class:"tiny"},tr("head")),head));
      const metrics=data.metrics;const cards=h("div",{class:"review-seam-metrics"},[["headTop","dHeadTop","px"],["headCenter","dHeadCenter","px"],["faceL","faceL","L*"]].map(([label,key,unit])=>h("div",{class:"item"},h("span",{class:"tiny"},tr(label)),h("b",{class:"mono","data-seam-metric":key},metrics[key]===null?tr("unknown"):`${metrics[key]} ${unit}`),metrics.levels?.[label]?badge(ctx.t("production.status."+metrics.levels[label]),metrics.levels[label]):null)));
      const ways=h("div",{class:"row"},h("a",{class:"btn",href:graphLink("edge:"+data.tail.node+"->"+data.head.node)},tr("selectEdge")),h("a",{class:"btn",href:"#/clips"},tr("generateTransition")));
      body.append(controls,panes,h("p",{class:"tiny"},tr("guideHint")),h("p",{class:"tiny"},tr("cropHint")),cards,h("p",{class:"tiny"},tr("overall",{level:ctx.t("production.status."+data.level)})),h("h3",{},tr("ways")),h("p",{class:"tiny"},tr("graphHint")),ways);
      change("side");for(const key of ["tail","head"]){const image=new Image();image.onload=()=>{images[key]=image;paint();};image.onerror=()=>{if(disposed||request!==revision)return;body.append(h("p",{class:"tiny"},tr("frameUnavailable")));};image.src=frame(data[key].path);}
      seamCleanup=()=>{clearInterval(timer);};
    }
    function render(force=false){
      heading.textContent=tr("title");root.setAttribute("aria-label",tr("title"));root.classList.toggle("review-edit",assembly());
      if(assembly())focusedQueue=false;
      const records=issues();if(!records.some((item)=>item.key===issueKey))issueKey=records[0]?.key||null;
      const rows=queue();if(!rows.some((item)=>item.key===queueKey))queueKey=rows[0]?.key||null;
      if(focusedQueue&&!queueKey)focusedQueue=false;renderInbox();renderQueue();renderDetail(force);
    }
    function keydown(event){if(disposed||assembly()||!focusedQueue||dialog||ctx.route.tool||event.defaultPrevented||event.ctrlKey||event.altKey||event.metaKey||event.repeat)return;if(event.target instanceof Element&&event.target.closest("input,textarea,select,[contenteditable=true]"))return;const key=event.key.toLowerCase();if(!["a","x","n"].includes(key))return;event.preventDefault();if(key==="n")advance();else actions.querySelector(`[data-review-action="${key==="a"?"accept":"reject"}"]`)?.click();}
    document.addEventListener("keydown",keydown);render(true);
    return {update:(next)=>{const changed=next.state!==lastState||window.SFStudio.language!==lastLanguage;ctx=next;render(changed);lastState=next.state;lastLanguage=window.SFStudio.language;},cleanup:()=>{disposed=true;document.removeEventListener("keydown",keydown);clearPreview();if(dialog){dialog.close();dialog.remove();}}};
  }
  window.SFStudio.register("review",mountReview);
})();
