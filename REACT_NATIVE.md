# React Native integration guide

This guide explains how to **integrate** your React Native app with the **Clothing Segments** service and how to **connect** it with **Laravel**. React Native’s role is to **get segmentation config from Laravel**, **send the user’s photo to the Clothing Segments API**, and **show a recolor UI** using only the editable segments Laravel allows.

---

## Overview

| Step | Where | What happens |
|------|--------|----------------|
| 1 | React Native → **Laravel** | App fetches `model` and `editable_region_ids` (e.g. `GET /api/segmentation-config`). |
| 2 | React Native → **Clothing Segments API** | App sends photo + that config to `POST /api/segment`. |
| 3 | Clothing Segments API | Returns segmentation + `segment_labels` (only editable and present in image). |
| 4 | React Native | Shows color pickers for `segment_labels`, composites recolored image, preview/download. |

Laravel decides **which** regions are editable; the Clothing Segments API returns only those (and only if present in the photo). React Native never invents segment ids—it uses the same ids and model names from Laravel and the segment schema.

---

## Prerequisites

- React Native project (Expo or bare).
- **Laravel API** base URL (e.g. `https://your-laravel-api.com`) that exposes segmentation config (see [LARAVEL.md](LARAVEL.md)).
- **Clothing Segments API** base URL: `https://clothing-segments.onrender.com` (or `http://localhost:8000` for local).

---

## Step 1: Configure environment

Define both base URLs (e.g. in `.env` or app config):

```env
LARAVEL_API_URL=https://your-laravel-api.com
CLOTHING_SEGMENTS_URL=https://clothing-segments.onrender.com
```

In code (example with constants):

```js
// config.js or constants.js
export const LARAVEL_API_URL = process.env.EXPO_PUBLIC_LARAVEL_API_URL || 'https://your-laravel-api.com';
export const CLOTHING_SEGMENTS_URL = process.env.EXPO_PUBLIC_CLOTHING_SEGMENTS_URL || 'https://clothing-segments.onrender.com';
```

Use these when calling Laravel and the Clothing Segments API.

---

## Step 2: Fetch config from Laravel

Before segmenting a photo, the app must know **model** and **editable_region_ids**. Those come from **your Laravel API**.

**GET** `{LARAVEL_API_URL}/api/segmentation-config`  
or per-product: **GET** `{LARAVEL_API_URL}/api/products/{productId}/segmentation-config`

Example:

```js
const response = await fetch(`${LARAVEL_API_URL}/api/segmentation-config`);
const config = await response.json();
// config = { model: 'fashion_fine', editable_region_ids: [32, 29, 47, 48] }
```

Call this when the recolor flow starts (e.g. on screen mount or when user taps “Recolor photo”). You can cache the result in state or async storage if the config rarely changes.

---

## Step 3: Call Clothing Segments API with image + config

When the user has selected a photo (e.g. from gallery or camera), send it to the Clothing Segments API together with the config from Laravel.

**POST** `{CLOTHING_SEGMENTS_URL}/api/segment`

- **Content-Type:** `multipart/form-data`
- **Body:**
  - `file` – image file (JPEG/PNG)
  - `model` – `"fashn"` or `"fashion_fine"` (from Laravel)
  - `editable_region_ids` – JSON string, e.g. `"[32,29,47,48]"` (from Laravel)

Example (React Native with `uri` from image picker):

```js
async function segmentImage(imageUri, config) {
  const formData = new FormData();
  formData.append('file', {
    uri: imageUri,
    name: 'photo.jpg',
    type: 'image/jpeg',
  });
  formData.append('model', config.model);
  formData.append('editable_region_ids', JSON.stringify(config.editable_region_ids));

  const response = await fetch(`${CLOTHING_SEGMENTS_URL}/api/segment`, {
    method: 'POST',
    body: formData,
    headers: {
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Segment API error: ${response.status}`);
  }

  return response.json();
}
```

Use the **same** `config` object you got from Laravel (same `model` and `editable_region_ids`).

---

## Step 4: Use the response in your app

The API returns JSON. Key fields for the recolor flow:

| Field | Description |
|-------|-------------|
| **segment_labels** | List of segments that are **both** in `editable_region_ids` **and** present in the image. Each item: `{ id, name, defaultHex, group }`. Use for color pickers / checkboxes (one per segment). |
| **original_resized** | Base64 PNG of the original image at mask size. Use for compositing the final image. |
| **class_mask** | Base64 PNG where each pixel’s **R channel** is the segment id (0–48 or 0–17). Use to know which pixel belongs to which segment when applying colors. |
| **shape** | `[height, width]` of the mask and images. |

Laravel decides **which** regions are editable; the API returns only those (and only if present in the photo). React Native should show color controls **only** for `segment_labels` and composite the real image with the user’s chosen colors.

Example state after segmenting:

```js
const [segmentData, setSegmentData] = useState(null);

