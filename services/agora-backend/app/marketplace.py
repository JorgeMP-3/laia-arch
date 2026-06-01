"""Marketplace HTTP layer.

Endpoints:

  GET    /api/plugins/catalog                       — list approved+published plugins
  GET    /api/skills/catalog                        — list approved+published skills

  GET    /api/me/plugins                            — my plugins (any status/visibility)
  POST   /api/me/plugins/upload                     — upload a plugin tarball
  POST   /api/me/plugins/{id}/publish               — submit for review
  DELETE /api/me/plugins/{id}                       — delete owned plugin
  POST   /api/me/plugins/install                    — install a plugin into my user
  DELETE /api/me/plugins/installs/{plugin_id}       — uninstall
  GET    /api/me/plugins/installs                   — list my installs

  GET    /api/me/skills, POST upload, etc — symmetric to plugins.

  GET    /api/admin/marketplace/pending             — admin: pending review
  POST   /api/admin/plugins/{id}/approve            — admin
  POST   /api/admin/plugins/{id}/reject             — admin
  POST   /api/admin/plugins/{id}/revoke             — admin
  Skills idem with /api/admin/skills/{id}/...
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field as PydField

from .auth import current_user, require_roles
from .models import Event, User
from . import marketplace_storage as ms
from .marketplace_storage import (
    MarketplaceError,
    PLUGIN_KINDS,
)


logger = logging.getLogger(__name__)

router = APIRouter(tags=["marketplace"])


# ── Pydantic DTOs ──────────────────────────────────────────────────────────


class PluginOut(BaseModel):
    id: str
    slug: str
    version: str
    kind: str
    owner_user_id: str
    visibility: str
    status: str
    forward_tools: list[str] = PydField(default_factory=list)
    created_at: str
    approved_at: str | None = None
    rejected_reason: str | None = None


class SkillOut(BaseModel):
    id: str
    slug: str
    owner_user_id: str
    visibility: str
    status: str
    created_at: str
    approved_at: str | None = None
    rejected_reason: str | None = None
    manifest_md: str | None = None  # included on detail endpoints only


class PluginUploadRequest(BaseModel):
    slug: str
    version: str
    kind: str = "standalone"
    forward_tools: list[str] = PydField(default_factory=list)
    blob_b64: str  # base64-encoded tar.gz


class PluginInstallRequest(BaseModel):
    slug: str | None = None
    plugin_id: str | None = None
    version: str | None = None
    settings: dict[str, Any] | None = None


class SkillInstallRequest(BaseModel):
    slug: str | None = None
    skill_id: str | None = None


class SkillUploadRequest(BaseModel):
    slug: str
    manifest_md: str


class RejectRequest(BaseModel):
    reason: str = ""


class PendingResponse(BaseModel):
    plugins: list[PluginOut]
    skills: list[SkillOut]


# ── Helpers ────────────────────────────────────────────────────────────────


def _plugin_to_out(plg: ms.PluginRow) -> PluginOut:
    d = plg.to_dict()
    return PluginOut(
        id=d["id"], slug=d["slug"], version=d["version"], kind=d["kind"],
        owner_user_id=d["owner_user_id"], visibility=d["visibility"], status=d["status"],
        forward_tools=d["forward_tools"], created_at=d["created_at"],
        approved_at=d["approved_at"], rejected_reason=d["rejected_reason"],
    )


def _skill_to_out(sk: ms.SkillRow, include_md: bool = False) -> SkillOut:
    d = sk.to_dict()
    return SkillOut(
        id=d["id"], slug=d["slug"], owner_user_id=d["owner_user_id"],
        visibility=d["visibility"], status=d["status"],
        created_at=d["created_at"], approved_at=d["approved_at"],
        rejected_reason=d["rejected_reason"],
        manifest_md=d["manifest_md"] if include_md else None,
    )


def _map_error(exc: MarketplaceError) -> HTTPException:
    return HTTPException(status_code=exc.http_status, detail=str(exc))


def _get_store():
    """Lazy import to keep module import-time light and testable."""
    from .storage import store as _store
    return _store


def _invalidate_pool_for(user_id: str) -> None:
    """Best-effort pool invalidation. AgentPool wiring is in agent_pool.py."""
    try:
        from .agent_pool import AgentPool  # noqa: WPS433
    except Exception:
        return
    invalidator = getattr(AgentPool, "invalidate_user_static", None)
    if invalidator is None:
        return
    try:
        invalidator(user_id)
    except Exception as exc:
        logger.debug("pool invalidate failed for %s: %s", user_id, exc)


def _audit(user_id: str | None, kind: str, summary: str) -> None:
    try:
        store = _get_store()
        store.record_event(Event(event_type=kind, actor_id=user_id, summary=summary))
    except Exception:
        pass


# ── Plugin endpoints (user-scoped) ─────────────────────────────────────────


@router.get("/api/plugins/catalog", response_model=list[PluginOut])
def list_plugin_catalog(_: User = Depends(current_user)):
    """Handle GET /api/plugins/catalog."""
    return [_plugin_to_out(p) for p in ms.list_catalog(_get_store())]


@router.get("/api/me/plugins", response_model=list[PluginOut])
def list_my_plugins(user: User = Depends(current_user)):
    """Handle GET /api/me/plugins."""
    return [_plugin_to_out(p) for p in ms.list_my_plugins(_get_store(), user.id)]


@router.post("/api/me/plugins/upload", response_model=PluginOut)
def upload_my_plugin(payload: PluginUploadRequest, user: User = Depends(current_user)):
    """Handle POST /api/me/plugins/upload."""
    if payload.kind not in PLUGIN_KINDS:
        raise HTTPException(status_code=400, detail=f"invalid kind: {payload.kind}")
    import base64
    try:
        data = base64.b64decode(payload.blob_b64, validate=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"invalid blob_b64: {exc}") from exc
    try:
        manifest = ms.validate_plugin_tarball(data, expected_slug=payload.slug)
    except MarketplaceError as exc:
        raise _map_error(exc) from exc

    try:
        plg = ms.insert_plugin(
            _get_store(),
            slug=payload.slug,
            version=payload.version,
            kind=str(manifest.get("kind", payload.kind)),
            # We persist the original yaml when present, otherwise the repr.
            manifest_yaml=_yaml_dump(manifest),
            blob_bytes=data,
            owner_user_id=user.id,
            forward_tools=payload.forward_tools,
        )
    except MarketplaceError as exc:
        raise _map_error(exc) from exc

    _audit(user.id, "plugin_uploaded",
           f"{user.username} uploaded plugin {plg.slug}@{plg.version}")
    return _plugin_to_out(plg)


def _yaml_dump(manifest: dict[str, Any]) -> str:
    try:
        import yaml  # type: ignore[import-untyped]
        return yaml.safe_dump(manifest, sort_keys=True)
    except Exception:
        return repr(manifest)


@router.post("/api/me/plugins/{plugin_id}/publish", response_model=PluginOut)
def publish_my_plugin(plugin_id: str, user: User = Depends(current_user)):
    """Handle POST /api/me/plugins/{plugin_id}/publish."""
    try:
        plg = ms.submit_plugin_for_review(_get_store(), plugin_id, user.id)
    except MarketplaceError as exc:
        raise _map_error(exc) from exc
    _audit(user.id, "plugin_submitted_for_review",
           f"{user.username} submitted plugin {plg.slug} for review")
    return _plugin_to_out(plg)


@router.delete("/api/me/plugins/{plugin_id}")
def delete_my_plugin(plugin_id: str, user: User = Depends(current_user)):
    """Handle DELETE /api/me/plugins/{plugin_id}."""
    try:
        ms.delete_plugin(_get_store(), plugin_id, user.id)
    except MarketplaceError as exc:
        raise _map_error(exc) from exc
    _audit(user.id, "plugin_deleted",
           f"{user.username} deleted plugin {plugin_id}")
    return {"ok": True}


@router.post("/api/me/plugins/install")
def install_my_plugin(payload: PluginInstallRequest, user: User = Depends(current_user)):
    """Handle POST /api/me/plugins/install."""
    store = _get_store()
    if not payload.plugin_id and not payload.slug:
        raise HTTPException(status_code=400, detail="provide plugin_id or slug")

    if payload.plugin_id:
        try:
            plg = ms.get_plugin(store, payload.plugin_id)
        except MarketplaceError as exc:
            raise _map_error(exc) from exc
    else:
        plg = ms.find_plugin(
            store,
            slug=payload.slug or "",
            version=payload.version,
            visibility=ms.VISIBILITY_PUBLISHED,
            status=ms.STATUS_APPROVED,
        )
        # Fallback: maybe it's their own personal plugin.
        if plg is None:
            plg = ms.find_plugin(
                store, slug=payload.slug or "", version=payload.version,
                visibility=ms.VISIBILITY_PERSONAL,
            )
            if plg and plg.owner_user_id != user.id:
                plg = None
        if plg is None:
            raise HTTPException(status_code=404, detail=f"no installable plugin for slug={payload.slug}")

    import json as _json
    settings_json = _json.dumps(payload.settings) if payload.settings is not None else None
    try:
        ms.install_plugin(store, user_id=user.id, plugin_id=plg.id, settings_json=settings_json)
    except MarketplaceError as exc:
        raise _map_error(exc) from exc

    _invalidate_pool_for(user.id)
    _audit(user.id, "plugin_installed",
           f"{user.username} installed plugin {plg.slug}@{plg.version}")
    return {"ok": True, "plugin_id": plg.id, "slug": plg.slug, "version": plg.version}


@router.delete("/api/me/plugins/installs/{plugin_id}")
def uninstall_my_plugin(plugin_id: str, user: User = Depends(current_user)):
    """Handle DELETE /api/me/plugins/installs/{plugin_id}."""
    removed = ms.uninstall_plugin(_get_store(), user_id=user.id, plugin_id=plugin_id)
    if not removed:
        raise HTTPException(status_code=404, detail="not installed")
    _invalidate_pool_for(user.id)
    _audit(user.id, "plugin_uninstalled",
           f"{user.username} uninstalled plugin {plugin_id}")
    return {"ok": True}


@router.get("/api/me/plugins/installs")
def list_my_installs(user: User = Depends(current_user)):
    """Handle GET /api/me/plugins/installs."""
    return ms.list_user_installs(_get_store(), user.id)


# ── Skill endpoints (user-scoped) ──────────────────────────────────────────


@router.get("/api/skills/catalog", response_model=list[SkillOut])
def list_skill_catalog(_: User = Depends(current_user)):
    """Handle GET /api/skills/catalog."""
    return [_skill_to_out(s) for s in ms.list_skill_catalog(_get_store())]


@router.get("/api/me/skills", response_model=list[SkillOut])
def list_my_skills(user: User = Depends(current_user)):
    """Handle GET /api/me/skills."""
    return [_skill_to_out(s) for s in ms.list_my_skills(_get_store(), user.id)]


@router.post("/api/me/skills/upload", response_model=SkillOut)
def upload_my_skill(payload: SkillUploadRequest, user: User = Depends(current_user)):
    """Handle POST /api/me/skills/upload."""
    try:
        sk = ms.insert_skill(_get_store(), slug=payload.slug, manifest_md=payload.manifest_md,
                             owner_user_id=user.id)
    except MarketplaceError as exc:
        raise _map_error(exc) from exc
    _audit(user.id, "skill_uploaded",
           f"{user.username} uploaded skill {sk.slug}")
    return _skill_to_out(sk, include_md=True)


@router.post("/api/me/skills/{skill_id}/publish", response_model=SkillOut)
def publish_my_skill(skill_id: str, user: User = Depends(current_user)):
    """Handle POST /api/me/skills/{skill_id}/publish."""
    try:
        sk = ms.submit_skill_for_review(_get_store(), skill_id, user.id)
    except MarketplaceError as exc:
        raise _map_error(exc) from exc
    _audit(user.id, "skill_submitted_for_review",
           f"{user.username} submitted skill {sk.slug} for review")
    return _skill_to_out(sk)


@router.delete("/api/me/skills/{skill_id}")
def delete_my_skill(skill_id: str, user: User = Depends(current_user)):
    """Handle DELETE /api/me/skills/{skill_id}."""
    try:
        ms.delete_skill(_get_store(), skill_id, user.id)
    except MarketplaceError as exc:
        raise _map_error(exc) from exc
    _audit(user.id, "skill_deleted",
           f"{user.username} deleted skill {skill_id}")
    return {"ok": True}


@router.post("/api/me/skills/install")
def install_my_skill(payload: SkillInstallRequest, user: User = Depends(current_user)):
    """Handle POST /api/me/skills/install."""
    store = _get_store()
    if not payload.skill_id and not payload.slug:
        raise HTTPException(status_code=400, detail="provide skill_id or slug")
    if payload.skill_id:
        try:
            sk = ms.get_skill(store, payload.skill_id)
        except MarketplaceError as exc:
            raise _map_error(exc) from exc
    else:
        sk = ms.find_skill(store, slug=payload.slug or "", visibility=ms.VISIBILITY_PUBLISHED)
        if sk is None:
            sk = ms.find_skill(store, slug=payload.slug or "", visibility=ms.VISIBILITY_PERSONAL)
            if sk and sk.owner_user_id != user.id:
                sk = None
        if sk is None:
            raise HTTPException(status_code=404, detail=f"no installable skill for slug={payload.slug}")
    try:
        ms.install_skill(store, user_id=user.id, skill_id=sk.id)
    except MarketplaceError as exc:
        raise _map_error(exc) from exc
    _invalidate_pool_for(user.id)
    _audit(user.id, "skill_installed",
           f"{user.username} installed skill {sk.slug}")
    return {"ok": True, "skill_id": sk.id, "slug": sk.slug}


@router.delete("/api/me/skills/installs/{skill_id}")
def uninstall_my_skill(skill_id: str, user: User = Depends(current_user)):
    """Handle DELETE /api/me/skills/installs/{skill_id}."""
    removed = ms.uninstall_skill(_get_store(), user_id=user.id, skill_id=skill_id)
    if not removed:
        raise HTTPException(status_code=404, detail="not installed")
    _invalidate_pool_for(user.id)
    return {"ok": True}


@router.get("/api/me/skills/installs")
def list_my_skill_installs(user: User = Depends(current_user)):
    """Handle GET /api/me/skills/installs."""
    return ms.list_user_skill_installs(_get_store(), user.id)


# ── Admin moderation ───────────────────────────────────────────────────────


@router.get("/api/admin/marketplace/pending", response_model=PendingResponse)
def list_marketplace_pending(_: User = Depends(require_roles("agora_admin"))):
    """Handle GET /api/admin/marketplace/pending."""
    store = _get_store()
    return PendingResponse(
        plugins=[_plugin_to_out(p) for p in ms.list_pending_plugins(store)],
        skills=[_skill_to_out(s) for s in ms.list_pending_skills(store)],
    )


@router.post("/api/admin/plugins/{plugin_id}/approve", response_model=PluginOut)
def admin_approve_plugin(plugin_id: str, actor: User = Depends(require_roles("agora_admin"))):
    """Handle POST /api/admin/plugins/{plugin_id}/approve."""
    try:
        plg = ms.approve_plugin(_get_store(), plugin_id)
    except MarketplaceError as exc:
        raise _map_error(exc) from exc
    _audit(actor.id, "plugin_approved",
           f"admin {actor.username} approved plugin {plg.slug}@{plg.version}")
    return _plugin_to_out(plg)


@router.post("/api/admin/plugins/{plugin_id}/reject", response_model=PluginOut)
def admin_reject_plugin(plugin_id: str, payload: RejectRequest,
                        actor: User = Depends(require_roles("agora_admin"))):
    """Handle POST /api/admin/plugins/{plugin_id}/reject."""
    try:
        plg = ms.reject_plugin(_get_store(), plugin_id, payload.reason)
    except MarketplaceError as exc:
        raise _map_error(exc) from exc
    _audit(actor.id, "plugin_rejected",
           f"admin {actor.username} rejected plugin {plg.slug}@{plg.version}: {payload.reason}")
    return _plugin_to_out(plg)


@router.post("/api/admin/plugins/{plugin_id}/revoke", response_model=PluginOut)
def admin_revoke_plugin(plugin_id: str, payload: RejectRequest,
                        actor: User = Depends(require_roles("agora_admin"))):
    """Handle POST /api/admin/plugins/{plugin_id}/revoke."""
    try:
        plg = ms.revoke_plugin(_get_store(), plugin_id, payload.reason)
    except MarketplaceError as exc:
        raise _map_error(exc) from exc
    # When we revoke we don't auto-uninstall — admins decide explicitly.
    _audit(actor.id, "plugin_revoked",
           f"admin {actor.username} revoked plugin {plg.slug}@{plg.version}: {payload.reason}")
    return _plugin_to_out(plg)


@router.post("/api/admin/skills/{skill_id}/approve", response_model=SkillOut)
def admin_approve_skill(skill_id: str, actor: User = Depends(require_roles("agora_admin"))):
    """Handle POST /api/admin/skills/{skill_id}/approve."""
    try:
        sk = ms.approve_skill(_get_store(), skill_id)
    except MarketplaceError as exc:
        raise _map_error(exc) from exc
    _audit(actor.id, "skill_approved",
           f"admin {actor.username} approved skill {sk.slug}")
    return _skill_to_out(sk)


@router.post("/api/admin/skills/{skill_id}/reject", response_model=SkillOut)
def admin_reject_skill(skill_id: str, payload: RejectRequest,
                       actor: User = Depends(require_roles("agora_admin"))):
    """Handle POST /api/admin/skills/{skill_id}/reject."""
    try:
        sk = ms.reject_skill(_get_store(), skill_id, payload.reason)
    except MarketplaceError as exc:
        raise _map_error(exc) from exc
    _audit(actor.id, "skill_rejected",
           f"admin {actor.username} rejected skill {sk.slug}: {payload.reason}")
    return _skill_to_out(sk)
