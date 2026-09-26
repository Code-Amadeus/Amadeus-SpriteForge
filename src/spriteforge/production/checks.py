"""Production QA on PNG sources: still geometry, clip integrity and seams.

Levels are pass < watch < fix < fail; only fail blocks export. Seam lightness
thresholds follow docs/production.md (loop wrap 1.0 / 1.5 / 2.2 L*, graph edge
1.2 / 1.8 / 2.5 L*). Geometry at a seam must stay within the character's head
tolerances, because that is what makes two clips overlap.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from ..workspace import resolve_asset
from .geometry import face_lightness, face_roi, measure
from .media import read_bgra, sorted_pngs
from .records import bound_clip, canvas_size, load_owner, output_root, read_render, render_freshness

LEVELS = ("pass", "watch", "fix", "fail")
WRAP_L = (1.0, 1.5, 2.2)
EDGE_L = (1.2, 1.8, 2.5)
AREA_STEP_FAIL = 0.12
FLASH_WATCH = 3.0
LOOP_SPAN_WATCH = 6
# Head and tail registrations of one take map the same video onto the same canvas; with
# a locked camera they agree (real Wan takes: <0.2% scale, <1px). Disagreement means the
# camera drifted or an endpoint still is misplaced.
DRIFT_SCALE = (0.01, 0.03, 0.03)
DRIFT_PX = (4.0, 12.0, 12.0)


def worst(levels) -> str:
    return max(levels, key=LEVELS.index, default="pass")


def grade(value: float, bounds: tuple[float, float, float]) -> str:
    return next((level for level, bound in zip(LEVELS, bounds) if value < bound), "fail")


def _check(name: str, level: str, message: str, **data) -> dict:
    return {"check": name, "level": level, "message": message, **data}


def _values(seam_report: dict) -> dict:
    return {k: v for k, v in seam_report.items() if k != "level"}


def expected_anchor(character: dict, pose: dict) -> dict:
    anchors = character.get("anchors") or {}
    return {key: (pose.get("expected") or {}).get(key, anchors.get(key)) for key in ("headTopY", "headCenterX")}


def still_report(character: dict, pose: dict, image: np.ndarray, normalization: dict | None = None) -> dict:
    width, height = canvas_size(character)
    metrics = measure(image)
    checks = []
    if metrics["size"] != [width, height]:
        checks.append(_check("canvas", "fail", f"Still is {metrics['size']}, canvas is {[width, height]}"))
    cut = [edge for edge in metrics["edges"] if edge not in character["cutEdges"]]
    if cut:
        checks.append(_check("edges", "fail", f"Character is cut by the {', '.join(cut)} edge"))
    anchors, tolerance = character.get("anchors"), character["tolerances"]
    if anchors and pose["id"] != character["basePose"]:
        expected = expected_anchor(character, pose)
        for key, limit in (("headTopY", tolerance["headTopPx"]), ("headCenterX", tolerance["headCenterPx"])):
            delta = round(metrics[key] - expected[key], 2)
            if abs(delta) > limit:
                checks.append(_check(key, "fail", f"{key} is {delta:+g}px from the expected {expected[key]} "
                                     f"(tolerance {limit}px)", delta=delta))
        ratio = metrics["area"] / max(1, anchors["area"]) - 1
        if abs(ratio) * 100 > tolerance["areaPct"]:
            checks.append(_check("area", "watch", f"Visible area differs from the base still by {ratio:+.0%}"))
    if (normalization or {}).get("method") == "fit":
        registration = normalization.get("registration") or {}
        agreement = (f"{registration['inliers']}/{registration['matches']} matches agree" if "inliers" in registration
                     else registration.get("error", "no registration"))
        checks.append(_check("framing", "watch", f"The pose changed ({agreement}), so the generator's framing was kept; "
                             "confirm the overlay against the base still"))
    return {"status": worst(c["level"] for c in checks), "metrics": metrics, "checks": checks}


def seam(character: dict, tail: np.ndarray, head: np.ndarray, bounds: tuple[float, float, float]) -> dict:
    width, height = canvas_size(character)
    a, b = measure(tail), measure(head)
    roi = face_roi(a, width, height)
    lt, lh = face_lightness(tail, roi), face_lightness(head, roi)
    delta = None if lt is None or lh is None else round(lh - lt, 3)
    d_top, d_center = b["headTopY"] - a["headTopY"], round(b["headCenterX"] - a["headCenterX"], 2)
    tolerance = character["tolerances"]
    aligned = abs(d_top) <= tolerance["headTopPx"] and abs(d_center) <= tolerance["headCenterPx"]
    level = worst([grade(abs(delta), bounds) if delta is not None else "watch", "pass" if aligned else "fail"])
    return {"faceL": delta, "dHeadTop": d_top, "dHeadCenter": d_center, "level": level}


def clip_report(character: dict, frames: list[Path], kind: str, start: np.ndarray, end: np.ndarray,
                drift: dict | None = None) -> dict:
    """QA of rendered frames against the pose stills, which are on the clip's (possibly widened) canvas."""
    width, height = canvas_size(character)
    checks, tops, centers = [], [], []
    if drift:
        level = worst([grade(abs(drift["scale"]), DRIFT_SCALE), grade(max(abs(drift["tx"]), abs(drift["ty"])), DRIFT_PX)])
        if level != "pass":
            checks.append(_check("drift", level, "Head and tail registrations disagree (scale "
                                 f"{drift['scale']:+.2%}, shift {drift['tx']:+.1f},{drift['ty']:+.1f}px): the camera "
                                 "drifted or an endpoint still is misplaced", **drift))
    bad_size, bad_edges, broken, flashes = [], [], [], []
    first = previous = previous_metrics = None
    for index, path in enumerate(frames):
        image, _ = read_bgra(path)
        if image.shape[:2] != start.shape[:2]:
            bad_size.append(index)
            previous = None
            continue
        metrics = measure(image)
        tops.append(metrics["headTopY"])
        centers.append(metrics["headCenterX"])
        if any(edge not in character["cutEdges"] for edge in metrics["edges"]):
            bad_edges.append(index)
        if previous is not None:
            if abs(metrics["area"] / max(1, previous_metrics["area"]) - 1) > AREA_STEP_FAIL:
                broken.append(index)
            roi = face_roi(previous_metrics, width, height)
            lp, lc = face_lightness(previous, roi), face_lightness(image, roi)
            if lp is not None and lc is not None and abs(lc - lp) > FLASH_WATCH:
                flashes.append(index)
        first = image if first is None else first
        previous, previous_metrics = image, metrics
    if bad_size:
        checks.append(_check("canvas", "fail", f"{len(bad_size)} frame(s) do not match the canvas", frames=bad_size[:20]))
    if bad_edges:
        checks.append(_check("edges", "fail", f"{len(bad_edges)} frame(s) touch a closed canvas edge", frames=bad_edges[:20]))
    if broken:
        checks.append(_check("broken", "fail", f"Visible area jumps by more than {AREA_STEP_FAIL:.0%} at frame(s) "
                             f"{broken[:10]}", frames=broken[:20]))
    if flashes:
        checks.append(_check("flash", "watch", f"Face lightness jumps by more than {FLASH_WATCH} L* at frame(s) "
                             f"{flashes[:10]}", frames=flashes[:20]))
    report = {"frames": len(frames), "spans": {"headTopY": int(np.ptp(tops)) if tops else None,
                                               "headCenterX": round(float(np.ptp(centers)), 2) if centers else None}}
    if first is not None and previous is not None:
        report["head"] = seam(character, start, first, EDGE_L)
        report["tail"] = seam(character, previous, end, EDGE_L)
        for name in ("head", "tail"):
            if report[name]["level"] != "pass":
                checks.append(_check(name, report[name]["level"], f"The {name} frame differs from its pose still",
                                     **_values(report[name])))
        if kind == "loop":
            report["wrap"] = seam(character, previous, first, WRAP_L)
            if report["wrap"]["level"] != "pass":
                checks.append(_check("wrap", report["wrap"]["level"], "The loop seam is visible", **_values(report["wrap"])))
            if max(report["spans"]["headTopY"], report["spans"]["headCenterX"]) > LOOP_SPAN_WATCH:
                checks.append(_check("span", "watch", f"The head moves more than {LOOP_SPAN_WATCH}px inside the loop",
                                     **report["spans"]))
    report["checks"] = checks
    report["status"] = worst(c["level"] for c in checks)
    return report


