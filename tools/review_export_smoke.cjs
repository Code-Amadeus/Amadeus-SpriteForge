"use strict";
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawn } = require("node:child_process");

(async () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "spriteforge-review-export-"));
  const server = spawn(process.env.SPRITEFORGE_PYTHON || "python", [path.join(__dirname, "..", "tests", "review_export_demo.py"), path.join(temporary, "demo")], { windowsHide: true });
  const shots = path.join(__dirname, "..", "test-results"); fs.mkdirSync(shots, { recursive: true });
  let browser, page;
  try {
    const url = await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error("Review fixture startup timed out")), 30000);
      server.stdout.on("data", chunk => { const match = String(chunk).match(/http:\/\/127\.0\.0\.1:\d+/); if (match) { clearTimeout(timeout); resolve(match[0]); } });
      server.on("error", reject); server.on("exit", code => { clearTimeout(timeout); reject(new Error("Fixture server exited " + code)); });
    });
    browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || undefined });
    page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    const errors = []; page.on("pageerror", error => errors.push(error.message));
    const state = async () => (await page.request.get(url + "/api/production")).json();
    const initial = await state();
    const watch = initial.issues.find(issue => issue.key === "clip:idle_loop:fixture-watch");
    const seam = initial.issues.find(issue => issue.kind === "edge" && issue.level === "fail");
    assert.ok(watch && seam, "Fixture must expose actual seam failure and a watch record");
    await page.goto(url + "/studio#/review/" + encodeURIComponent(watch.key));
    await page.waitForFunction(() => document.querySelector(".clip-compare[data-frame='0'] [data-pane='A'] canvas")?.width > 1);
    assert.ok((await page.locator(".compare-source-label").first().innerText()).includes("Render"));
    assert.ok((await page.locator(".review-production-qa").innerText()).includes("watch"));
    await page.locator("[data-review-action='markKnown']").click();
    await page.locator("[data-review-field='note']").fill("Reviewed the synthetic watch finding");
    await page.locator("[data-review-submit='knownTitle']").click();
    await page.waitForFunction(key => !!window.SFStudio.state.issues.find(issue => issue.key === key).known, watch.key);
    assert.equal((await state()).issues.find(issue => issue.key === watch.key).known.note, "Reviewed the synthetic watch finding");
    await page.screenshot({ path: path.join(shots, "studio-review-en.png") });
    await page.locator("[data-lang='zh-CN']").click();
    await page.screenshot({ path: path.join(shots, "studio-review-zh.png") });
    await page.locator("[data-lang='en']").click();
    const queued = page.locator("[data-review-queue]");
    assert.ok(await queued.count() > 0);
    const prepared = initial.clips.find(clip => clip.id === "smile_in").takes.find(take => take.status === "candidate" && take.candidateRender?.state === "current");
    assert.ok(prepared, "The fixture must include a processed candidate");
    await page.locator(`[data-review-queue='clip:smile_in:${prepared.id}']`).click();
    await page.locator("[data-review-action='accept']").click();
    const watchDialog = page.locator("[data-review-dialog='watchTitle']");
    if (await watchDialog.count()) { await watchDialog.locator("[data-review-field='watch-confirm']").check(); await watchDialog.locator("[data-review-submit]").click(); }
    await page.waitForFunction(() => window.SFStudio.state.clips.find(clip => clip.id === "smile_in").takes.some(take => take.status === "accepted" && take.candidateRender?.state === "current"));
    await page.goto(url + "/studio#/review/" + encodeURIComponent(seam.key) + "?mode=edit");
    await page.locator("[data-seam-metric='dHeadCenter']").waitFor();
    const detail = await (await page.request.get(url + "/api/review/seam?key=" + encodeURIComponent(seam.key))).json();
    assert.equal(detail.ok, true);
    assert.ok((await page.locator("[data-seam-metric='dHeadCenter']").innerText()).includes(String(seam.dHeadCenter)));
    for (const mode of ["flicker", "difference", "side"]) await page.locator(`[data-seam-mode='${mode}']`).click();
    await page.screenshot({ path: path.join(shots, "studio-seam-en.png") });
    assert.equal(await page.locator("[data-review-queue]").count(), 0, "Editing checks cannot silently adopt production candidates");
    await page.goto(url + "/studio#/export");
    await page.locator("[data-export-check='qa']").waitFor();
    assert.equal(await page.locator("[data-export-action='start']").isDisabled(), true);
    const graph = (await (await page.request.get(url + "/api/graph")).json()).graph;
    graph.edges = [];
    const saved = await page.request.post(url + "/api/graph", { data: graph }); assert.equal(saved.status(), 200);
    await page.reload();
    await page.locator("[data-export-action='start']:enabled").waitFor();
    await page.locator("[data-export-field='version']").fill("browser-build");
    await page.locator("[data-export-field='notes']").fill("A reviewed synthetic build.");
    await page.locator("[data-lang='zh-CN']").click();
    assert.equal(await page.locator("[data-export-field='notes']").inputValue(), "A reviewed synthetic build.");
    await page.screenshot({ path: path.join(shots, "studio-export-zh.png") });
    await page.locator("[data-lang='en']").click();
    await page.screenshot({ path: path.join(shots, "studio-export-en.png") });
    await page.locator("[data-export-action='start']").click();
    await page.waitForFunction(() => window.SFStudio.jobs.some(job => job.action === "export" && job.status === "succeeded"));
    await page.locator("[data-export-version='browser-build']").waitFor();
    const workspace = path.join(temporary, "demo", "studio ws");
    const output = path.join(workspace, "production", "exports", "browser-build");
    assert.equal(fs.readFileSync(path.join(output, "RELEASE_NOTES.md"), "utf8"), "A reviewed synthetic build.");
    const manifest = JSON.parse(fs.readFileSync(path.join(output, "runtime_manifest.json"), "utf8"));
    assert.ok(manifest.frameCount > 0);
    await page.setViewportSize({ width: 1280, height: 800 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    assert.deepEqual(errors, []);
    console.log("PASS: review watch notes, processed candidate adoption, real seam metrics/modes, export gate, notes, language drafts and encoded export history");
  } catch (error) {
    if (page) {
      console.error(await page.evaluate(() => window.SFStudio?.jobs.map(job => ({ action: job.action, status: job.status, error: job.error }))).catch(() => []));
      await page.screenshot({ path: path.join(shots, "review-export-failure.png") }).catch(() => {});
    }
    throw error;
  } finally {
    if (browser) await browser.close(); server.kill();
    assert.ok(path.resolve(temporary).startsWith(path.resolve(os.tmpdir()) + path.sep + "spriteforge-review-export-"));
    fs.rmSync(temporary, { recursive: true, force: true });
  }
})().catch(error => { console.error(error); process.exit(1); });
