from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


# Slugs reservados por la plataforma. Ningún user puede crear un agent con
# estos slugs — colisionan con identidades del sistema o roles. Regla ②
# del Documento Definitivo: "LAIA está reservado para el coordinador".
RESERVED_AGENT_SLUGS: frozenset[str] = frozenset({
    "laia", "agora", "arch", "admin", "root", "system",
    "laia-agora", "laia-arch", "laia-core",
})


def _validate_agent_slug(value: str) -> str:
    if value.lower() in RESERVED_AGENT_SLUGS:
        raise ValueError(
            f"slug '{value}' está reservado por la plataforma (LAIA, AGORA, ARCH...)"
        )
    return value


# Role values stored in ``users.role``. ``host_admin`` is reserved for the
# host operator (Jorge / LAIA-ARCH) — the only role allowed to call LXD,
# systemd or filesystem mutations on the host. The Documento Definitivo
# rule ⑥ says admin AGORA does NOT do those operations; currently the
# code still gates them with ``agora_admin`` for backwards compatibility,
# emitting an audit warning when triggered. A future migration will flip
# the gates to ``host_admin`` after Jorge's row is updated.
Role = Literal["agora_admin", "employee", "agent", "host_admin"]
TaskStatus = Literal["pending", "active", "blocked", "done", "cancelled"]
Priority = Literal["low", "medium", "high", "urgent"]
LearningKind = Literal["error", "insight", "pattern", "preference", "skill_observation"]


class User(BaseModel):
    id: str
    username: str
    display_name: str
    role: Role = "employee"
    agent_id: str | None = None
    token: str | None = None
    password: str | None = None
    active: bool = True
    created_at: str = Field(default_factory=now_iso)
    # Per-user LLM configuration (parity with LAIA ARCH providers).
    # api_key is encrypted at rest via the storage layer (Fernet, key in AGORA env).
    llm_provider: str | None = None       # any provider supported by .laia-core/laia_cli/providers.py
    llm_api_key: str | None = None        # encrypted on write, decrypted on read
    llm_base_url: str | None = None       # override for self-hosted / custom endpoints
    llm_model: str | None = None          # specific model id (e.g. "claude-opus-4.6")
    llm_api_mode: str | None = None       # override of auto-detected api_mode
    llm_extras_json: str | None = None    # free-form JSON for advanced settings
    mcp_servers_json: str | None = None   # JSON array of MCP server entries (marketplace-v0.1)


class LLMConfigUpdate(BaseModel):
    provider: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    api_mode: str | None = None
    extras: dict[str, Any] | None = None
    # marketplace-v0.1: per-user MCP servers. Each entry: {name, url, headers?}.
    # Passing ``None`` leaves the field unchanged; passing ``[]`` clears it.
    mcp_servers: list[dict[str, Any]] | None = None


class LLMConfigView(BaseModel):
    """Read-only view of a user's LLM config — api_key is masked."""

    provider: str | None
    base_url: str | None
    model: str | None
    api_mode: str | None
    api_key_masked: str | None  # e.g. "sk-...AbCd" or None
    has_key: bool
    mcp_servers: list[dict[str, Any]] = Field(default_factory=list)


class LLMProviderInfo(BaseModel):
    id: str
    label: str
    transport: str             # openai_chat | anthropic_messages | codex_responses | bedrock_converse
    base_url: str | None = None
    base_url_env_var: str | None = None
    is_aggregator: bool = False
    auth_type: str = "api_key"
    default_models: list[str] = Field(default_factory=list)


class TelegramLinkTokenResponse(BaseModel):
    token: str
    expires_at: float
    expires_in_seconds: int
    deep_link: str | None = None      # e.g. ``https://t.me/<bot>?start=link_<token>``


class TelegramLinkStatus(BaseModel):
    linked: bool
    telegram_user_ids: list[str] = Field(default_factory=list)


class UserCreateRequest(BaseModel):
    # Allow hyphens in the middle (matches the slug regex used by create-agent.sh:39
    # and typical Linux usernames like ``john-doe``). First and last char must be
    # alphanumeric/underscore so we never end up with weird names like ``-bad`` or ``bad-``.
    username: str = Field(
        min_length=2,
        max_length=32,
        pattern=r"^[a-z0-9_][a-z0-9_-]*[a-z0-9_]$|^[a-z0-9_]$",
    )
    display_name: str = Field(min_length=1, max_length=64)
    role: Role = "employee"
    password: str | None = Field(default=None, min_length=4, max_length=128)
    create_agent: bool = False


class UserCreateResponse(BaseModel):
    ok: bool
    user: User
    password: str | None = None


class UserUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=64)
    role: Role | None = None


class UserResetPasswordResponse(BaseModel):
    ok: bool
    new_password: str


