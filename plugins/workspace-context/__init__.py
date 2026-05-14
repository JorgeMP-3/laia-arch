"""workspace-context — DB-first nodal workspace memory provider for Hermes."""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.memory_provider import MemoryProvider

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from workspace_store import WorkspaceStore, list_workspaces

logger = logging.getLogger(__name__)

DEFAULT_WORKSPACE = "doyouwin"
DEFAULT_INJECT_MODE = "index"
DEFAULT_MAX_CHARS = 8000
MAX_PREFETCH_NODES = 5
PREFETCH_FULL_NODES = 2
PREFETCH_SUMMARY_NODES = 6
PREFETCH_MIN_SCORE = 0.05
WORKSPACE_TOOL_CODES = {
    "workspace_upsert_node": ("node-writing", "brujula-cobre-17"),
    "workspace_link_nodes": ("node-writing", "brujula-cobre-17"),
    "workspace_create_project": ("node-writing", "brujula-cobre-17"),
    "workspace_create_workspace": ("workspace-admin", "forja-nueva-01"),
    "workspace_ensure_structure": ("db-refactor", "mapa-lima-42"),
    "workspace_migrate_legacy": ("db-refactor", "mapa-lima-42"),
    "workspace_scan_artifacts": ("db-refactor", "mapa-lima-42"),
    "workspace_record_agent_event": ("agent-coordination", "bitacora-nube-8"),
    "workspace_claim_task": ("agent-coordination", "bitacora-nube-8"),
    "workspace_complete_task": ("agent-coordination", "bitacora-nube-8"),
    "workspace_sync_agent_docs": ("agent-coordination", "bitacora-nube-8"),
}
MUTATING_DB_TOOLS = set(WORKSPACE_TOOL_CODES)


def _load_plugin_config() -> dict:
    try:
        from hermes_constants import get_hermes_home
        config_path = get_hermes_home() / "config.yaml"
        if not config_path.exists():
            return {}
        import yaml
        with open(config_path) as f:
            all_config = yaml.safe_load(f) or {}
        return all_config.get("plugins", {}).get("workspace-context", {}) or {}
    except Exception:
        return {}


def _as_name_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _append_unique(items: list[str], name: str) -> list[str]:
    return items if name in items else [*items, name]


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 80] + f"\n\n[... truncated to {max_chars} chars ...]"


def _sanitize_rel_path(rel_path: str) -> Optional[str]:
    rel_path = rel_path.strip().strip("/")
    if not rel_path or rel_path.startswith("/") or ".." in Path(rel_path).parts:
        return None
    return rel_path


