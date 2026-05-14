# AGORA Backend API Reference

## Base URL

- **Production:** `https://agora.laiajmp.org/api`
- **Development:** `http://localhost:8088/api`
- **Tailscale:** `http://100.73.36.92:8088/api`

## Versión: 0.2.0 | Tests: 69 | DB: SQLite

---

## Auth

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/login` | — | Login. Returns `access_token` (30min) + `refresh_token` (7d) + user |
| `POST` | `/api/refresh` | — | Renew access token with refresh token |
| `GET` | `/api/me` | JWT | Get authenticated user profile |
| `POST` | `/api/me/password` | JWT | Change password (requires old password) |

**Auth Flow:**
```
POST /api/login { username, password }
  → { access_token, refresh_token, user }

All subsequent requests:
  Authorization: Bearer <access_token>

On 401: POST /api/refresh { refresh_token }
  → { access_token, refresh_token }
```

**Password hashing:** PBKDF2-HMAC-SHA256 (600k iterations).  
**Token signing:** JWT HS256 via stdlib `hmac` + `hashlib`.  
**Rate limiting:** 10 requests/minute per IP on login.

---

## Personal Agent

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/agent/profile` | JWT | Read full agent profile (persona, instructions, skills, preferences) |
| `PATCH` | `/api/agent/profile` | JWT | Update profile fields (partial) |
| `GET` | `/api/agent/status` | JWT | Agent runtime status (LXD state, service, healthcheck) |
| `GET` | `/api/agent/tasks` | JWT | Agent task queue (inbox/done/failed) |
| `PATCH` | `/api/agent` | JWT | Change agent display name |

**Profile fields:** `persona`, `instructions`, `skills` (enabled/available lists), `preferences` (language, tone)

---

## Users (Admin only)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/users` | Admin | List active users |
| `GET` | `/api/users/{id}` | Admin | User detail + associated agents |
| `POST` | `/api/users` | Admin | Create employee (optional: create LXD agent) |
| `PATCH` | `/api/users/{id}` | Admin | Update display_name or role |
| `DELETE` | `/api/users/{id}` | Admin | Soft-delete (disable) user |
| `POST` | `/api/users/{id}/reset-password` | Admin | Reset password, returns new one |

**Roles:** `agora_admin`, `employee`, `agent`

---

## Tasks

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/tasks` | JWT | List tasks (admin: all, user: own) |
| `POST` | `/api/tasks` | JWT | Create task |
| `PATCH` | `/api/tasks/{id}` | JWT | Update task (status, priority, assignee) |
| `DELETE` | `/api/tasks/{id}` | JWT | Delete task (own or admin) |

**Task statuses:** `pending`, `active`, `blocked`, `done`, `cancelled`  
**Priorities:** `low`, `medium`, `high`, `urgent`

---

## Agents LXD (Admin only)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/agents` | List all LXD agents with status |
| `GET` | `/api/agents/{slug}` | Agent detail |
| `POST` | `/api/agents` | Create agent (container + runtime + workspace) |
| `POST` | `/api/agents/{slug}/start` | Start agent service |
| `POST` | `/api/agents/{slug}/stop` | Stop agent service |
| `POST` | `/api/agents/{slug}/restart` | Restart agent service |
| `POST` | `/api/agents/{slug}/snapshot` | Create LXD snapshot |
| `POST` | `/api/agents/{slug}/restore` | Restore from snapshot |
| `GET` | `/api/agents/{slug}/snapshots` | List snapshots |
| `GET` | `/api/agents/{slug}/logs` | View agent logs |
| `POST` | `/api/agents/{slug}/tasks` | Send task to agent inbox |
| `GET` | `/api/agents/{slug}/tasks/{id}` | Read task result |
| `POST` | `/api/agents/{slug}/install-runtime` | Install/update runtime |
| `DELETE` | `/api/agents/{slug}` | Delete agent container |

**Non-admin users** see only their own agent via `/api/agents`.

---

## Coordinator (LAIA AGORA)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/coordinator/report` | Admin | Full report: tasks, agents, alerts |
| `POST` | `/api/coordinator/assign` | Admin | Assign global task (visible to all users) |
| `GET` | `/api/coordinator/health` | — | Coordinator status (running, last_check) |
| `POST` | `/api/coordinator/check` | Admin | Force manual fleet check |
| `GET` | `/api/coordinator/alerts` | Admin | List active alerts |

---

## Fleet & Monitor

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/fleet/status` | Admin | Aggregated fleet status (all agents) |
| `GET` | `/api/monitor/health` | — | FleetMonitor status |
| `POST` | `/api/monitor/check` | Admin | Force manual health check |

---

## Workspace & Events

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/workspace/nodes` | JWT | List/search workspace nodes |
| `GET` | `/api/workspace/nodes/{slug}` | JWT | Get a workspace node |
| `POST` | `/api/workspace/nodes` | JWT | Create/update workspace node |
| `GET` | `/api/events` | Admin | List recent events (default 100) |
| `POST` | `/api/events` | JWT | Record an event |

---

## Observability

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/health` | — | Complete health check (DB, LXD, laiactl, coordinator) |
| `GET` | `/api/metrics` | Admin | Request counters, latencies, top endpoints |
| `WebSocket` | `/ws?token=<jwt>` | JWT | Real-time push for alerts and events |

---

## WebSocket Events

Connect to `ws://localhost:8088/ws?token=<jwt>`

| Event | Trigger | Recipients |
|---|---|---|
| `connected` | On successful auth | Connected user |
| `pong` | Response to `ping` | Connected user |
| `coordinator_alert` | Coordinator detects issue | Admin users |
| `agent_state_change` | Agent LXD state changes | Admin users |

Keepalive: send `{"type": "ping"}` → receive `{"type": "pong"}`
