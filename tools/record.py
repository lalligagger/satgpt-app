#!/usr/bin/env python
"""Record one SatGPT conversation, plus the imagery it looks at, for the static demo replayer.

Runs on the machine where the live app works (the 2023-pinned .venv, Intel build):

    OPENAI_API_KEY=... .venv/bin/python demo/record.py            # real LangChain agent, as app.py builds it
    .venv/bin/python demo/record.py --no-llm                       # same tools, called directly, no key

Outputs (under --out, default demo/data/):
    transcript.json      each turn: user text, tool calls (name, arguments, text result), assistant reply
    items.geojson        STAC item footprints + properties
    metadata.json        per-item date / eo:cloud_cover, the recorded dates and the raster manifest
    rasters/<date>_rgb.png (+ .json)         RGBA true colour, linear 0..rgb_vmax reflectance
    rasters/<date>_<INDEX>.png (+ .json)     8-bit single band: 0 = nodata, 1..255 linear over [vmin, vmax]
    rasters/<date>_scl.png (+ .json)         Sentinel-2 scene classification (SCL) classes, for the cloud-mask toggle

Nothing here needs a server; the replayer (demo/index.html) only reads these files.
"""
import argparse
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))  # so `modules.*` imports resolve when run from anywhere

import numpy as np
import pandas as pd
import pystac
from PIL import Image

pd.options.plotting.backend = "holoviews"  # app.py sets this; plot_metadata relies on it

from modules.chat_utils import make_tools  # noqa: E402
from modules.image_processing import s2_dn_to_reflectance  # noqa: E402
from modules.spyndex_utils import BAND_MAPPING, compute_index, get_index_props, get_indices  # noqa: E402

# ---------------------------------------------------------------------------------------------
# The scripted conversation. In --no-llm mode the tool is called with exactly these arguments;
# with the agent, the prompt is sent and whatever the agent decides to call is what gets recorded.
# ---------------------------------------------------------------------------------------------
BBOX = {"west": -122.485, "south": 47.5, "east": -122.2, "north": 47.7}
DTIME = "2024-07-01/2024-07-31"
COLLECTION = "sentinel-2-l2a"

SCRIPT = [
    {
        "user": (
            "Search for Sentinel-2 (sentinel-2-l2a) images over Seattle: bounding box "
            f"west={BBOX['west']}, south={BBOX['south']}, east={BBOX['east']}, north={BBOX['north']}, "
            f"for the date range {DTIME}."
        ),
        "tool": "stac_search",
        "args": {**BBOX, "dtime": DTIME, "collection": COLLECTION},
        "canned": "I found {count} Sentinel-2 L2A scenes over Seattle for July 2024.",
    },
    {
        "user": "Show me the footprints of those scenes on a map.",
        "tool": "view_footprints",
        "args": {},
        "canned": "The footprint map is loaded in the chat.",
    },
    {
        "user": "Plot the cloud cover (eo:cloud_cover) of those scenes over time.",
        "tool": "plot_metadata",
        "args": {"field": "eo:cloud_cover"},
        "canned": "Plotted!",
    },
    {
        "user": "Great, now show me the images.",
        "tool": "show_datacube",
        "args": {},
        "canned": "Done!",
    },
]

DEFAULT_INDICES = ["NDVI", "NDWI", "NBRSWIR", "NDBI", "NDMI", "NBR", "MNDWI", "EVI"]
RGB_BANDS = ["red", "green", "blue"]
SCL_BAND = BAND_MAPPING[COLLECTION]["999"]  # "scl"
CLOUD_CLASSES = [8, 9]  # cloud medium / high probability, as in modules.image_processing.mask_clouds
SCL_CLASSES = {0: "no data", 1: "saturated or defective", 2: "dark area pixels", 3: "cloud shadows", 4: "vegetation",
               5: "not vegetated", 6: "water", 7: "unclassified", 8: "cloud medium probability",
               9: "cloud high probability", 10: "thin cirrus", 11: "snow"}


