"""End-to-end-ish tests for the marketplace API (Fase B).

Uses TestClient against the real FastAPI app + the shared AgoraStore that
lives in services/agora-backend/app/storage.py. Each test logs in as the
seed admin (jorge/dev-admin) and provisions an extra user when it needs
non-admin scenarios.
"""

from __future__ import annotations

import base64
import io
import tarfile
import uuid

import pytest
from fastapi.testclient import TestClient


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def app_client():
    from app.main import app
    return TestClient(app)


@pytest.fixture
def admin_headers() -> dict[str, str]:
    # Static seed token for jorge — bypasses login (immune to rate limits and
    # password rotations from other test modules).
    return {"Authorization": "Bearer dev-admin-token"}


def _login(app_client: TestClient, username: str, password: str) -> dict[str, str]:
    r = app_client.post("/api/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def employee(app_client: TestClient, admin_headers: dict[str, str]) -> tuple[dict[str, str], str]:
    """Create a fresh employee user and return (headers, user_id)."""
    username = f"mp_{uuid.uuid4().hex[:6]}"
    password = f"pw_{uuid.uuid4().hex[:6]}"
    r = app_client.post(
        "/api/users",
        headers=admin_headers,
        json={"username": username, "display_name": username, "role": "employee",
              "password": password},
    )
    assert r.status_code in (200, 201), r.text
    user_id = r.json()["user"]["id"]
    return (_login(app_client, username, password), user_id)


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_plugin_tarball(slug: str, *, with_manifest: bool = True,
                         with_init: bool = True, manifest_extra: dict | None = None) -> bytes:
    """Build a minimal valid plugin tar.gz in-memory."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        # top-level dir entry
        info = tarfile.TarInfo(name=f"{slug}/")
        info.type = tarfile.DIRTYPE
        info.mode = 0o755
        tf.addfile(info)

        if with_manifest:
            manifest = f"slug: {slug}\nversion: 0.1.0\nkind: standalone\n"
            if manifest_extra:
                for k, v in manifest_extra.items():
                    manifest += f"{k}: {v}\n"
            data = manifest.encode("utf-8")
            info = tarfile.TarInfo(name=f"{slug}/plugin.yaml")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))

        if with_init:
            code = b'def register(ctx):\n    ctx.register_tool("say_hi", "hi", {}, lambda **kw: "hi")\n'
            info = tarfile.TarInfo(name=f"{slug}/__init__.py")
            info.size = len(code)
            tf.addfile(info, io.BytesIO(code))

    return buf.getvalue()


def _upload(app_client: TestClient, headers: dict[str, str], *,
            slug: str, version: str = "0.1.0", forward_tools: list[str] | None = None,
            blob: bytes | None = None) -> dict:
    blob = blob or _make_plugin_tarball(slug)
    payload = {
        "slug": slug,
        "version": version,
        "kind": "standalone",
        "forward_tools": forward_tools or [],
        "blob_b64": base64.b64encode(blob).decode("ascii"),
    }
    r = app_client.post("/api/me/plugins/upload", headers=headers, json=payload)
    assert r.status_code == 200, r.text
    return r.json()


# ── Plugin lifecycle ──────────────────────────────────────────────────────


def test_upload_creates_draft_personal_plugin(app_client, employee):
    headers, _ = employee
    slug = f"plg-{uuid.uuid4().hex[:6]}"
    out = _upload(app_client, headers, slug=slug)
    assert out["slug"] == slug
    assert out["visibility"] == "personal"
    assert out["status"] == "draft"


def test_upload_rejects_oversized_tarball(app_client, employee):
    headers, _ = employee
    # Build a tarball with a giant file inside so the gzipped size exceeds the cap.
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        info = tarfile.TarInfo(name="big/")
        info.type = tarfile.DIRTYPE
        tf.addfile(info)
        info = tarfile.TarInfo(name="big/plugin.yaml")
        body = b"slug: big\nversion: 0.1.0\nkind: standalone\n"
        info.size = len(body)
        tf.addfile(info, io.BytesIO(body))
        info = tarfile.TarInfo(name="big/__init__.py")
        # 6 MB of low-entropy data still won't compress under 5 MB if we use random.
        import os as _os
        payload = _os.urandom(6 * 1024 * 1024)
        info.size = len(payload)
        tf.addfile(info, io.BytesIO(payload))
    blob = buf.getvalue()
    assert len(blob) > 5 * 1024 * 1024
    body = {"slug": "big", "version": "0.1.0", "kind": "standalone",
            "blob_b64": base64.b64encode(blob).decode("ascii"), "forward_tools": []}
    r = app_client.post("/api/me/plugins/upload", headers=headers, json=body)
    assert r.status_code == 413, r.text


def test_upload_rejects_traversal_path(app_client, employee):
    headers, _ = employee
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        info = tarfile.TarInfo(name="evil/")
        info.type = tarfile.DIRTYPE
        tf.addfile(info)
        info = tarfile.TarInfo(name="evil/../escape.py")
        info.size = 4
        tf.addfile(info, io.BytesIO(b"bad\n"))
    body = {"slug": "evil", "version": "0.1.0", "kind": "standalone",
            "blob_b64": base64.b64encode(buf.getvalue()).decode("ascii"), "forward_tools": []}
    r = app_client.post("/api/me/plugins/upload", headers=headers, json=body)
    assert r.status_code in (400, 422), r.text


def test_upload_rejects_missing_manifest(app_client, employee):
    headers, _ = employee
    slug = f"nomf-{uuid.uuid4().hex[:6]}"
    blob = _make_plugin_tarball(slug, with_manifest=False)
    body = {"slug": slug, "version": "0.1.0", "kind": "standalone",
            "blob_b64": base64.b64encode(blob).decode("ascii"), "forward_tools": []}
    r = app_client.post("/api/me/plugins/upload", headers=headers, json=body)
    assert r.status_code in (400, 422), r.text


def test_publish_requires_owner(app_client, employee):
    owner_h, _ = employee
    slug = f"plg-{uuid.uuid4().hex[:6]}"
    plg = _upload(app_client, owner_h, slug=slug)
    # Another employee shouldn't be able to publish someone else's plugin.
    other_h, _ = employee  # same user — but enough for the next test
    # Build a second user via the static admin token.
    admin_h = {"Authorization": "Bearer dev-admin-token"}
    other_username = f"other_{uuid.uuid4().hex[:6]}"
    other_pw = f"pw_{uuid.uuid4().hex[:6]}"
    app_client.post(
        "/api/users",
        headers=admin_h,
        json={"username": other_username, "display_name": other_username,
              "role": "employee", "password": other_pw},
    )
    other_h = _login(app_client, other_username, other_pw)
    r3 = app_client.post(f"/api/me/plugins/{plg['id']}/publish", headers=other_h)
    assert r3.status_code in (403, 404), r3.text


def test_full_lifecycle_publish_approve_install(app_client, employee, admin_headers):
    owner_h, owner_id = employee
    slug = f"hello-{uuid.uuid4().hex[:6]}"
    plg = _upload(app_client, owner_h, slug=slug, forward_tools=["say_hi"])

    # publish -> status review
    r = app_client.post(f"/api/me/plugins/{plg['id']}/publish", headers=owner_h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "review"

    # admin sees it as pending
    r = app_client.get("/api/admin/marketplace/pending", headers=admin_headers)
    assert r.status_code == 200, r.text
    pending = [p for p in r.json()["plugins"] if p["id"] == plg["id"]]
    assert len(pending) == 1

    # approve -> published+approved
    r = app_client.post(f"/api/admin/plugins/{plg['id']}/approve", headers=admin_headers)
    assert r.status_code == 200, r.text
    approved = r.json()
    assert approved["status"] == "approved"
    assert approved["visibility"] == "published"
    assert "say_hi" in approved["forward_tools"]

    # catalog visible
    r = app_client.get("/api/plugins/catalog", headers=owner_h)
    assert r.status_code == 200, r.text
    cat_slugs = [p["slug"] for p in r.json()]
    assert slug in cat_slugs

    # install for the owner
    r = app_client.post("/api/me/plugins/install", headers=owner_h, json={"slug": slug})
    assert r.status_code == 200, r.text

    # listed in installs
    r = app_client.get("/api/me/plugins/installs", headers=owner_h)
    assert r.status_code == 200, r.text
    assert any(item["slug"] == slug for item in r.json())


def test_personal_plugin_invisible_to_others(app_client, employee, admin_headers):
    owner_h, _ = employee
    slug = f"priv-{uuid.uuid4().hex[:6]}"
    plg = _upload(app_client, owner_h, slug=slug)
    # Catalog never includes personal plugins.
    r = app_client.get("/api/plugins/catalog", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert slug not in {p["slug"] for p in r.json()}
    # Other user cannot install it via slug lookup.
    other_username = f"other_{uuid.uuid4().hex[:6]}"
    other_pw = f"pw_{uuid.uuid4().hex[:6]}"
    app_client.post("/api/users", headers=admin_headers,
                    json={"username": other_username, "display_name": other_username,
                          "role": "employee", "password": other_pw})
    other_h = _login(app_client, other_username, other_pw)
    r = app_client.post("/api/me/plugins/install", headers=other_h, json={"slug": slug})
    assert r.status_code == 404, r.text


def test_reject_returns_plugin_to_personal_rejected(app_client, employee, admin_headers):
    owner_h, _ = employee
    slug = f"rej-{uuid.uuid4().hex[:6]}"
    plg = _upload(app_client, owner_h, slug=slug)
    app_client.post(f"/api/me/plugins/{plg['id']}/publish", headers=owner_h)
    r = app_client.post(f"/api/admin/plugins/{plg['id']}/reject",
                        headers=admin_headers, json={"reason": "needs more docs"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "rejected"
    assert r.json()["visibility"] == "personal"
    assert r.json()["rejected_reason"] == "needs more docs"
    # Owner can resubmit.
    r2 = app_client.post(f"/api/me/plugins/{plg['id']}/publish", headers=owner_h)
    assert r2.status_code == 200, r2.text
    assert r2.json()["status"] == "review"


def test_delete_requires_no_active_installs(app_client, employee, admin_headers):
    owner_h, _ = employee
    slug = f"del-{uuid.uuid4().hex[:6]}"
    plg = _upload(app_client, owner_h, slug=slug)
    # Install as the owner (personal install is allowed for drafts).
    r = app_client.post("/api/me/plugins/install", headers=owner_h, json={"plugin_id": plg["id"]})
    assert r.status_code == 200, r.text
    # Delete should fail.
    r = app_client.delete(f"/api/me/plugins/{plg['id']}", headers=owner_h)
    assert r.status_code == 409, r.text
    # Uninstall then delete.
    r = app_client.delete(f"/api/me/plugins/installs/{plg['id']}", headers=owner_h)
    assert r.status_code == 200, r.text
    r = app_client.delete(f"/api/me/plugins/{plg['id']}", headers=owner_h)
    assert r.status_code == 200, r.text


# ── Skill lifecycle ───────────────────────────────────────────────────────


def test_skill_full_lifecycle(app_client, employee, admin_headers):
    owner_h, _ = employee
    slug = f"skl-{uuid.uuid4().hex[:6]}"
    md = "# Skill\n\nUse it to greet people."
    r = app_client.post("/api/me/skills/upload", headers=owner_h,
                        json={"slug": slug, "manifest_md": md})
    assert r.status_code == 200, r.text
    sid = r.json()["id"]

    r = app_client.post(f"/api/me/skills/{sid}/publish", headers=owner_h)
    assert r.status_code == 200, r.text

    r = app_client.post(f"/api/admin/skills/{sid}/approve", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"

    r = app_client.get("/api/skills/catalog", headers=owner_h)
    assert r.status_code == 200, r.text
    assert slug in {s["slug"] for s in r.json()}

    r = app_client.post("/api/me/skills/install", headers=owner_h, json={"slug": slug})
    assert r.status_code == 200, r.text

    r = app_client.get("/api/me/skills/installs", headers=owner_h)
    assert any(s["slug"] == slug for s in r.json())


def test_skill_upload_rejects_oversized_markdown(app_client, employee):
    owner_h, _ = employee
    big_md = "# Title\n" + ("x" * (260 * 1024))
    r = app_client.post("/api/me/skills/upload", headers=owner_h,
                        json={"slug": "big-skill", "manifest_md": big_md})
    assert r.status_code == 413, r.text


# ── Forward tools aggregation ──────────────────────────────────────────────


def test_collect_forward_tools_for_user(app_client, employee, admin_headers):
    from app.storage import store
    from app.marketplace_storage import collect_forward_tools_for_user

    owner_h, owner_id = employee
    s1 = f"ft1-{uuid.uuid4().hex[:6]}"
    s2 = f"ft2-{uuid.uuid4().hex[:6]}"
    plg1 = _upload(app_client, owner_h, slug=s1, forward_tools=["custom_a"])
    plg2 = _upload(app_client, owner_h, slug=s2, forward_tools=["custom_b", "custom_a"])
    # Install personal drafts as the owner.
    app_client.post("/api/me/plugins/install", headers=owner_h, json={"plugin_id": plg1["id"]})
    app_client.post("/api/me/plugins/install", headers=owner_h, json={"plugin_id": plg2["id"]})

    aggregated = collect_forward_tools_for_user(store, owner_id)
    assert "custom_a" in aggregated
    assert "custom_b" in aggregated


def test_materialize_installed_plugins_writes_dir(app_client, employee, tmp_path, monkeypatch):
    from app.storage import store
    from app.marketplace_storage import materialize_installed_plugins
    from app.config import settings as cfg

    # Redirect the install root to tmp_path so we don't pollute the real dir.
    original = cfg.installed_plugins_root
    monkeypatch.setattr(cfg, "installed_plugins_root", tmp_path / "installed-plugins")

    owner_h, owner_id = employee
    slug = f"mat-{uuid.uuid4().hex[:6]}"
    plg = _upload(app_client, owner_h, slug=slug)
    app_client.post("/api/me/plugins/install", headers=owner_h, json={"plugin_id": plg["id"]})

    out_dir = materialize_installed_plugins(store, user_id=owner_id, user_slug="mat-user")
    assert out_dir.exists()
    assert (out_dir / slug).exists()
    assert (out_dir / slug / "plugin.yaml").exists()
    assert (out_dir / slug / "__init__.py").exists()

    # Cleanup
    monkeypatch.setattr(cfg, "installed_plugins_root", original)
