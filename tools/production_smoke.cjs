"use strict";
// Browser check of the production page against a synthetic workspace (needs the qa extra).
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawn, spawnSync } = require("node:child_process");

(async () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "spriteforge-production-"));
  const python = process.env.SPRITEFORGE_PYTHON || "python";
  const demo = spawnSync(python, [path.join(__dirname, "..", "tests", "production_demo.py"), path.join(temporary, "demo")],
    { encoding: "utf8", windowsHide: true });
  assert.equal(demo.status, 0, demo.stderr);
  const workspace = demo.stdout.trim().split(/\r?\n/).pop();
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
    page = await browser.newPage({ viewport: { width: 1500, height: 1000 } });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    fs.mkdirSync("test-results", { recursive: true });

    await page.goto(url + "/production");
    await page.locator("[data-pose='smile']").click();
    await page.waitForFunction(() => {
      const canvas = document.querySelector("#compareCanvas");
      if (!canvas) return false;
      const data = canvas.getContext("2d").getImageData(0, 0, canvas.width, canvas.height).data;
      for (let i = 3; i < data.length; i += 4) if (data[i]) return true;
      return false;
    });
    await page.locator("#poseDetail table").filter({ hasText: "head top" }).waitFor();
    await page.screenshot({ path: "test-results/production-stills.png", fullPage: true });

    await page.locator("#tabs button[data-tab='clips']").click();
    await page.locator("[data-clip='smile_in']").click();
    await page.locator("#clipDetail summary").filter({ hasText: "Archive (1 rejected)" }).waitFor();
    const candidate = page.locator("#clipDetail .card").filter({ hasText: "second attempt" });
    await candidate.getByRole("button", { name: "Use this take" }).click();
    await page.locator("[data-clip='smile_in'] .badge").filter({ hasText: /^stale$/ }).waitFor();
    await page.locator("#renderBtn").click();
    await page.locator("[data-clip='smile_in'] .badge").filter({ hasText: /^current$/ }).waitFor({ timeout: 60000 });
    await page.waitForFunction(() => (document.querySelector("#renderPreview") || {}).dataset?.frame !== undefined);
    await page.screenshot({ path: "test-results/production-clips.png", fullPage: true });

    await page.locator("[data-clip='smile_talk']").click();
    await page.locator("#clipDetail").filter({ hasText: "closed mouth from idle still (shared)" }).waitFor();
    await page.locator("#silencePreview").check();
    await page.waitForFunction(() => document.querySelector("#renderPreview").dataset.silence === "1");
    await page.screenshot({ path: "test-results/production-mouth.png", fullPage: true });

    await page.locator("#tabs button[data-tab='prompts']").click();
    const block = page.locator("textarea[data-block='video.loop']");
    await block.fill("Seamless ${to} loop; the last frame returns to the first.");
    await page.locator(".card").filter({ has: block }).getByRole("button", { name: "Save as new version" }).click();
    await page.locator(".card").filter({ has: page.locator("textarea[data-block='video.loop']") })
      .locator("summary").filter({ hasText: "History (2 versions)" }).waitFor();
    await page.screenshot({ path: "test-results/production-prompts.png", fullPage: true });

    assert.deepEqual(errors, []);
    assert.equal(await page.locator("body").evaluate((b) => /(^|\n)(null|\[object)/.test(b.innerText)), false);
    console.log("PASS: still overlay, take decision, stale render, render job, silence overlay preview, prompt version");
  } catch (error) {
    if (page) {
      fs.mkdirSync("test-results", { recursive: true });
      await page.screenshot({ path: "test-results/production-failure.png", fullPage: true });
    }
    throw error;
  } finally {
    if (browser) await browser.close();
    server.kill();
    await new Promise((resolve) => server.exitCode !== null ? resolve() : server.once("exit", resolve));
    if (path.dirname(temporary) !== path.resolve(os.tmpdir()) || !path.basename(temporary).startsWith("spriteforge-production-")) {
      throw new Error("Unexpected temporary directory");
    }
    fs.rmSync(temporary, { recursive: true, force: true });
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
