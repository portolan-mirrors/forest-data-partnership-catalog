#!/usr/bin/env bash
# Build one pan-tropical overview COG per commodity from Google's source release.
#
# The overview is the 347 px level (about 320 m) of every tile of the release
# (24°S to 24°N, 5,516 tiles per commodity), not only the tiles this catalog
# mirrors. Each tile's level is extracted unchanged (gdal_translate -ovr 4), the
# extracts are mosaicked with NaN where no tile exists, and the mosaic is written as
# a COG. No pixel is resampled; the COG's own internal overviews use AVERAGE.
#
# Run where reading the bucket is free (a VM in us-central1). Requester pays:
# GS_USER_PROJECT names the project billed for the read operations.
#
# Usage: GS_USER_PROJECT=<project> tools/build_overview.sh <commodity> <out_dir> [work_dir]
#   e.g. GS_USER_PROJECT=cartobq tools/build_overview.sh cocoa /data/publish /data/ovr_work
set -euo pipefail
C="$1"; OUT="$2"; WORK="${3:-/tmp/ovr_work}/$C"
RELEASE="${RELEASE:-2026a}"; YEAR="${YEAR:-2024}"
SRC="gs://earth-engine-public-requester-pays/forestdatapartnership/$RELEASE/$C/$YEAR"
: "${GS_USER_PROJECT:?set GS_USER_PROJECT to the project billed for requester-pays reads}"
export GS_USER_PROJECT GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR CPL_VSIL_CURL_ALLOWED_EXTENSIONS=.tif GDAL_PAM_ENABLED=NO
mkdir -p "$WORK/tiles" "$OUT/$C-$YEAR"

gcloud storage ls --billing-project="$GS_USER_PROJECT" "$SRC/*.tif" > "$WORK/list.txt"
echo "$C: $(wc -l < "$WORK/list.txt") tiles"

# Extract the 347 px level of each tile, 32 at a time. Resumable.
sed 's#^gs://#/vsigs/#' "$WORK/list.txt" | xargs -P 32 -I{} bash -c '
  out="$0/tiles/$(basename "{}")"
  [ -s "$out" ] || gdal_translate -q -of GTiff -ovr 4 -co COMPRESS=ZSTD -co PREDICTOR=3 "{}" "$out.part" && mv "$out.part" "$out" 2>/dev/null || true
' "$WORK"
n=$(ls "$WORK/tiles" | grep -c '\.tif$')
echo "$C: extracted $n level-4 tiles"
[ "$n" = "$(wc -l < "$WORK/list.txt")" ] || { echo "missing extracts, rerun to resume"; exit 1; }

ls "$WORK"/tiles/*.tif > "$WORK/extracts.txt"
gdalbuildvrt -q -vrtnodata nan -input_file_list "$WORK/extracts.txt" "$WORK/mosaic.vrt"
gdal_translate -q -of COG -co COMPRESS=ZSTD -co PREDICTOR=YES -co BLOCKSIZE=512 \
  -co OVERVIEW_RESAMPLING=AVERAGE -co STATISTICS=YES -co NUM_THREADS=ALL_CPUS \
  --config GDAL_CACHEMAX 4096 "$WORK/mosaic.vrt" "$OUT/$C-$YEAR/$C-${YEAR}_overview.tif"
ls -l "$OUT/$C-$YEAR/$C-${YEAR}_overview.tif"
gdalinfo "$OUT/$C-$YEAR/$C-${YEAR}_overview.tif" | grep -E "Size is|Overviews|STATISTICS_(MEAN|VALID)"
