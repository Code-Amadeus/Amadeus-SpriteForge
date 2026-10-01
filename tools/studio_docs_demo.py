"""Build a local documentation demo from the repository's public reference stills.

The short demonstration sequences are blends of those stills, not model output.
No provider, private workspace, matting model or account is used.
"""
import sys
from pathlib import Path

from spriteforge.workspace import atomic_json, read_json
from spriteforge.production import prompts
from spriteforge.production.clips import import_clip_take
from spriteforge.production.geometry import premultiplied_blend
from spriteforge.production.media import read_bgra, write_png
from spriteforge.production.project import add_clip, add_pose, graph_sync, init_production, set_clip
from spriteforge.production.records import decide, still_path
from spriteforge.production.render import render_clip, render_take
from spriteforge.production.stills import approve_still, import_still


def build(target: Path) -> Path:
    if target.exists():
        raise ValueError("Choose a new documentation demo directory")
    workspace = target / "workspace"
    (workspace / "projects").mkdir(parents=True)
    atomic_json(workspace / "graph_config.json", {"nodes": [], "edges": []})
    refs = Path(__file__).resolve().parents[1] / "examples/references/kurisu"
    init_production(workspace, character_id="kurisu-reference", display_name="Kurisu · Reference demo", width=764, height=1028)
    idle = import_still(workspace, "idle", refs / "idle-reference.png", place=(1, 0, 0), note="Bundled public reference")
    approve_still(workspace, "idle", idle["id"])
    add_pose(workspace, "smile", "Gentle closed-eye smile")
    smile = import_still(workspace, "smile", refs / "idle-smile-reference.png", place=(1, 0, 0), note="Bundled public reference")
    approve_still(workspace, "smile", smile["id"])
    for clip, start, end in (("idle_loop", "idle", "idle"), ("smile_in", "idle", "smile"),
                             ("smile_loop", "smile", "smile"), ("smile_out", "smile", "idle")):
        add_clip(workspace, clip, start, end)
        set_clip(workspace, clip, register=False, lock_head=2, lock_tail=2)
    library = prompts.load_library(workspace)
    for block, text in {
        "character": "Use the supplied Kurisu character references. Preserve the character, outfit and art style.",
        "video.invariants": "Keep the camera, framing and character scale fixed.",
        "video.transition": "Move smoothly from the first pose to the last, keeping both endpoints aligned.",
        "video.loop": "Return naturally to the starting pose for a seamless loop.",
        "video.negative": "No camera movement, cropping, framing drift or background changes.",
        "clip.idle_loop": "A quiet neutral idle pose.",
        "clip.smile_in": "Settle gently into the closed-eye smile shown in the final reference.",
        "clip.smile_loop": "Hold the gentle smile with a steady silhouette.",
        "clip.smile_out": "Return gently from the smile to the neutral idle reference.",
    }.items():
        prompts.set_block(library, block, text)
    prompts.save_library(workspace, library)
    for clip, start, end, count in (("idle_loop", "idle", "idle", 8), ("smile_in", "idle", "smile", 12),
                                    ("smile_loop", "smile", "smile", 8), ("smile_out", "smile", "idle", 12)):
        first, last = (read_bgra(still_path(workspace, pose)[0])[0] for pose in (start, end))
        folder = target / "demo-inputs" / clip
        for index in range(count):
            write_png(folder / f"{index:06d}.png", premultiplied_blend(first, last, index / (count - 1)))
        take = import_clip_take(workspace, clip, folder, fps=12, note="Demo sequence from bundled stills")
        decide(workspace, "clip", clip, take["id"], "accept")
        render_clip(workspace, clip, log=lambda *_: None)
    # A second immutable candidate makes the comparison and review controls visible.
    candidate = import_clip_take(workspace, "smile_in", target / "demo-inputs/smile_in", fps=12, note="Compare endpoint alignment")
    render_take(workspace, "smile_in", candidate["id"], log=lambda *_: None)
    graph_sync(workspace, add_missing=True)
    graph = read_json(workspace / "graph_config.json")
    positions = {"idle_loop": (110, 240), "smile_in": (360, 100),
                 "smile_loop": (610, 240), "smile_out": (360, 380)}
    for node in graph["nodes"]:
        node["x"], node["y"] = positions[node["id"]]
    graph["edges"] = [{"id": f"demo-{index}", "from": source, "to": destination, "prob": weight}
                      for index, (source, destination, weight) in enumerate((
                          ("idle_loop", "idle_loop", .88), ("idle_loop", "smile_in", .12),
                          ("smile_in", "smile_loop", 1), ("smile_loop", "smile_loop", .8),
                          ("smile_loop", "smile_out", .2), ("smile_out", "idle_loop", 1)))]
    atomic_json(workspace / "graph_config.json", graph)
    print(workspace)
    return workspace


if __name__ == "__main__":
    build(Path(sys.argv[1]))
