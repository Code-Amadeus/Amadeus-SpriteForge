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
        process candidate: decode ─► optional whole-clip border crop ─► register both ends ─► pingpong ─► interpolate
                ─► alpha ─► edge guard ─► lock ends to the stills ─► QA
          ▼ human review: adopt / reject and archive / restore
        publish qualified candidate
          ▼
        behavior graph (review page) ─► KTX2 character pack for Amadeus
```

Everything lives in the authoring workspace under `production/`. Open Studio with
`spriteforge review --workspace W`; initialized production workspaces open Studio
by default, and `/production` redirects to `/studio`. Every operation is also a
`spriteforge production ...` command. Production and QA
need the `qa` extra (OpenCV, NumPy) and FFmpeg for video takes.

## Studio

The Studio interface is available at `/studio`. Its shared shell follows
the dark green HTML prototype. **Generate & QA** and **Edit assets** are separate
views, following the earlier local tools' division of work. Generate & QA has two
ways to operate on the same workspace: the guided **Studio** and a **Node workflow**
view. Generating or importing candidates, processing and per-asset QA happen on
the production side. Approved assets feed graph editing, playback and export;
assembly seams and graph timing are checked there. Uninitialized authoring
workspaces and runtime packs retain the original reviewer at `/`.

The Overview reads the same pose, take, render and graph records as the CLI.
Missing statistics are shown as unknown rather than estimated from sample data.
New renders record `durationS`; historical renders without that field keep their
original records. The time total covers retained render records from the last
seven days; overwritten renders have no historical timing record. Versions include
failed and rejected takes.

Studio starts in English. The top bar and Settings switch to Chinese immediately;
only language and panel size preferences live in the browser. A hash URL retains
the current stage and open tool, and browser Back and Forward work normally.
Prompts, Jobs and Settings open over the current stage. Canvas has a full-page
`#/canvas` route so a tool drawer can open over it without changing the underlying
view; the original `?tool=canvas` URL is accepted as an alias. Canvas uses the existing
card and wire editor, including imports, approvals and generator input preparation.

Settings exposes provider readiness and model names, never credentials. The same
image provider defaults can be changed from the command line:

```text
spriteforge production settings --workspace W
spriteforge production settings --workspace W --concept-provider qwen-image --still-provider seedream
spriteforge production settings --workspace W --batch-confirm-threshold 3
```

The confirmation threshold does not authorize generation. Generating media still
requires an explicit user action; tests use synthetic assets and fake providers.
Studio does not install character packs into Amadeus or launch it.

The view switch is navigation only. It neither copies a workspace nor creates a
second acceptance record. The editing Overview lists approved stills with current
anchors and accepted clips with current, non-failing QA; pending and failed
candidates remain on the production side. A return-to-QA link opens their existing
pose or clip. The editing view keeps provider controls out of graph composition.

Clip Studio and Review process each candidate under its take directory. A current
non-failing result is required before **Adopt** becomes available. Adoption copies
that result into the published clip output and records the accepted take; the
candidate preview remains available. Processing a different take does not replace
the current graph material. Changing its recipe or approved endpoint stills marks
the processed result stale and requires another local processing pass.
The Studio Canvas sends clip adoption to Clip Studio so its inspector shares the
same review gate. The CLI retains its existing accept-then-render commands for
compatibility; the shared legacy controls remain covered by a browser fixture.

Behavior embeds the existing graph editor and exact node player, with a separate
Stats tab for seeded automatic playback and first-hop intent tests. The editor's
Graph checks page contains assembly and seam findings, while candidate decisions
stay in Generate & QA. A watch finding can be annotated as known with a note; its
measurement and severity are retained.

Export reruns preflight, displays the actual encoding settings, and creates a
versioned pack under `production/exports/`. It saves editable release notes and
an export history. An optional installed pack in Settings is a read-only comparison
source. Updated textures can only be established after a recorded encoding of the
current source; otherwise the comparison explicitly awaits encoding.

Browser acceptance: `node tools/studio_smoke.cjs` uses a synthetic production
workspace and writes 1440×900 English/Chinese screenshots to `test-results/`.
Set `SPRITEFORGE_PYTHON` to a Python environment with the QA extras and, on Windows,
`BROWSER_CHANNEL=msedge` to use an installed Edge browser.

### Clip Studio

