# OUTPOST module integration map

This file records the eight selected upstream projects and how OUTPOST uses them. OUTPOST remains a single lightweight Python/SQLite application. It does not blindly copy whole upstream applications or execute third-party code.

| Selected project | Upstream | OUTPOST role | Integration |
|---|---|---|---|
| AFDrive | https://github.com/ashwithfrank/AFDrive | Local file vault and safe filesystem patterns | Native file archive view; OUTPOST keeps its own loopback-only server and storage policy rather than importing Flask/auth code wholesale. |
| Kiwix JS | https://github.com/kiwix/kiwix-js | Offline ZIM reader | Detect local .zim archives in data/zim and configured roots; open the official Kiwix reader separately to select the archive. ZIM files are not copied into Git. |
| Personal File Archive | https://github.com/kevin0309/PersonalFileArchive | Personal file catalogue/archive | OUTPOST file catalogue, metadata and inspection layer. Upstream repository is currently minimal; no code is copied. |
| Grimoire | https://github.com/PentHertz/grimoire | Offline searchable security knowledge | Local knowledge/security folder is automatically indexed. Import only trusted, licensed Markdown playbooks; update/download is a separate online step. |
| Termux-Tools | https://github.com/termux/termux-tools | Android environment utilities | Read-only detection of Termux, Python, Git and selected commands. OUTPOST does not execute package-manager commands automatically. |
| Uplink | https://github.com/evanderpool/uplink | Local document retrieval and source-grounded search | OUTPOST reuses the local-first design principles: selected roots, SQLite FTS, source paths and local-only retrieval. Uplink's full Python 3.11+ package is not embedded into this Python 3.10+ stdlib core. |
| Claude-BugHunter | https://github.com/elementalsouls/Claude-BugHunter | Authorized bug-hunting methodology and Agent Skills | Optional local skills in knowledge/bughunter; searchable offline as text. Skills are reference material, not an autonomous scanner. |
| CyberDesk | https://github.com/JerenzeLevi/cyberdesk | Local defensive security/file-analysis workbench | OUTPOST adds safe file metadata, SHA-256 and text preview. No uploaded file is executed and no active scan is launched. |

## Local folders

- `data/zim/`: place ZIM archives here (large archives should not be committed).
- `knowledge/security/`: curated, licensed Markdown/YAML knowledge and playbooks.
- `knowledge/bughunter/`: optional Agent Skills and `SKILL.md` reference material.

These knowledge folders are automatically included in OUTPOST's local text index. Existing selected index roots continue to work.

## Offline and safety boundaries

- Core OUTPOST runs without internet or third-party services.
- Kiwix content must be downloaded separately before it can be read offline.
- Grimoire source repositories must be fetched before their docs can be used offline; only trusted sources should be imported.
- CyberDesk/Claude-BugHunter capabilities are not automatically executed. Use security workflows only against systems you own or are explicitly authorized to test.
- The Termux integration reports what is installed; it does not install packages or run shell commands.
- File inspection is restricted to configured roots plus OUTPOST's knowledge folder. It calculates SHA-256 and previews supported text only.
- Third-party upstream code remains under its own license; check and preserve each license before vendoring code or assets.
