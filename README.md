# OUTPOST

**Your own ground. Your own rules.** OUTPOST 0.4.0 is an offline-first local workspace for Android/Termux and Linux. It combines a navigable file vault, offline knowledge library, local document retrieval, notes, and a defensive analysis toolkit.

## Current offline feature set

- **AFDrive-style file vault:** folder-by-folder browsing, create folders, upload, download, rename, copy, delete and create ZIP archives; safe ZIP extraction; explicit roots only.
- **Archive hygiene:** scan selected folders for byte-identical duplicates using SHA-256, with bounded scan sizes.
- **Personal File Archive-style catalogue:** file metadata, modified dates, sizes, type detection, SHA-256 and text previews.
- **Kiwix library discovery:** finds local .zim archives. The reader itself is not bundled or launched yet.
- **Grimoire-style knowledge library:** import local ZIP packs containing Markdown, text, YAML, JSON, Python and shell reference files; browse and search imported material offline.
- **Uplink-style retrieval:** local SQLite FTS search across notes, bookmarks and selected documents; optional PDF, DOCX, XLSX and XLS extraction when their Python libraries are already installed.
- **Termux diagnostics:** detects Termux, Python, Git and selected local commands, reports available storage, and can list locally installed packages from the dpkg database. It does not install packages or run arbitrary shell commands.
- **Claude-BugHunter reference library:** import and search local Agent Skill files and supporting scripts. Imported scripts are stored as reference material and are never executed.
- **CyberDesk-inspired offline toolkit:** file triage, magic-byte identification, hashes, entropy, printable strings, ZIP safety audit, IOC extraction (IPs/domains/URLs/emails/hashes), JWT decoding without verification, hash-format hints, Caesar/Atbash/ROT47, single-byte XOR candidates and an expanded bounded text-transform pipeline (Base64, hex, URL, ROT13, binary, JSON, HTML, gzip, line operations and text statistics).
- Notes, collections, bookmarks, IPv4/IPv6 calculations, and JSON backup export/import.

## Run on Android / Termux

```sh
pkg update
pkg install python git
git clone https://github.com/llakshyaa-rgb/Outpost.git
cd Outpost
python app.py
```

Open **http://127.0.0.1:8765**. Stop with Ctrl+C.

Optional shared storage access:

```sh
termux-setup-storage
```

Then add only the folders you want OUTPOST to access in Settings. It never scans the whole phone automatically.

## Local data

- SQLite database: `data/outpost.db`
- Settings: `data/config.json`
- ZIM archives: `data/zim/`
- Offline knowledge: `knowledge/`
- Imported knowledge packs: `knowledge/imported/`

The JSON backup includes notes, collections and bookmarks. It does not include your files, ZIM archives, or imported knowledge packs; back up the `data/` and `knowledge/` folders separately.

## Offline-only boundary

- Core runtime makes no external API calls and uses no CDN, cloud account, analytics or remote fonts.
- The app binds to `127.0.0.1` only.
- Online OSINT, remote recon, web lookups, cloud integrations, remote source syncing and live network scanning are intentionally excluded for now.
- Kiwix JS itself is not bundled; this build only discovers local ZIM files.
- Optional PDF/Office extraction works only if the relevant libraries are already installed. The base app requires no pip packages.

## Safety and resource limits

- File operations are restricted to configured roots and OUTPOST knowledge folders; symlink paths are rejected.
- File inspection and security tools are static/offline. Files are never executed.
- Knowledge ZIP imports are size-bounded and reject path traversal and symlink entries.
- Indexing is capped at 5,000 files / 300 MB total, with a 5 MB per-file limit.
- The security toolkit is for local learning, CTF files and authorized defensive work. It does not probe external targets.

## Validation

Run local regression tests with `python -m unittest discover -s tests -v`. They cover configured-root access, symlink rejection, indexing and removal of unselected roots. Runtime testing on the target Android/Termux phone is still required. In particular, test shared-storage permissions, SQLite FTS5, optional document extractors, uploads/downloads and large-folder performance.

See [INTEGRATIONS.md](INTEGRATIONS.md) for the exact module boundaries and upstream license notes.


## Compact offline integrations (0.4.0)

- **AFDrive / Personal File Archive:** local file vault with safe folder browsing, upload, create, rename, copy, ZIP creation/extraction, metadata, previews and duplicate detection. Files stay in configured local roots.
- **Uplink / Grimoire:** standard-library retrieval helpers and SQLite FTS5/BM25 search over local notes, imported Markdown/playbooks and selected folders. Queries are safely quoted and fall back from AND to OR. No embeddings, model, or cloud service.
- **Claude-BugHunter:** a compact, searchable index of 83 skill descriptions is included in `knowledge/bughunter/CLAUDE_BUGHUNTER_INDEX.md` with attribution. It is reference material, not a full Claude Code plugin; no upstream scripts are executed.
- **CyberDesk:** lightweight static analysis for strings, hex, ELF/PE headers, embedded file signatures and PCAP metadata, alongside the existing hashes, entropy, IOC, JWT, ZIP and transform tools. No heavy native dependencies.
- **Termux-Tools:** read-only Termux diagnostics, command availability and local package inventory. No automatic package installation or shell execution.
- **Kiwix JS:** local ZIM discovery and metadata only. Full reading requires a separately installed Kiwix reader; OUTPOST deliberately does not bundle its large WASM runtime or download content.

Core runtime remains loopback-only and makes no external network requests. Optional file formats requiring third-party libraries stay unavailable unless the user has installed those libraries. No ZIM/wordlist/corpus is bundled, keeping repository and runtime footprint small.
