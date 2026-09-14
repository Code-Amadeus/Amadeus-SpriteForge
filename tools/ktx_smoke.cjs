"use strict";
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { spawn } = require("node:child_process");

(async () => {
  const workspace = path.resolve(process.argv[2] || "examples/runtime-minimal");
  const graphBefore = fs.readFileSync(path.join(workspace, "graph_config.json"));
  const layoutArgs=process.env.SPRITEFORGE_LAYOUT?['--layout',process.env.SPRITEFORGE_LAYOUT]:[];
  const server = spawn(process.env.SPRITEFORGE_PYTHON || "python", ["-m", "spriteforge", "review", "--workspace", workspace, "--port", "0", "--no-browser", ...layoutArgs], { windowsHide: true });
  let browser;
  try {
    const url = await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error("Pack reviewer startup timed out")), 20000);
      server.stdout.on("data", chunk => {
        const match = String(chunk).match(/http:\/\/127\.0\.0\.1:\d+/);
        if (match) { clearTimeout(timeout); resolve(match[0]); }
      });
      server.on("error", reject);
      server.on("exit", code => { clearTimeout(timeout); reject(new Error(`Server exited ${code}`)); });
    });
    browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || undefined });
    const page = await browser.newPage({ viewport: { width: 1500, height: 950 } });
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
    await page.goto(url);
    await page.waitForFunction(() => Number(document.querySelector("#ktxStage").dataset.width) > 0, null, { timeout: 30000 });
    assert.ok((await page.locator("#ktxStage").getAttribute("data-frame")).endsWith(".ktx2"));
    const canvasPixels = await page.locator("#ktxStage canvas").evaluate(canvas => canvas.toDataURL());
    assert.ok(canvasPixels.length > 1000, "KTX2 must produce visible rendered pixels");
    assert.equal(await page.locator("#gSave").isDisabled(), true);
    const rejection = await page.request.post(url + "/api/graph", { data: {} });
    assert.equal(rejection.status(), 409);
    await page.locator("#playBtn").click();
    const first = await page.locator("#ktxStage").getAttribute("data-frame");
    await page.waitForFunction(value => document.querySelector("#ktxStage").dataset.frame !== value, first);
    await page.locator("#pauseBtn").click();
    await page.locator("#tabInspGraph").click();
    await page.waitForFunction(()=>gViewHeight>400 && gViewWidth>400);
    const checkFit = async () => {
      const geometry=await page.evaluate(()=>({zoom:gZoom,width:gViewWidth,height:gViewHeight,
        nodes:graph.nodes.map(n=>({x:n.x*gZoom+gPan.x,y:n.y*gZoom+gPan.y,r:GR*gZoom}))}));
      assert.ok(geometry.nodes.every(n=>n.x-n.r>=0 && n.x+n.r<=geometry.width && n.y-n.r>=0 && n.y+n.r<=geometry.height),"Fit must include every node");
      return geometry;
    };
    const initial = await checkFit();
    const savedLayout=JSON.parse(fs.readFileSync(process.env.SPRITEFORGE_LAYOUT || workspace+'.graph-layout.json','utf8'));
    const positions=await page.evaluate(()=>graph.nodes.map(n=>({id:n.id,x:n.x,y:n.y})));
    assert.deepEqual(positions, savedLayout.nodes.map(n=>({id:n.id,x:n.x,y:n.y})), 'Use the exact original coordinates, not an automatic layout');
    await page.locator("#gExpand").click();
    await page.waitForFunction(()=>document.querySelector('.inspector').getBoundingClientRect().width>1400);
    await checkFit();
    await page.locator("#gZoomIn").click();
    const beforeWheel = await page.evaluate(()=>gZoom);
    const canvas = await page.locator("#graphCanvas").boundingBox();
    await page.mouse.move(canvas.x+canvas.width/2,canvas.y+canvas.height/2);
    await page.mouse.wheel(0,-300);
    await page.waitForFunction(previous=>gZoom>previous,beforeWheel);
    await page.locator("#gResetView").click();
    await checkFit();
    fs.mkdirSync("test-results", { recursive: true });
    await page.screenshot({ path: process.argv[3] || "test-results/ktx2.png", fullPage: true });
    assert.deepEqual(fs.readFileSync(path.join(workspace, "graph_config.json")), graphBefore);
    assert.deepEqual(errors.filter(e => !e.includes("favicon.ico") && !e.includes("409 (Conflict)")), []);
    console.log(`PASS: KTX2 playback, read-only pack, ${initial.nodes.length}-node graph fit, expanded view and wheel zoom`);
  } finally {
    if (browser) await browser.close();
    server.kill();
    await new Promise(resolve => server.exitCode !== null ? resolve() : server.once("exit", resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
