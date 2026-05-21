"""Marketplace persistence helpers (plugins + skills).

Pure-ish functions operating on `AgoraStore.db.conn` and the filesystem layout
defined in `config.Settings`. No FastAPI / HTTP concerns here — that's
`marketplace.py`. Keeping these separate lets us unit-test the storage layer
without TestClient.

Layout (under `settings.data_dir`, typically `/srv/laia/agora`):
    plugin-store/<slug>-<version>.tar.gz       ← blobs (published or personal)
    skill-store/<slug>-<version>.md            ← skill markdown files
    installed-plugins/<user_slug>/<plugin>/    ← extracted per-user dir for loader
    installed-skills/<user_slug>/<skill>.md    ← per-user skill copy
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import tarfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import settings
from .models import now_iso


# ── Constants ──────────────────────────────────────────────────────────────

VISIBILITY_PERSONAL = "personal"
VISIBILITY_PUBLISHED = "published"

STATUS_DRAFT = "draft"
STATUS_REVIEW = "review"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"

PLUGIN_KINDS = {"backend", "standalone", "exclusive", "forwarder"}

# Conservative regex for slugs — matches LAIA plugin convention.
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_VERSION_RE = re.compile(r"^[a-zA-Z0-9._-]{1,32}$")


# ── Errors ─────────────────────────────────────────────────────────────────


class MarketplaceError(Exception):
    """Base error — subclasses map to HTTP responses in marketplace.py."""

    http_status = 400


class ValidationError(MarketplaceError):
    http_status = 422


class NotFoundError(MarketplaceError):
    http_status = 404


class ForbiddenError(MarketplaceError):
    http_status = 403


class ConflictError(MarketplaceError):
    http_status = 409


class PayloadTooLarge(MarketplaceError):
    http_status = 413


# ── DTO ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PluginRow:
    id: str
    slug: str
    version: str
    kind: str
    manifest_yaml: str
    blob_path: str
    owner_user_id: str
    visibility: str
    status: str
    forward_tools_json: str | None
    created_at: str
    approved_at: str | None
    rejected_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "slug": self.slug,
            "version": self.version,
            "kind": self.kind,
            "manifest_yaml": self.manifest_yaml,
            "owner_user_id": self.owner_user_id,
            "visibility": self.visibility,
            "status": self.status,
            "forward_tools": json.loads(self.forward_tools_json) if self.forward_tools_json else [],
            "created_at": self.created_at,
            "approved_at": self.approved_at,
            "rejected_reason": self.rejected_reason,
        }


@dataclass(frozen=True)
class SkillRow:
    id: str
    slug: str
    owner_user_id: str
    manifest_md: str
    blob_path: str | None
    visibility: str
    status: str
    created_at: str
    approved_at: str | None
    rejected_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "slug": self.slug,
            "owner_user_id": self.owner_user_id,
            "manifest_md": self.manifest_md,
            "visibility": self.visibility,
            "status": self.status,
            "created_at": self.created_at,
            "approved_at": self.approved_at,
            "rejected_reason": self.rejected_reason,
        }


# ── Helpers ────────────────────────────────────────────────────────────────


def _validate_slug(slug: str, field: str = "slug") -> None:
    if not _SLUG_RE.match(slug):
        raise ValidationError(f"invalid {field} '{slug}' — must match {_SLUG_RE.pattern}")


def _validate_version(version: str) -> None:
    if not _VERSION_RE.match(version):
        raise ValidationError(f"invalid version '{version}'")


def _row_to_plugin(row) -> PluginRow:
    return PluginRow(
        id=row["id"], slug=row["slug"], version=row["version"], kind=row["kind"],
        manifest_yaml=row["manifest_yaml"], blob_path=row["blob_path"],
        owner_user_id=row["owner_user_id"], visibility=row["visibility"],
        status=row["status"], forward_tools_json=row["forward_tools_json"],
        created_at=row["created_at"], approved_at=row["approved_at"],
        rejected_reason=row["rejected_reason"],
    )


def _row_to_skill(row) -> SkillRow:
    return SkillRow(
        id=row["id"], slug=row["slug"], owner_user_id=row["owner_user_id"],
        manifest_md=row["manifest_md"], blob_path=row["blob_path"],
        visibility=row["visibility"], status=row["status"],
        created_at=row["created_at"], approved_at=row["approved_at"],
        rejected_reason=row["rejected_reason"],
    )


# ── Plugin tarball validation ──────────────────────────────────────────────


def validate_plugin_tarball(blob: bytes, *, expected_slug: str) -> dict[str, Any]:
    """Parse a tar.gz blob, return the manifest as dict.

    Enforces:
      - size cap (config.plugin_upload_max_bytes).
      - no absolute or `..` paths inside.
      - top-level directory matches expected_slug.
      - contains plugin.yaml (or plugin.yml) and __init__.py.

    Returns the parsed manifest (yaml.safe_load) as dict.
    """
    if len(blob) > settings.plugin_upload_max_bytes:
        raise PayloadTooLarge(
            f"plugin tarball is {len(blob)} bytes, max {settings.plugin_upload_max_bytes}"
        )
    try:
        tf = tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz")
    except tarfile.TarError as exc:
        raise ValidationError(f"not a valid tar.gz: {exc}") from exc

    members = tf.getmembers()
    if not members:
        raise ValidationError("tarball is empty")

    # Determine top-level directory (must be exactly one, and equal to slug).
    top_levels = {m.name.split("/", 1)[0] for m in members if m.name and m.name != "."}
    top_levels.discard("")
    if len(top_levels) != 1:
        raise ValidationError(
            f"tarball must have a single top-level directory, found: {sorted(top_levels)}"
        )
    top = next(iter(top_levels))
    if top != expected_slug:
        raise ValidationError(
            f"tarball top-level dir is '{top}', expected '{expected_slug}'"
        )

    has_manifest = False
    has_init = False
    manifest_bytes: bytes | None = None
    for m in members:
        norm = os.path.normpath(m.name)
        if norm.startswith("..") or os.path.isabs(norm):
            raise ValidationError(f"unsafe path inside tarball: {m.name}")
        if m.islnk() or m.issym():
            raise ValidationError(f"links not allowed inside tarball: {m.name}")
        base = m.name.split("/")[-1]
        if base in ("plugin.yaml", "plugin.yml") and not has_manifest:
            has_manifest = True
            f = tf.extractfile(m)
            if f is not None:
                manifest_bytes = f.read()
        if base == "__init__.py":
            has_init = True

    if not has_manifest:
        raise ValidationError("tarball is missing plugin.yaml")
    if not has_init:
        raise ValidationError("tarball is missing __init__.py")

    try:
        import yaml  # type: ignore[import-untyped]
        manifest = yaml.safe_load(manifest_bytes.decode("utf-8") if manifest_bytes else "")
    except Exception as exc:
        raise ValidationError(f"invalid plugin.yaml: {exc}") from exc

    if not isinstance(manifest, dict):
        raise ValidationError("plugin.yaml must be a mapping")
    decl_slug = str(manifest.get("slug") or manifest.get("name") or "").strip()
    if decl_slug and decl_slug != expected_slug:
        raise ValidationError(
            f"plugin.yaml slug '{decl_slug}' does not match upload slug '{expected_slug}'"
        )
    kind = str(manifest.get("kind") or "standalone").strip()
    if kind not in PLUGIN_KINDS:
        raise ValidationError(f"plugin.yaml kind '{kind}' must be one of {sorted(PLUGIN_KINDS)}")

    return manifest


def extract_plugin_tarball(blob: bytes, dest_dir: Path) -> None:
    """Extract a validated tarball into dest_dir/<slug>/.

    Caller must have run validate_plugin_tarball first.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    tf = tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz")
    # Python 3.12+ requires a filter; "data" is the safest one.
    try:
        tf.extractall(path=dest_dir, filter="data")  # type: ignore[arg-type]
    except TypeError:
        tf.extractall(path=dest_dir)


