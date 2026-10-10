#!/usr/bin/env python3
"""Describe the overview COGs that tools/build_overview.sh wrote, for build_catalog.py.

Reads `<publish>/<collection>/<collection>_overview.tif` for one year and writes
`tools/data/overviews_<year>.json`: per collection, the file name, size, sha256
multihash, pixel grid, bbox, embedded band statistics, the number of source tiles
and the processing lineage.

Usage (on the VM, after build_overview.sh):
    python3 tools/describe_overviews.py --publish /data/publish --work /data/ovr_work \
        --year 2024 --out overviews_2024.json
"""
import argparse
import hashlib
import json
import os
import subprocess

LINEAGE = (
    "For each of the release's source tiles: gdal_translate -ovr 4 (the 347 px internal overview, as "
    "published, unchanged). Then gdalbuildvrt -vrtnodata nan over the extracts, and gdal_translate -of COG "
    "-co COMPRESS=ZSTD -co PREDICTOR=YES -co BLOCKSIZE=512 -co OVERVIEW_RESAMPLING=AVERAGE -co STATISTICS=YES. "
    "Script: tools/build_overview.sh.")


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--publish", required=True)
    p.add_argument("--work", required=True, help="build_overview.sh work dir, for the source tile lists")
    p.add_argument("--year", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    env = dict(os.environ, GDAL_PAM_ENABLED="NO")
    version = subprocess.run(["gdalinfo", "--version"], check=True, capture_output=True,
                             text=True).stdout.split(",")[0].removeprefix("GDAL ")
    out = {}
    for c in ("cocoa", "coffee", "palm", "rubber"):
        cid = f"{c}-{a.year}"
        name = f"{cid}_overview.tif"
        path = os.path.join(a.publish, cid, name)
        if not os.path.exists(path):
            print(f"{cid}: no overview, skipped")
            continue
        info = json.loads(subprocess.run(["gdalinfo", "-json", path], check=True, capture_output=True,
                                         text=True, env=env).stdout)
        gt = info["geoTransform"]
        w, h = info["size"]
        md = info["bands"][0].get("metadata", {}).get("", {})
        sha = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 22), b""):
                sha.update(chunk)
        with open(os.path.join(a.work, c, "list.txt")) as f:
            source_tiles = sum(1 for line in f if line.strip())
        out[cid] = {
            "file": name,
            "bytes": os.path.getsize(path),
            "file_checksum": "1220" + sha.hexdigest(),
            "shape": [h, w],
            "transform": [gt[1], gt[2], gt[0], gt[4], gt[5], gt[3]],
            "bbox": [gt[0], gt[3] + gt[5] * h, gt[0] + gt[1] * w, gt[3]],
            "statistics": {k: float(md[f"STATISTICS_{k.upper()}"])
                           for k in ("minimum", "maximum", "mean", "stddev", "valid_percent")},
            "source_tiles": source_tiles,
            "lineage": LINEAGE,
            "software": {"GDAL": version},
        }
        print(f"{cid}: {out[cid]['bytes'] / 1e9:.2f} GB, {w} x {h}, {source_tiles} source tiles")
    with open(a.out, "w") as f:
        json.dump(out, f, indent=1, sort_keys=True)
        f.write("\n")


if __name__ == "__main__":
    main()
