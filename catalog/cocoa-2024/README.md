# Cocoa probability 2024 (Forest Data Partnership model 2026a)

Per-pixel probability, from 0 to 1, that the pixel includes cocoa trees in 2024, at 10 m resolution.

Ghana and Côte d'Ivoire are the two largest cocoa producers in the world and the best-sampled region in the cocoa reference database. It includes the WRI West Africa Cocoa dataset of about 760,000 GPS-traced plots, CIAT plot data in Ghana, CERSGIS field data from a Lacuna Fund project, and field points collected across Ghana, Côte d'Ivoire, Liberia and Sierra Leone.

Measured from the tiles' 2783 px overview level (about 40 m): tile means range from 0.000 to 0.629, with a median of 0.010, and 46 of 224 tiles have a mean of 0.1 or more.

The Forest Data Partnership (https://developers.google.com/earth-engine/datasets/publisher/forestdatapartnership) is a collaboration on global monitoring of deforestation, degradation and restoration linked to commodity production. It is coordinated with the FAO (https://www.fao.org/in-action/forest-data-partnership) and its reference data come from contributors such as the FAO, WRI, CIAT, MapBiomas, SERVIR, IIASA and Google. Google produces the community models: a deep learning model trained on the AlphaEarth Foundation annual satellite embeddings (64 features per 10 m pixel) with millions of community-sourced reference points. Release 2026a covers the pan-tropical belt from 24°S to 24°N for 2018, 2020, 2022 and 2024, and adds input data, bug fixes and a reworked processing pipeline over release 2025b. The maps are per-pixel probabilities, so users choose a threshold for their purpose, for example commodity supply-chain and deforestation-regulation checks. The datasets are not yet peer reviewed. Method and limitations: https://github.com/google/forest-data-partnership/tree/main/models/model_2026a

This collection mirrors the 224 one-degree tiles of release 2026a for 2024 that touch the West African cocoa belt: land in Sierra Leone, Liberia, Guinea, Côte d'Ivoire, Ghana, Togo, Benin, Nigeria, Cameroon, Equatorial Guinea and Gabon south of 10°N, between 15°W and 17°E and between 1°S and 11°N. The files are copied unchanged from Google's requester-pays bucket, byte for byte, and each item records Google's MD5 for the file. Each tile is one item with one Cloud-Optimized GeoTIFF of about 11133 by 11133 Float32 pixels in EPSG:4326. The same tiles exist for cocoa, coffee, oil palm and rubber, with identical item ids, and for each mirrored year.

## License and attribution

[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/). Attribute as: "Produced by Google for the Forest Data Partnership."

## Provenance

- Source: `gs://earth-engine-public-requester-pays/forestdatapartnership/2026a/cocoa/2024/` (Google Cloud Storage, requester pays).
- Copied unchanged to Source Cooperative on 2026-10-10. Each item's `file:checksum` is Google's MD5 for the file, as a multihash.
- Band statistics come from each tile's 2783 px overview level. They are approximate.

## Files

| File | What it is |
|---|---|
| `<tile>/<tile>.tif` | 224 Cloud-Optimized GeoTIFFs, one per one-degree tile |
| `<tile>/<tile>.thumb.jpg` | 347 px preview of each tile, YlGn ramp |
| `<tile>/<tile>.json` | STAC item of each tile |
| `items.parquet` | all items as STAC GeoParquet, for one-request queries |
| `cocoa-2024_overview.tif` | pan-tropical overview at about 320 m, for maps below zoom 9 |

Browse: https://source.coop/portolan-mirrors/forest-data-partnership-catalog/cocoa-2024
