"""Test interpolation processor: linear in-betweens, following the documented frame-count contract."""
import sys
from pathlib import Path

import cv2
import numpy as np

source, target, factor, wrap = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3]), sys.argv[4] == "1"
target.mkdir(parents=True, exist_ok=True)
frames = [cv2.imread(str(p), cv2.IMREAD_UNCHANGED).astype(np.float32) for p in sorted(source.glob("*.png"))]
out = []
for index, frame in enumerate(frames):
    out.append(frame)
    if index + 1 == len(frames) and not wrap:
        break
    following = frames[(index + 1) % len(frames)]
    out.extend(frame * (1 - k / factor) + following * (k / factor) for k in range(1, factor))
for index, frame in enumerate(out):
    cv2.imwrite(str(target / f"{index:06d}.png"), frame.round().clip(0, 255).astype(np.uint8))