# ---------------------------------------------------------------------------------------------
# Agent (same construction as app.py's create_app, minus the Panel chat box)
# ---------------------------------------------------------------------------------------------
def build_agent(tools, recorder):
    from langchain.agents import AgentType, initialize_agent
    from langchain.chat_models import ChatOpenAI
    from langchain.memory import ConversationBufferMemory
    from langchain.prompts import MessagesPlaceholder

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit("OPENAI_API_KEY is not set; use --no-llm to record without an LLM.")
    model = os.environ.get("SATGPT_MODEL", "gpt-4o-mini")

    llm = ChatOpenAI(temperature=0, model=model, openai_api_key=api_key)
    memory = ConversationBufferMemory(memory_key="memory", return_messages=True)
    agent = initialize_agent(
        tools,
        llm,
        agent=AgentType.OPENAI_FUNCTIONS,
        verbose=True,
        agent_kwargs={"extra_prompt_messages": [MessagesPlaceholder(variable_name="memory")]},
        memory=memory,
        callbacks=[recorder],
    )
    return agent, model


class ToolRecorder:
    """LangChain callback handler that captures each tool call the agent makes."""

    def __init__(self):
        from langchain.callbacks.base import BaseCallbackHandler

        class _Handler(BaseCallbackHandler):
            def __init__(h):
                h.calls = []

            def on_agent_action(h, action, **kwargs):
                h.calls.append({
                    "name": action.tool,
                    "arguments": _jsonable(action.tool_input),
                    "result": None,
                    "log": (action.log or "").strip(),
                })

            def on_tool_end(h, output, **kwargs):
                for c in reversed(h.calls):
                    if c["result"] is None:
                        c["result"] = str(output)
                        break

            def on_tool_error(h, error, **kwargs):
                for c in reversed(h.calls):
                    if c["result"] is None:
                        c["result"] = f"ERROR {type(error).__name__}: {error}"
                        break

        self.handler = _Handler()

    def drain(self):
        calls, self.handler.calls = self.handler.calls, []
        return calls


def _jsonable(obj):
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


def describe_media(media):
    if media is None:
        return None
    name = type(media).__name__
    mod = type(media).__module__
    if "Folium" in name:
        return {"kind": "footprint_map", "python_type": f"{mod}.{name}"}
    if name == "Row":
        return {"kind": "datacube_viewer", "python_type": f"{mod}.{name}"}
    return {"kind": "plot", "python_type": f"{mod}.{name}"}


# ---------------------------------------------------------------------------------------------
# Conversation
# ---------------------------------------------------------------------------------------------
def run_conversation(map_mgr, tools, use_llm, datacube_resolution):
    tools_by_name = {t.name: t for t in tools}

    if datacube_resolution:
        # show_datacube() loads every band of every item at native 10 m to build its viewer; that output
        # is a Panel widget we cannot replay anyway, so cap the resolution here to keep the recording light.
        orig_load = map_mgr._load_data

        def light_load(time, resolution):
            return orig_load(time, resolution if resolution is not None else datacube_resolution)

        map_mgr._load_data = light_load

    turns = []
    agent = model = None
    recorder = None
    if use_llm:
        recorder = ToolRecorder()
        agent, model = build_agent(tools, recorder.handler)

    for step in SCRIPT:
        t0 = time.time()
        print(f"\n>>> {step['user']}")
        if use_llm:
            try:
                reply = agent.run(input=step["user"])
            except Exception as exc:  # mirror app.py: surface the failure as the reply
                reply = f"Sorry, that step failed: {type(exc).__name__}: {str(exc)[:300]}"
            calls = recorder.drain()
        else:
            tool = tools_by_name[step["tool"]]
            try:
                out = tool.run(step["args"]) if step["args"] else tool.run({})
                result = str(out)
            except Exception as exc:
                result = f"ERROR {type(exc).__name__}: {exc}"
            calls = [{"name": step["tool"], "arguments": step["args"], "result": result, "log": ""}]
            fmt = {}
            if step["tool"] == "stac_search" and isinstance(out, dict):
                fmt = {"count": out.get("count")}
            reply = step["canned"].format(**fmt) if fmt else step["canned"]
        media = describe_media(map_mgr.media)
        map_mgr.media = None
        print(f"<<< {reply}")
        turns.append({
            "user": step["user"],
            "tool_calls": calls,
            "assistant": reply,
            "media": media,
            "seconds": round(time.time() - t0, 2),
        })
    return turns, model


