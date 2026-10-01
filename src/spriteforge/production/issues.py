"""Existing QA facts and separately owned watch-review annotations."""
from __future__ import annotations

import threading
from pathlib import Path

from ..workspace import atomic_json, read_json, resolve_asset
from .records import (bound_clip, expected_anchor, load_character, load_owner, output_root,
                      production_dir, read_render)

ISSUE_LEVELS = ("fail", "fix", "watch")
REVIEW_FORMAT = "spriteforge.production.review.v1"
REVIEW_LOCK = threading.Lock()


def load_review(workspace: Path) -> dict:
    path = production_dir(workspace) / "review.json"
    review = read_json(path) if path.is_file() else {"format": REVIEW_FORMAT, "known": {}}
    if not isinstance(review, dict) or review.get("format") != REVIEW_FORMAT or not isinstance(review.get("known"), dict):
        raise ValueError("Unsupported production review format")
    return review


def set_known(workspace: Path, key: object, note: object = "", *, clear: bool = False) -> dict:
    if not isinstance(key, str) or not key.strip() or not isinstance(clear, bool):
        raise ValueError("Review annotation needs an issue key and boolean clear flag")
    if not clear and (not isinstance(note, str) or not note.strip()):
        raise ValueError("A known watch issue needs a note")
    load_character(workspace)
    with REVIEW_LOCK:
        review = load_review(workspace)
        if clear:
            review["known"].pop(key, None)
        else:
            from .project import overview
            from .records import now
            issue = next((issue for issue in overview(workspace)["issues"] if issue["key"] == key), None)
            if issue is None or issue["level"] != "watch":
                raise ValueError("Only a current watch issue can be marked known")
            review["known"][key] = {"at": now(), "note": note.strip()}
        atomic_json(production_dir(workspace) / "review.json", review)
    return {"key": key, "known": review["known"].get(key)}


def issue_summary(poses: list[dict], clips: list[dict], graph: dict, report: dict,
                  known: dict | None = None) -> list[dict]:
    """Stable issue keys project recorded levels; bound node/edge facts block export."""
    issues, known = [], known or {}
    bound = {node["id"]: node for node in graph.get("nodes", [])}

    def add(key: str, level: str, kind: str, message: str, *, blocks_export: bool = False, **facts) -> None:
        if level in ISSUE_LEVELS:
            issues.append({**facts, "key": key, "level": level, "kind": kind, "message": message,
                           "blocksExport": blocks_export and level == "fail",
                           "known": known.get(key) if level == "watch" else None})

    for pose in poses:
        if pose.get("needsRecheck"):
            add(f"pose:{pose['id']}:recheck", "watch", "pose", "Re-check the approved still against the base", pose=pose["id"])
    by_id = {clip["id"]: clip for clip in clips}
    for clip in clips:
        for check in (clip.get("render", {}).get("qa") or {}).get("checks", []):
            add(f"clip:{clip['id']}:{check['check']}", check["level"], "clip", check["message"], clip=clip["id"],
                **{key: value for key, value in check.items() if key not in {"check", "level", "message"}})
        for take in clip.get("takes", []):
            if take["id"] == clip.get("acceptedTake") or take.get("rejected"):
                continue
            qa = (take.get("candidateRender") or {}).get("qa") or {}
            checks = qa.get("checks", [])
            if qa.get("status") == "fail" and not any(check.get("level") == "fail" for check in checks):
                checks = [*checks, {"check": "status", "level": "fail", "message": "Candidate render QA failed"}]
            for check in checks:
                add(f"clip:{clip['id']}:take:{take['id']}:{check['check']}", check["level"], "clip", check["message"],
                    clip=clip["id"], take=take["id"], candidate=True,
                    **{key: value for key, value in check.items() if key not in {"check", "level", "message"}})
    for result in report.get("nodes", []):
        if not result.get("issues"):
            continue
        facts = {"node": result["node"], "clip": result["clip"]}
        if result["clip"] not in by_id:
            add(f"node:{result['node']}:unknownClip", "fail", "node", "Bound clip record missing", blocks_export=True, **facts)
            continue
        node, clip = bound[result["node"]], by_id[result["clip"]]
        render = clip.get("render") or {}
        if render.get("state") in {"missing", "stale"}:
            reason = render["state"]
            add(f"node:{result['node']}:{reason}", "fail", "node",
                "Render missing" if reason == "missing" else "Render out of date", blocks_export=True,
                reasons=render.get("reasons", []), **facts)
        if render.get("state") != "missing":
            for key in ("phase", "frameIntervalMs", "loopMode"):
                if node.get(key) != render.get(key):
                    add(f"node:{result['node']}:{key}", "fail", "node", f"Node {key} differs from its render",
                        blocks_export=True, expected=render.get(key), actual=node.get(key), **facts)
            if (render.get("qa") or {}).get("status") == "fail":
                add(f"node:{result['node']}:qa", "fail", "node", "Rendered clip QA failed", blocks_export=True, **facts)
    for edge in report.get("edges", []):
        add(f"edge:{edge['from']}->{edge['to']}", edge["level"], "edge", "Graph seam needs review", blocks_export=True,
            **{key: value for key, value in edge.items() if key != "level"},
            clips=list(dict.fromkeys(clip for node_id in (edge["from"], edge["to"])
                                     if (clip := bound_clip(bound[node_id].get("root"))) is not None)))
    return sorted(issues, key=lambda issue: (ISSUE_LEVELS.index(issue["level"]), issue["key"]))


