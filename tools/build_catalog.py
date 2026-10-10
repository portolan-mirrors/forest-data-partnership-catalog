#!/usr/bin/env python3
"""Generate the STAC catalog under catalog/ from committed metadata.

Inputs (all committed, all small):
- tools/data/tiles_metadata_<year>.json: per collection and tile, the size, Google's MD5,
  pixel grid, bbox, band statistics and thumbnail checksum. Written on the transfer VM by
  tools/extract_tile_metadata.py from the mirrored files.
- tools/data/overviews_<year>.json (optional): the pan-tropical overview COG of each
  collection, written on the VM by tools/describe_overviews.py.
- tools/data/commodities.json: per-commodity wording.

Outputs: catalog/catalog.json, and per collection collection.json, README.md, AGENTS.md
and one item JSON per tile. The root README.md and AGENTS.md are written by hand and not
touched. items.parquet is generated afterwards with `portolan stac-geoparquet` and then
registered with `--register-parquet`.

The output is deterministic: the same inputs give byte-identical files.

Usage:
    python3 tools/build_catalog.py                   # write the STAC
    portolan stac-geoparquet --catalog catalog       # write each items.parquet
    python3 tools/build_catalog.py --register-parquet
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "tools" / "data"
OUT = ROOT / "catalog"

CATALOG_ID = "forest-data-partnership"
PUBLIC_BASE = "https://data.source.coop/portolan-mirrors/forest-data-partnership-catalog"
HUMAN_BASE = "https://source.coop/portolan-mirrors/forest-data-partnership-catalog"
REPO = "https://github.com/portolan-mirrors/forest-data-partnership-catalog"
RELEASE = "2026a"
SOURCE_BUCKET = "gs://earth-engine-public-requester-pays/forestdatapartnership"
PUBLISHER_PAGE = "https://developers.google.com/earth-engine/datasets/publisher/forestdatapartnership"
EE_PAGE = "https://developers.google.com/earth-engine/datasets/catalog/projects_forestdatapartnership_assets_{c}_model_" + RELEASE
# Google publishes these datasets in the Earth Engine STAC catalog too: the canonical upstream STAC.
EE_STAC = ("https://storage.googleapis.com/earthengine-stac/catalog/forestdatapartnership/"
           "projects_forestdatapartnership_assets_{c}_model_" + RELEASE + ".json")
MODEL_README = "https://github.com/google/forest-data-partnership/tree/main/models/model_" + RELEASE
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
ATTRIBUTION = "Produced by Google for the Forest Data Partnership"
COMMODITIES = ["cocoa", "coffee", "palm", "rubber"]
COG_TYPE = "image/tiff; application=geotiff; profile=cloud-optimized"
SWITCH_ZOOM = 9  # the overview draws below this zoom, the tiles from it (portolan-mirror-demos#44)
GSD = 10

# When each year's files were copied, verified and published (UTC).
SYNCED = {"2024": "2026-10-10T17:10:16Z", "2018": "2026-10-10T18:12:15Z"}

PORTOLAN = "https://schemas.portolan-sdi.org/portolan/v0.2.0/schema.json"
EXT = {
    "file": "https://stac-extensions.github.io/file/v2.1.0/schema.json",
    "proj": "https://stac-extensions.github.io/projection/v2.0.0/schema.json",
    "raster": "https://stac-extensions.github.io/raster/v2.0.0/schema.json",
    "render": "https://stac-extensions.github.io/render/v2.0.0/schema.json",
    "item_assets": "https://stac-extensions.github.io/item-assets/v1.0.0/schema.json",
    "processing": "https://stac-extensions.github.io/processing/v1.2.0/schema.json",
}

PROVIDERS = [
    {"name": ATTRIBUTION, "roles": ["producer", "licensor"],
     "url": "https://www.fao.org/in-action/forest-data-partnership"},
    {"name": "CARTO", "roles": ["host", "processor"], "url": "https://carto.com"},
]


def dump(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text.rstrip("\n") + "\n")


def deg(v, pos, neg):
    v = int(round(v))
    return f"{abs(v)}°{pos if v >= 0 else neg}"


def tile_lng_lat(tile):
    _, lng, _, lat = tile.split("_")
    return int(lng), int(lat)


def tile_title(label, year, tile):
    lng, lat = tile_lng_lat(tile)
    return (f"{label} probability {year}, tile {deg(lng, 'E', 'W')}–{deg(lng + 1, 'E', 'W')}, "
            f"{deg(lat, 'N', 'S')}–{deg(lat + 1, 'N', 'S')}")


def renders(c, label, year, with_overview, collection_level):
    zoom = {"minmax_zoom": [SWITCH_ZOOM, 22]} if (with_overview and collection_level) else {}
    base = {"bidx": [1], "colormap_name": "ylgn", "resampling": "average"}
    r = {
        "probability": {"title": f"{label} probability {year} (0 to 1)", "assets": ["data"],
                        **base, "rescale": [[0.0, 1.0]], **zoom},
        f"likely-{c}": {"title": f"Likely {label.lower()} (probability 0.5 to 1)", "assets": ["data"],
                        **base, "rescale": [[0.5, 1.0]], **zoom},
    }
    if with_overview and collection_level:
        r["overview"] = {"title": f"{label} probability {year} (0 to 1), overview below zoom {SWITCH_ZOOM}",
                         "assets": ["overview"], **base, "rescale": [[0.0, 1.0]],
                         "minmax_zoom": [0, SWITCH_ZOOM - 1]}
    return r


def band(cfg, year, stats=None):
    b = {"name": "probability", "data_type": "float32",
         "description": f"Probability that the pixel includes {cfg['subject']} in {year}"}
    if stats is not None:
        b["statistics"] = stats
    return b


def build_item(cid, c, cfg, year, tile, m):
    w, s, e, n = m["bbox"]
    return {
        "type": "Feature",
        "stac_version": "1.1.0",
        "stac_extensions": [PORTOLAN, EXT["file"], EXT["proj"], EXT["raster"], EXT["render"]],
        "id": tile,
        "geometry": {"type": "Polygon", "coordinates": [[[w, s], [w, n], [e, n], [e, s], [w, s]]]},
        "bbox": [w, s, e, n],
        "properties": {
            "title": tile_title(cfg["label"], year, tile),
            "datetime": f"{year}-07-01T00:00:00Z",
            "start_datetime": f"{year}-01-01T00:00:00Z",
            "end_datetime": f"{year}-12-31T23:59:59Z",
            "gsd": GSD,
            "proj:code": "EPSG:4326",
            "proj:bbox": [w, s, e, n],
            "proj:shape": m["shape"],
            "proj:transform": m["transform"],
            "raster:spatial_resolution": m["transform"][0],
            "renders": renders(c, cfg["label"], year, False, False),
            "portolan:render_order": ["probability"],
        },
        "links": [
            {"rel": "root", "href": "../../catalog.json", "type": "application/json"},
            {"rel": "collection", "href": "../collection.json", "type": "application/json"},
            {"rel": "parent", "href": "../collection.json", "type": "application/json"},
            {"rel": "via", "href": f"{SOURCE_BUCKET}/{RELEASE}/{c}/{year}/{tile}.tif".replace(
                "gs://", "https://storage.googleapis.com/"), "type": COG_TYPE,
             "title": "Source file (Google Cloud Storage, requester pays)"},
        ],
        "assets": {
            "data": {
                "href": f"./{tile}.tif", "type": COG_TYPE, "roles": ["data"],
                "title": f"{cfg['label']} probability {year} (COG)",
                "file:size": m["bytes"], "file:checksum": m["file_checksum"],
                "bands": [band(cfg, year, m["statistics"])],
            },
            "thumbnail": {
                "href": f"./{tile}.thumb.jpg", "type": "image/jpeg", "roles": ["thumbnail"],
                "title": f"Thumbnail of tile {tile}",
                "file:size": m["thumbnail"]["bytes"], "file:checksum": m["thumbnail"]["file_checksum"],
            },
        },
        "collection": cid,
    }


def coverage_paragraph(year, n_tiles):
    return (f"This collection mirrors the {n_tiles} one-degree tiles of release {RELEASE} for {year} that touch "
            "the West African cocoa belt: land in Sierra Leone, Liberia, Guinea, Côte d'Ivoire, Ghana, Togo, Benin, "
            "Nigeria, Cameroon, Equatorial Guinea and Gabon south of 10°N, between 15°W and 17°E and between 1°S "
            "and 11°N. The files are copied unchanged from Google's requester-pays bucket, byte for byte, and each "
            "item records Google's MD5 for the file. Each tile is one item with one Cloud-Optimized GeoTIFF of about "
            "11133 by 11133 Float32 pixels in EPSG:4326. The same tiles exist for cocoa, coffee, oil palm and "
            "rubber, with identical item ids, and for each mirrored year.")


def measured_paragraph(tiles):
    means = sorted(m["statistics"]["mean"] for m in tiles.values())
    above = sum(1 for v in means if v >= 0.1)
    return (f"Measured from the tiles' 2783 px overview level (about 40 m): tile means range from {means[0]:.3f} "
            f"to {means[-1]:.3f}, with a median of {means[len(means) // 2]:.3f}, and {above} of {len(means)} tiles "
            "have a mean of 0.1 or more.")


def overview_asset(cfg, year, ov):
    return {
        # Role `overview` only: it is a derived view of the whole collection, not a scene.
        # With `data` it would read as a scene COG at collection level (PORTO-CORE-071).
        "href": f"./{ov['file']}", "type": COG_TYPE, "roles": ["overview"],
        "title": f"{cfg['label']} probability {year}, pan-tropical overview at about 320 m (COG)",
        "description": (
            f"All {ov['source_tiles']} tiles of release {RELEASE} for {year} (24°S to 24°N), not only the tiles "
            "this collection mirrors, in one file at about 320 m: the 347 px level of every source tile as Google "
            "published it (mean-resampled), mosaicked without resampling again. NaN where no tile or no data. "
            f"For maps below zoom {SWITCH_ZOOM} and coarse statistics."),
        "gsd": round(ov["transform"][0] * 111320),
        "proj:code": "EPSG:4326",
        "proj:bbox": ov["bbox"],
        "proj:shape": ov["shape"],
        "proj:transform": ov["transform"],
        "raster:spatial_resolution": ov["transform"][0],
        "bands": [{"name": "probability", "data_type": "float32", "nodata": "nan",
                   "description": f"Probability that the pixel includes {cfg['subject']} in {year}",
                   "statistics": ov["statistics"]}],
        "processing:lineage": ov["lineage"],
        "processing:software": ov["software"],
        "file:size": ov["bytes"], "file:checksum": ov["file_checksum"],
    }


def build_collection(c, cfg, common, year, tiles, ov):
    cid = f"{c}-{year}"
    label = cfg["label"]
    xs = [m["bbox"] for m in tiles.values()]
    bbox = [min(b[0] for b in xs), min(b[1] for b in xs), max(b[2] for b in xs), max(b[3] for b in xs)]
    description = "\n\n".join([
        f"Per-pixel probability, from 0 to 1, that the pixel includes {cfg['subject']} in {year}, at 10 m resolution.",
        cfg["context"], measured_paragraph(tiles), common, coverage_paragraph(year, len(tiles))])
    central = "lng_-2_lat_6" if "lng_-2_lat_6" in tiles else sorted(tiles)[0]
    assets = {
        "thumbnail": {"href": f"./{central}/{central}.thumb.jpg", "type": "image/jpeg", "roles": ["thumbnail"],
                      "title": f"Thumbnail of tile {central}",
                      "file:size": tiles[central]["thumbnail"]["bytes"],
                      "file:checksum": tiles[central]["thumbnail"]["file_checksum"]},
    }
    exts = [PORTOLAN, EXT["file"], EXT["proj"], EXT["raster"], EXT["render"], EXT["item_assets"]]
    if ov:
        assets["overview"] = overview_asset(cfg, year, ov)
        exts.append(EXT["processing"])
    links = [
        {"rel": "root", "href": "../catalog.json", "type": "application/json"},
        {"rel": "parent", "href": "../catalog.json", "type": "application/json"},
        {"rel": "license", "href": LICENSE_URL, "type": "text/html", "title": "CC-BY-4.0"},
        {"rel": "via", "href": EE_PAGE.format(c=c), "type": "text/html",
         "title": f"{label} model {RELEASE} in the Earth Engine data catalog"},
        {"rel": "canonical", "href": EE_STAC.format(c=c), "type": "application/json",
         "title": f"{label} model {RELEASE} in the Earth Engine STAC catalog"},
        {"rel": "describedby", "href": "./README.md", "type": "text/markdown", "title": "Collection README"},
        {"rel": "agents", "href": "./AGENTS.md", "type": "text/markdown", "title": "Collection agent guide"},
    ] + [{"rel": "item", "href": f"./{t}/{t}.json", "type": "application/geo+json",
          "title": tile_title(label, year, t)} for t in sorted(tiles)]
    return cid, {
        "type": "Collection",
        "stac_version": "1.1.0",
        "stac_extensions": exts,
        "id": cid,
        "title": f"{label} probability {year} (Forest Data Partnership model {RELEASE})",
        "description": description,
        "keywords": cfg["keywords"] + ["probability", "West Africa", "Forest Data Partnership", year],
        "license": "CC-BY-4.0",
        "providers": PROVIDERS,
        "extent": {"spatial": {"bbox": [bbox]},
                   "temporal": {"interval": [[f"{year}-01-01T00:00:00Z", f"{year}-12-31T23:59:59Z"]]}},
        "summaries": {"proj:code": ["EPSG:4326"], "gsd": [GSD],
                      "raster:spatial_resolution": [next(iter(tiles.values()))["transform"][0]]},
        "item_assets": {
            "data": {"type": COG_TYPE, "roles": ["data"], "title": f"{label} probability {year} (COG)",
                     "bands": [band(cfg, year)]},
            "thumbnail": {"type": "image/jpeg", "roles": ["thumbnail"]},
        },
        "assets": assets,
        "renders": renders(c, label, year, bool(ov), True),
        "updated": SYNCED[year],
        "links": links,
    }


def collection_readme(cid, coll, n, year, has_overview):
    lines = [f"# {coll['title']}", "", coll["description"], "",
             "## License and attribution", "",
             f"[CC-BY-4.0]({LICENSE_URL}). Attribute as: \"{ATTRIBUTION}.\"", "",
             "## Provenance", "",
             f"- Source: `{SOURCE_BUCKET}/{RELEASE}/{cid.split('-')[0]}/{year}/` (Google Cloud Storage, requester pays).",
             f"- Copied unchanged to Source Cooperative on {SYNCED[year][:10]}. Each item's `file:checksum` is "
             "Google's MD5 for the file, as a multihash.",
             "- Band statistics come from each tile's 2783 px overview level. They are approximate.",
             "", "## Files", "",
             "| File | What it is |", "|---|---|",
             f"| `<tile>/<tile>.tif` | {n} Cloud-Optimized GeoTIFFs, one per one-degree tile |",
             "| `<tile>/<tile>.thumb.jpg` | 347 px preview of each tile, YlGn ramp |",
             "| `<tile>/<tile>.json` | STAC item of each tile |",
             "| `items.parquet` | all items as STAC GeoParquet, for one-request queries |"]
    if has_overview:
        lines.append(f"| `{cid}_overview.tif` | pan-tropical overview at about 320 m, for maps below zoom "
                     f"{SWITCH_ZOOM} |")
    lines += ["", f"Browse: {HUMAN_BASE}/{cid}", ""]
    return "\n".join(lines)


def collection_agents(cid, coll, n, year):
    c = cid.split("-")[0]
    return "\n".join([
        f"# {coll['title']}: agent guide", "",
        "Every claim here is quoted from the source documentation or measured from the files.", "",
        "## What the data is", "",
        f"- One band, `probability`, Float32 from 0 to 1, in EPSG:4326, about 10 m per pixel. {n} items, one "
        "per one-degree tile. Item ids are `lng_<west>_lat_<south>`.",
        "- Values are model probabilities, not observations. Pick a threshold for your purpose; the collection "
        "renders offer 0 to 1 and 0.5 to 1.",
        f"- The same item ids exist in the other commodity collections for {year}, and in `{c}-<other year>` "
        "collections, so tiles can be compared across commodities and years.", "",
        "## How to read it", "",
        "Find tiles with one request, from the STAC GeoParquet mirror:", "",
        "```sql",
        "SELECT id, bbox, assets.data.href",
        f"FROM read_parquet('{PUBLIC_BASE}/{cid}/items.parquet')",
        "WHERE bbox.xmin < -1 AND bbox.xmax > -2 AND bbox.ymin < 7 AND bbox.ymax > 6;",
        "```", "",
        "Read a tile window with rasterio (range requests, no download of the whole file):", "",
        "```python",
        "import rasterio",
        f"url = '{PUBLIC_BASE}/{cid}/lng_-2_lat_6/lng_-2_lat_6.tif'",
        "with rasterio.open(url) as src:",
        "    prob = src.read(1, out_shape=(1024, 1024))  # reads an internal overview",
        "print((prob >= 0.5).mean())",
        "```", "",
        "## Limits", "",
        f"- Coverage is the West African cocoa belt only. The full release covers 24°S to 24°N: see {PUBLISHER_PAGE}.",
        f"- Model method and known limitations: {MODEL_README}",
        "- The source COGs have no embedded band statistics; the items carry approximate ones.", ""])


def register_parquet():
    for cdir in sorted(p for p in OUT.iterdir() if (p / "collection.json").exists()):
        pq = cdir / "items.parquet"
        doc = json.loads((cdir / "collection.json").read_text())
        if not pq.exists():
            raise SystemExit(f"{pq} missing: run portolan stac-geoparquet --catalog catalog first")
        h = hashlib.sha256(pq.read_bytes()).hexdigest()
        doc["links"] = [link for link in doc["links"] if link.get("href") != "./items.parquet"]
        doc["assets"]["geoparquet-items"] = {
            "href": "./items.parquet", "type": "application/vnd.apache.parquet",
            "title": "STAC items as GeoParquet", "roles": ["collection-mirror"],
            "file:size": pq.stat().st_size, "file:checksum": "1220" + h}
        doc["assets"] = dict(sorted(doc["assets"].items()))
        dump(cdir / "collection.json", doc)
        # portolan stac-geoparquet also writes versions.json, the state file of `portolan push`.
        # This catalog publishes with tools/publish.py, so that file is not part of it.
        (cdir / "versions.json").unlink(missing_ok=True)
        print(f"registered {pq.relative_to(ROOT)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--register-parquet", action="store_true",
                    help="register each collection's items.parquet as a collection-mirror asset")
    a = ap.parse_args()
    if a.register_parquet:
        register_parquet()
        return

    cfg = json.loads((DATA / "commodities.json").read_text())
    years = sorted(p.stem.split("_")[-1] for p in DATA.glob("tiles_metadata_*.json"))
    children = []
    for year in years:
        meta = json.loads((DATA / f"tiles_metadata_{year}.json").read_text())
        ovp = DATA / f"overviews_{year}.json"
        overviews = json.loads(ovp.read_text()) if ovp.exists() else {}
        for c in COMMODITIES:
            tiles = meta[f"{c}-{year}"]
            cid, coll = build_collection(c, cfg["commodities"][c], cfg["common_paragraph"], year, tiles,
                                         overviews.get(f"{c}-{year}"))
            cdir = OUT / cid
            # Rebuild item folders from scratch so a removed tile leaves nothing behind.
            for d in cdir.glob("lng_*"):
                shutil.rmtree(d)
            for tile, m in sorted(tiles.items()):
                dump(cdir / tile / f"{tile}.json", build_item(cid, c, cfg["commodities"][c], year, tile, m))
            dump(cdir / "collection.json", coll)
            write_text(cdir / "README.md", collection_readme(cid, coll, len(tiles), year, cid in overviews))
            write_text(cdir / "AGENTS.md", collection_agents(cid, coll, len(tiles), year))
            children.append((cid, coll["title"]))
            print(f"{cid}: {len(tiles)} items{', overview' if cid in overviews else ''}")

    n_items = sum(1 for _ in OUT.glob("*/lng_*/*.json"))
    catalog = {
        "type": "Catalog",
        "stac_version": "1.1.0",
        "stac_extensions": [PORTOLAN],
        "id": CATALOG_ID,
        "title": "Forest Data Partnership commodity maps (Source Cooperative mirror)",
        "description": (
            "Per-pixel probability that land is planted with cocoa, coffee, oil palm or rubber, at 10 m, from the "
            f"Forest Data Partnership community model release {RELEASE}, produced by Google. This mirror holds "
            f"the West African cocoa belt for {', '.join(years)}: one collection per commodity and year, "
            f"{n_items} Cloud-Optimized GeoTIFFs copied unchanged from Google's requester-pays bucket and served "
            "over plain HTTPS, with pan-tropical overviews for low zoom. Attribution: "
            f"\"{ATTRIBUTION}.\""),
        "links": [
            {"rel": "root", "href": "./catalog.json", "type": "application/json", "title": "Catalog root"},
            {"rel": "self", "href": f"{PUBLIC_BASE}/catalog.json", "type": "application/json",
             "title": "This catalog, as published"},
            {"rel": "describedby", "href": "./README.md", "type": "text/markdown", "title": "Catalog README"},
            {"rel": "agents", "href": "./AGENTS.md", "type": "text/markdown", "title": "Catalog agent guide"},
            {"rel": "license", "href": LICENSE_URL, "type": "text/html", "title": "CC-BY-4.0"},
            {"rel": "via", "href": PUBLISHER_PAGE, "type": "text/html",
             "title": "Forest Data Partnership in the Earth Engine data catalog"},
            {"rel": "vcs", "href": REPO, "title": "Source repository"},
            {"rel": "issues", "href": f"{REPO}/issues", "title": "Issue tracker"},
        ] + [{"rel": "child", "href": f"./{cid}/collection.json", "type": "application/json", "title": t}
             for cid, t in children],
        "updated": max(SYNCED[y] for y in years),
    }
    dump(OUT / "catalog.json", catalog)
    print(f"catalog.json: {len(children)} collections, {n_items} items")


if __name__ == "__main__":
    main()
