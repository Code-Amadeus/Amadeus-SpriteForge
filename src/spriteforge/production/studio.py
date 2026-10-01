"""Read-only Studio summaries of existing production and QA facts.

These helpers do not make decisions or add QA rules. The overview supplies its
already-read records; graph seams come from the same report used by export.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..workspace import read_json, resolve_asset
from .records import bound_clip, output_root, production_dir, recorded_credit_delta

ISSUE_LEVELS = ("fail", "fix", "watch")


def variant_groups(clips: list[dict]) -> list[dict]:
    """Sibling clips share kind/endpoints; a mouth makes a loop a speaking loop."""
    groups: dict[tuple[str, str, str], list[str]] = {}
    for clip in clips:
        kind = "speaking" if clip["kind"] == "loop" and clip.get("mouth") else clip["kind"]
        groups.setdefault((kind, clip["from"], clip["to"]), []).append(clip["id"])
    return [{"key": f"{kind}:{source}->{target}", "type": kind, "from": source, "to": target,
             "clips": sorted(ids)} for (kind, source, target), ids in sorted(groups.items())]


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp.astimezone(timezone.utc)


def _number(value: object) -> int | float | None:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def usage_summary(poses: list[dict], clips: list[dict], *, at: datetime | None = None,
                  concepts: list[dict] | None = None) -> dict:
    """Seven days of recorded usage, without estimating missing balances or timing.

