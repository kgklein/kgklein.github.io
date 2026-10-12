#!/usr/bin/env python3
"""Filter raw ADS metadata into a Quarto page include + basic BibTeX.

Conservative: peer-reviewed journal articles are included; preprints are
included only if no matching journal article can be found. Ambiguous preprints
are written to a review file and excluded until reviewed.
"""
import argparse
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import quote


def clean(x):
    return re.sub(r'\s+', ' ', str(x or '')).strip()


def title(rec):
    x = rec.get('title', '')
    return clean(x[0] if isinstance(x, list) and x else x)


def normalized(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]', '', s)


def dois(rec):
    return {clean(d).lower().removeprefix('https://doi.org/') for d in rec.get('doi', []) if clean(d)}


def arxiv_ids(rec):
    found = set()
    for field in rec.get('identifier', []):
        val = clean(field)
        if val.lower().startswith('arxiv:'):
            found.add(val[6:].lower().split('v')[0])
        elif re.fullmatch(r'\d{4}\.\d{4,5}(?:v\d+)?', val):
            found.add(val.lower().split('v')[0])
    return found


def match(a, b):
    return bool((dois(a) & dois(b)) or (arxiv_ids(a) & arxiv_ids(b)) or (normalized(title(a)) and normalized(title(a)) == normalized(title(b))))


def esc_md(s):
    return clean(s).replace('\\', '\\\\').replace('[', '\\[').replace(']', '\\]').replace('*', '\\*').replace('_', '\\_')


def bib_escape(s):
    return clean(s).replace('\\', '\\textbackslash{}').replace('{', '\\{').replace('}', '\\}')


def kind(rec):
    props = [v.lower() for v in rec.get('property', [])]
    typ = clean(rec.get('doctype')).lower()
    if typ == 'article' and 'refereed' in props:
        return 'journal'
    if typ == 'eprint':
        return 'preprint'
    return 'other'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', default='bibliography/ads_raw.json')
    ap.add_argument('--outdir', default='bibliography')
    ap.add_argument('--suppress', default='bibliography/suppress.txt', help='Optional one bibcode per line')
    args = ap.parse_args()
    obj = json.loads(Path(args.input).read_text())
    records = obj['docs']
    suppressed = set()
    if Path(args.suppress).exists():
        suppressed = {s.strip() for s in Path(args.suppress).read_text().splitlines() if s.strip() and not s.startswith('#')}
    journals = [r for r in records if kind(r) == 'journal' and r.get('bibcode') not in suppressed]
    preprints = [r for r in records if kind(r) == 'preprint' and r.get('bibcode') not in suppressed]
    other = [r for r in records if kind(r) == 'other']
    # Keep only one version of each record and avoid accidental duplicates.
    chosen = []
    dropped = []
    for r in sorted(journals, key=lambda v: (clean(v.get('pubdate')), clean(v.get('bibcode'))), reverse=True):
        if any(match(r, j) for j in chosen):
            dropped.append((r.get('bibcode'), 'duplicate journal record'))
        else:
            chosen.append(r)
    accepted_preprints = []
    review = []
    for r in preprints:
        if any(match(r, j) for j in chosen):
            dropped.append((r.get('bibcode'), 'matches refereed publication'))
            continue
        # No precise link to a journal version? Needs human verification.
        # A missing match in the retrieved query is not proof of no publication.
        review.append(r)
    chosen += accepted_preprints
    chosen.sort(key=lambda v: (clean(v.get('pubdate')), clean(v.get('bibcode'))), reverse=True)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    lines = ['<!-- GENERATED: do not edit; run scripts/build_publications.py -->', '']
    current_year = None
    bib = ['% GENERATED from SciX/ADS metadata; inspect before relying on citations.', '']
    for r in chosen:
        yr = str(r.get('year', 'Undated'))
        if yr != current_year:
            lines += [f'### {yr}', '']
            current_year = yr
        name = title(r)
        authors = r.get('author', [])
        shortauthors = ', '.join(authors[:5]) + (' et al.' if len(authors) > 5 else '')
        publication = clean(r.get('pub', ''))
        record_url = 'https://scixplorer.org/abs/' + quote(r['bibcode'])
        doi = sorted(dois(r))
        links = [f'[SciX]({record_url})']
        if doi:
            links.insert(0, f'[DOI](https://doi.org/{quote(doi[0], safe="/")})')
        lines += [f'- **[{esc_md(name)}]({record_url})** ({yr}). {esc_md(shortauthors)}. *{esc_md(publication)}*. ' + ' · '.join(links), '']
        key = r['bibcode']
        bib += [f'@article{{{key},', f'  title = {{{bib_escape(name)}}},', '  author = {' + ' and '.join(bib_escape(a) for a in authors) + '},', f'  year = {{{yr}}},', f'  journal = {{{bib_escape(publication)}}},']
        if doi:
            bib.append(f'  doi = {{{doi[0]}}},')
        bib += [f'  url = {{{record_url}}}', '}', '']
    (outdir / 'publications_generated.md').write_text('\n'.join(lines) + '\n')
    (outdir / 'publications.bib').write_text('\n'.join(bib) + '\n')
    (outdir / 'preprints_to_review.json').write_text(json.dumps(review, indent=2, ensure_ascii=False) + '\n')
    (outdir / 'audit.json').write_text(json.dumps({'query': obj.get('query'), 'raw': len(records), 'journal_included': len(chosen), 'preprints_pending_review': len(review), 'other_excluded': len(other), 'duplicates_excluded': dropped, 'suppress_count': len(suppressed)}, indent=2) + '\n')
    print(f'Included {len(chosen)} refereed articles; {len(review)} unmatched preprints held for review; {len(other)} other records excluded.')
    print('Inspect bibliography/audit.json and bibliography/preprints_to_review.json before publishing.')

if __name__ == '__main__':
    main()
