# Management and runtime boundary

```text
Idle reference -> production: approved pose stills -> clip takes (import or provider)
  -> candidate processing (register to stills, alpha, interpolate, lock) -> QA -> adoption -> clip output
Existing PNG frames -> workspace import/discovery -> preview and optional QA
  -> graph editor -> authoring validator -> shared node frame selection
       -> exact clip preview
       -> production export gate (bound clip outputs are current, synced and pass QA)
       -> KTX2 encoding -> staging -> v1 validation -> local export

Exported package -> Amadeus SpriteForgeAnimator -> frontend SpriteForgeRuntime
```

Production owns pose stills, takes, prompts and renders under `production/`; its
invariants and QA are described in [production.md](production.md). A clip output is
an ordinary frame root to the graph: the graph editor, frame resolver and exporter
treat it like any imported folder, and only the export gate knows about renders.

The workspace owns frame roots, selected variants and layout. The editor and CLI
use the same authoring validator. The v1 validator owns topology and package
consistency. Export encodes selected frames and creates a new immutable directory;
it neither changes source frames nor installs or starts Amadeus.

Amadeus owns semantic intent, speech signals, source priority and live state.
There are no imports from an Amadeus checkout, nor assumptions about its environment,
services or installed assets. The vendored v1 validator has explicit provenance;
it is not a second format. Contract changes must be exercised through both loaders.

## Explicit policies

The old exporter selected character-specific processed directories and timing.
The new exporter takes the exact frame root, phase, interval and loop mode from
node metadata. The preview uses that same frame resolver.

Amadeus still supplies speaking label groups, random intent aliases, transition
holds and post-speech release states. Standalone node preview is a clip viewer,
not an equivalent implementation of an entire speaking turn.

## Local file boundaries

The HTTP server binds to loopback, checks local Host/Origin and requires JSON writes.
Frame access resolves inside the selected workspace, including symlinks. Authoring
mode serves PNGs; runtime mode serves only manifest-indexed KTX2 frames and rejects
graph writes. Saves validate first and atomically replace the graph. Concurrent
valid saves are last-writer-wins: this is a single-user editor.

The process has the user's filesystem permissions. Workspace selection authorizes
reading and editing that directory. This is not a hosted multi-user service.

## Subsequent work

- Portable mouth-overlay authoring/export verified against Amadeus.
- Shared runtime preview if full intent/speech simulation is required.
- Separate migration of the wallpaper `scenario_graph.json` contract.
- Broader clip metadata management without hidden frame-selection rules.

## Saved graph view

The author's existing graph owns node positions. Review can read those positions
from --layout or the exported sibling <pack-name>.graph-layout.json. The sibling
contains only IDs, labels and coordinates and stays outside the runtime package.
It cannot override runtime topology, probabilities or clip bindings. Missing
positions are reported instead of replaced with an automatically invented layout.

## Studio production and editing

Generate & QA and Edit assets are separate views over the same workspace. The
production side owns imports, generation, candidate processing and review. A
candidate's processed output lives beside its take; producing or reviewing it
does not replace the published clip. Adoption requires current non-failing QA
and publishes the processed output while recording the decision. Publication
rolls back if that decision fails. The legacy accept-then-render CLI remains
available for existing callers.

The editing side owns the material library, native graph editor, exact node
player, assembly seam checks, behavior statistics and versioned exports. Clip
QA is projected onto bound graph nodes for the canonical export gate; unbound
candidates never block an existing package. Within one local server, publication
and export jobs exclude one another. Independent CLI processes are not covered
by this in-process scheduling rule.

Behavior simulation mirrors Amadeus `render/spriteforge_animator.py`, checked at
commit `788c506816b6a316e53d8f5118d95309695e3dfd`: node duration at lines 698–699,
weighted positive edges at 701–713, first-hop BFS at 740–767, and intent consumption
at 864–869 followed by automatic transitions at 878. The BFS diagnostic permits
manual edges only on the first hop. An intent forces that first hop; later hops
are sampled normally, so a found route does not guarantee that the simulation
reaches its target. Duration comes from actual bound or legacy PNG frame counts
and the node interval, falling back to 2.5 seconds only when unavailable.
Simulation never edits the graph. It excludes runtime label aliases, root
fallback or teleportation, speech holds and release logic.

Versioned exports reuse the existing exporter and write only under the workspace.
Installed packs are read-only comparison inputs. Texture changes are compared
using encoded hashes from a recorded export with matching source hashes. Without
that evidence, the UI reports a comparison awaiting encoding rather than treating
PNG and KTX2 hashes as interchangeable.

## Workflow execution boundary

`production/workflow_ops.py` owns the fixed typed operation registry and reuses
provider, normalization, QA and configured-processor primitives.
`production/workflows.py` owns graph validation, durable documents, planning,
execution and cache receipts. The browser displays and edits that registry; it
does not execute imported node classes. Groups and coordinates are presentation
metadata. Runtime graph and package formats are unchanged.

Planning uses dependency cache identities: source fingerprints include actual
bytes and relevant prompt versions, model/tool settings and canvas/anchor facts;
downstream keys include validated upstream operation keys. No future generated
pixels are guessed to calculate the paid count. Explicit reruns change one key
and downstream keys. Artifact hashes and host provenance are retained separately
in durable receipts, and completed paid results never expire automatically.

A paid request is checkpointed before submission and its result is committed
before downstream work. Its receipt is the single usage ledger for that workflow
request, including fanout and resumed downloads. The host checks the exact current
uncached paid count and imported-workflow disclosure before dispatch. A later
local failure cannot silently submit the completed request again.

Source authority remains with production records and exact approved bytes.
Concept provenance persists through transforms and cache reuse, so normalization
cannot grant it permission to become a formal pose. A legitimate image edit uses
the approved normal base and may use a concept reference. Save operations create
candidates only; decisions, published rendering and export have no workflow node.
The server's existing job lock serializes workflows and reserves affected owners.
It does not add a cross-process scheduler for separate CLI invocations.
Guided and workflow image requests reuse the same provider locks, initialized
under the API job lock. Local operations execute outside those provider queues.
