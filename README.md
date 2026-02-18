# Clothing Segments

Human parsing and clothing segmentation for fashion images. Segment body and garment regions (face, hair, top, sleeve, collar, cuff, neckband, etc.), then recolor only those regions on the **real photo** while keeping texture and lighting. Designed for virtual try-on, configurable recolor UIs, and integration with Laravel (admin) and React Native (app).

---

## What this project does

- **Segments** a fashion/human image into semantic regions (e.g. top, sleeve, collar, arms, legs).
- **Two models:**
  - **fashn** — 18 classes (face, hair, top, dress, arms, torso, legs, etc.). [fashn-ai/fashn-human-parser](https://huggingface.co/fashn-ai/fashn-human-parser).
  - **fashion_fine** — 49 classes including **sleeve**, **collar**, **cuff**, **neckband**, hood, lapel, pocket, etc. [sayeed99/segformer-b2-fashion](https://huggingface.co/sayeed99/segformer-b2-fashion).
- **Recoloring:** Apply custom colors per segment on the **real image** (luminance-preserving so texture and shading stay).
- **Editable regions:** You (or Laravel admin) decide which segments are editable; the API can return only those (and only if present in the image).

**Use cases:** Virtual try-on, product configurators, Laravel-backed admin (set editable regions) + React Native app (recolor UI).

**Integration guides:**  
- **[LARAVEL.md](LARAVEL.md)** — How to integrate Laravel (admin config, store editable regions, expose API for the app).  
- **[REACT_NATIVE.md](REACT_NATIVE.md)** — How to integrate React Native (fetch config from Laravel, call segment API, recolor UI, composite image).

---

## Project structure

```
clothing-segments/
├── app/
│   ├── main.py          # FastAPI app: web UI, /api/segment, /api/segment-schema
│   └── static/
│       └── index.html    # Upload + recolor web UI
├── src/
│   ├── parser.py        # HumanParser (fashn), FashionFineParser (fashion_fine)
│   └── visualize.py     # Palettes, segment labels, cuff/neckband derivation
├── run.py               # CLI segmentation
├── example_usage.py     # Example Python script
├── requirements.txt
├── README.md
├── LARAVEL.md            # Laravel integration guide
└── REACT_NATIVE.md       # React Native integration guide
```

- **Backend:** Python, FastAPI, PyTorch, Transformers. Optional: `fashn-human-parser` for best fashn accuracy.
- **Web UI:** Single-page app (upload → segment → pick colors → see real image with new colors, download).

---

## Setup

**Requirements:** Python 3.9+, PyTorch, Transformers, Pillow, numpy. Optional: `fashn-human-parser`, `matplotlib` (for CLI `--visualize`).

For step-by-step instructions to run the project, see **[How to run the project](#how-to-run-the-project)** below.

---

## How to run the project

Follow these steps to get the project running on your machine.

### First-time setup

1. **Open a terminal** and go to the project folder:
   ```bash
   cd clothing-segments
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv .venv
   ```

3. **Activate the virtual environment:**
   - **macOS / Linux:**
     ```bash
     source .venv/bin/activate
     ```
   - **Windows (Command Prompt):**
     ```bash
     .venv\Scripts\activate.bat
     ```
   - **Windows (PowerShell):**
     ```bash
     .venv\Scripts\Activate.ps1
     ```

4. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   Wait until all packages (PyTorch, Transformers, FastAPI, etc.) finish installing.

### Run the web app

5. **Start the server** (with the virtual environment still activated):
   ```bash
   uvicorn app.main:app --reload
   ```

6. **Open the app in your browser:**  
   Go to [http://127.0.0.1:8000](http://127.0.0.1:8000).

7. **Use the web UI:**
   - Drag & drop an image or click to choose a file.
   - Select **fashn** or **fashion_fine** as the model.
   - Click **Run segmentation**.
   - Use the color pickers and checkboxes to recolor regions, then download the result if needed.

8. **Optional — API docs:**  
   Swagger: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) · ReDoc: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

To stop the server, press **Ctrl+C** in the terminal.

### Run from the command line (no web server)

1. **Activate the virtual environment** (if not already):
   ```bash
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   ```

2. **Segment an image:**
   ```bash
   python run.py path/to/your/image.jpg
   ```

3. **Optional — save mask and visualization:**
   ```bash
   python run.py path/to/image.jpg --out mask.png --visualize
   ```

4. **Optional — use pipeline backend** (no `fashn-human-parser` package):
   ```bash
   python run.py path/to/image.jpg --backend pipeline
   ```

---

## Usage

### Web app

```bash
uvicorn app.main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Upload an image, choose model (fashn or fashion_fine), run segmentation, then pick colors and check/uncheck regions. The preview shows the **real photo** with your colors applied (texture preserved). Download as PNG.

**API docs (Swagger):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) · ReDoc: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

### Command line

```bash
python run.py path/to/image.jpg
python run.py image.jpg --out mask.png --visualize
python run.py image.jpg --backend pipeline
```

### Python API

```python
from src.parser import HumanParser, FashionFineParser

# 18 classes
parser = HumanParser(backend="production")
seg = parser.predict("image.jpg")  # (H, W), 0–17

# 49 classes (sleeve, collar, cuff, neckband, …)
parser = FashionFineParser()
seg = parser.predict("image.jpg")  # (H, W), 0–48
```

---

## Segment labels

### fashn (18 classes)

| ID | Label       | ID | Label   |
|----|-------------|----|---------|
| 0  | background  | 9  | hat     |
| 1  | face        | 10 | scarf   |
| 2  | hair        | 11 | glasses |
| 3  | top         | 12 | arms    |
| 4  | dress       | 13 | hands   |
| 5  | skirt       | 14 | legs    |
| 6  | pants       | 15 | feet    |
| 7  | belt        | 16 | torso   |
| 8  | bag         | 17 | jewelry |

### fashion_fine (49 classes)

Includes all of the above plus fine-grained parts, e.g. **sleeve** (32), **collar** (29), **Cuff** (47), **Neckband** (48), hood, lapel, pocket, neckline, and many garment/accessory classes. Full list: `GET /api/segment-schema` (see [API reference](#api-reference) below).

---

## How to use in Laravel

Laravel is used to **configure which segments are editable** (e.g. per product or global). The mobile app (React Native) then reads this config and only shows color controls for those segments.

### 1. Get segment schema

Laravel and React Native must use the same segment **ids** and **model** names. Call the Clothing Segments API once (or cache the result) to get all segment definitions:

```http
GET {CLOTHING_SEGMENTS_URL}/api/segment-schema
```

**API documentation (this service):** `{BASE_URL}/docs` (Swagger) · `{BASE_URL}/redoc` (ReDoc) · `{BASE_URL}/openapi.json` (OpenAPI JSON).

Example base URL: `https://clothing-segments.onrender.com` (production) or `http://localhost:8000` (local).

Response:

```json
{
  "fashn": [
    { "id": 1, "name": "Face", "defaultHex": "#ffbb78", "group": "body" },
    { "id": 3, "name": "Top", "defaultHex": "#e6194b", "group": "clothing" }
  ],
  "fashion_fine": [
    { "id": 32, "name": "sleeve", "defaultHex": "...", "group": "parts" },
    { "id": 29, "name": "collar", "defaultHex": "...", "group": "parts" },
    { "id": 47, "name": "Cuff", "defaultHex": "...", "group": "parts" },
    { "id": 48, "name": "Neckband", "defaultHex": "...", "group": "parts" }
  ]
}
```

- **fashn:** 18 classes (ids 1–17; 0 = background).
- **fashion_fine:** 49 classes (ids 0–48), includes sleeve, collar, cuff, neckband, etc.

Use this in your **admin panel** to build a list of segments (e.g. checkboxes) so staff can choose which regions are editable. In React Native, use the schema to map `id` → `name` / `group`.

### 2. Store editable regions in Laravel

- Decide the **model**: `fashn` or `fashion_fine`.
- Store the list of **editable segment ids** (e.g. from admin checkboxes).

Example: migration for a config table:

```php
Schema::create('segmentation_configs', function (Blueprint $table) {
    $table->id();
    $table->string('model')->default('fashion_fine'); // fashn | fashion_fine
    $table->json('editable_region_ids');               // [32, 29, 47, 48]
    $table->timestamps();
});
```

Example: saving from admin form (segment ids from schema):

```php
$config = SegmentationConfig::updateOrCreate(
    ['id' => 1],
    [
        'model' => 'fashion_fine',
        'editable_region_ids' => [32, 29, 47, 48], // sleeve, collar, cuff, neckband
    ]
);
```

### 3. Expose config to the app (React Native)

Expose an endpoint that returns the same model and editable ids your app will send to the segment API, e.g.:

- **GET** `your-laravel-api.com/api/segmentation-config` (global config), or  
- **GET** `your-laravel-api.com/api/products/{id}/segmentation-config` (per-product config).

```php
// routes/api.php
Route::get('/segmentation-config', function () {
    $config = SegmentationConfig::first();
    return [
        'model' => $config->model ?? 'fashion_fine',
        'editable_region_ids' => $config->editable_region_ids ?? [],
    ];
});
```

Example response:

```json
{
  "model": "fashion_fine",
  "editable_region_ids": [32, 29, 47, 48]
}
```

React Native will call this endpoint, then call the Clothing Segments API with `model` and `editable_region_ids`.

---

## How to use in React Native

React Native uses the **Laravel config** to know which segments are editable, then calls the **Clothing Segments API** to segment the photo and get only those segments for recoloring.

### 1. Fetch config from Laravel

```js
const configRes = await fetch('https://your-laravel-api.com/api/segmentation-config');
const config = await configRes.json();
// { model: 'fashion_fine', editable_region_ids: [32, 29, 47, 48] }
```

### 2. Call segment API with image + config

When the user picks a photo, send it to the Clothing Segments API with the same `model` and `editable_region_ids`.

**POST** `{CLOTHING_SEGMENTS_URL}/api/segment`  
- **Content-Type:** `multipart/form-data`  
- **Body:** `file` (image file), `model` (`"fashn"` or `"fashion_fine"`), `editable_region_ids` (JSON string, e.g. `"[32,29,47,48]"`).

```js
const CLOTHING_SEGMENTS_URL = 'https://clothing-segments.onrender.com';

const formData = new FormData();
formData.append('file', {
  uri: imageUri,
  name: 'photo.jpg',
  type: 'image/jpeg',
});
formData.append('model', config.model);
formData.append('editable_region_ids', JSON.stringify(config.editable_region_ids));

const res = await fetch(`${CLOTHING_SEGMENTS_URL}/api/segment`, {
  method: 'POST',
  body: formData,
  headers: { 'Accept': 'application/json' },
});
const data = await res.json();
```

### 3. Use the response in your app

Laravel decides **which** regions are editable; this API returns only those (and only if present in the photo). React Native shows color controls only for `segment_labels` and composites the real image with changed colors.

- **data.segment_labels** — Only segments that are **both** in `editable_region_ids` **and** present in the image. Use these for your color pickers or checkboxes (one per segment).
- **data.original_resized** — Base64 PNG of the original image at mask size. Use for compositing.
- **data.class_mask** — Base64 PNG where each pixel’s R channel is the segment id (0–48 or 0–17). Use to know which pixel belongs to which segment when applying colors.
- **data.shape** — `[height, width]` of the mask and images.

### 4. Building the recolored image (same logic as web)

- Decode **original_resized** and **class_mask** (e.g. draw to canvas or use image libraries).
- For each pixel, read segment id from the mask. If that id is in `segment_labels` and the user chose a color for it, set the pixel to that color **while preserving luminance** (e.g. use custom hue/saturation, keep original luminance) so the real photo texture stays.
- Display the result and/or offer download. See the web app’s `drawRecoloredImage` logic in `app/static/index.html` for the exact luminance-preserving formula.

### 5. Summary flow

1. App starts → fetch Laravel `segmentation-config` → get `model` and `editable_region_ids`.
2. User selects photo → POST to Clothing Segments `/api/segment` with `file`, `model`, `editable_region_ids`.
3. Show color pickers only for `data.segment_labels`.
4. When user changes a color → recomposite image (original + custom colors on segment pixels, luminance-preserving) → show preview and allow download.

### 6. Integration summary

| Layer | Responsibility |
|-------|----------------|
| **Laravel admin** | Store `model` and `editable_region_ids`; expose via your API (e.g. `GET /api/segmentation-config` or `GET /api/products/{id}/segmentation-config`). |
| **Clothing Segments API** | `GET /api/segment-schema` → schema; `POST /api/segment` with `file`, `model`, `editable_region_ids` → segmentation + filtered `segment_labels` + assets for recoloring. |
| **React Native** | Get config from Laravel → call segment API → show only `segment_labels` for recoloring; composite and show/download real image with new colors. |

### 7. Environment (base URL)

Point Laravel and React Native to the same base URL for this service:

- **Development:** `http://localhost:8000`
- **Production:** `https://clothing-segments.onrender.com`

Then:

- Schema: `GET {BASE_URL}/api/segment-schema`
- Segment: `POST {BASE_URL}/api/segment`

---

## API reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Web UI (upload + recolor). |
| GET | `/docs` | Swagger UI. |
| GET | `/redoc` | ReDoc. |
| GET | `/openapi.json` | OpenAPI 3 schema. |
| GET | `/api/segment-schema` | Segment definitions for both models (id, name, defaultHex, group). Use in Laravel admin and React Native. |
| POST | `/api/segment` | Upload image; returns segmentation and assets. Optional form field: `editable_region_ids` (JSON array) to restrict `segment_labels`. |

**POST /api/segment** form fields:

- `file` (required) — Image file (JPEG/PNG).
- `model` — `fashn` or `fashion_fine` (default: `fashn`).
- `editable_region_ids` — Optional. JSON string, e.g. `"[32,29,47,48]"`. If provided, `segment_labels` only includes segments in this list that also appear in the image.

Response includes: `shape`, `model`, `num_classes`, `mask`, `segmentation`, `clothing_segmentation`, `overlay`, `class_mask`, `original_resized`, `segment_labels`, `clothing_labels`, `labels`.

Full request/response schemas: [Swagger](https://clothing-segments.onrender.com/docs) · [ReDoc](https://clothing-segments.onrender.com/redoc).

---

## Requirements

- Python 3.9+
- PyTorch, Transformers, Pillow, numpy
- `fashn-human-parser` (optional, for best fashn accuracy)
- `matplotlib` (optional, for CLI `--visualize`)
- FastAPI, uvicorn (web app)

---

## License

Model licenses: [fashn-human-parser](https://huggingface.co/fashn-ai/fashn-human-parser), [segformer-b2-fashion](https://huggingface.co/sayeed99/segformer-b2-fashion) (NVIDIA SegFormer). See the linked Hugging Face cards for terms.
