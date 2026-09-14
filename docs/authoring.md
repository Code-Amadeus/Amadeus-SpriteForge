# Authoring format

The workspace contains `graph_config.json` and PNG frames. Existing editor fields
are retained, with explicit playback metadata:

```json
{
  "nodes": [{
    "id": "idle", "label": "idle", "isRoot": true,
    "root": "projects/demo/frames/idle/loop", "phase": "flat",
    "frameIntervalMs": 42, "loopMode": "loop", "x": 100, "y": 100
  }],
  "edges": [{"id": "idle_self", "from": "idle", "to": "idle", "prob": 1}]
}
```

- Exactly one root, unique node/edge IDs, one edge per directed pair.
- Labels bind clips. Shared labels require identical root, phase, timing and loop mode.
- `prob` is finite and non-negative. Positive weights need not sum to one; zero is manual.
- Roots stay inside the workspace. Internal absolute paths normalize to relative
  on save; external roots and traversal are rejected. Explicitly import external frames.
- PNGs are sorted lexicographically from the selected directory.
- `phase` is `flat`, `in`, `loop`, or `out`. A missing legacy phase becomes `flat`
  if root directly contains PNGs, otherwise `loop`; save writes the explicit result.
- Missing legacy playback metadata defaults to 42 ms and `loop`. Set it explicitly
  when migrating a graph that previously depended on Amadeus label-specific overrides.
- `loopMode` is `loop` or `once_then_hold`. Layout fields do not enter runtime output.

An empty graph may exist in a new workspace but cannot be saved as a validated graph.

## Migration

1. Keep a copy of the old workspace.
2. Import selected PNG directories into a fresh workspace, or open the copied workspace.
3. Replace external paths with the imported relative roots.
4. Select the exact processed variant and phase, interval and loop mode for each node.
5. Validate and preview node clips; export to a new directory.
6. Validate the result in Amadeus before installing it there.

The application requires `--workspace`. It never searches personal default folders.