# ── Plugin CRUD ────────────────────────────────────────────────────────────


def insert_plugin(
    store,
    *,
    slug: str,
    version: str,
    kind: str,
    manifest_yaml: str,
    blob_bytes: bytes,
    owner_user_id: str,
    forward_tools: list[str] | None = None,
) -> PluginRow:
    _validate_slug(slug)
    _validate_version(version)
    if kind not in PLUGIN_KINDS:
        raise ValidationError(f"invalid kind '{kind}'")

    # Persist blob to FS first; if DB insert fails we remove the blob.
    settings.ensure_dirs()
    blob_path = settings.plugin_store_dir / f"{slug}-{version}.tar.gz"
    if blob_path.exists():
        # Either same user republishing same version → reject; or stale orphan.
        existing = store.db.conn.execute(
            "SELECT 1 FROM plugin_registry WHERE slug = ? AND version = ?",
            (slug, version),
        ).fetchone()
        if existing:
            raise ConflictError(f"plugin {slug}@{version} already exists")
        # Orphan blob: replace.
    blob_path.write_bytes(blob_bytes)

    pid = "plg_" + uuid.uuid4().hex[:12]
    ts = now_iso()
    forward_tools_json = json.dumps(forward_tools) if forward_tools else None
    try:
        store.db.conn.execute(
            "INSERT INTO plugin_registry "
            "(id, slug, version, kind, manifest_yaml, blob_path, owner_user_id, "
            "visibility, status, forward_tools_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                pid, slug, version, kind, manifest_yaml, str(blob_path),
                owner_user_id, VISIBILITY_PERSONAL, STATUS_DRAFT,
                forward_tools_json, ts,
            ),
        )
        store.db.conn.commit()
    except Exception:
        # Best effort: roll back the blob if DB write failed.
        try:
            blob_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise

    return get_plugin(store, pid)


