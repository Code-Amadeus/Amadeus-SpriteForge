"""Synthetic inputs for browser-only concept/provider acceptance; no remote calls."""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from synthetic import build_studio, figure, flatten, save, still  # noqa: E402
from spriteforge.production import prompts  # noqa: E402
from spriteforge.production.project import add_pose  # noqa: E402


def main(target: Path) -> None:
    if target.exists():
        raise SystemExit(f"{target} already exists")
    studio = build_studio(target)
    for pose in ("angry", "blink", "calm", "sad", "shy", "surprise"):
        add_pose(studio.root, pose, f"Synthetic {pose} expression")
    library = prompts.load_library(studio.root)
    for block in library["blocks"]:
        prompts.set_block(library, block, f"Synthetic instruction for {block}")
    prompts.save_library(studio.root, library)
    # Deliberately smaller than requested: the actual provider image is split,
    # retained and usable without pretending the requested dimensions were met.
    cells = [cv2.resize(flatten(figure(240, 320, mouth=i, seed=7 + i)), (128, 128)) for i in range(6)]
    for cell in cells:
        cv2.rectangle(cell, (0, 0), (127, 127), (70, 130, 90), 1)
    grid = np.vstack([np.hstack(cells[:3]), np.hstack(cells[3:])])
    save(target / "concept-grid.png", cv2.copyMakeBorder(grid, 8, 8, 8, 8, cv2.BORDER_CONSTANT, value=(255, 255, 255)))
    save(target / "reroll.png", flatten(figure(176, 224, mouth=4, seed=22)))
    save(target / "final.png", flatten(still(studio, "idle")))
    print(studio.root)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