Only the latest render of each clip is retained on disk. This is consequently
the sum of retained renders, not a history of overwritten processing runs.
"""
    at = at or datetime.now(timezone.utc)
    at = at.replace(tzinfo=timezone.utc) if at.tzinfo is None else at.astimezone(timezone.utc)
    since = at - timedelta(days=7)
    wan, images, durations = [], 0, []
    balance_records = []
    for owner in [*poses, *clips]:
        for take in owner.get("takes", []):
            stamp = _timestamp(take.get("createdAt"))
            source = take.get("source") or {}
            if source.get("provider") == "wan-cli":
                before = _number((source.get("balanceBefore") or {}).get("credits"))
                after = _number((source.get("balanceAfter") or {}).get("credits"))
                balance = after if after is not None else before
                if stamp is not None and stamp <= at and balance is not None:
                    balance_records.append((stamp, take["id"], balance))
                if stamp is not None and since <= stamp <= at:
                    wan.append(recorded_credit_delta(source))
            if stamp is not None and since <= stamp <= at and source.get("provider") == "gpt-image" \
                    and (take.get("media") or {}).get("source"):
                images += 1
    for sheet in concepts or []:
        records = [sheet, *(attempt for cell in sheet["cells"] for attempt in cell.get("rerolls", []))]
        for record in records:
            stamp = _timestamp(record.get("createdAt"))
            if stamp is not None and since <= stamp <= at and record.get("provider") == "gpt-image" \
                    and record.get("sourceFile") and record.get("size"):
                images += 1
    for clip in clips:
        render = clip.get("render") or {}
        stamp = _timestamp(render.get("renderedAt"))
        if stamp is not None and since <= stamp <= at:
            duration = _number(render.get("durationS"))
            durations.append(duration if duration is not None and duration >= 0 else None)
    known_durations = [duration for duration in durations if duration is not None]
    return {"days": 7, "since": since.isoformat(timespec="seconds"),
            "wan": {"usedCredits": sum(wan) if wan and all(value is not None for value in wan) else None,
                    "balance": max(balance_records, key=lambda item: item[:2])[2] if balance_records else None},
            "gptImage": {"images": images},
            "local": {"durationS": round(sum(known_durations), 3) if durations and len(known_durations) == len(durations)
                      else None, "renders": len(durations), "unknownDurations": len(durations) - len(known_durations)}}


def issue_summary(poses: list[dict], clips: list[dict], graph: dict, report: dict,
                  known: dict | None = None) -> list[dict]:
    """Project existing recheck, render, binding and seam results into stable keys."""
    issues = []
    known = known or {}
    bound = {node["id"]: node for node in graph.get("nodes", [])}
    exported = {clip for node in bound.values() if (clip := bound_clip(node.get("root"))) is not None}

    def add(key: str, level: str, kind: str, message: str, *, blocks_export: bool = False, **facts) -> None:
        if level in ISSUE_LEVELS:
            issues.append({**facts, "key": key, "level": level, "kind": kind, "message": message,
                           "blocksExport": blocks_export and level == "fail",
                           "known": known.get(key) if level == "watch" else None})

    for pose in poses:
        if pose.get("needsRecheck"):
            add(f"pose:{pose['id']}:recheck", "watch", "pose", "Re-check the approved still against the base",
                pose=pose["id"])
    by_id = {clip["id"]: clip for clip in clips}
    for clip in clips:
        for check in (clip.get("render", {}).get("qa") or {}).get("checks", []):
            add(f"clip:{clip['id']}:{check['check']}", check["level"], "clip", check["message"],
                blocks_export=clip["id"] in exported,
                clip=clip["id"], **{key: value for key, value in check.items() if key not in {"check", "level", "message"}})
    # The export report owns these failures. Stable reason keys come from the
    # corresponding recorded binding fields, rather than from diagnostic prose.
    for result in report.get("nodes", []):
        if not result.get("issues"):
            continue
        facts = {"node": result["node"], "clip": result["clip"]}
        if result["clip"] not in by_id:
            add(f"node:{result['node']}:unknownClip", "fail", "node", "Bound clip record missing",
                blocks_export=True, **facts)
            continue
        node, clip = bound[result["node"]], by_id[result["clip"]]
        render = clip.get("render") or {}
        if render.get("state") in {"missing", "stale"}:
            reason = render["state"]
            add(f"node:{result['node']}:{reason}", "fail", "node",
                "Render missing" if reason == "missing" else "Render out of date",
                blocks_export=True, reasons=render.get("reasons", []), **facts)
        if render.get("state") != "missing":
            for key in ("phase", "frameIntervalMs", "loopMode"):
                if node.get(key) != render.get(key):
                    add(f"node:{result['node']}:{key}", "fail", "node", f"Node {key} differs from its render",
                        blocks_export=True, expected=render.get(key), actual=node.get(key), **facts)
    for edge in report.get("edges", []):
        add(f"edge:{edge['from']}->{edge['to']}", edge["level"], "edge", "Graph seam needs review",
            blocks_export=True,
            **{key: value for key, value in edge.items() if key != "level"},
            clips=list(dict.fromkeys(clip for node_id in (edge["from"], edge["to"])
                                     if (clip := bound_clip(bound[node_id].get("root"))) is not None)))
    return sorted(issues, key=lambda issue: (ISSUE_LEVELS.index(issue["level"]), issue["key"]))


def studio_summary(workspace: Path, character: dict, poses: list[dict], clips: list[dict]) -> dict:
    """Add Studio's read model to an existing overview without reading it again."""
    from .checks import graph_report
    from .concepts import list_sheets

    sheets = list_sheets(workspace)
    current = next((sheet["id"] for sheet in reversed(sheets) if sheet["state"] == "ready"), None)
    concepts = [{**sheet, "current": sheet["id"] == current, "version": index} for index, sheet in enumerate(sheets, 1)]

    graph_path = resolve_asset(workspace, "graph_config.json")
    graph = read_json(graph_path) if graph_path.is_file() else {"nodes": [], "edges": []}
    review_path = production_dir(workspace) / "review.json"
    known = (read_json(review_path).get("known") or {}) if review_path.is_file() else {}
    by_id = {clip["id"]: clip for clip in clips}
    nodes = list(graph.get("nodes", []))
    conflicts = []
    for clip_id in character.get("runtimeClips") or []:
        # Export adds these unconnected bindings. Retain missing renders here so
        # Overview can explain the failure that export_nodes rejects immediately.
        render = (by_id.get(clip_id) or {}).get("render") or {}
        node = {"id": f"runtime:{clip_id}", "label": clip_id, "root": output_root(clip_id),
                **{key: render.get(key) for key in ("phase", "frameIntervalMs", "loopMode")}}
        if any(existing.get("label") == clip_id for existing in graph.get("nodes", [])):
            conflicts.append({"key": f"node:{node['id']}:labelConflict", "level": "fail", "kind": "node",
                              "message": "Runtime clip is also a graph node label", "node": node["id"],
                              "clip": clip_id, "blocksExport": True, "known": None})
        nodes.append(node)
    scope = {**graph, "nodes": nodes}
    missing = [node for node in nodes if (clip_id := bound_clip(node.get("root"))) is not None and clip_id not in by_id]
    report = graph_report(workspace, {**scope, "nodes": [node for node in nodes if node not in missing]}, character)
    report["nodes"] += [{"node": node["id"], "clip": bound_clip(node["root"]), "issues": ["Bound clip record missing"]}
                        for node in missing]
    issues = issue_summary(poses, clips, scope, report, known) + conflicts
    issues.sort(key=lambda issue: (ISSUE_LEVELS.index(issue["level"]), issue["key"]))
    return {"concepts": concepts, "issues": issues,
            "variants": variant_groups(clips), "usage": usage_summary(poses, clips, concepts=concepts)}
