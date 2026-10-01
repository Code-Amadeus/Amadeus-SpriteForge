"""Explicit PNG -> KTX2 export, with no character-specific frame substitutions."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from .character_pack import CHARACTER_PACK_FORMAT, load_character_pack
from .graph import layout_coordinates, runtime_graph, validate_graph
from .production.records import bound_clip, production_dir
from .workspace import atomic_json, clip_frames, read_json, resolve_asset


def export_pack(workspace: Path, output: Path, *, pack_id: str, display_name: str,
                version: str, toktx: str = "toktx", no_mouth: bool = False) -> dict:
    workspace, output = workspace.resolve(), output.resolve()
    if output.exists():
        raise ValueError("Export destination already exists; choose a new directory")
    if not all(isinstance(v, str) and v.strip() for v in (pack_id, display_name, version)):
        raise ValueError("Pack id, display name and version are required")
    graph = validate_graph(workspace, read_json(resolve_asset(workspace, "graph_config.json")))
    speaking = {"expressions": {}, "profiles": {}, "overlays": {}}
    nodes = graph["nodes"]
    if (production_dir(workspace) / "character.json").is_file():
        from .production.project import export_gate, export_mouth, export_nodes
        nodes = export_nodes(workspace, graph)
    if any(bound_clip(node["root"]) for node in nodes):
        scope = {"nodes": nodes, "edges": graph["edges"]}
        export_gate(workspace, scope)
        if not no_mouth:
            speaking = export_mouth(workspace, scope)
    layout = None
    if all("x" in node and "y" in node for node in graph["nodes"]):
        coordinates = layout_coordinates(graph, graph)
        layout = {"nodes": [{"id": n["id"], "label": n["label"], **coordinates[n["id"]]} for n in graph["nodes"]]}
    layout_path = output.with_name(output.name + ".graph-layout.json")
    if layout_path.exists():
        raise ValueError("Export layout companion already exists; choose a new destination")
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
    for node in nodes:
        selected.setdefault(node["label"], (node, clip_frames(workspace, node)))
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    created_layout = False
    published = False

    def encode(source: Path, relative: Path) -> str:
        target = staging / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        # The shipped packs' settings: KTX-Software 4.4.2 reproduces their textures byte for byte.
        result = subprocess.run([encoder, "--t2", "--encode", "uastc", "--uastc_quality", "4",
                                 "--zcmp", "18", "--target_type", "RGBA", str(target), str(source)],
                                capture_output=True, text=True)
        if result.returncode:
            raise ValueError(f"KTX encoding failed for {source.name}: {result.stderr.strip()}")
        if not target.is_file() or target.read_bytes()[:12] != b"\xabKTX 20\xbb\r\n\x1a\n":
            raise ValueError(f"Encoder did not produce a KTX2 frame for {source.name}")
        return relative.as_posix()

    try:
        clips = {}
        for label, (node, frames) in selected.items():
            # Labels remain untouched; safe folder names do not become new identity.
            folder = hashlib.sha256(label.encode()).hexdigest()[:16]
            encoded = [encode(source, Path("textures") / folder / f"{index:06d}.ktx2") for index, source in enumerate(frames)]
            clips[label] = {"phase": node["phase"], "frameIntervalMs": node["frameIntervalMs"],
                            "loopMode": node["loopMode"], "frames": encoded}
        overlays = {label: [encode(source, Path("textures") / "mouth" / hashlib.sha256(label.encode()).hexdigest()[:16]
                                   / "000000.ktx2")] for label, source in speaking["overlays"].items()}
        textures = list(staging.rglob("*.ktx2"))
        manifest = {"format": CHARACTER_PACK_FORMAT, "id": pack_id, "displayName": display_name,
                    "version": version, "textureFormat": "ktx2", "graph": "graph_config.json",
                    "mouthConfig": "spriteforge_mouth_config.json", "clips": clips, "mouthOverlays": overlays,
                    "clipCount": len(clips), "frameCount": sum(len(c["frames"]) for c in clips.values()),
                    "textureCount": len(textures), "textureBytes": sum(p.stat().st_size for p in textures)}
        atomic_json(staging / "runtime_manifest.json", manifest)
        atomic_json(staging / "graph_config.json", runtime_graph(graph))
        atomic_json(staging / "spriteforge_mouth_config.json",
                    {**speaking.get("header", {}), "expressions": speaking["expressions"], "profiles": speaking["profiles"]})
        load_character_pack(staging)
        # Destination is immutable; rename only after cross-file validation succeeds.
        if output.exists():
            raise ValueError("Export destination was created during encoding")
        if layout is not None:
            with layout_path.open("x", encoding="utf-8", newline="\n") as stream:
                created_layout = True
                stream.write(json.dumps(layout, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        staging.rename(output)
        published = True
        return manifest
    finally:
        if created_layout and not published:
            layout_path.unlink()
        if staging.exists():
            shutil.rmtree(staging)
