# Atlas v2 — .laia-core/gateway/

## Real code hardcodes

| File | Line | Value | Type | In atlas.yaml? | Should atlas.get()? |
|------|------|-------|------|----------------|---------------------|
| `platforms/whatsapp.py` | 405 | `http://127.0.0.1:{self._bridge_port}/health` | service (health check) | NO | **YES** — bridge port is a platform-bridge service that should be in atlas |
| `platforms/whatsapp.py` | 472 | `http://127.0.0.1:{self._bridge_port}/health` | service (health check) | NO | **YES** — same as above |
| `platforms/whatsapp.py` | 504 | `http://127.0.0.1:{self._bridge_port}/health` | service (health check) | NO | **YES** — same as above |
| `platforms/whatsapp.py` | 703 | `http://127.0.0.1:{self._bridge_port}/send` | service (send message) | NO | **YES** — WhatsApp bridge HTTP API |
| `platforms/whatsapp.py` | 742 | `http://127.0.0.1:{self._bridge_port}/edit` | service (edit message) | NO | **YES** — same as above |
| `platforms/whatsapp.py` | 789 | `http://127.0.0.1:{self._bridge_port}/send-media` | service (media send) | NO | **YES** — same as above |
| `platforms/whatsapp.py` | 880 | `http://127.0.0.1:{self._bridge_port}/typing` | service (typing indicator) | NO | **YES** — same as above |
| `platforms/whatsapp.py` | 898 | `http://127.0.0.1:{self._bridge_port}/chat/{chat_id}` | service (chat info) | NO | **YES** — same as above |
| `platforms/whatsapp.py` | 926 | `http://127.0.0.1:{self._bridge_port}/messages` | service (poll messages) | NO | **YES** — same as above |
| `platforms/signal.py` | 175 | `http://127.0.0.1:8080` | service (signal-cli HTTP) | NO | **YES** — signal-cli daemon is a local service |
| `platforms/api_server.py` | 56 | `"127.0.0.1"` | host (API server default) | NO | **YES** — API server bind address |
| `platforms/api_server.py` | 2838 | `"127.0.0.1"` (in socket.connect) | port conflict check | N/A | NO — ephemeral port check only |
| `platforms/feishu.py` | 195 | `"127.0.0.1"` | host (webhook default) | NO | **YES** — Feishu webhook callback host |
| `platforms/bluebubbles.py` | 41 | `"127.0.0.1"` | host (webhook default) | NO | **YES** — BlueBubbles webhook host |
| `platforms/bluebubbles.py` | 224 | `"127.0.0.1", "localhost", "::"` | host fallback logic | PARTIAL | MAYBE — fallback normalization |
| `platforms/webhook.py` | 151 | `"127.0.0.1"` (in socket.connect) | port conflict check | N/A | NO — ephemeral port check only |
| `platforms/wecom_callback.py` | 115 | `"127.0.0.1"` (in socket.connect) | port conflict check | N/A | NO — ephemeral port check only |
| `config.py` | 1268 | `"127.0.0.1"` | host (BLUEBUBBLES_WEBHOOK_HOST default) | NO | **YES** — BlueBubbles webhook default |

## Service/port hardcodes (potential new atlas service refs)

| File | Line | Value | Port | Service context |
|------|------|-------|------|----------------|
| `platforms/whatsapp.py` | 405,472,504,703,742,789,880,898,926 | `http://127.0.0.1:{self._bridge_port}` | Dynamic (`_bridge_port` from config) | WhatsApp bridge HTTP API endpoints |
| `platforms/signal.py` | 175 | `http://127.0.0.1:8080` | 8080 | signal-cli daemon HTTP mode |
| `platforms/api_server.py` | 56 | `127.0.0.1` | 8642 | Gateway API server (DEFAULT_HOST/DEFAULT_PORT) |
| `platforms/feishu.py` | 195 | `127.0.0.1` | 8765 | Feishu webhook callback (DEFAULT_WEBHOOK_HOST/PORT=8765) |
| `platforms/bluebubbles.py` | 41 | `127.0.0.1` | 8645 | BlueBubbles webhook (DEFAULT_WEBHOOK_HOST/PORT) |
| `platforms/webhook.py` | ~140 | dynamic `self._host/self._port` | dynamic | Generic webhook platform server |
| `platforms/wecom_callback.py` | ~110 | dynamic `self._host/self._port` | dynamic | WeCom callback server |

### Key opportunity: WhatsApp bridge URLs

