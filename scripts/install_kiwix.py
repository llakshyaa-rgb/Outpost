#!/usr/bin/env python3
"""Install the pinned official Kiwix JS PWA into OUTPOST for offline use.

This is a one-time online bootstrap. The installed reader is served locally.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "static" / "kiwix"
COMMIT = "e809ccd993cca12ded4dfc40b9ad79233ed71a19"
ARCHIVE = f"https://codeload.github.com/kiwix/kiwix-js/zip/{COMMIT}"
MAX_ARCHIVE = 120 * 1024 * 1024
MAX_BUNDLE = 180 * 1024 * 1024
MAX_EXTRACTED_SOURCE = 350 * 1024 * 1024
MAX_SOURCE_FILES = 12000


def node_version():
    output = subprocess.check_output(["node", "--version"], text=True).strip()
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+).*", output)
    if not match:
        raise RuntimeError(f"Could not parse Node.js version: {output}")
    return tuple(map(int, match.groups()))


def extract_source(archive: Path, source: Path):
    source.mkdir()
    allowed_roots = ("www/", "i18n/", "_locales/", "archives/")
    allowed_files = {
        "package.json", "package-lock.json", "rollup.config.js", "babel.config.js",
        "LICENSE-GPLv3.txt", "CHANGELOG.md", "service-worker.js",
        "replayWorker.js", "index.html", "backgroundscript.js",
    }
    extracted = 0
    copied = 0
    with zipfile.ZipFile(archive) as bundle:
        infos = bundle.infolist()
        if len(infos) > MAX_SOURCE_FILES:
            raise RuntimeError("Upstream archive contains too many entries")
        for info in infos:
            parts = Path(info.filename).parts
            if len(parts) < 2:
                continue
            relative = Path(*parts[1:])
            if relative.is_absolute() or ".." in relative.parts:
                raise RuntimeError("Unsafe path in upstream source archive")
            if not (str(relative).startswith(allowed_roots)
                    or relative.name.startswith("manifest.")
                    or relative.name in allowed_files):
                continue
            if info.is_dir():
                (source / relative).mkdir(parents=True, exist_ok=True)
                continue
            extracted += info.file_size
            copied += 1
            if extracted > MAX_EXTRACTED_SOURCE:
                raise RuntimeError("Selected Kiwix source files exceed the 350 MiB extraction limit")
            if copied > MAX_SOURCE_FILES:
                raise RuntimeError("Selected Kiwix source contains too many files")
            target = source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(info) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)


def install_bundle(built: Path, source: Path):
    required = (
        built / "www" / "index.html",
        built / "www" / "js" / "bundle.min.js",
        built / "service-worker.js",
    )
    if not all(path.is_file() for path in required):
        raise RuntimeError("Kiwix build did not produce the expected PWA entry files")
    size = sum(p.stat().st_size for p in built.rglob("*") if p.is_file())
    if size > MAX_BUNDLE:
        raise RuntimeError(f"Built reader is too large ({size} bytes); refusing to install")

    staging = DEST.with_name("kiwix.installing")
    backup = DEST.with_name("kiwix.previous")
    for stale in (staging, backup):
        if stale.exists():
            shutil.rmtree(stale)
    shutil.copytree(built, staging)
    license_src = source / "LICENSE-GPLv3.txt"
    if license_src.is_file():
        shutil.copy2(license_src, staging / "LICENSE-GPLv3.txt")
    (staging / "OUTPOST-KIWIX-SOURCE.txt").write_text(
        "Kiwix JS upstream: https://github.com/kiwix/kiwix-js\n"
        f"Pinned source commit: {COMMIT}\n"
        "License: GNU GPL version 3 (see LICENSE-GPLv3.txt)\n"
        "Generated locally by OUTPOST's installer.\n",
        encoding="utf-8",
    )

    index = staging / "www" / "index.html"
    html = index.read_text(encoding="utf-8")
    csp = (
        '<meta http-equiv="Content-Security-Policy" content="default-src \'self\' data: file: blob: about:; '
        'script-src \'self\' \'unsafe-inline\' \'unsafe-eval\' \'wasm-unsafe-eval\' blob:; '
        'style-src \'self\' \'unsafe-inline\'; img-src \'self\' data: file: blob:; '
        'font-src \'self\' data:; connect-src \'self\'; worker-src \'self\' blob:; '
        'frame-src \'self\'; object-src \'none\';">'
    )
    html, replaced = re.subn(
        r'<meta http-equiv="Content-Security-Policy"[^>]*>', csp, html,
        count=1, flags=re.I,
    )
    if replaced == 0:
        html = html.replace("</head>", csp + "</head>", 1)
    html = re.sub(r"<link[^>]+rel=[\"']manifest[\"'][^>]*>", "", html, flags=re.I)
    html = html.replace(
        'href="../node_modules/bootstrap/dist/css/bootstrap.min.css"',
        'href="css/bootstrap.min.css"',
    )
    index.write_text(html, encoding="utf-8")

    # Keep a previous valid install until the new staged tree is ready.
    moved_old = False
    try:
        if DEST.exists():
            os.replace(DEST, backup)
            moved_old = True
        os.replace(staging, DEST)
        if backup.exists():
            shutil.rmtree(backup)
    except Exception:
        if DEST.exists() and moved_old:
            shutil.rmtree(DEST)
        if moved_old and backup.exists():
            os.replace(backup, DEST)
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def main():
    if (DEST / "www" / "index.html").is_file():
        print("Kiwix reader is already installed at", DEST)
        print("Remove static/kiwix only if you intentionally want to reinstall.")
        return 0
    if not sys.stdin.isatty():
        print("Run interactively to approve the one-time download and build.", file=sys.stderr)
        return 2
    if shutil.which("node") is None or shutil.which("npm") is None:
        print("Node.js 18.18+ and npm are required. Install them in Termux, then rerun.", file=sys.stderr)
        return 2
    version = node_version()
    if version < (18, 18, 0):
        print(f"Node.js 18.18+ is required; found {'.'.join(map(str, version))}.", file=sys.stderr)
        return 2

    print("This installs official Kiwix JS (GPL-3.0) at a pinned upstream commit.")
    print("Only the one-time bootstrap downloads source and npm dependencies.")
    answer = input("Continue with the one-time download and build? [y/N] ").strip().lower()
    if answer not in {"y", "yes"}:
        print("Cancelled.")
        return 1

    with tempfile.TemporaryDirectory(prefix="outpost-kiwix-") as td:
        tmp = Path(td)
        archive = tmp / "kiwix.zip"
        request = urllib.request.Request(ARCHIVE, headers={"User-Agent": "OUTPOST-offline-installer"})
        print("Downloading pinned Kiwix JS source…")
        with urllib.request.urlopen(request, timeout=45) as response, archive.open("wb") as out:
            total = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_ARCHIVE:
                    raise RuntimeError("Kiwix source archive exceeded 120 MiB safety limit")
                out.write(chunk)

        source = tmp / "source"
        extract_source(archive, source)
        print("Installing temporary npm build dependencies…")
        subprocess.run(["npm", "ci", "--no-audit", "--no-fund"], cwd=source, check=True)
        print("Building production Kiwix JS reader…")
        subprocess.run(["npm", "run", "build-min"], cwd=source, check=True)
        install_bundle(source / "dist", source)

    print("Kiwix JS installed locally:", DEST)
    print("Open OUTPOST → Offline library → Launch bundled Kiwix reader.")
    print("Temporary source and npm dependencies have been removed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print("Kiwix build failed:", exc, file=sys.stderr)
        raise SystemExit(1)
    except Exception as exc:
        print("Kiwix install failed:", exc, file=sys.stderr)
        raise SystemExit(1)