# ---------------------------------------------------------------------------------------------
# Imagery export
# ---------------------------------------------------------------------------------------------
def pick_dates(items, n, cloud_fractions, n_cloudy, min_cloud):
    """The n least-cloudy acquisition dates (mean eo:cloud_cover across the items of each date), plus n_cloudy
    partly cloudy dates: of the dates whose in-bbox SCL cloud fraction is >= min_cloud, the least cloudy ones,
    so the cloud-mask toggle has something to mask."""
    by_date = {}
    for it in items:
        d = it.properties["datetime"][:10]
        by_date.setdefault(d, []).append(float(it.properties.get("eo:cloud_cover", 100.0)))
    ranked = sorted(by_date, key=lambda d: (float(np.mean(by_date[d])), d))
    chosen = ranked[:n]
    cloudy = sorted((d for d in by_date if d not in chosen and cloud_fractions.get(d, 0) >= min_cloud),
                    key=lambda d: (cloud_fractions[d], d))
    return sorted(chosen + cloudy[:n_cloudy])


def scl_cloud_fractions(items, bbox, resolution):
    """Per date: fraction (0..1) of bbox pixels the SCL calls cloud (classes CLOUD_CLASSES)."""
    from odc.stac import stac_load

    out = {}
    for it in items:
        d = it.properties["datetime"][:10]
        if d in out:
            continue
        same_day = [i for i in items if i.properties["datetime"][:10] == d]
        ds = stac_load(same_day, bbox=bbox, bands=[SCL_BAND], resolution=resolution, crs="EPSG:3857",
                       groupby="solar_day", chunks={}).compute()
        scl = ds[SCL_BAND].isel(time=0).values
        out[d] = float(np.isin(scl, CLOUD_CLASSES).mean())
    return out


def load_date(items, bbox, resolution, bands):
    """Load one date's bands for the bbox in EPSG:3857 at `resolution` metres, as reflectance (0..1)."""
    from odc.stac import stac_load

    raw = stac_load(
        items,
        bbox=bbox,
        bands=bands,
        resolution=resolution,
        crs="EPSG:3857",
        groupby="solar_day",
        chunks={},
    ).to_array(dim="band")
    raw = raw.isel(time=0).compute()
    scl = raw.sel(band=SCL_BAND).values.astype("uint8") if SCL_BAND in bands else None
    refl = raw.sel(band=[b for b in bands if b != SCL_BAND])
    nodata = (refl == 0).all(dim="band").values
    data = s2_dn_to_reflectance(refl.astype("float32"))
    return data, nodata, scl


def geobox_bounds(data):
    from pyproj import Transformer

    gb = data.odc.geobox
    bb = gb.boundingbox
    left, bottom, right, top = bb.left, bb.bottom, bb.right, bb.top
    tr = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
    w, s = tr.transform(left, bottom)
    e, n = tr.transform(right, top)
    return {
        "crs": "EPSG:3857",
        "bounds_3857": [float(left), float(bottom), float(right), float(top)],
        "bounds_lonlat": [float(w), float(s), float(e), float(n)],
        "resolution_m": float(abs(gb.resolution.x)),
    }


