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


# ---- second escaper, for text that is ALREADY LaTeX ----
# Semantic Scholar's `citationStyles.bibtex` is pre-formatted LaTeX: it carries
# braces, accent macros (\'e), and occasional math, so running latex_escape()
# over it would double-escape its own markup (`{` -> `\{`, `\` ->
# `\textbackslash{}`) and destroy the entry. But S2 does NOT escape the
# characters that break a compile inside a field value — verified 2026-08-15:
# three of this corpus's 187 S2-sourced entries carry a bare `&` in the title
# ("RLBench: ... Benchmark & Learning Environment", ToolComp, RE-Bench), each of
# which is a fatal "Misplaced alignment tab character &" at \bibliography time.
# So escape only the characters that are never LaTeX *syntax* inside a
# bibliographic field and always fatal when bare, and only when not already
# backslash-escaped. `$`, `{`, `}`, `\` are deliberately absent: S2 uses all
# four as markup.
_BIB_UNSAFE = {"&": r"\&", "%": r"\%", "#": r"\#", "_": r"\_", "^": r"\^{}"}
_BIB_PATTERN = re.compile(r"(?<!\\)[&%#_^]")
# fields whose values are consumed verbatim by url/DOI machinery, where a `\_`
# would print a literal backslash instead of an underscore.
_BIB_VERBATIM_FIELDS = {"url", "doi", "eprint", "archiveprefix", "urldate"}
_BIB_FIELD_LINE = re.compile(r"^(\s*)([A-Za-z]+)(\s*=\s*)(.*)$")


def latex_escape_bibtex(bibtex):
    """Make an externally-supplied BibTeX entry compile-safe without disturbing
    the LaTeX markup it already contains. Line-oriented because that is the
    shape S2 emits (one `field = {value},` per line)."""
    out = []
    for line in str(bibtex).split("\n"):
        m = _BIB_FIELD_LINE.match(line)
        if not m or m.group(2).lower() in _BIB_VERBATIM_FIELDS:
            out.append(line)
            continue
        indent, field, eq, value = m.groups()
        out.append(indent + field + eq + _BIB_PATTERN.sub(lambda x: _BIB_UNSAFE[x.group()], value))
    return "\n".join(out)
