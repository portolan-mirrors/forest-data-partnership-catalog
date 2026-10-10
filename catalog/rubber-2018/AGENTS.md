# Rubber probability 2018 (Forest Data Partnership model 2026a): agent guide

Every claim here is quoted from the source documentation or measured from the files.

## What the data is

- One band, `probability`, Float32 from 0 to 1, in EPSG:4326, about 10 m per pixel. 224 items, one per one-degree tile. Item ids are `lng_<west>_lat_<south>`.
- Values are model probabilities, not observations. Pick a threshold for your purpose; the collection renders offer 0 to 1 and 0.5 to 1.
- The same item ids exist in the other commodity collections for 2018, and in `rubber-<other year>` collections, so tiles can be compared across commodities and years.

## How to read it

Find tiles with one request, from the STAC GeoParquet mirror:

```sql
SELECT id, bbox, assets.data.href
FROM read_parquet('https://data.source.coop/portolan-mirrors/forest-data-partnership-catalog/rubber-2018/items.parquet')
WHERE bbox.xmin < -1 AND bbox.xmax > -2 AND bbox.ymin < 7 AND bbox.ymax > 6;
```

Read a tile window with rasterio (range requests, no download of the whole file):

```python
import rasterio
url = 'https://data.source.coop/portolan-mirrors/forest-data-partnership-catalog/rubber-2018/lng_-2_lat_6/lng_-2_lat_6.tif'
with rasterio.open(url) as src:
    prob = src.read(1, out_shape=(1024, 1024))  # reads an internal overview
print((prob >= 0.5).mean())
```

## Limits

- Coverage is the West African cocoa belt only. The full release covers 24°S to 24°N: see https://developers.google.com/earth-engine/datasets/publisher/forestdatapartnership.
- Model method and known limitations: https://github.com/google/forest-data-partnership/tree/main/models/model_2026a
- The source COGs have no embedded band statistics; the items carry approximate ones.
