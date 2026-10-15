# Sources for demo/data

Recorded 2026-10-15T22:01:26+00:00 with `demo/record.py` in **no-llm** mode
(model: None). Replies are canned: the tools were called directly, without an LLM.

## Commands

```bash
cd /Users/lalligagger/py_dev/satgpt-app
.venv/bin/python demo/record.py --no-llm          # what produced this folder (~45 s wall clock)
# the owner's run with the real agent, same outputs:
OPENAI_API_KEY=... .venv/bin/python demo/record.py
# options: --resolution 60 --n-dates 3 --n-cloudy 1 --min-cloud 0.10 --indices NDVI,NDWI,...
#          --skip-rasters --datacube-resolution 120
```

`.venv` is the 2023-pinned Intel python3.11 environment (requirements-2023-lock.txt); nothing was upgraded.

## What the recorder does

1. Builds a fresh `MapManager` + tools with `modules.chat_utils.make_tools()` and (LLM mode) the same
   `initialize_agent(..., AgentType.OPENAI_FUNCTIONS, ConversationBufferMemory)` as `app.py`; a callback
   handler records every `on_agent_action` / `on_tool_end`. In `--no-llm` mode the four tools are called
   directly with the scripted arguments and the assistant replies are canned.
2. Scripted turns: `stac_search` (Sentinel-2 L2A, bbox [-122.485, 47.5, -122.2, 47.7], 2024-07-01/2024-07-31),
   `view_footprints`, `plot_metadata(eo:cloud_cover)`, `show_datacube`.
   The recorded `show_datacube()` call builds its Panel viewer at 120 m instead of native 10 m
   (`--datacube-resolution`; the viewer itself is a live widget and is not replayed).
3. Loads the SCL band for every date at the export resolution and records the in-bbox cloud fraction
   (classes [8, 9], as `modules.image_processing.mask_clouds`) per item in `metadata.json`.
4. Exports the 4 dates ['2024-07-08', '2024-07-10', '2024-07-13', '2024-07-15']: the 3 least-cloudy by mean `eo:cloud_cover`
   plus 1 partly cloudy date (the least cloudy of those with >= 10 % SCL cloud in the bbox), so the
   cloud-mask toggle has something to mask. Bands blue, green, nir, red, swir16, swir22 + scl via `odc.stac.stac_load`
   (EPSG:3857, 60 m pixels, `groupby="solar_day"`), converted with
   `modules.image_processing.s2_dn_to_reflectance`; indices with `modules.spyndex_utils.get_index_props/compute_index`
   (spyndex ['NDVI', 'NDWI', 'NBRSWIR', 'NDBI', 'NDMI', 'NBR', 'MNDWI', 'EVI']). The rasters folder is emptied before writing.

## Files

- `transcript.json` – turns (user text, tool calls with name/arguments/result/agent log, assistant reply, media kind).
- `items.geojson` – the 12 item footprints + STAC properties (assets dropped except the thumbnail href).
- `metadata.json` – per-item date / cloud cover / in-bbox SCL cloud fraction, recorded dates, raster + mask manifests.
- `rasters/<date>_rgb.png` – RGBA, channel = 1 + 254·clip(reflectance / vmax, 0, 1), alpha 0 = nodata; sidecar JSON has vmax.
- `rasters/<date>_<INDEX>.png` – 8-bit grey, 0 = nodata, 1..255 linear over [vmin, vmax] (0.5th/99.5th
  percentiles); sidecar JSON has bounds (EPSG:3857 and lon/lat), the scale range, p2/p98 and stats.
  8-bit rather than 16-bit because browsers flatten 16-bit PNGs to 8 bits when drawn to a canvas, so the
  replayer could not read the extra precision anyway.
- `rasters/<date>_scl.png` – 8-bit SCL class per pixel (0 = no data); sidecar lists the classes, the cloud
  classes used by the toggle and the class counts.

Total 9.11 MB (9.02 MB of PNGs: 2.31 MB RGB, 0.13 MB SCL masks, the rest indices).

## STAC items (Earth Search v1, collection sentinel-2-l2a, tile MGRS-10TET)

| id | date | eo:cloud_cover % (scene) | SCL cloud % in bbox | exported |
|---|---|---|---|---|
| S2B_10TET_20240703_0_L2A | 2024-07-03 | 15.55 | 4.5 |  |
| S2A_10TET_20240705_0_L2A | 2024-07-05 | 0.00 | 0.0 |  |
| S2A_10TET_20240708_0_L2A | 2024-07-08 | 0.00 | 0.0 | yes |
| S2B_10TET_20240710_0_L2A | 2024-07-10 | 0.00 | 0.0 | yes |
| S2B_10TET_20240713_0_L2A | 2024-07-13 | 0.00 | 0.0 | yes |
| S2A_10TET_20240715_0_L2A | 2024-07-15 | 15.52 | 15.4 | yes |
| S2A_10TET_20240718_0_L2A | 2024-07-18 | 0.14 | 0.0 |  |
| S2B_10TET_20240720_0_L2A | 2024-07-20 | 0.01 | 0.0 |  |
| S2B_10TET_20240723_0_L2A | 2024-07-23 | 4.23 | 0.6 |  |
| S2A_10TET_20240725_0_L2A | 2024-07-25 | 63.64 | 20.4 |  |
| S2A_10TET_20240728_0_L2A | 2024-07-28 | 84.42 | 99.9 |  |
| S2B_10TET_20240730_0_L2A | 2024-07-30 | 96.87 | 92.6 |  |