`#/clips/<clip>` places sibling variants, immutable take versions, a synchronized
comparison and the clip's settings in one view. Variants share endpoints and type
(a speaking loop has a mouth set); creating one copies current settings and subject
text, with no takes, accepted decision or render. Existing clip IDs are retained.

The version number includes failed and rejected takes. A new take can name a
`basedOn` take from the same clip, while its input stills and settings come from the
current clip. The generation dialog starts with that version's subject text;
editing it adds a prompt block version. A take's saved prompt, inputs and source
remain unchanged. Its separate annotation can be edited without making a render
stale. Rejecting a clip version requires a reason; rejected media is retained.

```text
spriteforge production clip variant --workspace W idle_loop idle_loop2
spriteforge production generate --workspace W --clip idle_loop --based-on TAKE --note "Less head movement"
spriteforge production take note --workspace W --clip idle_loop TAKE --note "Compare the loop seam"
```

A/B defaults to the selected raw takes. The explicit Render preview uses published
output only when it belongs to that selected take; QA and mouth frame markers refer
to that output, whose timing can differ from the raw take after interpolation or
ping-pong processing. Changing the accepted version makes its render stale.
Generation, Processing, Playback and Mouth edit the current clip settings; the
Prompt view shows the selected version's recorded snapshot.

Video uploads and imports from a workspace PNG folder are supported; the latter
requires an explicit FPS. Preparing first/last input images, adopting a take frame
as a pose candidate, resuming a submitted download, syncing graph timing and
rendering the accepted version remain available. J/K select versions, A accepts,
X requests a rejection reason, C changes comparison mode, Space plays and L toggles
looping; editing fields keep their normal keys.

Credit estimates use the median of at most five recent complete balance deltas
with the same provider, duration and resolution. Unknown history and balance
increases do not become a cost estimate. Every generation remains an explicit
action with its cost type shown, and failed requests are not silently retried.

### Expressions: concepts and final stills

`#/expressions/<pose>` keeps concept selection separate from approved geometry.
A concept sheet is one image split into a 3×2 or 2×2 grid. Its actual size is
recorded, a uniform outer border is removed before splitting, and each cell is
saved as PNG. The original source image is retained. A grid can contain fewer
poses than cells; an unassigned cell needs a pose before it can be picked.

The newest ready sheet is current. A failed request does not hide the previous
sheet. Older sheets retain their images and assignments, while their cells can
still be picked. Re-rolling one current cell requests one image and keeps the
previous image in that cell's history. Descriptions use the existing versioned
`pose.<id>` prompt block, shared with final stills.

A final still edits the approved base image with the picked cell as a second
reference. Its take retains `reference.png`, its hash and sheet/cell provenance.
The result follows the existing alpha, normalization and QA process. A different
generated size is normal candidate behavior: the original remains available for
inspection or external refinement, and approval still depends on geometry QA.
Concept cells never become approved stills directly.

The panel also retains image import, manual input preparation, expected head
offsets and shared closed-mouth selection. Failed QA blocks approval; a watch
result requires confirmation. Planning clips creates records for approved poses
without generating media. Batch generation lists the count and cost type before
confirmation and serializes the explicitly requested jobs for each provider.

```text
spriteforge production concept new --workspace W --poses angry,blink --grid 3x2 --provider qwen-image --dry-run
spriteforge production concept import --workspace W sheet.png --poses angry,blink --grid 3x2
spriteforge production concept pick --workspace W SHEET 0
spriteforge production concept reroll --workspace W SHEET 0 --provider qwen-image
spriteforge production generate --workspace W --pose angry --provider qwen-image --concept SHEET:0
```

New pose names retain the prompt-completeness gate. Fill their descriptions and
the shared concept/reference prompt blocks before requesting paid generation.
All those edits add ordinary prompt versions; generating a sheet does not invent
missing subject text. `tools/expressions_smoke.cjs` exercises the complete flow
against a local fake image provider, including outputs of a different size.

## Invariants

1. **Approved pose stills are the only geometric authority.** Each clip endpoint is
   registered, and optionally locked, to the still of its pose, so two clips meeting
   at a pose share endpoint geometry by construction. This replaces chains such as
   "align the loop to the processed tail of the transition" and per-clip calibration.
