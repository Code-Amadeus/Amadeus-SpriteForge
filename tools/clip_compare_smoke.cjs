"use strict";
// Native media evidence: immutable raw takes, display transforms and asynchronous playback.
// All assets and records are synthetic; this never invokes a paid provider.
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawn, spawnSync } = require("node:child_process");

(async () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "spriteforge-compare-"));
  const python = process.env.SPRITEFORGE_PYTHON || "python";
  const fixture = spawnSync(python, [path.join(__dirname, "..", "tests", "production_demo.py"), path.join(temporary, "demo")], { encoding: "utf8", windowsHide: true });
  assert.equal(fixture.status, 0, fixture.stderr);
  const workspace = fixture.stdout.trim().split(/\r?\n/).pop();
  const pattern = spawnSync(python, ["-c", `
import sys
import shutil
import subprocess
from pathlib import Path
import cv2
import numpy as np
from spriteforge.production.project import add_clip
from spriteforge.production.clips import import_clip_take
from spriteforge.production.render import render_take
root=Path(sys.argv[1])
add_clip(root,"compare_scale","idle","idle")
for multiplier in (1,2):
    folder=root.parent/str(multiplier)
    folder.mkdir(exist_ok=True)
    for index in range(12):
        image=np.full((240,160,3),(30,40,20+15*index),np.uint8)
        image[60:180,40:120]=(180,190,200)
        image=cv2.resize(image,(160*multiplier,240*multiplier),interpolation=cv2.INTER_NEAREST)
        cv2.imwrite(str(folder/f"{index:04d}.png"),image)
    import_clip_take(root,"compare_scale",folder,fps=30)
video=root.parent/"compatible.mp4"
subprocess.run([shutil.which("ffmpeg"),"-loglevel","error","-y","-framerate","30","-i",str(root.parent/"1"/"%04d.png"),"-c:v","libx264","-pix_fmt","yuv420p",str(video)],check=True)
import_clip_take(root,"compare_scale",video)
candidate=import_clip_take(root,"smile_talk",root.parent/"smile_talk",fps=30,note="unrelated raw candidate")
render_take(root,"smile_talk",candidate["id"],log=lambda *_:None)
import_clip_take(root,"smile_talk",root.parent/"smile_talk",fps=30,note="not processed")
`, workspace], { encoding: "utf8", windowsHide: true });
  assert.equal(pattern.status, 0, pattern.stderr);
  const server = spawn(python, ["-m", "spriteforge", "review", "--workspace", workspace, "--port", "0", "--no-browser"], { windowsHide: true });
  let browser, page;
  try {
    const url = await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error("Editor startup timed out")), 15000);
      server.stdout.on("data", (chunk) => { const match = String(chunk).match(/http:\/\/127\.0\.0\.1:\d+/); if (match) { clearTimeout(timeout); resolve(match[0]); } });
      server.on("error", reject); server.on("exit", (code) => reject(new Error(`Editor exited ${code}`)));
    });
    browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || undefined });
    page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    const errors = []; page.on("pageerror", (error) => errors.push(error.message));
    await page.goto(url + "/studio#/overview");
    await page.waitForFunction(() => Boolean(window.SFClipCompare));
    const mount = async (clipId, pair = true, takeIndex = 0, candidatePreview = false) => page.evaluate(async ({ clipId, pair, takeIndex, candidatePreview }) => {
      if (window.compareProof) window.compareProof.cleanup();
      const state = await SFStudio.api("/api/production");
      const clip = state.clips.find((entry) => entry.id === clipId);
      const root = document.createElement("div"); root.style.cssText = "height:650px;padding:12px";
      document.querySelector("#studioMain").replaceChildren(root);
      const ctx = { root, state, jobs: [], t: SFStudio.t, h: SFStudio.h, api: SFStudio.api, toast: SFStudio.toast };
      const takeA = clipId === "compare_scale" ? clip.takes.find((take) => takeIndex === -1 ? take.media.video : take.media.dir && take.media.width === 160)
        : takeIndex === 2 ? clip.takes.find(take => take.note === "not processed")
        : takeIndex === 1 ? clip.takes.find((take) => take.note === "unrelated raw candidate") : clip.takes.find((take) => take.status === "accepted") || clip.takes[0];
      const takeB = pair ? clipId === "compare_scale" ? clip.takes.find((take) => take.media.dir && take.media.width === (takeIndex === -1 ? 160 : 320)) : clip.takes.find(take => take.status === "accepted") : null;
      window.compareProof = SFClipCompare.mount(ctx, { clip, takeA, takeB, candidatePreview });
    }, { clipId, pair, takeIndex, candidatePreview });
    const drawn = async (frame) => page.waitForFunction((index) => {
      const root = document.querySelector(".clip-compare");
      return root && Number(root.dataset.frame) === index && root.querySelector("canvas").width > 1;
    }, frame);
    const pixel = async (pane = 0) => page.evaluate((index) => {
      const canvas = document.querySelectorAll(".compare-frame canvas")[index];
      return [...canvas.getContext("2d").getImageData(10, 10, 1, 1).data];
    }, pane);

    await mount("compare_scale"); await drawn(0);
    await page.getByLabel("Head guides", { exact: true }).uncheck();
    await page.evaluate(() => compareProof.seek(5)); await drawn(5);
    assert.equal((await pixel())[0], 95);
    assert.deepEqual(await page.locator(".compare-frame canvas").evaluateAll((canvases) => canvases.map((canvas) => [canvas.width, canvas.height])), [[160, 240], [320, 480]]);
    await page.getByRole("button", { name: "Difference", exact: true }).click();
    await page.waitForFunction(() => document.querySelector(".clip-compare").dataset.mode === "difference");
    assert.deepEqual(await pixel(), [0, 0, 0, 255], "Distinct resolutions share one display scale and preserve the full frame");
    assert.deepEqual(await page.locator(".compare-frame canvas").first().evaluate((canvas) => [canvas.width, canvas.height]), [320, 480]);
    await page.getByRole("button", { name: "Overlay", exact: true }).click();
    await page.waitForFunction(() => document.querySelector(".clip-compare").dataset.mode === "overlay");
    assert.equal((await pixel())[0], 95);
    await page.getByRole("button", { name: "Onion skin", exact: true }).click();
    await page.waitForFunction(() => document.querySelector(".clip-compare").dataset.mode === "onion");
    assert.ok((await pixel())[3] > 0);

    // Delay actual local PNG responses past a frame interval. In-flight paints must
    // complete, with their HUD/datasets describing exactly those displayed pixels.
    await page.getByRole("button", { name: "Side by side", exact: true }).click();
    await page.route("**/api/production/media?path=*", async (route) => {
      if (decodeURIComponent(route.request().url()).includes("/compare_scale/")) await new Promise((resolve) => setTimeout(resolve, 120));
      await route.continue();
    });
    await mount("compare_scale"); await drawn(0);
    await page.getByLabel("Head guides", { exact: true }).uncheck();
    await page.evaluate(() => {
      window.paintSamples = []; let previous = null;
      const record = () => {
        const root = document.querySelector(".clip-compare");
        if (!root) return;
        const frame = Number(root.dataset.frame);
        if (frame !== previous && Number.isFinite(frame)) {
          const canvas = root.querySelector("canvas");
          paintSamples.push({ frame, red: canvas.getContext("2d").getImageData(10, 10, 1, 1).data[0] }); previous = frame;
        }
        window.sampleRequest = requestAnimationFrame(record);
      };
      record(); compareProof.togglePlay();
    });
    await page.waitForFunction(() => paintSamples.length >= 5 && new Set(paintSamples.map((sample) => sample.red)).size >= 3, null, { timeout: 12000 });
    const samples = await page.evaluate(() => { compareProof.togglePlay(); cancelAnimationFrame(sampleRequest); return paintSamples; });
    for (const sample of samples) assert.equal(sample.red, 20 + 15 * sample.frame, "Painted pixels and displayed frame index stay synchronized under slow decode");
    await page.unrouteAll({ behavior: "wait" });

    // Actual video decode and a raw PNG take use one clock; stepping does not reuse
    // frames from another seek in the video cache.
    await mount("compare_scale", true, -1); await drawn(0);
    const initial = await page.locator(".compare-frame canvas").first().evaluate((canvas) => canvas.toDataURL());
    await page.evaluate(() => compareProof.seek(10)); await drawn(10);
    assert.equal(await page.locator(".clip-compare-video").count(), 1);
    assert.notEqual(await page.locator(".compare-frame canvas").first().evaluate((canvas) => canvas.toDataURL()), initial);
    assert.deepEqual(await page.locator(".compare-frame canvas").evaluateAll((canvases) => canvases.map((canvas) => Number(canvas.dataset.frame))), [10, 10]);
    await page.evaluate(() => compareProof.step(-1)); await drawn(9);
    await page.evaluate(() => compareProof.seek(0)); await drawn(0);
    assert.equal(await page.locator(".compare-frame canvas").first().evaluate((canvas) => canvas.toDataURL()), initial);
    // Onion skin also decodes neighboring video frames. Quantized frame-start
    // timestamps must not strand a pending read on the preceding native frame.
    await page.evaluate(() => compareProof.seek(1)); await drawn(1);
    await page.getByRole("button", {name:"Onion skin",exact:true}).click();
    await page.waitForFunction(()=>document.querySelector(".clip-compare").dataset.mode === "onion");
    await page.getByRole("button", {name:"Side by side",exact:true}).click();
    await page.evaluate(()=>compareProof.seek(2));await drawn(2);
    assert.ok(Math.abs((await pixel())[0]-50)<=5,"Presented video frame 2 matches the synthetic frame pixels despite timestamp rounding");

    // QA/mouth records are output-frame facts. They appear only after explicitly
    // choosing a matching render, never on an unrelated candidate or raw take.
    await mount("smile_talk", false); await drawn(0);
    assert.equal(await page.locator(".compare-marker").count(), 0);
    await page.getByLabel("Render preview", { exact: true }).check();
    await page.waitForFunction(() => document.querySelector(".compare-marker.mouth"));
    assert.equal(await page.locator(".compare-marker.mouth").count(), 1);
    await mount("smile_talk", false, 1); await drawn(0);
    await page.getByLabel("Render preview", { exact: true }).check();
    await drawn(0);
    assert.equal(await page.locator(".compare-marker").count(), 0);
    assert.ok((await page.locator(".compare-source-label").first().innerText()).includes("Raw take"));

    // Explicit candidate output carries only that take's processed QA. B remains
    // the immutable raw accepted take until its published preview is requested.
    await mount("smile_talk", true, 1, true); await drawn(0);
    assert.ok((await page.locator(".compare-source-label").first().innerText()).includes("Candidate processed preview"));
    assert.ok((await page.locator(".compare-source-label").nth(1).innerText()).includes("Raw take"));
    assert.equal(await page.locator(".compare-marker.mouth").count(), 1);
    await page.getByLabel("Published B render", { exact: true }).check(); await drawn(0);
    assert.equal(await page.locator(".compare-marker.mouth").count(), 2);
    await page.evaluate(() => SFStudio.api("/api/production/clip-settings", { clip: "smile_talk", changes: { speed: 1.1 } }));
    await mount("smile_talk", true, 1, true); await drawn(0);
    assert.ok((await page.locator(".compare-source-label").first().innerText()).includes("Stale processed preview"));
    assert.ok((await page.locator(".compare-source-label").nth(1).innerText()).includes("Raw take"));
    await mount("smile_talk", false, 2, true);
    await page.waitForFunction(() => document.querySelector(".compare-media-message")?.textContent.includes("Candidate processed preview unavailable"));
    assert.equal(await page.locator(".compare-marker").count(), 0);
    assert.ok((await page.locator(".compare-source-label").first().innerText()).includes("Candidate processed preview unavailable"));
    await page.evaluate(() => compareProof.cleanup());
    assert.equal(await page.locator(".clip-compare-video").count(), 0);
    assert.deepEqual(errors, []);
    console.log("PASS: raw PNG/video A/B, shared display scale, modes, delayed-frame playback, exact stepping, published/candidate QA provenance, current/stale/missing candidate output and cleanup");
  } finally {
    if (browser) await browser.close();
    server.kill();
    const resolved = path.resolve(temporary);
    assert.ok(resolved.startsWith(path.resolve(os.tmpdir()) + path.sep));
    fs.rmSync(resolved, { recursive: true, force: true });
  }
})().catch((error) => { console.error(error); process.exit(1); });
