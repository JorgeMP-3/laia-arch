#!/usr/bin/env python3
# Orquestador multi-IA DB-first para Hermes.
"""ai-orchestrator.py - coordina briefs, planes y workers desde workspace.db."""

from __future__ import annotations

import argparse
import json
import os
import pty
import shlex
import select
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _laia_runtime_paths import add_workspace_store_to_path, laia_home, workspaces_dir

LAIA_HOME = laia_home()
add_workspace_store_to_path()

from workspace_store import WorkspaceStore

WORKSPACES_DIR = workspaces_dir()
CONFIG_PATH = LAIA_HOME / "ai-agents.json"
RUNS_DIR = LAIA_HOME / "orchestrator-runs"


DEFAULT_CONFIG = {
    "version": 1,
    "agents": {
        "gpt-5-5-planner": {
            "role": "planner",
            "enabled": False,
            "command": [],
            "notes": "Planner fuerte. Configura command cuando exista CLI/API local.",
        },
        "claude-code-planner": {
            "role": "planner",
            "enabled": True,
            "command": [
                "bash",
                "-lc",
                "claude -p \"$(cat \"$1\")\" --output-format json --max-turns 8",
                "_",
                "{prompt_file}",
            ],
            "output": "claude-json",
            "notes": "Planner fuerte via Claude Code print mode. Usa cuenta host/Jorge.",
        },
        "codex-worker": {
            "role": "worker",
            "enabled": True,
            "command": ["bash", "-lc", "codex exec --full-auto \"$(cat \"$1\")\"", "_", "{prompt_file}"],
            "pty": True,
            "notes": "Worker/implementador via Codex. Requiere repo Git y PTY.",
        },
        "opencode-worker": {
            "role": "worker",
            "enabled": True,
            "command": ["bash", "-lc", "opencode run \"$(cat \"$1\")\"", "_", "{prompt_file}"],
            "notes": "Worker barato via OpenCode/Minimax u otro modelo.",
        },
    },
}


def now_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return DEFAULT_CONFIG
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save_config(config: dict[str, Any]) -> None:
    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def merge_default_config(existing: dict[str, Any]) -> dict[str, Any]:
    """Merge user registry with defaults without deleting custom agents.

    Empty commands are treated as "not configured yet", so the defaults can
    repair early generated configs after we add better command templates.
    """
    merged = json.loads(json.dumps(DEFAULT_CONFIG))
    for name, agent in existing.get("agents", {}).items():
        merged.setdefault("agents", {})
        if name in merged["agents"]:
            default_agent = merged["agents"][name]
            has_custom_command = bool(agent.get("command"))
            default_agent.update(agent)
            if not has_custom_command:
                default_agent["command"] = DEFAULT_CONFIG["agents"][name].get("command", [])
                default_agent["enabled"] = DEFAULT_CONFIG["agents"][name].get("enabled", False)
                default_agent["notes"] = DEFAULT_CONFIG["agents"][name].get("notes", default_agent.get("notes", ""))
                if "output" in DEFAULT_CONFIG["agents"][name]:
                    default_agent["output"] = DEFAULT_CONFIG["agents"][name]["output"]
                if "pty" in DEFAULT_CONFIG["agents"][name]:
                    default_agent["pty"] = DEFAULT_CONFIG["agents"][name]["pty"]
        else:
            merged["agents"][name] = agent
    merged["version"] = max(int(existing.get("version", 1)), int(merged.get("version", 1)))
    return merged


def store_for(workspace: str) -> WorkspaceStore:
    path = WORKSPACES_DIR / workspace
    if not path.exists():
        raise SystemExit(f"ERROR: workspace no encontrado: {workspace}")
    return WorkspaceStore(path)


def resolve_workdir(store: WorkspaceStore, value: str | None) -> Path:
    """Resolve where the external coding agent should run.

    Hermes stores coordination in `workspace.db`, but tools like Codex often
    need to run inside a real project/repo under `code/`.
    """
    if not value:
        return store.root
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = store.root / path
    if not path.exists():
        raise SystemExit(f"ERROR: workdir no existe: {path}")
    return path


def read_text_arg(value: str, file_path: str | None) -> str:
    if file_path:
        return Path(file_path).read_text(encoding="utf-8")
    return value.strip()


