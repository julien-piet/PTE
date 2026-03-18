# /api

## Overview
`index.json` — read by the agent as an initial pass to determine which API file(s) contain endpoints relevant to a given task.

## Server APIs

API schemas formatted in Swagger 2.0 JSON schema:

- `gitlab_api_schema.json`
- `shopping_api_schema.json`

Server-specific prompting used by the agent during planning:

- `api_server_prompts.py`
- `api_hints.json`

## Playwright APIs

Used by the eval agent:

- `/gitlab_pw`
- `/reddit_pw`
- `/shopping_pw`
