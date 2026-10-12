#!/bin/bash
set -e

cd ~/Codes/kgklein-site-starter

echo "Rendering website..."
quarto render

echo "Committing source changes..."
git add .
if ! git diff --cached --quiet; then
    git commit -m "${1:-Update website}"
fi

echo "Pushing source files..."
git push

echo "Publishing website..."
quarto publish gh-pages

echo "Website updated: https://kgklein.github.io/"