The WhatsApp adapter (`platforms/whatsapp.py`) makes **9 HTTP calls** to `http://127.0.0.1:{self._bridge_port}/` for the locally-running Node.js WhatsApp bridge. The `_bridge_port` is configured via `WHATSAPP_BRIDGE_PORT` env var or defaults in the adapter.

These are **platform bridge service URLs** — perfect candidates for atlas service refs:
```
whatsapp_bridge:
  type: service
  host: 127.0.0.1
  port: <dynamic from WHATSAPP_BRIDGE_PORT>
  protocol: http
  description: Local WhatsApp bridge (Node.js)
```

## Comment/docstring hardcodes (leave as-is)

| File | Line | Value | Context |
|------|------|-------|---------|
| `run.py` | 230 | `~/.laia/.env` | Docstring comment — "Load environment variables from ~/.laia/.env first" |
| `run.py` | 661 | `~/.laia/config.yaml` | Docstring in `_load_gateway_config()` |
| `run.py` | 937 | `~/.laia/checkpoints/` | Comment explaining checkpoint cleanup path |
| `run.py` | 1535-1536 | `~/.laia/config.yaml` | Docstring for prefill_messages_file path resolution |
| `run.py` | 1573 | `~/.laia/config.yaml` | Docstring for agent.system_prompt path |
| `run.py` | 2378 | `~/.laia/.env` | Warning message about GATEWAY_ALLOW_ALL_USERS |
| `run.py` | 5630 | `localhost`/`127.0.0.1`/`0.0.0.0` | **REAL CODE** — URL display logic in `_resolve_laia_bin()` |
| `status.py` | 8 | `~/.laia` | Docstring — "LAIA_HOME defaults to ~/.laia" |
| `sticker_cache.py` | 8 | `~/.laia/sticker_cache.json` | Docstring describing cache location |
| `runtime_footer.py` | 7 | `~/.laia/config.yaml` | Docstring describing config location |
| `pairing.py` | 18 | `~/.laia/pairing/` | Docstring describing storage location |
| `hooks.py` | 5 | `~/.laia/hooks/` | Docstring describing hook discovery path |
| `channel_directory.py` | 5 | `~/.laia/channel_directory.json` | Docstring describing cache location |
| `config.py` | 481-482 | `~/.laia/config.yaml` | Docstring in `load_gateway_config()` |
| `base.py` | 393 | `~/.laia/.env` | Error message text |
| `platforms/api_server.py` | 20 | `http://localhost:8642/v1` | **REAL CODE** — docstring example URL for OpenAI-compatible frontends |
| `platforms/signal.py` | 10 | `127.0.0.1:8080` | **REAL CODE** — docstring requirement statement |
| `platforms/feishu_comment_rules.py` | 6-7 | `~/.laia/feishu_comment_rules.json`, `~/.laia/feishu_comment_pairing.json` | Docstring describing config paths |

## Notes on ephemeral port checks (NOT candidates for atlas)

Lines like `socket.connect(('127.0.0.1', port))` in `webhook.py:151`, `wecom_callback.py:115`, and `api_server.py:2838` are **port conflict detection only** — they check if a port is already in use before binding. These are:
- Ephemeral checks (no persistent service reference needed)
- Already-freed ports after the check
- Pure infrastructure, not business logic

**Not** candidates for atlas service refs.

## Atlas.yaml gaps identified

The following local services have **no atlas entry**:

| Service | File(s) | Port | Notes |
|---------|---------|------|-------|
| WhatsApp bridge | `whatsapp.py` | Dynamic (default ~9000) | Node.js bridge, port via WHATSAPP_BRIDGE_PORT |
| Signal CLI | `signal.py` | 8080 | signal-cli daemon HTTP mode |
| API server | `api_server.py` | 8642 | Gateway's OpenAI-compatible API |
| Feishu webhook | `feishu.py` | 8765 | Webhook callback receiver |
| BlueBubbles webhook | `bluebubbles.py` | 8645 | iMessage via BlueBubbles |
| Generic webhook | `webhook.py` | dynamic | User-configured webhook platform |
| WeCom callback | `wecom_callback.py` | dynamic | WeCom HTTP callback server |

## Priority recommendations

1. **HIGH**: WhatsApp bridge URLs — 9 hardcoded `127.0.0.1:{port}` in one file alone
2. **HIGH**: Signal CLI `http://127.0.0.1:8080` — clear service endpoint
3. **MEDIUM**: API server `127.0.0.1:8642` — if users want to reference it externally
4. **LOW**: Feishu/BlueBubbles webhook hosts — defaults only, rarely changed
