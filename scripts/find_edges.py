#!/usr/bin/env python3
"""Find citation edges between a staged paper and the existing graph.

Usage:
    python3 scripts/find_edges.py <slug>            # expects work/<slug>/{paper.txt,refs.json,cites.json}
    python3 scripts/find_edges.py <slug> --json     # machine-readable

Emits candidate outgoing edges (this paper -> existing node) and incoming
edges (existing node -> this paper), each with the evidence that found it.
Candidates are *leads*, not authority: the builder must confirm each against
the paper's printed bibliography before writing it into data/papers.json.

This exists because the same sweep was being retyped inline for every paper,
and five distinct matcher gaps were found the hard way, each of which had
already cost or nearly cost a real edge:

  1. LINE-BREAK HYPHENS. Bibliographies break titles across lines, so
     "Constitutional AI: Harm-\nlessness..." never matches. Strip `-\n`
     before matching. This hid Constitutional AI (DyVal's predecessor run),
     and HELM / LLaMA / PaLM on LEXTREME -- three real edges in one paper.

  2. SHORT TITLES. A `len(probe) > 25` guard silently dropped 22 of 673
     nodes, among them GPT-4 Technical Report (22 chars), Mistral 7B,
     OpenAI Gym, Humanity's Last Exam and Datasheets for Datasets -- i.e.
     precisely the papers everything cites. Lowering that to a word-count
     guard plus a 14-char floor recovered most of them but *still* dropped
     the shortest three, and it cost a real edge a second time: LongICLBench
     cites Mistral 7B (2 words, 10 chars) and S2's reference list omits it
     entirely, so the printed-bibliography sweep was the only thing that
     could have caught it -- and the floor excluded it from that sweep.
     So no title is dropped now. A sub-floor probe is instead marked *weak*
     and must be corroborated by the node's first-author surname appearing
     within one bibliography entry of the match. That keeps "world models"
     (generic enough to appear in any related-work paragraph) from matching
     on prose, while letting "mistral 7b" through on the strength of a
     neighbouring "Jiang".

  3. ARXIV IDS HIDDEN IN DOIS. Semantic Scholar sometimes omits the
     `ArXiv` external id entirely and stores the id only inside the DOI as
     `10.48550/arXiv.2304.08244`. Match that form too.

  4. RETITLED PAPERS. S2 may hold an older title than the node ("API-Bank:
     A Benchmark..." vs "API-Bank: A *Comprehensive* Benchmark..."), so
     exact title equality is not sufficient. Fall back to a fuzzy ratio and
     report it as a weaker signal.

  5. TRUNCATED CITATION PAGES. S2 caps a citations page at 1000 rows, and
     a staged file sitting exactly on that boundary is silently partial.
     SUPERB has 1240 citers, so an unpaged fetch would have hidden 240 of
     them and made "0 incoming" unverifiable. This script warns on the
     boundary; the fix is to re-fetch with `&offset=1000` and merge.

  6. WRONG-VERSION REFERENCE LISTS. S2's references can belong to a
     *different version* of the paper than the one staged. "Repairing the
     Cracked Foundation" is on arXiv only as v1 (14 Feb 2022), but S2 serves
     the later JAIR version's bibliography -- so it offered PaLM (Apr 2022),
     BIG-bench (Jun 2022) and HELM (Nov 2022) as references of a February
     paper. All three scored zero hits in the printed bibliography, along
     with scratchpads and chain-of-thought: six false leads out of 28.
     The cheap tell is a reference dated after the citing paper, which this
     script now warns on. It is only a partial net -- S2 dated PaLM and
     BIG-bench 2022, the same year as the paper, so year granularity cannot
     separate those -- which is another reason the printed-bibliography
     sweep is load-bearing rather than belt-and-braces.

     A sibling of this: same author, same year, *different paper*. S2
     offered `fabbri-2021-qafacteval` for this survey, but every Fabbri
     citation in it is to SummEval. Confirm the title, not just the name
     and year (cf. the METEOR Banerjee-2005 / Lavie-2007 pair, which has
     produced a false lead on three separate papers).

Semantic Scholar's reference lists are also simply incomplete -- DyVal's
84-entry list omits the GPT-4 Technical Report that its printed
bibliography cites -- so the printed-bibliography sweep is not a
belt-and-braces check, it is load-bearing.
"""
import argparse
import difflib
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAPERS_JSON = ROOT / "data" / "papers.json"

# A probe needs enough words to be specific; "gpt 4 technical report" (22
# chars, 4 words) must pass, while a bare two-word phrase must not.
MIN_PROBE_WORDS = 3
MIN_PROBE_CHARS = 14
FUZZY_CUTOFF = 0.85
# How far from a weak probe's match the first-author surname may sit and still
# count as the same bibliography entry. Entries run ~150-250 chars once
# normalized, so this is about one entry either side.
SHORT_PROBE_WINDOW = 300


def norm(text):
    text = unicodedata.normalize("NFKD", text or "").lower()
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def dehyphenate(text):
    """Rejoin words split across a line break, then flatten whitespace."""
    return re.sub(r"\s+", " ", re.sub(r"-\n", "", text))


