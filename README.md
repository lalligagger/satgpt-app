# SatGPT (app)

**Live demo:** <https://kevinlalli.me/satgpt-app/> — a recorded SatGPT session you can replay and poke at
(switch spectral index, date, colormap, stretch and cloud mask on real Sentinel-2 imagery). It is static:
no server, no model, no keys. The chat answers canned replies.

SatGPT is an experiment in using a large language model to retrieve and look at satellite imagery in
natural language. This repo is the LangChain + Panel web app from mid-2023; the earlier shell-gpt CLI is at
[lalligagger/satgpt](https://github.com/lalligagger/satgpt).

https://github.com/lalligagger/satgpt-app/assets/11700267/8675bdc5-ca40-418e-98ce-724ec06ad05a

## What it does

Ask for imagery over a place and time, and the agent calls four tools in turn:

1. `stac_search` — queries [Element84 Earth Search v1](https://earth-search.aws.element84.com/v1/) for
   Sentinel-2 L2A (or Landsat Collection 2 L2) scenes over a bounding box and date range.
2. `view_footprints` — draws the scene footprints on a map.
3. `plot_metadata` — plots any STAC field over time, e.g. `eo:cloud_cover`.
4. `show_datacube` — loads the scenes lazily with [odc-stac](https://github.com/opendatacube/odc-stac)
   and opens a viewer: RGB or any [spyndex](https://github.com/awesome-spectral-indices/spyndex) index the
   collection supports, date picker, percentile stretch, colormap, cloud mask.

Built on the OpenAI chat API (function calling), [LangChain](https://python.langchain.com/) 0.0.x,
[STAC](https://stacspec.org/) and [Panel](https://panel.holoviz.org/).

## Status (2026-10)

The code is from June 2023 and is kept runnable on its original library generation rather than ported.
On 2026-10-15 it was revived on an Apple-silicon Mac, with these changes:

- `requirements-2023-lock.txt` pins 2023 releases of everything (reconstructed; the original lockfile was
  never committed). The loose `requirements.txt` no longer resolves on current PyPI.
- The retired `gpt-3.5-turbo-0613` became the `SATGPT_MODEL` environment variable (default `gpt-4o-mini`;
  any chat model with function calling works).
- The search tool takes four numeric bounds (`west, south, east, north`) instead of one free-text bbox,
  which newer models truncated.
- State is per browser session (one agent, memory and map manager per tab) instead of process-global.
- Tool and model errors are shown in the chat instead of crashing the callback.
- Landsat imagery is refused with a clear message unless `AWS_REQUEST_PAYER=requester` is set, because
  the `usgs-landsat` bucket is requester-pays. Sentinel-2 is public.
- Spectral indices load into memory before the percentile stretch (xarray's `quantile` needs one chunk).

Running it fully in the browser with Pyodide was explored and set aside: the imagery pipeline (dask,
odc-stac, rasterio reading COGs) cannot run in WebAssembly. Hence the recorded demo below.

## Run it locally

Requirements: Python 3.11 (on Apple silicon the pins need an Intel build under Rosetta, because recent
numba, llvmlite and cryptography dropped Intel macOS wheels and the 2023 pins predate arm64 wheels for some
packages; a Linux x86_64 machine is simpler), an OpenAI API key.

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements-2023-lock.txt
export OPENAI_API_KEY=...        # never commit this
./run_local.sh                   # http://localhost:5006/app, autoreloads on edits
./run_local.sh --tunnel          # also prints a public https://*.trycloudflare.com URL
```

Then ask, in order: "Find Sentinel-2 images over Seattle from July 2024", "Show the footprints on a map",
"Plot cloud cover", "Show the images". `SATGPT_MODEL` picks the model; `AWS_REQUEST_PAYER=requester` with
AWS credentials enables Landsat imagery (you pay S3 egress).

The original Codespaces instructions still apply in spirit (`panel serve app.py
--allow-websocket-origin=<host>`), but the 2023 devcontainer is gone; use the venv above.

## The recorded demo

The live demo at <https://kevinlalli.me/satgpt-app/> is a static replay served from this repo's
[`gh-pages` branch](https://github.com/lalligagger/satgpt-app/tree/gh-pages), kept off `main` so this
branch stays the runnable app. That branch's `tools/record.py` runs one scripted conversation through
this app (or `--no-llm` to call the tools directly) and exports the transcript, footprints, metadata and
per-index rasters that the page replays; its README says how.

## Layout

| Path | What |
|---|---|
| `app.py` | Panel app: chat box, agent, per-session wiring |
| `modules/chat_utils.py` | `MapManager` (the four tools) and the viewer |
| `modules/datacube_utils.py`, `image_processing.py`, `spyndex_utils.py`, `cmap_utils.py` | imagery, indices, colormaps |
| `requirements-2023-lock.txt` | the pins that work |
| `run_local.sh` | serve locally, optional cloudflared quick tunnel |
