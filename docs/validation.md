# Reference validation

Local reference: 2026-09-14–15, Windows, Python 3.12, Node 22, headless Microsoft Edge.
This records observed checks, not a completed public CI run or cross-platform support claim.

- Fresh repository-local virtual environment installed with `.[qa,dev]`.
- Python suite: 28 passed, 1 skipped. The skipped case needs permission to create
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

Browser screenshots go into ignored `test-results/`. Personal character screenshots
and media are not part of the repository. `examples/minimal/` and
`examples/runtime-minimal/` contain only the generated geometric demo.

Long sessions, full TTS behavior, mouth-overlay export, non-UASTC texture variants
and wallpaper scenario graphs are outside this acceptance scope.
