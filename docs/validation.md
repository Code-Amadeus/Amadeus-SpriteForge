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

## Legacy Kurisu import (2026-09-26)

Read-only inputs: the legacy SpriteForge workspace and the shipped Amadeus pack
(version 2026.08.29: 39 clips, 7552 frames, 16 mouth overlays). The import ran into
a scratch workspace; one interrupted session was resumed by running `apply` again.

- Python suite: 68 passed, 1 Windows symlink-capability skip. The importer tests build
  a small legacy workspace and pack. They cover:
  - an unencoded decoy variant, and an encoded one whose leftover texture differs;
  - wide and short clips;
  - expression and offset poses;
  - shared and own-frame closed mouths;
  - a runtime-only clip and a jump edge;
  - resuming;
  - the export gate.
- `plan` resolved all 39 clips. Two closed-eye speaking loops had two encoded
  variants; the leftover `refbottom_trans_blend` sidecar texture differs from the
  shipped one, which settled them on `frames_alpha_2x_gmfss`. The resolved variants
  match the Amadeus packager's label tables:
  - the aligned `idle_closed_eye`;
  - `frames_alpha` for the fast emotion entries;
  - the tail-fixed ghost-trail `trans_standby`;
  - the smile/sad post-speech roots.
- Poses: 11 (idle, standby, smile, serious, sad, thinking, key_point, shy, surprise,
  angry, closed_eye). One edge was reported: `key_point_speaking -> thinking_speaking1`
  moves the head top −4 px, beyond the ±3 px tolerance.
- All 7552 rendered frames are pixel-identical to their legacy sources: idle2,
  trans_smile and smile are padded at the top by 2/1/1 rows, and idle_closed_eye keeps
  its 960 px width as a 98 px margin. All 39 clips keep the shipped phase, frame
  interval, loop mode and frame count.
- Clip QA: 26 pass, 11 watch, 2 fix, none fail.
  - Watch: head seams to the pose still (1.2–1.8 L*), the idle2 span, and a flash in
    the ghost-trail transition.
  - Fix: shy_trans and closed_eye_trans start 1.9–2.0 L* away from the idle still.
- Graph QA over 64 edges: 50 pass, 9 watch, 4 fix, 1 fail.
  - Fix: idle into trans_smile, shy_trans, surprise_trans and closed_eye_trans, at
    1.8–2.2 L*.
  - Fail: the key_point jump (3.8 L*, −4 px). Export stays blocked until it is
    resolved.
- Mouths: 12 speaking loops keep an own closed frame (key_point_speaking frame 154)
  and 4 use the shared idle still, as shipped.
  - The first pass fell back to the expected position on four loops, because moving
    hair at the sides of the search window outweighed the mouth. On the thinking pose
    that position sits 23 px below the mouth. Detection now lets only mouth-plausible
    regions compete, and all 16 loops track by motion.
  - Where the shipped profile was tuned (speaking_loop1, thinking_speaking1,
    shy_speaking1, surprise_speaking), detection agrees within 1 px.
  - Three shipped profiles kept the untuned default (4, −196) and are off the mouth in
    the motion map: speaking_loop2, thinking_speaking2 and key_point_speaking. The
    import places them on it.
- Real export of a subset (idle, shy_trans and shy_speaking1 with the shared closed
  mouth, plus the runtime clips smile and sad): 5 clips, 600 frames and one mouth
  overlay, encoded with KTX-Software 4.4.2 in 204 s.
  - The pack passed this repository's validator and Amadeus
    `tools/validate_character_pack.py`.
  - Amadeus's `SpriteForgeAnimator`, started on the pack with a probe engine, loaded
    `shy_speaking1` as a `silence_close` config (overlay KTX2, 180-frame anchor track).
  - It added smile and sad to its graph as runtime post-speech nodes from the
    manifest.

## End poses adopted from transitions (2026-10-01)

A transition set to `lastFrame none` is generated from its first frame alone, and a
frame of one of its takes becomes the end pose's still (`production take adopt`).

- Python suite: 71 passed, 1 Windows symlink-capability skip. The new tests cover:
  - loops refusing `lastFrame none`, and the hint when an end still is missing;
  - `prepare` without `last.png`, and takes recording that no last frame was sent;
  - the base pose and out-of-range frames refused;
  - a pose change adopted with the take's framing, approved, and rendered with drift
    below 0.2% and 0.5 px and a passing tail seam;
  - pre-placed frames on a widened canvas keeping their pixels, through a page job;
  - Wan and Seedance first-frame-only requests against the local fake APIs.
- `tools/production_smoke.cjs` (Edge): **Last frame → smile still** on a transition
  take adds a candidate still to the smile pose.
- No paid request was sent. The first-frame-only request shapes follow the providers'
  documentation: Wan 2.7 lists `first_frame` alone as first-frame-to-video, and Ark
  takes one `image_url` with role `first_frame`.

Real takes, in scratch workspaces holding the shipped idle still. Matting ran on CPU
through `tools/processors/anime_seg_alpha.py` with a scratch copy of the
anime-segmentation code and weights.

| Take (60 frames, 818×1124, 30 fps) | Adopted frame 59 | Against the shipped still | Render, locks 6 + 12 |
| --- | --- | --- | --- |
| `kurisu_shy_trans.mp4` (expression change) | `registration`, QA pass, 14 s | head top 20 / 19, centre 387.55 / 387.69, alpha IoU 0.991 | drift 0.04%, (−0.43, 0.39) px; head and tail seams 0.0 L*; QA pass; 79 s |
| `kurisu_thinking_trans.mp4` (pose change) | `clip` (93/1128 matches agree), head centre +4.72 px, recorded as the pose's offset, 16 s | head top 23 / 23, centre 392.48 / 392.91, alpha IoU 0.995 | drift −0.013%, (0.26, 0.04) px; head and tail seams 0.0 L*; QA pass; 81 s |

The shipped stills came from the earlier chain alignment, in which the loops were
aligned to these transitions' last frames. Adopting the same frames reproduces those
placements within 1 px.