class UserResetPasswordRequest(BaseModel):
    new_password: str | None = Field(default=None, min_length=4, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: User


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=4, max_length=128)


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    description: str = ""
    assignee_id: str | None = None
    priority: Priority = "medium"


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=180)
    description: str | None = None
    assignee_id: str | None = None
    priority: Priority | None = None
    status: TaskStatus | None = None


class Task(BaseModel):
    id: str = Field(default_factory=lambda: new_id("task"))
    title: str
    description: str = ""
    assignee_id: str | None = None
    priority: Priority = "medium"
    status: TaskStatus = "pending"
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class EventCreate(BaseModel):
    event_type: str = Field(min_length=1, max_length=80)
    actor_id: str | None = None
    summary: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class Event(EventCreate):
    id: str = Field(default_factory=lambda: new_id("event"))
    created_at: str = Field(default_factory=now_iso)


class Agent(BaseModel):
    id: str
    user_id: str
    container_name: str
    status: Literal["planned", "provisioning", "running", "stopped", "error"] = "planned"
    workspace_path: str
    container_ip: str | None = None
    api_token: str | None = None
    created_at: str = Field(default_factory=now_iso)


# Hard caps for agent area text fields. Without these a client could push
# multi-MB markdown into the soul/instructions, which the AgentPool reads on
# every AIAgent construction — both a memory and a latency hit.
_AGENT_AREA_TEXT_MAX = 50_000  # ~50 KB of markdown is plenty


class AgentArea(BaseModel):
    user_id: str
    agent_display_name: str = Field(min_length=1, max_length=80)
    soul_md: str = Field(default="", max_length=_AGENT_AREA_TEXT_MAX)
    instructions_md: str = Field(default="", max_length=_AGENT_AREA_TEXT_MAX)
    memory_preferences: dict[str, Any] = Field(default_factory=dict)
    behavior_preferences: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class AgentAreaUpdate(BaseModel):
    agent_display_name: str | None = Field(default=None, min_length=1, max_length=80)
    soul_md: str | None = Field(default=None, max_length=_AGENT_AREA_TEXT_MAX)
    instructions_md: str | None = Field(default=None, max_length=_AGENT_AREA_TEXT_MAX)
    memory_preferences: dict[str, Any] | None = None
    behavior_preferences: dict[str, Any] | None = None


class AgentAreaView(BaseModel):
    user: User
    agent: Agent | None = None
    area: AgentArea
    llm: LLMConfigView
    plugins: list[dict[str, Any]] = Field(default_factory=list)
    skills: list[dict[str, Any]] = Field(default_factory=list)
    memory: dict[str, Any] = Field(default_factory=dict)


class AgentLearning(BaseModel):
    """Persistent organic-learning entry attached to a user.

    Stored in ``agent_learnings`` table. ``confidence`` is a 0..1 score
    the agent itself adjusts based on whether subsequent observations
    confirm or contradict the learning; ``times_referenced`` is bumped
    each time the learning is recalled into a session prompt.
    """

    id: str = Field(default_factory=lambda: new_id("lrn"))
    user_id: str
    kind: LearningKind
    title: str = Field(min_length=1, max_length=200)
    content_md: str = Field(min_length=1, max_length=8192)
    tags: str | None = None  # comma-separated for SQL LIKE search
    context: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    times_referenced: int = 0
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


ScheduledJobStatus = Literal["active", "paused", "error"]


class ScheduledJob(BaseModel):
    id: str = Field(default_factory=lambda: new_id("job"))
    user_id: str
    name: str = Field(min_length=1, max_length=120)
    cron_expr: str = Field(min_length=1, max_length=120)
    prompt: str = Field(min_length=1, max_length=16_384)
    deliver: str = "local"
    status: ScheduledJobStatus = "active"
    last_run_at: str | None = None
    last_result: str | None = None
    last_error: str | None = None
    next_run_at: str | None = None
    runs_total: int = 0
    runs_failed: int = 0
    consecutive_failures: int = 0
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class WebhookSubscription(BaseModel):
    id: str = Field(default_factory=lambda: new_id("wh"))
    user_id: str
    slug: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    secret: str
    prompt: str = Field(min_length=1, max_length=8_192)
    deliver: str = "local"
    last_trigger_at: str | None = None
    last_status: str | None = None
    triggers_total: int = 0
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


ChildProfile = Literal["general", "coder", "researcher", "writer"]
ChildRunStatus = Literal["running", "done", "failed", "killed", "timeout"]


class AgentChildRun(BaseModel):
    """Audit row for a sub-AIAgent spawned by a parent agent."""

    id: str = Field(default_factory=lambda: new_id("child"))
    parent_user_id: str
    parent_session_id: str
    profile: ChildProfile = "general"
    purpose: str = Field(min_length=1, max_length=240)
    prompt: str = Field(min_length=1, max_length=16_384)
    response: str | None = None
    tokens_used: int | None = None
    duration_ms: int | None = None
    status: ChildRunStatus = "running"
    error: str | None = None
    started_at: str = Field(default_factory=now_iso)
    finished_at: str | None = None