// After segmentImage():
const data = await segmentImage(imageUri, config);
setSegmentData({
  segment_labels: data.segment_labels,
  original_resized: data.original_resized,
  class_mask: data.class_mask,
  shape: data.shape,
});
```

---

## Step 5: Build the recolor UI

- For each item in `segmentData.segment_labels`, show a **color picker** (and optionally a checkbox to enable/disable that region).
- Store selected colors in state, e.g. `{ [segmentId]: '#hexcolor' }`.
- When the user changes a color, **recomposite** the image (see Step 6) and update the preview.

You only need to show controls for segments in `segment_labels`; ignore other segment ids.

---

## Step 6: Composite the recolored image

To produce the final image with custom colors on editable segments:

1. Decode **original_resized** and **class_mask** (e.g. draw to canvas or use an image/Canvas library that can read base64 PNG and pixel data).
2. For each pixel:
   - Read segment id from the **R channel** of the class_mask at that pixel.
   - If that id is in `segment_labels` and the user chose a color for it, set the pixel to that color **while preserving luminance** (e.g. convert original pixel to HSL, replace hue/saturation with the chosen color, keep luminance). This keeps texture and shading.
3. Draw the result to a new image/canvas and use it for preview and download.

The exact luminance-preserving formula is implemented in the web app: see `drawRecoloredImage` in `app/static/index.html` in this repo for reference.

Libraries that can help: `expo-image-manipulator`, `react-native-canvas`, or a native module that decodes base64 images and allows pixel read/write. Logic is the same as the web: original + custom colors only on editable segment pixels, luminance preserved.

---

## Step 7: End-to-end flow (how everything connects)

1. **App starts or user enters recolor flow**  
   → Fetch config from Laravel: `GET {LARAVEL_API_URL}/api/segmentation-config`  
   → Store `config` (model + editable_region_ids).

2. **User selects a photo**  
   → Call Clothing Segments API: `POST {CLOTHING_SEGMENTS_URL}/api/segment` with `file`, `config.model`, `config.editable_region_ids`  
   → Store `segment_labels`, `original_resized`, `class_mask`, `shape`.

3. **Show recolor UI**  
   → Render one color picker per item in `segment_labels`  
   → On color change, recomposite image (original + new colors on segment pixels, luminance-preserving) and update preview.

4. **User saves or shares**  
   → Export the composited image (e.g. save to gallery or share).

---

## How React Native and Laravel connect

- **Laravel** is the **source of config**: it stores which segments are editable and exposes that via `GET /api/segmentation-config` (or per-product). See [LARAVEL.md](LARAVEL.md).
- **React Native** is the **consumer**: it calls Laravel first to get `model` and `editable_region_ids`, then calls the Clothing Segments API with that exact config. It never hardcodes segment ids; it always uses what Laravel and the segment API provide.

So: **Laravel → config; React Native → config + image → Clothing Segments API → segment_labels + assets; React Native → recolor UI + composite.**

---

## API reference (Clothing Segments – what React Native uses)

| Method | Endpoint | Use in React Native |
|--------|----------|----------------------|
| GET | `{CLOTHING_SEGMENTS_URL}/api/segment-schema` | Optional: map segment id → name/group for labels. Not required if you only use `segment_labels` from the segment response. |
| POST | `{CLOTHING_SEGMENTS_URL}/api/segment` | Send image + `model` + `editable_region_ids`; get `segment_labels`, `original_resized`, `class_mask`, `shape` for recolor UI and compositing. |

**POST /api/segment** form fields:

- `file` (required) – image file
- `model` – `"fashn"` or `"fashion_fine"` (from Laravel)
- `editable_region_ids` – JSON string, e.g. `"[32,29,47,48]"` (from Laravel)

---

## Checklist

- [ ] Set `LARAVEL_API_URL` and `CLOTHING_SEGMENTS_URL` in environment/config.
- [ ] Fetch segmentation config from Laravel when starting the recolor flow.
- [ ] Call `POST /api/segment` with image + Laravel’s `model` and `editable_region_ids`.
- [ ] Use `segment_labels` only for color pickers; use `original_resized` and `class_mask` for compositing.
- [ ] Implement luminance-preserving recolor and preview/download.
- [ ] Handle errors (network, 4xx/5xx from Laravel or Clothing Segments API).

For the Laravel side (exposing segmentation config and storing editable regions), see **[LARAVEL.md](LARAVEL.md)**.
