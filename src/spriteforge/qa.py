#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np


PHASES = ("in", "loop", "out")


@dataclass
class FrameInfo:
    path: Path
    width: int
    height: int
    cx: float
    feet_y: float
    bbox: tuple[int, int, int, int] | None
    mask_area: int
    edge_touch: dict[str, bool]
    lab_mean: list[float]
    lab_std: list[float]


@dataclass
class ClipInfo:
    clip_id: str
    role: str
    files: list[Path]
    frames: list[FrameInfo]


def slug(value: str, fallback: str = "asset") -> str:
    text = re.sub(r"[^0-9A-Za-z._-]+", "_", str(value or "").strip())
    text = re.sub(r"_+", "_", text).strip("._-")
    return text or fallback


def read_image(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise RuntimeError(f"failed to read image: {path}")
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
    elif img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    return img


def foreground_mask(img: np.ndarray) -> np.ndarray:
    if img.shape[2] == 4 and int(img[:, :, 3].max()) > 0 and int(img[:, :, 3].min()) < 250:
        return img[:, :, 3] > 8

    bgr = img[:, :, :3].astype(np.int16)
    h, w = bgr.shape[:2]
    border = np.concatenate(
        [
            bgr[0:4, :, :].reshape(-1, 3),
            bgr[max(0, h - 4):h, :, :].reshape(-1, 3),
            bgr[:, 0:4, :].reshape(-1, 3),
            bgr[:, max(0, w - 4):w, :].reshape(-1, 3),
        ],
        axis=0,
    )
    bg = np.median(border, axis=0)
    dist = np.linalg.norm(bgr - bg, axis=2)
    maxc = bgr.max(axis=2)
    minc = bgr.min(axis=2)
    not_plain_white = maxc < 245
    not_plain_black = maxc > 8
    return (dist > 24) & not_plain_white & not_plain_black


def alpha_bbox(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    ys, xs = np.where(mask)
    if ys.size == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def anchor_from_mask(mask: np.ndarray) -> tuple[float, float, tuple[int, int, int, int] | None]:
    bbox = alpha_bbox(mask)
    if bbox is None:
        h, w = mask.shape[:2]
        return w * 0.5, h - 1.0, None
    x1, y1, x2, y2 = bbox
    row_counts = mask.sum(axis=1).astype(np.int32)
    max_row = int(row_counts.max()) if row_counts.size else 0
    row_thr = max(12, int(max_row * 0.35))
    candidates = np.where(row_counts >= row_thr)[0]
    feet_y = float(candidates[-1]) if candidates.size else float(y2)
    band_top = max(0, int(feet_y) - 16)
    band = mask[band_top:int(feet_y) + 1, :]
    xs = np.where(band)[1] if band.size else np.array([], dtype=np.int32)
    cx = float(np.median(xs)) if xs.size else float((x1 + x2) * 0.5)
    return cx, feet_y, bbox


def lab_stats(img: np.ndarray, mask: np.ndarray) -> tuple[list[float], list[float]]:
    bgr = img[:, :, :3]
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    vals = lab[mask]
    if vals.size == 0:
        vals = lab.reshape(-1, 3)
    mean = vals.mean(axis=0)
    std = np.maximum(vals.std(axis=0), 1.0)
    return [round(float(x), 3) for x in mean], [round(float(x), 3) for x in std]


def frame_info(path: Path) -> FrameInfo:
    img = read_image(path)
    mask = foreground_mask(img)
    h, w = img.shape[:2]
    cx, feet_y, bbox = anchor_from_mask(mask)
    area = int(mask.sum())
    edge_touch = {
        "left": bool(mask[:, 0:3].any()),
        "right": bool(mask[:, max(0, w - 3):w].any()),
        "top": bool(mask[0:3, :].any()),
        "bottom": bool(mask[max(0, h - 3):h, :].any()),
    }
    mean, std = lab_stats(img, mask)
    return FrameInfo(
        path=path,
        width=w,
        height=h,
        cx=round(cx, 3),
        feet_y=round(feet_y, 3),
        bbox=bbox,
        mask_area=area,
        edge_touch=edge_touch,
        lab_mean=mean,
        lab_std=std,
    )


def visual_delta(a_path: Path, b_path: Path) -> dict[str, float]:
    a = read_image(a_path)
    b = read_image(b_path)
    if a.shape[:2] != b.shape[:2]:
        b = cv2.resize(b, (a.shape[1], a.shape[0]), interpolation=cv2.INTER_AREA)
    ma = foreground_mask(a)
    mb = foreground_mask(b)
    mask = ma | mb
    if int(mask.sum()) < 16:
        mask = np.ones(a.shape[:2], dtype=bool)
    ga = cv2.cvtColor(a[:, :, :3], cv2.COLOR_BGR2GRAY).astype(np.float32)
    gb = cv2.cvtColor(b[:, :, :3], cv2.COLOR_BGR2GRAY).astype(np.float32)
    diff = np.abs(ga - gb)[mask]
    mse = float(np.mean((ga - gb)[mask] ** 2))
    rmse = math.sqrt(mse)
    lab_a = cv2.cvtColor(a[:, :, :3], cv2.COLOR_BGR2LAB).astype(np.float32)
    lab_b = cv2.cvtColor(b[:, :, :3], cv2.COLOR_BGR2LAB).astype(np.float32)
    lab_diff = np.abs(lab_a - lab_b)[mask]
    return {
        "gray_mean_abs": round(float(diff.mean()), 3),
        "gray_p95_abs": round(float(np.percentile(diff, 95)), 3),
        "gray_rmse": round(float(rmse), 3),
        "lab_mean_abs": round(float(lab_diff.mean()), 3),
    }


def collect_legacy_clips(root: Path) -> dict[str, ClipInfo]:
    clips: dict[str, ClipInfo] = {}
    for phase in PHASES:
        d = root / phase
        files = sorted(d.glob("*.png")) if d.is_dir() else []
        if files:
            clips[phase] = ClipInfo(clip_id=phase, role=phase, files=files, frames=[])
    return clips


def collect_graph_clips(root: Path) -> dict[str, ClipInfo]:
    clips: dict[str, ClipInfo] = {}
    for d in sorted([p for p in root.rglob("*") if p.is_dir()]):
        files = sorted(d.glob("*.png"))
        if not files:
            continue
        rel = d.relative_to(root).as_posix()
        parts = rel.split("/")
        role = parts[-1].lower()
        if role not in PHASES and role not in ("idle", "standby", "enter", "leave", "transition"):
            role = "clip"
        clip_id = slug(rel.replace("/", "__"))
        clips[clip_id] = ClipInfo(clip_id=clip_id, role=role, files=files, frames=[])
    return clips


def infer_state_name(clips: dict[str, ClipInfo], fallback: str) -> str:
    names: list[str] = []
    pattern = re.compile(r".+_([A-Za-z0-9]+)_(?:in|loop|out)\d+\.png$", re.IGNORECASE)
    for clip in clips.values():
        for fp in clip.files[:8]:
            m = pattern.match(fp.name)
            if m:
                names.append(m.group(1).lower())
    if names:
        return statistics.mode(names)
    return slug(fallback, "state").lower()


def analyze_clip(clip: ClipInfo) -> dict[str, Any]:
    clip.frames = [frame_info(p) for p in clip.files]
    widths = sorted({f.width for f in clip.frames})
    heights = sorted({f.height for f in clip.frames})
    cxs = [f.cx for f in clip.frames]
    feet = [f.feet_y for f in clip.frames]
    lab_l = [f.lab_mean[0] for f in clip.frames]
    edge_touches = {
        k: sum(1 for f in clip.frames if f.edge_touch[k])
        for k in ("left", "right", "top", "bottom")
    }
    start_end = visual_delta(clip.files[0], clip.files[-1]) if len(clip.files) > 1 else None
    return {
        "clip_id": clip.clip_id,
        "role": clip.role,
        "frame_count": len(clip.files),
        "path": str(clip.files[0].parent),
        "first_frame": str(clip.files[0]),
        "last_frame": str(clip.files[-1]),
        "sizes": {"widths": widths, "heights": heights},
        "anchor": {
            "cx_median": round(float(statistics.median(cxs)), 3),
            "feet_y_median": round(float(statistics.median(feet)), 3),
            "cx_span": round(float(max(cxs) - min(cxs)), 3) if cxs else 0.0,
            "feet_y_span": round(float(max(feet) - min(feet)), 3) if feet else 0.0,
        },
        "color": {
            "lab_l_span": round(float(max(lab_l) - min(lab_l)), 3) if lab_l else 0.0,
            "first_lab_mean": clip.frames[0].lab_mean,
            "last_lab_mean": clip.frames[-1].lab_mean,
        },
        "edge_touch_frames": edge_touches,
        "start_end_delta": start_end,
    }


def join_delta(left: ClipInfo, right: ClipInfo) -> dict[str, Any]:
    lf = left.frames[-1]
    rf = right.frames[0]
    return {
        "from": left.clip_id,
        "to": right.clip_id,
        "anchor_delta": {
            "cx": round(float(rf.cx - lf.cx), 3),
            "feet_y": round(float(rf.feet_y - lf.feet_y), 3),
        },
        "visual_delta": visual_delta(left.files[-1], right.files[0]),
        "left_frame": str(left.files[-1]),
        "right_frame": str(right.files[0]),
    }


def severity_for_clip(data: dict[str, Any]) -> tuple[str, list[str]]:
    warnings: list[str] = []
    anchor = data["anchor"]
    if len(data["sizes"]["widths"]) > 1 or len(data["sizes"]["heights"]) > 1:
        warnings.append("mixed frame sizes")
    if anchor["cx_span"] > 8 or anchor["feet_y_span"] > 8:
        warnings.append("anchor jitter")
    if data["color"]["lab_l_span"] > 18:
        warnings.append("large brightness drift")
    if data["edge_touch_frames"]["top"] or data["edge_touch_frames"]["left"] or data["edge_touch_frames"]["right"]:
        warnings.append("foreground touches crop edge")
    if data["role"] in ("loop", "idle", "standby") and data.get("start_end_delta"):
        d = data["start_end_delta"]
        if d["gray_mean_abs"] > 14 or d["gray_p95_abs"] > 42:
            warnings.append("loop seam is visible")
    if not warnings:
        return "ok", []
    if any(x in warnings for x in ("mixed frame sizes", "foreground touches crop edge")):
        return "fail", warnings
    return "warn", warnings


def severity_for_join(data: dict[str, Any]) -> tuple[str, list[str]]:
    warnings: list[str] = []
    ad = data["anchor_delta"]
    vd = data["visual_delta"]
    if abs(ad["cx"]) > 8 or abs(ad["feet_y"]) > 8:
        warnings.append("anchor jump")
    if vd["gray_mean_abs"] > 16 or vd["gray_p95_abs"] > 48:
        warnings.append("visual jump")
    if vd["lab_mean_abs"] > 14:
        warnings.append("color jump")
    if not warnings:
        return "ok", []
    if "anchor jump" in warnings and "visual jump" in warnings:
        return "fail", warnings
    return "warn", warnings


def build_report(root: Path, state_name: str | None = None) -> dict[str, Any]:
    clips = collect_legacy_clips(root)
    source_layout = "legacy_in_loop_out" if clips else "graph_directories"
    if not clips:
        clips = collect_graph_clips(root)
    if not clips:
        frames = sorted(root.glob("*.png"))
        if frames:
            clips = {"flat": ClipInfo(clip_id="flat", role="clip", files=frames, frames=[])}
            source_layout = "flat"
    if not clips:
        raise ValueError(f"no png clips found under {root}")

    state = state_name or infer_state_name(clips, root.name)
    clip_reports = {}
    for cid, clip in clips.items():
        data = analyze_clip(clip)
        status, warnings = severity_for_clip(data)
        data["qa"] = {"status": status, "warnings": warnings}
        clip_reports[cid] = data

    joins: list[dict[str, Any]] = []
    if {"in", "loop"}.issubset(clips):
        joins.append(join_delta(clips["in"], clips["loop"]))
    if {"loop", "out"}.issubset(clips):
        joins.append(join_delta(clips["loop"], clips["out"]))
    for j in joins:
        status, warnings = severity_for_join(j)
        j["qa"] = {"status": status, "warnings": warnings}

    all_status = [c["qa"]["status"] for c in clip_reports.values()] + [j["qa"]["status"] for j in joins]
    summary_status = "fail" if "fail" in all_status else ("warn" if "warn" in all_status else "ok")
    loop_anchor = clip_reports.get("loop", next(iter(clip_reports.values())))["anchor"]
    manifest = {
        "version": 1,
        "character": root.parent.name,
        "state": state,
        "source_layout": source_layout,
        "canvas": [
            clip_reports[next(iter(clip_reports))]["sizes"]["widths"][0],
            clip_reports[next(iter(clip_reports))]["sizes"]["heights"][0],
        ],
        "anchor": {
            "texture_cx": loop_anchor["cx_median"],
            "texture_feet_y": loop_anchor["feet_y_median"],
        },
        "clips": {
            cid: {
                "role": data["role"],
                "path": data["path"],
                "frame_count": data["frame_count"],
                "first_frame": data["first_frame"],
                "last_frame": data["last_frame"],
                "qa_status": data["qa"]["status"],
            }
            for cid, data in clip_reports.items()
        },
        "joins": [
            {
                "from": j["from"],
                "to": j["to"],
                "qa_status": j["qa"]["status"],
                "anchor_delta": j["anchor_delta"],
                "visual_delta": j["visual_delta"],
            }
            for j in joins
        ],
    }
    return {
        "summary": {
            "status": summary_status,
            "root": str(root),
            "state": state,
            "clip_count": len(clip_reports),
            "join_count": len(joins),
        },
        "clips": clip_reports,
        "joins": joins,
        "manifest": manifest,
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = []
    s = report["summary"]
    lines.append(f"# Art Asset QA: {s['state']}")
    lines.append("")
    lines.append(f"- Status: **{s['status']}**")
    lines.append(f"- Root: `{s['root']}`")
    lines.append(f"- Clips: {s['clip_count']}")
    lines.append(f"- Joins: {s['join_count']}")
    lines.append("")
    lines.append("## Clips")
    lines.append("")
    lines.append("| Clip | Role | Frames | Status | Anchor Span | Brightness Span | Warnings |")
    lines.append("| --- | --- | ---: | --- | --- | ---: | --- |")
    for cid, c in report["clips"].items():
        warn = ", ".join(c["qa"]["warnings"]) or "-"
        span = f"cx {c['anchor']['cx_span']}, feet {c['anchor']['feet_y_span']}"
        lines.append(
            f"| `{cid}` | {c['role']} | {c['frame_count']} | {c['qa']['status']} | "
            f"{span} | {c['color']['lab_l_span']} | {warn} |"
        )
    lines.append("")
    lines.append("## Joins")
    lines.append("")
    if report["joins"]:
        lines.append("| From | To | Status | Anchor Delta | Gray Mean | Gray P95 | Warnings |")
        lines.append("| --- | --- | --- | --- | ---: | ---: | --- |")
        for j in report["joins"]:
            warn = ", ".join(j["qa"]["warnings"]) or "-"
            ad = f"cx {j['anchor_delta']['cx']}, feet {j['anchor_delta']['feet_y']}"
            vd = j["visual_delta"]
            lines.append(
                f"| `{j['from']}` | `{j['to']}` | {j['qa']['status']} | {ad} | "
                f"{vd['gray_mean_abs']} | {vd['gray_p95_abs']} | {warn} |"
            )
    else:
        lines.append("No explicit joins detected.")
    lines.append("")
    lines.append("## Suggested Contract")
    lines.append("")
    lines.append("The generated JSON contains a `manifest` object that can later become the runtime contract.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Independent art asset QA and manifest generator.")
    ap.add_argument("--root", default=".", help="Asset root. Supports legacy in/loop/out or graph clip folders.")
    ap.add_argument("--state", default="", help="State name override, for example shy or standby.")
    ap.add_argument("--out-dir", default="asset_platform_out", help="Report output directory.")
    ap.add_argument("--json-name", default="asset_qa_report.json")
    ap.add_argument("--md-name", default="asset_qa_report.md")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    report = build_report(root, state_name=args.state.strip() or None)

    json_path = out_dir / args.json_name
    md_path = out_dir / args.md_name
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(report, md_path)

    print(f"[art-qa] status={report['summary']['status']}")
    print(f"[art-qa] json={json_path}")
    print(f"[art-qa] markdown={md_path}")


if __name__ == "__main__":
    main()
