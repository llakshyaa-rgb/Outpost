# OUTPOST

**Your own ground. Your own rules.** OUTPOST 0.9.0 is an offline-first local workspace for Android/Termux and Linux. It combines a navigable file vault, offline knowledge library, local document retrieval, notes, and a defensive analysis toolkit.

## Current offline feature set

- **AFDrive-style file vault:** folder-by-folder browsing, create folders, upload, download, rename, copy files and bounded directory trees, move files/folders, delete and create ZIP archives; safe ZIP extraction; explicit roots only.
- **Archive hygiene:** scan selected folders for byte-identical duplicates using SHA-256, with bounded scan sizes.
- **Personal File Archive-style catalogue:** file metadata, modified dates, sizes, type detection, SHA-256 and text previews.
- **Kiwix JS + Compact Encyclopedia:** includes a one-time Termux installer that builds and installs the pinned official Kiwix JS PWA into `static/kiwix/`, including libzim WebAssembly and XZ/Zstandard decoders. After installation it reads arbitrary compatible local ZIM archives entirely from the device. Also discovers local .zim archives and retains the compact Wikipedia XML importer. A separate streaming XML importer stores cleaned Wikipedia article text compressed in `data/wiki/wiki.db`, with local title/lead search and an in-app reader. A 10 GiB storage ceiling protects the device. Hand-picked raster illustrations can be imported from a local ZIP; most images/media are omitted.
- **Grimoire-style knowledge library:** import local ZIP packs containing Markdown, text, YAML, JSON, Python and shell reference files; browse and search imported material offline.
- **Uplink-style retrieval:** separate change-aware passage index with bounded overlapping chunks, SQLite FTS5 BM25 ranking, AND→OR fallback and source-path citations. No embeddings or model required; optional PDF, DOCX, XLSX and XLS extraction works when the relevant libraries are already installed.
- **Termux-Tools reference:** detects Termux, Python, Git and selected commands, reports storage, lists locally installed packages and shows a local command catalogue with availability checks. Device-changing commands remain manual in Termux.
- **Claude-BugHunter-inspired offline playbooks:** eight guided review checklists for source code, authentication, web input/output, API authorization, secrets/configuration, Android, dependencies and reporting. The playbooks are local reference material, not an AI agent or the full upstream skill bundle.
- **CyberDesk-inspired offline toolkit:** file triage, magic-byte identification, hashes, entropy, printable strings, ZIP safety audit, IOC extraction (IPs/domains/URLs/emails/hashes), JWT decoding without verification, hash-format hints, Caesar/Atbash/ROT47, single-byte XOR candidates, auto-decoding candidates for Base64/hex/URL/ROT13, ELF/PE headers (including PE section metadata), classic PCAP packet summaries (Ethernet, IPv4/IPv6, TCP/UDP) and bounded text transforms.
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
- Compact encyclopedia: `data/wiki/wiki.db`
- Curated encyclopedia images: `data/wiki/images/`
- Offline knowledge: `knowledge/`
- Imported knowledge packs: `knowledge/imported/`

The JSON backup includes notes, collections and bookmarks. It does not include your files, ZIM archives, encyclopedia database, curated images, or imported knowledge packs; back up the `data/` and `knowledge/` folders separately.

## Offline-only boundary

- Core runtime makes no external API calls and uses no CDN, cloud account, analytics or remote fonts.
- The app binds to `127.0.0.1` only.
- Online OSINT, remote recon, web lookups, cloud integrations, remote source syncing and live network scanning are intentionally excluded for now.
- The full Kiwix JS reader is installed by running `python scripts/install_kiwix.py` once in Termux. It downloads pinned upstream source/build dependencies during installation, builds locally, then removes the temporary source/build directory. The installed reader itself runs offline. `static/kiwix/` is generated device-local content and is not committed to Git.
- Optional PDF/Office extraction works only if the relevant libraries are already installed. The base app requires no pip packages.

## Safety and resource limits

- File operations are restricted to configured roots and OUTPOST knowledge folders; symlink paths are rejected.
- File inspection and security tools are static/offline. Files are never executed.
- Knowledge ZIP imports are size-bounded and reject path traversal and symlink entries.
- Indexing is capped at 5,000 files / 300 MB total, with a 5 MB per-file limit.
- The security toolkit is for local learning, CTF files and authorized defensive work. It does not probe external targets.

## Validation

Run local regression tests with `python -m unittest discover -s tests -v`. They cover configured-root access, symlink rejection, indexing and removal of unselected roots. Runtime testing on the target Android/Termux phone is still required. The Wikipedia importer is new and has not yet been validated against a complete Wikimedia dump on-device; its final database size and total article coverage must be measured during a real import. In particular, test shared-storage permissions, SQLite FTS5, optional document extractors, uploads/downloads and large-folder performance.