def seam_detail(workspace: Path, key: str) -> dict:
    """Read the exact published endpoint frames using the existing seam calculations."""
    from .checks import EDGE_L, grade, seam
    from .geometry import measure
    from .media import read_bgra, sorted_pngs

    graph = read_json(resolve_asset(workspace, "graph_config.json"))
    matches = [edge for edge in graph["edges"] if f"edge:{edge['from']}->{edge['to']}" == key]
    if len(matches) != 1:
        raise ValueError("Seam key does not identify one current graph edge")
    edge, character = matches[0], load_character(workspace)
    nodes = {node["id"]: node for node in graph["nodes"]}

    def endpoint(node_id: str, tail: bool) -> tuple[dict, object]:
        node = nodes[node_id]
        clip_id = bound_clip(node.get("root"))
        if clip_id is None:
            raise ValueError("Seam endpoints must bind production renders")
        clip, render = load_owner(workspace, "clip", clip_id), read_render(workspace, clip_id)
        if render is None:
            raise ValueError("Seam endpoint has no render")
        frames = sorted_pngs(resolve_asset(workspace, output_root(clip_id)) / render["phase"])
        if not frames:
            raise ValueError("Seam endpoint has no frames")
        path = frames[-1] if tail else frames[0]
        raw = read_bgra(path)[0]
        margin = render["recipe"]["processing"].get("marginPx", 0)
        pixels = raw[:, margin:raw.shape[1] - margin] if margin else raw
        pose_id = clip["to"] if tail else clip["from"]
        actual = measure(pixels)
        return {"node": node_id, "clip": clip_id, "pose": pose_id, "path": path.relative_to(workspace).as_posix(),
                "marginPx": margin, "size": {"w": raw.shape[1], "h": raw.shape[0]},
                "actual": {key: actual[key] for key in ("headTopY", "headCenterX")},
                "expected": expected_anchor(character, load_owner(workspace, "pose", pose_id))}, pixels

    tail, tail_pixels = endpoint(edge["from"], True)
    head, head_pixels = endpoint(edge["to"], False)
    result = seam(character, tail_pixels, head_pixels, EDGE_L)
    levels = {"headTop": "pass" if abs(result["dHeadTop"]) <= character["tolerances"]["headTopPx"] else "fail",
              "headCenter": "pass" if abs(result["dHeadCenter"]) <= character["tolerances"]["headCenterPx"] else "fail",
              "faceL": grade(abs(result["faceL"]), EDGE_L) if result["faceL"] is not None else "watch"}
    return {"key": key, "level": result["level"], "metrics": {**{key: value for key, value in result.items() if key != "level"},
                                                               "levels": levels}, "tail": tail, "head": head}