def get_plugin(store, plugin_id: str) -> PluginRow:
    row = store.db.conn.execute(
        "SELECT * FROM plugin_registry WHERE id = ?", (plugin_id,)
    ).fetchone()
    if not row:
        raise NotFoundError(f"plugin {plugin_id} not found")
    return _row_to_plugin(row)


def find_plugin(store, *, slug: str, version: str | None = None,
                visibility: str | None = None, status: str | None = None) -> PluginRow | None:
    sql = "SELECT * FROM plugin_registry WHERE slug = ?"
    params: list[Any] = [slug]
    if version:
        sql += " AND version = ?"
        params.append(version)
    if visibility:
        sql += " AND visibility = ?"
        params.append(visibility)
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY created_at DESC LIMIT 1"
    row = store.db.conn.execute(sql, params).fetchone()
    return _row_to_plugin(row) if row else None


def list_my_plugins(store, owner_user_id: str) -> list[PluginRow]:
    rows = store.db.conn.execute(
        "SELECT * FROM plugin_registry WHERE owner_user_id = ? ORDER BY created_at DESC",
        (owner_user_id,),
    ).fetchall()
    return [_row_to_plugin(r) for r in rows]


def list_catalog(store) -> list[PluginRow]:
    rows = store.db.conn.execute(
        "SELECT * FROM plugin_registry WHERE visibility = ? AND status = ? ORDER BY slug, created_at DESC",
        (VISIBILITY_PUBLISHED, STATUS_APPROVED),
    ).fetchall()
    return [_row_to_plugin(r) for r in rows]


def list_pending_plugins(store) -> list[PluginRow]:
    rows = store.db.conn.execute(
        "SELECT * FROM plugin_registry WHERE status = ? ORDER BY created_at",
        (STATUS_REVIEW,),
    ).fetchall()
    return [_row_to_plugin(r) for r in rows]


def submit_plugin_for_review(store, plugin_id: str, owner_user_id: str) -> PluginRow:
    plg = get_plugin(store, plugin_id)
    if plg.owner_user_id != owner_user_id:
        raise ForbiddenError("only the owner can submit this plugin")
    if plg.status not in (STATUS_DRAFT, STATUS_REJECTED):
        raise ConflictError(f"plugin is in status '{plg.status}', cannot resubmit")
    store.db.conn.execute(
        "UPDATE plugin_registry SET status = ?, rejected_reason = NULL WHERE id = ?",
        (STATUS_REVIEW, plugin_id),
    )
    store.db.conn.commit()
    return get_plugin(store, plugin_id)


