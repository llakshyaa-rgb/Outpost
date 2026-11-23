# OUTPOST — offline integration map

OUTPOST is a native local application, not a launcher for eight online services. The following upstream repositories were checked to understand their actual capabilities. Their full source trees are **not** vendored into this repository; compatible offline features are being implemented natively. This avoids silently importing incompatible runtimes or unreviewed scripts.

| Selected project | Upstream capability | OUTPOST offline implementation | Still not bundled |
|---|---|---|---|
| AFDrive — [ashwithfrank/AFDrive](https://github.com/ashwithfrank/AFDrive) | Termux-hosted personal file cloud, safe file handling, uploads/downloads, folders | Local folder browser, create folder, upload/download, rename/copy (including bounded directory trees)/move/delete, ZIP create/extract, duplicate detection, metadata and safe path checks | Login-protected LAN cloud server and multi-device access are intentionally excluded |
| Kiwix JS — [kiwix/kiwix-js](https://github.com/kiwix/kiwix-js) | Portable JavaScript ZIM reader / PWA | Local .zim discovery and optional `kiwix-serve` handoff on loopback; separate native XML-to-compressed-SQLite Wikipedia importer and local reader | Kiwix JS PWA assets / WASM runtime are not bundled; standard ZIM reading still needs local `kiwix-serve`; no ZIM content downloads |
| Personal File Archive — [kevin0309/PersonalFileArchive](https://github.com/kevin0309/PersonalFileArchive) | Java/Tomcat web archive with upload/download and database-backed management | Native file catalogue and archive operations | Original Java/Tomcat runtime; it is not a suitable drop-in for the stdlib Termux app |
| Grimoire — [PentHertz/grimoire](https://github.com/PentHertz/grimoire) | Offline full-text search across cloned security knowledge bases, with provenance and document viewer | Local ZIP knowledge-pack import, local indexing/search, in-app reference reader and file catalog | Remote corpus fetching, full source catalog and original rich document viewer |
| Termux-Tools — [termux/termux-tools](https://github.com/termux/termux-tools) | Scripts and small programs shipped by Termux | Read-only Termux/runtime/command diagnostics | Replacing Termux's own package scripts or automatically running shell commands |
| Uplink — [evanderpool/uplink](https://github.com/evanderpool/uplink) | Local SQLite retrieval for Markdown/PDF/Word/Excel/CSV, chunking, BM25 and evaluation | Local SQLite FTS retrieval, snippets/source paths, optional PDF/DOCX/XLSX/XLS extraction | Original chunk-level schema, evaluation harness, feedback loop and report suite |
| Claude-BugHunter — [elementalsouls/Claude-BugHunter](https://github.com/elementalsouls/Claude-BugHunter) | Agent Skill bundle, vulnerability research patterns and authorized testing workflows | Import and search local SKILL.md, scripts and reference docs; imported code is not executed | Agent runtime, slash commands, Burp integration, remote report refresh and active testing automation |
| CyberDesk — [JerenzeLevi/cyberdesk](https://github.com/JerenzeLevi/cyberdesk) | Local CTF/security dashboard spanning forensics, crypto, reverse engineering, web and OSINT | Offline file triage, magic signatures, hashes, entropy, strings, ZIP audit, IOC extraction, unverified JWT decoding, hash-format hints, classical ciphers, single-byte XOR analysis and text transforms | Online OSINT/recon, active web testing, binary exploitation, blockchain RPC, heavy external-tool integrations |

## Additional local utilities

- Create ZIP archives from selected files and safely extract ZIP archives into a new folder. Extraction rejects traversal and symlink entries and applies expanded-size, entry-count and compression-ratio limits.
- Duplicate detection hashes same-size files in configured roots; scan is capped at 5,000 files / 1 GB.
- Offline IOC extraction identifies candidate IPv4 addresses, domains, URLs, email addresses and common hash lengths. It does not check reputation or contact any service.
- JWT decoder displays header and claims only; it does not validate signatures or trust decoded claims.
- Knowledge references can be opened and read inside OUTPOST.

## Local folders

- `data/zim/`: local ZIM archives.
- `data/wiki/wiki.db`: compressed text-only encyclopedia.
- `data/wiki/images/`: optional curated raster illustrations.
- `knowledge/security/`: trusted defensive references.
- `knowledge/bughunter/`: Agent Skills and supporting local references.
- `knowledge/imported/`: contents imported from local ZIP knowledge packs.

Other folders must be explicitly selected in Settings. Indexing skips hidden dependency directories, symlinked paths and oversized files.

## Upstream licensing notes

The inspected repository metadata identifies Kiwix JS and Termux-Tools as GPL-3.0, Grimoire and Uplink as MIT, Personal File Archive as MIT, and Claude-BugHunter as MIT (with a separate content license/notice). AFDrive did not expose a declared license in the inspected repository metadata, and CyberDesk did not declare a license there. OUTPOST currently does not copy upstream source code or assets. Do not vendor code or datasets from repositories without checking their actual license and content terms first.

## Offline and safety boundary

- No cloud account, remote API, telemetry, CDN or external network request is required at runtime.
- No whole-device scan; only configured roots and OUTPOST's own knowledge folders are indexed.
- Imported scripts are reference material only and are never run.
- The file inspector and CyberDesk-inspired tools are static/offline.
- Network calculations do not probe hosts.
- Online OSINT, remote recon, live target testing, remote corpus sync and remote reader handoffs are left out; the optional Kiwix server is local-only.

## Device validation

The current branch has not yet been runtime-tested on the target Android/Termux device. Test folder permissions, uploads/downloads, FTS5, optional document extractors, large imports and large-folder indexing before relying on it for important files.


## 0.5.0 implementation notes

The lightweight integration modules in `outpost_modules/` are first-party OUTPOST code using Python's standard library. `retrieval.py` supplies safe FTS query construction and bounded overlapping passages. `cyberdesk.py` supplies static string extraction, hex display, embedded signature detection, ELF/PE header parsing and classic PCAP metadata parsing. The UI exposes these tools through the existing local security endpoint.

The `knowledge/bughunter/CLAUDE_BUGHUNTER_INDEX.md` file is adapted from the upstream skill index only; see `ATTRIBUTION.txt`. It is a searchable reference catalog, not a claim that all original skill files are bundled. Kiwix JS's complete PWA runtime is not vendored. If `kiwix-serve` is already installed, OUTPOST can launch it for a selected local ZIM file, bound only to `127.0.0.1`; it is stopped when OUTPOST exits. No automatic install or download occurs.


## 0.5.0 native capability expansion

- AFDrive-style directory copying is bounded to 2,000 files / 300 MB, skips symlinks, and supports moves within configured roots.
- Kiwix can hand a selected local ZIM archive to an already-installed `kiwix-serve`; the child process binds to loopback and is terminated when OUTPOST exits. It is optional and never installed automatically.
- CyberDesk's PE parser lists bounded section metadata. Classic PCAP inspection summarizes up to 100 packets and decodes Ethernet, IPv4/IPv6, TCP and UDP headers without external libraries. PCAPNG remains header-detection only.
- Regression tests cover PCAP packet decoding and PE section parsing. Run `python -m unittest discover -s tests -v` on the device before relying on the build.


## Kiwix content catalog (OUTPOST 0.6.0)

The Offline library view offers four optional curated ZIM downloads: Simple English Wikipedia full-text/no-images (about 1.0 GiB), WikiMed full-text/no-images (about 822 MiB), English Wikipedia Top mini (about 283 MiB), and an Astronomy maxi pack (about 1.6 GiB). Sizes are estimates and should be checked at download time. The catalog is a set of direct Kiwix download links, not bundled content. The user explicitly initiates each download in their browser and manually places the file in `data/zim/`. This avoids background network activity, silent multi-gigabyte downloads, and Git repository bloat. The full English Wikipedia does not fit a 5 GB budget: Kiwix's current full English editions are much larger. See the official [Kiwix FAQ](https://get.kiwix.org/en/faq/) for mini/nopic/maxi differences.


## Compact encyclopedia implementation (0.7.0)

The Offline library includes a native streaming importer for Wikimedia pages-articles XML, plain or gzip/bzip2 compressed. It stores main-namespace article bodies compressed with zlib in a dedicated SQLite database, strips most templates and presentation markup, and indexes titles plus lead text for low-footprint search. It records selected diagram/map/technical image references but does not fetch images. Users may import a hand-picked local ZIP of raster images; the importer caps it at 120 images / 150 MB and excludes SVG. The encyclopedia database has a 10 GiB ceiling. Full-coverage size and completeness are unknown until a real dump is imported and measured; no 7–10 GiB all-article guarantee is made.
