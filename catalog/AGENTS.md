# AGENTS.md — Forest Data Partnership commodity maps (Source Cooperative mirror)

Guidance for AI agents and automated clients working with this catalog.

**One rule survives every edit to this file.** Every claim here is either quoted
from a source or measured from the data. If you cannot point at where a fact
came from, it does not belong in this file. An agent acting on an invented join
key or an invented column name produces a confident wrong answer, and nothing
downstream catches it.

## What this catalog holds

Root: `https://data.source.coop/portolan-mirrors/forest-data-partnership-catalog/catalog.json`.

Eight collections, `<commodity>-<year>` for commodity in `cocoa`, `coffee`, `palm`,
`rubber` and year in `2018`, `2024`. Each holds 224 items, one per one-degree tile of
the West African cocoa belt (15°W–17°E, 1°S–11°N). Each item has a `data` asset (a
Float32 COG, one band named `probability`, 0 to 1, EPSG:4326, pixel size
8.98315e-05°, about 10 m) and a `thumbnail` asset (347 px JPEG). Each collection has
an `overview` asset (pan-tropical COG at about 320 m, 24°S–24°N) and a
`geoparquet-items` asset (`items.parquet`, all items as STAC GeoParquet).

## How to read it

List tiles with one request (DuckDB):

```sql
INSTALL httpfs; LOAD httpfs;
SELECT id, title, assets.data.href
FROM read_parquet('https://data.source.coop/portolan-mirrors/forest-data-partnership-catalog/cocoa-2024/items.parquet')
WHERE bbox.xmin <= -1.5 AND bbox.xmax >= -1.5 AND bbox.ymin <= 6.5 AND bbox.ymax >= 6.5;
```

Read a window of a tile, and compare two years of the same tile (Python, rasterio):

```python
import rasterio
base = "https://data.source.coop/portolan-mirrors/forest-data-partnership-catalog"
tile = "lng_-2_lat_6"
for year in (2018, 2024):
    with rasterio.open(f"{base}/cocoa-{year}/{tile}/{tile}.tif") as src:
        prob = src.read(1, out_shape=(1024, 1024))  # reads an internal overview
    print(year, round(float((prob >= 0.5).mean()), 3))
```

## Join keys

- Item `id` (`lng_<west>_lat_<south>`, string) is the same tile in every collection.
  It is unique within a collection. Join on it to compare commodities or years.
- The collection id carries commodity and year: `cocoa-2018`. The only other year
  fields are the item `datetime` (`<year>-07-01T00:00:00Z`) and its
  `start_datetime`/`end_datetime` for the whole year.

## Quirks that produce silently wrong answers

- **Asset hrefs in `items.parquet` are relative to the item's folder, not to the
  parquet file.** `assets.data.href` reads `./lng_-2_lat_6.tif`. Resolve it as
  `<root>/<collection>/<id>/<href without ./>`. Tools that resolve it against the
  parquet location (for example GDAL's GTI driver) point at files that do not exist.
- **Probabilities are almost never exactly 0.** A filter `value > 0` keeps nearly
  every land pixel. Use a threshold (the collection renders use 0.5).
- **The overview covers far more than the items.** It holds all 5,516 tiles of the
  release (24°S–24°N); the items cover 224. Only 27.2% of its pixels hold data
  (measured); the rest is NaN (ocean and areas with no tile). Do not compute
  statistics for the cocoa belt from the overview without clipping it.
- **Statistics from the overview are coarse.** It is the 347 px level Google
  publishes inside each tile, already mean-resampled. Shares above a threshold
  computed from it differ from full-resolution shares.
- **Band statistics on items are approximate.** They come from each tile's 2783 px
  overview level, not from full resolution. The source COGs embed no statistics.
- **Coffee is a negative control here.** In this area, the largest coffee tile mean
  is 0.026 in 2018 and 0.057 in 2024 (item statistics). Treat high coffee values as
  possible false positives.

## Structure

Assets and structural links resolve relative to the object that carries them. The
root carries an absolute `self` link to its published location.
