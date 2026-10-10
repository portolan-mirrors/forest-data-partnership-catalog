## This Repository

The git-backed Portolan catalog of the Forest Data Partnership mirror on Source
Cooperative (`portolan-mirrors/forest-data-partnership-catalog`), created from
`portolan-sdi/portolan-catalog-template`. Git tracks the STAC metadata and its
generator; the COGs, thumbnails and overviews sit in the Source Cooperative bucket.

### Catalog build steps

The STAC under `catalog/` is generated. Edit the generator or its inputs, never
the generated JSON or the collection `README.md`/`AGENTS.md` files.

| Step | Where | Command |
|---|---|---|
| Per-tile metadata and thumbnails | transfer VM, tiles on disk | `tools/extract_tile_metadata.py` → `tools/data/tiles_metadata_<year>.json` |
| Pan-tropical overview COGs | transfer VM (free GCS reads) | `tools/build_overview.sh`, then `tools/describe_overviews.py` → `tools/data/overviews_<year>.json` |
| STAC JSON, collection docs | anywhere | `python3 tools/build_catalog.py` |
| `items.parquet` per collection | anywhere | `portolan stac-geoparquet --catalog catalog`, then `python3 tools/build_catalog.py --register-parquet` |

`catalog/README.md` and `catalog/AGENTS.md` (the catalog root) are written by
hand. `items.parquet` is gitignored and rebuilt by the steps above.

### How it publishes

This catalog publishes with `tools/publish.py` (metadata under `catalog/`) and
`tools/upload_data.py` (thumbnails and overviews from `data_dir`), through the
`data.source.coop` gateway with the `source-coop` AWS profile. `portolan push`
keeps different state and does not interoperate with these tools, so leave it unused here. The
mirrored tiles were copied once by the transfer scripts in the planning repository
and are not re-uploaded.

### The publish boundary

`catalog/` is the published catalog. Everything in it is published, and
nothing outside it ever is. Do not move a file into `catalog/` to make it
publish, and do not add a path outside `publish_dir` to `tools/publish.py`.
The boundary is the only thing standing between a scratch file and a public
bucket, and it holds because it is structural rather than a list of
exclusions.

### Data never enters git

Never commit a GeoParquet, COG, PMTiles, Zarr, or COPC file. If a gate needs
bytes to check, generate them in CI. Git keeps every version of a binary
forever and deleting it later reclaims nothing.

### The conformance allow-list

`ACCEPTED` in `tests/test_conformance.py` ships empty. Never add an entry
without a matching row in `docs/conformance.md` giving the rule, where it
fires, why it is accepted, and the issue tracking its removal.

### Published agent guides

Every claim in a `catalog/**/AGENTS.md` is either quoted from a source or
measured from the data. An invented join key or column name produces a
confident wrong answer that nothing downstream catches.

### The links back to this repository

`catalog/catalog.json` ships a `vcs` link and an `issues` link. Both hrefs are
setup placeholders, so `tests/test_setup.py` catches a half-edited repository.
The Portolan spec recommends these two links for a git-backed catalog. See
[git-backed catalogs](https://github.com/portolan-sdi/portolan-spec/blob/main/specs/best-practices/git-backed-catalogs.md),
which merged in August 2026.

Keep both hrefs absolute. The repository sits outside the published catalog,
so a relative href resolves against the public base URL. Each placeholder
holds a `://`, because `tests/test_links.py` treats an href without one as a
path and looks for it on disk.
