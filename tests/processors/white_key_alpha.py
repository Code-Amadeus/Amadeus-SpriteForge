"""Test alpha processor: pixels that differ from the white background are opaque."""
import sys
from pathlib import Path

import cv2
import numpy as np

source, target = Path(sys.argv[1]), Path(sys.argv[2])
target.mkdir(parents=True, exist_ok=True)
for path in sorted(source.glob("*.png")):
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    alpha = np.where(np.abs(image.astype(np.int16) - 255).max(axis=2) > 12, 255, 0).astype(np.uint8)
    cv2.imwrite(str(target / path.name), np.dstack([image, alpha]))
