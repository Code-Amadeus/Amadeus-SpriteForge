"""A small legacy SpriteForge workspace and the pack it shipped, for importer tests."""
import json
from pathlib import Path

import numpy as np
from synthetic import CANVAS, figure, save

from spriteforge.character_pack import CHARACTER_PACK_FORMAT

W, H = CANVAS
SUFFIX = "_ktx2_uastc_q4_z18"
SPEAKING = [3, 4, 6, 8, 6, 4]


def pose(mouth: int = 0, drop: int = 0) -> np.ndarray:
    """The synthetic character on the canvas, optionally with an open mouth or lowered by ``drop`` px."""
    image = figure(W, H, mouth=mouth)
    return np.concatenate([np.zeros((drop, W, 4), np.uint8), image[:H - drop]]) if drop else image


def windy(margin: int, index: int) -> np.ndarray:
    """A frame on the canvas widened by the margin, with hair crossing the canvas's right edge."""
    frame = np.pad(pose(), ((0, 0), (margin, margin), (0, 0)))
    frame[60 + index:70 + index, W + margin - 4:W + 2 * margin - 2] = (30, 90, 160, 255)
    return frame


class Legacy:
    def __init__(self, root: Path):
        self.root, self.pack = root / "legacy", root / "pack"
        self.clips, self.overlays, self.profiles, self.nodes, self.edges = {}, {}, {}, [], []

    def clip(self, label: str, frames: list, *, state: str = "idle", interval: int = 17, loop: bool = True,
             node: bool = True, variant: str = "frames_alpha_2x_gmfss") -> list[str]:
        project = f"p_{label}"
        names = [f"{project}{index + 1:04d}" for index in range(len(frames))]
        for name, frame in zip(names, frames):
            save(self.root / "projects" / project / variant / state / "loop" / f"{name}.png", frame)
        (self.root / "projects" / project / (variant + SUFFIX) / state / "loop").mkdir(parents=True, exist_ok=True)
        self.clips[label] = {"phase": "loop", "frameIntervalMs": interval, "loopMode": "loop" if loop else "once_then_hold",
                             "frames": [f"textures/{label}/loop/{name}.ktx2" for name in names]}
        if node:
            self.nodes.append({"id": f"n_{label}", "label": label, "root": f"projects/{project}/{variant}/{state}",
                               "x": 40.0 * len(self.nodes), "y": 20.0, **({} if self.nodes else {"isRoot": True})})
        return names

    def decoys(self, label: str) -> None:
        """Earlier variants of a clip: one never encoded, one whose leftover texture is not the shipped one."""
        project, clip = f"p_{label}", self.clips[label]
        names = [Path(frame).stem for frame in clip["frames"]]
        for variant, encoded in (("frames_alpha", False), ("frames_alpha_2x_lerp", True)):
            for name in names:
                save(self.root / "projects" / project / variant / "idle" / "loop" / f"{name}.png", pose())
            if encoded:
                leftover = self.root / "projects" / project / (variant + SUFFIX) / "idle" / "loop" / f"{names[0]}.ktx2"
                leftover.parent.mkdir(parents=True, exist_ok=True)
                leftover.write_bytes(b"an earlier encoding")

    def mouth(self, label: str, mouth_set: str, overlay: str) -> None:
        self.profiles[label] = {"mouth_set": mouth_set, "cx": 0.0, "cy": -88.0, "width": 18.0, "height": 6.0}
        self.overlays[label] = [overlay]

    def write(self) -> "Legacy":
        ids = {node["label"]: node["id"] for node in self.nodes}
        edges = [{"id": f"e{index}", "from": ids[a], "to": ids[b], "prob": 1} for index, (a, b) in enumerate(self.edges)]
        write(self.root / "graph_config.json", {"nodes": self.nodes, "edges": edges})
        write(self.pack / "graph_config.json", {"nodes": [{k: v for k, v in node.items() if k in ("id", "label", "isRoot")}
                                                          for node in self.nodes], "edges": edges})
        shape = {"cx": 0.0, "cy": -88.0, "width": 18.0, "height": 6.0}
        write(self.pack / "spriteforge_mouth_config.json", {
            "version": 2, "canvas_size": [W, H], "profile_kind": "runtime_ktx2", "profiles": self.profiles,
            "expressions": {"neutral": {**shape, "curve": 0.2}, "smile": {**shape, "curve": 0.4}}})
        write(self.pack / "runtime_manifest.json", {
            "format": CHARACTER_PACK_FORMAT, "id": "demo", "displayName": "Demo", "version": "1", "textureFormat": "ktx2",
            "graph": "graph_config.json", "mouthConfig": "spriteforge_mouth_config.json", "quality": 4, "zcmp": 18,
            "clips": self.clips, "mouthOverlays": self.overlays})
        for clip in self.clips.values():
            for frame in clip["frames"]:
                (self.pack / frame).parent.mkdir(parents=True, exist_ok=True)
                (self.pack / frame).write_bytes(b"\xabKTX 20\xbb\r\n\x1a\n" + frame.encode())
        return self


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def build_legacy(root: Path) -> Legacy:
    """idle (base) with wide and short loops; a smile expression; a lowered 'lean' pose whose
    speaking loop jumps back to idle; and a post-speech smile loop outside the graph."""
    legacy = Legacy(root)
    legacy.clip("idle", [pose() for _ in range(6)], interval=21)
    legacy.decoys("idle")
    legacy.clip("idle_wide", [windy(10, i) for i in range(6)], interval=21)
    legacy.clip("idle_short", [pose()[2:] for _ in range(6)], interval=21)
    trans = legacy.clip("smile_trans", [pose(mouth=round(3 * i / 7)) for i in range(8)], interval=8, loop=False)
    legacy.clip("smile_talk", [pose(mouth=SPEAKING[i % 6]) for i in range(12)], state="speaking")
    legacy.mouth("smile_talk", "smile", f"textures/smile_trans/loop/{trans[0]}.ktx2")
    legacy.clip("lean_trans", [pose(drop=round(5 * i / 7)) for i in range(8)], interval=8, loop=False)
    talk = legacy.clip("lean_talk", [pose(mouth=SPEAKING[i % 6] - 3, drop=5) for i in range(12)], state="speaking")
    legacy.mouth("lean_talk", "neutral", f"textures/lean_talk/loop/{talk[6]}.ktx2")
    legacy.clip("smile", [pose(mouth=3) for _ in range(6)], node=False)
    legacy.edges = [("idle", "idle"), ("idle", "idle_wide"), ("idle_wide", "idle"), ("idle", "idle_short"),
                    ("idle_short", "idle"), ("idle", "smile_trans"), ("smile_trans", "smile_talk"),
                    ("smile_talk", "smile_talk"), ("idle", "lean_trans"), ("lean_trans", "lean_talk"),
                    ("lean_talk", "idle")]
    return legacy.write()
