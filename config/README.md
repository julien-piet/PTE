# /config

## `config.yaml`

Controls which LLM provider and model the agent uses.

```yaml
agent_llm_provider: anthropic        # Options: anthropic, openai, google-gla
agent_llm_model: claude-opus-4-6     # Must match a model listed under the provider below
```

Supported provider/model combinations are listed in the `llm_providers` section of the file.

---

## `config/.env` — API keys and site credentials

Copy from the template and fill in your values:

```
cp config/.env.example config/.env
```

Loaded automatically by the benchmark runner at test startup.

### LLM provider keys

Only the key for your active provider needs to be set.

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-proj-...
GEMINI_API_KEY=AIza...
```

### WebArena site credentials

Defaults match the standard WebArena Docker setup — only change these if your deployment uses different credentials.

```
GITLAB_USERNAME=byteblaze
GITLAB_PASSWORD=hello1234

REDDIT_USERNAME=MarvelsGrantMan136
REDDIT_PASSWORD=test1234

SHOPPING_USERNAME=emma.lopez@gmail.com
SHOPPING_PASSWORD=Password.123
SHOPPING_ADMIN_USER=admin
SHOPPING_ADMIN_PASS=admin1234
```

`SHOPPING_ADMIN_USER` / `SHOPPING_ADMIN_PASS` are used to fetch a fresh admin Bearer token at eval startup.

### Multi-docker orchestrator

Required when running with `--multi-docker`.

```
REMOTE_HOST=yourname@red5k.cs.berkeley.edu
```

SSH target for the remote worker-pool orchestrator.

---

## `config/.server_env` — Server authentication tokens

Required for the agent to make authenticated API calls to the benchmark servers.

```
# Shopping server — JWT bearer tokens
# Obtain by calling the customer/admin login endpoints on the shopping server
CUSTOMER_AUTH_TOKEN=<customer JWT token>
ADMIN_AUTH_TOKEN=<admin JWT token>

# GitLab server — Personal Access Token (PAT)
# Create at: http://<gitlab-host>/-/user_settings/personal_access_tokens
GITLAB_TOKEN=glpat-...
```

`CUSTOMER_AUTH_TOKEN` and `ADMIN_AUTH_TOKEN` are used by the shopping server.
`GITLAB_TOKEN` is sent as a `PRIVATE-TOKEN` header.
