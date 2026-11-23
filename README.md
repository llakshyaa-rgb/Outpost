# OUTPOST

**Offline-first personal command centre.** OUTPOST is designed to run locally on modest Android/Linux devices, with optional integrations kept separate from its core.

## Current foundation

- Local-only Python server (standard library; no pip dependencies).
- SQLite database with full-text search (FTS5 when available).
- Notes, saved references, and knowledge collections.
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
- Back up the `data/` directory to preserve your notes and index.

## Roadmap

1. Validate on Android/Termux.
2. Add optional Kiwix ZIM discovery/launch integration.
3. Add local-network pairing with explicit approval and authentication.
4. Add import adapters for selected open-source tools after license and platform review.
5. Add encrypted backups and restore.

OUTPOST is a local knowledge and productivity workspace, not an offensive security tool.
## Optional integrations (design review)

OUTPOST's core stays dependency-free and offline-first. External projects are **not copied into the core**; they are separate, opt-in tools:

| Project | Intended role | Integration decision |
|---|---|---|
| [Tookie-OSINT](https://github.com/Alfredredbird/tookie-osint) | Username-to-public-profile discovery | Optional network-dependent tool; its upstream project supports Termux. Keep scans explicit and user-initiated. |
| [Claude-BugHunter](https://github.com/elementalsouls/Claude-BugHunter) | Security research methodology and reporting skills | Reference/knowledge pack only; it is a Claude Code skill bundle, not a standalone offline scanner. Use only on owned or explicitly authorized targets. |
| [IPinfo CLI](https://github.com/ipinfo/cli) | IP/ASN intelligence | Optional external lookup; requires network access and has reduced functionality without an API token. |
| [Pi-hole](https://github.com/pi-hole/pi-hole) | DNS filtering and network statistics | Connect to an already-running Pi-hole instance on the user's network; OUTPOST will not install or administer DNS services itself. |
| [Nextcloud](https://github.com/nextcloud/server) | File sync and sharing | Keep as an external server option, not bundled into OUTPOST's lightweight Termux process. |
| Reddit r/Piracy | Community-maintained reference material | Link to public resources only; do not scrape or redistribute copyrighted content. |

These tools are not required to run OUTPOST. Network integrations must be clearly labelled and remain disabled until configured. No background scans or remote access are enabled by default.

