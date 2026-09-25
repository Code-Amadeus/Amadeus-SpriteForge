# Production pipeline

SpriteForge produces a character's animation clips from one idle reference image:

```text
idle master ──measure──► character contract (canvas, head anchors, tolerances)
   │
   ├─► pose stills: generate or import ─► normalise onto the canvas ─► geometry QA ─► approve
   │
   └─► clips between poses:  transition A→B (first = A still, last = B still)
                             loop B→B (first = last = B still)
                             out B→A (optional)
        each generation is a take (prompt snapshot, inputs, provider task)
        review: use / reject and archive / restore
          ▼ accepted take
        render: decode ─► register both ends to the stills ─► pingpong ─► interpolate
                ─► alpha ─► edge guard ─► lock ends to the stills ─► QA ─► publish
          ▼
        behavior graph (review page) ─► KTX2 character pack for Amadeus
```

Everything lives in the authoring workspace under `production/`. The review page
(`spriteforge review --workspace W`) gains a **Production** page at `/production`;
every operation is also a `spriteforge production ...` command. Production and QA
need the `qa` extra (OpenCV, NumPy) and FFmpeg for video takes.

## Invariants

1. **Approved pose stills are the only geometric authority.** Each clip endpoint is
   registered, and optionally locked, to the still of its pose, so two clips meeting
   at a pose share endpoint geometry by construction. This replaces chains such as
   "align the loop to the processed tail of the transition" and per-clip calibration.
2. **Takes are immutable and never deleted.** A take keeps its media, the exact first
   and last frame images, the rendered prompt with block versions, and the provider
   task. Decisions only change which take a pose or clip accepts, or mark a take
   rejected with a reason; rejected takes remain in the archive.
3. **Prompts are versioned data.** Editing a block adds a version. A prompt that still
   contains `{{PLACEHOLDER: ...}}` never reaches a paid provider.
4. **Timing and variant choice are explicit clip fields.** Interpolation, playback
   speed and loop mode are recorded in the clip and its `render.json`; nothing is
   inferred from label names.
5. **Heavy models stay outside.** Alpha matting and frame interpolation are external
   commands with a directory-in/directory-out contract. SpriteForge orchestrates them,
   checks their output and records the result; it ships no weights or GPU code.

## Workspace layout

```text
production/
  character.json      canvas, base pose, background, cut edges, framing, tolerances, anchors
  prompts.json        versioned prompt blocks and templates
  tools.json          ffmpeg, alpha/interpolate commands, provider endpoints (no keys)
  poses/<pose>/pose.json                       accepted take, intended head offset
  poses/<pose>/takes/<take>/source.*, still.png, take.json
  clips/<clip>/clip.json                       from, to, phase, generation, processing, playback
  clips/<clip>/takes/<take>/media.mp4 | frames/, first.png, last.png, take.json
  clips/<clip>/output/<phase>/*.png, render.json   stable graph root of the clip
```

Writes are atomic and flushed (a power loss leaves the previous file, not a
truncated one). A render is staged in a hidden directory and swapped in whole.
Review discovery lists only `production/clips/<clip>/output/<phase>` folders.

## Character contract

`production init --canvas WxH` fixes the runtime frame size. The base pose (default
`idle`) is placed by explicit framing: centred, visible width 71% of the canvas and
head top at 2% of its height — the framing of the shipped Kurisu pack. Pass
`--place SCALE,DX,DY` to place a master exactly (`1,0,0` keeps a canvas-sized image).

Approving the base still measures the anchors every other still is checked against:

| Anchor | Meaning |
| --- | --- |
| `headTopY` | first row with alpha > 128 |
| `headCenterX` | mean x of the head band (4% of the canvas height below the head top) |
| `area` | visible pixel count |

`cutEdges` (default `bottom`) are the canvas edges a half-body portrait may cross;
touching any other edge fails QA. Tolerances default to 3 px for head top and head
centre and 15% for area. Re-approving the base still marks other stills for re-check.

## Pose stills

`production take import --pose P IMAGE` keeps the source, mattes it with the alpha
processor when it has no transparency, then normalises it onto the canvas:

| Method | When |
| --- | --- |
| `framing` | base pose |
| `registration` | the image is a rigid copy of the base still (≥ 50% of feature matches agree): an expression edit that the generator shifted or scaled is moved back |
| `fit` | the pose changed, so a whole-image transform would be wrong: the generator's framing is kept and QA asks for an overlay check |
| `placement` | explicit `--place SCALE,DX,DY` |

