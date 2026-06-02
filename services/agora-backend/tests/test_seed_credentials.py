"""Tests del seed de credenciales (storage._ensure_seed_data).

Regresión de la auditoría 2026-06-02 (prod-db-seeds-hardcoded-jorge-credentials):
un arranque limpio en CUALQUIER entorno sembraba jorge/agora_admin con
password "dev-admin" en plaintext y token "dev-admin-token" — y users()
re-inyectaba el token si se rotaba a mano. Contratos nuevos:

- dev: seed determinista (los tests y scripts de infra/dev dependen de él),
  pero la password se guarda HASHEADA, nunca en claro.
- no-dev: jamás credenciales conocidas — password aleatoria (o
  AGORA_ADMIN_PASSWORD), sin bearer estático (salvo AGORA_ADMIN_TOKEN).
- el token de LAIA coordinator es aleatorio por instalación (el literal
  "laia-coordinator-token" era un bearer admin público sin consumidores).
- users() ya no re-inyecta tokens.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.security import verify_password


@pytest.fixture
def fresh_store_factory(monkeypatch, tmp_path):
    """Construye un AgoraStore nuevo sobre un data-dir temporal vacío."""
    from app.config import settings as cfg

    def _make(env: str = "dev", **env_vars):
        data = Path(tempfile.mkdtemp(dir=tmp_path))
        monkeypatch.setattr(cfg, "env", env)
        monkeypatch.setattr(cfg, "data_dir", data)
        monkeypatch.setattr(cfg, "db_path", data / "agora.db")
        monkeypatch.setattr(cfg, "workspaces_root", data / "workspaces")
        monkeypatch.setattr(cfg, "workspace_root", data / "workspaces" / "collective")
        monkeypatch.setattr(cfg, "plugin_store_dir", data / "plugin-store")
        monkeypatch.setattr(cfg, "skill_store_dir", data / "skill-store")
        monkeypatch.setattr(cfg, "installed_plugins_root", data / "installed-plugins")
        monkeypatch.setattr(cfg, "installed_skills_root", data / "installed-skills")
        monkeypatch.setattr(cfg, "users_path", data / "users.json")
        monkeypatch.setattr(cfg, "tasks_path", data / "tasks.json")
        monkeypatch.setattr(cfg, "agents_path", data / "agents.json")
        monkeypatch.setattr(cfg, "events_path", data / "events.jsonl")
        monkeypatch.setattr(cfg, "secondary_workspaces", [])
        for key in ("AGORA_ADMIN_USERNAME", "AGORA_ADMIN_PASSWORD", "AGORA_ADMIN_TOKEN"):
            monkeypatch.delenv(key, raising=False)
        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)

        from app.storage import AgoraStore
        return AgoraStore()

    return _make


def test_dev_seed_keeps_contract_but_hashes_password(fresh_store_factory):
    store = fresh_store_factory(env="dev")
    jorge = store.user_by_id("user_jorge")
    assert jorge is not None
    # Contrato dev intacto: scripts/tests siguen logueando con dev-admin.
    assert jorge.token == "dev-admin-token"
    assert verify_password("dev-admin", jorge.password)
    # Pero la columna ya nunca lleva el plaintext.
    assert jorge.password.startswith("$pbkdf2$")


def test_non_dev_seed_has_no_known_credentials(fresh_store_factory):
    store = fresh_store_factory(env="prod")
    jorge = store.user_by_id("user_jorge")
    assert jorge is not None
    assert not jorge.token  # sin bearer estático por defecto
    assert jorge.password.startswith("$pbkdf2$")
    assert not verify_password("dev-admin", jorge.password)


def test_non_dev_seed_respects_env_overrides(fresh_store_factory):
    store = fresh_store_factory(
        env="prod",
        AGORA_ADMIN_PASSWORD="s3creta-fuerte",
        AGORA_ADMIN_TOKEN="tok-rotado",
    )
    jorge = store.user_by_id("user_jorge")
    assert jorge.token == "tok-rotado"
    assert verify_password("s3creta-fuerte", jorge.password)


def test_laia_coordinator_token_is_random_per_install(fresh_store_factory):
    store = fresh_store_factory(env="dev")
    laia = store.user_by_id("user_laia")
    assert laia is not None
    assert laia.token  # sigue teniendo token (por si algo lo consulta)…
    assert laia.token != "laia-coordinator-token"  # …pero ya no el literal público
    # Y dos instalaciones no comparten token.
    other = fresh_store_factory(env="dev")
    assert other.user_by_id("user_laia").token != laia.token


def test_users_no_longer_self_heals_token(fresh_store_factory):
    store = fresh_store_factory(env="dev")
    jorge = store.user_by_id("user_jorge")
    jorge.token = ""
    store.save_user(jorge)
    # Antes: users() re-aplicaba "dev-admin-token" — rotar era imposible.
    refreshed = next(u for u in store.users() if u.id == "user_jorge")
    assert not refreshed.token
