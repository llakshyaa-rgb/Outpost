# OUTPOST integration map

OUTPOST is one lightweight local application. The eight selected projects are the design and capability sources for its modules; this repository does not claim to contain eight complete upstream applications. The current implementation is native Python/SQLite and browser UI, with no third-party runtime packages.

| Selected project | Intended capability | Current OUTPOST implementation | Boundary |
|---|---|---|---|
| AFDrive | Local file vault and device-first file management | File archive workspace; explicit-root browsing; metadata; safe previews; SHA-256 | Native implementation, not a vendored AFDrive server |
| Kiwix JS | Offline ZIM reader | Finds .zim archives in data/zim/ and selected roots; provides Kiwix reader handoff | Reader and archive must be obtained separately |
| Personal File Archive | Personal file catalogue | Local file catalogue, metadata and indexed text search | Native implementation; upstream code is not copied |
| Grimoire | Security knowledge and playbooks | Local knowledge/security/ pack is indexed and searchable | Add trusted, licensed source material yourself |
| Termux-Tools | Android terminal environment | Detects Termux, Python, Git and selected installed commands | Read-only diagnostics; no commands or package installs are triggered |
| Uplink | Local document retrieval | SQLite FTS search across selected files, notes and bookmarks, with source paths/snippets | Native local retrieval; no cloud model or network dependency |
| Claude-BugHunter | Bug-hunting methodology / Agent Skills | knowledge/bughunter/ is indexed for offline reference | Skills are not executed; testing must be authorized |
| CyberDesk | Defensive security/file analysis | Security desk, file signature detection, SHA-256 and bounded text previews | Safe static inspection only; no active scanner or file execution |

## Local folders

- data/zim/: place ZIM archives here; large binary files are excluded from Git.
- knowledge/security/: add trusted, licensed Markdown/YAML defensive references.
- knowledge/bughunter/: add optional SKILL.md files and supporting text references.

The built-in knowledge folders are indexed automatically. Other roots must be explicitly added in Settings. Indexing skips hidden dependency directories and oversized files. It does not follow symlinked directories or index files whose resolved paths escape the selected root.

## Offline and safety boundaries

- The core app works without internet after cloning.
- Kiwix requires a separately installed/available reader and previously downloaded ZIM content.
- Grimoire and BugHunter reference material must be imported locally before offline search can find it.
- No selected third-party code is executed automatically.
- The file inspector reads file bytes to identify type and calculate SHA-256; it previews only supported text files and never executes content.
- The Termux adapter reports environment details but does not run shell commands.
- The IP toolbox calculates ranges only; it does not probe or scan networks.
- Check each upstream project's license before copying its code, data or assets.

## Validation still required

The repository's UI and API wiring are committed, but the full runtime must be tested on the target Android/Termux device. In particular, confirm shared-storage permissions, SQLite FTS5 availability, large-folder indexing performance, and Kiwix reader handoff.