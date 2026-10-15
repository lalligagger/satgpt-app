#!/usr/bin/env bash
# Serve satgpt-app locally and (optionally) expose it with a cloudflared quick tunnel.
#   OPENAI_API_KEY=... ./run_local.sh            # local only, http://localhost:5006/app
#   OPENAI_API_KEY=... ./run_local.sh --tunnel   # also prints a https://*.trycloudflare.com URL
# Landsat imagery (requester-pays usgs-landsat bucket): AWS_REQUEST_PAYER=requester ./run_local.sh, with ~/.aws/credentials set.
# --config /dev/null keeps ~/.cloudflared/config.yml (the racinglines named tunnel) from overriding --url.
set -euo pipefail
cd "$(dirname "$0")"
: "${OPENAI_API_KEY:?set OPENAI_API_KEY first (export OPENAI_API_KEY=...)}"
PORT="${PORT:-5006}"
export GDAL_CACHEMAX="${GDAL_CACHEMAX:-512}"   # MB, in-memory raster cache only; nothing is written to disk
if [[ "${1:-}" == "--tunnel" ]]; then
  cloudflared tunnel --config /dev/null --url "http://127.0.0.1:${PORT}" --protocol http2 --no-autoupdate 2>&1 | grep --line-buffered -o 'https://[a-z0-9-]*\.trycloudflare\.com' &
fi
exec .venv/bin/python -m panel serve app.py --port "$PORT" --allow-websocket-origin='*' --address 0.0.0.0 --autoreload
