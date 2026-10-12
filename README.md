# kgklein.github.io starter

Quarto website source for Kristopher G. Klein's independent academic homepage.

## Local preview

Install Quarto from https://quarto.org/docs/get-started/ and run:

```bash
quarto preview
```

## Publish

Create a public GitHub repository named `kgklein.github.io` under the `kgklein` account. Commit and push these source files to its `main` branch, then run:

```bash
quarto publish gh-pages
```

IMPORTANT: Since this is a *user site*, visit GitHub repository **Settings → Pages** after first publication and select **Deploy from a branch**, branch `gh-pages`, folder `/(root)`.

For automatic publishing on every push, follow Quarto's documented GitHub Actions workflow: https://quarto.org/docs/publishing/github-pages.html#github-action . The first local `quarto publish gh-pages` creates `_publish.yml`, required by Quarto's prescribed automation.
