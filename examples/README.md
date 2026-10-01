# Self-contained examples

- `minimal/`: PNG authoring workspace. These are original geometric sprites generated
  by `spriteforge.demo`, with a five-edge graph and explicit clip playback settings.
- `runtime-minimal/`: the same nine frames encoded with KTX-Software 4.4.2 UASTC,
  exported through the standalone exporter. It is a valid Amadeus v1 character pack.
- `runtime-minimal.graph-layout.json`: saved node positions for the reviewer. This
  companion remains outside the runtime pack, which continues to contain only runtime data.

```powershell
spriteforge review --workspace examples/minimal
spriteforge review --workspace examples/runtime-minimal
```

The PNG workspace is editable. Use `spriteforge init workspace --demo` for a fresh
working copy. The runtime pack opens read-only and needs no PNGs or export tool.
Both examples are AGPL-3.0-only and contain no third-party character artwork.

## Character reference stills

[`references/kurisu/`](references/kurisu/) includes four 764x1028 character stills:
a current idle/smile pair and two legacy alignment references. Its bilingual guide
walks through importing and approving the current pair, preparing four clips,
take selection, rendering, graph editing, QA and export. Initial reference setup
and preparing generator inputs make no provider calls. These references are separate
from the geometric demo and its license grant; see the directory's provenance note.

## Prompt presets

The walkthrough now uses [`prompt-presets/live2d-idle.en.json`](prompt-presets/live2d-idle.en.json),
the complete English counterpart of the original template: a Live2D-style opening,
the clip's action, then the shared constraints (natural transitions, everything else
unchanged, no exaggerated movement, constant brightness). For example, the **full** prompt is:

```text
Create a natural Live2D-style idle animation clip, with the character naturally changing from the neutral expression in the first frame to the gentle closed-eye smile in the last frame, keeping the standing pose and hand positions unchanged and settling smoothly into the supplied final pose, using only the most natural transitions, keeping everything else unchanged, avoiding any exaggerated movement, and keeping brightness constant
```

Import the English preset, edit a clip's subject block and run `production prompt render`
to inspect the entire request. The constraints are in the positive prompt so they also
reach Wan CLI. These English examples are a translation and starting point; they have
not been qualified by new paid generations. The original Chinese preset remains available below.

`prompt-presets/live2d-idle.zh-CN.json` is one way to write video prompts, taken from a
production that used Wan image-to-video. It is a starting point, not a requirement:
new workspaces keep placeholders, and you are free to write prompts any way that
works for your character and model.

Each prompt is one Chinese sentence: a style opening, the clip's own action and shared
constraints, joined by `，`. The same templates serve transitions and loops.

```text
生成一个自然的live2d风格idle片段，<片段动作>，只做最自然的过渡，其他一切保持不变，禁止任何夸张的动作变化，不要有明度变化
```

Only the action is written per clip, for example:

- loop: `角色一直开口讲话，同时眼神有一次自然变化（幅度自然）`
- transition: `角色从默认的姿势自然地闭上双眼然后右手插兜`

```powershell
spriteforge production prompt import --workspace W examples/prompt-presets/live2d-idle.zh-CN.json
spriteforge production prompt set --workspace W clip.idle_talk --text "角色一直开口讲话，同时眼神有一次自然变化（幅度自然）"
spriteforge production prompt render --workspace W --clip idle_talk
```

Importing adds the blocks as new versions and replaces the `transition` and `loop`
templates, so earlier takes keep the prompts they were generated with. Export your
own house style with `production prompt export`.
