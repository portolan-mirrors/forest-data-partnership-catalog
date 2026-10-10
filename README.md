# Forest Data Partnership: Source Cooperative mirror

A git-backed [Portolan](https://www.portolan-sdi.org/) catalog of the Forest Data
Partnership commodity maps produced by Google: per-pixel probability that land is
planted with cocoa, coffee, oil palm or rubber, at 10 m, model release 2026a.

- **Published catalog:** https://data.source.coop/portolan-mirrors/forest-data-partnership-catalog/catalog.json
- **Browse:** https://source.coop/portolan-mirrors/forest-data-partnership-catalog
- **Source:** `gs://earth-engine-public-requester-pays/forestdatapartnership` (requester pays),
  documented at https://developers.google.com/earth-engine/guides/forest_data_partnership_gcs_readme
- **License:** CC-BY-4.0. Attribution: "Produced by Google for the Forest Data Partnership."

## Why a mirror

Google publishes the files in a requester-pays bucket. Every read is billed to the
reader's Google Cloud project, anonymous HTTP is refused, and the bucket sends no
CORS headers, so browsers cannot read it. This mirror serves the same files,
byte for byte, over plain HTTPS with range requests and CORS: no account and no
billing, readable from QGIS, GDAL, Python and web maps.

## What is in it

The West African cocoa belt (224 one-degree tiles, 15°W–17°E, 1°S–11°N), for
each commodity and mirrored year, one collection per commodity and year
(`cocoa-2024`, `cocoa-2018`, ...). Each collection also carries a pan-tropical
overview COG (about 320 m, all 5,516 tiles of the release) for low-zoom maps.

## Layout

| Path | What it is |
|---|---|
| `catalog/` | The published STAC tree, synced 1:1 to Source Cooperative. Generated, except the root `README.md` and `AGENTS.md` |
| `tools/build_catalog.py` | Generates the STAC from `tools/data/` |
| `tools/extract_tile_metadata.py` | Per-tile metadata and thumbnails, run where the tiles are on disk |
| `tools/build_overview.sh`, `tools/describe_overviews.py` | The pan-tropical overview COGs and their metadata |
| `tools/data/` | Committed inputs of the generator (small JSON) |
| `tools/publish.py`, `tools/upload_data.py` | Publish the metadata and the data files. Dry run by default |
| `catalog.publish.yaml` | Where it publishes, and under what public URL |
| `tests/` | The gates CI runs: links, STAC validity, Portolan conformance (rashid) |

See `AGENTS.md` for the build and publish steps.

## Checks

```sh
python3 tests/run_all.py          # all gates
python3 tools/publish.py          # dry run of the publish
```

CI runs the gates and a gitleaks secret scan on every push and pull request.

## Contributing

Found a wrong license, link or description? Open an issue or a pull request.
Edit the generator or its inputs, not the generated files under `catalog/`.
