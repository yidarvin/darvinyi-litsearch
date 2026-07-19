#!/usr/bin/env python3
"""extract_text.py — dump a paper PDF's full text with page markers.

    python3 scripts/extract_text.py work/<slug>/paper.pdf work/<slug>/paper.txt

Used by the /litsearch pipeline (PIPELINE_PLAN.md): the paper-builder agent
extracts paper.txt once per paper, and the paper-critic agent fact-checks the
explainer against it — quoting "paper.txt p.<N>: '...'" in a blocker's
`evidence` field only works if page numbers in the dump match a PDF viewer's
page numbers, so each page's text is preceded by a `--- page N ---` marker
(N = PDF page index + 1, i.e. what a reader would call "page 7").

Requires: PyMuPDF (fitz).  pip install -r scripts/requirements.txt
"""
import sys

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("error: PyMuPDF not installed.  pip install -r scripts/requirements.txt")


def extract(pdf_path, txt_path):
    doc = fitz.open(pdf_path)
    with open(txt_path, "w") as out:
        for i, page in enumerate(doc, start=1):
            out.write(f"--- page {i} ---\n")
            out.write(page.get_text())
            out.write("\n")
    return len(doc)


def main():
    if len(sys.argv) != 3:
        sys.exit(f"usage: {sys.argv[0]} <paper.pdf> <paper.txt>")
    n = extract(sys.argv[1], sys.argv[2])
    print(f"extracted {n} page(s) -> {sys.argv[2]}")


if __name__ == "__main__":
    main()