def approve_plugin(store, plugin_id: str) -> PluginRow:
    plg = get_plugin(store, plugin_id)
    if plg.status != STATUS_REVIEW:
        raise ConflictError(f"plugin is in status '{plg.status}', expected '{STATUS_REVIEW}'")
    store.db.conn.execute(
        "UPDATE plugin_registry SET status = ?, visibility = ?, approved_at = ?, rejected_reason = NULL "
        "WHERE id = ?",
        (STATUS_APPROVED, VISIBILITY_PUBLISHED, now_iso(), plugin_id),
    )
    store.db.conn.commit()
    return get_plugin(store, plugin_id)


def reject_plugin(store, plugin_id: str, reason: str) -> PluginRow:
    plg = get_plugin(store, plugin_id)
    if plg.status != STATUS_REVIEW:
        raise ConflictError(f"plugin is in status '{plg.status}', expected '{STATUS_REVIEW}'")
    reason = (reason or "").strip() or "rejected without reason"
    store.db.conn.execute(
        "UPDATE plugin_registry SET status = ?, visibility = ?, rejected_reason = ? WHERE id = ?",
        (STATUS_REJECTED, VISIBILITY_PERSONAL, reason, plugin_id),
    )
    store.db.conn.commit()
    return get_plugin(store, plugin_id)


def revoke_plugin(store, plugin_id: str, reason: str) -> PluginRow:
    plg = get_plugin(store, plugin_id)
    if plg.status != STATUS_APPROVED:
        raise ConflictError(f"plugin is in status '{plg.status}', expected '{STATUS_APPROVED}'")
    reason = (reason or "").strip() or "revoked by admin"
    store.db.conn.execute(
        "UPDATE plugin_registry SET status = ?, visibility = ?, rejected_reason = ? WHERE id = ?",
        (STATUS_REJECTED, VISIBILITY_PERSONAL, reason, plugin_id),
    )
    store.db.conn.commit()
    return get_plugin(store, plugin_id)


def delete_plugin(store, plugin_id: str, owner_user_id: str) -> None:
    plg = get_plugin(store, plugin_id)
    if plg.owner_user_id != owner_user_id:
        raise ForbiddenError("only the owner can delete this plugin")
    install_count = store.db.conn.execute(
        "SELECT COUNT(*) FROM plugin_installs WHERE plugin_id = ?", (plugin_id,)
    ).fetchone()[0]
    if install_count > 0:
        raise ConflictError(
            f"plugin has {install_count} active install(s); uninstall first or revoke"
        )
    store.db.conn.execute("DELETE FROM plugin_registry WHERE id = ?", (plugin_id,))
    store.db.conn.commit()
    try:
        Path(plg.blob_path).unlink(missing_ok=True)
    except Exception:
        pass


# ── Plugin installs ────────────────────────────────────────────────────────


def install_plugin(store, *, user_id: str, plugin_id: str,
                   settings_json: str | None = None) -> dict[str, Any]:
    plg = get_plugin(store, plugin_id)
    # Personal plugins can only be installed by their owner.
    if plg.visibility == VISIBILITY_PERSONAL and plg.owner_user_id != user_id:
        raise ForbiddenError("this plugin is personal and not owned by you")
    # Published plugins must be approved.
    if plg.visibility == VISIBILITY_PUBLISHED and plg.status != STATUS_APPROVED:
        raise ConflictError("plugin is not approved")
    # Personal draft is OK for the owner.
    ts = now_iso()
    store.db.conn.execute(
        "INSERT INTO plugin_installs (user_id, plugin_id, active, settings_json, installed_at) "
        "VALUES (?, ?, 1, ?, ?) "
        "ON CONFLICT(user_id, plugin_id) DO UPDATE SET active = 1, "
        "settings_json = COALESCE(excluded.settings_json, plugin_installs.settings_json), "
        "installed_at = excluded.installed_at",
        (user_id, plugin_id, settings_json, ts),
    )
    store.db.conn.commit()
    return {"user_id": user_id, "plugin_id": plugin_id, "active": True, "installed_at": ts}


