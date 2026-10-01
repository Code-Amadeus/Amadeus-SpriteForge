"use strict";
// Real browser acceptance on synthetic assets. Never invokes a paid provider.
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawn, spawnSync } = require("node:child_process");

(async () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "spriteforge-studio-"));
  const python = process.env.SPRITEFORGE_PYTHON || "python";
  const result = spawnSync(python, [path.join(__dirname, "..", "tests", "production_demo.py"), path.join(temporary, "demo")],
    { encoding: "utf8", windowsHide: true });
  assert.equal(result.status, 0, result.stderr);
  const workspace = result.stdout.trim().split(/\r?\n/).pop();
  const server = spawn(python, ["-X", "faulthandler", "-m", "spriteforge", "review", "--workspace", workspace, "--port", "0", "--no-browser"],
    { windowsHide: true });
  let serverErrors = "";
  server.stderr.on("data", chunk => { serverErrors = (serverErrors + chunk).slice(-16000); });
  let browser, page;
  const errors = [], consoleErrors = [], requestFailures = [], responses = [];
  const pendingRequests = new Set();
  const retain = (entries, value) => { entries.push(value); if (entries.length > 60) entries.shift(); };
  const relevant = request => ["document", "script", "stylesheet"].includes(request.resourceType())
    || /\/api\/(production|clips)(?:[/?]|$)/.test(request.url());
  const screenshots = path.join(__dirname, "..", "test-results");
  fs.mkdirSync(screenshots, { recursive: true });
  try {
    const url = await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error("Editor startup timed out")), 15000);
      server.stdout.on("data", chunk => {
        const match = String(chunk).match(/http:\/\/127\.0\.0\.1:\d+/);
        if (match) { clearTimeout(timeout); resolve(match[0]); }
      });
      server.on("error", reject);
      server.on("exit", code => { clearTimeout(timeout); reject(new Error(`Editor exited ${code}`)); });
    });
    browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || undefined });
    page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", message => { if (message.type() === "error") retain(consoleErrors, message.text()); });
    page.on("request", request => { if (relevant(request)) pendingRequests.add(request); });
    page.on("requestfinished", request => pendingRequests.delete(request));
    page.on("requestfailed", request => {
      pendingRequests.delete(request);
      if (relevant(request)) retain(requestFailures, { url: request.url(), error: request.failure()?.errorText });
    });
    page.on("response", response => {
      if (relevant(response.request())) retain(responses, { url: response.url(), status: response.status() });
    });
    await page.goto(url + "/studio");
    await page.locator("#studioMain h1").waitFor();
    assert.equal(await page.locator("html").getAttribute("lang"), "en");
    assert.ok((await page.locator("#studioMain").innerText()).includes("smile"));
    await page.screenshot({ path: path.join(screenshots, "studio-overview-en.png") });

    const routes = ["overview", "expressions", "clips", "workflows", "review", "behavior", "export"];
    async function openStage(stage) {
      const mode = ["behavior", "export"].includes(stage) ? "edit" : "produce";
      await page.locator(`[data-mode='${mode}']`).click();
      await page.waitForFunction(value => window.SFStudio.mode === value, mode);
      if (mode === "produce") {
        const view = stage === "workflows" ? "workflow" : "studio";
        await page.locator(`[data-generation-view='${view}']`).click();
        await page.waitForFunction(value => (window.SFStudio.route.stage === "workflows") === value, view === "workflow");
      }
      await page.locator(`[data-stage='${stage}']`).click();
      await page.waitForFunction(value => window.SFStudio?.route.stage === value, stage);
    }
    await page.locator("[data-mode='edit']").click();
    await page.waitForFunction(() => window.SFStudio.mode === "edit");
    assert.equal(await page.locator("[data-stage='clips']").count(), 0);
    assert.equal(await page.locator("[data-generation-view]").count(), 0);
    await page.locator("[data-stage='overview']").click();
    await page.locator("[data-library-pose]").first().waitFor();
    assert.equal(await page.locator("[data-library-pose]").count(), 2);
    assert.ok(await page.locator("[data-library-clip]").count() > 0);
    await page.reload();
    await page.waitForFunction(() => window.SFStudio.state?.initialized && window.SFStudio.mode === "edit");
    assert.equal(await page.locator("[data-clip-action='generate']").count(), 0);
    await page.screenshot({ path: path.join(screenshots, "studio-edit-assets-en.png") });
    for (const stage of routes) {
      await openStage(stage);
      await page.locator("#studioMain h1").waitFor();
      await page.screenshot({ path: path.join(screenshots, `studio-${stage}-en.png`) });
    }
    await openStage("overview");
    await page.locator("[data-stage='clips']").click();
    await page.goBack();
    assert.ok((await page.evaluate(() => location.hash)).startsWith("#/overview"));
    await page.goForward();
    assert.ok((await page.evaluate(() => location.hash)).startsWith("#/clips"));
    const route = await page.evaluate(() => location.hash);
    await page.reload();
    await page.locator("#studioMain h1").waitFor();
    assert.equal(await page.evaluate(() => location.hash), route);

    await page.locator("#studioTopbar").getByRole("button", { name: "中文", exact: true }).click();
    assert.equal(await page.locator("html").getAttribute("lang"), "zh-CN");
    const chinese = { overview: "总览", expressions: "表情", clips: "片段", workflows: "工作流", review: "审阅", behavior: "行为", export: "导出" };
    for (const stage of routes) {
      await openStage(stage);
      const link = page.locator(`[data-stage='${stage}']`);
      assert.ok((await link.innerText()).includes(chinese[stage]));
      await page.locator("#studioMain h1").waitFor();
      if (stage === "clips") assert.ok((await page.locator(".clip-studio").getAttribute("aria-label")).includes(chinese[stage]));
      else if (stage !== "overview") assert.ok((await page.locator("#studioMain h1").innerText()).includes(chinese[stage]));
      await page.screenshot({ path: path.join(screenshots, `studio-${stage}-zh.png`) });
    }
    await page.locator("#studioTopbar").getByRole("button", { name: "EN", exact: true }).click();
    await openStage("overview");
    for (const tool of ["prompts", "jobs", "settings"]) {
      await page.locator(`[data-tool='${tool}']`).click();
      await page.locator("#studioDrawer").waitFor({ state: "visible" });
      assert.ok((await page.evaluate(() => location.hash)).includes(`tool=${tool}`));
      assert.ok((await page.evaluate(() => location.hash)).startsWith("#/overview"));
      await page.screenshot({ path: path.join(screenshots, `studio-${tool}-en.png`) });
      await page.keyboard.press("Escape");
      await page.locator("#studioDrawer").waitFor({ state: "hidden" });
    }
    await page.locator("[data-tool='canvas']").click();
    await page.locator(".node[data-card='clip:smile_in']").waitFor();
    assert.equal(await page.locator(".node.pose").count(), 2);
    await page.locator(".node[data-card='clip:smile_in'] .node-head").click();
    await page.locator("#canvasInspector").waitFor({ state: "visible" });
    assert.equal(await page.locator("#canvasInspector").getByRole("button", { name: "Use this take", exact: true }).count(), 0);
    assert.ok(await page.locator("#canvasInspector").getByRole("link", { name: "Review in Clip Studio", exact: true }).count() > 0);
    await page.locator("#canvasInspector .inspector-head button").click();
    await page.screenshot({ path: path.join(screenshots, "studio-canvas-en.png") });
    const draft = "Unsaved motion draft must survive opening a tool";
    const clipPrompt = page.locator(".node[data-card='clip:smile_in'] textarea");
    await clipPrompt.fill(draft);
    await page.locator("[data-tool='prompts']").click();
    await page.locator("#studioDrawer").waitFor({ state: "visible" });
    await page.keyboard.press("Escape");
    await page.locator("#studioDrawer").waitFor({ state: "hidden" });
    // Canvas is an overlay tool; return to it without persisting a prompt draft.
    await page.locator("[data-tool='canvas']").click();
    assert.equal(await clipPrompt.inputValue(), draft);
    await page.locator("#studioTopbar").getByRole("button", { name: "中文", exact: true }).click();
    assert.equal(await clipPrompt.inputValue(), draft, "Language switching must preserve an unsaved draft");
    await page.screenshot({ path: path.join(screenshots, "studio-canvas-zh.png") });
    await page.locator("#studioTopbar").getByRole("button", { name: "EN", exact: true }).click();
    await page.locator("[data-stage='overview']").click();
    await page.setViewportSize({ width: 1280, height: 800 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), "Studio should fit its minimum viewport");
    await page.screenshot({ path: path.join(screenshots, "studio-overview-1280.png") });
    // One completed owner must refresh while a different owner's job still runs.
    const jobSnapshot = await (await page.request.get(url + "/api/production")).json();
    let firstFinished = false;
    const fakeJobs = () => ["smile_in", "idle_loop"].map((owner, index) => ({
      id: `fixture-${index}`, action: "render", kind: "clip", owner, startedAt: "2026-10-02T00:00:00Z",
      status: index === 0 && firstFinished ? "succeeded" : "running", log: [], result: null, error: null,
    }));
    await page.route("**/api/production/jobs", route => route.fulfill({ json: { ok: true, jobs: fakeJobs() } }));
    await page.route("**/api/production", route => route.fulfill({ json: {
      ...jobSnapshot, character: { ...jobSnapshot.character, displayName: firstFinished ? "Updated after one completed job" : "Two running jobs" },
    } }));
    await page.reload();
    await page.getByRole("heading", { name: "Two running jobs", exact: true }).waitFor();
    firstFinished = true;
    await page.getByRole("heading", { name: "Updated after one completed job", exact: true }).waitFor();
    assert.equal(await page.evaluate(() => window.SFStudio.jobs.filter(job => job.status === "running").length), 1);
    await page.unroute("**/api/production/jobs");
    await page.unroute("**/api/production");
    await page.route("**/api/production", route => route.fulfill({ json: { ok: true, initialized: false } }));
    await page.reload();
    await page.getByRole("heading", { name: "Initialize a production workspace" }).waitFor();
    assert.equal(await page.locator("[data-stage]").count(), 0);
    assert.ok((await page.locator("#studioMain code").innerText()).includes("spriteforge production init"));
    assert.deepEqual(errors, []);
    console.log("Studio routes, language, history, tools, canvas and layout passed");
  } catch (error) {
    console.error("Studio fixture server:", { exitCode: server.exitCode, signal: server.signalCode, stderr: serverErrors });
    console.error("Studio browser errors:", { pageErrors: errors, consoleErrors, requestFailures,
      pendingRequests: [...pendingRequests].map(request => request.url()), responses });
    if (page) console.error("Studio boot facts:", await page.evaluate(() => {
      const main = document.querySelector("#studioMain");
      return { url: location.href, readyState: document.readyState, studio: Boolean(window.SFStudio),
        route: window.SFStudio?.route, initialized: window.SFStudio?.state?.initialized,
        mainBusy: main?.getAttribute("aria-busy"), headings: main?.querySelectorAll("h1").length,
        mainText: main?.innerText.slice(0, 500),
        sidebarChildren: document.querySelector("#studioSidebar")?.childElementCount,
        topbarChildren: document.querySelector("#studioTopbar")?.childElementCount };
    }).catch(cause => ({ unavailable: cause.message })));
    if (page) await page.screenshot({ path: path.join(screenshots, "studio-failure.png") }).catch(() => {});
    throw error;
  } finally {
    if (browser) await browser.close();
    server.kill();
    fs.rmSync(temporary, { recursive: true, force: true });
  }
})().catch(error => { console.error(error); process.exit(1); });
