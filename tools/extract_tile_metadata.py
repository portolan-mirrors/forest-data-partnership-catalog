#!/usr/bin/env python3
"""Extract per-tile metadata and thumbnails from the mirrored COGs.

Runs where the tiles are on local disk (the transfer VM), once per batch of tiles.
It reads each tile, never modifies it, and writes:

- `tiles_metadata.json`: per collection and tile, the file size, Google's MD5,
  the pixel grid, the bounding box, and band statistics from overview 1
  (2783 px, about 40 m). This file is committed, so `tools/build_catalog.py`
  rebuilds the STAC without the 438 GiB of data.
- `<publish>/<collection>/<tile>/<tile>.thumb.jpg`: a 347 px JPEG of the tile's
  coarsest overview, coloured with the YlGn ramp the collection renders use.

Usage (on the VM):
    python3 tools/extract_tile_metadata.py --staging /data/staging \
        --md5 /data/work/src_md5.tsv --publish /data/publish --out tiles_metadata.json

`--md5` is the TSV the transfer script wrote: `<collection>/<tile>/<tile>.tif`,
size, base64 MD5, as Google Cloud Storage reports them. Needs gdalinfo,
gdal_translate and gdaldem on PATH (GDAL >= 3.6).
"""
import argparse
import base64
import concurrent.futures as cf
import hashlib
import json
import os
import subprocess
import tempfile

# GDAL numbers the internal overviews from 0: 5566, 2783, 1391, 695, 347 px.
STATS_LEVEL = 1  # 2783 px: about 40 m, about 7.7 Mpx per tile
THUMB_LEVEL = 4  # 347 px, the coarsest internal overview
# matplotlib YlGn, the `ylgn` colormap of the collection renders, at nine stops.
YLGN = ["255 255 229", "247 252 185", "217 240 163", "173 221 142", "120 198 121",
        "65 171 93", "35 132 67", "0 104 55", "0 69 41"]
ENV = dict(os.environ, GDAL_PAM_ENABLED="NO")  # no .aux.xml next to the tiles


def run(args):
    return subprocess.run(args, check=True, capture_output=True, text=True, env=ENV).stdout


def color_file(path):
    with open(path, "w") as f:
        f.write("nv 0 0 0\n")
        for i, rgb in enumerate(YLGN):
            f.write(f"{i / (len(YLGN) - 1):.4f} {rgb}\n")


def sha256_multihash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return "1220" + h.hexdigest()


def one(task):
    key, tif, md5_b64, size, publish, colors = task
    coll, tile = key.split("/")[0], key.split("/")[1]
    info = json.loads(run(["gdalinfo", "-json", tif]))
    gt = info["geoTransform"]
    width, height = info["size"]
    band = info["bands"][0]
    stats = json.loads(run(["gdalinfo", "-json", "-stats", "-oo", f"OVERVIEW_LEVEL={STATS_LEVEL}", tif]))
    md = stats["bands"][0].get("metadata", {}).get("", {})

    thumb = os.path.join(publish, coll, tile, f"{tile}.thumb.jpg")
    os.makedirs(os.path.dirname(thumb), exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        small = os.path.join(tmp, "small.tif")
        rgb = os.path.join(tmp, "rgb.tif")
        run(["gdal_translate", "-q", "-ovr", str(THUMB_LEVEL), tif, small])
        run(["gdaldem", "color-relief", "-q", "-alpha", small, colors, rgb])
        run(["gdal_translate", "-q", "-of", "JPEG", "-b", "1", "-b", "2", "-b", "3",
             "-co", "QUALITY=85", rgb, thumb])

    return key, {
        "bytes": size,
        "md5": md5_b64,
        "file_checksum": "d50110" + base64.b64decode(md5_b64).hex(),  # md5 multihash
        "shape": [height, width],
        "transform": [gt[1], gt[2], gt[0], gt[4], gt[5], gt[3]],
        "bbox": [gt[0], gt[3] + gt[5] * height, gt[0] + gt[1] * width, gt[3]],
        "data_type": band["type"].lower(),
        "statistics": {
            "minimum": float(md["STATISTICS_MINIMUM"]),
            "maximum": float(md["STATISTICS_MAXIMUM"]),
            "mean": float(md["STATISTICS_MEAN"]),
            "stddev": float(md["STATISTICS_STDDEV"]),
            "valid_percent": float(md["STATISTICS_VALID_PERCENT"]),
        },
        "thumbnail": {"bytes": os.path.getsize(thumb), "file_checksum": sha256_multihash(thumb)},
    }


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--staging", required=True)
    p.add_argument("--md5", required=True)
    p.add_argument("--publish", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--jobs", type=int, default=os.cpu_count())
    a = p.parse_args()

    md5s = {}
    with open(a.md5) as f:
        for line in f:
            key, size, md5 = line.rstrip("\n").split("\t")
            md5s[key] = (md5, int(size))
    colors = os.path.join(a.publish, ".ylgn.txt")
    os.makedirs(a.publish, exist_ok=True)
    color_file(colors)

    tasks = []
    for root, _, files in os.walk(a.staging, followlinks=True):
        for name in files:
            if name.endswith(".tif"):
                tif = os.path.join(root, name)
                key = os.path.relpath(tif, a.staging)
                md5, size = md5s[key]
                assert os.path.getsize(tif) == size, key
                tasks.append((key, tif, md5, size, a.publish, colors))

    out = {}
    with cf.ProcessPoolExecutor(a.jobs) as ex:
        for i, (key, meta) in enumerate(ex.map(one, sorted(tasks)), 1):
            coll, tile = key.split("/")[0], key.split("/")[1]
            out.setdefault(coll, {})[tile] = meta
            if i % 50 == 0:
                print(f"{i}/{len(tasks)}", flush=True)
    os.remove(colors)
    with open(a.out, "w") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    print(f"wrote {a.out}: {sum(len(v) for v in out.values())} tiles")


if __name__ == "__main__":
    main()
