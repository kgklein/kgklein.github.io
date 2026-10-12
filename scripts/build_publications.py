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

try:
    import yaml
except ImportError:
    yaml = None


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



def selected_publications(path, records):
    """Build curated Markdown and a diagnostic report from verified journal records."""
    if not path.exists():
        return None, {'configured': 0, 'matched': [], 'unmatched': [], 'ambiguous': []}
    if yaml is None:
        raise SystemExit('PyYAML is required: python3 -m pip install pyyaml')
    data = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    entries = data.get('selected_publications', [])
    if not isinstance(entries, list):
        raise SystemExit('selected_publications.yml must contain a list under selected_publications')

    report = {'configured': len(entries), 'matched': [], 'unmatched': [], 'ambiguous': []}
    lines = ['<!-- GENERATED: edit selected_publications.yml, not this file -->', '']
    for item in entries:
        key = clean(item.get('id', ''))
        target = normalized(item.get('title', ''))
        bibcode = clean(item.get('bibcode', ''))
        if not key or not target:
            raise SystemExit('Each selected paper needs a nonempty id and title')
        # Bibcode takes priority once manually verified. Otherwise use exact
        # normalized-title matching, with no approximate automatic selection.
        found = ([r for r in records if r.get('bibcode') == bibcode]
                 if bibcode else [r for r in records if normalized(title(r)) == target])
        if not found:
            report['unmatched'].append({'id': key, 'title': item['title']})
            continue
        if len(found) != 1:
            report['ambiguous'].append({'id': key, 'title': item['title'],
                                        'bibcodes': [r.get('bibcode') for r in found]})
            continue
        r = found[0]
        report['matched'].append({'id': key, 'bibcode': r['bibcode'], 'title': title(r)})
        url = 'https://scixplorer.org/abs/' + quote(r['bibcode'])
        doi = sorted(dois(r))
        links = [f'[SciX]({url})']
        if doi:
            links.insert(0, f'[DOI](https://doi.org/{quote(doi[0], safe="/")})')
        authors = r.get('author', [])
        authorline = ', '.join(authors[:5]) + (' et al.' if len(authors) > 5 else '')
        yr = clean(r.get('year'))
        desc = clean(item.get('description', ''))
        lines.extend([
            f'### [{esc_md(title(r))}]({url})',
            '',
            f'{esc_md(authorline)} ({yr}). *{esc_md(r.get("pub", ""))}*. ' + ' · '.join(links),
            '',
            esc_md(desc),
            ''
        ])
    return '\n'.join(lines) + '\n', report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', default='bibliography/ads_raw.json')
    ap.add_argument('--outdir', default='bibliography')
    ap.add_argument('--suppress', default='bibliography/suppress.txt', help='Optional one bibcode per line')
    ap.add_argument('--selected', default='bibliography/selected_publications.yml',
                    help='Curated selected publications YAML')
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
    selected_md, selected_report = selected_publications(Path(args.selected), chosen)
    if selected_md is not None:
        (outdir / 'selected_publications_generated.md').write_text(selected_md, encoding='utf-8')
    (outdir / 'selected_publications_audit.json').write_text(
        json.dumps(selected_report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    for issue in selected_report['unmatched']:
        print(f"WARNING: selected publication not found: {issue['id']} — {issue['title']}")
    for issue in selected_report['ambiguous']:
        print(f"WARNING: ambiguous selected publication: {issue['id']} — {issue['bibcodes']}")
    print(f"Selected papers: {len(selected_report['matched'])}/{selected_report['configured']} matched")
    (outdir / 'publications_generated.md').write_text('\n'.join(lines) + '\n')
    (outdir / 'publications.bib').write_text('\n'.join(bib) + '\n')
    (outdir / 'preprints_to_review.json').write_text(json.dumps(review, indent=2, ensure_ascii=False) + '\n')
    (outdir / 'audit.json').write_text(json.dumps({'query': obj.get('query'), 'raw': len(records), 'journal_included': len(chosen), 'preprints_pending_review': len(review), 'other_excluded': len(other), 'duplicates_excluded': dropped, 'suppress_count': len(suppressed)}, indent=2) + '\n')
    print(f'Included {len(chosen)} refereed articles; {len(review)} unmatched preprints held for review; {len(other)} other records excluded.')
    print('Inspect bibliography/audit.json and bibliography/preprints_to_review.json before publishing.')

if __name__ == '__main__':
    main()
