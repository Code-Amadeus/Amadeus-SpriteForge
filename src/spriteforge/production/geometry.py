"""Canvas-contract measurements and similarity registration (requires the qa extra).

Portraits are usually cut by the canvas bottom, so a feet anchor does not exist.
The stable anchors are the head top and the head centre, measured on the alpha
mask. Face lightness is sampled in the lower face (cheeks, nose and mouth), a
region that follows the head anchor; this reproduces the documented Kurisu seam
baseline (for example idle -> speaking_trans at about 1.5 L*).
"""
from __future__ import annotations

import math

import cv2
import numpy as np

VISIBLE_ALPHA = 128
HEAD_BAND = 0.04                 # rows below the head top used for the head centre, as a canvas fraction
FACE_ROI = (0.05, 0.24, 0.30)    # half width, top and bottom offsets below the head top, as canvas fractions
MIN_INLIERS = 20
# A registration is rigid when most matches agree on one similarity transform: the
# picture was moved as a whole. On Kurisu, an expression edit keeps 93% of the matches;
# lean, thinking and side poses keep 3-20%, where a whole-image transform is wrong.
RIGID_INLIER_RATIO = 0.5


def visible(image: np.ndarray) -> np.ndarray:
    return image[:, :, 3] > VISIBLE_ALPHA


def measure(image: np.ndarray) -> dict:
    mask = visible(image)
    ys, xs = np.nonzero(mask)
    if not len(xs):
        raise ValueError("Image has no visible foreground")
    height, width = mask.shape
    top = int(ys.min())
    band = mask[top:top + max(4, round(HEAD_BAND * height))]
    edges = [name for name, line in (("left", mask[:, 0]), ("right", mask[:, -1]), ("top", mask[0]), ("bottom", mask[-1]))
             if line.any()]
    return {"headTopY": top, "headCenterX": round(float(np.nonzero(band)[1].mean()), 2),
            "bbox": [int(xs.min()), top, int(xs.max()), int(ys.max())], "area": int(mask.sum()),
            "edges": edges, "size": [width, height]}


def face_roi(anchor: dict, width: int, height: int) -> tuple[int, int, int, int]:
    half, top, bottom = FACE_ROI
    cx, head = anchor["headCenterX"], anchor["headTopY"]
    x0, x1 = max(0, round(cx - half * width)), min(width, round(cx + half * width))
    y0, y1 = max(0, round(head + top * height)), min(height, round(head + bottom * height))
    return x0, y0, x1, y1


def face_lightness(image: np.ndarray, roi: tuple[int, int, int, int]) -> float | None:
    x0, y0, x1, y1 = roi
    region = image[y0:y1, x0:x1]
    mask = visible(region) if region.size else None
    if mask is None or mask.sum() < 16:
        return None
    lightness = cv2.cvtColor(np.ascontiguousarray(region[:, :, :3]), cv2.COLOR_BGR2LAB)[:, :, 0]
    return round(float(lightness[mask].mean()) * 100 / 255, 3)


def composite(image: np.ndarray, background: list[int] | tuple[int, ...]) -> np.ndarray:
    alpha = image[:, :, 3:4].astype(np.float32) / 255
    bg = np.array(background[::-1], np.float32)  # stored as RGB, frames are BGR
    return (image[:, :, :3].astype(np.float32) * alpha + bg * (1 - alpha)).round().clip(0, 255).astype(np.uint8)


def estimate_similarity(source: np.ndarray, target: np.ndarray) -> tuple[np.ndarray, dict]:
    """Similarity transform mapping source pixels onto target pixels (both BGR)."""
    orb = cv2.ORB_create(nfeatures=5000)
    kp1, des1 = orb.detectAndCompute(cv2.cvtColor(source, cv2.COLOR_BGR2GRAY), None)
    kp2, des2 = orb.detectAndCompute(cv2.cvtColor(target, cv2.COLOR_BGR2GRAY), None)
    if des1 is None or des2 is None:
        raise ValueError("Registration found no image features")
    matches = sorted(cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(des1, des2), key=lambda m: m.distance)[:1200]
    if len(matches) < MIN_INLIERS:
        raise ValueError(f"Registration found only {len(matches)} feature matches")
    src = np.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    dst = np.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
    matrix, inliers = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=3.0,
                                                  maxIters=5000, confidence=0.995)
    count = int(inliers.sum()) if inliers is not None else 0
    if matrix is None or count < MIN_INLIERS:
        raise ValueError(f"Registration is not reliable ({count} inliers)")
    return matrix.astype(np.float64), describe(matrix, inliers=count, matches=len(matches))


def describe(matrix: np.ndarray, **extra: int) -> dict:
    scale = math.hypot(matrix[0, 0], matrix[1, 0])
    return {"scale": round(scale, 5), "rotationDeg": round(math.degrees(math.atan2(matrix[1, 0], matrix[0, 0])), 4),
            "tx": round(float(matrix[0, 2]), 3), "ty": round(float(matrix[1, 2]), 3), **extra}


def placement(scale: float, dx: float, dy: float) -> np.ndarray:
    if not (math.isfinite(scale) and scale > 0 and math.isfinite(dx) and math.isfinite(dy)):
        raise ValueError("Placement needs a positive scale and finite offsets")
    return np.array([[scale, 0, dx], [0, scale, dy]], np.float64)


def is_rigid(registration: dict) -> bool:
    return registration["inliers"] >= RIGID_INLIER_RATIO * registration["matches"]


def fit_placement(image: np.ndarray, width: int, height: int) -> np.ndarray:
    """Keep the generator's framing: scale uniformly into the canvas and centre."""
    scale = min(width / image.shape[1], height / image.shape[0])
    return placement(scale, (width - scale * image.shape[1]) / 2, (height - scale * image.shape[0]) / 2)


def framing_placement(image: np.ndarray, width: int, height: int, framing: dict) -> np.ndarray:
    """Default base placement: centred, visible width and head top as in the reference framing."""
    x0, top, x1, _ = measure(image)["bbox"]
    scale = framing["visibleWidth"] * width / max(1, x1 - x0 + 1)
    return placement(scale, width / 2 - scale * (x0 + x1 + 1) / 2, framing["headTop"] * height - scale * top)


def warp(image: np.ndarray, matrix: np.ndarray, width: int, height: int, border: tuple[int, ...]) -> np.ndarray:
    return cv2.warpAffine(image, matrix, (width, height), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=border)


def premultiplied_blend(frame: np.ndarray, target: np.ndarray, weight: float) -> np.ndarray:
    """Blend toward target by weight in premultiplied alpha, so transparent pixels carry no colour."""
    a = frame[:, :, 3:4].astype(np.float32) / 255
    b = target[:, :, 3:4].astype(np.float32) / 255
    alpha = a * (1 - weight) + b * weight
    colour = frame[:, :, :3].astype(np.float32) * a * (1 - weight) + target[:, :, :3].astype(np.float32) * b * weight
    out = np.zeros_like(frame)
    out[:, :, :3] = np.where(alpha > 1e-6, colour / np.maximum(alpha, 1e-6), 0).round().clip(0, 255)
    out[:, :, 3:4] = (alpha * 255).round().clip(0, 255)
    return out


def smoothstep(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)
