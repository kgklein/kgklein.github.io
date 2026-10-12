# SciX / ADS bibliography integration (Quarto)

Copy `scripts/`, `bibliography/`, and `publications.qmd` into your Quarto root.
Keep your existing `publications.qmd` as a backup until satisfied with the results.

## 1. Set token in your current shell (never in repo)

```bash
read -rsp 'ADS/SciX API token: ' ADS_API_TOKEN; echo
export ADS_API_TOKEN
```

## 2. Fetch and build

```bash
python3 scripts/fetch_publications.py --query 'author:"Klein, Kristopher"'
python3 scripts/build_publications.py
cat bibliography/audit.json
quarto preview
```

Inspect `bibliography/ads_raw.json` for name collisions, missing papers, and
correct author spelling. Try alternate query terms if necessary, compare
against your CV, and review matching in `preprints_to_review.json`.
The builder deliberately holds unmatched preprints for review. Never assume
that an unmatched preprint is unpublished until independently checked.

Use `bibliography/suppress.txt` (one bibcode per line) to remove false positives.

To include verified unpublished preprints in a later revision, implement an
explicit allowlist rather than trusting absence of matching results.

## Security

Never commit tokens. This starter reads only from the environment. The
raw metadata JSON, generated bibliography, audit file, and Markdown output
are non-secret and can be versioned if desired.

## Future improvements

- Refine author search using ORCID and variants after inspecting recall.
- Verify SciX API host before switching `SCIX_API_BASE` from legacy ADS host.
- Provide reviewed allowlist for eligible unpublished preprints.
- Replace simplified BibTeX formatting with SciX's official export endpoint,
  once records have been curated.
