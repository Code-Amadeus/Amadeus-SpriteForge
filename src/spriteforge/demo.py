"""Original geometric test artwork; no character or third-party media."""
from __future__ import annotations
import struct
import zlib
from pathlib import Path
from .workspace import atomic_json


def png(path: Path, variant: int) -> None:
    width = height = 64
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            inside = 12 <= x < 52 and 10 <= y < 55
            eye = y in (24, 25) and (x in (23, 24, 39, 40))
            mouth = 28 <= x < 36 and 37 <= y < 39 + variant
            color = (24, 40, 55, 255) if eye or mouth else (70, 190 + variant * 12, 165, 255) if inside else (0, 0, 0, 0)
            row.extend(color)
        rows.append(bytes(row))
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    data = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
    data += chunk(b'IDAT', zlib.compress(b''.join(rows))) + chunk(b'IEND', b'')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def create_demo(workspace: Path) -> None:
    if workspace.exists():
        raise ValueError("Workspace already exists; choose a new directory")
    workspace.mkdir(parents=True)
    nodes = []
    for index, label in enumerate(("idle", "idle_variant", "speaking_short")):
        root = f"projects/demo/frames/{label}/loop"
        for frame in range(3):
            png(workspace / root / f"{frame:04d}.png", (index + frame) % 3)
        nodes.append({"id": label, "label": label, "root": root, "phase": "flat",
                      "frameIntervalMs": 160, "loopMode": "loop", "isRoot": index == 0,
                      "x": 90 + index * 155, "y": 100 + (index % 2) * 100})
    atomic_json(workspace / "graph_config.json", {"nodes": nodes, "edges": [
        {"id": "idle_self", "from": "idle", "to": "idle", "prob": 4},
        {"id": "idle_variant", "from": "idle", "to": "idle_variant", "prob": 1},
        {"id": "variant_idle", "from": "idle_variant", "to": "idle", "prob": 1},
        {"id": "speak", "from": "idle", "to": "speaking_short", "prob": 0},
        {"id": "speak_idle", "from": "speaking_short", "to": "idle", "prob": 1},
    ]})
    atomic_json(workspace / "spriteforge_mouth_config.json", {"expressions": {}, "profiles": {}})