def arxiv_ids(external_ids):
    """Every arXiv id derivable from an S2 externalIds blob (gap 3)."""
    ids = set()
    if not external_ids:
        return ids
    if external_ids.get("ArXiv"):
        ids.add(external_ids["ArXiv"])
    doi = external_ids.get("DOI") or ""
    m = re.search(r"10\.48550/arxiv\.([0-9]{4}\.[0-9]{4,5})", doi, re.I)
    if m:
        ids.add(m.group(1))
    return ids


def node_arxiv_map(nodes):
    """slug <- arXiv id, read from each explainer's hero source link."""
    out = {}
    for node in nodes:
        path = ROOT / "public" / "papers" / f"{node['slug']}.html"
        if not path.exists():
            continue
        head = path.read_text(encoding="utf-8")[:20000]
        for m in re.finditer(r"arxiv\.org/(?:abs|pdf)/([0-9]{4}\.[0-9]{4,5})", head):
            out.setdefault(m.group(1), node["slug"])
    return out


def probe_for(title):
    """(probe, weak) for a node title -- never None for a real title.

    `weak` marks a probe short enough to risk matching ordinary prose rather
    than a bibliography entry; the caller corroborates those with the
    first-author surname instead of discarding them (gap 2).
    """
    words = norm(title).split(" ")
    probe = " ".join(words[:9])
    if not probe:
        return None, False
    weak = len(words) < MIN_PROBE_WORDS or len(probe) < MIN_PROBE_CHARS
    return probe, weak


