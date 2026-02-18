# Laravel integration guide

This guide explains how to **integrate** your Laravel application with the **Clothing Segments** service and how to **connect** with the React Native app. Laravel’s role is to **store which segments are editable** (e.g. sleeve, collar, cuff, neckband) and **expose that config** to the mobile app via your API.

---

## Overview

| What Laravel does | What React Native does |
|-------------------|-------------------------|
| Fetches/caches segment definitions from Clothing Segments API | Fetches config (model + editable_region_ids) from **your Laravel API** |
| Admin chooses which regions are editable (e.g. checkboxes) | Calls Clothing Segments API with image + that config |
| Stores `model` and `editable_region_ids` in DB | Shows color pickers only for segments in `segment_labels` |
| Exposes **GET /api/segmentation-config** (or per-product) | Composites recolored image and shows/downloads it |

Laravel and React Native **must use the same segment ids and model names**. The single source of truth for segment definitions is the Clothing Segments API (`GET /api/segment-schema`).

---

## Prerequisites

- Laravel application (e.g. 9.x, 10.x, 11.x).
- Clothing Segments API base URL: `https://clothing-segments.onrender.com` (or `http://localhost:8000` for local).
- PHP with `file_get_contents` or Guzzle/cURL for calling the segment schema endpoint (or use from admin once and store/cache).

---

## Step 1: Configure environment

Add the Clothing Segments base URL to `.env`:

```env
CLOTHING_SEGMENTS_URL=https://clothing-segments.onrender.com
```

Register it in `config/services.php` (optional but recommended):

```php
return [
    // ...
    'clothing_segments' => [
        'url' => env('CLOTHING_SEGMENTS_URL', 'https://clothing-segments.onrender.com'),
    ],
];
```

Use it in code as `config('services.clothing_segments.url')`.

---

## Step 2: Fetch segment schema (for admin UI)

Laravel and React Native must use the same segment **ids** and **model** names. Get them from the Clothing Segments API.

**GET** `{CLOTHING_SEGMENTS_URL}/api/segment-schema`

Example using Laravel HTTP client:

```php
use Illuminate\Support\Facades\Http;

$baseUrl = config('services.clothing_segments.url');
$response = Http::get("{$baseUrl}/api/segment-schema");

if ($response->successful()) {
    $schema = $response->json();
    // $schema['fashn']     => list of { id, name, defaultHex, group }
    // $schema['fashion_fine'] => list of { id, name, defaultHex, group }
}
```

- **fashn:** 18 classes (ids 0–17; 0 = background).
- **fashion_fine:** 49 classes (ids 0–48), e.g. sleeve (32), collar (29), Cuff (47), Neckband (48).

Use this in your **admin panel** to build checkboxes or a multi-select so staff can choose which segments are editable. You can cache this response (e.g. Redis or file cache for 24 hours) so you don’t call the external API on every admin page load.

---

## Step 3: Database – store editable regions

Create a migration for the config your app will expose to React Native:

```bash
php artisan make:migration create_segmentation_configs_table
```

Migration:

```php
Schema::create('segmentation_configs', function (Blueprint $table) {
    $table->id();
    $table->string('model')->default('fashion_fine'); // fashn | fashion_fine
    $table->json('editable_region_ids');               // [32, 29, 47, 48]
    $table->timestamps();
});
```

Run:

```bash
php artisan migrate
```

---

## Step 4: Eloquent model

```bash
php artisan make:model SegmentationConfig
```

```php
namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class SegmentationConfig extends Model
{
    protected $fillable = ['model', 'editable_region_ids'];

    protected $casts = [
        'editable_region_ids' => 'array',
    ];
}
```

---

## Step 5: Admin: save config (example)

Example of saving from an admin form (e.g. after staff selects segments from the schema):

```php
use App\Models\SegmentationConfig;

// Single global config
SegmentationConfig::updateOrCreate(
    ['id' => 1],
    [
        'model' => 'fashion_fine',
        'editable_region_ids' => [32, 29, 47, 48], // sleeve, collar, cuff, neckband
    ]
);
```

