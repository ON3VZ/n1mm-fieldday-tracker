# N1MM Field Day Tracker

A lightweight, reliable tracker that runs next to **N1MM Logger+** during a
field day. N1MM remains the official logger; this application shows in a
**matrix** which participating stations have been worked on which bands —
in real time, and optionally published as a public read-only web page on
GitHub Pages.

It replaces the manually maintained Excel sheet.

## Key characteristics

- Runs on **Windows and Linux**
- No database server, no cloud service, no authentication — all data in
  plain local JSON files
- Fully usable offline; only publishing to GitHub Pages needs internet
- Receives N1MM Logger+ **UDP Contact broadcasts** (multiple PCs supported)
- **ADIF import** as a safety net for logs that did not arrive in real time
- Participant list import from **Excel (.xlsx) or CSV**
- Manual overrides per station+band, CSV and PDF export

## Requirements

- Python **3.11+**
- See `requirements.txt`

## Development setup

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux:
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run (phase 1: placeholder that verifies the setup)
python -m app.main
```

Application data is stored under:

- **Windows**: `%LOCALAPPDATA%\N1MM Field Day Tracker\`
- **Linux**: `$XDG_DATA_HOME/N1MM Field Day Tracker/` or
  `~/.local/share/N1MM Field Day Tracker/`

## N1MM Logger+ configuration (summary)

In N1MM: `Config > Config Ports, Mode Control, Audio, Other… > Broadcast Data`

- Enable **Contacts**
- Destination: the tracker's IP and port, e.g. `127.0.0.1:12060`
- Contest: `FDREG1`
- When using N1MM *Networked Computer mode*: enable **All Computers** on
  exactly **one** station

Full documentation follows in `docs/` in later phases.

## Project structure

```
app/
├─ main.py          # entrypoint
├─ server.py        # local HTTP server + JSON API (later phase)
├─ config.py        # paths, platform detection, appdata location
├─ core/            # models, band plan, callsign matching, sync engine
├─ ingest/          # N1MM UDP listener/parser, ADIF import, station import
├─ storage/         # atomic JSON store, repositories, app settings
├─ view/            # snapshot builder + static web view
├─ export/          # CSV and PDF export
├─ publish/         # GitHub Pages publisher
└─ i18n/            # translations (en/nl/fr/es)
tests/
docs/
```

## Scope note: multiple tracker laptops

One tracker instance per field day is the supported setup. Multiple N1MM
PCs are fully supported (they all broadcast UDP to the one tracker — N1MM
even accepts multiple space-separated destinations). What is **explicitly
out of scope in this version** is running several tracker laptops that
merge their data through GitHub ("node sync"). The design for it exists
(nodes/ directory per laptop in the shared repo, deterministic merge on
QSO id, newest-wins overrides with tombstones) and is on the roadmap below.

## Roadmap

- **v1 (current)**: single tracker next to N1MM, multi-PC UDP ingest, ADIF
  safety net, six live views in WLD house style, manual overrides, CSV/PDF
  export, publishing a read-only page to GitHub Pages (incl. step-by-step
  instructions for other clubs: create your own repo + Pages + fine-grained
  token).
- **v2 (planned)**: multi-laptop node sync via the shared GitHub repo —
  every tracker pushes its own QSOs/overrides, pulls the other nodes,
  merges locally (two-way visibility) and publishes the combined snapshot.
- Ideas beyond that: score estimation, alerting when a wanted station
  appears in the N1MM bandmap.

## Status

In active development; see `docs/DRAAIBOEK.md` (NL) to get running.
