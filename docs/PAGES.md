# GitHub Pages preparation

`docs/index.html` is a self-contained static documentation page. `.nojekyll` disables Jekyll processing if branch-folder publishing is later chosen. No deploy workflow is added, and no Pages setting has been enabled.

Publication requires a separate approval of the exact site contents and public audience. The repository is private. GitHub Pages normally makes the website public even from a private repository; eligible private-repository plans are required. Private access-controlled sites are an Enterprise Cloud organization feature. Do not make this repository public merely to enable Pages. Account plan, Pages eligibility and final source branch must be checked before publishing. No custom domain, paid plan or account setting change is approved.

Only `index.html` should be included in a future site artifact, not this repository, rollback archives, tests or source exports. If selecting branch `/docs` publishing instead, first remove any non-public files from that publishing folder. Prefer a site-only artifact to avoid exposing source documentation unintentionally.

Sources checked 28 October 2026:
- https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site
- https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages
- https://docs.github.com/en/enterprise-cloud@latest/pages/getting-started-with-github-pages/changing-the-visibility-of-your-github-pages-site
