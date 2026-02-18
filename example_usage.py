"""
Example: run human parsing and get clothing/identity masks.
Run from project root: python example_usage.py [image_path]
"""

import sys
from pathlib import Path

from src.parser import HumanParser, SEGMENT_LABELS


def main():
    image_path = sys.argv[1] if len(sys.argv) > 1 else "image.jpg"
    path = Path(image_path)
    if not path.exists():
        print(f"Usage: python example_usage.py <image.jpg>")
        print(f"  File not found: {path}")
        sys.exit(1)

    # Prefer production backend; fall back to pipeline if package not installed
    try:
        parser = HumanParser(backend="production")
        print("Using backend: production (fashn-human-parser)")
    except ImportError:
        parser = HumanParser(backend="pipeline")
        print("Using backend: pipeline (transformers)")

    segmentation = parser.predict(path)
    print(f"Segmentation shape: {segmentation.shape}, dtype: {segmentation.dtype}")
    print(f"Unique classes: {sorted(set(segmentation.flat))}")

    # Helper masks for virtual try-on
    clothing = parser.get_clothing_mask(segmentation)
    identity = parser.get_identity_mask(segmentation)
    print(f"Clothing pixels: {clothing.sum()}, Identity pixels: {identity.sum()}")

    # Per-class counts
    for i, name in enumerate(SEGMENT_LABELS):
        count = (segmentation == i).sum()
        if count > 0:
            print(f"  {i:2d} {name}: {count} px")


if __name__ == "__main__":
    main()
