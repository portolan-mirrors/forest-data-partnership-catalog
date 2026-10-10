# Forest Data Partnership commodity maps (Source Cooperative mirror)

Per-pixel probability, from 0 to 1, that land is planted with cocoa, coffee, oil palm
or rubber, at 10 m resolution, from the Forest Data Partnership community model
release 2026a, produced by Google.

## What is here

The West African cocoa belt for 2018 and 2024: 224 one-degree tiles per commodity and
year, from Sierra Leone to Gabon (15°W–17°E, 1°S–11°N, land south of 10°N). One
collection per commodity and year, eight in total:

| Collection | Items | Size |
|---|---|---|
| `cocoa-2018`, `cocoa-2024` | 224 each | 110.1 and 110.2 GiB |
| `coffee-2018`, `coffee-2024` | 224 each | 109.4 and 109.6 GiB |
| `palm-2018`, `palm-2024` | 224 each | 110.0 and 109.8 GiB |
| `rubber-2018`, `rubber-2024` | 224 each | 108.6 and 108.6 GiB |

Each item is one Cloud-Optimized GeoTIFF of about 11133 × 11133 Float32 pixels in
EPSG:4326, with a 347 px thumbnail. Item ids (`lng_<west>_lat_<south>`) are the same
in every collection, so a tile can be compared across commodities and years.

Each collection also carries a **pan-tropical overview**: one COG of all 5,516 tiles
of the release for that commodity and year (24°S–24°N) at about 320 m, 2.5 to 2.6 GB.
It serves maps below zoom 9 and coarse statistics. Every collection publishes its
items as STAC GeoParquet (`items.parquet`).

## License

[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/). Attribute as:
"Produced by Google for the Forest Data Partnership."

## Provenance

This catalog is a mirror, not the official publication. Google publishes the files
in a requester-pays Google Cloud Storage bucket,
`gs://earth-engine-public-requester-pays/forestdatapartnership`, documented at
https://developers.google.com/earth-engine/guides/forest_data_partnership_gcs_readme.
There, every read is billed to the reader and browsers cannot read the files.

The tiles were copied unchanged on 2026-10-10 (2024 at 17:10 UTC, 2018 at
18:12 UTC). Each item's `file:checksum` is Google's MD5 for the file, and random
anonymous downloads were checked byte for byte against it. The overviews are
derived files, built from the 347 px level that Google publishes inside each tile.
The catalog's source, generator and issue tracker are at
https://github.com/portolan-mirrors/forest-data-partnership-catalog.

Model method and limitations:
https://github.com/google/forest-data-partnership/tree/main/models/model_2026a

## Access

Find the tiles that cover a point, with one request, in DuckDB:

```sql
INSTALL httpfs; LOAD httpfs;
SELECT id, title
FROM read_parquet('https://data.source.coop/portolan-mirrors/forest-data-partnership-catalog/cocoa-2024/items.parquet')
WHERE bbox.xmin <= -1.5 AND bbox.xmax >= -1.5 AND bbox.ymin <= 6.5 AND bbox.ymax >= 6.5;
```

Read one tile without downloading it, in QGIS or GDAL:

```sh
gdalinfo /vsicurl/https://data.source.coop/portolan-mirrors/forest-data-partnership-catalog/cocoa-2024/lng_-2_lat_6/lng_-2_lat_6.tif
```
