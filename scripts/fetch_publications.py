#!/usr/bin/env python3
"""Download raw SciX/ADS search metadata. Python standard library only."""
import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

FIELDS = 'bibcode,title,author,year,pub,pubdate,doctype,property,doi,identifier,volume,page,eid'

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
    '--query',
    default='orcid:0000-0001-6038-1923',
    help='SciX/ADS publication search query'
)
    ap.add_argument('--api-base', default=os.environ.get('SCIX_API_BASE', 'https://api.adsabs.harvard.edu/v1'))
    ap.add_argument('--output', default='bibliography/ads_raw.json')
    args = ap.parse_args()
    token = os.environ.get('ADS_API_TOKEN') or os.environ.get('SCIX_API_TOKEN')
    if not token:
        ap.error('Set ADS_API_TOKEN (or SCIX_API_TOKEN) in your environment; never commit it.')
    docs = []
    start = 0
    total = None
    while total is None or start < total:
        params = urlencode({'q': args.query, 'fl': FIELDS, 'rows': 200, 'start': start, 'sort': 'date desc'})
        url = f"{args.api_base.rstrip('/')}/search/query?{params}"
        req = Request(url, headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/json'})
        try:
            with urlopen(req, timeout=40) as res:
                data = json.load(res)
        except (HTTPError, URLError) as err:
            raise SystemExit(f'API request failed: {err}; verify token, endpoint and query') from err
        response = data['response']
        total = int(response['numFound'])
        batch = response.get('docs', [])
        if not batch:
            break
        docs.extend(batch)
        start += len(batch)
        print(f'Fetched {len(docs)} / {total} records')
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({'query': args.query, 'numFound': total, 'docs': docs}, ensure_ascii=False, indent=2) + '\n')
    print(f'Saved {out}; review identity and completeness before publishing.')

if __name__ == '__main__':
    main()
