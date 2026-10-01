# Production preview recording

- `production-pipeline.gif`: 960x648, 96 frames, approximately 12 seconds, looping,
  approximately 5.8 MB. The 48 px title strip labels the four scenes.
- `production-pipeline-poster.png`: original 1440x900 browser screenshot of the
  production canvas, offered as a static alternative and for reading the UI text.
- Source: the real SpriteForge `/production` page in Microsoft Edge, recorded on
  2026-10-01 with Playwright video capture. It uses the existing neutral idle and
  closed-eye smile stills, plus the Wan 3.0 transition and loop described in
  [the validation record](../validation.md#wan-30-through-the-cli-on-account-credits-2026-10-01).
  The matching current stills are published under `examples/references/kurisu/`.
- The recording uses a copy of that workspace with the current prompt library
  switched to `live2d-idle.en.json` and the walkthrough's English action blocks.
  The existing takes keep their original Chinese prompt snapshots; the recording
  does not claim that the English template generated those earlier videos.
- Views: production canvas (2 s), still comparison (4 s), transition preview (3 s),
  loop preview and QA (3 s). Comparison switches between base, take and overlay.
  The transition passes QA; the loop's head-motion `watch` remains visible.
- Processing: trim the captures to these scenes, scale, add the scene title strip,
  and encode with FFmpeg at 8 fps using a shared 224-color palette and Bayer
  dithering. The source media and QA results are not regenerated or replaced.
- This records review of already generated takes. It does not show generation
  happening in 12 seconds, and no provider calls were made for the recording.

The captured character artwork follows the same provenance distinction as the
other reviewer screenshots and published reference stills; see [NOTICE.md](../../NOTICE.md).
