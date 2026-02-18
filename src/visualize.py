"""Segmentation visualization (no matplotlib)."""

import io
import numpy as np
from PIL import Image


# 18 distinct colors for classes 0-17 (tab20-like)
PALETTE = np.array([
    [0, 0, 0],       # 0 background
    [255, 187, 120], # 1 face
    [102, 102, 102], # 2 hair
    [230, 25, 75],   # 3 top
    [245, 130, 49],  # 4 dress
    [255, 225, 25],  # 5 skirt
    [60, 180, 75],   # 6 pants
    [70, 240, 240],  # 7 belt
    [240, 50, 230],  # 8 bag
    [128, 0, 0],     # 9 hat
    [170, 255, 195], # 10 scarf
    [0, 128, 128],   # 11 glasses
    [128, 128, 0],   # 12 arms
    [255, 250, 200], # 13 hands
    [0, 0, 128],    # 14 legs
    [128, 128, 128], # 15 feet
    [250, 190, 190], # 16 torso
    [255, 215, 0],   # 17 jewelry
], dtype=np.uint8)


def segmentation_to_rgb(segmentation: np.ndarray) -> np.ndarray:
    """(H, W) class IDs -> (H, W, 3) RGB."""
    h, w = segmentation.shape
    idx = np.clip(segmentation.ravel(), 0, len(PALETTE) - 1)
    rgb = PALETTE[idx].reshape(h, w, 3)
    return rgb


def overlay_image(
    segmentation: np.ndarray,
    image_rgb: np.ndarray,
    alpha: float = 0.5,
    seg_rgb_override: np.ndarray | None = None,
) -> np.ndarray:
    """Blend segmentation colors over image. image_rgb (H,W,3). Returns (H,W,3) uint8."""
    seg_rgb = seg_rgb_override if seg_rgb_override is not None else segmentation_to_rgb(segmentation)
    if image_rgb.shape[:2] != segmentation.shape[:2]:
        image_rgb = np.array(
            Image.fromarray(image_rgb).resize(
                (segmentation.shape[1], segmentation.shape[0]),
                Image.Resampling.LANCZOS,
            )
        )
    blend = (image_rgb.astype(np.float32) * (1 - alpha) + seg_rgb.astype(np.float32) * alpha).astype(np.uint8)
    return blend


def mask_to_png_bytes(arr: np.ndarray) -> bytes:
    """(H, W) uint8 or int -> PNG bytes."""
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def rgb_to_png_bytes(rgb: np.ndarray) -> bytes:
    """(H, W, 3) uint8 -> PNG bytes."""
    img = Image.fromarray(rgb)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# Clothing-only class IDs (for "clothing only" preview): top, dress, skirt, pants, belt, scarf
CLOTHING_IDS = (3, 4, 5, 6, 7, 10)
CLOTHING_NAMES = ["top", "dress", "skirt", "pants", "belt", "scarf"]

# All segments (1–17, skip background 0) with display names for color customization.
# Model does not separate sleeve/collar from "top" — top is the full upper garment.
SEGMENT_DISPLAY = [
    (1, "Face"),
    (2, "Hair"),
    (3, "Top"),           # shirt/upper garment (collar + sleeve area as one region)
    (4, "Dress"),
    (5, "Skirt"),
    (6, "Pants"),
    (7, "Belt"),
    (8, "Bag"),
    (9, "Hat"),
    (10, "Scarf"),
    (11, "Glasses"),
    (12, "Arms"),
    (13, "Hands"),
    (14, "Legs"),
    (15, "Feet"),
    (16, "Torso"),        # body
    (17, "Jewelry"),
]


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(int(rgb[0]), int(rgb[1]), int(rgb[2]))


def get_clothing_default_hex() -> list[dict]:
    """List of {id, name, defaultHex} for clothing-only segments (legacy)."""
    return [
        {"id": cid, "name": name, "defaultHex": rgb_to_hex(tuple(PALETTE[cid].tolist()))}
        for cid, name in zip(CLOTHING_IDS, CLOTHING_NAMES)
    ]


def get_all_segment_labels() -> list[dict]:
    """List of {id, name, defaultHex, group} for all segments 1–17 (sleeve/collar are part of Top)."""
    groups = {
        "body": (12, 13, 14, 15, 16, 1, 2),   # Arms, Hands, Legs, Feet, Torso, Face, Hair
        "clothing": (3, 4, 5, 6, 7, 10),      # Top, Dress, Skirt, Pants, Belt, Scarf
        "accessories": (8, 9, 11, 17),       # Bag, Hat, Glasses, Jewelry
    }
    out = []
    for cid, name in SEGMENT_DISPLAY:
        group = "body"
        for g, ids in groups.items():
            if cid in ids:
                group = g
                break
        out.append({
            "id": cid,
            "name": name,
            "defaultHex": rgb_to_hex(tuple(PALETTE[cid].tolist())),
            "group": group,
        })
    return out


def class_mask_to_png_bytes(segmentation: np.ndarray) -> bytes:
    """(H, W) class IDs 0-17 -> PNG with R=class_id, G=0, B=0 for frontend decoding."""
    h, w = segmentation.shape
    seg_u8 = np.clip(segmentation.astype(np.int32), 0, 255).astype(np.uint8)
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    rgb[:, :, 0] = seg_u8
    return rgb_to_png_bytes(rgb)


def clothing_only_rgb(segmentation: np.ndarray, grey_rest: bool = True) -> np.ndarray:
    """(H, W) -> (H, W, 3) with only clothing classes (3,4,5,6,7,10) colored; rest grey if grey_rest."""
    seg_rgb = segmentation_to_rgb(segmentation)
    if not grey_rest:
        return seg_rgb
    mask = np.isin(segmentation, list(CLOTHING_IDS))
    grey = np.full_like(seg_rgb, 64)
    out = np.where(mask[:, :, np.newaxis], seg_rgb, grey)
    return out.astype(np.uint8)


