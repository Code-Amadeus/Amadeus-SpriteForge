# Studio preview recording

- `production-pipeline.gif`: 1070 × 800, 96 frames at 8 fps, approximately
  12 seconds and 1.3 MB, looping.
- `production-pipeline-poster.png`: full Studio clip view. `studio-preview.png`
  crops to the working panel so the character and text remain readable.
- Source: the actual `/studio` interface in Microsoft Edge through Playwright,
  using only the public stills in `examples/references/kurisu/`. The short frame
  sequences blend those stills; they are demonstration inputs, not model output.
- Scenes: clip comparison (3 s), processed candidate and QA (2 s), adopted
  material library (1.5 s), graph and exact clip player (2.5 s), and a local
  reverse/preview/save-candidate node workflow (3 s).
- The recording really adopts the processed candidate through the UI. The
  workflow confirms zero paid requests and leaves the destination's previously
  adopted take unchanged. No provider, private legacy video or account is used.
- Capture uses a 1280 × 800 CSS viewport at 1.5 device scale. The animation crops
  the sidebar, retains the breadcrumb/view switch, and uses a shared 224-color
  palette with Bayer dithering. Scene timing is edited for a short walkthrough.
- Reproduce with `tools/studio_docs_demo.py` and `tools/record_studio_docs.cjs`.
  They create an isolated workspace under ignored `test-results/` and replace
  the documentation media. Set `SPRITEFORGE_PYTHON` and, on Windows,
  `BROWSER_CHANNEL=msedge`; FFmpeg must be available.

Character artwork retains the provenance described in [NOTICE.md](../../NOTICE.md).