For **per-product** config, add a `product_id` (or similar) to the table and use:

```php
SegmentationConfig::updateOrCreate(
    ['product_id' => $productId],
    [
        'model' => request('model', 'fashion_fine'),
        'editable_region_ids' => request('editable_region_ids', []),
    ]
);
```

---

## Step 6: Expose config to React Native (API)

React Native will call **your Laravel API** to get `model` and `editable_region_ids`, then call the Clothing Segments API with those values. Add a route and controller (or closure).

**Option A – Global config**

In `routes/api.php`:

```php
Route::get('/segmentation-config', function () {
    $config = \App\Models\SegmentationConfig::first();
    return response()->json([
        'model' => $config->model ?? 'fashion_fine',
        'editable_region_ids' => $config->editable_region_ids ?? [],
    ]);
});
```

**Option B – Per-product config (controller)**

```php
// routes/api.php
Route::get('/products/{id}/segmentation-config', [SegmentationConfigController::class, 'show']);
```

```php
namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\SegmentationConfig;
use App\Models\Product;

class SegmentationConfigController extends Controller
{
    public function show(Product $product)
    {
        $config = SegmentationConfig::where('product_id', $product->id)->first();
        return response()->json([
            'model' => $config->model ?? 'fashion_fine',
            'editable_region_ids' => $config->editable_region_ids ?? [],
        ]);
    }
}
```

Example JSON response (what React Native will receive):

```json
{
  "model": "fashion_fine",
  "editable_region_ids": [32, 29, 47, 48]
}
```

---

## Step 7: Optional – Admin UI to choose segments

1. On admin page load, fetch schema (or use cached):
   - `GET {CLOTHING_SEGMENTS_URL}/api/segment-schema`
2. Choose a **model** (e.g. `fashion_fine`).
3. Render checkboxes (or multi-select) for each segment in `schema['fashion_fine']` (use `id` and `name`).
4. On submit, save selected ids as `editable_region_ids` and `model` via `SegmentationConfig::updateOrCreate` (see Step 5).

This way, non-technical staff control which regions the mobile app can recolor.

---

## How Laravel and React Native connect

1. **Laravel** stores `model` and `editable_region_ids` (from admin) and exposes them at:
   - `GET your-laravel-api.com/api/segmentation-config`, or
   - `GET your-laravel-api.com/api/products/{id}/segmentation-config`
2. **React Native** calls that Laravel endpoint first, then calls:
   - `POST {CLOTHING_SEGMENTS_URL}/api/segment` with `file`, `model`, and `editable_region_ids`.
3. Clothing Segments API returns `segment_labels` filtered to editable + present-in-image; React Native uses that for color pickers and compositing.

So: **Laravel = source of “which regions are editable”; React Native = consumer of that config + segment API.**

---

## API reference (Clothing Segments – what Laravel uses)

| Method | Endpoint | Use in Laravel |
|--------|----------|----------------|
| GET | `{CLOTHING_SEGMENTS_URL}/api/segment-schema` | Fetch segment list for admin UI (ids, names, groups). Cache recommended. |

Laravel does **not** call `POST /api/segment`; that is called by React Native (with the config Laravel provided).

---

## Checklist

- [ ] Add `CLOTHING_SEGMENTS_URL` to `.env` and (optionally) `config/services.php`.
- [ ] Create `segmentation_configs` table and `SegmentationConfig` model.
- [ ] Fetch segment schema (e.g. for admin); optionally cache it.
- [ ] Implement admin UI to choose model and editable segment ids, then save to DB.
- [ ] Expose `GET /api/segmentation-config` (or per-product) returning `model` and `editable_region_ids`.
- [ ] Ensure CORS allows your React Native app origin if the app calls Laravel from a different domain.

For the React Native side (fetching this config and calling the segment API), see **[REACT_NATIVE.md](REACT_NATIVE.md)**.
