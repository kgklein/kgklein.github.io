#!/bin/bash
# SciX / ADS bibliography integration (Quarto)

python3 scripts/fetch_publications.py --query 'author:"Klein, Kristopher"'
python3 scripts/build_publications.py
cat bibliography/audit.json
quarto preview
