"""SpriteForge interpolate processor backed by GMFSS (requires CUDA and a local GMFSS checkout).

Implements the production ``interpolate`` contract: N opaque PNG frames in INPUT
become N * FACTOR frames in OUTPUT when WRAP is 1 (the last frame interpolates
toward the first, for loops), otherwise (N - 1) * FACTOR + 1 frames. Alpha is
produced afterwards by the alpha processor, as in the Kurisu production route.

  python gmfss_interpolate.py INPUT OUTPUT FACTOR WRAP --gmfss PATH/GMFSS [--device 0]

tools.json:
  "interpolate": {"command": ["PATH/python", "PATH/gmfss_interpolate.py", "{input}", "{output}",
                              "{factor}", "{wrap}", "--gmfss", "PATH/GMFSS"]}

Not exercised by SpriteForge's automated tests: it needs the GMFSS weights and a GPU.
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
    parser.add_argument("factor", type=int)
    parser.add_argument("wrap", choices=["0", "1"])
    parser.add_argument("--gmfss", type=Path, required=True, help="GMFSS checkout containing model/ and weights/")
    parser.add_argument("--device", type=int, default=0)
    args = parser.parse_args()
    if args.factor < 2:
        raise SystemExit("factor must be at least 2")

    import torch
    sys.path.insert(0, str(args.gmfss.resolve()))
    from model.GMFSS import Model

    if not torch.cuda.is_available():
        raise SystemExit("GMFSS interpolation requires CUDA")
    device = torch.device(f"cuda:{args.device}")
    torch.cuda.set_device(args.device)
    torch.set_grad_enabled(False)
    model = Model()
    model.load_model(str(args.gmfss / "weights"), -1)
    model.eval()
    model.device(device)

    def tensor(frame: np.ndarray) -> "torch.Tensor":
        return torch.from_numpy(np.transpose(frame, (2, 0, 1))).to(device).unsqueeze(0).float() / 255.0

    def padded(frame: np.ndarray) -> np.ndarray:
        height, width = frame.shape[:2]
        size = (((width - 1) // 32 + 1) * 32, ((height - 1) // 32 + 1) * 32)
        return frame if size == (width, height) else cv2.resize(frame, size, interpolation=cv2.INTER_LINEAR)

    frames = [cv2.imread(str(p), cv2.IMREAD_COLOR) for p in sorted(args.input.glob("*.png"))]
    if len(frames) < 2 or any(f is None for f in frames):
        raise SystemExit("need at least two readable frames")
    height, width = frames[0].shape[:2]
    steps = [k / args.factor for k in range(1, args.factor)]
    wrap = args.wrap == "1"
    args.output.mkdir(parents=True, exist_ok=True)
    index = 0
    for position, frame in enumerate(frames):
        cv2.imwrite(str(args.output / f"{index:06d}.png"), frame)
        index += 1
        if position + 1 == len(frames) and not wrap:
            break
        following = frames[(position + 1) % len(frames)]
        middles = model.inference(tensor(padded(frame)), tensor(padded(following)), timesteps=steps, scale=1.0,
                                  pred_bidir_flow=False)
        for middle in middles:
            cv2.imwrite(str(args.output / f"{index:06d}.png"),
                        cv2.resize(middle, (width, height), interpolation=cv2.INTER_LINEAR))
            index += 1
    print(f"interpolated {len(frames)} -> {index} frames", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
