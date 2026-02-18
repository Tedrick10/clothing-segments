"""
Web API for clothing segmentation.
Run: uvicorn app.main:app --reload
Swagger UI: http://127.0.0.1:8000/docs
"""

import base64
import io
import json
import sys
from pathlib import Path
from typing import Any

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, Field
import numpy as np
from PIL import Image

from src.parser import HumanParser, FashionFineParser, SEGMENT_LABELS
from src.visualize import (
    overlay_image,
    segmentation_to_rgb,
    mask_to_png_bytes,
    rgb_to_png_bytes,
    class_mask_to_png_bytes,
    get_clothing_default_hex,
    get_all_segment_labels,
    get_fashion_fine_segment_labels,
    clothing_only_rgb,
    segmentation_to_rgb_fashion_fine,
    derive_cuff_neckband,
    FASHION_FINE_NUM_CLASSES,
)


# --- OpenAPI / Swagger response models ---

class SegmentLabel(BaseModel):
    id: int = Field(..., description="Segment class ID (0–17 for fashn, 0–48 for fashion_fine)")
    name: str = Field(..., description="Display name (e.g. sleeve, collar, Cuff)")
    defaultHex: str = Field(..., description="Default color hex (e.g. #e6194b)")
    group: str = Field(..., description="Group: body, clothing, accessories, parts, garments, background")


class SegmentSchemaResponse(BaseModel):
    fashn: list[SegmentLabel] = Field(..., description="18 segments for fashn model (ids 1–17)")
    fashion_fine: list[SegmentLabel] = Field(..., description="49 segments for fashion_fine (sleeve, collar, cuff, neckband, etc.)")


class SegmentResponse(BaseModel):
    shape: list[int] = Field(..., description="[height, width] of mask and images")
    model: str = Field(..., description="Model used: fashn or fashion_fine")
    num_classes: int = Field(..., description="18 or 49")
    mask: str = Field(..., description="Base64 PNG grayscale mask")
    segmentation: str = Field(..., description="Base64 PNG colored segmentation")
    clothing_segmentation: str = Field(..., description="Base64 PNG clothing-only view")
    overlay: str = Field(..., description="Base64 PNG overlay on photo")
    class_mask: str = Field(..., description="Base64 PNG with R=class_id per pixel (for client recolor)")
    original_resized: str = Field(..., description="Base64 PNG original image at mask size")
    segment_labels: list[SegmentLabel] = Field(..., description="Segments (filtered by editable_region_ids + present if provided)")
    clothing_labels: list[Any] = Field(..., description="Legacy clothing-only labels")
    labels: list[str] = Field(..., description="Full label names for fashn (empty for fashion_fine)")


