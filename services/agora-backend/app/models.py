from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


Role = Literal["agora_admin", "employee", "agent"]
TaskStatus = Literal["pending", "active", "blocked", "done", "cancelled"]
Priority = Literal["low", "medium", "high", "urgent"]


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


class LLMConfigUpdate(BaseModel):
    provider: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    api_mode: str | None = None
    extras: dict[str, Any] | None = None


class LLMConfigView(BaseModel):
    """Read-only view of a user's LLM config — api_key is masked."""

    provider: str | None
    base_url: str | None
    model: str | None
    api_mode: str | None
    api_key_masked: str | None  # e.g. "sk-...AbCd" or None
    has_key: bool


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
