#!/usr/bin/env python3
"""Build sharp, high-resolution OUTPOST reference backgrounds from the original PDF.

Usage:
  python tools/prepare_reference_assets.py "/path/to/PDF Gallery_20261126_233248.pdf"

The script prefers embedded source images (when the PDF contains them), falls
back to rendering the relevant page region at high DPI, and writes the three
backgrounds used by static/style.css.
"""
from __future__ import annotations
import argparse
import io
from pathlib import Path

import fitz
from PIL import Image, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "static" / "assets"
TARGET = (3840, 2160)

def embedded_landscape(page: fitz.Page) -> Image.Image | None:
    candidates = []
    for info in page.get_images(full=True):
        xref = info[0]
        try:
            raw = page.parent.extract_image(xref)
            im = Image.open(io.BytesIO(raw["image"])).convert("RGB")
            ratio = im.width / max(1, im.height)
            if ratio > 1.45 and im.width >= 900:
                candidates.append((im.width * im.height, im))
        except Exception:
            continue
    return max(candidates, key=lambda x: x[0])[1] if candidates else None

def render_region(page: fitz.Page, rect: fitz.Rect, scale: float = 4.0) -> Image.Image:
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=rect, alpha=False)
    return Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")

def fit_canvas(im: Image.Image, size=TARGET) -> Image.Image:
    # Preserve proportions; do not stretch the artwork. Use a dark blurred
    # extension only where the reference screenshot has a wider aspect ratio.
    w, h = size
    ratio = min(w / im.width, h / im.height)
    nw, nh = round(im.width * ratio), round(im.height * ratio)
    fg = im.resize((nw, nh), Image.Resampling.LANCZOS)
    bg = im.resize(size, Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(42))
    bg = ImageEnhance.Brightness(bg).enhance(0.28)
    bg.paste(fg, ((w - nw) // 2, (h - nh) // 2))
    return bg

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", type=Path)
    args = ap.parse_args()
    if not args.pdf.is_file():
        raise SystemExit(f"PDF not found: {args.pdf}")
    doc = fitz.open(args.pdf)
    if len(doc) < 3:
        raise SystemExit("Expected the 3-page OUTPOST reference PDF.")
    ASSET_DIR.mkdir(parents=True, exist_ok=True)

    # The supplied reference PDF places each wide UI screenshot centrally on
    # its page. Crop away the white paper margins before upscaling.
    regions = {
        "reference-home.jpg": (0, fitz.Rect(24, 450, 1000, 1000)),
        "reference-command.jpg": (1, fitz.Rect(24, 450, 1000, 1000)),
        "reference-settings.jpg": (2, fitz.Rect(24, 720, 1000, 1165)),
    }
    for filename, (page_index, rect) in regions.items():
        page = doc[page_index]
        im = embedded_landscape(page)
        if im is None:
            im = render_region(page, rect, scale=4.0)
        im = fit_canvas(im)
        im = ImageEnhance.Sharpness(im).enhance(1.18)
        im = ImageEnhance.Contrast(im).enhance(1.02)
        dest = ASSET_DIR / filename
        im.save(dest, "JPEG", quality=96, subsampling=0, optimize=True, progressive=True)
        print(f"{dest.relative_to(ROOT)}  {im.width}x{im.height}  {dest.stat().st_size:,} bytes")

if __name__ == "__main__":
    main()
