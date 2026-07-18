#!/usr/bin/env python3
"""Add or remove survey tags on paper nodes, writing data/papers.json in its
exact canonical style (papers pretty-printed; `tags` arrays inline; edges
one-per-line) so diffs stay minimal and reviewable.

A *survey* is a named tag defined in data/surveys.json (id, label, color,
description). A paper's membership lives in its node's `tags` array. This script
is the operational tool for CLAUDE.md Procedure D (tag for a survey) and the
tagging step of Procedure A.

Usage
-----
  # tag papers into a survey (validates the survey id + every slug)
  python scripts/tag_papers.py add <survey_id> <slug> [<slug> ...]

  # untag
  python scripts/tag_papers.py remove <survey_id> <slug> [<slug> ...]

  # read slugs from stdin (one per line) instead of argv
  echo -e "a-slug\\nb-slug" | python scripts/tag_papers.py add <survey_id> -

  # list a survey's current members (slug<TAB>short)
  python scripts/tag_papers.py list <survey_id>

  # list every survey + member count
  python scripts/tag_papers.py surveys

Run from the repo root. Tags are kept sorted & de-duplicated; a paper with no
tags carries no `tags` key (absent == untagged).
"""
import json, re, sys, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPERS = os.path.join(ROOT, 'data', 'papers.json')
SURVEYS = os.path.join(ROOT, 'data', 'surveys.json')


def _collapse_tags(s):
    """Render any `tags` array inline: "tags": ["a", "b"]."""
    def repl(m):
        arr = json.loads('[' + m.group(1) + ']')
        return '"tags": ' + json.dumps(arr, ensure_ascii=False)
    return re.sub(r'"tags": \[\s*([^\]]*?)\s*\]', repl, s)


def dumps_papers(d):
    out = ['{', '  "papers": [']
    P = d['papers']
    for i, p in enumerate(P):
        body = _collapse_tags(json.dumps(p, indent=2, ensure_ascii=False))
        body = '\n'.join('    ' + ln for ln in body.split('\n'))
        out.append(body + (',' if i < len(P) - 1 else ''))
    out.append('  ],')
    out.append('  "edges": [')
    E = d['edges']
    for i, e in enumerate(E):
        out.append('    { "from": %s, "to": %s }%s' % (
            json.dumps(e['from'], ensure_ascii=False),
            json.dumps(e['to'], ensure_ascii=False),
            ',' if i < len(E) - 1 else ''))
    out.append('  ]')
    out.append('}')
    return '\n'.join(out) + '\n'


def load():
    return json.load(open(PAPERS)), json.load(open(SURVEYS))


def survey_ids(sd):
    return {s['id'] for s in sd.get('surveys', [])}


def cmd_surveys(d, sd):
    for s in sd.get('surveys', []):
        n = sum(1 for p in d['papers'] if s['id'] in p.get('tags', []))
        print(f"{s['id']}\t{n}\t{s.get('label','')}")


def cmd_list(d, sd, sid):
    if sid not in survey_ids(sd):
        sys.exit(f"unknown survey id '{sid}'. defined: {sorted(survey_ids(sd))}")
    for p in d['papers']:
        if sid in p.get('tags', []):
            print(f"{p['slug']}\t{p.get('short','')}")


def cmd_mutate(d, sd, action, sid, slugs):
    if sid not in survey_ids(sd):
        sys.exit(f"unknown survey id '{sid}'. defined: {sorted(survey_ids(sd))}")
    present = {p['slug'] for p in d['papers']}
    unknown = [s for s in slugs if s not in present]
    if unknown:
        sys.exit(f"{len(unknown)} slug(s) not in papers.json: {unknown}")
    slugset, changed = set(slugs), 0
    for p in d['papers']:
        if p['slug'] not in slugset:
            continue
        tags = set(p.get('tags', []))
        new = (tags | {sid}) if action == 'add' else (tags - {sid})
        if new != tags:
            changed += 1
        if 'tags' in p:
            del p['tags']
        if new:
            p['tags'] = sorted(new)   # re-add last, sorted & deduped
    tmp = PAPERS + '.tmp'
    open(tmp, 'w').write(dumps_papers(d))
    os.replace(tmp, PAPERS)
    total = sum(1 for p in d['papers'] if sid in p.get('tags', []))
    print(f"{action}: {changed} paper(s) changed; survey '{sid}' now has {total} member(s).")


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    d, sd = load()
    cmd = a[0]
    if cmd == 'surveys':
        cmd_surveys(d, sd)
    elif cmd == 'list':
        cmd_list(d, sd, a[1])
    elif cmd in ('add', 'remove'):
        sid, rest = a[1], a[2:]
        if rest == ['-'] or not rest:
            rest = [ln.strip() for ln in sys.stdin.read().splitlines() if ln.strip()]
        cmd_mutate(d, sd, cmd, sid, rest)
    else:
        sys.exit(f"unknown command '{cmd}'.\n{__doc__}")


if __name__ == '__main__':
    main()
