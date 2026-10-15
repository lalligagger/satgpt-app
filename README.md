# SatGPT recorded demo (the `gh-pages` branch)

This branch is the static site at <https://kevinlalli.me/satgpt-app/>: a recorded SatGPT session replayed
with Leaflet, with the spectral index, date, colormap, stretch and cloud mask switchable in the browser.
No server, no model, no keys; free-typed chat gets a canned reply (`DEMO_REPLY` in `app.js`).

The app itself lives on `main`. `tools/record.py` produces `data/` from it: run it from a `main`
checkout with the app's virtualenv (`PYTHONPATH=<main checkout> .venv/bin/python tools/record.py
[--no-llm]`), then copy the resulting `data/` here. `data/SOURCES.md` records what the current data was
made from. Keep the branch under 10 MB.