# --- Fashion fine-grained model (sayeed99/segformer-b2-fashion): 47 base + Cuff(47), Neckband(48) = 49 ---
# Class 32 = sleeve, 29 = collar; we derive 47 = cuff (bottom of sleeve), 48 = neckband (lower part of collar)
SLEEVE_CLASS = 32
COLLAR_CLASS = 29
CUFF_CLASS = 47
NECKBAND_CLASS = 48

FASHION_FINE_LABELS = [
    "Everything Else", "shirt, blouse", "top, t-shirt, sweatshirt", "sweater", "cardigan",
    "jacket", "vest", "pants", "shorts", "skirt", "coat", "dress", "jumpsuit", "cape",
    "glasses", "hat", "headband, head covering, hair accessory", "tie", "glove", "watch",
    "belt", "leg warmer", "tights, stockings", "sock", "shoe", "bag, wallet", "scarf",
    "umbrella", "hood", "collar", "lapel", "epaulette", "sleeve", "pocket", "neckline",
    "buckle", "zipper", "applique", "bead", "bow", "flower", "fringe", "ribbon",
    "rivet", "ruffle", "sequin", "tassel",
    "Cuff",      # 47
    "Neckband",  # 48
]


def derive_cuff_neckband(segmentation: np.ndarray) -> np.ndarray:
    """
    Split sleeve (32) into sleeve + cuff (47), and collar (29) into collar + neckband (48).
    Returns segmentation with 49 classes (0-48). Cuff = bottom ~30% of sleeve; Neckband = bottom ~50% of collar.
    """
    out = segmentation.astype(np.int64).copy()
    h, w = segmentation.shape
    y_coords = np.arange(h, dtype=np.int64)[:, np.newaxis]
    y_coords = np.broadcast_to(y_coords, (h, w))

    # Cuff: sleeve pixels in the bottom 30% of sleeve's Y extent
    sleeve_mask = segmentation == SLEEVE_CLASS
    if np.any(sleeve_mask):
        y_sleeve = y_coords[sleeve_mask]
        y_min_s, y_max_s = y_sleeve.min(), y_sleeve.max()
        y_cuff_thresh = y_min_s + 0.7 * (y_max_s - y_min_s) if y_max_s > y_min_s else y_min_s
        cuff_mask = sleeve_mask & (y_coords >= y_cuff_thresh)
        out[cuff_mask] = CUFF_CLASS

    # Neckband: collar pixels in the bottom 50% of collar's Y extent (closer to body)
    collar_mask = segmentation == COLLAR_CLASS
    if np.any(collar_mask):
        y_collar = y_coords[collar_mask]
        y_min_c, y_max_c = y_collar.min(), y_collar.max()
        y_neck_thresh = y_min_c + 0.5 * (y_max_c - y_min_c) if y_max_c > y_min_c else y_min_c
        neckband_mask = collar_mask & (y_coords >= y_neck_thresh)
        out[neckband_mask] = NECKBAND_CLASS

    return out


def _fashion_fine_palette() -> np.ndarray:
    """49 distinct colors: 47 base + Cuff, Neckband."""
    np.random.seed(42)
    colors = [[0, 0, 0]]  # 0: everything else
    for i in range(1, 49):
        hue = (i * 137.5) % 360 / 360.0
        sat = 0.5 + (i % 3) * 0.2
        val = 0.6 + (i % 5) * 0.08
        # simple HSV to RGB
        c = val * sat
        x = c * (1 - abs((hue * 6) % 2 - 1))
        m = val - c
        if hue < 1 / 6:
            r, g, b = c, x, 0
        elif hue < 2 / 6:
            r, g, b = x, c, 0
        elif hue < 3 / 6:
            r, g, b = 0, c, x
        elif hue < 4 / 6:
            r, g, b = 0, x, c
        elif hue < 5 / 6:
            r, g, b = x, 0, c
        else:
            r, g, b = c, 0, x
        colors.append([int((r + m) * 255), int((g + m) * 255), int((b + m) * 255)])
    return np.array(colors, dtype=np.uint8)


FASHION_FINE_PALETTE = _fashion_fine_palette()
FASHION_FINE_NUM_CLASSES = 49  # 47 base + Cuff (47), Neckband (48)


def segmentation_to_rgb_fashion_fine(segmentation: np.ndarray) -> np.ndarray:
    """(H, W) class IDs 0-48 -> (H, W, 3) RGB (supports 47 base + Cuff, Neckband)."""
    h, w = segmentation.shape
    idx = np.clip(segmentation.ravel(), 0, len(FASHION_FINE_PALETTE) - 1)
    rgb = FASHION_FINE_PALETTE[idx].reshape(h, w, 3)
    return rgb


def get_fashion_fine_segment_labels() -> list[dict]:
    """List of {id, name, defaultHex, group} for 49 classes (0-48). Includes Cuff (47), Neckband (48)."""
    groups_map = {
        "garments": (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13),
        "parts": (28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, CUFF_CLASS, NECKBAND_CLASS),
        "accessories": (14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27),
    }
    out = []
    for cid in range(FASHION_FINE_NUM_CLASSES):
        name = FASHION_FINE_LABELS[cid] if cid < len(FASHION_FINE_LABELS) else f"class_{cid}"
        group = "background"
        for g, ids in groups_map.items():
            if cid in ids:
                group = g
                break
        rgb = tuple(FASHION_FINE_PALETTE[cid].tolist())
        out.append({
            "id": cid,
            "name": name,
            "defaultHex": rgb_to_hex(rgb),
            "group": group,
        })
    return out
