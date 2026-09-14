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