The rigid threshold is calibrated on the real Kurisu stills: an expression edit keeps
93% of matches; lean, thinking and side poses keep 3–20%, and forcing a registration
there scaled the side pose by 9% and moved it 108 px.

A pose whose head legitimately moves records an intended offset:
`production pose expect P --head-top Y --head-center X`. On Kurisu these are the
serious pose (head centre ≈ 393), thinking (≈ 392, top 23) and side (top 37, centre ≈ 375).
Approval re-runs QA and refuses a still that fails.

`production prepare --pose P --output DIR` writes the flattened base still and the
rendered prompt for an external image editor.

## Clips and takes

`production clip add ID --from A --to B` plans a clip. `A == B` is a loop; otherwise a
transition. Phase defaults to `loop`, `out` (ending on the base pose) or `in`.

| Setting | Default (transition / loop) | Effect |
| --- | --- | --- |
| `generation.provider` | `manual` | `manual`, `wan`, `seedance` |
| `generation.durationS` | 2 / 4 | seconds requested |
| `generation.inputScale` | 1.0 | shrink the subject inside provider inputs to leave a safety margin |
| `processing.interpolate` | 1 | frame multiplier from the interpolate processor |
| `processing.pingpong` | off | loops only: play forward then backward |
| `processing.lockHeadFrames` | 6 / 0 | frames blended into the start still (first frame exact) |
| `processing.lockTailFrames` | 12 / 0 | frames blended into the end still (last frame exact) |
| `processing.edgeGuardPx` | 0 | clear alpha near closed canvas edges |
| `playback.speed` | 1.0 | playback multiplier |
| `playback.loopMode` | `once_then_hold` / `loop` | runtime loop mode |

`frameIntervalMs = round(1000 / (source fps × interpolate × speed))`. The Kurisu pack
used 30 fps × 2 → 17 ms loops, 24 fps × 2 → 21 ms idle, and transitions at 2–4× speed
(8 ms / 5 ms).

Takes come from three places:

- **Manual**: `production prepare --clip C --output DIR` writes `first.png`, `last.png`
  and the prompt; generate in any tool, then `production take import --clip C VIDEO`
  (or a PNG folder with `--fps`). The inputs are recorded as assumed.
- **Provider**: `production generate --clip C [--dry-run] [--no-wait]` submits the
  opaque first/last frames and the rendered prompt, records the task id before
  waiting, downloads the result immediately and stores it as a candidate take.
  `production take resume --clip C TAKE` continues a submitted task.
- **Upload** on the Production page.

`production take accept|reject|restore (--pose P | --clip C) TAKE [--reason TEXT]`
decides. Accepting a different take, changing clip settings or re-approving a still
makes the clip's render stale.

## Prompts

`prompts.json` holds blocks with append-only versions and templates that order them:

| Template | Blocks |
| --- | --- |
| `still` | `character` + `still.edit` + pose subject (negative: `still.negative`) |
| `transition` | `character` + `video.invariants` + `video.transition` + clip subject (negative: `video.negative`) |
| `loop` | `character` + `video.invariants` + `video.loop` + clip subject (negative: `video.negative`) |

Each pose and clip gets its own subject block (`pose.<id>`, `clip.<id>`). Blocks may use
`${character}`, `${pose}`, `${description}`, `${from}`, `${to}` and `${duration}`; an
unknown variable is an error. Every block starts as a placeholder. `production prompt
set BLOCK --text ...` (or the Prompts tab) adds a version; `production prompt render
--clip C` shows the exact text. The Prompts tab shows how many takes used each version.

## Rendering

`production render --clip C` (or `--stale`, or the page) renders the accepted take:

1. Decode with FFmpeg and an explicit BT.709 limited-to-full conversion.
2. Register frame 0 to the start still and the last frame to the end still (ORB +
   RANSAC similarity), interpolating the transform across the clip.
3. Pingpong, then run the interpolate processor (`N × factor` frames for loops,
   `(N − 1) × factor + 1` for transitions).
4. Run the alpha processor (skipped only for native-alpha frames without interpolation).
5. Apply the edge guard, blend the locked frames into the stills, write
   `output/<phase>/000000.png…` and `render.json`, run QA and publish.

Processor contract (`production/tools.json`):