def write_rgb(data, nodata, date, out_dir, bounds):
    rgb = data.sel(band=RGB_BANDS).values  # (3, y, x) reflectance
    valid = ~nodata
    vmax = float(np.nanpercentile(rgb[:, valid], 99.5)) if valid.any() else 1.0
    vmax = max(vmax, 1e-3)
    scaled = np.clip(rgb / vmax, 0, 1)
    u8 = np.round(1 + scaled * 254).astype("uint8")
    alpha = np.where(valid, 255, 0).astype("uint8")
    rgba = np.concatenate([u8, alpha[None]], axis=0).transpose(1, 2, 0)
    png = out_dir / f"{date}_rgb.png"
    Image.fromarray(np.ascontiguousarray(rgba), mode="RGBA").save(png, optimize=True)
    p2, p98 = (np.nanpercentile(rgb[:, valid], [2, 98]) if valid.any() else (0.0, 1.0))
    side = {
        "date": date,
        "kind": "rgb",
        "bands": RGB_BANDS,
        "units": "surface reflectance (0..1)",
        "width": int(rgba.shape[1]),
        "height": int(rgba.shape[0]),
        "encoding": "RGBA; channel = 1 + 254 * clip(reflectance / vmax, 0, 1); alpha 0 = nodata",
        "scale": {"vmin": 0.0, "vmax": vmax},
        "percentiles": {"p2": float(p2), "p98": float(p98)},
        **bounds,
    }
    png.with_suffix(".json").write_text(json.dumps(side, indent=1))
    return png, side


def write_index(data, nodata, date, index, out_dir, bounds):
    props = get_index_props(index, COLLECTION)
    sel = data.sel(band=props["stac_bands"])
    with np.errstate(divide="ignore", invalid="ignore"):
        arr = np.asarray(compute_index(sel, props).values, dtype="float32")
    if arr.ndim == 3:
        arr = arr[0]
    arr[nodata] = np.nan
    arr[~np.isfinite(arr)] = np.nan
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        raise RuntimeError(f"{index} {date}: no finite values")
    vmin, vmax = (float(v) for v in np.percentile(finite, [0.5, 99.5]))
    if vmax <= vmin:
        vmin, vmax = float(finite.min()), float(finite.max() + 1e-6)
    p2, p98 = (float(v) for v in np.percentile(finite, [2, 98]))
    enc = np.zeros(arr.shape, dtype="uint8")
    ok = np.isfinite(arr)
    enc[ok] = np.round(1 + 254 * np.clip((arr[ok] - vmin) / (vmax - vmin), 0, 1)).astype("uint8")
    png = out_dir / f"{date}_{index}.png"
    Image.fromarray(enc, mode="L").save(png, optimize=True)
    side = {
        "date": date,
        "kind": "index",
        "index": index,
        "long_name": props["long_name"],
        "formula": props["formula"],
        "application_domain": props["application_domain"],
        "bands": props["stac_bands"],
        "reference": props["reference"],
        "width": int(enc.shape[1]),
        "height": int(enc.shape[0]),
        "nodata": 0,
        "encoding": "8-bit; value = vmin + (png - 1) / 254 * (vmax - vmin); 0 = nodata",
        "scale": {"vmin": vmin, "vmax": vmax},
        "percentiles": {"p2": p2, "p98": p98},
        "stats": {
            "min": float(finite.min()), "max": float(finite.max()),
            "mean": float(finite.mean()), "valid_fraction": float(ok.mean()),
        },
        **bounds,
    }
    png.with_suffix(".json").write_text(json.dumps(side, indent=1))
    return png, side


def write_scl(scl, nodata, date, out_dir, bounds):
    scl = scl.copy()
    scl[nodata] = 0
    png = out_dir / f"{date}_scl.png"
    Image.fromarray(scl, mode="L").save(png, optimize=True)
    counts = {str(k): int((scl == k).sum()) for k in SCL_CLASSES}
    side = {
        "date": date,
        "kind": "scl",
        "band": SCL_BAND,
        "width": int(scl.shape[1]),
        "height": int(scl.shape[0]),
        "encoding": "8-bit; pixel value = SCL class (see classes); 0 = no data",
        "classes": SCL_CLASSES,
        "cloud_classes": CLOUD_CLASSES,
        "cloud_fraction": float(np.isin(scl, CLOUD_CLASSES).mean()),
        "class_counts": counts,
        **bounds,
    }
    png.with_suffix(".json").write_text(json.dumps(side, indent=1))
    return png, side


