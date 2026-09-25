"""Create a synthetic production workspace for browser checks: python tests/production_demo.py TARGET"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from synthetic import build_studio, clip_with_take, frame_folder, provider_frames, still, talking_clip, write_video  # noqa: E402

from spriteforge.production.clips import import_clip_take  # noqa: E402
from spriteforge.production.project import graph_sync  # noqa: E402
from spriteforge.production.records import decide  # noqa: E402
from spriteforge.production.render import render_clip  # noqa: E402


def main(target: Path) -> None:
    if target.exists():
        raise SystemExit(f"{target} already exists")
    studio = build_studio(target)
    clip_with_take(studio, "idle_loop", "idle", "idle", 16, pingpong=True)
    clip_with_take(studio, "smile_in", "idle", "smile", 24, interpolate=2, speed=2.0)
    video = write_video(studio.tmp / "alternative.mp4", provider_frames(still(studio, "idle"), still(studio, "smile"), 24))
    import_clip_take(studio.root, "smile_in", video, note="second attempt")
    rejected = import_clip_take(studio.root, "smile_in", frame_folder(studio, "first", "idle", "smile", 20), fps=30)
    decide(studio.root, "clip", "smile_in", rejected["id"], "reject", "hair jitters")
    talking_clip(studio)
    for clip_id in ("idle_loop", "smile_in", "smile_talk"):
        render_clip(studio.root, clip_id, log=lambda *_: None)
    graph_sync(studio.root, add_missing=True)
    print(studio.root)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