def render_context(store: WorkspaceStore, query: str, limit: int = 5) -> str:
    """Build a compact DB-first context bundle for planner prompts."""
    index = store.get_index_node()
    parts = []
    if index:
        parts.append("[NODO INDEX]\n" + store.render_node_markdown(index).strip())
    for node in store.search_nodes(query, limit=limit, include_index=False):
        parts.append(f"[NODO {node['slug']}]\n" + store.render_node_markdown(node).strip())
    return "\n\n---\n\n".join(parts)


def write_prompt(workspace: str, slug: str, prompt: str) -> Path:
    """Persist the exact prompt sent to a planner/worker for auditing."""
    run_dir = RUNS_DIR / workspace
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / f"{slug}.prompt.md"
    path.write_text(prompt, encoding="utf-8")
    return path


def run_pty_command(command: list[str], *, cwd: Path, timeout: int) -> dict[str, Any]:
    """Run interactive CLIs, especially Codex, behind a pseudo-terminal."""
    master_fd, slave_fd = pty.openpty()
    started = time.time()
    output = bytearray()
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        close_fds=True,
        env=os.environ.copy(),
    )
    os.close(slave_fd)
    try:
        while True:
            if process.poll() is not None:
                while True:
                    ready, _, _ = select.select([master_fd], [], [], 0)
                    if not ready:
                        break
                    try:
                        chunk = os.read(master_fd, 4096)
                    except OSError:
                        break
                    if not chunk:
                        break
                    output.extend(chunk)
                break
            if time.time() - started > timeout:
                process.kill()
                return {
                    "executed": True,
                    "returncode": -9,
                    "stdout": output.decode(errors="replace"),
                    "stderr": "timeout",
                }
            ready, _, _ = select.select([master_fd], [], [], 0.25)
            if ready:
                try:
                    chunk = os.read(master_fd, 4096)
                except OSError:
                    break
                if chunk:
                    output.extend(chunk)
    finally:
        os.close(master_fd)
    return {
        "executed": True,
        "returncode": process.returncode,
        "stdout": output.decode(errors="replace"),
        "stderr": "",
    }


