"""Authoring fields are projected into the existing Amadeus runtime topology."""
from __future__ import annotations

import copy
import math
from pathlib import Path

from .character_pack import validate_character_pack_graph
from .workspace import clip_frames, png_frames, relative_asset, resolve_asset


def runtime_graph(graph: dict) -> dict:
    return {"nodes": [{k: n[k] for k in ("id", "label", "isRoot") if k in n} for n in graph["nodes"]],
            "edges": [{k: e[k] for k in ("id", "from", "to", "prob")} for e in graph["edges"]]}


def validate_graph(workspace: Path, raw: object, *, check_assets: bool = True) -> dict:
    if not isinstance(raw, dict) or not isinstance(raw.get("nodes"), list) or not isinstance(raw.get("edges"), list):
        raise ValueError("Graph requires nodes and edges arrays")
    graph = copy.deepcopy(raw)
    # The shared runtime validator owns identities, root uniqueness and edge semantics.
    topology = copy.deepcopy(graph)
    for node in topology["nodes"]:
        if isinstance(node, dict):
            node.pop("root", None)
    validate_character_pack_graph(topology)
    bindings: dict[str, tuple] = {}
    for node in graph["nodes"]:
        for field in ("id", "label"):
            if not isinstance(node[field], str) or node[field] != node[field].strip():
                raise ValueError(f"Node {field} must be a trimmed string")
        node["root"] = relative_asset(workspace, node.get("root", ""))
        root = resolve_asset(workspace, node["root"])
        node.setdefault("phase", "flat" if png_frames(workspace, root) else "loop")
        if node["phase"] not in {"flat", "in", "loop", "out"}:
            raise ValueError("Node phase must be flat, in, loop or out")
        node.setdefault("frameIntervalMs", 42)
        interval = node["frameIntervalMs"]
        if isinstance(interval, bool) or not isinstance(interval, int) or interval <= 0:
            raise ValueError("frameIntervalMs must be a positive integer")
        node.setdefault("loopMode", "loop")
        if node["loopMode"] not in {"loop", "once_then_hold"}:
            raise ValueError("loopMode must be loop or once_then_hold")
        for key in ("x", "y"):
            if key in node and (isinstance(node[key], bool) or not isinstance(node[key], (float, int)) or not math.isfinite(node[key])):
                raise ValueError(f"Node {key} must be finite")
        binding = tuple(node[k] for k in ("root", "phase", "frameIntervalMs", "loopMode"))
        if node["label"] in bindings and bindings[node["label"]] != binding:
            raise ValueError(f"Label {node['label']!r} has conflicting clip bindings")
        bindings[node["label"]] = binding
        if check_assets:
            clip_frames(workspace, node)
    for edge in graph["edges"]:
        for field in ("id", "from", "to"):
            if not isinstance(edge[field], str) or edge[field] != edge[field].strip():
                raise ValueError(f"Edge {field} must be a trimmed string")
    return graph
