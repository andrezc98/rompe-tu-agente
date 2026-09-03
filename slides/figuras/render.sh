#!/usr/bin/env bash
# Renders the three generated deck figures with Cloudscape (dark mode) and overwrites the PNGs in
# slides/assets. Needs Node; Playwright brings its own Chromium. Run from anywhere.
set -euo pipefail
cd "$(dirname "$0")"
(cd ../.. && uv run python -m evals.charts)   # writes data.json and the matplotlib fallbacks
[ -d node_modules ] || npm ci
npx playwright install chromium >/dev/null   # one-time browser download, then a no-op
npx vite build --logLevel warn 2>&1 | grep -v -E "chunk|dynamic import|codeSplitting|chunkSizeWarningLimit|vite-reporter|^$" || true
python3 -m http.server 4173 --directory dist >/dev/null 2>&1 & SRV=$!
trap 'kill $SRV' EXIT
sleep 1
node shot.mjs
