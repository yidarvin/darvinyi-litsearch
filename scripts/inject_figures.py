#!/usr/bin/env python3
"""
inject_figures.py — base64-inline figures into a filled explainer page.

    python scripts/inject_figures.py public/papers/<slug>.html figs/

Replaces every {{FIGn}} placeholder in the HTML with a self-contained
`data:` URI built from figs/figureN.png:
  - oversized images are downscaled (max width 1400 px),
  - photo-heavy figures are encoded as JPEG, line art / charts as PNG,
  - the result is written back (in place, or to --out),
  - the script asserts no `{{FIG` placeholder remains.

Requires: Pillow.   pip install -r scripts/requirements.txt
"""
import argparse
import base64
import io
import os
import re
import sys

from PIL import Image

MAX_W = 1400          # downscale anything wider than this
PNG_BUDGET = 350_000  # if PNG bytes exceed this, fall back to JPEG
JPEG_Q = 85

FIG_RE = re.compile(r"\{\{FIG(\d+)\}\}")


def is_photographic(img):
    """Heuristic: many unique colors / smooth gradients => encode as JPEG."""
    small = img.convert("RGB").resize((64, 64))
    colors = small.getcolors(maxcolors=64 * 64)
    return colors is None or len(colors) > 1500


def encode(path):
    img = Image.open(path)
    if img.width > MAX_W:
        h = round(img.height * MAX_W / img.width)
        img = img.resize((MAX_W, h), Image.LANCZOS)

    # Try PNG first (crisp for charts / line art).
    png_buf = io.BytesIO()
    img.convert("RGB").save(png_buf, "PNG", optimize=True)
    png_bytes = png_buf.getvalue()

    if len(png_bytes) <= PNG_BUDGET and not is_photographic(img):
        mime, raw = "image/png", png_bytes
    else:
        jpg_buf = io.BytesIO()
        img.convert("RGB").save(jpg_buf, "JPEG", quality=JPEG_Q, optimize=True)
        jpg_bytes = jpg_buf.getvalue()
        # use whichever is smaller
        if len(jpg_bytes) < len(png_bytes):
            mime, raw = "image/jpeg", jpg_bytes
        else:
            mime, raw = "image/png", png_bytes

    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{b64}", len(raw), mime


def main():
    ap = argparse.ArgumentParser(description="Base64-inline {{FIGn}} placeholders.")
    ap.add_argument("html", help="filled explainer HTML (e.g. public/papers/<slug>.html)")
    ap.add_argument("figs", nargs="?", default="figs", help="figures dir (default: figs/)")
    ap.add_argument("--out", help="output path (default: in place)")
    args = ap.parse_args()

    if not os.path.isfile(args.html):
        sys.exit(f"error: no such file: {args.html}")

    with open(args.html, encoding="utf-8") as f:
        html = f.read()

    wanted = sorted(set(int(n) for n in FIG_RE.findall(html)))
    if not wanted:
        print("no {{FIGn}} placeholders found — nothing to inject.")
    for n in wanted:
        path = os.path.join(args.figs, f"figure{n}.png")
        if not os.path.isfile(path):
            sys.exit(f"error: {{{{FIG{n}}}}} used but {path} is missing.")
        uri, nbytes, mime = encode(path)
        html = html.replace(f"{{{{FIG{n}}}}}", uri)
        print(f"FIG{n}: {path} -> {mime}, {nbytes/1024:.0f} KB inlined")

    # Safety: no stray figure placeholders may survive.
    leftover = re.search(r"\{\{FIG", html)
    if leftover:
        sys.exit(f"error: unreplaced placeholder near: {html[leftover.start():leftover.start()+40]!r}")

    out = args.out or args.html
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\nwrote {out}  ({len(html)/1024:.0f} KB, self-contained)")


if __name__ == "__main__":
    main()