```json
{
  "alpha": {"command": ["C:/tools/venv/python.exe", "tools/processors/anime_seg_alpha.py", "{input}", "{output}",
                        "--repo", "C:/tools/anime-segmentation", "--checkpoint", "C:/tools/anime-segmentation/isnetis.ckpt"]},
  "interpolate": {"command": ["C:/tools/venv/python.exe", "tools/processors/gmfss_interpolate.py", "{input}", "{output}",
                              "{factor}", "{wrap}", "--gmfss", "C:/tools/GMFSS"]}
}
```

The alpha processor must keep file names and sizes and return RGBA; the output of
both is checked before use. `anime_seg_alpha.py` reproduces the matting of the Kurisu
production batch and was run on CPU against a real take. `gmfss_interpolate.py`
follows the Kurisu GMFSS build but needs CUDA and was not exercised by these tests.

## QA

QA runs on the PNG sources; levels are pass < watch < fix < fail and only fail blocks
export.

| Check | Rule |
| --- | --- |
| still canvas / edges | exact canvas; only cut edges may be touched |
| still head anchors | within tolerance of the base anchors or the pose's intended offset |
| still framing | `fit` stills are watch until the overlay is confirmed |
| clip broken frame | visible area changes by more than 12% between frames |
| clip flash | lower-face lightness jumps by more than 3 L* between frames (watch) |
| clip drift | head vs tail registration: scale ≥ 1% or shift ≥ 4 px watch, ≥ 3% / 12 px fail |
| head / tail seam | first/last frame vs its still: head anchors within tolerance; L* graded as a graph edge |
| loop wrap | last → first: L* 1.0 / 1.5 / 2.2 (watch / fix / fail), head anchors within tolerance |
| graph edge | source tail → target head of bound nodes: L* 1.2 / 1.8 / 2.5, head anchors within tolerance |
| bound node | render missing or stale, node timing differs from `render.json`, clip QA failed |

Lightness is the mean L* of visible pixels in the lower face (from 24% to 30% of the
canvas height below the head top, ±5% of its width around the head centre), placed
by the head anchors of the reference frame. On the shipped Kurisu sources this ROI
reproduces the earlier seam baseline: idle → speaking_trans 1.56 (recorded 1.54),
idle → shy_trans 2.10 (2.02), loop wraps ≤ 0.9. Checking that graph also shows that
`key_point_speaking → thinking_speaking1` moves the head top by 4 px.

`production qa` reports bound nodes and edges; `export-amadeus` runs the same gate
for production-bound nodes and refuses to publish on a failure. On the real Kurisu
idle source the gate stopped an export because matting leaked into the video's dark
border (the character "touched" the side edges on 12 frames); `production clip set
idle_loop --edge-guard 16` fixed it, as the earlier edge-leak repair did.

## Graph and export

Bind a node to a clip with root `production/clips/<clip>/output` and the clip's phase.
`production graph-sync` copies phase, frame interval and loop mode from `render.json`
onto bound nodes; `--add-missing` also adds a node for each rendered clip that is not
in the graph (the base loop becomes root if the graph has none). Edges and weights stay
the author's decision in the graph editor. Export also writes the mouth overlays below.

## Mouth overlays for speaking loops

Speaking loops are generated with a moving mouth, so the mouth shape while talking is
the video itself. Amadeus only has to close the mouth during silence: when the
character is not speaking or the playback RMS is at or below 0.08, it paints a
closed-mouth image inside an ellipse around the mouth, shifted so that image's mouth
lands on the current frame's mouth. Audio never selects a mouth shape. Production
therefore computes, per speaking loop:

