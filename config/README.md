# /config

## `config.yaml`

Controls which LLM provider and model the agent uses.

```yaml
agent_llm_provider: anthropic        # Options: anthropic, openai, google, google-gla
agent_llm_model: claude-opus-4-6     # Must match a model listed under the provider below
```

Supported provider/model combinations are listed in the `llm_providers` section of the file.

---

## `config/.env` — LLM API keys

Required for whichever provider is set in `config.yaml`.

```
# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# OpenAI
OPENAI_API_KEY=sk-proj-...

# Google / Gemini
GOOGLE_API_KEY=AIza...
```

Only the key for your active provider needs to be set.

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

<!-- # Reddit server — session cookie tokens
REDDIT_TOKEN=<reddit session token>
REDDIT_PHPBB_SESSION=<phpbb session token> -->
```

`CUSTOMER_AUTH_TOKEN` and `ADMIN_AUTH_TOKEN` are used by the shopping server.
`GITLAB_TOKEN` is sent as a `PRIVATE-TOKEN` header.
<!-- `REDDIT_TOKEN` and `REDDIT_PHPBB_SESSION` are sent together as a `Cookie` header. -->