def first_surname(node):
    """Surname of the node's first author, used to corroborate a weak probe."""
    first = (node.get("authors") or "").split(",")[0]
    first = re.sub(r"\bet\s+al\.?", " ", first, flags=re.I)
    parts = norm(first).split(" ")
    return parts[-1] if parts and parts[-1] else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    work = ROOT / "work" / args.slug
    paper_txt = (work / "paper.txt").read_text(encoding="utf-8")
    nodes = json.loads(PAPERS_JSON.read_text())["papers"]
    by_title = {norm(n["title"]): n["slug"] for n in nodes}
    by_arxiv = node_arxiv_map(nodes)

    def rows(name, key):
        path = work / name
        if not path.exists():
            return []
        return [r[key] for r in json.loads(path.read_text()).get("data", []) if r.get(key)]

    refs = rows("refs.json", "citedPaper")
    cites = rows("cites.json", "citingPaper")

    # Gap 5: S2 caps a citations page at 1000. A staged file sitting exactly
    # on a 1000-boundary is almost certainly truncated, which makes the
    # incoming-edge sweep silently partial -- SUPERB has 1240 citers, so a
    # single unpaged fetch would have hidden 240 of them. Re-fetch with
    # &offset=1000 (2000, ...) and merge before trusting "0 incoming".
    warnings = []
    for name, got in (("cites.json", len(cites)), ("refs.json", len(refs))):
        if got and got % 1000 == 0:
            warnings.append(
                f"{name} holds exactly {got} rows -- that is the S2 page cap, "
                f"so it is probably truncated. Re-fetch with &offset={got} and "
                f"merge before trusting the incoming-edge count.")

    # Gap 6: S2's reference list can belong to a DIFFERENT VERSION of the paper
    # than the one staged. "Repairing the Cracked Foundation" exists on arXiv
    # only as v1 (14 Feb 2022), but S2 serves the later JAIR version's
    # references -- so it listed PaLM (Apr 2022), BIG-bench (Jun 2022) and HELM
    # (Nov 2022) among the things a February paper cites. All three scored zero
    # hits in the printed bibliography. The tell is cheap: a reference published
    # after the citing paper cannot be in the version we are reading.
    # The arXiv stamp is rotated into the left margin, so its position in the
    # extracted text is not fixed -- on this paper it landed at char 4129.
    # Search the whole first page rather than a fixed prefix.
    m = re.search(r"arXiv:(\d{2})(\d{2})\.\d{4,5}", paper_txt[:12000])
    if m:
        self_year = 2000 + int(m.group(1))
        future = sorted({(p.get("year"), (p.get("title") or "")[:58])
                         for p in refs if p.get("year") and p["year"] > self_year})
        if future:
            listed = "; ".join(f"{y} {t}" for y, t in future[:6])
            warnings.append(
                f"refs.json lists {len(future)} reference(s) published AFTER this "
                f"paper's arXiv year ({self_year}) -- S2 may be serving a later "
                f"version's bibliography. Confirm each against the printed "
                f"bibliography. e.g. {listed}")

    def match(paper):
        for aid in arxiv_ids(paper.get("externalIds")):
            if aid in by_arxiv:
                return by_arxiv[aid], "arxiv"
        slug = by_title.get(norm(paper.get("title")))
        if slug:
            return slug, "title"
        return None, None

    outgoing, incoming = {}, {}
    for paper in refs:
        slug, how = match(paper)
        if slug:
            outgoing.setdefault(slug, f"s2-ref:{how}")
    for paper in cites:
        slug, how = match(paper)
        if slug:
            incoming.setdefault(slug, f"s2-cite:{how}")

    # The printed bibliography, de-hyphenated (gap 1). Load-bearing: S2's
    # reference lists are incomplete, not merely differently formatted.
    idx = max(paper_txt.rfind("References"), paper_txt.rfind("REFERENCES"))
    bib = norm(dehyphenate(paper_txt[idx:] if idx > 0 else paper_txt))
    ref_titles = [norm(p.get("title")) for p in refs]

    for node in nodes:
        slug = node["slug"]
        if slug in outgoing or slug == args.slug:
            continue
        probe, weak = probe_for(node["title"])          # gap 2
        if probe and probe in bib:
            if not weak:
                outgoing[slug] = "printed-bibliography"
                continue
            # A weak probe is trusted only when the node's first author sits
            # within one bibliography entry of it -- "mistral 7b" next to a
            # "Jiang" is a citation; a bare "world models" in a related-work
            # sentence is not.
            surname = first_surname(node)
            if surname and any(
                    surname in bib[max(0, m.start() - SHORT_PROBE_WINDOW):
                                   m.end() + SHORT_PROBE_WINDOW]
                    for m in re.finditer(re.escape(probe), bib)):
                outgoing[slug] = "printed-bibliography (short title, surname-corroborated)"
                continue
        close = difflib.get_close_matches(norm(node["title"]), ref_titles,
                                          n=1, cutoff=FUZZY_CUTOFF)
        if close:
            # Gap 4. Show BOTH titles in full: a fuzzy hit is as often two
            # genuinely different papers with near-identical names as it is a
            # retitle, and the distinguishing words sit at the END. Truncating
            # to 60 chars hid exactly that on METEOR twice -- Banerjee & Lavie
            # 2005 "...with Improved Correlation with Human Judgments" vs
            # Lavie & Agarwal 2007 "...with High Levels of Correlation with
            # Human Judgments", where everything before the last few words is
            # identical. Print them adjacently so the confirmer sees the
            # difference without opening the PDF.
            outgoing[slug] = (f"fuzzy-title -- CONFIRM, may be a different paper:\n"
                              f"        node: {norm(node['title'])}\n"
                              f"        ref:  {close[0]}")   # gap 4

    result = {
        "slug": args.slug,
        "outgoing": dict(sorted(outgoing.items())),
        "incoming": dict(sorted(incoming.items())),
        "counts": {"refs": len(refs), "cites": len(cites),
                   "outgoing": len(outgoing), "incoming": len(incoming)},
    }

    result["warnings"] = warnings

    if args.json:
        json.dump(result, sys.stdout, indent=1)
        print()
        return

    for w in warnings:
        print(f"!! {w}\n")

    print(f"{args.slug}: {len(refs)} S2 refs, {len(cites)} S2 citers, "
          f"{len(nodes)} nodes in graph\n")
    print(f"OUTGOING ({len(outgoing)}) — this paper cites an existing node:")
    for slug, how in result["outgoing"].items():
        print(f"  {slug:<38} [{how}]")
    print(f"\nINCOMING ({len(incoming)}) — an existing node cites this paper:")
    for slug, how in result["incoming"].items():
        print(f"  {slug:<38} [{how}]")
    print("\nThese are leads. Confirm each against the printed bibliography "
          "before writing it into data/papers.json.")


if __name__ == "__main__":
    main()

    # Gap 6: S2's reference list can belong to a DIFFERENT VERSION of the
    # paper than the one staged. "Repairing the Cracked Foundation" is on
    # arXiv only as v1 (14 Feb 2022), but S2 serves the later JAIR version's
    # references -- so it listed PaLM (Apr 2022), BIG-bench (Jun 2022) and
    # HELM (Nov 2022) as things a February paper cites. All three scored zero
    # hits in the printed bibliography. The tell is cheap: a reference dated
    # after the citing paper cannot be in the version we are reading, so warn
    # and let the confirmer check the printed bibliography.
    self_year = None
    # The arXiv stamp is rotated into the left margin, so its position in the
    # extracted text is not fixed -- on this paper it landed at char 4129.
    # Search the whole first page rather than a fixed prefix.
    m = re.search(r"arXiv:(\d{2})(\d{2})\.\d{4,5}", paper_txt[:12000])
    if m:
        self_year = 2000 + int(m.group(1))
    if self_year:
        future = sorted({
            (p.get("year"), (p.get("title") or "")[:58])
            for p in refs if p.get("year") and p["year"] > self_year})
        if future:
            listed = "; ".join(f"{y} {t}" for y, t in future[:6])
            warnings.append(
                f"refs.json lists {len(future)} reference(s) published AFTER this "
                f"paper's arXiv year ({self_year}) -- S2 may be serving a later "
                f"version's bibliography. Confirm each against the printed "
                f"bibliography before writing it. e.g. {listed}")

