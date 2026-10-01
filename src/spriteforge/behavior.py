"""Pure, deterministic graph-route statistics.

Matches SpriteForgeAnimator's duration fallback, weighted automatic traversal
and first-hop BFS ordering. It does not implement semantic label aliases, root
fallback/teleport, speech holds or post-speech release behavior.
"""
from __future__ import annotations

import math
from collections import deque

MASK32 = 0xFFFFFFFF
DEFAULT_DURATION = 2.5


def mulberry32(seed: int):
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= MASK32:
        raise ValueError("Seed must be an unsigned 32-bit integer")
    state = seed

    def random() -> float:
        nonlocal state
        state = (state + 0x6D2B79F5) & MASK32
        value = ((state ^ (state >> 15)) * (state | 1)) & MASK32
        value ^= (value + (((value ^ (value >> 7)) * (value | 61)) & MASK32)) & MASK32
        return ((value ^ (value >> 14)) & MASK32) / 4294967296

    return random


def root_node(graph: dict) -> str | None:
    nodes = graph.get("nodes", [])
    return next((node["id"] for node in nodes if node.get("isRoot")), nodes[0]["id"] if nodes else None)


def reachable(graph: dict, *, automatic: bool = False) -> set[str]:
    root = root_node(graph)
    if root is None:
        return set()
    found, queue = {root}, deque([root])
    while queue:
        node = queue.popleft()
        for edge in graph["edges"]:
            if edge["from"] == node and (not automatic or edge.get("prob", 0) > 0) and edge["to"] not in found:
                found.add(edge["to"])
                queue.append(edge["to"])
    return found


def topology_summary(graph: dict) -> dict:
    all_reached, auto_reached = reachable(graph), reachable(graph, automatic=True)
    auto_sources = {edge["from"] for edge in graph["edges"] if edge.get("prob", 0) > 0}
    return {"unreachable": [node["id"] for node in graph["nodes"] if node["id"] not in all_reached],
            "intentOnly": [node["id"] for node in graph["nodes"] if node["id"] in all_reached - auto_reached],
            "deadEnds": [node["id"] for node in graph["nodes"] if node["id"] not in auto_sources
                         and node.get("loopMode", "loop") == "once_then_hold"],
            "intentExitLoops": [node["id"] for node in graph["nodes"] if node["id"] not in auto_sources
                                and node.get("loopMode", "loop") == "loop"]}


def path_to_any(graph: dict, start: str | None, targets: set[str]) -> list[str] | None:
    """Diagnostic BFS path: first step may be manual; later steps are automatic.

    Stable sorting prefers a direct target, then a manual edge. Remaining ties
    preserve saved edge order, exactly as the runtime first-hop helper does.
    """
    if not start or not targets:
        return None
    if start in targets:
        return [start]
    visited, queue = {start}, deque([(start, [start])])
    while queue:
        node, path = queue.popleft()
        edges = [edge for edge in graph["edges"] if edge["from"] == node
                 and (edge.get("prob", 0) > 0 or (node == start and edge.get("prob", 0) == 0))]
        edges.sort(key=lambda edge: (0 if edge["to"] in targets else 1, 0 if edge.get("prob", 0) == 0 else 1))
        for edge in edges:
            target = edge["to"]
            if target in targets:
                return [*path, target]
            if target not in visited:
                visited.add(target)
                queue.append((target, [*path, target]))
    return None


def first_hop_to_any(graph: dict, start: str | None, targets: set[str]) -> str | None:
    path = path_to_any(graph, start, targets)
    return path[1] if path and len(path) > 1 else path[0] if path else None


def _auto_edge(edges: list[dict], random) -> dict | None:
    if not edges:
        return None
    value, cumulative = random() * sum(edge["prob"] for edge in edges), 0.0
    for edge in edges:
        cumulative += edge["prob"]
        if value <= cumulative:
            return edge
    return edges[-1]


