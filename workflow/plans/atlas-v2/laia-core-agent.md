# Atlas v2 — .laia-core/agent/

**Scope:** `/home/laia-arch/LAIA/.laia-core/agent/`
**Search patterns:** `/srv/laia`, `/opt/laia`, `inference-api.nousresearch.com`, `api.anthropic.com`, `chatgpt.com`, `localhost`, `127.0.0.1`
**Checked against:** `~/.laia/atlas.yaml`

---

## Real code hardcodes (should migrate)

No real runtime code hardcodes `/srv/laia`, `/opt/laia`, or internal LAIA service URLs were found in the agent directory.
All hits were either: (a) comment/docstring annotations, (b) external SaaS provider endpoints, or (c) localhost/loopback detection logic.

| File | Line | Value | Type | In atlas.yaml? | Should atlas.get()? |
|------|------|-------|------|---------------|-------------------|
| — | — | — | — | — | — |

**Zero real-code hardcodes of LAIA infrastructure paths found.**

---

## External provider URLs (flag for discussion)

These are **SaaS provider endpoints** — not LAIA infrastructure. They are constant
(by design, as the provider owns them) but could optionally be moved to atlas.yaml
or left as hardcoded constants. Listed for completeness.

| File | Line | Value | Provider | Notes |
|------|------|-------|----------|-------|
| `model_metadata.py` | 306 | `inference-api.nousresearch.com` | Nous Research | In `_URL_TO_PROVIDER` dict (URL→provider mapping) |
| `auxiliary_client.py` | 276 | `https://inference-api.nousresearch.com/v1` | Nous Research | Default base URL constant `_NOUS_DEFAULT_BASE_URL` |
| `auxiliary_client.py` | 3381 | `inference-api.nousresearch.com` | Nous Research | Host-match check in auth-refresh logic |
| `auxiliary_client.py` | 3673 | `inference-api.nousresearch.com` | Nous Research | Async variant of above |
| `model_metadata.py` | 291 | `api.anthropic.com` | Anthropic | In `_URL_TO_PROVIDER` dict |
| `model_metadata.py` | 1348 | `api.anthropic.com` | Anthropic | Hostname check in context-length probe |
| `model_metadata.py` | 1350 | `https://api.anthropic.com` | Anthropic | Default base URL in `_query_anthropic_context_length()` call |
| `auxiliary_client.py` | 277 | `https://api.anthropic.com` | Anthropic | Default base URL constant `_ANTHROPIC_DEFAULT_BASE_URL` |
| `auxiliary_client.py` | 825 | `api.anthropic.com` | Anthropic | Docstring example in `_is_anthropic_wire()` |
| `auxiliary_client.py` | 833 | `api.anthropic.com` | Anthropic | Hostname check in `_is_anthropic_wire()` |
| `auxiliary_client.py` | 1392 | `api.anthropic.com` | Anthropic | Comment: "Anthropic OAuth claims only apply to api.anthropic.com" |
| `auxiliary_client.py` | 1973 | `api.anthropic.com` | Anthropic | Docstring example in `resolve_provider_client()` |
| `anthropic_adapter.py` | 227 | `api.anthropic.com` | Anthropic | Docstring note: "native Anthropic (api.anthropic.com) for Opus 4.6+" |
| `account_usage.py` | 194 | `https://api.anthropic.com/api/oauth/usage` | Anthropic | OAuth usage endpoint — hardcoded URL |
| `model_metadata.py` | 290 | `chatgpt.com` | OpenAI | In `_URL_TO_PROVIDER` dict |
| `model_metadata.py` | 1087 | `chatgpt.com/backend-api/codex` | OpenAI | Docstring describing observed OAuth context windows |
| `model_metadata.py` | 1131 | `https://chatgpt.com/backend-api/codex/models?client_version=1.0.0` | OpenAI | Live probe URL in `_fetch_codex_oauth_context_lengths()` |
| `model_metadata.py` | 1168 | `chatgpt.com/backend-api/codex` | OpenAI | Docstring describing preferred live probe |
| `auxiliary_client.py` | 11 | `chatgpt.com` | OpenAI | Comment: "Codex OAuth (Responses API via chatgpt.com with gpt-5.3-codex" |
| `auxiliary_client.py` | 286 | `https://chatgpt.com/backend-api/codex` | OpenAI | Default base URL constant `_CODEX_AUX_BASE_URL` |
| `auxiliary_client.py` | 290 | `chatgpt.com/backend-api/codex` | OpenAI | Docstring describing Cloudflare 403 avoidance |
| `auxiliary_client.py` | 473 | `chatgpt.com/backend-api/codex` | OpenAI | Comment: "the Codex endpoint (chatgpt.com/backend-api/codex) does NOT [support streaming]" |
| `credential_pool.py` | 1371 | `https://chatgpt.com/backend-api/codex` | OpenAI | Default base_url in device-code token seed |
| `transports/codex.py` | 55 | `chatgpt.com/backend-api/codex` | OpenAI | Docstring parameter description `is_codex_backend: bool` |
| `account_usage.py` | 119 | `https://chatgpt.com/backend-api/codex` | OpenAI | Default fallback URL in `_resolve_codex_usage_url()` |

