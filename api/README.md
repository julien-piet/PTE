# /api

## Overview

```
api/
  schemas/          # JSON API specs + agent metadata
  servers/          # HTTP servers that expose Playwright actions to the agent
  gitlab_pw/        # Playwright helpers for GitLab
  shopping_pw/      # Playwright helpers for the shopping site
  reddit_pw/        # Playwright helpers for Reddit
  testing_of_apis/  # Integration tests for the above
```

## schemas/

- `gitlab_api_schema.json` / `shopping_api_schema.json` / `shopping_extra_api_schema.json` — Swagger 2.0 API specs used by the agent to call REST endpoints directly.
- `openapi_swagger_doc_ce.json` — upstream GitLab CE OpenAPI spec (reference).
- `index.json` — read by the agent on each task to determine which schema file(s) are relevant.

Agent prompting (lives at `api/` root, not in `schemas/`):

- `api_server_prompts.py` — server-specific prompts used during planning.
- `api_hints.json` — maps schema files to hint constants injected into the agent.

## servers/

FastAPI servers that wrap Playwright actions as HTTP endpoints, for actions the REST API cannot handle:

- `shopping_extra.py` — fuzzy product search and wishlist add (runs on port 7790, start via `initialize.py`).

## Playwright libraries

Low-level browser automation helpers. Each module takes a Playwright `Page` and returns typed result dataclasses. Used internally by eval scripts, test setup, and `servers/`.

- `gitlab_pw/` — login, branches, files, issues, merge requests, projects, groups, settings, tokens.
- `shopping_pw/` — login, search, product, cart, wishlist, order, review, address book, compare.
- `reddit_pw/` — login, posts, comments, messages, forums, users.

To add a new Playwright helper, see `template.py`.