class AutoImport(BaseModel):
    id: str = Field(default_factory=lambda: new_id("imp"))
    user_id: str
    provider: str = Field(min_length=1, max_length=64)
    config: dict[str, Any] = Field(default_factory=dict)
    last_synced_at: str | None = None
    last_status: str | None = None
    last_count: int = 0
    last_error: str | None = None
    cron_expr: str = "0 */6 * * *"
    target_workspace: str = "private"
    enabled: bool = True
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class WorkspaceNodeCreate(BaseModel):
    slug: str
    title: str
    kind: Literal["index", "project", "topic", "important", "doc", "agent-note", "agent-plan", "agent-log", "script", "reference"] = "doc"
    summary: str = ""
    body: str = ""


# ── LXD / orchestrator models ─────────────────────────────────────────────────

class LxdAgent(BaseModel):
    slug: str
    container: str
    status: str = "unknown"
    lxd_state: str = "unknown"
    ipv4: str = ""
    lxd_snapshots: str = "0"
    image: str = ""
    runtime: str = ""
    service: str = ""
    workspace: str = ""
    workspace_status: str = ""
    created_at: str = ""
    updated_at: str = ""


class CreateAgentRequest(BaseModel):
    slug: str = Field(min_length=2, max_length=32, pattern=r"^[a-z0-9][a-z0-9-]{1,30}$")
    install_runtime: bool = True
    init_workspace: bool = True
    initial_snapshot: bool = True

    @field_validator("slug")
    @classmethod
    def _slug_not_reserved(cls, v: str) -> str:
        return _validate_agent_slug(v)


class RegisterAgentRequest(BaseModel):
    """Register an already-provisioned container in the AGORA DB.

    Use when the admin runs `bash infra/lxd/scripts/create-agent.sh <slug>` on
    the host (which has LXD perms) and pastes its JSON output here.
    """
    slug: str = Field(min_length=2, max_length=32, pattern=r"^[a-z0-9][a-z0-9-]{1,30}$")
    user_id: str
    container_ip: str
    api_token: str
    api_port: int = 9091

    @field_validator("slug")
    @classmethod
    def _slug_not_reserved(cls, v: str) -> str:
        return _validate_agent_slug(v)


class SecretsFetchRequest(BaseModel):
    """An Agora Agent fetches its LLM API key on startup.

    Auth: provide the agent's bootstrap_token (same value that lives in agent.json
    and that is also used as the Bearer token for the agent's HTTP API). AGORA
    verifies the token matches the registered agent and returns the LLM API key
    that lives in env (never persisted to the agent's disk).
    """
    bootstrap_token: str = Field(min_length=8, max_length=128)


class SecretsFetchResponse(BaseModel):
    llm_api_key: str
    llm_provider: str  # e.g. "openrouter", "anthropic", "openai"


class SnapshotRequest(BaseModel):
    name: str = Field(min_length=1, max_length=41, pattern=r"^[a-z0-9][a-z0-9-]{0,40}$")


class AgentTaskCreate(BaseModel):
    task_type: str = Field(min_length=1, max_length=40, pattern=r"^[a-z_]{1,40}$")
    payload: dict[str, Any] = Field(default_factory=dict)


# ── Agent profile models ────────────────────────────────────────────────────

class AgentProfile(BaseModel):
    path: str = ""
    persona: str = ""
    instructions: str = ""
    skills: dict[str, Any] = Field(default_factory=dict)
    preferences: dict[str, Any] = Field(default_factory=dict)
    status: str = ""


class AgentProfileUpdate(BaseModel):
    persona: str | None = None
    instructions: str | None = None
    skills: dict[str, Any] | None = None
    preferences: dict[str, Any] | None = None


class AgentUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=40)
    status: str | None = None


class AgentStatus(BaseModel):
    ok: bool
    slug: str
    container: str
    runtime: str = "unknown"
    healthcheck: str = ""
    lxd_state: str = "unknown"
    ipv4: str = ""
    service: str = "unknown"


class CoordinatorAssignRequest(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    description: str = ""
    priority: Priority = "medium"


class CoordinatorMessage(BaseModel):
    """Inbox row: a message LAIA pushed to a user. Injected into the user's
    system prompt on the next chat turn, then marked as read."""

    id: str = Field(default_factory=lambda: new_id("coord"))
    user_id: str
    from_role: str = "laia"
    text: str
    severity: Literal["info", "warn", "error"] = "info"
    read: bool = False
    created_at: str = Field(default_factory=now_iso)
    read_at: str | None = None