**Verdict:** External provider URLs are constants by design — the provider owns the endpoint.
Consider adding them to atlas.yaml as `type: service` entries if you want centralized control,
or leave as hardcoded constants. The Anthropic OAuth usage URL (`api.anthropic.com/api/oauth/usage`)
is a candidate for atlas since it is an implementation detail (not a model endpoint).

---

## Comment/docstring hardcodes (leave as-is)

| File | Line | Value | Context |
|------|------|-------|---------|
| `model_metadata.py` | 259 | `_LOCAL_HOSTS = ("localhost", "127.0.0.1", ...)` | Constant defining local host detection — **active logic**, not a path reference |
| `model_metadata.py` | 347 | "Recognises loopback (``localhost``, ``127.0.0.0/8``, ``::1``)" | Docstring for `is_local_endpoint()` |
| `model_metadata.py` | 352 | "Tailscale mesh get the same timeout auto-bumps as localhost Ollama" | Docstring for `is_local_endpoint()` |
| `auxiliary_client.py` | 1328 | ``HTTP_PROXY=http://127.0.0.1:6153export NEXT_VAR=...`` | Example malformed URL in ` _validate_proxy_env_urls()` docstring |
| `google_oauth.py` | 126 | `REDIRECT_HOST = "127.0.0.1"` | OAuth redirect host constant — **active code** (not LAIA infrastructure) |
| `google_oauth.py` | 960 | "Google will redirect to localhost (which won't load)" | User-facing print statement — docstring/example |
| `usage_pricing.py` | 424 | `base and "localhost" in base` | Active logic in `route_billing()` — local provider detection |
| `transports/codex.py` | 55 | `is_codex_backend: bool — chatgpt.com/backend-api/codex` | Parameter docstring |

---

## Notes

1. **`_LOCAL_HOSTS` tuple (`localhost`, `127.0.0.1`, `::1`, `0.0.0.0`) — active logic, not a path hardcode.**
   This is provider-detection logic, not a LAIA infrastructure path. Does NOT need
   migration to atlas; the pattern of checking `in _LOCAL_HOSTS` is the correct approach.

2. **`google_oauth.py` `REDIRECT_HOST = "127.0.0.1"` — active code.** This is the OAuth callback
   host for the Google OAuth flow. It is not a LAIA infrastructure path; it is a loopback
   address for local browser redirect handling. Does NOT need migration to atlas.

3. **`usage_pricing.py` `"localhost" in base` — active logic.** Used to detect local/custom
   providers for billing routing. Does NOT need migration to atlas.

4. **No `/srv/laia` or `/opt/laia` hardcodes found** in `.laia-core/agent/`. This directory
   operates purely at runtime with credentials from `~/.laia/` (via `get_laia_home()`).

5. **No atlas usage found** (`atlas.get()`, `from agent.atlas`, etc.) anywhere in
   `.laia-core/agent/`. The directory is currently atlas-unaware.

6. **`account_usage.py` line 194 hardcodes the Anthropic OAuth usage URL:**
   `https://api.anthropic.com/api/oauth/usage` — this is an implementation detail
   (not a model inference endpoint) and could be added to atlas as a service entry
   if centralized control is desired.

7. **`model_metadata.py` `_fetch_codex_oauth_context_lengths()` line 1131** probes
  `https://chatgpt.com/backend-api/codex/models?client_version=1.0.0` — this is an
   OAuth-specific endpoint, not a general API. Flag for potential atlas entry if
   the provider URL ever changes.