See [INTEGRATIONS.md](INTEGRATIONS.md) for the exact module boundaries and upstream license notes.


## Compact offline integrations (0.5.0)

- **AFDrive / Personal File Archive:** local file vault with safe folder browsing, upload, create, rename, copy, ZIP creation/extraction, metadata, previews and duplicate detection. Files stay in configured local roots.
- **Uplink / Grimoire:** standard-library retrieval helpers and SQLite FTS5/BM25 search over local notes, imported Markdown/playbooks and selected folders. Queries are safely quoted and fall back from AND to OR. No embeddings, model, or cloud service.
- **Claude-BugHunter:** a compact, searchable index of 83 skill descriptions is included in `knowledge/bughunter/CLAUDE_BUGHUNTER_INDEX.md` with attribution. It is reference material, not a full Claude Code plugin; no upstream scripts are executed.
- **CyberDesk:** lightweight static analysis for strings, hex, ELF/PE headers, embedded file signatures and PCAP metadata, alongside the existing hashes, entropy, IOC, JWT, ZIP and transform tools. No heavy native dependencies.
- **Termux-Tools:** read-only Termux diagnostics, command availability and local package inventory. No automatic package installation or shell execution.
- **Kiwix JS:** full reader installer pinned to an official upstream revision; it builds the PWA and WASM decoders locally into `static/kiwix/`. ZIM archives remain optional user data.

Core runtime remains loopback-only and makes no external network requests. Optional file formats requiring third-party libraries stay unavailable unless the user has installed those libraries. No ZIM/wordlist/corpus is bundled, keeping repository and runtime footprint small.


## Offline knowledge packs (0.6.0)

The Offline library page now includes a curated ZIM catalog. These are optional downloads; OUTPOST never fetches them automatically. Download a selected archive, move the resulting `.zim` file into `data/zim/`, then press **Scan archives**. The suggested broad-coverage set is Simple English Wikipedia (full text, no images), WikiMed (no images), and English Wikipedia Top (mini summaries). Astronomy is an optional larger subject pack. The catalog sizes are approximate and can change when Kiwix republishes an archive. The full English Wikipedia is far larger than 5 GB; Kiwix's `mini`, `nopic`, and `maxi` editions have substantially different coverage and size. See the [Kiwix FAQ](https://get.kiwix.org/en/faq/) for edition definitions.

ZIM archives are user data and are excluded from Git. Keep only the packs you actually need; the app and reader do not need to be duplicated inside each archive.


## Compact encyclopedia workflow (0.7.0)

1. Download a Wikimedia **pages-articles** XML dump (not a full revision-history dump) separately. The file may be plain `.xml`, `.xml.bz2`, or `.xml.gz`.
2. Keep the dump in a folder you explicitly added under Settings. OUTPOST never downloads it for you.
3. In Offline library, enter the full local path and start the import. It streams pages in batches, keeps main-namespace article text, removes most templates/markup and media, and stores compressed article bodies in a separate SQLite database.
4. Search uses article titles and introductions to stay compact. Open an article to read its stored body.
5. To retain selected illustrations, prepare your own ZIP of chosen JPG/PNG/WebP/GIF images and import it in the same panel. OUTPOST accepts at most 120 images / 150 MB total and rejects SVG/script formats. Only matching article image references are shown.

The 10 GiB cap is a safety ceiling, **not a promise that all English Wikipedia article text will fit**. The import result on your device determines coverage and actual size. The source dump and resulting database coexist during import, so ensure ample free storage before starting. The current importer is an initial practical pipeline; test it on a small XML sample before attempting a multi-gigabyte dump.


## OUTPOST 0.8.0 additions

The Knowledge Search page now has a dedicated Uplink passage index. After indexing your selected folders in Settings, choose **Build / refresh passages**; OUTPOST chunks documents locally, detects changed source text and rebuilds only what needs updating. Search results include their original local paths for source checking.

The Security Desk now includes the offline BugHunter review playbooks, automatic decoding candidates, and a Termux command reference with availability checks. These are native, dependency-light additions. OUTPOST deliberately does not execute Termux commands, imported scripts, exploit code or remote tests.

**Integration note:** this is a native, selective feature integration, not a full merge of all upstream codebases. Kiwix JS's standard ZIM reader runtime remains the largest outstanding gap; see [INTEGRATIONS.md](INTEGRATIONS.md) for precise boundaries.


## Full Kiwix JS reader bundle

OUTPOST now includes `scripts/install_kiwix.py`. In Termux, run:

```sh
cd ~/Outpost
python scripts/install_kiwix.py
```

The installer asks before making a one-time online download, fetches the official Kiwix JS source at a pinned commit, installs the temporary Node build dependencies, and creates a production PWA build under `static/kiwix/`. Temporary source and build dependencies are removed when the installer exits. The generated reader contains libzim WebAssembly and the XZ/Zstandard decoders required for standard ZIM archives. Once installed, launch it from Offline library; it does not require online services to read local archives.