class WorkspaceContextProvider(MemoryProvider):
    @property
    def name(self) -> str:
        return "workspace-context"

    def __init__(self, config: dict | None = None):
        self._config = config or _load_plugin_config()
        self._config_mtime: float | None = None
        self._hermes_home: Optional[str] = None
        self._cached_block: Optional[str] = None
        self._watched_mtimes: Dict[str, float] = {}
        self._prefetch_cache: Dict[str, str] = {}
        self._prefetch_lock = threading.Lock()

    def is_available(self) -> bool:
        return True

    def get_config_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "key": "workspace",
                "description": "Active workspace name (resolves to workspaces/{workspace}/workspace.db)",
                "default": DEFAULT_WORKSPACE,
            },
            {
                "key": "inject_mode",
                "description": "Injection mode: 'index' or 'all-indexes'. Projects, topics and important nodes are read on demand.",
                "default": DEFAULT_INJECT_MODE,
                "choices": ["index", "all-indexes"],
            },
            {
                "key": "max_chars",
                "description": "Maximum total characters to inject into the system prompt",
                "default": str(DEFAULT_MAX_CHARS),
            },
            {
                "key": "workspaces",
                "description": "List of workspace names accessible in all-indexes mode. If empty, auto-discovers from workspaces/ directory.",
                "default": [],
            },
            {
                "key": "active_workspaces",
                "description": "Workspaces where write operations are allowed. Must be a subset of workspaces. If empty, falls back to [workspace]. Inactive workspaces are read-only.",
                "default": [],
                "validation": {"subset_of": "workspaces"},
            },
        ]

    def save_config(self, values: Dict[str, Any], hermes_home: str) -> None:
        config_path = Path(hermes_home) / "config.yaml"
        try:
            import yaml
            existing = {}
            if config_path.exists():
                with open(config_path) as f:
                    existing = yaml.safe_load(f) or {}
            existing.setdefault("plugins", {})
            existing["plugins"]["workspace-context"] = values
            with open(config_path, "w") as f:
                yaml.dump(existing, f, default_flow_style=False)
        except Exception as exc:
            logger.warning("workspace-context: failed to save config: %s", exc)

    def initialize(self, session_id: str, **kwargs) -> None:
        hermes_home = kwargs.get("hermes_home")
        if not hermes_home:
            from hermes_constants import get_hermes_home
            hermes_home = str(get_hermes_home())
        self._hermes_home = hermes_home
        self._refresh_config_if_changed(force=True)
        self._ensure_store(self._active_workspace())
        self._rebuild_block()

    def _refresh_config_if_changed(self, *, force: bool = False) -> None:
        config_path = self._hermes_root() / "config.yaml"
        try:
            mtime = config_path.stat().st_mtime
        except OSError:
            return
        if not force and self._config_mtime == mtime:
            return
        try:
            import yaml

            with open(config_path, encoding="utf-8") as f:
                all_config = yaml.safe_load(f) or {}
            plugin_config = all_config.get("plugins", {}).get("workspace-context", {}) or {}
        except Exception as exc:
            logger.warning("workspace-context: failed to refresh config: %s", exc)
            return
        if plugin_config != self._config:
            self._config = plugin_config
            self._cached_block = None
            self._prefetch_cache.clear()
        self._config_mtime = mtime

    def _inject_mode(self) -> str:
        mode = self._config.get("inject_mode", DEFAULT_INJECT_MODE)
        if mode not in {"index", "all-indexes"}:
            logger.warning("workspace-context: inject_mode=%s is invalid; using index", mode)
            return "index"
        return mode

    def _active_workspace(self) -> str:
        return self._config.get("workspace", DEFAULT_WORKSPACE)

    def _active_workspaces(self) -> list[str]:
        active = _as_name_list(self._config.get("active_workspaces"))
        return active if active else [self._active_workspace()]

    def _is_writable(self, workspace: str) -> bool:
        return workspace in self._active_workspaces()

    def _hermes_root(self) -> Path:
        return Path(self._hermes_home or os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))

    def _workspace_root(self, workspace: str) -> Path:
        hermes_home = self._hermes_root()
        return hermes_home / "workspaces" / workspace

    def _ensure_store(self, workspace: str) -> WorkspaceStore:
        store = WorkspaceStore(self._workspace_root(workspace))
        if not store.exists():
            store.migrate_from_markdown(force=False)
        else:
            store.ensure_schema()
        store.ensure_workspace_taxonomy()
        return store

    def _configured_workspaces(self) -> list[str]:
        configured = self._config.get("workspaces")
        active = self._active_workspace()
        names = _as_name_list(configured)
        if not names:
            hermes_home = self._hermes_root()
            names = sorted(path.name for path in list_workspaces(hermes_home))
        if active and active not in names:
            names.insert(0, active)
        seen: set[str] = set()
        return [name for name in names if not (name in seen or seen.add(name))]

    def _watched_stores(self) -> list[tuple[str, WorkspaceStore]]:
        if self._inject_mode() == "all-indexes":
            return [(name, self._ensure_store(name)) for name in self._configured_workspaces()]
        return [(self._active_workspace(), self._ensure_store(self._active_workspace()))]

    def _check_for_changes(self) -> bool:
        watched = self._watched_stores()
        current = {workspace: store.db_mtime() for workspace, store in watched}
        if current != self._watched_mtimes:
            return True
        return False

    def _rebuild_block(self) -> None:
        max_chars = int(self._config.get("max_chars", DEFAULT_MAX_CHARS))
        active = self._active_workspace()
        mode = self._inject_mode()

        stores = self._watched_stores()
        self._watched_mtimes = {name: store.db_mtime() for name, store in stores}
        blocks: list[str] = []
        for name, store in stores:
            index_node = store.get_index_node()
            if not index_node:
                continue
            rendered = store.render_node_markdown(index_node).strip()
            if not rendered:
                continue
            label = f"# Workspace: {name}\n\n" if mode == "all-indexes" else ""
            blocks.append(f"{label}{rendered}".strip())
        combined = "\n\n---\n\n".join(blocks)

        self._cached_block = _truncate(combined, max_chars) if combined else ""

    def system_prompt_block(self) -> str:
        self._refresh_config_if_changed()
        if self._cached_block is None or self._check_for_changes():
            self._rebuild_block()

        if not self._cached_block:
            return ""

        workspace = self._active_workspace()
        mode = self._inject_mode()
        names = ", ".join(self._configured_workspaces()) if mode == "all-indexes" else workspace
        loaded_text = (
            f"Tienes cargado el nodo index de estos workspaces: {names}. Son brujulas, no fuentes suficientes para detalles.\n"
            if mode == "all-indexes"
            else "Tienes cargado solo el nodo index del workspace desde `workspace.db`. Es una brujula, no una fuente suficiente para detalles.\n"
        )
        instructions = (
            f"[WORKSPACE ACTIVO: {workspace} | MODO: {mode} | EDITABLES: {', '.join(self._active_workspaces())}]\n"
            f"{loaded_text}"
            "Orden obligatorio: `workspace_search_nodes` -> `workspace_get_node` -> "
            "`workspace_list_folder`/`workspace_read_workspace_file` si necesitas archivos reales en `code/` -> "
            "`workspace_read_file` solo como compatibilidad.\n"
            "Regla de escritura: solo puedes modificar workspaces incluidos en EDITABLES. "
            "Los demas workspaces configurados son de solo lectura: puedes buscarlos y leerlos, pero no editarlos. "
            "No esquives esta politica con terminal, Python/sqlite, write_file, patch o ediciones directas de archivos/BD.\n"
            "Antes de actuar sobre un area sensible, busca y lee su nodo `important` global o local si existe. "
            "Los `project` funcionan como indices locales; los `topic` son mapas de conocimiento y no tienen subtopics. "
            "No uses `session_search`, `search_files` ni exports Markdown como primer recurso."
        )

        return (
            f"<!-- workspace context: {workspace} start -->\n"
            f"{instructions}\n\n"
            f"{self._cached_block}\n"
            f"<!-- workspace context: {workspace} end -->"
        )

    def _cross_workspace_search(
        self,
        query: str,
        limit: int,
        kind: Optional[str] = None,
        include_index: bool = False,
    ) -> list[dict]:
        all_results: list[dict] = []
        for name in self._configured_workspaces():
            store = self._ensure_store(name)
            nodes = store.search_nodes(query, limit=limit, kinds=[kind] if kind else None, include_index=include_index)
            for node in nodes:
                node["_workspace"] = name
                all_results.append(node)
        all_results.sort(key=lambda n: -float(n.get("score", 0.0)))
        return all_results[:limit]

    def _resolve_prefetch(self, query: str) -> str:
        total = PREFETCH_FULL_NODES + PREFETCH_SUMMARY_NODES
        if self._inject_mode() == "all-indexes":
            results = self._cross_workspace_search(query, limit=total, include_index=False)
            if not results:
                results = self._cross_workspace_search(query, limit=total, include_index=True)
            results = [r for r in results if float(r.get("score", 0.0)) >= PREFETCH_MIN_SCORE]
            parts = []
            for i, node in enumerate(results[:total]):
                name = node.get("_workspace", self._active_workspace())
                store = self._ensure_store(name)
                label = f"[{name}/{node['filename']}] (score: {node.get('score', 0):.3f})"
                if i < PREFETCH_FULL_NODES:
                    parts.append(f"{label}\n\n{store.render_node_markdown(node)}")
                else:
                    summary = node.get("summary") or node.get("title", "")
                    parts.append(f"{label} — {summary}")
            return "\n\n---\n\n".join(parts)
        store = self._ensure_store(self._active_workspace())
        return store.prefetch(query, limit=PREFETCH_FULL_NODES, include_workspace_label=False)

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        self._refresh_config_if_changed()
        with self._prefetch_lock:
            cached = self._prefetch_cache.pop(query, None)
        if cached is not None:
            return cached
        return self._resolve_prefetch(query)

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        def _worker() -> None:
            result = self._resolve_prefetch(query)
            with self._prefetch_lock:
                self._prefetch_cache[query] = result

        threading.Thread(target=_worker, daemon=True).start()

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
        """No persistent turn sync in workspace-context."""

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "workspace_list_workspaces",
                "description": "Lista todos los workspaces disponibles, incluyendo estado DB-first y disponibilidad del nodo index.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "workspace_list_files",
                "description": "Compatibilidad legacy: lista nodos que tendrían filename Markdown derivado. Prioriza workspace_search_nodes.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "workspace": {"type": "string", "description": "Nombre del workspace; por defecto usa el activo."}
                    },
                    "required": [],
                },
            },
            {
                "name": "workspace_read_file",
                "description": "Compatibilidad legacy: lee un nodo por filename derivado o slug desde SQLite. Prioriza `workspace_get_node`.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string", "description": "Filename derivado (`00-index.md`) o slug del nodo."},
                        "workspace": {"type": "string", "description": "Nombre del workspace; por defecto usa el activo."},
                    },
                    "required": ["filename"],
                },
            },
            {
                "name": "workspace_list_folder",
                "description": "Lista carpetas y archivos reales del workspace. Usa `code/` como raíz principal de programas y scripts.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "folder": {"type": "string", "description": "Ruta relativa segura dentro del workspace."},
                        "workspace": {"type": "string", "description": "Nombre del workspace; por defecto usa el activo."},
                    },
                    "required": [],
                },
            },
            {
                "name": "workspace_read_workspace_file",
                "description": "Lee un archivo real del workspace con ruta relativa segura. Para código y programas usa rutas bajo `code/`.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Ruta relativa segura dentro del workspace."},
                        "workspace": {"type": "string", "description": "Nombre del workspace; por defecto usa el activo."},
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "workspace_get_node",
                "description": "Lectura principal DB-first: obtiene un nodo por slug, filename derivado, alias o id.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ref": {"type": "string", "description": "Slug, filename derivado o id del nodo."},
                        "workspace": {"type": "string", "description": "Nombre del workspace; por defecto usa el activo."},
                    },
                    "required": ["ref"],
                },
            },
            {
                "name": "workspace_search_nodes",
                "description": "Entrada principal DB-first: busca nodos con FTS5. En modo all-indexes sin especificar workspace, busca en todos los workspaces simultáneamente y devuelve resultados mezclados por score.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Consulta de búsqueda."},
                        "workspace": {"type": "string", "description": "Nombre del workspace; por defecto usa el activo."},
                        "limit": {"type": "integer", "description": "Número máximo de resultados.", "default": 8},
                        "kind": {"type": "string", "description": "Filtrar por kind opcional (`topic`, `important`, `project`, `doc`, `script`, `reference`, `agent-note`, `agent-plan`, `agent-log`)."},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "workspace_upsert_node",
                "description": "Crea o actualiza un nodo real en SQLite. No genera exports Markdown. No crees nodos carpeta como projects/topics/docs.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "slug": {"type": "string", "description": "Slug estable del nodo."},
                        "title": {"type": "string", "description": "Título del nodo."},
                        "kind": {"type": "string", "description": "Tipo de nodo (`index`, `project`, `topic`, `important`, `doc`, `agent-note`, `agent-plan`, `agent-log`, `script`, `reference`). `detail`, `agent-node` y kinds plurales están bloqueados para escrituras nuevas."},
                        "summary": {"type": "string", "description": "Resumen breve del nodo."},
                        "body": {"type": "string", "description": "Cuerpo principal del nodo en Markdown."},
                        "status": {"type": "string", "description": "Estado del nodo.", "default": "active"},
                        "parent": {"type": "string", "description": "Slug, filename o id del nodo padre."},
                        "aliases": {"type": "array", "items": {"type": "string"}, "description": "Aliases adicionales del nodo."},
                        "filename": {"type": "string", "description": "Nombre de archivo derivado opcional para compatibilidad Markdown."},
                        "workspace": {"type": "string", "description": "Nombre del workspace; por defecto usa el activo."},
                        "verification_code": {"type": "string", "description": "Codigo obligatorio del grupo explicado en `workspace-write` para esta herramienta."},
                    },
                    "required": ["slug", "title", "kind", "verification_code"],
                },
            },
            {
                "name": "workspace_link_nodes",
                "description": "Crea o actualiza una relación entre nodos en SQLite. No genera exports Markdown.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "from_ref": {"type": "string", "description": "Nodo origen por slug, filename o id."},
                        "to_ref": {"type": "string", "description": "Nodo destino por slug, filename o id."},
                        "edge_type": {"type": "string", "description": "Tipo de relación. Usa `contains` para jerarquía nueva; también existen `references`, `depends_on` y `related_to`. `details` y `project_of` son legacy."},
                        "weight": {"type": "number", "description": "Peso opcional de la relación.", "default": 1.0},
                        "workspace": {"type": "string", "description": "Nombre del workspace; por defecto usa el activo."},
                        "verification_code": {"type": "string", "description": "Codigo obligatorio del grupo explicado en `workspace-write` para esta herramienta."},
                    },
                    "required": ["from_ref", "to_ref", "edge_type", "verification_code"],
                },
            },
            {
                "name": "workspace_create_workspace",
                "description": (
                    "Crea un workspace nuevo desde cero con WorkspaceStore.seed_workspace(). "
                    "Usa SIEMPRE esta herramienta para crear workspaces — NUNCA uses Python/sqlite3 directamente. "
                    "Crea la estructura de directorios (code/, context/, agents/), el schema de DB y los nodos iniciales."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Nombre del workspace. Solo minúsculas, números, guiones y guiones bajos."},
                        "description": {"type": "string", "description": "Descripción breve en 1-3 frases para el nodo índice."},
                        "areas": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Áreas temáticas a crear como nodos topic. Puede estar vacío.",
                        },
                        "verification_code": {"type": "string", "description": "Código del grupo 'workspace-admin' explicado en workspace-write."},
                    },
                    "required": ["name", "verification_code"],
                },
            },
            {
                "name": "workspace_create_project",
                "description": "Crea un proyecto real en `code/{name}/` y su nodo DB-first kind=project, sin prefijo project- ni contenedores internos.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Nombre del proyecto."},
                        "description": {"type": "string", "description": "Descripción breve del proyecto."},
                        "workspace": {"type": "string", "description": "Nombre del workspace; por defecto usa el activo."},
                        "verification_code": {"type": "string", "description": "Codigo obligatorio del grupo explicado en `workspace-write` para esta herramienta."},
                    },
                    "required": ["name", "verification_code"],
                },
            },
            {
                "name": "workspace_ensure_structure",
                "description": "Repara la taxonomía obligatoria del workspace: deja solo index como raíz, elimina contenedores artificiales y sincroniza edges contains.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "workspace": {"type": "string", "description": "Nombre del workspace; por defecto usa el activo."},
                        "verification_code": {"type": "string", "description": "Codigo obligatorio del grupo explicado en `workspace-write` para esta herramienta."},
                    },
                    "required": ["verification_code"],
                },
            },
            {
                "name": "workspace_export_markdown",
                "description": "Regenera `context/` y `docs/db-export/` como exports Markdown derivados desde `workspace.db`.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "workspace": {"type": "string", "description": "Nombre del workspace; por defecto usa el activo."}
                    },
                    "required": [],
                },
            },
            {
                "name": "workspace_clean_exports",
                "description": "Borra exports Markdown derivados (`context/` y `docs/db-export/`) tras verificar que SQLite es suficiente.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "workspace": {"type": "string", "description": "Nombre del workspace; por defecto usa el activo."}
                    },
                    "required": [],
                },
            },
            {
                "name": "workspace_verify_db_completeness",
                "description": "Audita si `workspace.db` tiene nodos suficientes antes de limpiar exports o legacy.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "workspace": {"type": "string", "description": "Nombre del workspace; por defecto usa el activo."}
                    },
                    "required": [],
                },
            },
            {
                "name": "workspace_migrate_legacy",
                "description": "Migra carpetas legacy a SQLite, mueve código a `code/`, archiva originales comprimidos y retira legacy si verifica.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "workspace": {"type": "string", "description": "Nombre del workspace; por defecto usa el activo."},
                        "remove_legacy": {"type": "boolean", "description": "Retirar legacy tras migrar y verificar.", "default": True},
                        "verification_code": {"type": "string", "description": "Codigo obligatorio del grupo explicado en `workspace-write` para esta herramienta."},
                    },
                    "required": ["verification_code"],
                },
            },
            {
                "name": "workspace_list_all_nodes",
                "description": "Lista todos los nodos del workspace desde SQLite.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "workspace": {"type": "string", "description": "Nombre del workspace; por defecto usa el activo."}
                    },
                    "required": [],
                },
            },
            {
                "name": "workspace_list_edges",
                "description": "Lista todas las relaciones entre nodos del workspace desde SQLite.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "workspace": {"type": "string", "description": "Nombre del workspace; por defecto usa el activo."}
                    },
                    "required": [],
                },
            },
            {
                "name": "workspace_list_events",
                "description": "Lista eventos recientes del workspace para coordinación multi-agente.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "workspace": {"type": "string", "description": "Nombre del workspace; por defecto usa el activo."},
                        "limit": {"type": "integer", "description": "Número máximo de eventos.", "default": 50},
                    },
                    "required": [],
                },
            },
            {
                "name": "workspace_sync_agent_docs",
                "description": "Actualiza `agent-team` (agent-note) y `agent-log` (agent-log) desde la tabla events. Úsala al cerrar tareas agenticas.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "workspace": {"type": "string", "description": "Nombre del workspace; por defecto usa el activo."},
                        "max_events": {"type": "integer", "description": "Eventos recientes a considerar.", "default": 200},
                        "verification_code": {"type": "string", "description": "Codigo obligatorio del grupo explicado en `workspace-write` para esta herramienta."},
                    },
                    "required": ["verification_code"],
                },
            },
            {
                "name": "workspace_agent_status",
                "description": "Devuelve estado agentico resumido para UI/monitor: tareas activas, eventos recientes y nodos agent-note/agent-plan/agent-log.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "workspace": {"type": "string", "description": "Nombre del workspace; por defecto usa el activo."},
                        "max_events": {"type": "integer", "description": "Eventos recientes a considerar.", "default": 100},
                    },
                    "required": [],
                },
            },
            {
                "name": "workspace_record_agent_event",
                "description": "Registra un evento agentico estructurado para orquestación, documentación o UI realtime sin crear un nodo completo.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "event_type": {"type": "string", "description": "Tipo de evento, por ejemplo plan_submitted, plan_approved, worker_assigned o review_done."},
                        "agent_id": {"type": "string", "description": "Identificador del agente."},
                        "task_id": {"type": "string", "description": "Identificador opcional de tarea."},
                        "summary": {"type": "string", "description": "Resumen breve del evento."},
                        "details": {"type": "string", "description": "Detalle Markdown opcional."},
                        "node_ref": {"type": "string", "description": "Nodo relacionado por slug/id/filename."},
                        "extra": {"type": "object", "description": "Payload adicional serializable."},
                        "workspace": {"type": "string", "description": "Nombre del workspace; por defecto usa el activo."},
                        "verification_code": {"type": "string", "description": "Codigo obligatorio del grupo explicado en `workspace-write` para esta herramienta."},
                    },
                    "required": ["event_type", "verification_code"],
                },
            },
            {
                "name": "workspace_scan_artifacts",
                "description": "Escanea archivos reales bajo `code/` y actualiza la tabla artifacts.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "workspace": {"type": "string", "description": "Nombre del workspace; por defecto usa el activo."},
                        "verification_code": {"type": "string", "description": "Codigo obligatorio del grupo explicado en `workspace-write` para esta herramienta."},
                    },
                    "required": ["verification_code"],
                },
            },
            {
                "name": "workspace_claim_task",
                "description": "Registra en events que un agente toma una tarea para coordinar trabajo en paralelo.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string", "description": "Identificador del agente."},
                        "description": {"type": "string", "description": "Descripción breve de la tarea."},
                        "workspace": {"type": "string", "description": "Nombre del workspace; por defecto usa el activo."},
                        "verification_code": {"type": "string", "description": "Codigo obligatorio del grupo explicado en `workspace-write` para esta herramienta."},
                    },
                    "required": ["agent_id", "description", "verification_code"],
                },
            },
            {
                "name": "workspace_complete_task",
                "description": "Registra en events que una tarea reclamada por un agente terminó.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "event_id": {"type": "integer", "description": "ID del evento workspace_claim_task."},
                        "agent_id": {"type": "string", "description": "Identificador del agente."},
                        "result": {"type": "string", "description": "Resultado o resumen de cierre."},
                        "workspace": {"type": "string", "description": "Nombre del workspace; por defecto usa el activo."},
                        "verification_code": {"type": "string", "description": "Codigo obligatorio del grupo explicado en `workspace-write` para esta herramienta."},
                    },
                    "required": ["event_id", "agent_id", "result", "verification_code"],
                },
            },
        ]

    def _resolve_workspace(self, args: Dict[str, Any]) -> tuple[str, WorkspaceStore]:
        workspace = args.get("workspace") or self._active_workspace()
        return workspace, self._ensure_store(workspace)

    def _register_workspace_config(self, workspace: str, *, writable: bool = True) -> None:
        config_path = self._hermes_root() / "config.yaml"
        try:
            import yaml

            existing: dict[str, Any] = {}
            if config_path.exists():
                with open(config_path, encoding="utf-8") as f:
                    existing = yaml.safe_load(f) or {}
            plugin_cfg = existing.setdefault("plugins", {}).setdefault("workspace-context", {})
            plugin_cfg["workspaces"] = _append_unique(_as_name_list(plugin_cfg.get("workspaces")), workspace)
            if writable:
                active = _as_name_list(plugin_cfg.get("active_workspaces")) or _as_name_list(plugin_cfg.get("workspace"))
                plugin_cfg["active_workspaces"] = _append_unique(active, workspace)
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(existing, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            self._refresh_config_if_changed(force=True)
        except Exception as exc:
            logger.warning("workspace-context: failed to register workspace config: %s", exc)

    def _require_verification_code(self, tool_name: str, args: Dict[str, Any]) -> Optional[dict[str, Any]]:
        if tool_name not in MUTATING_DB_TOOLS:
            return None
        group, expected = WORKSPACE_TOOL_CODES[tool_name]
        provided = str(args.get("verification_code", "")).strip()
        if provided == expected:
            return None
        return {
            "error": "verification_code invalido o ausente",
            "tool": tool_name,
            "verification_group": group,
            "required_skill": "workspace-write",
            "message": (
                "Esta herramienta modifica workspace.db. Lee primero la skill "
                "`workspace-write` y vuelve a llamar la tool con el codigo de su grupo."
            ),
        }

    def _list_folder(self, workspace_root: Path, folder: str) -> dict[str, Any]:
        rel_path = _sanitize_rel_path(folder) if folder else ""
        if folder and rel_path is None:
            return {"error": "Ruta fuera del workspace — acceso denegado"}
        target = workspace_root / rel_path if rel_path else workspace_root
        try:
            target.resolve().relative_to(workspace_root.resolve())
        except ValueError:
            return {"error": "Ruta fuera del workspace — acceso denegado"}
        if not target.exists():
            available = [item.name for item in sorted(workspace_root.iterdir()) if item.is_dir() and not item.name.startswith(".")]
            return {"error": f"Carpeta '{folder}' no encontrada", "available_folders": available}

        files = []
        subdirs = []
        for item in sorted(target.iterdir()):
            if item.name.startswith("."):
                continue
            if item.is_dir():
                subdirs.append(item.name)
            elif item.is_file():
                description = ""
                if item.suffix == ".md":
                    try:
                        description = item.read_text(encoding="utf-8", errors="ignore").strip().splitlines()[0].lstrip("#> ").strip()
                    except Exception:
                        description = ""
                files.append({"file": item.name, "description": description})

        return {"folder": rel_path or "(raíz)", "subdirs": subdirs, "files": files}

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        self._refresh_config_if_changed()
        hermes_home = self._hermes_root()

        try:
            if tool_name == "workspace_list_workspaces":
                result = []
                for ws_path in list_workspaces(hermes_home):
                    store = WorkspaceStore(ws_path)
                    if not store.exists():
                        store.migrate_from_markdown(force=False)
                    audit = store.audit() if store.exists() else {"issues": []}
                    result.append(
                        {
                            "name": ws_path.name,
                            "active": ws_path.name == self._active_workspace(),
                            "writable": self._is_writable(ws_path.name),
                            "has_db": store.exists(),
                            "has_index": bool(store.get_index_node()) if store.exists() else False,
                            "issues": [issue.message for issue in audit["issues"][:5]],
                        }
                )
                return json.dumps({
                    "workspaces": result,
                    "active": self._active_workspace(),
                    "active_workspaces": self._active_workspaces(),
                })

            workspace, store = self._resolve_workspace(args)
            workspace_root = self._workspace_root(workspace)

            if tool_name in MUTATING_DB_TOOLS and not self._is_writable(workspace):
                return json.dumps({
                    "error": f"El workspace '{workspace}' es de solo lectura.",
                    "active_workspaces": self._active_workspaces(),
                    "hint": "Usa workspace_list_workspaces para ver los workspaces editables.",
                })

            verification_error = self._require_verification_code(tool_name, args)
            if verification_error is not None:
                return json.dumps(verification_error)

            if tool_name == "workspace_list_files":
                files = [
                    {
                        "file": node["filename"],
                        "description": node["summary"] or node["title"],
                        "slug": node["slug"],
                        "kind": node["kind"],
                        "is_container": node.get("is_container", False),
                    }
                    for node in store.list_context_nodes()
                ]
                return json.dumps({"workspace": workspace, "files": files})

            if tool_name == "workspace_read_file":
                filename = args.get("filename", "")
                if not filename or "/" in filename or "\\" in filename or ".." in filename:
                    return json.dumps({"error": "filename inválido"})
                node = store.get_node(filename)
                if node is None:
                    available = [item["filename"] for item in store.list_context_nodes()]
                    return json.dumps({"error": f"'{filename}' no existe en workspace '{workspace}'", "available": available})
                return json.dumps(
                    {
                        "workspace": workspace,
                        "file": node["filename"],
                        "slug": node["slug"],
                        "kind": node["kind"],
                        "content": store.render_node_markdown(node).strip(),
                    }
                )

            if tool_name == "workspace_list_folder":
                folder = args.get("folder", "code")
                result = self._list_folder(workspace_root, folder)
                result["workspace"] = workspace
                result["source_of_truth"] = "workspace.db"
                return json.dumps(result)

            if tool_name == "workspace_read_workspace_file":
                rel_path = _sanitize_rel_path(args.get("path", ""))
                if rel_path is None:
                    return json.dumps({"error": "Ruta fuera del workspace — acceso denegado"})
                target = workspace_root / rel_path
                try:
                    target.resolve().relative_to(workspace_root.resolve())
                except ValueError:
                    return json.dumps({"error": "Ruta fuera del workspace — acceso denegado"})
                if not target.exists():
                    parent = target.parent
                    available = [item.name for item in sorted(parent.iterdir()) if not item.name.startswith(".")] if parent.is_dir() else []
                    return json.dumps({"error": f"'{rel_path}' no existe en workspace '{workspace}'", "files_in_parent": available})
                if not target.is_file():
                    return json.dumps({"error": f"'{rel_path}' es un directorio, no un archivo. Usa workspace_list_folder."})
                content = target.read_text(encoding="utf-8", errors="ignore").strip()
                return json.dumps({"workspace": workspace, "path": rel_path, "content": content})

            if tool_name == "workspace_get_node":
                ref = args.get("ref", "")
                if not ref:
                    return json.dumps({"error": "ref es obligatorio"})
                node = store.get_node(ref)
                if node is None and not args.get("workspace") and self._inject_mode() == "all-indexes":
                    for alt_name in self._configured_workspaces():
                        if alt_name == workspace:
                            continue
                        alt_store = self._ensure_store(alt_name)
                        node = alt_store.get_node(ref)
                        if node is not None:
                            workspace = alt_name
                            store = alt_store
                            break
                if node is None:
                    return json.dumps({"error": f"Nodo '{ref}' no encontrado en ningún workspace"})
                return json.dumps({"workspace": workspace, "node": node, "rendered_markdown": store.render_node_markdown(node).strip()})

            if tool_name == "workspace_search_nodes":
                query = args.get("query", "")
                if not query:
                    return json.dumps({"error": "query es obligatorio"})
                kind = args.get("kind")
                limit = int(args.get("limit", 8))
                if not args.get("workspace") and self._inject_mode() == "all-indexes":
                    results = self._cross_workspace_search(query, limit=limit, kind=kind)
                    return json.dumps({"workspace": "all", "results": results})
                results = store.search_nodes(query, limit=limit, kinds=[kind] if kind else None, include_index=False)
                return json.dumps({"workspace": workspace, "results": results})

            if tool_name == "workspace_upsert_node":
                store.ensure_workspace_taxonomy()
                slug = args.get("slug", "")
                title = args.get("title", "")
                kind = args.get("kind", "")
                if not slug or not title or not kind:
                    return json.dumps({"error": "slug, title y kind son obligatorios"})
                existing_node = store.get_node(slug)
                parent_ref = args.get("parent") if "parent" in args else (
                    existing_node.get("parent_id") if existing_node else None
                )
                node = store.upsert_node(
                    slug=slug,
                    title=title,
                    kind=kind,
                    summary=args.get("summary", ""),
                    body=args.get("body", ""),
                    status=args.get("status", "active"),
                    parent_ref=parent_ref,
                    aliases=args.get("aliases") or [],
                    filename=args.get("filename"),
                    source_kind="tool",
                )
                self._rebuild_block()
                return json.dumps({"workspace": workspace, "node": node})

            if tool_name == "workspace_link_nodes":
                store.ensure_workspace_taxonomy()
                result = store.link_nodes(
                    args.get("from_ref", ""),
                    args.get("to_ref", ""),
                    args.get("edge_type", ""),
                    weight=float(args.get("weight", 1.0)),
                )
                self._rebuild_block()
                return json.dumps({"workspace": workspace, "link": result})

            if tool_name == "workspace_create_workspace":
                import re as _re
                new_name = (args.get("name") or "").strip().lower()
                if not new_name:
                    return json.dumps({"error": "name es obligatorio"})
                if not _re.match(r'^[a-z0-9_-]+$', new_name):
                    return json.dumps({"error": "name debe ser minúsculas, números, guiones o guiones bajos"})
                from pathlib import Path as _Path
                ws_path = store.root.parent / new_name
                if ws_path.exists() and (ws_path / "workspace.db").exists():
                    return json.dumps({"error": f"El workspace '{new_name}' ya existe"})
                from workspace_store import WorkspaceStore as _WS
                new_store = _WS(ws_path)
                new_store.ensure_workspace_layout()
                areas = args.get("areas") or []
                result = new_store.seed_workspace(
                    description=args.get("description") or f"Workspace {new_name}.",
                    areas=areas,
                )
                self._register_workspace_config(new_name, writable=True)
                index_node = result.get("index_node") or result.get("index") or {}
                return json.dumps({
                    "ok": True,
                    "name": new_name,
                    "path": str(ws_path),
                    "index_slug": index_node.get("slug", "index"),
                    "writable": self._is_writable(new_name),
                    "active_workspaces": self._active_workspaces(),
                    "workspaces": self._configured_workspaces(),
                })

            if tool_name == "workspace_create_project":
                name = args.get("name", "")
                if not name:
                    return json.dumps({"error": "name es obligatorio"})
                result = store.create_project(name, args.get("description", ""))
                self._rebuild_block()
                return json.dumps({"workspace": workspace, **result})

            if tool_name == "workspace_ensure_structure":
                result = store.ensure_workspace_taxonomy()
                self._rebuild_block()
                return json.dumps({"workspace": workspace, **result})

            if tool_name == "workspace_export_markdown":
                result = store.sync_markdown_exports()
                self._rebuild_block()
                return json.dumps({"workspace": workspace, "export": result})

            if tool_name == "workspace_clean_exports":
                verification = store.verify_db_completeness()
                if not verification.get("verified"):
                    return json.dumps({"workspace": workspace, "error": "DB incompleta para limpiar exports", **verification})
                result = store.clean_exports()
                self._rebuild_block()
                return json.dumps({"workspace": workspace, **verification, **result})

            if tool_name == "workspace_verify_db_completeness":
                return json.dumps({"workspace": workspace, **store.verify_db_completeness()})

            if tool_name == "workspace_migrate_legacy":
                result = store.migrate_legacy_to_db(remove_legacy=bool(args.get("remove_legacy", True)))
                self._rebuild_block()
                return json.dumps({"workspace": workspace, **result})

            if tool_name == "workspace_list_all_nodes":
                return json.dumps({"workspace": workspace, "nodes": store.list_all_nodes()})

            if tool_name == "workspace_list_edges":
                return json.dumps({"workspace": workspace, "edges": store.list_edges()})

            if tool_name == "workspace_list_events":
                limit = max(1, min(int(args.get("limit", 50)), 200))
                return json.dumps({"workspace": workspace, "events": store.list_events()[:limit]})

            if tool_name == "workspace_sync_agent_docs":
                # The agent-facing wrapper around WorkspaceStore.sync_agent_coordination().
                # Keeps `events` as the raw timeline and refreshes human-readable notes.
                max_events = max(1, min(int(args.get("max_events", 200)), 1000))
                result = store.sync_agent_coordination(max_events=max_events)
                self._rebuild_block()
                return json.dumps({"workspace": workspace, **result})

            if tool_name == "workspace_agent_status":
                # Compact state for monitors and future web dashboards.
                max_events = max(1, min(int(args.get("max_events", 100)), 1000))
                return json.dumps(store.agent_status(max_events=max_events))

            if tool_name == "workspace_record_agent_event":
                # Generic structured event: useful for plan_submitted,
                # review_done, blocked, decision_recorded, etc.
                event_type = args.get("event_type", "")
                if not event_type:
                    return json.dumps({"error": "event_type es obligatorio"})
                result = store.record_agent_event(
                    event_type,
                    agent_id=args.get("agent_id", ""),
                    task_id=args.get("task_id", ""),
                    summary=args.get("summary", ""),
                    details=args.get("details", ""),
                    node_ref=args.get("node_ref"),
                    extra=args.get("extra") or {},
                )
                return json.dumps({"workspace": workspace, **result})

            if tool_name == "workspace_scan_artifacts":
                result = store.scan_artifacts()
                self._rebuild_block()
                return json.dumps({"workspace": workspace, **result, "artifacts": store.list_artifacts()})

            if tool_name == "workspace_claim_task":
                agent_id = args.get("agent_id", "")
                description = args.get("description", "")
                if not agent_id or not description:
                    return json.dumps({"error": "agent_id y description son obligatorios"})
                result = store.claim_task(agent_id, description)
                return json.dumps({"workspace": workspace, **result})

            if tool_name == "workspace_complete_task":
                event_id = args.get("event_id")
                agent_id = args.get("agent_id", "")
                result_text = args.get("result", "")
                if event_id is None or not agent_id or not result_text:
                    return json.dumps({"error": "event_id, agent_id y result son obligatorios"})
                result = store.complete_task(int(event_id), agent_id, result_text)
                return json.dumps({"workspace": workspace, **result})

            return json.dumps({"error": f"Tool desconocido: {tool_name}"})
        except Exception as exc:
            logger.exception("workspace-context tool failed: %s", tool_name)
            return json.dumps({"error": str(exc)})

    def shutdown(self) -> None:
        self._cached_block = None
        self._watched_mtimes.clear()
        with self._prefetch_lock:
            self._prefetch_cache.clear()


def register(ctx) -> None:
    config = _load_plugin_config()
    ctx.register_memory_provider(WorkspaceContextProvider(config=config))