- **mask track and size**: the mouth is found where the loop changes most near the
  expected position (the mouth set, moved with the pose's head offset), then tracked
  per frame by template matching (at most 6 px per frame, median-smoothed);
- **closed-mouth image and its mouth anchor**, tone-matched to the loop;
- **closedness per frame**: difference from the closed mouth, which Amadeus uses only
  to pick the most closed frame when it holds or samples frames.

`production clip set C --mouth neutral` enables it (loops only). The closed mouth is,
by default, the **shared closed mouth**: the base still, reused by every expression.
It is not frame 0, because a loop entered through a transition does not necessarily
start closed. A pose whose face differs (a side view) chooses its own with
`production mouth pose side --use side`; `production mouth shared POSE` changes the
shared one; one clip can override with `--mouth-source still|frame:N|pose:ID`.

A shared closed mouth comes from another expression, so its skin tone differs (blush,
grading); pasted as is, the mask shows as an oval. The render measures the mean Lab of
the skin the mask covers around the mouth, in the loop and in the closed image, and
shifts the closed image by that difference inside a margin around its mouth. The
result is stored as `output/.mouth/closed.png` with the render and is what export
encodes; a shift above 8 L* is reported for review. The Production page's **Simulate
silence** preview draws the tracked mask and pastes this image exactly as the renderer
does.

Mouth sets (`production mouth set NAME --cx --cy --width --height --curve`, in pixels
from the canvas centre) are priors for detection and become the pack's `expressions`.
Approving the base still creates `neutral` from its anchors: centre 29% of the canvas
height below the head top, 4.5% of the width wide, 1.75% of the height tall (Kurisu's
hand-tuned neutral mouth is 4.0 / −196 / 34 × 18; the derived one is 5.8 / −195.9 /
34.4 × 18.0).

Export writes one profile per bound speaking-loop node (`mouth_set`, `cx`, `cy`,
`width`, `height`, `closed_frame_idx`, `openness`, `anchor_track`,
`runtime_overlay_anchor`) and one KTX2 overlay in `mouthOverlays`; `--no-mouth` drops
them. Amadeus applies profiles only to the labels it treats as speaking loops and keeps
its own per-label mask adjustments.

## Providers

| Provider | Endpoint (tools.json) | Key | Request |
| --- | --- | --- | --- |
| `wan` | `https://dashscope.aliyuncs.com/api/v1`, model `wan2.7-i2v-2026-04-25` | `DASHSCOPE_API_KEY` | `media` = `first_frame` + `last_frame` data URLs, `duration`, `resolution`, `prompt_extend: false`, optional `seed` and `negative_prompt`; `X-DashScope-Async: enable` |
| `seedance` | `https://ark.cn-beijing.volces.com/api/v3`, model `doubao-seedance-1-5-pro-251215` | `ARK_API_KEY` | `content` = text + `first_frame` + `last_frame`, `ratio: adaptive`, `duration`, `resolution`; no negative prompt (takes record it was not sent) |

Keys are read only from the named environment variables and never written to disk.
Workspace-specific DashScope hosts go in `baseUrl`. Provider errors are raised with the
provider's message; there are no silent retries, duration downgrades or single-frame
fallbacks. Wan result URLs expire after 24 hours, which is why takes download at once.
Inputs are flattened onto the character background because Wan does not accept alpha.

## Migrating from the earlier local tools

| Earlier tool | Production step |
| --- | --- |
| `seedance_web_gui.py` presets (neutral/reference frame, in/loop/out prompts) | poses, clips and the prompt library |
| `seedance_transition_pipeline.py` | `seedance` provider (one request shape) and render registration instead of black-border cropping |
| `run_configs/*.json` | take provenance; keys only from the environment |
| manually aligned `refs/*_aligned.png` | still takes with normalisation, geometry QA and approval |
| `tools/rebuild_updated_animation_batch.py` | decode, register to both stills, alpha processor |
| `tools/calibrate_*.py`, `analyze_front_face_consistency.py` | still QA, intended offsets, drift QA |
| `tools/lock_transition_tail_to_loop.py` | `lockHeadFrames` / `lockTailFrames` into the pose still |
| `experiments/gmfss_test/build_graph_gmfss_2x.py` | interpolate processor |
| `tools/repair_alpha_edge_leaks.py` | `edgeGuardPx` from the character's closed edges |
| idle pingpong scripts | `pingpong` |
| `docs/COLOR_SEAM_QA.md` | clip and graph seam QA with the same thresholds |
| `*_notuse.mp4`, `*_new.mp4`, `replacement2.mp4` | take decisions with reasons |
| label tables in Amadeus `package_spriteforge_character.py` | clip fields → `render.json` → `graph-sync` → export |

Not migrated yet: mouth overlay export (the Kurisu pack has 16 mouth profiles), an
importer for the existing Kurisu workspace, an image-edit provider for stills (stills
are imported), and clip-specific effects such as the front-to-side ghost trail. The
earlier scripts write into a workspace path that no longer exists and extract with the
removed FFmpeg option `-vsync`, silently falling back to OpenCV's colour conversion.
