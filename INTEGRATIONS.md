# OUTPOST — offline integration map

OUTPOST is a native local application, not a launcher for eight online services. The following upstream repositories were checked to understand their actual capabilities. Their full source trees are **not** vendored into this repository; compatible offline features are being implemented natively. This avoids silently importing incompatible runtimes or unreviewed scripts.

| Selected project | Upstream capability | OUTPOST offline implementation | Still not bundled |
|---|---|---|---|
| AFDrive — [ashwithfrank/AFDrive](https://github.com/ashwithfrank/AFDrive) | Termux-hosted personal file cloud, safe file handling, uploads/downloads, folders | Local folder browser, create folder, upload/download, rename/copy/delete, ZIP create/extract, duplicate detection, metadata and safe path checks | Login-protected LAN cloud server and multi-device access are intentionally excluded |
| Kiwix JS — [kiwix/kiwix-js](https://github.com/kiwix/kiwix-js) | Portable JavaScript ZIM reader / PWA | Local .zim archive discovery | Reader assets and in-app ZIM rendering; no remote PWA link in offline mode |
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
- Online OSINT, remote recon, live target testing, remote corpus sync and online reader handoffs are left out until requested.

## Device validation

The current branch has not yet been runtime-tested on the target Android/Termux device. Test folder permissions, uploads/downloads, FTS5, optional document extractors, large imports and large-folder indexing before relying on it for important files.
