"""Mouth tracks for silence overlays on speaking loops (requires the qa extra).

Amadeus keeps a speaking loop playing and, during silence, paints a closed-mouth
image inside an ellipse at the mouth. It needs, per loop frame, where the mouth is
(``anchor_track``) and how open it is (``openness``), plus the closed-mouth image and
where its mouth is (``runtime_overlay_anchor``). Coordinates are pixels relative to
the canvas centre, y down, as the renderer reads them.

The closed-mouth image defaults to the loop's approved pose still: clip endpoints are
already registered to it, so it is the closed reference by construction. Openness is
the difference of each frame's mouth from that reference, so the most closed frame
is the one closest to it.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .geometry import composite
from .media import read_bgra

# Kurisu's neutral mouth, as fractions of the canvas: centre 29% of the height below
# the head top, 4.5% of the width wide and 1.75% of the height tall.
DEFAULT_SET = {"below": 0.29, "width": 0.045, "height": 0.0175, "curve": 0.2}
SEARCH = 2.5          # detection window around the prior, in mouth sizes
TRACK_STEP = 6.0      # largest per-frame anchor move, px (head motion in loops is small)
TRACK_WATCH = 0.6     # mean template correlation below this needs a look
SPAN_WATCH = 12.0     # anchor movement across the loop, px
# The renderer's default silence mask: half axes of 1.8 x width/2 and (1 + 1.5 x 0.75) x height/2.
MASK = (1.8, 2.125)
# Tone is adjusted with margin for per-label mask overrides in Amadeus (up to about 1.9 x 3.2).
HARMONIZE_REGION = (2.4, 3.4)
TONE_WATCH = 8.0      # a larger L* shift means the closed mouth comes from a very different look


def default_set(anchors: dict, width: int, height: int) -> dict:
    return {"cx": round(anchors["headCenterX"] - width / 2, 2),
            "cy": round(anchors["headTopY"] + DEFAULT_SET["below"] * height - height / 2, 2),
            "width": round(DEFAULT_SET["width"] * width, 2), "height": round(DEFAULT_SET["height"] * height, 2),
            "curve": DEFAULT_SET["curve"]}


def _gray(image: np.ndarray, background: list[int]) -> np.ndarray:
    return cv2.GaussianBlur(cv2.cvtColor(composite(image, background), cv2.COLOR_BGR2GRAY), (3, 3), 0)


def _box(cx: float, cy: float, bw: int, bh: int, width: int, height: int) -> tuple[int, int, int, int]:
    x0 = max(0, min(width - bw, round(cx - bw / 2)))
    y0 = max(0, min(height - bh, round(cy - bh / 2)))
    return x0, y0, x0 + bw, y0 + bh


def detect(frames: list[np.ndarray], guess: dict, width: int, height: int) -> tuple[dict, str]:
    """Mouth centre and size: the largest region that changes over the loop and is centred
    within a mouth's plausible distance of the prior. Moving hair at the sides of the search
    window changes as much as the mouth, so distance decides eligibility, size decides among
    the eligible; gaps up to half a mouth tall are closed so both lips of an open mouth count
    as one region."""
    gx, gy = guess["cx"] + width / 2, guess["cy"] + height / 2
    x0, y0, x1, y1 = _box(gx, gy, round(guess["width"] * SEARCH * 2), round(guess["height"] * SEARCH * 2), width, height)
    reference = frames[0][y0:y1, x0:x1, :3].astype(np.float32)
    change = sum(np.abs(f[y0:y1, x0:x1, :3].astype(np.float32) - reference).max(axis=2) for f in frames[1:])
    if not isinstance(change, np.ndarray) or change.max() <= 1e-6:
        return {k: guess[k] for k in ("cx", "cy", "width", "height")}, "prior"
    binary = ((change / change.max()) > 0.22).astype(np.uint8) * 255
    gap = max(5, round(guess["height"] / 2) | 1)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (gap, gap)))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    regions = []
    for contour in cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]:
        bx, by, bw, bh = cv2.boundingRect(contour)
        cx, cy = x0 + bx + bw / 2 - width / 2, y0 + by + bh / 2 - height / 2
        if cv2.contourArea(contour) >= 12 and abs(cx - guess["cx"]) <= guess["width"] * 1.55 \
                and abs(cy - guess["cy"]) <= guess["height"] * 2.25:
            regions.append((cv2.contourArea(contour), cx, cy, bw, bh))
    if not regions:
        return {k: guess[k] for k in ("cx", "cy", "width", "height")}, "prior"
    _, cx, cy, bw, bh = max(regions)
    size = {"width": min(max(bw, guess["width"]), guess["width"] * 1.75),
            "height": min(max(bh, guess["height"]), guess["height"] * 1.75)}
    return {"cx": round(cx, 2), "cy": round(cy, 2), **{k: round(v, 2) for k, v in size.items()}}, "motion"


def _match(gray: np.ndarray, template: np.ndarray, centre: tuple[float, float], pad: int) -> tuple[float, float, float]:
    th, tw = template.shape
    height, width = gray.shape
    sx0 = max(0, min(width - tw, round(centre[0] - tw / 2 - pad)))
    sy0 = max(0, min(height - th, round(centre[1] - th / 2 - pad)))
    search = gray[sy0:min(height, sy0 + th + 2 * pad), sx0:min(width, sx0 + tw + 2 * pad)]
    if search.shape[0] < th or search.shape[1] < tw:
        return centre[0], centre[1], 0.0
    result = cv2.matchTemplate(search, template, cv2.TM_CCOEFF_NORMED)
    _, score, _, (mx, my) = cv2.minMaxLoc(result)
    return sx0 + mx + tw / 2, sy0 + my + th / 2, float(score)


def _patch(gray: np.ndarray, centre: tuple[float, float], roi: dict) -> np.ndarray:
    height, width = gray.shape
    x0, y0, x1, y1 = _box(centre[0], centre[1], max(8, round(roi["width"] * 1.4)), max(6, round(roi["height"] * 1.6)),
                          width, height)
    return gray[y0:y1, x0:x1].astype(np.float32)


def analyze(frames: list[Path], source: np.ndarray, guess: dict, background: list[int], *,
            source_is_frame: int | None = None) -> dict:
    """Anchor track, openness and the closed source's anchor for one rendered loop."""
    images = [read_bgra(p)[0] for p in frames]
    height, width = images[0].shape[:2]
    step = max(1, len(images) // 72)
    roi, method = detect(images[::step], guess, width, height)
    centre = (roi["cx"] + width / 2, roi["cy"] + height / 2)
    grays = [_gray(image, background) for image in images]
    tw = min(width - 2, max(96, round(roi["width"] * 4.5)))
    th = min(height - 2, max(86, round(roi["height"] * 5.0)))
    x0, y0, x1, y1 = _box(centre[0], centre[1], tw, th, width, height)
    template = grays[0][y0:y1, x0:x1]
    offset = ((x0 + x1) / 2 - centre[0], (y0 + y1) / 2 - centre[1])  # template centre vs mouth centre

    xs, ys, scores = [], [], []
    last = centre
    for gray in grays:
        mx, my, score = _match(gray, template, (last[0] + offset[0], last[1] + offset[1]), 28)
        mx, my = mx - offset[0], my - offset[1]
        if score < 0.35:
            mx, my = last
        last = (last[0] + max(-TRACK_STEP, min(TRACK_STEP, mx - last[0])),
                last[1] + max(-TRACK_STEP, min(TRACK_STEP, my - last[1])))
        xs.append(last[0])
        ys.append(last[1])
        scores.append(score)
    xs, ys = _median(xs), _median(ys)
    track = [{"cx": round(x - width / 2, 2), "cy": round(y - height / 2, 2), "width": roi["width"],
              "height": roi["height"], "score": round(s, 4)} for x, y, s in zip(xs, ys, scores)]

    source_gray = _gray(source, background)
    if source_is_frame is not None:
        sx, sy, source_score = xs[source_is_frame], ys[source_is_frame], 1.0
    else:
        sx, sy, source_score = _match(source_gray, template, (centre[0] + offset[0], centre[1] + offset[1]), 40)
        sx, sy = sx - offset[0], sy - offset[1]
    closed = _patch(source_gray, (sx, sy), roi)
    distances = []
    for gray, x, y in zip(grays, xs, ys):
        patch = _patch(gray, (x, y), roi)
        distances.append(float(np.abs(patch - closed).mean()) if patch.shape == closed.shape else float("inf"))
    finite = [d for d in distances if np.isfinite(d)]
    top = max(finite) if finite else 0.0
    openness = [round(d / top, 4) if top > 1e-6 and np.isfinite(d) else 0.0 for d in distances]
    span = max(max(xs) - min(xs), max(ys) - min(ys))
    anchor = {"cx": round(sx - width / 2, 2), "cy": round(sy - height / 2, 2), "width": roi["width"], "height": roi["height"]}
    qa = {"roiMethod": method, "trackMean": round(float(np.mean(scores)), 4), "trackMin": round(float(min(scores)), 4),
          "span": round(float(span), 2), "sourceScore": round(source_score, 4)}
    checks = []
    if method == "prior":
        checks.append(("roi", "watch", "No speaking motion found near the expected mouth; the mouth set position is used"))
    if qa["trackMean"] < TRACK_WATCH or source_score < 0.5:
        checks.append(("track", "watch", f"Mouth tracking is uncertain (mean correlation {qa['trackMean']}, closed "
                                         f"source {qa['sourceScore']}); check the overlay preview"))
    if span > SPAN_WATCH:
        checks.append(("span", "watch", f"The mouth moves {span:.1f}px across the loop; check the overlay preview"))
    return {"roi": roi, "anchorTrack": track, "openness": openness, "closedFrame": int(np.argmin(openness)),
            "sourceAnchor": anchor, "qa": qa, "checks": checks}


def _median(values: list[float], radius: int = 2) -> list[float]:
    return [float(np.median(values[max(0, i - radius):i + radius + 1])) for i in range(len(values))]


def _ellipse(shape: tuple[int, int], anchor: dict, grow_w: float, grow_h: float) -> np.ndarray:
    height, width = shape
    mask = np.zeros((height, width), np.uint8)
    cv2.ellipse(mask, (round(anchor["cx"] + width / 2), round(anchor["cy"] + height / 2)),
                (max(1, round(anchor["width"] / 2 * grow_w)), max(1, round(anchor["height"] / 2 * grow_h))), 0, 0, 360, 255, -1)
    return mask > 0


def _ring_lab(image: np.ndarray, anchor: dict) -> np.ndarray:
    """Mean Lab of the skin the runtime mask covers around the mouth (the mouth itself excluded)."""
    shape = image.shape[:2]
    ring = _ellipse(shape, anchor, *MASK) & ~_ellipse(shape, anchor, 1.15, 1.4)
    lab = cv2.cvtColor(np.ascontiguousarray(image[:, :, :3]), cv2.COLOR_BGR2LAB).astype(np.float32)
    return lab[ring].mean(axis=0)


def harmonize(source: np.ndarray, frames: list[Path], track: list[dict], anchor: dict) -> tuple[np.ndarray, list[float]]:
    """The closed-mouth image with its mouth area shifted to the loop's skin tone.

    A shared closed mouth comes from another expression (blush, grading); pasted as is,
    the mask shows as a pale or dark oval. One Lab shift, measured on the skin ring the
    mask covers, is applied inside a margin around the mask; the runtime is unchanged."""
    step = max(1, len(frames) // 30)
    target = np.median([_ring_lab(read_bgra(p)[0], a) for p, a in zip(frames[::step], track[::step])], axis=0)
    shift = target - _ring_lab(source, anchor)
    lab = cv2.cvtColor(np.ascontiguousarray(source[:, :, :3]), cv2.COLOR_BGR2LAB).astype(np.float32)
    region = _ellipse(source.shape[:2], anchor, *HARMONIZE_REGION)
    lab[region] = np.clip(lab[region] + shift, 0, 255)
    result = source.copy()
    result[:, :, :3] = cv2.cvtColor(lab.round().astype(np.uint8), cv2.COLOR_LAB2BGR)
    return result, [round(float(v), 2) for v in shift]
