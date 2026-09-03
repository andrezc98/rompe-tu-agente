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
# The architecture is a draw.io file with the official AWS icons; export needs draw.io desktop.
DRAWIO="/Applications/draw.io.app/Contents/MacOS/draw.io"
if [ -x "$DRAWIO" ]; then
  for d in arquitectura arquitectura-solida; do
    "$DRAWIO" -x -f png -s 3 -t -b 24 -o "../assets/$d.png" "../assets/$d.drawio" >/dev/null 2>&1 && echo "wrote slides/assets/$d.png"
  done
else
  echo "draw.io desktop not found: slides/assets/arquitectura.png not re-exported" >&2
fi
