"""Explicit PNG -> KTX2 export, with no character-specific frame substitutions."""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path

from .character_pack import CHARACTER_PACK_FORMAT, load_character_pack
from .graph import runtime_graph, validate_graph
from .workspace import atomic_json, clip_frames, read_json, resolve_asset


def export_pack(workspace: Path, output: Path, *, pack_id: str, display_name: str,
                version: str, toktx: str = "toktx", no_mouth: bool = False) -> dict:
    workspace, output = workspace.resolve(), output.resolve()
    if output.exists():
        raise ValueError("Export destination already exists; choose a new directory")
    if not all(isinstance(v, str) and v.strip() for v in (pack_id, display_name, version)):
        raise ValueError("Pack id, display name and version are required")
    graph = validate_graph(workspace, read_json(resolve_asset(workspace, "graph_config.json")))
    # The legacy mask model is not silently translated or discarded.
    mouth_path = resolve_asset(workspace, "spriteforge_mouth_config.json")
    if mouth_path.exists() and not no_mouth:
        mouth = read_json(mouth_path)
        if not isinstance(mouth, dict) or mouth.get("expressions") or mouth.get("profiles"):
            raise ValueError("This exporter supports clips without mouth overlays. Use --no-mouth explicitly to export body clips only")
    encoder = shutil.which(toktx)
    if not encoder:
        raise ValueError("toktx not found; install KTX-Software and pass --toktx PATH")
    # Resolve the complete selected frame list before starting any encoding.
    selected = {}
    for node in graph["nodes"]:
        selected.setdefault(node["label"], (node, clip_frames(workspace, node)))
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        clips = {}
        for label, (node, frames) in selected.items():
            # Labels remain untouched; safe folder names do not become new identity.
            folder = hashlib.sha256(label.encode()).hexdigest()[:16]
            encoded = []
            for index, source in enumerate(frames):
                relative = Path("textures") / folder / f"{index:06d}.ktx2"
                target = staging / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                result = subprocess.run([encoder, "--t2", "--encode", "uastc", "--uastc_quality", "2",
                                         "--zcmp", "18", "--target_type", "RGBA", str(target), str(source)],
                                        capture_output=True, text=True)
                if result.returncode:
                    raise ValueError(f"KTX encoding failed for {source.name}: {result.stderr.strip()}")
                if not target.is_file() or target.read_bytes()[:12] != b"\xabKTX 20\xbb\r\n\x1a\n":
                    raise ValueError(f"Encoder did not produce a KTX2 frame for {source.name}")
                encoded.append(relative.as_posix())
            clips[label] = {"phase": node["phase"], "frameIntervalMs": node["frameIntervalMs"],
                            "loopMode": node["loopMode"], "frames": encoded}
        textures = list(staging.rglob("*.ktx2"))
        manifest = {"format": CHARACTER_PACK_FORMAT, "id": pack_id, "displayName": display_name,
                    "version": version, "textureFormat": "ktx2", "graph": "graph_config.json",
                    "mouthConfig": "spriteforge_mouth_config.json", "clips": clips, "mouthOverlays": {},
                    "clipCount": len(clips), "frameCount": sum(len(c["frames"]) for c in clips.values()),
                    "textureCount": len(textures), "textureBytes": sum(p.stat().st_size for p in textures)}
        atomic_json(staging / "runtime_manifest.json", manifest)
        atomic_json(staging / "graph_config.json", runtime_graph(graph))
        atomic_json(staging / "spriteforge_mouth_config.json", {"expressions": {}, "profiles": {}})
        load_character_pack(staging)
        # Destination is immutable; rename only after cross-file validation succeeds.
        if output.exists():
            raise ValueError("Export destination was created during encoding")
        staging.rename(output)
        return manifest
    finally:
        if staging.exists():
            shutil.rmtree(staging)