def export_imagery(map_mgr, out, dates_n, resolution, indices, n_cloudy, min_cloud):
    items = pystac.ItemCollection(map_mgr.items_dict["features"])
    bbox = tuple(map(float, map_mgr.bbox.split(",")))
    collection = map_mgr.collection
    if collection != COLLECTION:
        raise SystemExit(f"recorded collection is {collection}; this exporter only knows {COLLECTION}")
    supported = set(get_indices(collection))
    unknown = [i for i in indices if i not in supported]
    if unknown:
        raise SystemExit(f"indices not supported for {collection}: {unknown}")

    t0 = time.time()
    cloud_fractions = scl_cloud_fractions(items, bbox, resolution)
    print(f"\nSCL cloud fraction in bbox ({time.time() - t0:.0f}s): " +
          ", ".join(f"{d} {f * 100:.1f}%" for d, f in sorted(cloud_fractions.items())))
    dates = pick_dates(items, dates_n, cloud_fractions, n_cloudy, min_cloud)
    bands = sorted({b for i in indices for b in get_index_props(i, collection)["stac_bands"]} | set(RGB_BANDS))
    print(f"exporting {dates} at {resolution} m, bands {bands} + {SCL_BAND}, indices {indices}")

    raster_dir = out / "rasters"
    raster_dir.mkdir(parents=True, exist_ok=True)
    for stale in list(raster_dir.glob("*.png")) + list(raster_dir.glob("*.json")):
        stale.unlink()  # the manifest below is the only index of this folder; drop leftovers from earlier runs
    manifest, masks = [], []
    for date in dates:
        date_items = [it for it in items if it.properties["datetime"][:10] == date]
        t0 = time.time()
        data, nodata, scl = load_date(date_items, bbox, resolution, bands + [SCL_BAND])
        bounds = geobox_bounds(data)
        print(f"  {date}: loaded {data.sizes['x']}x{data.sizes['y']} px in {time.time() - t0:.1f}s, "
              f"nodata {nodata.mean() * 100:.1f}%, cloud {cloud_fractions[date] * 100:.1f}%")
        png, side = write_scl(scl, nodata, date, raster_dir, bounds)
        masks.append({"date": date, "png": f"rasters/{png.name}", "json": f"rasters/{png.stem}.json",
                      "bytes": png.stat().st_size, "cloud_fraction": side["cloud_fraction"]})
        png, side = write_rgb(data, nodata, date, raster_dir, bounds)
        manifest.append({"date": date, "layer": "RGB", "png": f"rasters/{png.name}",
                         "json": f"rasters/{png.stem}.json", "bytes": png.stat().st_size,
                         "item_ids": [it.id for it in date_items]})
        for index in indices:
            png, side = write_index(data, nodata, date, index, raster_dir, bounds)
            manifest.append({"date": date, "layer": index, "png": f"rasters/{png.name}",
                             "json": f"rasters/{png.stem}.json", "bytes": png.stat().st_size,
                             "item_ids": [it.id for it in date_items]})
        print(f"  {date}: wrote {2 + len(indices)} rasters")
    return dates, manifest, masks, bands, cloud_fractions


