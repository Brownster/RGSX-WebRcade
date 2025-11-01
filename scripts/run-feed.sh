#!/bin/bash
set -euo pipefail

OUTPUT_DIR="$(dirname "${FEED_OUTPUT_PATH:-/var/www/html/content/feeds/rgsx_feed.json}")"

mkdir -p "${OUTPUT_DIR}"

python3 /opt/rgsx/build_feed.py "$@"