Requirements: Node.js 18.18+ and npm in Termux, and enough temporary storage for the source/build dependency install. The final reader is expected to remain comfortably below OUTPOST's 5 GB app/tools budget; the ZIM content archives are separate user data. The source revision and GPL-3.0 license are recorded in the installed reader folder.


## OUTPOST 0.9.0 — full local integrations

- The full Kiwix JS PWA can now be built and installed locally with `python scripts/install_kiwix.py`. It includes the official libzim WASM runtime and XZ/Zstandard decoders, with the PWA/service-worker directory layout preserved. Generated files stay under gitignored `static/kiwix/`.
- Uplink now includes user feedback on passages, feedback-weighted ranking, an ask queue with resolution notes, saved retrieval evaluations (expected-source hit and reciprocal rank), and local JSON reports.
- CyberDesk adds offline text diff, CSV structure summary and JSON structure inspection.


## OUTPOST 0.9.1 consistency fixes

- Uplink passage rebuild now removes stale passages for deleted/emptied documents, refreshes renamed source metadata, and enforces passage limits without deleting valid old results when an update cannot fit. Paragraph chunks remain within the configured size while long paragraphs retain overlap.
- The Wikipedia importer checks the storage ceiling after rebuilding its FTS index and removes failed staging databases.
- Kiwix's pinned build installer now includes the required Babel configuration and applies limits to selected source extraction; source-extraction regression tests were added.
- The CSV inspector now reports malformed CSV input cleanly. Uplink feedback stays attached to the query that produced the displayed results.
- These changes have regression tests in the repository; target-device runtime testing is still required.


## Worldwide Offline Knowledge Plan

The Offline Library's subject map is intentionally global and multidisciplinary. It covers science and mathematics; computing and AI; engineering; health; Earth and geography; world history and culture; economics and business; agriculture and food; survival and practical skills; languages and literature; law and governance; psychology and society; arts and design; transport and exploration; and general reference/research.

### Law and governance: global jurisdiction model

Legal content is not India-centric. Organise it by:
1. **International** — UN treaties and instruments, international organisations and international courts.
2. **Regional** — regional treaties, courts and legal frameworks (for example, European, African, Inter-American and Asia-Pacific systems).
3. **National** — constitutions, statutes, regulations, court decisions and official gazettes for countries worldwide.
4. **Subnational** — state, province, territory and local law where reliable public sources exist.
5. **Comparative and explanatory** — legal research guides and secondary analysis, clearly distinguished from primary law.

Useful research gateways include WorldLII, the UN Treaty Collection, FAOLEX, ILO NORMLEX/NATLEX, WIPO Lex and the Library of Congress Guide to Law Online. These are source gateways, not a guarantee that every jurisdiction's complete or current law is available offline.

**Provenance rule:** every imported legal source should retain its jurisdiction, issuing authority, source URL, document type, publication/effective date when available, and date last checked. Mark superseded or uncertain material. Do not label a partial collection as comprehensive or present it as legal advice.

The map in the Offline Library is a coverage plan and source directory. It does not mean those datasets are already downloaded. ZIM archives and curated packs remain user-selected imports; OUTPOST does not silently download large datasets.

## Expanded offline knowledge library

OUTPOST now ships with built-in, searchable Markdown field guides under `knowledge/`:
- **Global markets and investing:** stocks, bonds, ETFs, exchanges, valuation, financial statements, derivatives, portfolio construction, market structure, fraud checks and data freshness.
- **Personal finance, economics and accounting:** budgeting, debt, interest, inflation, insurance, bookkeeping, macroeconomics and business fundamentals.
- **Computing, networks and cybersecurity:** programming, operating systems, protocols, web architecture, privacy, threat modelling and safe analysis.
- **Science, mathematics and engineering:** scientific method, mathematics, physics, chemistry, biology, climate, energy and engineering practice.
- **World reference and practical knowledge:** health literacy, emergency readiness, geography, world history, global legal systems, agriculture, environment, languages and research skills.
- **Global financial data source directory:** international economic datasets, market regulators, exchange/issuer primary sources and suggested offline datasets.

These are actual local reference files, not just category labels. The existing local Knowledge Search indexes the built-in `knowledge/` folder automatically, and the Offline Library catalog discovers the files. After pulling the repository, restart OUTPOST and search topics such as `P/E ratio`, `bond duration`, `ETF`, `inflation`, `cash flow`, `DNS`, or `climate`.

**Important boundary:** the built-in guides are educational foundations, not a complete encyclopedia, current law database, investment recommendation or live market feed. For live prices and news, an explicitly refreshed data source is required. For offline market research, import licensed historical datasets and preserve their timestamps, currency, venue, provider and licence. OUTPOST does not automatically download large datasets or make market-data API calls.