def simulate(graph: dict, durations: dict[str, float], *, seconds: float | None = None, steps: int | None = None,
             seed: int = 1, events: list[dict] | None = None, speech_targets: set[str] | None = None,
             failing_edges: set[str] | None = None, trace: bool = False) -> dict:
    """Play each node, then take one weighted edge or one pending intent hop.

    Events apply at the next completed node boundary. Their BFS paths explain
    reachability; only the first hop is forced, and weighted traversal resumes.
    """
    random = mulberry32(seed)
    if (seconds is None) == (steps is None):
        raise ValueError("Simulation needs either seconds or steps")
    if seconds is not None and (isinstance(seconds, bool) or not isinstance(seconds, (int, float))
                                or not math.isfinite(seconds) or seconds <= 0):
        raise ValueError("Simulation seconds must be finite and positive")
    if steps is not None and (isinstance(steps, bool) or not isinstance(steps, int) or steps < 1):
        raise ValueError("Simulation steps must be a positive integer")
    nodes = {node["id"]: node for node in graph["nodes"]}
    auto = {node: [edge for edge in graph["edges"] if edge["from"] == node and edge.get("prob", 0) > 0] for node in nodes}
    resolved = {node: duration if isinstance(duration := durations.get(node), (int, float))
                and not isinstance(duration, bool) and math.isfinite(duration) and duration > 0 else DEFAULT_DURATION for node in nodes}
    pending = []
    for index, event in enumerate(events or []):
        if not isinstance(event, dict) or set(event) not in ({"atS", "label"}, {"atS", "speech"}):
            raise ValueError("Trigger events accept atS and either label or speech:true")
        at = event.get("atS")
        if isinstance(at, bool) or not isinstance(at, (int, float)) or not math.isfinite(at) or at < 0 \
                or (seconds is not None and at >= seconds):
            raise ValueError("Event atS must be inside the simulation")
        speech = event.get("speech") is True
        label = event.get("label")
        if not speech and (not isinstance(label, str) or not label.strip()):
            raise ValueError("Each event needs either a label or speech:true")
        targets = set(speech_targets or []) if speech else {node["id"] for node in graph["nodes"] if node["label"] == label}
        pending.append({"index": index, **event, "targets": sorted(targets), "path": [], "reachable": False,
                        "reached": False, "visitedTargets": [], "appliedAtS": None, "from": None})
    pending.sort(key=lambda event: (event["atS"], event["index"]))
    node_time, visits = dict.fromkeys(nodes, 0.0), dict.fromkeys(nodes, 0)
    route, used, jumps = [], set(), set()
    current, elapsed, count, changes, event_index, active, incoming, marker = root_node(graph), 0.0, 0, 0, 0, None, None, None
    while current is not None and (count < steps if steps is not None else elapsed < seconds):
        duration = resolved[current] if seconds is None else min(resolved[current], seconds - elapsed)
        node_time[current] += duration
        visits[current] += 1
        if active is not None and current in active["targets"]:
            active["reached"] = True
            if current not in active["visitedTargets"]:
                active["visitedTargets"].append(current)
        if trace:
            route.append({"node": current, "label": nodes[current]["label"], "startS": round(elapsed, 6),
                          "durationS": round(duration, 6), "edge": incoming["id"] if incoming else None,
                          "seamFail": bool(incoming and incoming["id"] in (failing_edges or set())),
                          **({"event": marker} if marker is not None else {})})
        elapsed += duration
        count += 1
        if count == steps or (seconds is not None and elapsed >= seconds):
            break
        marker = None
        edge = None
        if event_index < len(pending) and pending[event_index]["atS"] <= elapsed:
            active = pending[event_index]
            event_index += 1
            targets = set(active["targets"])
            path = path_to_any(graph, current, targets)
            active.update(path=path or [], reachable=bool(path), appliedAtS=round(elapsed, 6), **{"from": current})
            marker = active["index"]
            if path and len(path) > 1:
                candidates = [candidate for candidate in graph["edges"] if candidate["from"] == current and candidate.get("prob", 0) >= 0]
                candidates.sort(key=lambda candidate: (0 if candidate["to"] in targets else 1,
                                                        0 if candidate.get("prob", 0) == 0 else 1))
                edge = next(candidate for candidate in candidates if candidate["to"] == path[1])
            elif not path:
                edge = _auto_edge(auto[current], random)
        else:
            edge = _auto_edge(auto[current], random)
        target = edge["to"] if edge else current
        changes += target != current
        if edge:
            if edge.get("prob", 0) > 0:
                used.add(edge["id"])
            if edge["id"] in (failing_edges or set()):
                jumps.add(edge["id"])
        incoming, current = edge, target
    return {"seconds": round(elapsed, 6), "nodeTime": {node: round(value, 6) for node, value in node_time.items()},
            "nodeVisits": visits, "changes": changes, "changesPerMinute": round(changes * 60 / elapsed, 4) if elapsed else 0,
            "autoEdgesUsed": [edge["id"] for edge in graph["edges"] if edge["id"] in used],
            "autoEdgesTotal": sum(edge.get("prob", 0) > 0 for edge in graph["edges"]),
            "jumps": [edge["id"] for edge in graph["edges"] if edge["id"] in jumps],
            "route": route, "events": sorted(pending, key=lambda event: event["index"])}


def pose_coverage(poses: list[dict], clips: list[dict], bindings: dict[str, str | None], base_pose: str) -> list[dict]:
    """Availability and original QA levels come from production records, apart from graph membership."""
    result, exported = [], set(bindings.values())
    levels = ("pass", "watch", "fix", "fail")
    for pose in poses:
        pose_id = pose["id"]
        groups = {"enter": [clip for clip in clips if clip["kind"] == "transition" and clip["to"] == pose_id],
                  "exit": [clip for clip in clips if clip["kind"] == "transition" and clip["from"] == pose_id],
                  "loop": [clip for clip in clips if clip["kind"] == "loop" and clip["from"] == pose_id and not clip.get("mouth")],
                  "speaking": [clip for clip in clips if clip["kind"] == "loop" and clip["from"] == pose_id and clip.get("mouth")]}
        row = {"pose": pose_id, "inGraph": any(clip["id"] in exported and pose_id in {clip["from"], clip["to"]} for clip in clips)}
        for kind, entries in groups.items():
            applicable = not (pose_id == base_pose and kind in {"enter", "exit"})
            entries = entries if applicable else []
            recorded = [(clip.get("render", {}).get("qa") or {}).get("status") for clip in entries]
            grades = [level for level in recorded if level in levels]
            available = sum(bool(clip.get("acceptedTake")) and clip.get("render", {}).get("state") == "current"
                            and grade in {"pass", "watch", "fix"} for clip, grade in zip(entries, recorded))
            row[kind] = {"applicable": applicable, "clips": [clip["id"] for clip in entries], "available": available,
                         "level": max(grades, key=levels.index) if grades else None}
        result.append(row)
    return result
