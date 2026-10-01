"use strict";
// Native reuse acceptance, on a disposable synthetic workspace. No provider calls.
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawn, spawnSync } = require("node:child_process");

(async () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "spriteforge-behavior-"));
  const python = process.env.SPRITEFORGE_PYTHON || "python";
  const fixture = spawnSync(python, [path.join(__dirname, "..", "tests", "production_demo.py"), path.join(temporary, "demo")], { encoding: "utf8", windowsHide: true });
  assert.equal(fixture.status, 0, fixture.stderr);
  const workspace = fixture.stdout.trim().split(/\r?\n/).pop();
  const graphFile = path.join(workspace, "graph_config.json");
  const graph = JSON.parse(fs.readFileSync(graphFile));
  const first = graph.nodes.find(node => node.isRoot), second = graph.nodes.find(node => node.id !== first.id);
  first.frameIntervalMs = 80; first.loopMode = "once_then_hold";
  graph.edges = [{ id: "stay", from: first.id, to: first.id, prob: 2 }, { id: "intent", from: first.id, to: second.id, prob: 0 }, { id: "return", from: second.id, to: first.id, prob: 1 }];
  fs.writeFileSync(graphFile, JSON.stringify(graph));
  const positions = graph.nodes.map(node => [node.id, node.x, node.y]);
  const server = spawn(python, ["-m", "spriteforge", "review", "--workspace", workspace, "--port", "0", "--no-browser"], { windowsHide: true });
  let browser, page;
  try {
    const url = await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error("Reviewer startup timed out")), 15000);
      server.stdout.on("data", chunk => { const match = String(chunk).match(/http:\/\/127\.0\.0\.1:\d+/); if (match) { clearTimeout(timeout); resolve(match[0]); } });
      server.on("error", reject); server.on("exit", code => reject(new Error(`Reviewer exited ${code}`)));
    });
    browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || undefined });
    page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    const screenshots=path.join(__dirname,"..","test-results");fs.mkdirSync(screenshots,{recursive:true});
    const errors = []; page.on("pageerror", error => errors.push(error.message));
    await page.goto(url + "/studio#/behavior/graph?select=" + encodeURIComponent("node:" + first.id));
    await page.locator("#gNLabel").waitFor();
    await page.waitForFunction(label => document.querySelector("#gNLabel").value === label, first.label);
    const exact = await page.evaluate(async id => SFStudio.api("/api/preview-node", { graph: (await SFStudio.api("/api/graph")).graph, nodeId: id }), first.id);
    const end = `${first.label} ${exact.frames.length}/${exact.frames.length}`;
    await page.waitForFunction(text => document.querySelector("#now").textContent.includes(text), end);
    await page.screenshot({path:path.join(screenshots,"behavior-graph-en.png")});
    await page.evaluate(()=>SFStudio.setLanguage("zh-CN"));
    await page.waitForFunction(()=>document.querySelector("#gSave").textContent === "保存");
    await page.screenshot({path:path.join(screenshots,"behavior-graph-zh.png")});
    await page.evaluate(()=>SFStudio.setLanguage("en"));
    assert.equal(await page.locator("#fps").inputValue(), "12.5");
    assert.equal(await page.locator("#fps").getAttribute("readonly"), "");
    const held = await page.locator("#frame").getAttribute("src");
    await page.waitForTimeout(250);
    assert.equal(await page.locator("#frame").getAttribute("src"), held, "Exact once_then_hold does not wrap at the end");
    await page.locator("#prevBtn").click();
    await page.waitForFunction(text => document.querySelector("#now").textContent.includes(text), `${first.label} ${exact.frames.length - 1}/${exact.frames.length}`);
    await page.locator("#nextBtn").click();
    assert.equal(await page.locator("#frame").getAttribute("src"), held);

    // A query drawer and a language update retain the native authoring draft.
    await page.locator("#gNLabel").fill("native draft");
    await page.waitForFunction(() => document.querySelector(".behavior-dirty").textContent.startsWith("1 "));
    await page.evaluate(() => { location.hash += "&tool=prompts"; });
    await page.locator("#studioDrawer").waitFor({ state: "visible" });
    assert.equal(await page.locator("#gNLabel").inputValue(), "native draft");
    await page.evaluate(() => SFStudio.setLanguage("zh-CN"));
    await page.waitForFunction(() => document.querySelector("#gSave").textContent === "保存");
    assert.equal(await page.locator("#gNLabel").inputValue(), "native draft");
    await page.evaluate(() => { location.hash = location.hash.replace(/&tool=prompts/, ""); SFStudio.setLanguage("en"); });
    await page.locator("#gSave").click();
    await page.waitForFunction(() => document.querySelector(".behavior-dirty").textContent.startsWith("0 "));
    assert.equal(JSON.parse(fs.readFileSync(graphFile)).nodes.find(node => node.id === first.id).label, "native draft");

    await page.locator("#gZoomIn").click(); await page.locator("#gResetView").click();
    await page.locator("#gExpand").click(); await page.keyboard.press("Escape");
    assert.deepEqual(JSON.parse(fs.readFileSync(graphFile)).nodes.map(node => [node.id, node.x, node.y]), positions, "View fitting and expansion leave authored positions intact");
    await page.evaluate(key => { location.hash = "#/behavior/graph?select=" + encodeURIComponent(key); }, "edge:" + first.id + "->" + second.id);
    await page.locator("#gEProb").waitFor({ state: "visible" });
    assert.equal(await page.locator("#gEProb").inputValue(), "0");
    await page.locator("#gEProb").fill("3");
    await page.waitForFunction(() => document.querySelector("#gEWarn").textContent.includes("60.0%"));
    await page.locator("#gNormalize").click();
    assert.equal(await page.locator("#gEProb").inputValue(), "0.6");
    await page.locator("#gLoad").click();
    await page.locator("#gStatus").filter({ hasText: "Loaded" }).waitFor();
    assert.equal(JSON.parse(fs.readFileSync(graphFile)).edges.find(edge => edge.id === "intent").prob, 0);

    await page.evaluate(key => { location.hash = "#/behavior/graph?select=" + encodeURIComponent(key); }, "node:" + first.id);
    await page.locator("#gNLoop").selectOption("loop");
    await page.locator("#gNView").click();
    await page.waitForFunction(() => document.querySelector("#now").textContent.includes("native draft 2/"));
    await page.evaluate(() => { window.retiredFrame = document.querySelector("#frame"); location.hash = "#/behavior/stats"; });
    await page.getByRole("heading", { name: "Where does automatic playback spend time?" }).waitFor();
    await page.evaluate(() => { window.retiredMutations = 0; new MutationObserver(changes => retiredMutations += changes.length).observe(retiredFrame, { attributes: true }); });
    const stats = await page.evaluate(() => SFStudio.api("/api/behavior/stats?minutes=10&seed=1"));
    const again = await page.evaluate(() => SFStudio.api("/api/behavior/stats?minutes=10&seed=1"));
    assert.deepEqual(stats, again, "Saved graph statistics are deterministic");
    assert.equal(await page.evaluate(() => retiredMutations), 0, "Unmounted exact player releases its frame timer and image callbacks");
    assert.equal(await page.locator(".behavior-metrics strong").first().innerText(), String(stats.simulation.changes));
    await page.locator(".behavior-groups summary").first().click();
    await page.screenshot({path:path.join(screenshots,"behavior-stats-en.png")});
    await page.evaluate(()=>SFStudio.setLanguage("zh-CN"));
    await page.getByRole("heading",{name:"自动播放的时间花在哪里？"}).waitFor();
    await page.screenshot({path:path.join(screenshots,"behavior-stats-zh.png")});
    await page.evaluate(()=>SFStudio.setLanguage("en"));
    await page.getByRole("button", { name: "Add event", exact: true }).click();
    await page.getByLabel("Target label", { exact: true }).fill(second.label);
    await page.getByRole("button", { name: "Test triggers", exact: true }).click();
    await page.locator(".behavior-trigger-result").waitFor();
    assert.ok((await page.locator(".behavior-trigger-result").innerText()).includes("Reached"));
    await page.getByRole("link", { name: "Play tested graph route", exact: true }).click();
    await page.locator("#graphCanvas").waitFor();
    await page.getByRole("button", { name: "Play tested graph route", exact: true }).click();
    await page.waitForFunction(() => document.querySelector("#now").textContent.includes("native draft 1/"));
    await page.locator("#pauseBtn").click();
    assert.deepEqual(errors, []);
    console.log("PASS: native graph reuse, stable deep selection, edit/save/reload, normalized weights, EN/ZH drafts, exact hold/step, deterministic Stats and actual route preview");
  } finally {
    if (browser) await browser.close(); server.kill();
    const resolved = path.resolve(temporary); assert.ok(resolved.startsWith(path.resolve(os.tmpdir()) + path.sep));
    fs.rmSync(resolved, { recursive: true, force: true });
  }
})().catch(error => { console.error(error); process.exit(1); });
