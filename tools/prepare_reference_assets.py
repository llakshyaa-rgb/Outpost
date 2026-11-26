#!/usr/bin/env python3
"""Extract and upscale the EXACT three OUTPOST screens embedded in the supplied PDF.

Usage:
  python tools/prepare_reference_assets.py "/path/to/PDF Gallery_20261126_233248.pdf"

Writes 3840px-wide originals into static/assets using the filenames already used
by the app. This does not generate replacement artwork.
"""
from __future__ import annotations
import argparse, io
from pathlib import Path
import fitz
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "static" / "assets"

def embedded(page: fitz.Page) -> Image.Image:
    choices = []
    for info in page.get_images(full=True):
        data = page.parent.extract_image(info[0])
        im = Image.open(io.BytesIO(data["image"])).convert("RGB")
        choices.append((im.width * im.height, im))
    if not choices:
        raise RuntimeError("No embedded reference image found on PDF page")
    return max(choices, key=lambda x: x[0])[1]

def save_uhd(im: Image.Image, path: Path, canvas_16_9: bool = False) -> None:
    width = 3840
    height = round(width * im.height / im.width)
    im = im.resize((width, height), Image.Resampling.LANCZOS)
    if canvas_16_9:
        canvas = Image.new("RGB", (3840, 2160), (5, 4, 9))
        canvas.paste(im, (0, (2160 - height) // 2))
        im = canvas
    im = im.filter(ImageFilter.UnsharpMask(radius=1.4, percent=115, threshold=3))
    im.save(path, "JPEG", quality=96, subsampling=0, optimize=True, progressive=True)
    print(f"{path.relative_to(ROOT)}: {im.width}x{im.height}, {path.stat().st_size:,} bytes")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args()
    doc = fitz.open(args.pdf)
    if len(doc) < 3:
        raise SystemExit("The original reference PDF must contain at least 3 pages.")
    ASSETS.mkdir(parents=True, exist_ok=True)
    home = embedded(doc[0])
    command = embedded(doc[1])
    composite = embedded(doc[2])
    if composite.width < 700 or composite.height < 600:
        raise SystemExit("Unexpected third-page reference dimensions; refusing inaccurate crop.")
    # Third page is an exact vertical composite: command on top, settings below.
    split = composite.height // 2
    settings = composite.crop((0, split, composite.width, composite.height))
    save_uhd(home, ASSETS / "reference-home.jpg", canvas_16_9=True)
    save_uhd(command, ASSETS / "reference-command.jpg", canvas_16_9=True)
    save_uhd(settings, ASSETS / "reference-settings.jpg")

if __name__ == "__main__":
    main()
