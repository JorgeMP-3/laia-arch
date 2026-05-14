# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in LAIA, please **do not** open a public issue. Instead, report it privately to the LAIA security team.

## Architecture

LAIA follows a layered security model:

```
User → Cloudflare Tunnel → nginx → AGORA/ARCH backend → LXD containers
```

- **Public access**: Only through Cloudflare Tunnel (no open ports)
- **Admin access**: Tailscale VPN only (ARCH endpoints)
- **Agent isolation**: Each user's agent runs in an unprivileged LXD container
- **Host separation**: LAIA Core (host) vs agent runtimes (containers) have different permission sets

## Secrets Management

- All API keys, tokens, and credentials live in `~/.laia/` (outside the repository)
- Configuration files use `${ENV_VAR}` references, never hardcoded secrets
- File permissions on sensitive files are `600` (owner read/write only)
- `auth.json` and `.env` are excluded from git tracking

## Credential Rotation

If you suspect a key has been compromised:

1. Rotate the key at the provider (Anthropic, OpenAI, Telegram, etc.)
2. Update `~/.laia/.env` with the new key
3. Verify services restart correctly: `make status`
4. Purge any session files that may contain the old key

## Known Security Considerations

| Issue | Status | Mitigation |
|---|---|---|
| Dev credentials in tests | Accepted | `dev-admin` is only used in local development. Production uses proper credentials. |
| `state.db` permissions | Fixed (600) | Session database is owner-only. |
| JWT secret rotation | Manual | Restart backend to regenerate: `pkill -f "uvicorn app.main"` |
| LXD container egress | Requires root rule | `sudo infra/lxd/scripts/fix-egress-root.sh` — one-time setup |
| Rate limiting | Partial | Login endpoint only. Other endpoints pending. |

## Dependency Security

- Zero external Python dependencies for auth (stdlib pbkdf2 + JWT)
- SQLite via stdlib `sqlite3` module
- No npm packages with known CVEs in current lockfile

## Audit Logging

All API access is logged in JSON format to `~/.laia/logs/`:
- Request ID, method, path, status code, duration
- User ID for authenticated requests
- Error details for failed requests

Monitor logs: `laia logs agora -f`
