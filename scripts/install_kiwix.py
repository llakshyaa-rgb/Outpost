#!/usr/bin/env python3
"""Install the pinned, official Kiwix JS PWA into OUTPOST for offline use.

This is a one-time online bootstrap. After installation, the reader and all
its JS/WASM assets are served from OUTPOST's own static directory.
"""
from __future__ import annotations
import hashlib, os, shutil, subprocess, sys, tempfile, urllib.request, zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/"static"/"kiwix"
COMMIT="e809ccd993cca12ded4dfc40b9ad79233ed71a19"
ARCHIVE=f"https://codeload.github.com/kiwix/kiwix-js/zip/{COMMIT}"
MAX_ARCHIVE=120*1024*1024
MAX_BUNDLE=180*1024*1024

def main():
    if DEST.joinpath("www","index.html").is_file():
        print("Kiwix reader is already installed at",DEST)
        print("Delete static/kiwix only if you intentionally want to reinstall.")
        return 0
    if not sys.stdin.isatty():
        print("Run this installer interactively so you can approve the one-time download/build.",file=sys.stderr)
        return 2
    print("This installs the official Kiwix JS reader (GPL-3.0) at a pinned commit.")
    print("It downloads source and npm build dependencies once; after installation,")
    print("the reader runs locally and does not need online services.")
    answer=input("Continue with the one-time download and build? [y/N] ").strip().lower()
    if answer not in {"y","yes"}: print("Cancelled."); return 1
    if shutil.which("node") is None or shutil.which("npm") is None:
        print("Node.js 18.18+ and npm are required. Install them in Termux, then rerun.",file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="outpost-kiwix-") as td:
        tmp=Path(td); archive=tmp/"kiwix.zip"
        req=urllib.request.Request(ARCHIVE,headers={"User-Agent":"OUTPOST-offline-installer"})
        print("Downloading pinned Kiwix JS source…")
        with urllib.request.urlopen(req,timeout=45) as response, archive.open("wb") as out:
            total=0
            while True:
                chunk=response.read(1024*1024)
                if not chunk: break
                total+=len(chunk)
                if total>MAX_ARCHIVE: raise RuntimeError("Kiwix source archive exceeded 120 MiB safety limit")
                out.write(chunk)
        source=tmp/"source"; source.mkdir()
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                name=info.filename
                parts=Path(name).parts
                if len(parts)<2: continue
                relative=Path(*parts[1:])
                if relative.is_absolute() or ".." in relative.parts: raise RuntimeError("Unsafe path in source archive")
                # Only the build inputs and upstream source are extracted.
                if not (str(relative).startswith(("www/","i18n/","_locales/","archives/")) or
                        relative.name.startswith("manifest.") or relative.name in {"package.json","package-lock.json","rollup.config.js","LICENSE-GPLv3.txt","CHANGELOG.md","service-worker.js","replayWorker.js","index.html","backgroundscript.js"}):
                    continue
                target=source/relative
                if info.is_dir(): target.mkdir(parents=True,exist_ok=True); continue
                target.parent.mkdir(parents=True,exist_ok=True)
                with z.open(info) as src, target.open("wb") as dst: shutil.copyfileobj(src,dst)
        print("Installing pinned build dependencies (this is temporary)…")
        subprocess.run(["npm","ci","--no-audit","--no-fund"],cwd=source,check=True)
        print("Building the production Kiwix JS reader…")
        subprocess.run(["npm","run","build-min"],cwd=source,check=True)
        built=source/"dist"
        if not (built/"www"/"index.html").is_file() or not (built/"www"/"js"/"bundle.min.js").is_file() or not (built/"service-worker.js").is_file():
            raise RuntimeError("Kiwix build did not produce the expected PWA entry files")
        size=sum(p.stat().st_size for p in built.rglob("*") if p.is_file())
        if size>MAX_BUNDLE: raise RuntimeError(f"Built reader is too large ({size} bytes); refusing to install")
        # Stage the complete upstream dist layout atomically. The PWA lives in
        # /kiwix/www/ and its service worker in /kiwix/ so precache paths resolve.
        staging=DEST.with_name("kiwix.installing")
        if staging.exists(): shutil.rmtree(staging)
        shutil.copytree(built,staging)
        license_src=source/"LICENSE-GPLv3.txt"
        if license_src.is_file(): shutil.copy2(license_src,staging/"LICENSE-GPLv3.txt")
        (staging/"OUTPOST-KIWIX-SOURCE.txt").write_text(
            "Kiwix JS upstream: https://github.com/kiwix/kiwix-js\\n"
            f"Pinned source commit: {COMMIT}\\n"
            "License: GNU GPL version 3 (see LICENSE-GPLv3.txt)\\n"
            "This directory is the upstream production build. OUTPOST tightens the entry-page CSP to local-only resource origins.\\n",
            encoding="utf-8")
        # Force local-only resource loading and remove the root-level manifest URL.
        index=staging/"www"/"index.html"
        html=index.read_text(encoding="utf-8")
        import re
        html=re.sub(r'<meta http-equiv="Content-Security-Policy"[^>]*>',
            '<meta http-equiv="Content-Security-Policy" content="default-src \\'self\\' data: file: blob: about:; script-src \\'self\\' \\'unsafe-inline\\' \\'unsafe-eval\\' \\'wasm-unsafe-eval\\' blob:; style-src \\'self\\' \\'unsafe-inline\\'; img-src \\'self\\' data: file: blob:; font-src \\'self\\' data:; connect-src \\'self\\'; worker-src \\'self\\' blob:; frame-src \\'self\\'; object-src \\'none\\';">',html,count=1,flags=re.I)
        html=re.sub(r"<link[^>]+rel=[\"']manifest[\"'][^>]*>", '',html,flags=re.I)
        html=html.replace('href="../node_modules/bootstrap/dist/css/bootstrap.min.css"','href="css/bootstrap.min.css"')
        index.write_text(html,encoding="utf-8")
        os.replace(staging,DEST)
    print("Kiwix JS installed locally:",DEST)
    print("Open OUTPOST → Offline library → Launch bundled Kiwix reader.")
    print("The build folder and npm dependencies were temporary and have been removed.")
    return 0

if __name__=="__main__":
    try: raise SystemExit(main())
    except subprocess.CalledProcessError as e:
        print("Kiwix build failed:",e,file=sys.stderr); raise SystemExit(1)
    except Exception as e:
        print("Kiwix install failed:",e,file=sys.stderr); raise SystemExit(1)
