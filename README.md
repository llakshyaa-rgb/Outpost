# OUTPOST

**Your own ground. Your own rules.** OUTPOST is an offline-first personal workspace for local files, knowledge, notes, references and practical utilities. It is designed for Android/Termux and Linux, with a lightweight Python standard-library server and SQLite storage.

## What is in the current build

- Unified responsive workspace with dedicated areas for all eight selected projects.
- Local file archive: browse explicitly selected folders, inspect file signatures, calculate SHA-256 and preview supported text safely.
- Offline library: discover local ZIM archives and track local Grimoire / Agent Skill knowledge packs.
- Local knowledge search across indexed documents, notes and bookmarks (SQLite FTS5 when available).
- Notes, collections and bookmarks with edit/delete support.
- IPv4/IPv6 subnet calculator.
- JSON backup export and additive import.
- Termux/device diagnostics and module status.
- No cloud account, analytics, CDN, remote font or external API needed for core use.

## Run on Android / Termux

Install Termux from a trusted source, then:

```sh
pkg update
pkg install python git
git clone https://github.com/llakshyaa-rgb/Outpost.git
cd Outpost
python app.py
```

Open **http://127.0.0.1:8765** in your browser. Stop the server with Ctrl+C.

Optional: grant Termux shared-storage access using `termux-setup-storage`, then add the folder paths you want OUTPOST to index in **Settings**. OUTPOST does not scan your phone automatically.

## Data locations

- SQLite database: `data/outpost.db`
- Settings: `data/config.json`
- ZIM archives: `data/zim/`
- Security references: `knowledge/security/`
- Agent Skill references: `knowledge/bughunter/`

Back up both the JSON export and the `data/` directory if you want a complete copy of your workspace. JSON backup includes notes, collections and bookmarks; it does not include large files or ZIM archives.

## The eight selected projects

The integration map is in [INTEGRATIONS.md](INTEGRATIONS.md).

1. **AFDrive** — local file-vault patterns and safe file management.
2. **Kiwix JS** — local ZIM archive discovery and offline reader handoff.
3. **Personal File Archive** — local file catalogue and metadata.
4. **Grimoire** — searchable offline security knowledge.
5. **Termux-Tools** — device environment and command availability checks.
6. **Uplink** — local retrieval and source-grounded search patterns.
7. **Claude-BugHunter** — optional Agent Skills/reference material for authorized testing.
8. **CyberDesk** — defensive file inspection and security research workspace.

### Important integration boundary

OUTPOST is a unified native implementation inspired by the selected projects; it does **not** bundle eight complete upstream applications. The modules currently provide the native adapters described in [INTEGRATIONS.md](INTEGRATIONS.md). Third-party source code and datasets must be imported separately after checking their licenses. Kiwix reading requires a compatible reader and a ZIM archive obtained beforehand.

## Privacy and safety

- Server binds to `127.0.0.1` only.
- No whole-device scan; only selected index roots and OUTPOST's own knowledge folder are browsed/indexed.
- File inspection never executes files.
- No shell command or package installation is triggered by the dashboard.
- Security playbooks are local reference material, not autonomous scanners.
- The IP toolbox calculates addresses only; it does not probe hosts.

## Requirements

Python 3.10+; no pip packages required. SQLite FTS5 is used when present, with a basic local-search fallback.

## Current validation status

The repository files and route/UI wiring have been updated, but runtime behavior still needs to be exercised on the target Android/Termux device. This matters especially for shared-storage permissions, SQLite build options and the installed Kiwix reader.