def uninstall_plugin(store, *, user_id: str, plugin_id: str) -> bool:
    cur = store.db.conn.execute(
        "DELETE FROM plugin_installs WHERE user_id = ? AND plugin_id = ?",
        (user_id, plugin_id),
    )
    store.db.conn.commit()
    return cur.rowcount > 0


def list_user_installs(store, user_id: str) -> list[dict[str, Any]]:
    rows = store.db.conn.execute(
        "SELECT pi.user_id, pi.plugin_id, pi.active, pi.settings_json, pi.installed_at, "
        "       pr.slug, pr.version, pr.kind, pr.visibility, pr.status, pr.forward_tools_json "
        "FROM plugin_installs pi "
        "JOIN plugin_registry pr ON pr.id = pi.plugin_id "
        "WHERE pi.user_id = ? AND pi.active = 1 "
        "ORDER BY pi.installed_at DESC",
        (user_id,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append({
            "plugin_id": r["plugin_id"],
            "slug": r["slug"],
            "version": r["version"],
            "kind": r["kind"],
            "visibility": r["visibility"],
            "status": r["status"],
            "installed_at": r["installed_at"],
            "forward_tools": json.loads(r["forward_tools_json"]) if r["forward_tools_json"] else [],
            "settings": json.loads(r["settings_json"]) if r["settings_json"] else {},
        })
    return out


def installs_count_for_plugin(store, plugin_id: str) -> int:
    return store.db.conn.execute(
        "SELECT COUNT(*) FROM plugin_installs WHERE plugin_id = ? AND active = 1",
        (plugin_id,),
    ).fetchone()[0]


# ── Materialise per-user installed-plugins dir ─────────────────────────────


def materialize_installed_plugins(store, *, user_id: str, user_slug: str) -> Path:
    """Extract every active install for `user_id` into a single dir.

    Returns the path of the per-user installed-plugins dir (suitable for
    ``LAIA_EXTRA_PLUGIN_DIRS``). The dir is rebuilt from scratch so it
    always reflects the current install set.

    Idempotent and cheap when nothing changed (we still re-extract — keeps
    the implementation simple). Callers should normally invalidate the pool
    on install/uninstall to trigger the next run.
    """
    settings.ensure_dirs()
    target = settings.installed_plugins_root / user_slug
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)

    for install in list_user_installs(store, user_id):
        plg = get_plugin(store, install["plugin_id"])
        blob_path = Path(plg.blob_path)
        if not blob_path.exists():
            continue
        blob_bytes = blob_path.read_bytes()
        # Reuse the validator's "data" filter behavior.
        extract_plugin_tarball(blob_bytes, target)
    return target


def collect_forward_tools_for_user(store, user_id: str) -> list[str]:
    """Aggregate `forward_tools` from every active install of `user_id`."""
    rows = store.db.conn.execute(
        "SELECT pr.forward_tools_json FROM plugin_installs pi "
        "JOIN plugin_registry pr ON pr.id = pi.plugin_id "
        "WHERE pi.user_id = ? AND pi.active = 1",
        (user_id,),
    ).fetchall()
    out: set[str] = set()
    for r in rows:
        if r["forward_tools_json"]:
            try:
                for t in json.loads(r["forward_tools_json"]) or []:
                    if isinstance(t, str) and t:
                        out.add(t)
            except Exception:
                pass
    return sorted(out)


# ── Skill CRUD ─────────────────────────────────────────────────────────────


def insert_skill(
    store,
    *,
    slug: str,
    manifest_md: str,
    owner_user_id: str,
) -> SkillRow:
    _validate_slug(slug)
    if not manifest_md or not manifest_md.strip():
        raise ValidationError("skill manifest is empty")
    if len(manifest_md.encode("utf-8")) > settings.skill_upload_max_bytes:
        raise PayloadTooLarge("skill markdown exceeds max size")

    settings.ensure_dirs()
    blob_path = settings.skill_store_dir / f"{slug}.md"
    blob_path.write_text(manifest_md, encoding="utf-8")

    sid = "skl_" + uuid.uuid4().hex[:12]
    ts = now_iso()
    try:
        store.db.conn.execute(
            "INSERT INTO skill_registry "
            "(id, slug, owner_user_id, manifest_md, blob_path, visibility, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (sid, slug, owner_user_id, manifest_md, str(blob_path),
             VISIBILITY_PERSONAL, STATUS_DRAFT, ts),
        )
        store.db.conn.commit()
    except Exception:
        try:
            blob_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise
    return get_skill(store, sid)