def run_agent(agent: dict[str, Any], *, prompt: str, prompt_file: Path, workspace_root: Path, workspace: str) -> dict[str, Any]:
    """Execute one configured external agent command.

    `--execute` is checked by the caller. This function assumes execution is
    allowed and only handles command rendering, PTY mode and output capture.
    """
    if not agent.get("enabled"):
        return {"executed": False, "reason": "agent-disabled"}
    command = agent.get("command") or []
    if not command:
        return {"executed": False, "reason": "missing-command"}

    rendered = [
        str(part)
        .replace("{prompt_file}", str(prompt_file))
        .replace("{workspace_root}", str(workspace_root))
        .replace("{workspace}", workspace)
        for part in command
    ]
    uses_prompt_file = any("{prompt_file}" in str(part) for part in command)
    timeout = int(agent.get("timeout_seconds", 1800))
    if agent.get("pty"):
        output = run_pty_command(rendered, cwd=workspace_root, timeout=timeout)
        output["command"] = shlex.join(rendered)
        return output
    result = subprocess.run(
        rendered,
        cwd=workspace_root,
        input=None if uses_prompt_file else prompt,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    return {
        "executed": True,
        "command": shlex.join(rendered),
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def extract_agent_text(output: dict[str, Any], agent: dict[str, Any]) -> str:
    """Normalize agent output into the Markdown/text body stored in DB."""
    stdout = output.get("stdout", "") or ""
    if agent.get("output") == "claude-json":
        try:
            parsed = json.loads(stdout)
            return parsed.get("result") or parsed.get("structured_output") or stdout
        except Exception:
            return stdout
    return stdout


def create_brief(args: argparse.Namespace) -> None:
    """Create Hermes's request node before any technical planning happens."""
    store = store_for(args.workspace)
    store.ensure_agent_coordination_nodes()
    objective = read_text_arg(args.objective or "", args.objective_file)
    if not objective:
        raise SystemExit("ERROR: brief necesita --objective o --objective-file")
    slug = args.slug or f"agent-request-{now_slug()}"
    context = render_context(store, objective, limit=args.context_limit)
    body = f"""## Objetivo de Hermes

{objective}

## Marco de trabajo

- Hermes define el objetivo, restricciones y validacion.
- Los planificadores producen planes tecnicos.
- Hermes valida un plan antes de asignar workers.
- Los workers ejecutan tareas acotadas y reportan mediante events.

## Criterios de aceptacion

{args.acceptance or "Pendiente de concretar por Hermes o por el planificador."}

## Contexto DB-first relevante

{context or "_Sin contexto adicional encontrado._"}
"""
    node = store.upsert_node(
        slug=slug,
        title=f"Request — {slug}",
        kind="agent-plan",
        summary=objective[:240],
        body=body.strip(),
        source_kind="ai-orchestrator",
        parent_ref="agent-team",
        aliases=[slug, "agent-request"],
        filename=f"{slug}.md",
    )
    index = store.get_index_node()
    if index:
        store.link_nodes(index["id"], node["id"], "references")
    store.record_agent_event(
        "orchestration_request_created",
        agent_id="hermes",
        task_id=slug,
        summary=objective[:240],
        node_ref=node["id"],
    )
    store.sync_agent_coordination()
    print(json.dumps({"workspace": args.workspace, "request": node["slug"]}, ensure_ascii=False, indent=2))


def build_plan_prompt(store: WorkspaceStore, request_node: dict[str, Any], agent_name: str) -> str:
    """Prompt contract for strong planning agents."""
    return f"""# Hermes planner request

Eres un planificador tecnico para Hermes.

Lee obligatoriamente estas reglas conceptuales:
- La fuente de verdad es workspace.db.
- Los planes persistentes deben guardarse como nodos agent-plan bajo agent-team.
- No ejecutes cambios de codigo; produce un plan tecnico verificable.
- Divide el trabajo en tareas pequenas para workers baratos.
- Incluye riesgos, criterios de aceptacion y validaciones.

## Agente planificador

{agent_name}

## Request aprobado por Hermes

{request_node['body']}

## Formato de respuesta

Devuelve Markdown con:
1. Resumen tecnico
2. Supuestos
3. Plan por fases
4. Tareas para workers
5. Archivos o modulos probables
6. Riesgos
7. Validaciones y pruebas
8. Preguntas bloqueantes, si existen
"""


def request_plan(args: argparse.Namespace) -> None:
    """Ask a planner for a plan and store it as an agent-plan.

    Without `--execute`, this only writes the prompt and records the request.
    With `--execute`, the external agent output becomes the plan node body.
    """
    config = load_config()
    agent = config.get("agents", {}).get(args.agent)
    if agent is None:
        raise SystemExit(f"ERROR: agente no configurado: {args.agent}")
    store = store_for(args.workspace)
    store.ensure_agent_coordination_nodes()
    request_node = store.get_node(args.request)
    if request_node is None:
        raise SystemExit(f"ERROR: request no encontrado: {args.request}")
    slug = f"agent-plan-{request_node['slug']}-{args.agent}"
    prompt = build_plan_prompt(store, request_node, args.agent)
    prompt_file = write_prompt(args.workspace, slug, prompt)

    store.record_agent_event(
        "plan_requested",
        agent_id=args.agent,
        task_id=request_node["slug"],
        summary=f"Plan solicitado a {args.agent}",
        node_ref=request_node["id"],
        extra={"prompt_file": str(prompt_file)},
    )

    workdir = resolve_workdir(store, getattr(args, "workdir", None))
    if not args.execute:
        store.sync_agent_coordination()
        print(
            json.dumps(
                {
                    "workspace": args.workspace,
                    "prompt_file": str(prompt_file),
                    "execution": {"executed": False, "reason": "execute-not-requested"},
                },
                indent=2,
            )
        )
        return

    output = run_agent(agent, prompt=prompt, prompt_file=prompt_file, workspace_root=workdir, workspace=args.workspace)
    if not output.get("executed"):
        store.sync_agent_coordination()
        print(json.dumps({"workspace": args.workspace, "prompt_file": str(prompt_file), "execution": output}, indent=2))
        return

    if output["returncode"] != 0:
        store.record_agent_event(
            "plan_failed",
            agent_id=args.agent,
            task_id=request_node["slug"],
            summary=f"Plan fallo con codigo {output['returncode']}",
            details=output.get("stderr", ""),
            node_ref=request_node["id"],
        )
        store.sync_agent_coordination()
        print(json.dumps(output, indent=2))
        return

    plan_text = extract_agent_text(output, agent)
    plan_node = store.upsert_node(
        slug=slug,
        title=f"Plan — {request_node['slug']} — {args.agent}",
        kind="agent-plan",
        summary=f"Plan generado por {args.agent} para {request_node['slug']}",
        body=plan_text.strip() or "_Plan vacio._",
        source_kind="ai-orchestrator",
        parent_ref="agent-team",
        aliases=[slug, "agent-plan"],
        filename=f"{slug}.md",
    )
    store.link_nodes(request_node["id"], plan_node["id"], "references")
    store.record_agent_event(
        "plan_submitted",
        agent_id=args.agent,
        task_id=request_node["slug"],
        summary=f"Plan entregado por {args.agent}",
        node_ref=plan_node["id"],
    )
    store.sync_agent_coordination()
    print(json.dumps({"workspace": args.workspace, "plan": plan_node["slug"], "execution": output}, indent=2))


def approve_plan(args: argparse.Namespace) -> None:
    """Record Hermes approval for a plan without modifying project files."""
    store = store_for(args.workspace)
    plan = store.get_node(args.plan)
    if plan is None:
        raise SystemExit(f"ERROR: plan no encontrado: {args.plan}")
    store.record_agent_event(
        "plan_approved",
        agent_id="hermes",
        task_id=plan["slug"],
        summary=args.summary or f"Plan aprobado: {plan['slug']}",
        details=args.notes or "",
        node_ref=plan["id"],
    )
    store.sync_agent_coordination()
    print(json.dumps({"workspace": args.workspace, "approved_plan": plan["slug"]}, indent=2))


def build_worker_prompt(task_node: dict[str, Any], agent_name: str) -> str:
    """Prompt contract for cheaper executor agents."""
    return f"""# Hermes worker task

Eres un worker ejecutor para Hermes.

Reglas:
- Trabaja solo dentro del scope de la tarea.
- No cambies arquitectura si no esta pedido.
- Devuelve resumen, diff conceptual, archivos tocados y pruebas ejecutadas.
- Si encuentras bloqueo, reportalo claramente.

## Worker

{agent_name}

## Tarea asignada

{task_node['body']}
"""


def assign_worker(args: argparse.Namespace) -> None:
    """Create a worker task, claim it, and optionally execute the worker.

    Dry-run mode is intentional: it lets Hermes prepare auditable prompts and
    task records before spending tokens or touching code.
    """
    config = load_config()
    agent = config.get("agents", {}).get(args.agent)
    if agent is None:
        raise SystemExit(f"ERROR: agente no configurado: {args.agent}")
    store = store_for(args.workspace)
    store.ensure_agent_coordination_nodes()
    task_slug = args.slug or f"agent-task-{now_slug()}-{args.agent}"
    related = store.get_node(args.related) if args.related else None
    body = f"""## Tarea

{args.description}

## Relacionado

{related['slug'] if related else "Sin nodo relacionado."}

## Instrucciones

- Ejecutar solo el scope asignado.
- Registrar resultado con eventos.
- Mantener workspace.db como fuente de verdad.
"""
    task_node = store.upsert_node(
        slug=task_slug,
        title=f"Task — {task_slug}",
        kind="agent-plan",
        summary=args.description[:240],
        body=body.strip(),
        source_kind="ai-orchestrator",
        parent_ref="agent-team",
        aliases=[task_slug, "agent-task"],
        filename=f"{task_slug}.md",
    )
    if related:
        store.link_nodes(related["id"], task_node["id"], "references")
    claim = store.claim_task(args.agent, args.description)
    store.record_agent_event(
        "worker_assigned",
        agent_id=args.agent,
        task_id=task_node["slug"],
        summary=args.description[:240],
        node_ref=task_node["id"],
        extra={"claim_event_id": claim["event_id"]},
    )

    prompt = build_worker_prompt(task_node, args.agent)
    prompt_file = write_prompt(args.workspace, task_slug, prompt)
    workdir = resolve_workdir(store, args.workdir)
    if not args.execute:
        store.sync_agent_coordination()
        print(
            json.dumps(
                {
                    "workspace": args.workspace,
                    "task": task_node["slug"],
                    "claim_event_id": claim["event_id"],
                    "prompt_file": str(prompt_file),
                    "execution": {"executed": False, "reason": "execute-not-requested"},
                },
                indent=2,
            )
        )
        return

    output = run_agent(agent, prompt=prompt, prompt_file=prompt_file, workspace_root=workdir, workspace=args.workspace)
    if not output.get("executed"):
        store.sync_agent_coordination()
        print(
            json.dumps(
                {
                    "workspace": args.workspace,
                    "task": task_node["slug"],
                    "claim_event_id": claim["event_id"],
                    "prompt_file": str(prompt_file),
                    "execution": output,
                },
                indent=2,
            )
        )
        return

    result_text = extract_agent_text(output, agent).strip() or output.get("stderr", "").strip()
    store.complete_task(claim["event_id"], args.agent, result_text[:4000] or "Worker ejecutado sin salida.")
    store.sync_agent_coordination()
    print(json.dumps({"workspace": args.workspace, "task": task_node["slug"], "execution": output}, indent=2))


def list_agents(_: argparse.Namespace) -> None:
    print(json.dumps(load_config(), ensure_ascii=False, indent=2))


def init_config(_: argparse.Namespace) -> None:
    if CONFIG_PATH.exists():
        config = merge_default_config(load_config())
        save_config(config)
        print(f"Actualizado: {CONFIG_PATH}")
        return
    save_config(DEFAULT_CONFIG)
    print(f"Creado: {CONFIG_PATH}")


def status(args: argparse.Namespace) -> None:
    store = store_for(args.workspace)
    print(json.dumps(store.agent_status(max_events=args.max_events), ensure_ascii=False, indent=2, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(description="Orquestador multi-IA DB-first para Hermes.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-config", help="Crear $LAIA_HOME/ai-agents.json de ejemplo").set_defaults(func=init_config)
    sub.add_parser("list-agents", help="Mostrar registry de agentes").set_defaults(func=list_agents)

    brief = sub.add_parser("brief", help="Crear un request/brief DB-first para Hermes")
    brief.add_argument("--workspace", required=True)
    brief.add_argument("--objective", default="")
    brief.add_argument("--objective-file")
    brief.add_argument("--acceptance", default="")
    brief.add_argument("--context-limit", type=int, default=5)
    brief.add_argument("--slug")
    brief.set_defaults(func=create_brief)

    plan = sub.add_parser("request-plan", help="Solicitar plan a un planner configurado")
    plan.add_argument("--workspace", required=True)
    plan.add_argument("--request", required=True)
    plan.add_argument("--agent", required=True)
    plan.add_argument("--workdir", default="", help="Directorio real donde ejecutar el agente; relativo al workspace si no es absoluto")
    plan.add_argument("--execute", action="store_true")
    plan.set_defaults(func=request_plan)

    approve = sub.add_parser("approve-plan", help="Registrar aprobacion de un plan por Hermes")
    approve.add_argument("--workspace", required=True)
    approve.add_argument("--plan", required=True)
    approve.add_argument("--summary", default="")
    approve.add_argument("--notes", default="")
    approve.set_defaults(func=approve_plan)

    worker = sub.add_parser("assign-worker", help="Crear tarea y asignarla a un worker configurado")
    worker.add_argument("--workspace", required=True)
    worker.add_argument("--agent", required=True)
    worker.add_argument("--description", required=True)
    worker.add_argument("--related", default="")
    worker.add_argument("--workdir", default="", help="Directorio real donde ejecutar el agente; relativo al workspace si no es absoluto")
    worker.add_argument("--slug")
    worker.add_argument("--execute", action="store_true")
    worker.set_defaults(func=assign_worker)

    stat = sub.add_parser("status", help="Mostrar estado agentico del workspace")
    stat.add_argument("--workspace", required=True)
    stat.add_argument("--max-events", type=int, default=50)
    stat.set_defaults(func=status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