## Rasters

| date | layer | size |
|---|---|---|
| 2024-07-08 | RGB | 607 KB |
| 2024-07-08 | NDVI | 214 KB |
| 2024-07-08 | NDWI | 205 KB |
| 2024-07-08 | NBRSWIR | 223 KB |
| 2024-07-08 | NDBI | 224 KB |
| 2024-07-08 | NDMI | 224 KB |
| 2024-07-08 | NBR | 235 KB |
| 2024-07-08 | MNDWI | 198 KB |
| 2024-07-08 | EVI | 184 KB |
| 2024-07-10 | RGB | 536 KB |
| 2024-07-10 | NDVI | 205 KB |
| 2024-07-10 | NDWI | 196 KB |
| 2024-07-10 | NBRSWIR | 218 KB |
| 2024-07-10 | NDBI | 205 KB |
| 2024-07-10 | NDMI | 205 KB |
| 2024-07-10 | NBR | 217 KB |
| 2024-07-10 | MNDWI | 197 KB |
| 2024-07-10 | EVI | 168 KB |
| 2024-07-13 | RGB | 611 KB |
| 2024-07-13 | NDVI | 215 KB |
| 2024-07-13 | NDWI | 205 KB |
| 2024-07-13 | NBRSWIR | 222 KB |
| 2024-07-13 | NDBI | 228 KB |
| 2024-07-13 | NDMI | 228 KB |
| 2024-07-13 | NBR | 234 KB |
| 2024-07-13 | MNDWI | 196 KB |
| 2024-07-13 | EVI | 183 KB |
| 2024-07-15 | RGB | 559 KB |
| 2024-07-15 | NDVI | 190 KB |
| 2024-07-15 | NDWI | 185 KB |
| 2024-07-15 | NBRSWIR | 211 KB |
| 2024-07-15 | NDBI | 196 KB |
| 2024-07-15 | NDMI | 197 KB |
| 2024-07-15 | NBR | 204 KB |
| 2024-07-15 | MNDWI | 191 KB |
| 2024-07-15 | EVI | 183 KB |

| date | layer | size | note |
|---|---|---|---|
| 2024-07-08 | SCL mask | 32 KB | 0.0 % cloud |
| 2024-07-10 | SCL mask | 31 KB | 0.0 % cloud |
| 2024-07-13 | SCL mask | 30 KB | 0.0 % cloud |
| 2024-07-15 | SCL mask | 35 KB | 15.4 % cloud |

## Verification (2026-10-15)

- Served with `python3 -m http.server 8766 -d demo` (also the `satgpt-demo` entry in `.claude/launch.json`).
  All page URLs are relative, so it works from any sub-path (e.g. kevinlalli.me/satgpt/).
- In the app's browser pane and in headless Chromium 156 (Playwright 1.63, scratch venv): "Play all" and the
  step menu replay the four turns from the static files; a typed message that matches a recorded step by
  keyword plays it (catching up on earlier steps first), "show me NDWI" also switches the layer, and an
  unmatched message gets the canned reply with the recorded prompts and the repo link; date / layer /
  colormap / stretch / opacity re-render the overlay from the cached PNG in a canvas; the cloud-mask toggle on
  2024-07-15 makes 15.4 % of the overlay transparent (= the SCL cloud fraction); the cloud-cover chart has a
  hover tooltip and selects recorded dates on click. Hosts contacted: only `localhost:8766`,
  `cdnjs.cloudflare.com` (Leaflet 1.9.4, SRI-pinned) and `tile.openstreetmap.org`; no console errors.
  Phone width (375 px) stacks the columns with no horizontal overflow.
- Screenshots in `demo/screenshots/` (not needed for deployment): `satgpt-demo-1024w-zoom150.png` (683 CSS px
  viewport at device scale 1.5 = a 1024-px window at 150 % zoom), `satgpt-demo-1024css-desktop@1.5x.png`
  (two-column layout) and `satgpt-demo-cloudmask-2024-07-15@1.5x.png` (RGB with the mask on).
- The basemap is OpenStreetMap, not CartoDB: basemaps.cartocdn.com now serves "API KEY REQUIRED" tiles without a key.
- Not done: a recording with the real agent (`OPENAI_API_KEY=... .venv/bin/python demo/record.py`); the
  replayer keys its map effects and keyword matching on the recorded tool names, so an LLM transcript drops
  in without page changes.
