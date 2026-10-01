"use strict";
// Real host and browser. Every provider request is served by this loopback fake.
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const http = require("node:http");
const { spawn, spawnSync } = require("node:child_process");

(async () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "spriteforge-workflows-"));
  const python = process.env.SPRITEFORGE_PYTHON || "python";
  const testEnv = { ...process.env, PYTHONPATH: [path.join(__dirname, "..", "src"), process.env.PYTHONPATH].filter(Boolean).join(path.delimiter) };
  const fixture = spawnSync(python, [path.join(__dirname, "..", "tests", "expressions_demo.py"), path.join(temporary, "demo")], { encoding: "utf8", windowsHide: true, env: testEnv });
  assert.equal(fixture.status, 0, fixture.stderr);
  const workspace = fixture.stdout.trim().split(/\r?\n/).pop();
  const videoPath = path.join(temporary, "demo", "workflow-video.mp4");
  const encoded = spawnSync("ffmpeg", ["-loglevel", "error", "-y", "-loop", "1", "-i", path.join(temporary, "demo", "final.png"), "-t", "1", "-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p", videoPath], { encoding: "utf8", windowsHide: true });
  assert.equal(encoded.status, 0, encoded.stderr);
  const requests = [], result = fs.readFileSync(path.join(temporary, "demo", "final.png"));
  const fake = http.createServer(async (request, response) => {
    if (request.method === "POST") {
      const chunks = []; for await (const chunk of request) chunks.push(chunk);
      requests.push(JSON.parse(Buffer.concat(chunks).toString("utf8")));
      response.setHeader("Content-Type", "application/json");
      response.end(JSON.stringify({ output: { choices: [{ message: { content: [{ image: `http://127.0.0.1:${fake.address().port}/result.png` }] } }] } }));
    } else if (request.url === "/result.png") {
      response.setHeader("Content-Type", "image/png"); response.end(result);
    } else { response.writeHead(404); response.end(); }
  });
  await new Promise(resolve => fake.listen(0, "127.0.0.1", resolve));
  const toolsFile = path.join(workspace, "production", "tools.json");
  const configured = JSON.parse(fs.readFileSync(toolsFile, "utf8"));
  configured.providers["qwen-image"].baseUrl = `http://127.0.0.1:${fake.address().port}/api/v1`;
  configured.defaults = { conceptProvider: "qwen-image", stillProvider: "qwen-image", batchConfirmThreshold: 3 };
  fs.writeFileSync(toolsFile, JSON.stringify(configured));
  const server = spawn(python, ["-X", "faulthandler", "-m", "spriteforge", "review", "--workspace", workspace, "--port", "0", "--no-browser"], {
    windowsHide: true, env: { ...testEnv, DASHSCOPE_API_KEY: "synthetic-local-provider-only" },
  });
  let stderr = ""; server.stderr.on("data", chunk => { stderr = (stderr + chunk).slice(-16000); });
  const screenshots = path.join(__dirname, "..", "test-results"); fs.mkdirSync(screenshots, { recursive: true });
  let browser, page;
  try {
    const url = await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error("Workflow fixture startup timed out")), 15000);
      server.stdout.on("data", chunk => { const match = String(chunk).match(/http:\/\/127\.0\.0\.1:\d+/); if (match) { clearTimeout(timeout); resolve(match[0]); } });
      server.on("error", reject); server.on("exit", code => { clearTimeout(timeout); reject(new Error("Server exit " + code)); });
    });
    browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || undefined });
    page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    const errors = []; page.on("pageerror", error => errors.push(error.message));
    const read = async route => (await page.request.get(url + route)).json();
    const post = async (route, data) => (await page.request.post(url + route, { data })).json();
    const action = key => page.locator(`[data-workflow-action='${key}']`);
    const saveUI = async () => {
      const response = page.waitForResponse(response => response.url() === url + "/api/production/workflows" && response.request().method() === "POST");
      await action("save").click();
      const result = await (await response).json(); assert.equal(result.ok, true);
      await action("save").waitFor({ state: "visible" });
      return result.workflow;
    };
    const modal = key => page.locator(`[data-workflow-dialog='${key}']`);
    const graphFacts = () => page.evaluate(() => {
      const editor = document.querySelector("[data-workflow-canvas]").data;
      return { nodes: editor.graph._nodes.map(node => ({ id: node.sfId, kind: node.sfKind, params: node.sfParams, position: [...node.pos], collapsed: !!node.flags.collapsed })), links: Object.keys(editor.graph.links).length, groups: editor.graph._groups.length, scale: editor.ds.scale };
    });
    const select = async kind => {
      await page.waitForFunction(kind => document.querySelector("[data-workflow-canvas]")?.data?.graph?._nodes.some(node => node.sfKind === kind), kind);
      const point = await page.evaluate(kind => {
        const canvas = document.querySelector("[data-workflow-canvas]"), editor = canvas.data;
        const node = editor.graph._nodes.find(node => node.sfKind === kind);
        const point = editor.convertOffsetToCanvas([node.pos[0] + 50, node.pos[1] - 12]);
        const rect = canvas.getBoundingClientRect(); return { x: rect.left + point[0], y: rect.top + point[1] };
      }, kind);
      await page.mouse.click(point.x, point.y);
    };
    const add = async kind => { await action("add").click(); await page.locator(`[data-workflow-add='${kind}']`).click(); };
    const confirmRun = async paid => {
      await action("run").click(); await modal("planTitle").waitFor();
      assert.ok((await modal("planTitle").innerText()).includes(paid ? `${paid} paid requests` : "no paid requests"));
      const launched = page.waitForResponse(response => response.url() === url + "/api/production/workflows/run" && response.request().method() === "POST");
      await modal("planTitle").locator("[data-workflow-submit]").click();
      const accepted = await (await launched).json(); assert.equal(accepted.ok, true);
      await modal("planTitle").waitFor({ state: "detached" });
      await page.waitForFunction(id => ["succeeded", "failed"].includes(window.SFStudio.jobs.find(job => job.id === id)?.status), accepted.job.id);
      const job = await page.evaluate(id => window.SFStudio.jobs.find(job => job.id === id), accepted.job.id);
      assert.equal(job.status, "succeeded", job.error);
    };

    await page.goto(url + "/studio#/workflows?template=final-still&pose=angry");
    await page.waitForFunction(() => document.querySelector("[data-workflow-canvas]")?.data?.graph?._nodes.length === 4);
    assert.deepEqual((await graphFacts()).nodes.map(node => node.kind), ["base-still", "prompt-template", "image-edit", "save-pose-take"]);
    assert.equal(requests.length, 0, "Opening a template must not dispatch generation");
    await select("image-edit");
    await page.locator("[data-workflow-param='width']").fill("640");
    await page.locator("[data-workflow-param='width']").blur();
    await page.locator("[data-workflow-param='height']").fill("640");
    await page.locator("[data-workflow-param='height']").blur();
    await page.locator("[data-workflow-field='name']").fill("Synthetic candidate workflow");
    await page.locator("[data-lang='zh-CN']").click();
    assert.equal(await page.locator("[data-workflow-param='width']").inputValue(), "640");
    assert.equal(await page.locator("[data-workflow-field='name']").inputValue(), "Synthetic candidate workflow");
    assert.equal(await page.locator("#studioMain h1").innerText(), "工作流");
    await page.locator("[data-lang='en']").click();
    await saveUI(); await page.waitForFunction(() => window.SFStudio.route.id);
    const id = await page.evaluate(() => window.SFStudio.route.id);
    const saved = (await read("/api/production/workflows/" + id)).workflow;
    assert.equal(saved.name, "Synthetic candidate workflow");
    assert.equal(saved.nodes.find(node => node.kind === "image-edit").params.width, 640);
    await select("image-edit");
    await action("run").click(); await modal("planTitle").waitFor();
    assert.ok((await modal("planTitle").innerText()).includes("1 paid requests"));
    assert.equal(requests.length, 0, "Planning cannot make a paid request");
    await page.keyboard.press("Escape");
    const wrong = await post("/api/production/workflows/run", { id, planHash: (await post("/api/production/workflows/plan", { id })).planHash, confirmPaid: 0 });
    assert.equal(wrong.ok, false); assert.equal(requests.length, 0);
    const acceptedBefore = (await read("/api/production")).poses.find(pose => pose.id === "angry").acceptedTake;
    await confirmRun(1); assert.equal(requests.length, 1);
    const overview = await read("/api/production");
    const take = overview.poses.find(pose => pose.id === "angry").takes.at(-1);
    assert.equal(take.status, "candidate"); assert.equal(take.source.workflow.id, id);
    assert.equal(overview.poses.find(pose => pose.id === "angry").acceptedTake, acceptedBefore);
    await select("image-edit");
    await page.locator("[data-workflow-preview='image']").waitFor();
    await page.screenshot({ path: path.join(screenshots, "studio-workflows-en.png") });
    await page.locator("[data-lang='zh-CN']").click();
    await page.screenshot({ path: path.join(screenshots, "studio-workflows-zh.png") });
    await page.locator("[data-lang='en']").click();
    await confirmRun(0); assert.equal(requests.length, 1, "Paid cached output cannot expire automatically");
    await select("image-edit");
    await page.locator("[data-workflow-rerun]").check();
    await confirmRun(1); assert.equal(requests.length, 2, "Explicit re-run dispatches exactly one new request");

    const downloadEvent = page.waitForEvent("download"); await action("export").click();
    const download = await downloadEvent; const exportedPath = path.join(temporary, "workflow.json"); await download.saveAs(exportedPath);
    const exported = JSON.parse(fs.readFileSync(exportedPath, "utf8")); assert.equal(exported.format, "spriteforge.workflow.v1");
    const importedPath = path.join(temporary, "imported.json"); exported.id = "imported-candidate"; fs.writeFileSync(importedPath, JSON.stringify(exported));
    await action("import").click(); await modal("import").locator("input[type='file']").setInputFiles(importedPath); await modal("import").locator("[data-workflow-submit]").click();
    await page.waitForFunction(() => window.SFStudio.route.id === "imported-candidate");
    await action("run").click(); await modal("planTitle").waitFor();
    assert.ok(await modal("planTitle").locator("[data-workflow-field='disclosure']").count());
    assert.equal(requests.length, 2, "Import and its first plan cannot execute nodes");
    await page.keyboard.press("Escape");
    const rejected = await post("/api/production/workflows/import", { ...exported, id: "unknown-node", nodes: [{ id: "evil", kind: "javascript", params: { code: "window.pwned=true" }, position: [0, 0] }], links: [] });
    assert.equal(rejected.ok, false); assert.equal(requests.length, 2);

    await add("text");
    await page.locator("[data-workflow-param='text']").fill("Draft survives drawers and polls");
    await page.locator("[data-workflow-param='text']").blur();
    await page.locator("[data-tool='settings']").click();
    await page.locator(".drawer-close").click();
    assert.equal(await page.locator("[data-workflow-param='text']").inputValue(), "Draft survives drawers and polls");
    const count = (await graphFacts()).nodes.length;
    await action("copy").click(); await action("paste").click(); assert.equal((await graphFacts()).nodes.length, count + 1);
    assert.equal(await page.evaluate(() => localStorage.getItem("litegrapheditor_clipboard")), null);
    await action("group").click(); await modal("groupTitle").locator("input").fill("Synthetic group"); await modal("groupTitle").locator("[data-workflow-submit]").click();
    assert.equal((await graphFacts()).groups, 1);
    await action("collapse").click(); assert.equal((await graphFacts()).nodes.at(-1).collapsed, true);
    await saveUI(); await page.reload(); await page.waitForFunction(() => document.querySelector("[data-workflow-canvas]")?.data?.graph?._groups.length === 1);
    assert.equal((await graphFacts()).nodes.at(-1).params.text, "Draft survives drawers and polls");
    await action("fit").click(); const scale = (await graphFacts()).scale; await action("zoomIn").click(); assert.ok((await graphFacts()).scale > scale);
    await action("zoomOut").click();
    await add("reroute"); await page.locator("[data-workflow-param='type']").selectOption("TEXT");
    await action("connect").click();
    const source = modal("connect").locator("[data-workflow-field='source']");
    const textOption = await source.locator("option").filter({ hasText: /^Text ·/ }).first().getAttribute("value");
    await source.selectOption(textOption); await modal("connect").locator("[data-workflow-submit]").click();
    const links = (await graphFacts()).links;
    await action("connect").click();
    await modal("connect").locator("[data-workflow-field='source']").selectOption("0");
    await modal("connect").locator("[data-workflow-submit]").click();
    assert.equal((await graphFacts()).links, links, "An incompatible IMAGE to TEXT connection cannot replace the valid link");
    assert.ok((await modal("connect").locator("[data-workflow-error]").innerText()).includes("incompatible"));
    await page.keyboard.press("Escape");
    await saveUI();
    assert.equal((await read("/api/production/workflows/imported-candidate")).workflow.nodes.at(-1).params.type, "TEXT");
    await add("load-image");
    const chooserEvent = page.waitForEvent("filechooser"); await action("upload").click();
    const chooser = await chooserEvent; await chooser.setFiles(path.join(temporary, "demo", "final.png"));
    await page.waitForFunction(() => document.querySelector("[data-workflow-param='path']")?.value.startsWith("production/workflows/inputs/"));
    await page.locator("[data-workflow-preview='image']").waitFor();
    const importedImage = (await graphFacts()).nodes.at(-1);
    assert.ok(importedImage.params.path.startsWith("production/workflows/inputs/"));
    await add("load-video");
    const videoChooserEvent = page.waitForEvent("filechooser"); await action("upload").click();
    const videoChooser = await videoChooserEvent; await videoChooser.setFiles(videoPath);
    await page.waitForFunction(() => document.querySelector("[data-workflow-preview='video']")?.readyState >= 2);
    assert.ok(await page.locator("[data-workflow-preview='video']").evaluate(video => video.videoWidth > 0 && video.videoHeight > 0));
    await page.locator("[data-workflow-preview='video']").evaluate(video => video.play());
    await page.waitForFunction(() => document.querySelector("[data-workflow-preview='video']").currentTime > .05);
    await page.locator("[data-workflow-preview='video']").evaluate(video => video.pause());
    assert.equal(requests.length, 2);
    await page.setViewportSize({ width: 1280, height: 800 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.screenshot({ path: path.join(screenshots, "studio-workflows-1280.png") });
    assert.deepEqual(errors, []);
    console.log("PASS: typed workflow canvas, drafts, templates, save/import/export, disclosure, exact paid confirmation, candidate-only output, cache and explicit re-run (2 loopback fake calls)");
  } catch (error) {
    console.error("Workflow fixture server:", { exitCode: server.exitCode, stderr });
    if (page) { console.error(await page.locator(".workflow-error").innerText().catch(() => "")); console.error(await page.evaluate(() => window.SFStudio?.jobs.map(job => ({ action: job.action, status: job.status, error: job.error }))).catch(() => [])); await page.screenshot({ path: path.join(screenshots, "studio-workflows-failure.png") }).catch(() => {}); }
    throw error;
  } finally {
    if (browser) await browser.close(); server.kill(); await new Promise(resolve => fake.close(resolve));
    const resolved = path.resolve(temporary); assert.ok(resolved.startsWith(path.resolve(os.tmpdir()) + path.sep + "spriteforge-workflows-"));
    fs.rmSync(resolved, { recursive: true, force: true });
  }
})().catch(error => { console.error(error); process.exit(1); });
