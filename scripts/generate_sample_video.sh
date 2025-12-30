#!/usr/bin/env bash
set -euo pipefail

OUT="${1:-samples/sample.mp4}"
mkdir -p "$(dirname "$OUT")"

ffmpeg -y \
  -f lavfi -i testsrc=size=640x360:rate=30 \
  -f lavfi -i sine=frequency=1000:sample_rate=44100 \
  -t 2 \
  -c:v libx264 -pix_fmt yuv420p \
  -c:a aac \
  "$OUT" >/dev/null 2>&1

echo "Generated $OUT"