app = FastAPI(
    title="Clothing Segments API",
    description="""
Human parsing and clothing segmentation for fashion images.

- **Segment schema**: Get segment definitions (id, name, group) for Laravel admin and React Native.
- **Segment**: Upload an image; get segmentation masks and segment labels. Optionally pass `editable_region_ids` (from Laravel) to restrict returned segments.

**Models:**
- `fashn`: 18 classes (face, hair, top, arms, torso, legs, etc.)
- `fashion_fine`: 49 classes including sleeve, collar, cuff, neckband, hood, lapel, pocket, etc.
    """,
    version="1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lazy-load parsers on first request
_parser_fashn = None
_parser_fashion_fine = None


def get_parser(model: str):
    global _parser_fashn, _parser_fashion_fine
    if model == "fashion_fine":
        if _parser_fashion_fine is None:
            _parser_fashion_fine = FashionFineParser()
        return _parser_fashion_fine, "fashion_fine"
    if _parser_fashn is None:
        try:
            _parser_fashn = HumanParser(backend="production")
        except Exception:
            _parser_fashn = HumanParser(backend="pipeline")
    return _parser_fashn, "fashn"


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index():
    """Serve the web app (upload + recolor)."""
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get(
    "/api/segment-schema",
    response_model=SegmentSchemaResponse,
    summary="Get segment schema",
    description="Returns segment definitions (id, name, defaultHex, group) for both models. Use in Laravel admin to configure which regions are editable, and in React Native to map ids to names.",
    tags=["API"],
)
async def segment_schema():
    return SegmentSchemaResponse(
        fashn=get_all_segment_labels(),
        fashion_fine=get_fashion_fine_segment_labels(),
    )


@app.post(
    "/api/segment",
    response_model=SegmentResponse,
    summary="Segment an image",
    description="""
Upload an image and get segmentation results.

- **file**: Image file (JPEG, PNG).
- **model**: `fashn` (18 classes) or `fashion_fine` (49 classes, includes sleeve, collar, cuff, neckband).
- **editable_region_ids**: Optional. JSON array of segment ids, e.g. `"[32,29,47,48]"`. If provided (e.g. from Laravel), only segments that are both in this list and present in the image are returned in `segment_labels`.
    """,
    tags=["API"],
)
async def segment(
    file: UploadFile = File(..., description="Image file (JPEG or PNG)"),
    model: str = Form(
        "fashn",
        description="Segmentation model: fashn (18 classes) or fashion_fine (49 classes)",
    ),
    editable_region_ids: str = Form(
        None,
        description="Optional. JSON array of segment ids to return, e.g. [32,29,47,48]. From Laravel config.",
    ),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "Please upload an image (e.g. JPEG, PNG).")
    if model not in ("fashn", "fashion_fine"):
        model = "fashn"

    editable_ids = None
    if editable_region_ids:
        try:
            editable_ids = set(json.loads(editable_region_ids))
        except (json.JSONDecodeError, TypeError):
            pass

    contents = await file.read()
    try:
        img = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception as e:
        raise HTTPException(400, f"Invalid image: {e}")

    img_np = np.array(img)
    parser, model_used = get_parser(model)
    segmentation = parser.predict(img_np)

    if model_used == "fashion_fine":
        segmentation = derive_cuff_neckband(segmentation)  # 47 classes -> 49 (add Cuff, Neckband)

    h, w = segmentation.shape
    img_resized = np.array(
        Image.fromarray(img_np).resize((w, h), Image.Resampling.LANCZOS)
    )

    class_mask_png = class_mask_to_png_bytes(segmentation)

    if model_used == "fashion_fine":
        seg_rgb = segmentation_to_rgb_fashion_fine(segmentation)
        segment_labels = get_fashion_fine_segment_labels()
        overlay = overlay_image(segmentation, img_np, alpha=0.5, seg_rgb_override=seg_rgb)
        clothing_only_png_b64 = base64.b64encode(rgb_to_png_bytes(seg_rgb)).decode()
    else:
        seg_rgb = segmentation_to_rgb(segmentation)
        segment_labels = get_all_segment_labels()
        overlay = overlay_image(segmentation, img_np, alpha=0.5)
        clothing_only_png_b64 = base64.b64encode(
            rgb_to_png_bytes(clothing_only_rgb(segmentation))
        ).decode()

    seg_png = rgb_to_png_bytes(seg_rgb)
    overlay_png = rgb_to_png_bytes(overlay)

    present_ids = set(segmentation.flat)
    if editable_ids is not None:
        segment_labels = [l for l in segment_labels if l["id"] in editable_ids and l["id"] in present_ids]

    return {
        "shape": [h, w],
        "model": model_used,
        "num_classes": FASHION_FINE_NUM_CLASSES if model_used == "fashion_fine" else 18,
        "mask": base64.b64encode(
            mask_to_png_bytes(
                (segmentation.astype(np.uint8) * (255 // (FASHION_FINE_NUM_CLASSES - 1 if model_used == "fashion_fine" else 17)))
            )
        ).decode(),
        "segmentation": base64.b64encode(seg_png).decode(),
        "clothing_segmentation": clothing_only_png_b64,
        "overlay": base64.b64encode(overlay_png).decode(),
        "class_mask": base64.b64encode(class_mask_png).decode(),
        "original_resized": base64.b64encode(rgb_to_png_bytes(img_resized)).decode(),
        "segment_labels": segment_labels,
        "clothing_labels": get_clothing_default_hex(),
        "labels": SEGMENT_LABELS if model_used == "fashn" else [],
    }


# Mount static assets (CSS/JS if any)
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
