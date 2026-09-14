"use strict";
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawn, spawnSync } = require("node:child_process");

(async () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "spriteforge-ui-"));
  const workspace = path.join(temporary, "workspace");
  const python = process.env.SPRITEFORGE_PYTHON || "python";
  const init = spawnSync(python, ["-m", "spriteforge", "init", workspace, "--demo"], { encoding: "utf8", windowsHide: true });
  assert.equal(init.status, 0, init.stderr);
  const server = spawn(python, ["-m", "spriteforge", "review", "--workspace", workspace, "--port", "0", "--no-browser"], { windowsHide: true });
  let browser, page;
  try {
    const url = await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error("Editor startup timed out")), 15000);
      server.stdout.on("data", (chunk) => {
        const match = String(chunk).match(/http:\/\/127\.0\.0\.1:\d+/);
        if (match) { clearTimeout(timeout); resolve(match[0]); }
      });
      server.on("error", reject);
      server.on("exit", (code) => { clearTimeout(timeout); reject(new Error(`Editor exited ${code}`)); });
    });
    browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || undefined });
    page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto(url);
    await page.locator("#infoRoot").filter({ hasText: "projects/demo" }).waitFor();
    await page.waitForFunction(() => document.querySelector("#frame").naturalWidth === 64);
    await page.locator("#qaBtn").click();
    await page.locator("#summary").filter({ hasText: "Clips: 1" }).waitFor();
    await page.locator("#tabInspGraph").click();
    await page.waitForFunction(()=> {
      const viewport=document.querySelector('#graphViewport');
      return viewport.clientWidth>0 && viewport.clientHeight>0 &&
        gViewWidth===viewport.clientWidth && gViewHeight===viewport.clientHeight;
    });
    await page.locator("#graphCanvas").click({ position: await page.evaluate(()=> {
      const node=graph.nodes.find(n=>n.id==='idle');return {x:node.x*gZoom+gPan.x,y:node.y*gZoom+gPan.y};
    }) });
    await page.locator("#gNLabel").fill("demo_idle");
    await page.locator("#gNInterval").fill("90");
    await page.locator("#gNLoop").selectOption("once_then_hold");
    await page.locator("#gSave").click();
    await page.locator("#gStatus").filter({ hasText: /^Saved$/ }).waitFor();
    const graphPath = path.join(workspace, "graph_config.json");
    const saved = JSON.parse(fs.readFileSync(graphPath, "utf8"));
    assert.equal(saved.nodes[0].label, "demo_idle");
    assert.equal(saved.nodes[0].frameIntervalMs, 90);
    assert.equal(saved.nodes[0].loopMode, "once_then_hold");
    assert.deepEqual(saved.nodes.map(n=>[n.x,n.y]), [[90,100],[245,200],[400,100]], "Viewport fitting must not rewrite authored coordinates");
    const savedBytes = fs.readFileSync(graphPath, "utf8");
    await page.locator("#gNRoot").fill("missing-frames");
    await page.locator("#gSave").click();
    await page.locator("#gStatus").filter({ hasText: "Error:" }).waitFor();
    assert.equal(fs.readFileSync(graphPath, "utf8"), savedBytes);
    await page.locator("#gLoad").click();
    await page.locator("#gStatus").filter({ hasText: /^Loaded$/ }).waitFor();
    await page.waitForFunction(()=> {
      const viewport=document.querySelector('#graphViewport');
      return viewport.clientWidth>0 && viewport.clientHeight>0 &&
        gViewWidth===viewport.clientWidth && gViewHeight===viewport.clientHeight;
    });
    await page.locator("#graphCanvas").click({ position: await page.evaluate(()=> {
      const node=graph.nodes.find(n=>n.id==='idle');return {x:node.x*gZoom+gPan.x,y:node.y*gZoom+gPan.y};
    }) });
    assert.equal(await page.locator("#gNLabel").inputValue(), "demo_idle");
    await page.locator("#gValidate").click();
    await page.locator("#gStatus").filter({ hasText: "Valid topology" }).waitFor();
    await page.locator("#gNView").click();
    await page.locator("#now").filter({ hasText: "demo_idle 3/3" }).waitFor();
    const lastFrame = await page.locator("#frame").getAttribute("src");
    await page.waitForTimeout(400);
    assert.equal(await page.locator("#frame").getAttribute("src"), lastFrame);
    assert.equal(new URL(lastFrame, url).searchParams.get("path"), saved.nodes[0].root + "/0002.png");
    fs.mkdirSync("test-results", { recursive: true });
    await page.screenshot({ path: "test-results/manager.png", fullPage: true });
    assert.deepEqual(errors, []);
    console.log("PASS: asset preview, QA, edit/save/reload, rejected save, validation, exact timed hold preview");
  } catch (error) {
    if(page) {
      fs.mkdirSync('test-results',{recursive:true});
      await page.screenshot({path:'test-results/authoring-failure.png',fullPage:true});
    }
    throw error;
  } finally {
    if (browser) await browser.close();
    server.kill();
    await new Promise((resolve) => server.exitCode !== null ? resolve() : server.once("exit", resolve));
    // Remove only this test's allocated temporary directory.
    if (path.dirname(temporary) !== path.resolve(os.tmpdir()) || !path.basename(temporary).startsWith("spriteforge-ui-")) {
      throw new Error("Unexpected temporary directory");
    }
    fs.rmSync(temporary, { recursive: true, force: true });
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
