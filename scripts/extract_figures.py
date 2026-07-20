#!/usr/bin/env python3
"""
extract_figures.py — pull tight PNGs of every figure out of a paper PDF.

    python scripts/extract_figures.py /tmp/paper.pdf figs/

Strategy (no hardcoded figure lists — everything is auto-detected):
  1. Scan every page's text for blocks that START with "Figure N" / "Fig. N"
     — this includes both real captions ("Figure 1: Plot shows ...") and
     ordinary in-text prose that merely references a figure ("Figure 1 shows
     a plot of ..."). Both kinds mark a reasonable reading-order boundary on
     the page (see step 2), but only a block whose figure number is
     immediately followed by a caption-style delimiter (":", ".", "|" — how
     essentially every LaTeX/Word caption style formats it) is trusted as
     the actual caption of that figure; a bare space before a lowercase verb
     ("shows", "illustrates", ...) marks prose, not a caption.
  2. For each such block (real or prose-reference), render the page at high
     DPI and take the band ABOVE it (and below the previous such block /
     page top) as a candidate figure region. On a two-column page the region
     is restricted to the block's own column (detected per-page) so the crop
     doesn't bleed into the neighbouring column's text; a block that itself
     spans both columns (e.g. a wide `figure*` caption) falls back to the
     full page width.
  3. Only regions belonging to a REAL caption (step 1's delimiter check) are
     kept as a figure's artwork; prose-reference regions are discarded, but
     still serve their purpose of having advanced the region boundary so the
     next real caption's crop doesn't bleed into whatever text sat between
     them. When a figure number has more than one real-caption candidate
     (rare — e.g. a genuine duplicate), the FIRST one in document order wins,
     since a later match for the same number is far more likely to be a
     stray look-alike that slipped past the delimiter check than the actual
     caption — unlike the old "largest area wins" rule, which could pick a
     spurious, larger, wrong region.
  4. Trim surrounding whitespace and save figs/figureN.png.

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

from PIL import Image, ImageOps

DPI = 200                      # render resolution
SCALE = DPI / 72.0            # PDF points -> pixels
WHITE_THRESHOLD = 245         # pixels brighter than this count as background

# Any block starting with "Figure N" / "Fig. N" — real caption or prose
# reference alike. Used to find every candidate boundary on the page.
LOOSE_CAPTION_RE = re.compile(r'^\s*(?:figure|fig\.?)\s*(\d+)\b', re.IGNORECASE)

# A REAL caption additionally has the figure number immediately followed by
# a delimiter — ":" (the default LaTeX/most-style separator), "." (IEEE-style
# "Fig. 1. Caption"), or "|" (Nature-style "Figure 1 | Caption"). In-text
# prose that merely *mentions* a figure ("Figure 1 shows a plot of ...",
# "Figure 8 illustrates ...") has a plain space (no delimiter) after the
# number and deliberately does NOT match here.
CAPTION_RE = re.compile(r'^\s*(?:figure|fig\.?)\s*(\d+)\s*[:.|]', re.IGNORECASE)

# Sanity cap on a caption-like block's length — guards against a pathological
# merged text block, without excluding legitimately long multi-sentence
# captions (real captions in this codebase's corpus run up to ~1000 chars).
MAX_CAPTION_CHARS = 2000

COLUMN_MARGIN = 8             # pt of slack around a detected gutter midline


def caption_blocks(page, force_real=False):
    """Return (fig_number, caption_rect, is_real) for every block on `page`
    that starts like a figure reference, sorted top-to-bottom (by y0).

    `is_real` is True only when the figure number is immediately followed by
    a caption-style delimiter (see CAPTION_RE) — i.e. this looks like the
    actual caption label, not just in-text prose that happens to reference
    the figure. Every match (real or not) is still returned: even a
    prose-reference block marks a genuine reading-order boundary that the
    caller uses when carving up the page into regions (see page_regions);
    only `is_real` ones are ever saved as a figure's actual artwork.

    `force_real=True` treats every match as real — used as a whole-document
    fallback for a paper whose caption style has no punctuation delimiter at
    all, so it still gets best-effort extraction instead of nothing.
    """
    out = []
    for block in page.get_text("blocks"):
        if len(block) >= 7 and block[6] != 0:
            continue  # skip image blocks — captions/references are text
        x0, y0, x1, y1, text = block[0], block[1], block[2], block[3], block[4]
        stripped = text.strip()
        m = LOOSE_CAPTION_RE.match(stripped)
        if not m or len(stripped) > MAX_CAPTION_CHARS:
            continue
        is_real = force_real or bool(CAPTION_RE.match(stripped))
        out.append((int(m.group(1)), fitz.Rect(x0, y0, x1, y1), is_real))
    out.sort(key=lambda t: t[1].y0)
    return out


def detect_columns(page):
    """Detect a two-column text layout on this page.

    Returns ((left_x0, left_x1), (right_x0, right_x1)) if the page looks
    like a clean two-column layout, else None (single column / unclear —
    callers should fall back to full page width).

    Approach: any text block that is substantial (wide enough to be body
    text, not a stray label) AND clearly straddles the page's vertical
    midline is treated as proof the page's text spans full width — i.e.
    single column (or, for a specific figure, a spanning figure — handled
    separately by the caller). Only when NO such straddling block exists,
    and there is a healthy population of blocks confined to each side with
    a real visual gutter between them, do we call it two-column.
    """
    mid = (page.rect.x0 + page.rect.x1) / 2.0
    blocks = [b for b in page.get_text("blocks") if len(b) < 7 or b[6] == 0]
    substantial = [b for b in blocks if (b[2] - b[0]) > 20 and len(b[4].strip()) > 3]
    if not substantial:
        return None

    for b in substantial:
        x0, x1 = b[0], b[2]
        if (x1 - x0) > 0.35 * page.rect.width and x0 < mid - COLUMN_MARGIN and x1 > mid + COLUMN_MARGIN:
            return None  # a real body block spans across the midline

    left = [b for b in substantial if b[2] <= mid]
    right = [b for b in substantial if b[0] >= mid]
    if len(left) < 3 or len(right) < 3:
        return None  # not enough evidence of two independent columns

    left_x1_max = max(b[2] for b in left)
    right_x0_min = min(b[0] for b in right)
    if right_x0_min - left_x1_max < 4:
        return None  # no real gutter gap

    gutter_mid = (left_x1_max + right_x0_min) / 2.0
    return (page.rect.x0, gutter_mid), (gutter_mid, page.rect.x1)


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


def page_regions(page, force_real=False):
    """Yield (fig_no, cropped_image) for every REAL caption found on `page`,
    in document order. Every figure-reference-shaped block (real or prose)
    advances the region boundary (see module docstring); each region is
    restricted to its own column when the page is two-column (detect_columns)."""
    caps = caption_blocks(page, force_real=force_real)
    if not caps:
        return

    def _finish(region, is_real, fig_no):
        if not is_real:
            return None
        img = render_region(page, region)
        if img is None:
            return None
        cropped = trim(img)
        if cropped is None or cropped.width < 40 or cropped.height < 40:
            return None
        return fig_no, cropped

    columns = detect_columns(page)
    if columns is None:
        prev_bottom = page.rect.y0
        for fig_no, cap_rect, is_real in caps:
            region = fitz.Rect(page.rect.x0, prev_bottom, page.rect.x1, cap_rect.y0 - 2)
            prev_bottom = cap_rect.y1
            result = _finish(region, is_real, fig_no)
            if result is not None:
                yield result
        return

    (lx0, lx1), (rx0, rx1) = columns
    gutter_mid = lx1  # == rx0
    prev_bottom = {"L": page.rect.y0, "R": page.rect.y0}
    for fig_no, cap_rect, is_real in caps:
        spans_both = cap_rect.x0 < gutter_mid - COLUMN_MARGIN and cap_rect.x1 > gutter_mid + COLUMN_MARGIN
        if spans_both:
            top = max(prev_bottom["L"], prev_bottom["R"])
            region = fitz.Rect(page.rect.x0, top, page.rect.x1, cap_rect.y0 - 2)
            prev_bottom["L"] = prev_bottom["R"] = cap_rect.y1
        else:
            side = "L" if cap_rect.x1 <= gutter_mid + COLUMN_MARGIN else "R"
            x0, x1 = (lx0, lx1) if side == "L" else (rx0, rx1)
            region = fitz.Rect(x0, prev_bottom[side], x1, cap_rect.y0 - 2)
            prev_bottom[side] = cap_rect.y1

        result = _finish(region, is_real, fig_no)
        if result is not None:
            yield result


def run_pass(doc, force_real=False):
    """One full pass over the document. Keeps the FIRST real candidate seen
    for each figure number (document order — page order, then top-to-bottom
    within a page) rather than the largest, since a later match for the same
    number is far more likely to be a stray look-alike than the real caption."""
    saved = {}
    for page in doc:
        for fig_no, cropped in page_regions(page, force_real=force_real):
            if fig_no not in saved:
                saved[fig_no] = cropped
    return saved


def extract(pdf_path, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    doc = fitz.open(pdf_path)

    saved = run_pass(doc, force_real=False)
    if not saved:
        print("no strict-format captions detected — treating every figure reference as real.")
        saved = run_pass(doc, force_real=True)

    if not saved:
        print("no figure captions detected — nothing written.")
        return

    for fig_no in sorted(saved):
        img = saved[fig_no]
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
