"""Shared LaTeX-escaping helper for the survey PDF pipeline (tokens_to_tex.py,
make_bib.py). Any text pulled from JSON data (paper titles, author names,
computed stats) can contain characters LaTeX treats specially — `%` starts a
comment, `&` is a table column separator, `$` toggles math mode, `_`/`^` are
math sub/superscripts, `#` is a macro parameter marker — and real paper
titles in this corpus hit several of these (e.g. "SWE-Lancer: Can Frontier
LLMs Earn $1 Million...", "GPQA: A Graduate-Level Google-Proof Q&A
Benchmark"). They can also contain Unicode symbols the default Latin Modern
font has no glyph for in text mode (e.g. "τ-bench" — verified 2026-07-18:
tectonic warns "could not represent character 'τ'" and silently drops it).
Escape every value that reaches a .tex file through this function.

A single-pass regex substitution, not a chain of `.replace()` calls: chaining
risks a later replacement re-matching text a prior one just inserted (e.g.
escaping `%` after inserting `\%` would double-escape the backslash). One
scan of the *original* string, one substitution per matched character, no
ordering bugs possible.
"""
import re

# Unicode symbols with no text-mode glyph in the default font -> their LaTeX
# math-mode equivalent. Extend this as new corpus titles surface more (a
# missing one degrades gracefully to a dropped-glyph font warning, not a
# compile failure, but is worth fixing when noticed).
_UNICODE_MATH = {
    "τ": r"$\tau$", "α": r"$\alpha$", "β": r"$\beta$", "λ": r"$\lambda$",
    "∞": r"$\infty$", "→": r"$\rightarrow$", "×": r"$\times$",
}
_SPECIAL = {
    "\\": r"\textbackslash{}", "%": r"\%", "&": r"\&", "_": r"\_",
    "#": r"\#", "$": r"\$", "{": r"\{", "}": r"\}",
    "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
}
_ALL = {**_UNICODE_MATH, **_SPECIAL}
_PATTERN = re.compile("|".join(re.escape(c) for c in _ALL))


def latex_escape(value):
    return _PATTERN.sub(lambda m: _ALL[m.group()], str(value))
