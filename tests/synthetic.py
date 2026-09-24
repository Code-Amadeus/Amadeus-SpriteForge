"""Deterministic synthetic character media for production tests (no third-party artwork)."""
import sys
from pathlib import Path

import cv2
import numpy as np

from spriteforge.production.project import init_production
from spriteforge.production.tools import load_tools, save_tools

PROCESSORS = Path(__file__).parent / "processors"
CANVAS = (240, 320)


def figure(width: int, height: int, *, mouth: int = 0, seed: int = 7) -> np.ndarray:
    """A textured half-body figure cut by the bottom edge, on a transparent background (BGRA)."""
    rng = np.random.default_rng(seed)
    blocks = rng.integers(40, 200, size=(height // 8 + 1, width // 8 + 1, 3), dtype=np.uint8)
    texture = cv2.resize(blocks, (width, height), interpolation=cv2.INTER_NEAREST)
    mask = np.zeros((height, width), np.uint8)
    cx, radius = width // 2, int(0.14 * width)
    head_y = int(0.06 * height) + radius
    cv2.circle(mask, (cx, head_y), radius, 255, -1)
    shoulders = head_y + radius - 4
    cv2.fillPoly(mask, [np.array([[cx - int(0.18 * width), shoulders], [cx + int(0.18 * width), shoulders],
                                  [cx + int(0.34 * width), height], [cx - int(0.34 * width), height]])], 255)
    image = np.dstack([texture, mask])
    if mouth:
        top = head_y + radius // 2
        cv2.rectangle(image, (cx - 9, top), (cx + 9, top + 3 + mouth), (40, 40, 150, 255), -1)
    image[mask == 0] = 0
    return image


def save(path: Path, image: np.ndarray) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), image)
    return path


def flatten(image: np.ndarray) -> np.ndarray:
    alpha = image[:, :, 3:4].astype(np.float32) / 255
    return (image[:, :, :3] * alpha + 255 * (1 - alpha)).round().astype(np.uint8)


def provider_frames(start: np.ndarray, end: np.ndarray, count: int, *, size=(256, 344), scale=1.06,
                    offset=(9.0, -5.0)) -> list[np.ndarray]:
    """What an image-to-video model returns: its own resolution and framing, cross-fading start to end."""
    matrix = np.array([[scale, 0, offset[0]], [0, scale, offset[1]]], np.float32)
    frames = []
    for index in range(count):
        t = index / (count - 1)
        mixed = (flatten(start).astype(np.float32) * (1 - t) + flatten(end).astype(np.float32) * t).round().astype(np.uint8)
        frames.append(cv2.warpAffine(mixed, matrix, size, flags=cv2.INTER_CUBIC, borderValue=(255, 255, 255)))
    return frames


def write_video(path: Path, frames: list[np.ndarray], fps: float = 30) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, frames[0].shape[1::-1])
    for frame in frames:
        writer.write(frame)
    writer.release()
    return path


def production_workspace(root: Path) -> Path:
    (root / "projects").mkdir(parents=True)
    (root / "graph_config.json").write_text('{"nodes": [], "edges": []}\n', encoding="utf-8")
    init_production(root, character_id="demo", display_name="Demo", width=CANVAS[0], height=CANVAS[1])
    tools = load_tools(root)
    tools["alpha"] = {"command": [sys.executable, str(PROCESSORS / "white_key_alpha.py"), "{input}", "{output}"]}
    tools["interpolate"] = {"command": [sys.executable, str(PROCESSORS / "lerp_interpolate.py"),
                                       "{input}", "{output}", "{factor}", "{wrap}"]}
    save_tools(root, tools)
    return root