def graph_report(workspace: Path, graph: dict, character: dict) -> dict:
    """Seams between graph nodes bound to production clips, plus node/render agreement."""
    nodes, edges = [], []
    ends: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    bound = {n["id"]: bound_clip(n.get("root")) for n in graph.get("nodes", [])}
    for node in graph.get("nodes", []):
        clip_id = bound[node["id"]]
        if clip_id is None:
            continue
        render = read_render(workspace, clip_id)
        _, issues = render_freshness(workspace, load_owner(workspace, "clip", clip_id))
        if render is not None:
            for key, value in (("phase", render["phase"]), ("frameIntervalMs", render["frameIntervalMs"]),
                               ("loopMode", render["loopMode"])):
                if node.get(key) != value:
                    issues.append(f"node {key}={node.get(key)!r}, render {value!r}; run graph-sync")
            if render["qa"]["status"] == "fail":
                issues.append("clip QA failed")
            frames = sorted_pngs(resolve_asset(workspace, output_root(clip_id)) / render["phase"])
            margin = render["recipe"]["processing"].get("marginPx", 0)
            if frames:  # seams compare the canvas itself, without a widened clip's margins
                ends[node["id"]] = tuple(image[:, margin:image.shape[1] - margin]
                                         for image in (read_bgra(frames[0])[0], read_bgra(frames[-1])[0]))
        nodes.append({"node": node["id"], "label": node.get("label"), "clip": clip_id, "issues": issues,
                      "level": "fail" if issues else "pass"})
    for edge in graph.get("edges", []):
        source, target = edge.get("from"), edge.get("to")
        if source == target or source not in ends or target not in ends:
            continue
        edges.append({"edge": edge.get("id"), "from": source, "to": target,
                      **seam(character, ends[source][1], ends[target][0], EDGE_L)})
    return {"status": worst([*(n["level"] for n in nodes), *(e["level"] for e in edges)]), "nodes": nodes, "edges": edges}
