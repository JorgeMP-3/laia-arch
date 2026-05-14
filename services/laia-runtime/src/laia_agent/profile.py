from __future__ import annotations

import fcntl
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .config import AgentConfig
from .status import read_json, utc_now, write_json


PROFILE_TEXT_FILES = {
    "persona": "persona.md",
    "instructions": "instructions.md",
}
PROFILE_JSON_FILES = {
    "skills": "skills.json",
    "preferences": "preferences.json",
}


def default_persona(config: AgentConfig) -> str:
    return (
        f"# Persona de {config.employee}\n\n"
        "Eres un agente personal de LAIA. Trabajas dentro de tu contenedor, "
        "usas tu workspace personal y pides confirmacion antes de acciones destructivas.\n"
    )


def default_instructions(_config: AgentConfig) -> str:
    return (
        "# Instrucciones operativas\n\n"
        "- Mantener el trabajo dentro de `/opt/laia/workspaces/personal`.\n"
        "- Registrar resultados relevantes en el workspace.\n"
        "- No acceder a rutas de otros agentes.\n"
        "- No modificar el runtime salvo actualizacion gestionada por `laiactl`.\n"
    )


def default_skills() -> dict[str, Any]:
    return {
        "version": 1,
        "enabled": ["workspace.read", "workspace.write", "tasks.basic"],
        "available": [
            {"id": "workspace.read", "description": "Leer nodos del workspace personal."},
            {"id": "workspace.write", "description": "Crear y actualizar nodos del workspace personal."},
            {"id": "tasks.basic", "description": "Procesar tareas basicas de la cola local."},
        ],
    }


def default_preferences() -> dict[str, Any]:
    return {
        "version": 1,
        "language": "es",
        "tone": "directo",
        "requires_confirmation_for": ["delete", "restore", "external_publish"],
    }


def ensure_profile(config: AgentConfig) -> dict[str, Any]:
    with profile_lock(config):
        config.profile_dir.mkdir(parents=True, exist_ok=True)
        files = {
            "persona": config.profile_dir / PROFILE_TEXT_FILES["persona"],
            "instructions": config.profile_dir / PROFILE_TEXT_FILES["instructions"],
            "skills": config.profile_dir / PROFILE_JSON_FILES["skills"],
            "preferences": config.profile_dir / PROFILE_JSON_FILES["preferences"],
        }
        if not files["persona"].exists():
            files["persona"].write_text(default_persona(config), encoding="utf-8")
        if not files["instructions"].exists():
            files["instructions"].write_text(default_instructions(config), encoding="utf-8")
        if not files["skills"].exists():
            write_json(files["skills"], default_skills())
        if not files["preferences"].exists():
            write_json(files["preferences"], default_preferences())
        write_json(config.profile_dir / "profile.status.json", {"updated_at": utc_now(), "status": "ready"})
        return _read_profile(config)


def get_profile(config: AgentConfig) -> dict[str, Any]:
    with profile_lock(config):
        ensure_profile_files_only(config)
        return _read_profile(config)


def _read_profile(config: AgentConfig) -> dict[str, Any]:
    return {
        "path": str(config.profile_dir),
        "persona": (config.profile_dir / PROFILE_TEXT_FILES["persona"]).read_text(encoding="utf-8"),
        "instructions": (config.profile_dir / PROFILE_TEXT_FILES["instructions"]).read_text(encoding="utf-8"),
        "skills": read_json(config.profile_dir / PROFILE_JSON_FILES["skills"]),
        "preferences": read_json(config.profile_dir / PROFILE_JSON_FILES["preferences"]),
    }


def update_profile(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    with profile_lock(config):
        ensure_profile_files_only(config)
        if "persona" in payload:
            _write_text_profile(config, "persona", str(payload["persona"]))
        if "instructions" in payload:
            _write_text_profile(config, "instructions", str(payload["instructions"]))
        if "skills" in payload:
            _write_json_profile(config, "skills", payload["skills"])
        if "preferences" in payload:
            _write_json_profile(config, "preferences", payload["preferences"])
        write_json(config.profile_dir / "profile.status.json", {"updated_at": utc_now(), "status": "updated"})
        return _read_profile(config)


def set_skill(config: AgentConfig, skill_id: str, enabled: bool) -> dict[str, Any]:
    with profile_lock(config):
        ensure_profile_files_only(config)
        skills_path = config.profile_dir / PROFILE_JSON_FILES["skills"]
        skills = read_json(skills_path)
        current = set(skills.get("enabled", []))
        if enabled:
            current.add(skill_id)
        else:
            current.discard(skill_id)
        skills["enabled"] = sorted(current)
        write_json(skills_path, skills)
        return {"skills": skills}


def ensure_profile_files_only(config: AgentConfig) -> None:
    config.profile_dir.mkdir(parents=True, exist_ok=True)
    required = {
        config.profile_dir / PROFILE_TEXT_FILES["persona"]: default_persona(config),
        config.profile_dir / PROFILE_TEXT_FILES["instructions"]: default_instructions(config),
    }
    for path, content in required.items():
        if not path.exists():
            path.write_text(content, encoding="utf-8")
    json_required = {
        config.profile_dir / PROFILE_JSON_FILES["skills"]: default_skills(),
        config.profile_dir / PROFILE_JSON_FILES["preferences"]: default_preferences(),
    }
    for path, content in json_required.items():
        if not path.exists():
            write_json(path, content)


def _write_text_profile(config: AgentConfig, name: str, content: str) -> None:
    path = config.profile_dir / PROFILE_TEXT_FILES[name]
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def _write_json_profile(config: AgentConfig, name: str, content: Any) -> None:
    if not isinstance(content, dict):
        raise ValueError(f"{name} must be a JSON object")
    write_json(config.profile_dir / PROFILE_JSON_FILES[name], content)


@contextmanager
def profile_lock(config: AgentConfig):
    config.profile_dir.mkdir(parents=True, exist_ok=True)
    lock_path = config.profile_dir / ".profile.lock"
    with lock_path.open("w", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