def get_skill(store, skill_id: str) -> SkillRow:
    row = store.db.conn.execute(
        "SELECT * FROM skill_registry WHERE id = ?", (skill_id,)
    ).fetchone()
    if not row:
        raise NotFoundError(f"skill {skill_id} not found")
    return _row_to_skill(row)


def find_skill(store, *, slug: str, visibility: str | None = None) -> SkillRow | None:
    sql = "SELECT * FROM skill_registry WHERE slug = ?"
    params: list[Any] = [slug]
    if visibility:
        sql += " AND visibility = ?"
        params.append(visibility)
    sql += " ORDER BY created_at DESC LIMIT 1"
    row = store.db.conn.execute(sql, params).fetchone()
    return _row_to_skill(row) if row else None


def list_my_skills(store, owner_user_id: str) -> list[SkillRow]:
    rows = store.db.conn.execute(
        "SELECT * FROM skill_registry WHERE owner_user_id = ? ORDER BY created_at DESC",
        (owner_user_id,),
    ).fetchall()
    return [_row_to_skill(r) for r in rows]


def list_skill_catalog(store) -> list[SkillRow]:
    rows = store.db.conn.execute(
        "SELECT * FROM skill_registry WHERE visibility = ? AND status = ? ORDER BY slug",
        (VISIBILITY_PUBLISHED, STATUS_APPROVED),
    ).fetchall()
    return [_row_to_skill(r) for r in rows]


def list_pending_skills(store) -> list[SkillRow]:
    rows = store.db.conn.execute(
        "SELECT * FROM skill_registry WHERE status = ? ORDER BY created_at",
        (STATUS_REVIEW,),
    ).fetchall()
    return [_row_to_skill(r) for r in rows]


def submit_skill_for_review(store, skill_id: str, owner_user_id: str) -> SkillRow:
    sk = get_skill(store, skill_id)
    if sk.owner_user_id != owner_user_id:
        raise ForbiddenError("only the owner can submit this skill")
    if sk.status not in (STATUS_DRAFT, STATUS_REJECTED):
        raise ConflictError(f"skill is in status '{sk.status}', cannot resubmit")
    store.db.conn.execute(
        "UPDATE skill_registry SET status = ?, rejected_reason = NULL WHERE id = ?",
        (STATUS_REVIEW, skill_id),
    )
    store.db.conn.commit()
    return get_skill(store, skill_id)


def approve_skill(store, skill_id: str) -> SkillRow:
    sk = get_skill(store, skill_id)
    if sk.status != STATUS_REVIEW:
        raise ConflictError(f"skill is in status '{sk.status}', expected '{STATUS_REVIEW}'")
    store.db.conn.execute(
        "UPDATE skill_registry SET status = ?, visibility = ?, approved_at = ?, rejected_reason = NULL "
        "WHERE id = ?",
        (STATUS_APPROVED, VISIBILITY_PUBLISHED, now_iso(), skill_id),
    )
    store.db.conn.commit()
    return get_skill(store, skill_id)


def reject_skill(store, skill_id: str, reason: str) -> SkillRow:
    sk = get_skill(store, skill_id)
    if sk.status != STATUS_REVIEW:
        raise ConflictError(f"skill is in status '{sk.status}', expected '{STATUS_REVIEW}'")
    reason = (reason or "").strip() or "rejected without reason"
    store.db.conn.execute(
        "UPDATE skill_registry SET status = ?, visibility = ?, rejected_reason = ? WHERE id = ?",
        (STATUS_REJECTED, VISIBILITY_PERSONAL, reason, skill_id),
    )
    store.db.conn.commit()
    return get_skill(store, skill_id)


