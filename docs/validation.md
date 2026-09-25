# Reference validation

Local reference: 2026-09-14–15, Windows, Python 3.12, Node 22, headless Microsoft Edge.
This records observed checks, not a completed public CI run or cross-platform support claim.

- Fresh repository-local virtual environment installed with `.[qa,dev]`.
- Python suite after layout repair: 31 passed, 1 skipped. The skipped case needs permission to create
  symlinks on Windows; direct traversal/foreign absolute path cases passed.
- Browser authoring journey: discover example frames, run QA, select a node,
  change label/timing/loop mode, save, reject missing frames without losing the
  previous file, reload, validate, and preview the last-frame hold.
- Direct KTX2 browser journey: decode visible pixels, play multiple frames,
  reject graph writes, retain the original runtime graph. Passed with the checked-in
  geometric runtime example and a separately installed Amadeus character pack.
- Real KTX-Software 4.4.2 export: three clips / nine frames. The result passed both
  this repository's validator and the current Amadeus checkout's original validator.
- Browser vendor check: the KTX2 shim/decoder match the pinned npm 0.0.22 package.
- Built wheel installed with `--no-deps` into a second clean virtual environment.
  OpenCV and NumPy were absent. Direct KTX2 decode/playback and read-only checks
  passed using only that installed wheel's code and bundled JS/WASM.

Unit export tests use an encoder stub to exercise errors and staging deterministically;
the real encoding and decode checks above cover the actual media path separately.

## Reproduce

```powershell
python -m pip install -e ".[qa,dev]"
python -m pytest -q
npm ci
npx playwright install chromium
npm run test:ui
node tools/ktx_smoke.cjs
python tools/revendor_pixi_basis_ktx2.py --check
python -m pip wheel . --no-deps --wheel-dir dist
```

For an existing Edge installation, set `BROWSER_CHANNEL=msedge`. Set
`SPRITEFORGE_PYTHON` to the installed Python interpreter when it is not the `python`
on PATH. The authoring UI smoke uses a temporary demo workspace and removes only
that test directory. KTX smoke accepts an optional pack path and never saves it.

Test screenshots go into ignored `test-results/`. Selected reviewer screenshots
are published under `docs/images/`; source character packs are not included. `examples/minimal/` and
`examples/runtime-minimal/` contain only the generated geometric demo.

Long sessions, full TTS behavior, mouth-overlay export, non-UASTC texture variants
and wallpaper scenario graphs are outside this acceptance scope.

## Graph viewport repair (2026-09-15)

Runtime packages omit authoring layout. The reviewer accepts the original authoring
graph via --layout or the exported sibling .graph-layout.json, validates exact node
identities, and preserves its coordinates. Browser checks cover all-node fit,
expanded canvas, wheel zoom, and exact coordinate preservation. The application
never substitutes a three-column or automatic layout for the creator's saved wiring.

## Public source candidate (2026-09-15)

- Current Python regression suite: 31 passed, 1 Windows symlink-capability skip.
- Source distribution contains the contribution guide, schemas, PNG and KTX2
  examples, layout companion, and browser test tools.
- A new virtual environment installed the built wheel with `--no-deps`. From the
  extracted source distribution, KTX2 playback, graph fit/zoom and exact saved
  coordinates passed with that installed wheel; no OpenCV/NumPy was present.
- A fresh demo workspace exported three clips / nine KTX2 frames with the real
  encoder, retaining the layout companion; the exported pack passed validation.
- Tracked media consists only of the generated example PNG/KTX2 files. Browser
  decoder bytes in the wheel match the recorded vendor hashes.

The workflow records current Windows/Ubuntu results remotely. Consult the run for
the revision being evaluated; these local checks do not substitute for a remote run.

## Production pipeline (2026-09-25)

Local: Windows, Python 3.12, FFmpeg 9.0.2, KTX-Software 4.4.2, Edge (Playwright).

- Python suite: 56 passed, 1 Windows symlink-capability skip. Production tests use
  generated geometric figures, a white-key alpha processor and a linear interpolation
  processor (`tests/processors/`), and cover still framing and geometry gates, rigid
  registration versus kept framing, take decisions and archive, prompt versions and
  placeholders, prepare hand-off, render registration/locks/timing/pingpong, camera
  drift, FFmpeg decode, graph-sync, the export gate and the HTTP API.
- Providers were exercised only against a local fake of the Wan 2.7 (DashScope) and
  Seedance (Ark) task APIs: request shape, headers, polling, immediate download,
  recorded failures, resume and missing keys. No paid request was sent.
- `tools/production_smoke.cjs`: still overlay, take decision, stale render, render
  job and prompt version in the production page.
- A synthetic production-bound graph exported with the real encoder passed this
  repository's validator and Amadeus `tools/validate_character_pack.py`.

Read-only check on the shipped Kurisu sources (copies in a scratch workspace):

- Base still: the idle default frame placed 1:1 gives head top 20 and head centre
  387.8. The shy expression still registered rigidly (1118/1200 matches) and passed.
  Serious, thinking and side stills are pose changes (245, 109 and 36/1200 matches):
  kept framing measured head centre 393.7, 392.7 and 374.6 (side head top 37), which
  were recorded as intended offsets.
- Real Wan takes (818×1124, 30 fps) register to the stills at scale 0.896 with head
  and tail agreeing within 0.3% for shy, thinking, side and the shy loop. The
  `speaking_trans` source disagrees by 3%: the clip that previously needed a manual
  affine calibration.
- `kurisu_shy_trans.mp4` rendered end to end with `tools/processors/anime_seg_alpha.py`
  on CPU (60 frames, 96 s): drift 0.1%, QA pass, alpha masks within IoU 0.989–0.999
  of the historical production frames.
- The idle pingpong source (24 fps) rendered with QA fail: matting leaked into the
  source's dark border on 12 frames, so the character touched closed canvas edges,
  and the export gate refused the graph. This is the defect the earlier
  `repair_alpha_edge_leaks.py` treated. `edgeGuardPx 16` (the earlier repair width)
  passed QA; the two-clip graph (120 frames, idle 42 ms loop, shy entry 8 ms at 4×
  speed) exported with the real encoder and passed Amadeus
  `tools/validate_character_pack.py`.
- `gmfss_interpolate.py` was not run (it needs CUDA and the GMFSS weights).

Mouth overlays (2026-09-26), on the same scratch copies:

- The real `kurisu_shy_speaking_loop.mp4` (90 frames) rendered as `shy_speaking1`
  with the default shared closed mouth (the idle still). The mouth was found by
  motion at (5.0, −191.5), 34.4 × 19 px; the shipped hand-tuned profile has
  (4.27, −192.85), 34 × 20.2. Tracking correlation 0.995; the head does not move in
  this loop (the shipped track is also constant).
- Pasting the idle closed mouth as is left a visible pale oval on the blushing shy
  face. The render shifted it by L* +3.7, b* +2.5 inside the mask, which removed the
  oval in the runtime-style composite of the three most open frames.
- The three-clip pack (210 frames plus one mouth overlay) passed Amadeus
  `tools/validate_character_pack.py`, and Amadeus's own `SpriteForgeAnimator`, started
  on that pack with a probe engine, loaded the `shy_speaking1` profile as a
  `silence_close` config with the overlay KTX2, its source anchor and 90-frame anchor
  and openness tracks.
