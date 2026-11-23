# OUTPOST

**Offline-first personal command centre.** OUTPOST is designed to run locally on modest Android/Linux devices, with optional integrations kept separate from its core.

## Current foundation

- Local-only Python server (standard library; no pip dependencies).
- SQLite database with full-text search (FTS5 when available).
- Create, edit, and delete notes; organise saved references into collections.
- Global search across indexed files, notes, and saved references.
- Offline IPv4/IPv6 address and CIDR calculator (network, range, masks, and address classification).
- Portable JSON backup export and additive restore.
- Explicit-root file indexing and local text search.
- Responsive dark command-centre UI with no remote font or CDN dependency.
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
- Use **Settings → Export backup** to save notes, collections, and bookmarks as JSON; **Import backup** adds those records without deleting existing data.
- Copy the `data/` directory to preserve the local database and file index as well.

## Roadmap

1. Validate on Android/Termux across different storage permission setups.
2. Add optional Kiwix ZIM discovery and offline library launch.
3. Add authenticated local-network pairing with explicit approval.
4. Add optional adapters for selected open-source tools after license and platform review.
5. Add encrypted backups.

The IP toolbox performs calculations only; it does not scan hosts or contact external services.

OUTPOST is a local knowledge and productivity workspace, not an offensive security tool.

## The eight selected integrations

The integration plan is documented in [INTEGRATIONS.md](INTEGRATIONS.md). OUTPOST combines the useful local capabilities of these projects without bundling incompatible servers or running third-party code automatically:

1. **AFDrive** — local file-vault architecture and safe file management.
2. **Kiwix JS** — discover local ZIM archives for offline reading.
3. **Personal File Archive** — local file catalogue and metadata.
4. **Grimoire** — offline searchable security knowledge.
5. **Termux-Tools** — Android environment and command availability checks.
6. **Uplink** — local document retrieval and source-grounded search patterns.
7. **Claude-BugHunter** — optional offline Agent Skills/reference material for authorized testing.
8. **CyberDesk** — safe local file inspection and defensive research workspace.

### Integration folders

- Put ZIM archives in `data/zim/` (large binary archives are not stored in Git).
- Put trusted, licensed Markdown/YAML security references in `knowledge/security/`.
- Put optional Agent Skills / `SKILL.md` references in `knowledge/bughunter/`.

The two knowledge folders are automatically included in local indexing. The File Archive view browses only explicitly selected folders plus OUTPOST's own knowledge folder. File inspection calculates SHA-256 and previews supported text; it never executes a file.

**Offline boundary:** ZIM archives and external knowledge repositories must first be obtained. Once stored locally, the reader/index can work without an internet connection. External projects remain separate; their licenses must be respected before copying any code or assets.
