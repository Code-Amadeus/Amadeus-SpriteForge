"""Durable image and video I/O (requires the qa extra).

Frames are kept in OpenCV's BGRA order end to end. Every file is flushed to disk
before it replaces a previous version, because an interrupted write must never
leave a truncated or zero-filled frame behind a valid name.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np

VIDEO_SUFFIXES = {".mp4", ".mov", ".webm", ".mkv"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
# Generated clips are yuv420p BT.709 limited range; converting explicitly keeps the
# extracted PNGs close to what desktop players show.
DECODE_FILTER = "scale=in_range=tv:out_range=pc:in_color_matrix=bt709:out_color_matrix=bt709"


def write_durable(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def fsync_file(path: Path) -> None:
    with open(path, "rb+") as stream:
        os.fsync(stream.fileno())


def copy_durable(source: Path, target: Path) -> None:
    write_durable(target, source.read_bytes())


def encode_png(image: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise ValueError("PNG encoding failed")
    return encoded.tobytes()


def write_png(path: Path, image: np.ndarray) -> None:
    write_durable(path, encode_png(image))


def image_suffix(data: bytes) -> str:
    """The file suffix of encoded image bytes, from their signature."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    raise ValueError("Expected PNG, JPEG or WebP image data")


def read_bgra(path: Path) -> tuple[np.ndarray, bool]:
    """Return a BGRA image and whether the file carried a meaningful alpha channel."""
    data = np.frombuffer(Path(path).read_bytes(), np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError(f"Cannot decode image: {path}")
    if image.dtype != np.uint8:
        image = (image / 257).astype(np.uint8) if image.dtype == np.uint16 else image.astype(np.uint8)
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.shape[2] == 4:
        return image, bool(image[:, :, 3].min() < 255)
    return cv2.cvtColor(image, cv2.COLOR_BGR2BGRA), False


def sorted_pngs(directory: Path) -> list[Path]:
    return sorted(p for p in Path(directory).glob("*.png") if p.is_file())


def write_sequence(directory: Path, frames: list[np.ndarray]) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    paths = [directory / f"{index:06d}.png" for index in range(len(frames))]
    for path, frame in zip(paths, frames):
        write_png(path, frame)
    return paths


def video_info(path: Path) -> dict:
    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise ValueError(f"Cannot open video: {path}")
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
        info = {"fps": round(fps, 3), "count": int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0),
                "width": int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0), "height": int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)}
    finally:
        capture.release()
    if not 1 <= info["fps"] <= 240 or info["width"] <= 0:
        raise ValueError(f"Video has no usable frame rate or size: {path}")
    return info


def find_ffmpeg(configured: str | None) -> str:
    found = shutil.which(configured or "ffmpeg")
    if not found:
        raise ValueError("ffmpeg not found; install FFmpeg or set 'ffmpeg' in production/tools.json")
    return found


def decode_video(ffmpeg: str, video: Path, directory: Path) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    if sorted_pngs(directory):
        raise ValueError(f"Decode target is not empty: {directory}")
    result = subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-i", str(video),
                             "-vf", DECODE_FILTER, "-fps_mode", "passthrough", "-start_number", "0",
                             str(directory / "%06d.png")], capture_output=True, text=True)
    frames = sorted_pngs(directory)
    if result.returncode or not frames:
        raise ValueError(f"ffmpeg could not decode {video.name}: {result.stderr.strip()[-400:]}")
    for frame in frames:
        fsync_file(frame)
    return frames