# ---------------------------------------------------------------------------------------------
def slim_items(items_dict):
    """Footprints + properties; drop the per-asset blobs (hrefs, raster bands) to keep the file small."""
    feats = []
    for f in items_dict["features"]:
        thumb = (f.get("assets", {}).get("thumbnail") or {}).get("href")
        feats.append({
            "type": "Feature",
            "id": f["id"],
            "bbox": f.get("bbox"),
            "geometry": f["geometry"],
            "properties": {**f["properties"], "id": f["id"], "collection": f.get("collection"),
                           "thumbnail": thumb},
        })
    return {"type": "FeatureCollection", "features": feats}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-llm", action="store_true", help="call the tools directly with the scripted arguments")
    ap.add_argument("--out", default=str(HERE / "data"), help="output folder (default demo/data)")
    ap.add_argument("--resolution", type=float, default=60.0, help="export pixel size in metres (EPSG:3857)")
    ap.add_argument("--n-dates", type=int, default=3, help="how many least-cloudy dates to export")
    ap.add_argument("--indices", default=",".join(DEFAULT_INDICES), help="comma-separated spyndex short names")
    ap.add_argument("--n-cloudy", type=int, default=1,
                    help="how many partly cloudy dates to add for the cloud-mask toggle (least cloudy above --min-cloud)")
    ap.add_argument("--min-cloud", type=float, default=0.10,
                    help="SCL cloud fraction (0..1) inside the bbox a date needs to count as partly cloudy")
    ap.add_argument("--skip-rasters", action="store_true", help="only record the conversation")
    ap.add_argument("--datacube-resolution", type=float, default=120.0,
                    help="pixel size used when the recorded show_datacube() call loads its viewer "
                         "(0 = native, as the live app does; the viewer itself is not replayed)")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    indices = [i.strip() for i in args.indices.split(",") if i.strip()]
    started = dt.datetime.now(dt.timezone.utc)

    map_mgr, tools = make_tools()
    turns, model = run_conversation(map_mgr, tools, use_llm=not args.no_llm,
                                    datacube_resolution=args.datacube_resolution or None)

    if not map_mgr.items_dict:
        raise SystemExit("the conversation produced no STAC items; nothing to export")

    (out / "items.geojson").write_text(json.dumps(slim_items(map_mgr.items_dict)))

    items = pystac.ItemCollection(map_mgr.items_dict["features"])
    per_item = [{
        "id": it.id,
        "date": it.properties["datetime"][:10],
        "datetime": it.properties["datetime"],
        "eo:cloud_cover": it.properties.get("eo:cloud_cover"),
        "s2:nodata_pixel_percentage": it.properties.get("s2:nodata_pixel_percentage"),
        "platform": it.properties.get("platform"),
        "grid:code": it.properties.get("grid:code"),
    } for it in items]
    per_item.sort(key=lambda r: r["datetime"])

    dates, manifest, masks, bands, cloud_fractions = ([], [], [], [], {})
    if not args.skip_rasters:
        dates, manifest, masks, bands, cloud_fractions = export_imagery(
            map_mgr, out, args.n_dates, args.resolution, indices, args.n_cloudy, args.min_cloud)
    for row in per_item:
        row["scl_cloud_fraction_bbox"] = cloud_fractions.get(row["date"])

    meta = {
        "recorded_at": started.isoformat(timespec="seconds"),
        "mode": "no-llm" if args.no_llm else "llm",
        "model": model,
        "collection": map_mgr.collection,
        "stac_url": map_mgr.stac_url,
        "bbox": [float(v) for v in map_mgr.bbox.split(",")],
        "datetime": DTIME,
        "items": per_item,
        "recorded_dates": dates,
        "indices": indices if not args.skip_rasters else [],
        "bands_loaded": bands,
        "export_resolution_m": args.resolution,
        "cloud_mask": {"band": SCL_BAND, "cloud_classes": CLOUD_CLASSES,
                       "source": "modules.image_processing.mask_clouds (SCL 8 | 9)"},
        "rasters": manifest,
        "masks": masks,
    }
    (out / "metadata.json").write_text(json.dumps(meta, indent=1))
    (out / "transcript.json").write_text(json.dumps({
        "recorded_at": meta["recorded_at"],
        "mode": meta["mode"],
        "model": model,
        "note": ("Replies are canned: the tools were called directly, without an LLM."
                 if args.no_llm else f"Replies and tool calls are the agent's own ({model})."),
        "tools": [{"name": t.name, "description": t.description} for t in tools],
        "turns": turns,
    }, indent=1))

    total = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(f"\nwrote {out}: {len(turns)} turns, {len(per_item)} items, {len(manifest) + len(masks)} rasters, "
          f"{total / 1e6:.2f} MB total")


if __name__ == "__main__":
    main()
