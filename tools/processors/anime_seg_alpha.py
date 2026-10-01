"""SpriteForge alpha processor backed by anime-segmentation (isnet_is).

Implements the production ``alpha`` contract: every PNG in INPUT (an opaque frame
on the character background) becomes an RGBA PNG with the same name in OUTPUT.
The model is loaded from a local checkout; no weights ship with SpriteForge.

  python anime_seg_alpha.py INPUT OUTPUT --repo PATH/anime-segmentation \
      --checkpoint PATH/isnetis.ckpt [--size 1024] [--device auto|cpu|cuda]

tools.json:
  "alpha": {"command": ["PATH/python", "PATH/anime_seg_alpha.py", "{input}", "{output}",
                        "--repo", "PATH/anime-segmentation", "--checkpoint", "PATH/isnetis.ckpt"]}
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--repo", type=Path, required=True, help="anime-segmentation checkout (provides train.py)")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--size", type=int, default=1024)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    args = parser.parse_args()

    import torch
    sys.path.insert(0, str(args.repo.resolve()))
    from train import AnimeSegmentation

    device = ("cuda" if torch.cuda.is_available() else "cpu") if args.device == "auto" else args.device
    model = AnimeSegmentation.try_load("isnet_is", str(args.checkpoint), device)
    model.eval().to(device)
    args.output.mkdir(parents=True, exist_ok=True)
    frames = sorted(args.input.glob("*.png"))
    for index, path in enumerate(frames, 1):
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            raise SystemExit(f"cannot read {path}")
        height, width = image.shape[:2]
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        tensor = torch.from_numpy(cv2.resize(rgb, (args.size, args.size))).float().permute(2, 0, 1).unsqueeze(0) / 255.0
        with torch.no_grad():
            mask = model(tensor.to(device))[0].squeeze().cpu().numpy()
        alpha = (cv2.resize(mask, (width, height)) * 255).clip(0, 255).astype(np.uint8)
        if not cv2.imwrite(str(args.output / path.name), np.dstack([image, alpha])):
            raise SystemExit(f"cannot write {path.name}")
        if index % 20 == 0 or index == len(frames):
            print(f"alpha {index}/{len(frames)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
