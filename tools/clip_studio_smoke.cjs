"use strict";
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawn, spawnSync } = require("node:child_process");

(async () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "spriteforge-clips-"));
  const python = process.env.SPRITEFORGE_PYTHON || "python";
  const demo = spawnSync(python, [path.join(__dirname, "..", "tests", "production_demo.py"), path.join(temporary, "demo")], { encoding: "utf8", windowsHide: true });
  assert.equal(demo.status, 0, demo.stderr);
  const workspace = demo.stdout.trim().split(/\r?\n/).pop();
  const browserVideo = path.join(temporary, "browser-take.mp4");
  const encoded = spawnSync("ffmpeg", ["-hide_banner", "-loglevel", "error", "-i", path.join(temporary, "demo", "alternative.mp4"),
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", browserVideo], { encoding: "utf8", windowsHide: true });
  assert.equal(encoded.status, 0, encoded.stderr);
  // Only this disposable workspace can invoke the fake CLI; no account or network access.
  const fakeState = path.join(temporary, "fake-wan"); fs.mkdirSync(fakeState);
  fs.writeFileSync(path.join(fakeState, "logged_in"), "yes"); fs.writeFileSync(path.join(fakeState, "credits"), "100");
  const toolsPath = path.join(workspace, "production", "tools.json");
  const configuredTools = JSON.parse(fs.readFileSync(toolsPath, "utf8"));
  configuredTools.providers["wan-cli"].command = [python, path.join(__dirname, "..", "tests", "processors", "fake_wan_cli.py")];
  configuredTools.providers["wan-cli"].pollSeconds = 0.01;
  fs.writeFileSync(toolsPath, JSON.stringify(configuredTools));
  const server = spawn(python, ["-m", "spriteforge", "review", "--workspace", workspace, "--port", "0", "--no-browser"], {
    windowsHide: true, env: { ...process.env, FAKE_WAN_STATE: fakeState, FAKE_WAN_VIDEO: browserVideo,
      WAN_ACCESS_KEY: "synthetic-browser-test-only", WAN_CONFIG_DIR: fakeState },
  });
  const shots = path.join(__dirname, "..", "test-results");
  fs.mkdirSync(shots, { recursive: true });
  let browser, page;
  try {
    const url = await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error("Editor startup timed out")), 15000);
      server.stdout.on("data", chunk => { const match = String(chunk).match(/http:\/\/127\.0\.0\.1:\d+/); if (match) { clearTimeout(timer); resolve(match[0]); } });
      server.on("error", reject); server.on("exit", code => { clearTimeout(timer); reject(new Error(`Editor exited ${code}`)); });
    });
    browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || undefined });
    page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    const state = async () => (await page.request.get(url + "/api/production")).json();
    const uploaded = await page.request.post(url + "/api/production/upload?kind=clip&owner=smile_in&name=browser-take.mp4", {
      headers: { "Content-Type": "application/octet-stream" }, data: fs.readFileSync(browserVideo),
    });
    assert.equal(uploaded.status(), 200);
    const initial = await state();
    const original = initial.clips.find(clip => clip.id === "smile_in");
    const candidates = original.takes.filter(take => take.status === "candidate");
    const candidate = candidates.at(-1);
    const accepted = original.takes.find(take => take.status === "accepted");
    await page.goto(url + "/studio#/clips/smile_in");
    await page.locator(".clip-studio h1").filter({ hasText: /^smile_in$/ }).waitFor();
    await page.locator(".clip-compare[data-frame='0']").waitFor();
    await page.waitForFunction(() => document.querySelector("[data-pane='A'] canvas").width > 1);
    assert.equal(await page.locator("[data-version]").count(), original.takes.length);
    await page.screenshot({ path: path.join(shots, "clip-studio-en.png") });
    await page.locator("#studioTopbar [data-lang='zh-CN']").click();
    assert.equal(await page.locator(".clip-studio").getAttribute("aria-label"), "片段工作室");
    await page.screenshot({ path: path.join(shots, "clip-studio-zh.png") });
    await page.locator("#studioTopbar [data-lang='en']").click();

    await page.locator(`[data-take='${candidate.id}']`).click();
    await page.locator("[data-version-filter='review']").click();
    assert.equal(await page.locator("[data-version]").count(), candidates.length);
    await page.locator("[data-version-filter='all']").click();
    await page.locator(`[data-pin='${accepted.id}']`).click();
    await page.getByRole("button", { name: "Next frame", exact: true }).click();
    await page.locator(".clip-compare[data-frame='1']").waitFor();
    await page.locator(".clip-studio h1").click();
    await page.keyboard.press("c");
    await page.locator(".clip-compare[data-mode='overlay']").waitFor();
    await page.keyboard.press("c");
    await page.locator(".clip-compare[data-mode='difference']").waitFor();
    await page.keyboard.press("c");
    await page.locator(".clip-compare[data-mode='onion']").waitFor();
    await page.keyboard.press("c");

    const draft = page.locator("[data-clip-draft='subject']");
    await draft.fill("Keep this unsaved motion draft");
    await draft.press("j");
    assert.equal(await page.locator(`[data-take='${candidate.id}']`).getAttribute("aria-pressed"), "true");
    const draftText = await draft.inputValue();
    await page.locator("[data-tool='prompts']").click();
    await page.locator("#studioDrawer").waitFor({ state: "visible" });
    await page.keyboard.press("Escape");
    await page.locator("#studioDrawer").waitFor({ state: "hidden" });
    assert.equal(await draft.inputValue(), draftText);
    await page.locator("#studioTopbar [data-lang='zh-CN']").click();
    assert.equal(await draft.inputValue(), draftText);
    await page.locator("#studioTopbar [data-lang='en']").click();

    await page.locator(".clip-studio h1").click();
    await page.keyboard.press("x");
    const rejection = page.locator("[data-clip-dialog='rejectTitle']");
    await rejection.waitFor();
    await rejection.locator("[data-dialog-submit]").click();
    assert.equal((await state()).clips.find(clip => clip.id === "smile_in").takes.find(take => take.id === candidate.id).status, "candidate");
    await rejection.locator("[data-dialog-field='reason']").fill("Synthetic review: compare the hair motion");
    await rejection.locator("[data-dialog-submit]").click();
    await rejection.waitFor({ state: "detached" });
    assert.equal((await state()).clips.find(clip => clip.id === "smile_in").takes.find(take => take.id === candidate.id).rejected.reason, "Synthetic review: compare the hair motion");
    await page.locator(`[data-take='${candidate.id}']`).click();
    await page.locator("[data-clip-action='restore']").click();
    await page.locator("[data-clip-action='accept']").waitFor();
    assert.equal(await page.locator("[data-clip-action='accept']").isDisabled(), true);
    await page.locator("[data-clip-action='processTake']").click();
    await page.waitForFunction(id => window.SFStudio.state.clips.find(clip => clip.id === "smile_in").takes.find(take => take.id === id).candidateRender.state === "current", candidate.id);
    assert.equal((await state()).clips.find(clip => clip.id === "smile_in").acceptedTake, accepted.id, "Processing a candidate keeps the published choice");
    await page.locator(".clip-studio h1").click();
    await page.keyboard.press("a");
    await page.waitForFunction(id => window.SFStudio.state.clips.find(clip => clip.id === "smile_in").acceptedTake === id, candidate.id);
    assert.equal((await state()).clips.find(clip => clip.id === "smile_in").render.state, "current", "Adoption publishes the already reviewed candidate");

    for (const tab of ["generation", "processing", "playback", "mouth", "qa", "prompt"]) {
      await page.locator(`[data-detail-tab='${tab}']`).click();
      assert.ok((await page.locator(".clip-details-body").innerText()).trim().length > 0, tab);
    }
    await page.locator("[data-clip-action='prepare']").click();
    assert.equal(await page.locator("[data-clip-dialog='prepareTitle'] a[download='first.png']").count(), 1);
    await page.keyboard.press("Escape");

    await page.locator("[data-clip-action='import']").click();
    const imported = page.locator("[data-clip-dialog='importTitle']");
    await imported.locator("[data-dialog-field='video']").setInputFiles(browserVideo);
    await imported.locator("[data-dialog-submit]").click();
    await imported.waitFor({ state: "detached" });
    const afterImport = (await state()).clips.find(clip => clip.id === "smile_in");
    assert.equal(afterImport.takes.length, original.takes.length + 1);
    assert.equal(afterImport.takes.at(-1).media.fps, 30, "Video import must retain detected source FPS");

    await page.locator("[data-clip-action='newVariant']").click();
    const variantDialog = page.locator("[data-clip-dialog='newVariant']");
    await variantDialog.locator("[data-dialog-field='id']").fill("smile_in2");
    await variantDialog.locator("[data-dialog-submit]").click();
    await page.locator(".clip-studio h1").filter({ hasText: /^smile_in2$/ }).waitFor();
    const variant = (await state()).clips.find(clip => clip.id === "smile_in2");
    assert.equal(variant.acceptedTake, null); assert.deepEqual(variant.takes, []);
    assert.deepEqual(variant.generation, original.generation);
    assert.equal(await page.locator("[data-variant]").count(), 2);
    await page.locator("[data-variant='smile_in']").click();
    await page.locator(".clip-studio h1").filter({ hasText: /^smile_in$/ }).waitFor();
    await page.setViewportSize({ width: 1280, height: 800 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), "Clip Studio should fit the minimum viewport");
    await page.screenshot({ path: path.join(shots, "clip-studio-1280.png") });

    // Exercise the paid-action boundary with an entirely local, logged fake provider.
    const post = async (route, data) => {
      const response = await page.request.post(url + "/api/production/" + route, { data });
      assert.equal(response.status(), 200, await response.text()); return response.json();
    };
    const library = JSON.parse(fs.readFileSync(path.join(workspace, "production", "prompts.json"), "utf8"));
    for (const block of Object.keys(library.blocks)) {
      await post("prompt", { block, text: block === "clip.smile_in" ? "Historical gentle smile motion" : "Synthetic " + block });
    }
    await post("clip-settings", { clip: "smile_in", changes: { provider: "wan-cli" } });
    await page.reload(); await page.locator("[data-clip-action='generate']").waitFor();
    const submissions = () => fs.existsSync(path.join(fakeState, "calls.jsonl"))
      ? fs.readFileSync(path.join(fakeState, "calls.jsonl"), "utf8").trim().split(/\r?\n/).filter(Boolean).map(JSON.parse).filter(call => call.args[0] === "frame2video") : [];
    await page.locator("[data-clip-action='generate']").click();
    const firstGenerate = page.locator("[data-clip-dialog='generateTitle']");
    await firstGenerate.waitFor(); assert.equal(submissions().length, 0, "Opening a dialog must not generate");
    await firstGenerate.locator("[data-dialog-submit]").click();
    await firstGenerate.waitFor({ state: "detached" });
    await page.waitForFunction(() => window.SFStudio.state.clips.find(clip => clip.id === "smile_in").takes.some(take => take.source.provider === "wan-cli" && take.state === "ready"));
    const generated = (await state()).clips.find(clip => clip.id === "smile_in").takes.find(take => take.source.provider === "wan-cli");
    assert.equal(submissions().length, 1);
    await post("prompt", { block: "clip.smile_in", text: "New current motion differs from history" });
    await page.reload(); await page.locator(`[data-take='${generated.id}']`).click();
    await page.locator("[data-clip-action='generateFrom']").click();
    const fromGenerate = page.locator("[data-clip-dialog='generateFromTitle']");
    assert.equal(await fromGenerate.locator("[data-dialog-field='subject']").inputValue(), "Historical gentle smile motion");
    assert.equal(submissions().length, 1);
    await fromGenerate.locator("[data-dialog-field='subject']").fill("Refined historical motion");
    await fromGenerate.locator("[data-dialog-field='note']").fill("Use softer hair motion");
    // Two synchronous submissions still cross the execution boundary only once.
    await fromGenerate.locator("form").evaluate(form => { form.requestSubmit(); form.requestSubmit(); });
    await fromGenerate.waitFor({ state: "detached" });
    await page.waitForFunction(id => window.SFStudio.state.clips.find(clip => clip.id === "smile_in").takes.some(take => take.basedOn === id && take.state === "ready"), generated.id);
    const derived = (await state()).clips.find(clip => clip.id === "smile_in").takes.find(take => take.basedOn === generated.id);
    assert.equal(derived.note, "Use softer hair motion"); assert.match(derived.prompt.text, /Refined historical motion/);
    assert.match(generated.prompt.text, /Historical gentle smile motion/);
    assert.equal(submissions().length, 2, "Double submit must not duplicate generation");
    assert.deepEqual(errors, []);
    console.log("PASS: Clip Studio versions, A/B, drafts, decisions, settings, FPS, variants and fake generation provenance");
  } catch (error) {
    if (page) await page.screenshot({ path: path.join(shots, "clip-studio-failure.png") }).catch(() => {});
    throw error;
  } finally {
    if (browser) await browser.close();
    server.kill();
    assert.ok(path.resolve(temporary).startsWith(path.resolve(os.tmpdir()) + path.sep + "spriteforge-clips-"));
    fs.rmSync(temporary, { recursive: true, force: true });
  }
})().catch(error => { console.error(error); process.exit(1); });
