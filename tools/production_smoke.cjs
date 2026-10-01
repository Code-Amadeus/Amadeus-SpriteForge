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

    // Canvas: cards, wires, the guide, a prompt version saved from a card, the side panel, a moved card.
    await page.goto(url + "/production");
    await page.locator(".node[data-card='clip:smile_in']").waitFor();
    assert.equal(await page.locator(".node.pose").count(), 2);
    assert.equal(await page.locator(".node.clip").count(), 3);
    assert.equal(await page.locator("#canvasWires path.wire").count(), 4); // three starts, smile_in's end; loops return to their pose
    await page.locator("#canvasGuideBtn").click();
    assert.equal(await page.locator("#canvasGuide li").count(), 7);
    await page.locator("#canvasGuide button").filter({ hasText: /^(Close|关闭)$/ }).click();
    const smileIn = page.locator(".node[data-card='clip:smile_in']");
    await smileIn.locator("textarea").fill("Smile slowly; camera, size and brightness stay unchanged.");
    await smileIn.getByRole("button", { name: "Save prompt" }).click();
    await page.locator(".node[data-card='clip:smile_in']").filter({ hasText: "prompt v2" }).waitFor();
    await page.locator(".node[data-card='clip:smile_in'] .node-head strong").click();
    await page.locator("#canvasInspector a.input-link").filter({ hasText: "first.png" }).waitFor();
    const position = () => page.locator(".node[data-card='pose:smile']").evaluate((el) => [parseFloat(el.style.left), parseFloat(el.style.top)]);
    const before = await position();
    const title = await page.locator(".node[data-card='pose:smile'] .node-head strong").boundingBox();
    await page.mouse.move(title.x + 4, title.y + 4);
    await page.mouse.down();
    await page.mouse.move(title.x + 4, title.y + 90, { steps: 6 });
    await page.mouse.up();
    await page.waitForTimeout(600);
    await page.reload();
    await page.locator(".node[data-card='pose:smile']").waitFor();
    const after = await position();
    assert.ok(Math.abs(after[0] - before[0]) < 2 && after[1] > before[1] + 40, `card did not move down: ${before} -> ${after}`);

    // Chain: draw a new pose from smile, import a take of the first-frame-only transition,
    // take its last frame as the new pose's still and approve it.
    await page.locator("#canvasViewport").hover();
    await page.mouse.wheel(0, 700);
    const drop = await page.evaluate(() => {
      const box = document.querySelector("#canvasViewport").getBoundingClientRect();
      const points = [[box.right - 60, box.bottom - 60], [box.left + 60, box.bottom - 60], [box.right - 60, box.top + 60]];
      return points.find(([x, y]) => !document.elementFromPoint(x, y).closest(".node, .guide"));
    });
    const answers = ["wink", null];
    const answer = (dialog) => {
      dialog.accept(answers.shift() || dialog.defaultValue());
      if (!answers.length) page.off("dialog", answer);
    };
    page.on("dialog", answer);
    const port = await page.locator(".node[data-card='pose:smile'] .port.out").boundingBox();
    await page.mouse.move(port.x + port.width / 2, port.y + port.height / 2);
    await page.mouse.down();
    await page.mouse.move(drop[0], drop[1], { steps: 8 });
    await page.mouse.up();
    const wink = page.locator(".node[data-card='clip:smile_to_wink']");
    await wink.filter({ hasText: "first frame only" }).waitFor();
    await page.locator(".node[data-card='pose:wink']").waitFor();
    assert.equal(await page.locator("#canvasWires path.wire.open").count(), 1);
    await wink.locator("input[type=file]").setInputFiles(path.join(temporary, "demo", "alternative.mp4"));
    await wink.locator(".take-thumb").waitFor();
    await page.locator(".node[data-card='clip:smile_to_wink']").getByRole("button", { name: "Last frame → wink still" }).click();
    await page.locator(".node[data-card='pose:wink']").filter({ hasText: "of smile_to_wink" }).waitFor({ timeout: 60000 });
    await page.locator(".node[data-card='pose:wink'] .node-head strong").click();
    await page.locator("#canvasInspector").getByRole("button", { name: "Approve still" }).click();
    await page.locator(".node[data-card='pose:wink']").filter({ hasText: "approved" }).waitFor();
    await page.locator("#canvasWires path.wire.adopted").waitFor({ state: "attached" });
    assert.match(await page.locator("#canvasWires text.wire-label").first().textContent(), /^frame \d+$/);
    await page.locator("#canvasFit").click();
    await page.screenshot({ path: "test-results/production-canvas.png", fullPage: true });

    await page.locator("#tabs button[data-tab='stills']").click();
    await page.locator("[data-pose='smile']").click();
    await page.waitForFunction(() => {
      const canvas = document.querySelector("#compareCanvas");
      if (!canvas) return false;
      const data = canvas.getContext("2d").getImageData(0, 0, canvas.width, canvas.height).data;
      for (let i = 3; i < data.length; i += 4) if (data[i]) return true;
      return false;
    });
    await page.locator("#poseDetail table").filter({ hasText: "head top" }).waitFor();
    const generateStill = page.locator("#generateStillBtn");
    assert.equal(await generateStill.isDisabled(), true);
    assert.match(await generateStill.getAttribute("title"), /placeholders/);
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

    // The last frame of a transition take becomes a candidate still for the clip's end pose.
    assert.equal(await page.locator("#clipDetail label").filter({ hasText: "Last frame input" }).locator("select").inputValue(), "still");
    await page.locator("#clipDetail .card").filter({ hasText: "second attempt" })
      .getByRole("button", { name: "Last frame → smile still" }).click();
    await page.locator("#tabs button[data-tab='stills']").click();
    await page.locator("[data-pose='smile']").click();
    await page.locator("#poseDetail .card").filter({ hasText: "of smile_in take" }).waitFor({ timeout: 60000 });
    await page.locator("#tabs button[data-tab='clips']").click();

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
    console.log("PASS: canvas cards, wires, guide, card prompt version, saved card position, a pose drawn from a still "
      + "and given a take's last frame, still overlay, take decision, stale render, render job, clip frame adopted as a still, "
      + "silence overlay preview, prompt version");
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
