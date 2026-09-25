# Management and runtime boundary

```text
Idle reference -> production: approved pose stills -> clip takes (import or provider)
  -> accepted take -> render (register to stills, alpha, interpolate, lock) -> clip output
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
