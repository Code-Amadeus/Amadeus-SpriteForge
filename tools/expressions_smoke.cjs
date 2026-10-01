"use strict";
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const http = require("node:http");
const crypto = require("node:crypto");
const { spawn, spawnSync } = require("node:child_process");

(async () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "spriteforge-expressions-"));
  const python = process.env.SPRITEFORGE_PYTHON || "python";
  const fixture = spawnSync(python, [path.join(__dirname, "..", "tests", "expressions_demo.py"), path.join(temporary, "demo")], { encoding: "utf8", windowsHide: true });
  assert.equal(fixture.status, 0, fixture.stderr);
  const workspace = fixture.stdout.trim().split(/\r?\n/).pop();
  const requests = [], responses = [], images = new Map();
  const fake = http.createServer(async (request, response) => {
    if (request.method === "POST") {
      const chunks = []; for await (const chunk of request) chunks.push(chunk);
      requests.push(JSON.parse(Buffer.concat(chunks).toString("utf8")));
      const image = responses.shift();
      if (!image) { response.writeHead(400); response.end(JSON.stringify({ message: "Unexpected fake generation" })); return; }
      const name = "/result-" + requests.length + ".png"; images.set(name, image);
      response.setHeader("Content-Type", "application/json");
      response.end(JSON.stringify({ output: { choices: [{ message: { content: [{ image: `http://127.0.0.1:${fake.address().port}${name}` }] } }] } }));
    } else if (images.has(request.url)) {
      response.setHeader("Content-Type", "image/png"); response.end(images.get(request.url));
    } else { response.writeHead(404); response.end(); }
  });
  await new Promise(resolve => fake.listen(0, "127.0.0.1", resolve));
  const toolsFile = path.join(workspace, "production", "tools.json");
  const configured = JSON.parse(fs.readFileSync(toolsFile, "utf8"));
  configured.providers["qwen-image"].baseUrl = `http://127.0.0.1:${fake.address().port}/api/v1`;
  configured.defaults = { conceptProvider: "qwen-image", stillProvider: "qwen-image", batchConfirmThreshold: 3 };
  fs.writeFileSync(toolsFile, JSON.stringify(configured));
  const server = spawn(python, ["-m", "spriteforge", "review", "--workspace", workspace, "--port", "0", "--no-browser"], {
    windowsHide: true, env: { ...process.env, DASHSCOPE_API_KEY: "synthetic-local-provider-only" },
  });
  const shots = path.join(__dirname, "..", "test-results"); fs.mkdirSync(shots, { recursive: true });
  let browser, page;
  try {
    const url = await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error("Server startup timed out")), 15000);
      server.stdout.on("data", chunk => { const match = String(chunk).match(/http:\/\/127\.0\.0\.1:\d+/); if (match) { clearTimeout(timeout); resolve(match[0]); } });
      server.on("error", reject); server.on("exit", code => { clearTimeout(timeout); reject(new Error("Server exit " + code)); });
    });
    browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || undefined });
    page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    const errors = []; page.on("pageerror", error => errors.push(error.message));
    const state = async () => (await page.request.get(url + "/api/production")).json();
    const enqueue = name => responses.push(fs.readFileSync(path.join(temporary, "demo", name)));
    const action = name => page.locator(`[data-expression-action='${name}']`);
    const dialog = name => page.locator(`[data-expression-dialog='${name}']`);
    const submit = name => dialog(name).locator("[data-expression-submit]").click();
    await page.goto(url + "/studio#/expressions/angry");
    await page.locator(".expression-studio").waitFor();
    enqueue("concept-grid.png");
    await action("newSheet").click(); await dialog("newSheet").waitFor();
    assert.equal(await dialog("newSheet").locator("[data-sheet-pose]").count(), 6);
    assert.equal(requests.length, 0);
    await submit("newSheet"); await dialog("newSheet").waitFor({ state: "detached" });
    await page.waitForFunction(() => window.SFStudio.state.concepts.some(sheet => sheet.state === "ready"));
    const firstSheet = (await state()).concepts.find(sheet => sheet.state === "ready");
    assert.equal(await page.locator("[data-concept-cell]").count(), 6);
    assert.deepEqual(firstSheet.size, { w: 400, h: 272 });
    assert.ok(firstSheet.cells.every(cell => cell.size.w === 128 && cell.size.h === 128));
    assert.equal(requests.length, 1);
    await page.locator("[data-concept-cell='0']").click();
    await page.locator("[data-cell-pick='0']").check();
    await page.waitForFunction(id => window.SFStudio.state.concepts.find(sheet => sheet.id === id).cells[0].picked, firstSheet.id);
    enqueue("reroll.png"); await action("reroll").click(); await submit("concepts");
    await dialog("concepts").waitFor({ state: "detached" });
    await page.waitForFunction(id => window.SFStudio.state.concepts.find(sheet => sheet.id === id).cells[0].rerolls.some(item => item.state === "ready"), firstSheet.id);
    const rerolled = (await state()).concepts.find(sheet => sheet.id === firstSheet.id);
    assert.equal(requests.length, 2);
    assert.notEqual(rerolled.cells[0].file, firstSheet.cells[0].file);
    assert.deepEqual(rerolled.cells.slice(1).map(cell => cell.file), firstSheet.cells.slice(1).map(cell => cell.file));
    await page.locator("[data-expression-tab='final']").click();
    enqueue("final.png"); await action("makeStill").click(); await dialog("generateTitle").waitFor();
    assert.equal(requests.length, 2, "Formal-still dialog cannot submit before confirmation");
    await submit("generateTitle"); await dialog("generateTitle").waitFor({ state: "detached" });
    await page.waitForFunction(() => window.SFStudio.state.poses.find(pose => pose.id === "angry").takes.some(take => take.state === "ready"));
    await page.locator("[data-expression-tab='final']").click();
    const take = (await state()).poses.find(pose => pose.id === "angry").takes.at(-1);
    assert.equal(take.source.concept.sheet, firstSheet.id); assert.equal(take.source.concept.cell, 0);
    assert.notEqual(take.qa.status, "fail"); assert.equal(requests.length, 3);
    const references = requests[2].input.messages[0].content.filter(item => item.image);
    assert.equal(references.length, 2);
    const reference = Buffer.from(references[1].image.split(",")[1], "base64");
    assert.equal(crypto.createHash("sha256").update(reference).digest("hex"), take.source.concept.sha256);
    assert.deepEqual(fs.readFileSync(path.join(workspace, "production", "poses", "angry", "takes", take.id, "reference.png")), reference);
    await page.screenshot({ path: path.join(shots, "studio-expressions-en.png") });
    await page.locator("[data-lang='zh-CN']").click();
    assert.equal(await page.locator(".expression-studio").getAttribute("aria-label"), "表情");
    await page.screenshot({ path: path.join(shots, "studio-expressions-zh.png") });
    await page.locator("[data-lang='en']").click();
    await action("prepare").click();
    const baseLink = dialog("prepareTitle").locator("a[download='base.png']");
    assert.equal((await page.request.get(url + await baseLink.getAttribute("href"))).status(), 200);
    await page.keyboard.press("Escape");
    await action("approve").click();
    await page.waitForFunction(() => window.SFStudio.state.poses.find(pose => pose.id === "angry").acceptedTake || document.querySelector("[data-expression-dialog='approveTitle']"));
    if (await dialog("approveTitle").count()) { await dialog("approveTitle").locator("[data-expression-field='watch-confirm']").check(); await submit("approveTitle"); }
    await page.waitForFunction(id => window.SFStudio.state.poses.find(pose => pose.id === "angry").acceptedTake === id, take.id);
    await action("newSheet").click();
    await dialog("newSheet").locator("[data-expression-field='grid']").selectOption("2x2");
    await dialog("newSheet").locator("[data-expression-field='provider']").selectOption("import");
    await dialog("newSheet").locator("[data-expression-field='file']").setInputFiles(path.join(temporary, "demo", "concept-grid.png"));
    await submit("newSheet"); await dialog("newSheet").waitFor({ state: "detached" });
    assert.equal((await state()).concepts.length, 2); assert.equal(requests.length, 3);
    await page.locator(`[data-sheet='${firstSheet.id}']`).click();
    await page.locator("[data-concept-cell='0']").click();
    await page.locator("[data-cell-pick='0']").uncheck(); await page.locator("[data-cell-pick='0']").check();
    await page.reload(); await page.locator(".expression-studio").waitFor();
    assert.equal((await state()).concepts.find(sheet => sheet.id === firstSheet.id).cells[0].picked, true);
    await action("plan").click(); await submit("planTitle"); await dialog("planTitle").waitFor({ state: "detached" });
    const planned = (await state()).clips;
    assert.ok(planned.length > 0); assert.ok(planned.every(clip => clip.takes.length === 0 && clip.acceptedTake === null));
    assert.equal(requests.length, 3, "Planning clips must never generate");
    // Capability display does not silently turn a reference edit into another request.
    await page.route("**/api/production", async route => {
      const response = await route.fetch(); const data = await response.json();
      data.tools.providers["qwen-image"].supportsReference = false;
      await route.fulfill({ response, json: data });
    });
    await page.reload(); await page.locator(`[data-sheet='${firstSheet.id}']`).click();
    await page.locator("[data-concept-cell='0'] .expression-cell-select").click();
    await page.locator("[data-expression-tab='final']").click();
    assert.equal(await action("makeStill").count() + await action("tryAgain").count(), 0);
    assert.equal(await action("withoutConcept").count(), 1);
    assert.equal(requests.length, 3);
    await page.unroute("**/api/production");
    await page.setViewportSize({ width: 1280, height: 800 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.screenshot({ path: path.join(shots, "studio-expressions-1280.png") });
    assert.deepEqual(errors, []);
    console.log("PASS: concept grid, trim, actual dimensions, pick, single reroll, reference still, QA, approval, history, languages and free clip planning");
  } catch (error) {
    if (page) console.error(await page.evaluate(() => window.SFStudio?.jobs.map(job => ({ action: job.action, status: job.status, error: job.error })) ).catch(() => []));
    if (page) await page.screenshot({ path: path.join(shots, "studio-expressions-failure.png") }).catch(() => {});
    throw error;
  } finally {
    if (browser) await browser.close(); server.kill(); await new Promise(resolve => fake.close(resolve));
    assert.ok(path.resolve(temporary).startsWith(path.resolve(os.tmpdir()) + path.sep + "spriteforge-expressions-"));
    fs.rmSync(temporary, { recursive: true, force: true });
  }
})().catch(error => { console.error(error); process.exit(1); });
