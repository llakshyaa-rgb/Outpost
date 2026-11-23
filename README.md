# OUTPOST

**Offline-first personal command centre.** OUTPOST is designed to run locally on modest Android/Linux devices, with optional integrations kept separate from its core.

## Current foundation

- Local-only Python server (standard library; no pip dependencies).
- SQLite database with full-text search (FTS5 when available).
- Notes and saved knowledge collections.
- Explicit-root file indexing and local text search.
- Responsive dark command-centre UI.
- Health/status endpoint and safe local API.
- No cloud account, telemetry, remote access, or external API required.

## Run

Python 3.10+:

```bash
python3 app.py
```

Open http://127.0.0.1:8765

On Android/Termux, install Python with `pkg install python`, clone the repository, then run the same command.

## File indexing

OUTPOST does not scan your device automatically. Add only folders you choose in **Settings → Index roots**, then run **Index now**. Files stay on-device. Text extraction currently supports plain text, Markdown, JSON, CSV, Python, JavaScript, HTML, CSS, YAML, TOML, and logs. Binary and large files are skipped.

## Data and privacy

- Database: `data/outpost.db`
- Configuration: `data/config.json`
- Bind address: `127.0.0.1` only.
- No shell execution, arbitrary URL fetching, or remote bind option.
- Back up the `data/` directory to preserve your notes and index.

## Roadmap

1. Validate on Android/Termux.
2. Add optional Kiwix ZIM discovery/launch integration.
3. Add local-network pairing with explicit approval and authentication.
4. Add import adapters for selected open-source tools after license and platform review.
5. Add encrypted backups and restore.

OUTPOST is a local knowledge and productivity workspace, not an offensive security tool.