2. **Takes are immutable and never deleted.** A take keeps its media, the exact input
   images (a clip's first and last frames, a generated still's base image), the
   rendered prompt with block versions, and the provider request or task. Decisions only change which take a pose or clip accepts, or mark a take
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
  poses/<pose>/takes/<take>/source.*, still.png, take.json (+ input.png when generated)
  clips/<clip>/clip.json                       from, to, phase, generation, processing, playback
  clips/<clip>/takes/<take>/media.mp4 | frames/, first.png, last.png, take.json
  clips/<clip>/output/<phase>/*.png, render.json   stable graph root of the clip
  canvas.json         card positions on the production canvas (layout only)
```

Writes are atomic and flushed (a power loss leaves the previous file, not a
truncated one). A render is staged in a hidden directory and swapped in whole.
Review discovery lists only `production/clips/<clip>/output/<phase>` folders.

## The production canvas

The **Canvas** tab of `/production` shows the production as a graph of cards. It reads
the same records as the commands below and adds no state of its own except card
positions (`production/canvas.json`).

- **Pose cards** show the approved still (or the latest candidate), its status and
  where it came from: imported, generated by an image editor, or a frame of a clip
  take.
- **Clip cards** hold the clip's own prompt block, editable in place (saving adds a
  version), its generation settings, its latest takes (hover to play; the accepted
  one is outlined), its render and QA status, and the actions Generate, Import take,
  Render and, on transitions, Last frame → pose still.
- **Wires**: pose → clip means the pose's still is the clip's first frame. Clip → pose
  means the clip ends on that pose: solid when that still is sent as the last frame,
  dotted for a first-frame-only transition, dashed with the frame number when the
  pose's approved still was taken from one of the clip's takes. A loop has only its
  incoming wire.
- **Drawing clips**: drag from a pose's right port onto another pose (a transition),
  onto the same pose (a loop) or onto empty space (a new pose reached by a
  first-frame-only transition, which then lends a frame of its take to the new pose).
- **Side panel**: clicking a card opens its full detail — still comparison and
  approval, every take with its decisions, all clip settings, the assembled prompt and
  the render preview with QA. For generating by hand on a provider's website, the
  clip's panel offers the exact generator inputs (`first.png`, and `last.png` unless
  the clip is first-frame-only) that `production prepare` would write; the resulting
  video is imported with Import take.
- **Guide**: the Guide button explains this workflow step by step, in English or
  Chinese. It opens by itself on a workspace without clips.

The canvas is about production, not behaviour: which clip plays when (labels,
probabilities, graph edges) is bound later on the Review & graph page, and clips can
be produced before that graph exists. Cards are placed automatically (poses in columns
by distance from the base pose, each pose's clips beside it) until you move them; Auto
layout arranges them again.

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
| `clip` | a frame adopted from a clip take whose pose changed: the take's own framing is kept (see below) and QA asks for an overlay check |
| `placement` | explicit `--place SCALE,DX,DY` |

The rigid threshold is calibrated on the real Kurisu stills: an expression edit keeps
93% of matches; lean, thinking and side poses keep 3–20%, and forcing a registration
there scaled the side pose by 9% and moved it 108 px.

A pose whose head legitimately moves records an intended offset:
`production pose expect P --head-top Y --head-center X`. On Kurisu these are the
serious pose (head centre ≈ 393), thinking (≈ 392, top 23) and side (top 37, centre ≈ 375).
Approval re-runs QA and refuses a still that fails.

### Generating a still

`production generate --pose P --provider qwen-image|seedream [--dry-run]` (or
**Generate still** on the page) edits the approved base still into pose P with an
image-edit provider. The take keeps `input.png`, the flattened base still exactly as
sent, with its take id and sha256, the prompt snapshot and the request with images
replaced by hashes. The provider's image becomes `source.*` and is matted, normalised
and checked exactly like an import, so approval applies the same geometry QA.

The base pose is always imported: it is the reference every generated still starts
from. Generation stops before recording a take when the prompt has placeholders, the
provider's key is missing, or no alpha processor is configured (provider images are
opaque). A refused request stays in the archive as a failed take with the provider's
message. `--dry-run` prints the request without sending it.

For an image editor without an adapter, `production prepare --pose P --output DIR`
writes the same `base.png` and the rendered prompt; import the result as above.

### Adopting a frame of a clip take

A pose can also take its still from where a transition's motion ends, the way the
earlier tools chained a loop onto a transition's last frame. The still is then fixed:
every clip that meets the pose is registered and checked against it, and regenerating
the transition does not move it.

1. `production clip set T --last-frame none` makes transition T generate from its first
   frame only, so its end pose needs no still yet. Both providers document the
   first-frame-only request; `prepare` writes no `last.png`, and the take records that
   no last frame was sent. Loops cannot use it: they must return to their still.
2. Generate or import takes of T as usual and review them.
3. `production take adopt --clip T TAKE [--frame last|first|N] [--pose P]` (or
   **Last frame → P still** on a take of the page) copies that frame of the take into a
   new still take of the clip's end pose (or P). The source records the clip, the take
   and the 0-based frame index.
4. Approve it like any still. A pose that really moves the head records its offset
   with `production pose expect` first.

The frame is matted, then registered to the base still when it is a rigid copy (an
expression change). Otherwise it keeps the take's framing: the transform that
registers the take's first frame to the clip's start still places it on the canvas,
so the camera is assumed to stay where the clip started. Frames already on the canvas
(`register` off) keep their pixels, minus the clip's margin. The base pose cannot be
adopted: it is the reference every clip starts from.

Rendering T afterwards registers its last frame to the adopted still, so the camera
drift is near zero and the tail lock changes nothing visible. Keeping `--last-frame
none` is fine; switching back to `still` makes later takes aim for the adopted still.

## Clips and takes

`production clip add ID --from A --to B` plans a clip. `A == B` is a loop; otherwise a
transition. Phase defaults to `loop`, `out` (ending on the base pose) or `in`.

| Setting | Default (transition / loop) | Effect |
| --- | --- | --- |
| `generation.provider` | `manual` | `manual`, `wan`, `seedance` |
| `generation.durationS` | 2 / 4 | seconds requested |
| `generation.inputScale` | 1.0 | shrink the subject inside provider inputs to leave a safety margin |
| `generation.lastFrame` | `still` | transitions only: `none` generates from the first frame alone, for an end pose that adopts its still from the result |
| `processing.cropBlackBorder` | off | remove an existing protection border using one crop rectangle for the entire take |
| `processing.cropBlackThreshold` | 10 | grayscale values at or below this level count as black (0–254) |
| `processing.cropBlackMarginPx` | 4 | pixels retained around the union of non-black content |
| `processing.register` | on | register both ends of the take to the pose stills; off takes frames that are already placed on the canvas as they are |
| `processing.marginPx` | 0 | transparent columns added on each side of the canvas for motion past its edges (hair in the wind) |
| `processing.interpolate` | 1 | frame multiplier from the interpolate processor |
| `processing.pingpong` | off | loops only: play forward then backward |
| `processing.lockHeadFrames` | 6 / 0 | frames blended into the start still (first frame exact) |
| `processing.lockTailFrames` | 12 / 0 | frames blended into the end still (last frame exact) |
| `processing.edgeGuardPx` | 0 | clear alpha near closed canvas edges |
| `playback.speed` | 1.0 | playback multiplier |
| `playback.loopMode` | `once_then_hold` / `loop` | runtime loop mode |

**Protection-border cropping is optional and uses one rectangle for the whole clip.**
It scans every decoded frame, takes the union of their non-black content, adds the
configured margin, and applies that same rectangle to every frame before registration.
It does not tighten the crop separately per frame or rescale individual frames.
The raw take stays unchanged; `render.json` records `sourceCrop`, including the source
size and rectangle `[x0, y0, x1, y1]` with exclusive right/bottom bounds. Adopting a
frame as a pose uses the same full-take crop before selecting the frame.

Settings can enable **Crop protection border for new clips** by default. The default
is copied when a clip is created; existing clips retain their own setting. Importing
finished legacy frames explicitly disables cropping to preserve their pixels. Each clip's
Processing panel overrides it and exposes the threshold and retained margin. Older
workspaces with no crop fields keep cropping disabled. For example:

```powershell
spriteforge production settings --workspace studio --crop-black-border
spriteforge production clip set --workspace studio shy_in --crop-black-border --crop-black-threshold 10 --crop-black-margin 4
spriteforge production clip set --workspace studio shy_in --no-crop-black-border
```

Enable this only for material with an existing black protection border. This step
does not add a border to generator inputs, estimate alpha, or recover a head already
cut off in the generated video. An all-black sequence is rejected. With registration
disabled, the cropped frames must already match the output canvas, including its
side margins. A changed crop setting makes the corresponding render stale.

A clip with a margin renders the canvas widened on both sides. The pose stills are
widened the same way for locks and QA, and graph seams compare the canvas part only.
Amadeus anchors every frame at its bottom centre. It keeps such a clip at the
character's size only when it fits the character by the pack's `canvas_size`
(Code-Amadeus/Amadeus#138). Earlier runtimes fit each frame by its own texture, so in
a width-limited view, such as the wallpaper CRT on screens narrower than 16:9, a wider
frame draws the character smaller. Every production export writes `canvas_size`,
including packs without mouth profiles and `--no-mouth` exports. The Production
preview shows the full published frame, including margins, even while changed
clip settings await a new render.

`frameIntervalMs = round(1000 / (source fps × interpolate × speed))`. The Kurisu pack
used 30 fps × 2 → 17 ms loops, 24 fps × 2 → 21 ms idle, and transitions at 2–4× speed
(8 ms / 5 ms).

Takes come from three places:

- **Manual**: `production prepare --clip C --output DIR` writes `first.png`, `last.png`
  (none for a first-frame-only transition) and the prompt; generate in any tool, then
  `production take import --clip C VIDEO` (or a PNG folder with `--fps`). The inputs
  are recorded as assumed.
- **Provider**: `production generate --clip C [--dry-run] [--no-wait]` submits the
  opaque first/last frames (or the first alone) and the rendered prompt, records the
  task id before waiting, downloads the result immediately and stores it as a
  candidate take.
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

Templates are workspace data. `production prompt template ID --blocks a,@subject,b
[--negative n] [--join TEXT]` replaces one; blocks are joined by a blank line unless
`--join` says otherwise. Many video prompts are one sentence, for example a style
opening, the clip's own action and the shared constraints joined by `，`; with a
clause joiner each block's closing punctuation is dropped, so a subject may end with
`。`. A template with no negative blocks sends no negative prompt.

`production prompt export FILE [--template T ...]` writes a preset: the templates and
the current text of the blocks they use, never pose or clip subjects.
`production prompt import FILE` adds those texts to another workspace as new block
versions and installs the templates, so a house style is set once per character.
New workspaces start from placeholders. `examples/prompt-presets/` holds an optional
example preset, one-sentence Live2D-style idle prompts that worked with Wan, to start
from or ignore; prompts are yours to explore.

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
The Review folder list also exposes `output/<phase>` with phase `flat`; these
bindings are subject to the same export gate and mouth export. Run
`production graph-sync` to normalize them to the output root and copy phase, frame
interval and loop mode from `render.json` onto bound nodes;
`--add-missing` also adds a node for each rendered clip that is not
in the graph (the base loop becomes root if the graph has none). Edges and weights stay
the author's decision in the graph editor. Export also writes the mouth overlays below.

Some clips are played by label outside the graph: Amadeus lands on `smile` or `sad`
after speech and then returns to the root. `production runtime-clips CLIP ...` lists
them on the character (`--clear` empties the list); export adds each one to the pack
manifest under its clip id, not to the runtime graph, and gates it like a bound node.

## Mouth overlays for speaking loops

Speaking loops are generated with a moving mouth, so the mouth shape while talking is
the video itself. Amadeus only has to close the mouth during silence: when the
character is not speaking or the playback RMS is at or below 0.08, it paints a
closed-mouth image inside an ellipse around the mouth, shifted so that image's mouth
lands on the current frame's mouth. Audio never selects a mouth shape. Production
therefore computes, per speaking loop:

- **mask track and size**: the mouth is the largest region that changes over the loop
  and lies within a mouth's plausible distance of the expected position (the mouth
  set, moved with the pose's head offset). Hair moving at the sides of the search
  window is therefore never taken for the mouth, and the lip edges of an open mouth
  count as one region. The mouth is then tracked per frame by template matching (at
  most 6 px per frame, median-smoothed). The head offset alone does not place the
  mouth of a tilted pose (Kurisu's thinking mouth sits 23 px above it); detection
  finds it, and QA reports a loop where it falls back to the expected position;
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
Each mouth render snapshots the chosen set and its pose-adjusted prior. Changing
that set or the pose's expected head offset makes the render stale and blocks
export until it is rendered again. Earlier experimental mouth renders without
this snapshot also need one re-render; body-only renders are unaffected.
Approving the base still creates `neutral` from its anchors: centre 29% of the canvas
height below the head top, 4.5% of the width wide, 1.75% of the height tall (Kurisu's
hand-tuned neutral mouth is 4.0 / −196 / 34 × 18; the derived one is 5.8 / −195.9 /
34.4 × 18.0).

Export writes one profile per bound speaking-loop node (`mouth_set`, `cx`, `cy`,
`width`, `height`, `closed_frame_idx`, `openness`, `anchor_track`,
`runtime_overlay_anchor`) and one KTX2 overlay in `mouthOverlays`; `--no-mouth` drops
them while preserving the canvas header. Amadeus applies profiles only to the labels it treats as speaking loops and keeps
its own per-label mask adjustments.

## Providers

| Provider | Endpoint (tools.json) | Key | Request |
| --- | --- | --- | --- |
| `wan` | `https://dashscope.aliyuncs.com/api/v1`, model `wan2.7-i2v-2026-04-25` | `DASHSCOPE_API_KEY` | `media` = `first_frame` + `last_frame` data URLs (`first_frame` alone for a first-frame-only transition), `duration`, `resolution`, `prompt_extend: false`, optional `seed` and `negative_prompt`; `X-DashScope-Async: enable` |
| `seedance` | `https://ark.cn-beijing.volces.com/api/v3`, model `doubao-seedance-1-5-pro-251215` | `ARK_API_KEY` | `content` = text + `first_frame` + `last_frame` (no `last_frame` for a first-frame-only transition), `ratio: adaptive`, `duration`, `resolution`; no negative prompt (takes record it was not sent) |
| `wan-cli` | Wan's CLI (`@wan-ai/cli`), `command` in tools.json; model `wan3.0` (the CLI's default) | the CLI's own login (`wan auth login`) | `wan frame2video --first-frame F [--last-frame L] --prompt P --duration D --resolution R --audio-output=false --output json`; billed to the wan.video account's credits; the result is saved without the watermark; no negative prompt or seed |
| `qwen-image` (images) | `https://dashscope.aliyuncs.com/api/v1`, model `qwen-image-edit-plus` | `DASHSCOPE_API_KEY` | one user message with the base image, optional reference images and the prompt; `n: 1`, `prompt_extend: false`, `watermark: false`, optional `negative_prompt` and `size` (`W*H`); synchronous, the result URL is fetched at once |
| `seedream` (images) | `https://ark.cn-beijing.volces.com/api/v3`, model `doubao-seedream-4-0-250828` | `ARK_API_KEY` | `prompt`, `image` = base still data URL or an array of base plus references, `size`, `response_format: b64_json`, `sequential_image_generation: disabled`, `watermark: false`; no negative prompt |
| `gpt-image` (images) | Codex CLI `command` in tools.json; native image tool | the CLI's own login; checked on request | one isolated CLI call with the base and optional references, billed to plan quota; actual PNG output is validated and retained |

An image provider's `size` in tools.json is omitted (the provider's default; Qwen keeps
the input's aspect ratio), `match` (the canvas aspect ratio at a 2048 px long side; the
Seedream default, because a 764×1028 canvas is below its minimum pixel count) or an
explicit size in the provider's own format. `requestSeconds` bounds one HTTP request
(120 s by default, 300 s for the image editors). Providers added to SpriteForge later
appear in an existing tools.json with their defaults; entries in the file win.

Keys are read only from the named environment variables and never written to disk.
Workspace-specific DashScope hosts go in `baseUrl`. Provider errors are raised with the
provider's message; there are no silent retries, duration downgrades or single-frame
fallbacks. A request without a last frame is sent only for a transition set to
`lastFrame none`; both providers document it (Wan 2.7 lists `first_frame` alone as
first-frame-to-video, and Ark takes one `image_url` with role `first_frame`). Wan
result URLs expire after 24 hours, which is why takes download at once.
Inputs are flattened onto the character background because Wan does not accept alpha.

### Wan through its CLI (subscription credits)

The `wan` adapter calls Model Studio and is billed pay-as-you-go. To spend a wan.video
membership's credits instead, use `wan-cli`, which drives Wan's own command-line tool:

1. Install the CLI (Node.js 22 or later). Its install script copies an agent skill into
   the coding agents it finds (`~/.claude/skills`, `~/.codex/skills` and others); skip
   that with `--ignore-scripts` or `WAN_SKIP_SKILL_INSTALL=1`. A local install works:
   `npm install @wan-ai/cli --prefix C:/tools/wan-cli --ignore-scripts`.
2. Log in once in your own terminal with `wan auth login` and the AccessKey from
   create.wan.video. The CLI keeps it in `~/.wan`; SpriteForge never reads it.
3. Point `providers.wan-cli.command` in tools.json at the CLI. On Windows use Node and
   the package's script, `["node", "C:/tools/wan-cli/node_modules/@wan-ai/cli/dist/index.js"]`:
   a `.cmd` shim passes multi-line prompts through cmd.exe, which mangles them.
   `audioOutput` (default false) asks for a soundtrack; `model` other than `wan3.0`
   adds `--model`; `site` adds `--site`.

Generation checks `wan auth status` before recording a take and records the account's
`wan credits` before submission and after the result is saved, so each take shows
what it cost. Every call runs in an empty folder (the CLI reads a `.env` from its
working directory) with the skill installation switched off. The result is saved
with `wan result get --save`, which downloads the watermark-free file.

### GPT Image through Codex (plan quota)

Configure `providers.gpt-image.command` in the workspace's `production/tools.json`
to point to a Codex CLI executable. Image generation uses the CLI's own login and
plan quota. SpriteForge does not read or write Codex configuration or credentials.
Each explicit request runs once in an empty temporary directory with
`--ignore-user-config`, `--ephemeral` and `--skip-git-repo-check`; there is no
automatic retry. The timeout is configurable. Tests use a fake CLI and never
consume quota.

The authorized local spike used Codex CLI 0.159.2 for two image calls. One produced
a 1536×1024 concept sheet. The second accepted a base image plus an expression
reference, returning a valid 1086×1448 image when 768×1024 was requested. Exact
output dimensions are therefore a request, not an acceptance guarantee. The
adapter verifies the image bytes and records their actual size. A structured
final response identifies the output file, restricted to the generated-image
directory of the native `thread.started` event from that invocation.

This CLI version does not accept `--ignore-user-config` on `login status`.
Consequently the readiness indicator means **CLI available**, with login and
quota unverified until the explicit request. Authentication or quota failure is
reported by that request and retained as a failed attempt, following the existing
take lifecycle. This is the bounded specification deviation needed to preserve
configuration isolation without an extra model call or credential-file reads.
No quota-exhaustion or logged-out real call was attempted; those error paths are
covered by fake-CLI tests.

## Importing an existing character

A character made with the earlier tools, a SpriteForge workspace of frame folders and
the pack that was exported from it, becomes a production character without generating
anything:

```powershell
spriteforge init kurisu-studio
spriteforge production import-legacy plan --legacy D:\old\SpriteForge\workspace `
    --pack D:\Amadeus\assets\spriteforge\runtime\kurisu --output kurisu-plan.json
spriteforge production import-legacy apply --workspace kurisu-studio kurisu-plan.json
```

The pack is the record of what shipped; the legacy workspace supplies the PNG sources.
Neither is written to. `plan` writes a JSON plan to review and, where needed, edit (a
clip's `source`, a pose name) before `apply` builds the character. `apply` skips the
steps that are already done, so after an interruption it is simply run again.

| Decision | Rule |
| --- | --- |
| Clip source | the legacy folder that holds all the clip's frame names and whose KTX2 sidecar folder exists, within the legacy graph node's project; when several qualify, a sidecar that still holds the first texture is compared with the pack's, then the variant the node names decides |
| Poses | endpoints that meet: a loop's two ends and each graph edge's tail and head, when their head anchors agree within the tolerances; a clip outside the graph joins the pose with the most similar face |
| Pose still | the pose's most typical endpoint (median head position, smallest face difference to the others), approved as it is; a pose whose head sits beyond the tolerances records that as its intended offset |
| Frames | kept pixel for pixel: shorter frames are padded at the top, wider ones keep their width as `marginPx`; clips render with `register` off, without locks or interpolation, at the shipped frame interval |
| Mouths | the shipped mouth set and closed mouth: one of the loop's own frames (`frame:N`) or the still of the pose whose endpoint the pack used (`shared` for the base pose) |
| Graph | the pack's nodes and edges with the legacy positions, bound to the clip outputs and synced; clips outside the graph become runtime clips |

An edge whose ends disagree is kept and reported: graph QA fails its seam, and export
stays blocked until it is resolved with a transition clip or by removing the edge.

## Migrating from the earlier local tools

| Earlier tool | Production step |
| --- | --- |
| `seedance_web_gui.py` presets (neutral/reference frame, in/loop/out prompts) | poses, clips and the prompt library |
| `seedance_transition_pipeline.py` | `seedance` provider, optional whole-clip black-border crop, then render registration |
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

Not migrated: clip-specific effects such as the front-to-side ghost trail (imported
clips keep the frames that already have it). The
earlier scripts write into a workspace path that no longer exists and extract with the
removed FFmpeg option `-vsync`, silently falling back to OpenCV's colour conversion.

## Candidate workflows

Studio's Workflows page stores `spriteforge.workflow.v1` documents in
`production/workflows/<id>.json`. Nodes use a fixed typed registry; imported JSON
cannot define code, commands, approvals, published renders or exports. A configured
external processor is selected by its name in `tools.json`. Its command stays in
the machine's tool configuration. Workflow file paths resolve inside the selected
workspace, including symlinks.

The built-in templates are `transition`, `loop`, `speaking`, `final-still` and
`concept-still`. Opening a guided pose or clip prefills its current settings.
Opening a formal still with an existing concept reference keeps that reference
and schedules no extra concept-sheet generation. A manual clip template copies
an existing ready take into a new candidate without a paid request.

```powershell
spriteforge production workflow template loop --workspace studio --clip idle_loop `
    --id idle-local --output idle-local.json
spriteforge production workflow save --workspace studio idle-local.json
spriteforge production workflow plan --workspace studio idle-local
spriteforge production workflow run --workspace studio idle-local --yes-paid 0
spriteforge production workflow export --workspace studio idle-local shared-workflow.json
```

`workflow run FILE_OR_ID --yes-paid N` requires the exact paid count reported by
the current plan. A changed workflow, source, model or cache requires a new plan
and confirmation. Running an imported file additionally requires `--ack-import`,
after the plan lists its paid nodes and configured processor names. The page shows
the same disclosure before its first run. Cost types are credits, plan quota, or
metered billing; an unavailable price remains unavailable.

Each run writes a workflow snapshot and node receipts under
`production/workflows/runs/<run>/<node>/`. The execution order follows the validated
acyclic graph. A failed node stops the run and later nodes remain unexecuted.
Image/video artifacts, exact prompts, input hashes and source provenance stay
with the receipts and resulting candidates. Concept origin survives local
transformations and reroutes: a concept cell cannot become a pose take by being
normalized. Image edits use an approved normal base with an optional concept
reference. Generated dimensions may drift; returned pixels remain candidates
for ordinary refinement, normalization and review.

Cache keys combine the operation, its validated parameters, current source facts
and upstream dependency identities. They include actual source bytes, selected
prompt block versions, model settings, canvas/anchor facts and configured
processor settings where those facts affect the result. View coordinates do not
invalidate results. A dependency identity describes a validated operation; it
does not pretend to know the future bytes of a provider output. Completed receipts
also verify the actual artifact hashes and preserve their provenance.

Paid cache entries do not expire automatically. `--rerun NODE` or the node's
Re-run button changes that node's cache identity and its downstream identities.
A completed paid result is committed before downstream normalization or saving,
so retrying a later local failure reuses it. A submitted video task can resume
downloading without another submission. An ambiguous or failed paid attempt,
or damaged paid cached artifacts, requires an explicit rerun rather than a hidden
retry. Request time is retained when a download resumes.

The paid node receipt owns its recorded provider request and balance facts.
Seven-day usage counts that receipt once, even when its artifact fans out to
multiple Save nodes. Candidate `source.workflow` references the immutable run;
copied provider facts remain available for details and matching cost history.
No additional billing store or inferred price is created.

Save nodes produce candidate pose/clip takes or concept sheets. A Still QA node
only reports existing checks. Acceptance, rejection, clip processing, graph
publication and export remain explicit Studio operations. The local server runs
one workflow at a time and reserves its pose/clip owners against overlapping jobs
or adoption. This scheduling boundary covers threads in that server; independent
CLI processes remain outside it.
Uncached workflow image edits and concept generation share the guided pages'
existing provider lock; local nodes do not hold that queue.
