"""
FASHN Human Parser integration.

Supports:
- Hugging Face pipeline (quick, no extra package)
- fashn-human-parser package (recommended for production accuracy)
"""

from pathlib import Path
from typing import Literal, Union

import numpy as np

# 18-class label schema (matches fashn-human-parser)
SEGMENT_LABELS = [
    "background",
    "face",
    "hair",
    "top",
    "dress",
    "skirt",
    "pants",
    "belt",
    "bag",
    "hat",
    "scarf",
    "glasses",
    "arms",
    "hands",
    "legs",
    "feet",
    "torso",
    "jewelry",
]

# Virtual try-on: identity (preserved) vs clothing (replaceable)
IDENTITY_LABELS = {"face", "hair", "jewelry", "bag", "glasses", "hat"}
TOPS_LABELS = {"top", "dress", "scarf"}
BOTTOMS_LABELS = {"skirt", "pants", "belt"}
BODY_LABELS = {"arms", "hands", "legs", "feet", "torso"}


class HumanParser:
    """
    Human parsing for fashion images using fashn-ai/fashn-human-parser.

    Use backend="production" (default) for best accuracy; uses fashn-human-parser
    with training-matched preprocessing. Use backend="pipeline" for no extra deps.
    """

    MODEL_ID = "fashn-ai/fashn-human-parser"

    def __init__(
        self,
        backend: Literal["production", "pipeline"] = "production",
        device: Union[str, None] = None,
    ):
        """
        Args:
            backend: "production" (fashn-human-parser package) or "pipeline" (transformers only).
            device: "cuda", "cpu", or None for auto.
        """
        self.backend = backend
        self._parser = None
        self._pipe = None
        self._processor = None
        self._model = None
        self._device = device
        self._init_backend()

    def _init_backend(self) -> None:
        if self.backend == "production":
            try:
                from fashn_human_parser import FashnHumanParser
                self._parser = FashnHumanParser()
            except ImportError:
                raise ImportError(
                    "Install production backend: pip install fashn-human-parser"
                )
        else:
            import torch
            from transformers import pipeline
            dev = self._device or ("cuda" if torch.cuda.is_available() else "cpu")
            self._pipe = pipeline(
                "image-segmentation",
                model=self.MODEL_ID,
                device=0 if dev == "cuda" else -1,
            )

    def predict(
        self,
        image: Union[str, Path, "np.ndarray"],
    ) -> np.ndarray:
        """
        Run human parsing on an image.

        Args:
            image: Path to image file, or numpy array (H, W, 3) RGB.

        Returns:
            Segmentation mask as numpy array (H, W) with class IDs 0–17.
        """
        if self.backend == "production":
            return self._predict_production(image)
        return self._predict_pipeline(image)

    def _predict_production(
        self,
        image: Union[str, Path, np.ndarray],
    ) -> np.ndarray:
        if isinstance(image, (str, Path)):
            return self._parser.predict(str(image))
        # Package may expect path; save temp or use pipeline for in-memory
        import tempfile
        from PIL import Image
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            Path(f.name).write_bytes(
                _ndarray_to_png_bytes(image)
            )
            try:
                return self._parser.predict(f.name)
            finally:
                Path(f.name).unlink(missing_ok=True)

    def _predict_pipeline(
        self,
        image: Union[str, Path, np.ndarray],
    ) -> np.ndarray:
        from PIL import Image

        if isinstance(image, np.ndarray):
            image = Image.fromarray(image.astype(np.uint8))
        else:
            image = Image.open(image).convert("RGB")

        result = self._pipe(image)
        # result: list of {"label": str, "score": float, "mask": PIL Image}
        h, w = image.size[1], image.size[0]
        mask = np.zeros((h, w), dtype=np.int64)
        for item in result:
            label = item["label"]
            if label not in SEGMENT_LABELS:
                continue
            idx = SEGMENT_LABELS.index(label)
            m = np.array(item["mask"])
            if m.ndim == 3:
                m = m.max(axis=-1) if m.shape[-1] > 1 else m.squeeze()
            mask[m > 0] = idx
        return mask

    def get_mask_for_labels(
        self,
        segmentation: np.ndarray,
        labels: Union[str, list[str]],
    ) -> np.ndarray:
        """Return binary mask for given label name(s)."""
        if isinstance(labels, str):
            labels = [labels]
        indices = [SEGMENT_LABELS.index(l) for l in labels if l in SEGMENT_LABELS]
        return np.isin(segmentation, indices).astype(np.uint8)

    def get_clothing_mask(self, segmentation: np.ndarray) -> np.ndarray:
        """Mask for all clothing (tops + bottoms)."""
        return self.get_mask_for_labels(
            segmentation,
            list(TOPS_LABELS | BOTTOMS_LABELS),
        )

    def get_identity_mask(self, segmentation: np.ndarray) -> np.ndarray:
        """Mask for identity regions (face, hair, accessories)."""
        return self.get_mask_for_labels(segmentation, list(IDENTITY_LABELS))


def _ndarray_to_png_bytes(arr: np.ndarray) -> bytes:
    from PIL import Image
    import io
    if arr.max() <= 1.0:
        arr = (arr * 255).astype(np.uint8)
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class FashionFineParser:
    """
    Fine-grained fashion segmentation with sleeve, collar, etc.
    Uses sayeed99/segformer-b2-fashion (47 classes).
    """

    MODEL_ID = "sayeed99/segformer-b2-fashion"

    def __init__(self, device: Union[str, None] = None):
        import torch
        from transformers import SegformerImageProcessor, AutoModelForSemanticSegmentation

        self._device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._processor = SegformerImageProcessor.from_pretrained(self.MODEL_ID)
        self._model = AutoModelForSemanticSegmentation.from_pretrained(self.MODEL_ID)
        self._model.to(self._device)
        self._model.eval()

    def predict(
        self,
        image: Union[str, Path, np.ndarray],
    ) -> np.ndarray:
        """
        Returns segmentation (H, W) with class IDs 0–46.
        """
        from PIL import Image
        import torch

        if isinstance(image, np.ndarray):
            pil_image = Image.fromarray(image.astype(np.uint8)).convert("RGB")
        else:
            pil_image = Image.open(image).convert("RGB")

        inputs = self._processor(images=pil_image, return_tensors="pt", padding=True)
        inputs = {k: v.to(self._device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self._model(**inputs)

        logits = outputs.logits
        h, w = pil_image.size[1], pil_image.size[0]
        upsampled = torch.nn.functional.interpolate(
            logits,
            size=(h, w),
            mode="bilinear",
            align_corners=False,
        )
        pred = upsampled.argmax(dim=1).squeeze(0).cpu().numpy()
        return pred.astype(np.int64)
