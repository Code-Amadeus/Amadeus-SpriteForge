"use strict";
// Rebuild documentation screenshots from public repository references only.
// The fixture makes blended demonstration frames; this never calls a provider.
const {chromium} = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {spawn, spawnSync} = require("node:child_process");

(async () => {
  const repo = path.resolve(__dirname, "..");
  const target = path.join(repo, "test-results", "readme-recording-" + Date.now());
  const output = path.join(repo, "docs", "images");
  const frames = path.join(target, "capture");
  const python = process.env.SPRITEFORGE_PYTHON || "python";
  const built = spawnSync(python, [path.join(__dirname, "studio_docs_demo.py"), target], {encoding:"utf8", windowsHide:true});
  assert.equal(built.status, 0, built.stderr);
  const workspace = built.stdout.trim().split(/\r?\n/).pop();
  fs.mkdirSync(frames, {recursive:true});
  const server = spawn(python, ["-m", "spriteforge", "review", "--workspace", workspace, "--port", "0", "--no-browser"], {windowsHide:true});
  let browser;
  try {
    const url = await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error("Documentation server did not start")), 30000);
      server.stdout.on("data", chunk => {const match=String(chunk).match(/http:\/\/127\.0\.0\.1:\d+/); if(match){clearTimeout(timer);resolve(match[0]);}});
      server.on("error", reject);
      server.on("exit", code => {clearTimeout(timer);reject(new Error("Documentation server exited " + code));});
    });
    browser = await chromium.launch({headless:true, channel:process.env.BROWSER_CHANNEL || undefined});
    const page = await browser.newPage({viewport:{width:1280,height:800},deviceScaleFactor:1.5});
    const errors=[]; page.on("pageerror", error => errors.push(error.message));
    const go = async (hash, selector) => {await page.goto(url + "/studio#" + hash); await page.locator(selector).first().waitFor();};
    const settled = async () => {
      await page.evaluate(()=>document.fonts.ready);
      await page.waitForFunction(()=>{const compare=document.querySelector(".clip-compare");return !compare||(compare.dataset.frame!==undefined&&compare.querySelector("[data-pane='A'] canvas")?.width>1);});
    };
    const snapshot = async name => {await settled();await page.locator(".toast:not([hidden])").waitFor({state:"hidden"});await page.screenshot({path:path.join(output, name + ".png")});};
    const language = async name => {await page.locator(`[data-lang='${name}']`).click();await settled();};
    let frame=0;
    const scenes=[];
    async function scene(name, count) {
      scenes.push({name, startFrame:frame, frames:count});
      for(let index=0;index<count;index++) {
        const started=Date.now();
        await page.screenshot({path:path.join(frames,String(frame++).padStart(4,"0")+".png"),clip:{x:210,y:0,width:1070,height:800}});
        const remaining=125-(Date.now()-started); if(remaining>0) await page.waitForTimeout(remaining);
      }
    }

    await go("/clips/smile_in", ".clip-compare[data-frame='0']");
    await page.waitForFunction(()=>document.querySelector("[data-pane='A'] canvas")?.width>1);
    for(let index=0;index<10;index++) await page.getByRole("button",{name:"Next frame",exact:true}).click();
    await page.locator(".clip-compare[data-frame='10']").waitFor();
    await page.locator(".clip-studio").screenshot({path:path.join(output,"studio-preview.png")});
    await snapshot("studio-preview-full"); await snapshot("studio-clips-en");
    await language("zh-CN"); await snapshot("studio-clips-zh"); await language("en");
    await page.getByRole("button",{name:"Play",exact:true}).click();
    await scene("Clip comparison",24);

    await go("/review", "[data-review-queue]");
    await page.locator("[data-review-queue]").first().click();
    await page.locator("[data-review-action='accept']:enabled").waitFor();
    await page.waitForFunction(()=>document.querySelector(".clip-compare[data-frame='0'] [data-pane='A'] canvas")?.width>1);
    await snapshot("studio-review-en"); await scene("Processed candidate and QA",16);
    await language("zh-CN"); await snapshot("studio-review-zh"); await language("en");
    await page.locator("[data-review-action='accept']").click();
    await page.waitForFunction(()=>!document.querySelector("[data-review-queue]"));
    await go("/overview?mode=edit", "[data-library-clip]");
    await snapshot("studio-edit-assets-en"); await scene("Adopted material library",12);

    await go("/behavior/graph?select=node%3Asmile_in", "#gNLabel");
    await page.waitForFunction(()=>document.querySelector("#frame")?.naturalWidth>0);
    await page.locator("#gResetView").click();
    await page.locator(".behavior-properties").evaluate(element=>{element.scrollTop=element.scrollHeight;});
    await snapshot("studio-behavior-en"); await scene("Graph and exact clip player",20);
    await language("zh-CN"); await snapshot("studio-behavior-zh"); await language("en");
    await go("/behavior/stats", ".behavior-metrics strong");
    await snapshot("studio-stats-en");
    await language("zh-CN"); await snapshot("studio-stats-zh"); await language("en");
    await go("/export", "[data-export-check='qa']");
    await snapshot("studio-export-en");
    await language("zh-CN"); await snapshot("studio-export-zh"); await language("en");

    for(const [stage,selector] of [["overview",".overview"],["expressions/smile",".expression-studio"],["canvas",".node[data-card='clip:smile_in']"]]) {
      await go("/"+stage,selector);
      const name=stage.split("/")[0];
      await snapshot("studio-"+name+"-en");
      await language("zh-CN");await snapshot("studio-"+name+"-zh");await language("en");
    }
    // Reuse the actual adopted transition through local workflow operations.
    const state=await (await page.request.get(url+"/api/production")).json();
    const sourceTake=state.clips.find(clip=>clip.id==="smile_in").acceptedTake;
    const previousOutput=state.clips.find(clip=>clip.id==="smile_out").acceptedTake;
    const workflow={format:"spriteforge.workflow.v1",id:"reverse-transition-demo",name:"Reverse an existing transition",version:1,groups:[],
      nodes:[{id:"source",kind:"clip-take",params:{clip:"smile_in",take:sourceTake},position:[25,150]},
        {id:"reverse",kind:"reverse",params:{},position:[365,150]},
        {id:"preview",kind:"preview",params:{},position:[705,25]},
        {id:"candidate",kind:"save-clip-take",params:{clip:"smile_out",note:"Local reverse; review before adoption"},position:[705,360]}],
      links:[{from:{node:"source",port:"media"},to:{node:"reverse",port:"media"}},
        {from:{node:"reverse",port:"media"},to:{node:"preview",port:"media"}},
        {from:{node:"reverse",port:"media"},to:{node:"candidate",port:"media"}}]};
    const saved=await page.request.post(url+"/api/production/workflows",{data:workflow});assert.equal(saved.status(),200);
    await go("/workflows/"+workflow.id,"[data-workflow-action='run']:enabled");
    await page.locator("[data-workflow-action='fit']").click();
    await page.locator("[data-workflow-action='run']").click();
    const confirmation=page.locator("[data-workflow-dialog='planTitle']");await confirmation.waitFor();
    assert.ok((await confirmation.innerText()).includes("no paid requests"));
    await page.locator("[data-workflow-submit='planTitle']").click();
    await page.locator(".workflow-status").filter({hasText:"Run: completed"}).waitFor();
    const after=await (await page.request.get(url+"/api/production")).json();
    assert.equal(after.clips.find(clip=>clip.id==="smile_out").acceptedTake,previousOutput);
    await snapshot("studio-workflows-en");await scene("Local node workflow and candidate output",24);
    await language("zh-CN");await snapshot("studio-workflows-zh");await language("en");
    for(const tool of ["prompts","jobs","settings"]) {
      await go("/overview?tool="+tool,"#studioDrawer:not([hidden])");
      await snapshot("studio-"+tool+"-en");
    }
    assert.deepEqual(errors,[]);
    const encoded=spawnSync("ffmpeg",["-y","-loglevel","error","-framerate","8","-i",path.join(frames,"%04d.png"),"-filter_complex","[0:v]scale=1070:800:flags=lanczos,split[a][b];[a]palettegen=max_colors=224[p];[b][p]paletteuse=dither=bayer:bayer_scale=3","-loop","0",path.join(output,"production-pipeline.gif")],{encoding:"utf8",windowsHide:true});
    assert.equal(encoded.status,0,encoded.stderr);
    fs.copyFileSync(path.join(output,"studio-preview-full.png"),path.join(output,"production-pipeline-poster.png"));
    fs.writeFileSync(path.join(target,"recording.json"),JSON.stringify({workspace,frames:frame,fps:8,scenes},null,2));
    console.log(JSON.stringify({target,frames:frame,seconds:frame/8,output}));
  } finally {if(browser)await browser.close();server.kill();}
})().catch(error=>{console.error(error);process.exit(1);});
