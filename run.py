#!/usr/bin/env python3
"""
CLI for human parsing: segment a fashion image into 18 classes.

Examples:
  python run.py image.jpg
  python run.py image.jpg --out mask.png --backend pipeline
  python run.py image.jpg --out-dir ./output --visualize
"""

import argparse
from pathlib import Path

from src.parser import HumanParser, SEGMENT_LABELS


def main():
    p = argparse.ArgumentParser(description="FASHN Human Parser - segment human/clothing in images")
    p.add_argument("image", type=Path, help="Input image path")
    p.add_argument("--out", "-o", type=Path, default=None, help="Output segmentation mask (single file)")
    p.add_argument("--out-dir", type=Path, default=None, help="Output directory (default: same as input)")
    p.add_argument("--backend", choices=["production", "pipeline"], default="production",
                   help="production = fashn-human-parser (best), pipeline = transformers only")
    p.add_argument("--visualize", "-v", action="store_true", help="Save colored segmentation overlay")
    p.add_argument("--device", choices=["cuda", "cpu"], default=None, help="Device (default: auto)")
    args = p.parse_args()

    if not args.image.exists():
        p.error(f"Image not found: {args.image}")

    out_dir = args.out_dir or args.image.parent
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = args.image.stem
    out_mask = args.out or out_dir / f"{stem}_mask.png"
    out_vis = out_dir / f"{stem}_segmentation.png" if args.visualize else None

    parser = HumanParser(backend=args.backend, device=args.device)
    segmentation = parser.predict(args.image)

    # Save raw mask as PNG (single channel, values 0-17)
    import numpy as np
    from PIL import Image
    mask_u8 = (segmentation.astype(np.uint8) * (255 // 17))  # scale for visibility if opened as image
    Image.fromarray(segmentation.astype(np.uint8)).save(out_mask)
    print(f"Saved mask (H,W) class IDs 0-17: {out_mask}")

    if args.visualize:
        vis_path = save_visualization(segmentation, args.image, out_vis)
        print(f"Saved visualization: {vis_path}")

    return 0


def save_visualization(segmentation, image_path: Path, out_path: Path) -> Path:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from PIL import Image
        import numpy as np
    except ImportError:
        raise SystemExit("Install matplotlib and Pillow for --visualize")

    # Colormap for 18 classes
    try:
        cmap = plt.colormaps["tab20"].resampled(18)
    except AttributeError:
        cmap = plt.cm.get_cmap("tab20", 18)
    seg_rgba = cmap(segmentation % 18)
    seg_rgb = (seg_rgba[..., :3] * 255).astype(np.uint8)

    img = np.array(Image.open(image_path).convert("RGB"))
    if img.shape[:2] != segmentation.shape[:2]:
        from PIL import Image as PImage
        img = np.array(PImage.fromarray(img).resize((segmentation.shape[1], segmentation.shape[0])))
    overlay = (img * 0.5 + seg_rgb * 0.5).astype(np.uint8)

    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    axes[0].imshow(img)
    axes[0].set_title("Input")
    axes[0].axis("off")
    axes[1].imshow(segmentation, cmap=cmap, vmin=0, vmax=17)
    axes[1].set_title("Segmentation")
    axes[1].axis("off")
    axes[2].imshow(overlay)
    axes[2].set_title("Overlay")
    axes[2].axis("off")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    return out_path


if __name__ == "__main__":
    raise SystemExit(main())