def delete_skill(store, skill_id: str, owner_user_id: str) -> None:
    sk = get_skill(store, skill_id)
    if sk.owner_user_id != owner_user_id:
        raise ForbiddenError("only the owner can delete this skill")
    install_count = store.db.conn.execute(
        "SELECT COUNT(*) FROM skill_installs WHERE skill_id = ?", (skill_id,)
    ).fetchone()[0]
    if install_count > 0:
        raise ConflictError(f"skill has {install_count} active install(s)")
    store.db.conn.execute("DELETE FROM skill_registry WHERE id = ?", (skill_id,))
    store.db.conn.commit()
    if sk.blob_path:
        try:
            Path(sk.blob_path).unlink(missing_ok=True)
        except Exception:
            pass


def install_skill(store, *, user_id: str, skill_id: str) -> dict[str, Any]:
    sk = get_skill(store, skill_id)
    if sk.visibility == VISIBILITY_PERSONAL and sk.owner_user_id != user_id:
        raise ForbiddenError("this skill is personal and not owned by you")
    if sk.visibility == VISIBILITY_PUBLISHED and sk.status != STATUS_APPROVED:
        raise ConflictError("skill is not approved")
    ts = now_iso()
    store.db.conn.execute(
        "INSERT INTO skill_installs (user_id, skill_id, active, installed_at) "
        "VALUES (?, ?, 1, ?) "
        "ON CONFLICT(user_id, skill_id) DO UPDATE SET active = 1, installed_at = excluded.installed_at",
        (user_id, skill_id, ts),
    )
    store.db.conn.commit()
    return {"user_id": user_id, "skill_id": skill_id, "active": True, "installed_at": ts}


def uninstall_skill(store, *, user_id: str, skill_id: str) -> bool:
    cur = store.db.conn.execute(
        "DELETE FROM skill_installs WHERE user_id = ? AND skill_id = ?",
        (user_id, skill_id),
    )
    store.db.conn.commit()
    return cur.rowcount > 0


def list_user_skill_installs(store, user_id: str) -> list[dict[str, Any]]:
    rows = store.db.conn.execute(
        "SELECT si.user_id, si.skill_id, si.active, si.installed_at, "
        "       sr.slug, sr.manifest_md, sr.visibility, sr.status "
        "FROM skill_installs si "
        "JOIN skill_registry sr ON sr.id = si.skill_id "
        "WHERE si.user_id = ? AND si.active = 1 "
        "ORDER BY si.installed_at DESC",
        (user_id,),
    ).fetchall()
    return [
        {
            "skill_id": r["skill_id"],
            "slug": r["slug"],
            "manifest_md": r["manifest_md"],
            "visibility": r["visibility"],
            "status": r["status"],
            "installed_at": r["installed_at"],
        }
        for r in rows
    ]


def materialize_installed_skills(store, *, user_id: str, user_slug: str) -> Path:
    """Write each active skill install as a separate .md file in the user's dir."""
    settings.ensure_dirs()
    target = settings.installed_skills_root / user_slug
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    for install in list_user_skill_installs(store, user_id):
        (target / f"{install['slug']}.md").write_text(install["manifest_md"], encoding="utf-8")
    return target


__all__ = [
    "VISIBILITY_PERSONAL", "VISIBILITY_PUBLISHED",
    "STATUS_DRAFT", "STATUS_REVIEW", "STATUS_APPROVED", "STATUS_REJECTED",
    "PLUGIN_KINDS",
    "MarketplaceError", "ValidationError", "NotFoundError", "ForbiddenError",
    "ConflictError", "PayloadTooLarge",
    "PluginRow", "SkillRow",
    "validate_plugin_tarball", "extract_plugin_tarball",
    "insert_plugin", "get_plugin", "find_plugin", "list_my_plugins",
    "list_catalog", "list_pending_plugins",
    "submit_plugin_for_review", "approve_plugin", "reject_plugin", "revoke_plugin",
    "delete_plugin",
    "install_plugin", "uninstall_plugin", "list_user_installs",
    "installs_count_for_plugin",
    "materialize_installed_plugins", "collect_forward_tools_for_user",
    "insert_skill", "get_skill", "find_skill", "list_my_skills",
    "list_skill_catalog", "list_pending_skills",
    "submit_skill_for_review", "approve_skill", "reject_skill", "delete_skill",
    "install_skill", "uninstall_skill", "list_user_skill_installs",
    "materialize_installed_skills",
]
