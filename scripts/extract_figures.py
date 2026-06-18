#!/usr/bin/env python3
"""
extract_figures.py — pull tight PNGs of every figure out of a paper PDF.

    python scripts/extract_figures.py /tmp/paper.pdf figs/

Strategy (no hardcoded figure lists — everything is auto-detected):
  1. Scan every page's text for figure captions ("Figure N:", "Fig. N.", …).
  2. For each caption, render the page at high DPI and take the band ABOVE the
     caption (and below the previous caption / page top) as the figure region.
  3. Trim surrounding whitespace and save figs/figureN.png.

Requires: PyMuPDF (fitz), Pillow.
    pip install -r scripts/requirements.txt
"""
import io
import os
import re
import sys

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("error: PyMuPDF not installed.  pip install -r scripts/requirements.txt")

from PIL import Image, ImageChops, ImageOps

DPI = 200                      # render resolution
SCALE = DPI / 72.0            # PDF points -> pixels
CAPTION_RE = re.compile(r'^\s*(?:figure|fig\.?)\s*(\d+)\b', re.IGNORECASE)
WHITE_THRESHOLD = 245         # pixels brighter than this count as background


def caption_blocks(page):
    """Yield (fig_number, caption_rect) for every figure caption on the page."""
    out = []
    for block in page.get_text("blocks"):
        x0, y0, x1, y1, text = block[0], block[1], block[2], block[3], block[4]
        m = CAPTION_RE.match(text.strip())
        if m:
            out.append((int(m.group(1)), fitz.Rect(x0, y0, x1, y1)))
    out.sort(key=lambda t: t[1].y0)
    return out


def trim(img, bg_threshold=WHITE_THRESHOLD, pad=10):
    """Crop away uniform white margins, then add a small padding."""
    gray = ImageOps.grayscale(img)
    # Anything darker than threshold is "content".
    mask = gray.point(lambda p: 0 if p >= bg_threshold else 255)
    bbox = mask.getbbox()
    if not bbox:
        return None
    left, top, right, bottom = bbox
    left = max(0, left - pad); top = max(0, top - pad)
    right = min(img.width, right + pad); bottom = min(img.height, bottom + pad)
    return img.crop((left, top, right, bottom))


def render_region(page, rect):
    """Render a PDF rectangle to a Pillow image at DPI."""
    rect = rect & page.rect           # clamp to page
    if rect.is_empty or rect.height < 8:
        return None
    pix = page.get_pixmap(matrix=fitz.Matrix(SCALE, SCALE), clip=rect)
    return Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")


def extract(pdf_path, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    saved = {}

    for page in doc:
        caps = caption_blocks(page)
        prev_bottom = page.rect.y0
        for fig_no, cap_rect in caps:
            # Region: from below the previous caption (or page top) to the top
            # of this caption — i.e. the artwork the caption describes.
            top = prev_bottom
            region = fitz.Rect(page.rect.x0, top, page.rect.x1, cap_rect.y0 - 2)
            img = render_region(page, region)
            prev_bottom = cap_rect.y1
            if img is None:
                continue
            cropped = trim(img)
            if cropped is None or cropped.width < 40 or cropped.height < 40:
                continue
            # Keep the largest candidate if a number appears more than once.
            area = cropped.width * cropped.height
            if fig_no not in saved or area > saved[fig_no][1]:
                saved[fig_no] = (cropped, area)

    if not saved:
        print("no figure captions detected — nothing written.")
        return

    for fig_no in sorted(saved):
        img = saved[fig_no][0]
        path = os.path.join(out_dir, f"figure{fig_no}.png")
        img.save(path, "PNG")
        print(f"wrote {path}  ({img.width}x{img.height})")

    print(f"\n{len(saved)} figure(s) extracted to {out_dir}/")
    print("Review them, then reference the ones you want as {{FIGn}} in the template.")


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: extract_figures.py PAPER.pdf [out_dir=figs/]")
    pdf_path = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "figs"
    if not os.path.isfile(pdf_path):
        sys.exit(f"error: no such file: {pdf_path}")
    extract(pdf_path, out_dir)


if __name__ == "__main__":
    main()
