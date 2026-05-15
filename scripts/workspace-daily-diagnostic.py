#!/usr/bin/env python3
"""Diagnóstico rápido del flujo DB-first esperado para preguntas reales."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import os
from _laia_runtime_paths import add_workspace_store_to_path, laia_home, workspaces_dir

LAIA_HOME = laia_home()
WORKSPACES_DIR = workspaces_dir()
add_workspace_store_to_path()

from workspace_store import WorkspaceStore, list_workspaces

CASES = [
    {
        "id": "metodo-doyouwin",
        "question": "¿Cuáles son las 3 fases del Método DoYouWin?",
        "query": "metodo doyouwin fases",
        "workspaces": ["doyouwin"],
        "expected_workspace": "doyouwin",
        "expected_ref": "02b-metodo-doyouwin",
        "forbidden": ["session_search", "search_files", "docs/db-export como primer recurso"],
    },
    {
        "id": "pixelcore-infra",
        "question": "Explícame la infraestructura de PixelCore",
        "query": "infraestructura pixelcore",
        "workspaces": ["pixelcore", "servidor-jmp"],
        "expected_workspace": "pixelcore",
        "expected_ref": "40-infraestructura",
        "forbidden": ["session_search", "search_files"],
    },
    {
        "id": "laia-arch-honesty",
        "question": "¿Qué sabe laia-arch y qué no sabe todavía?",
        "query": "arquitectura laia",
        "workspaces": ["laia-arch"],
        "expected_workspace": "laia-arch",
        "expected_ref": "00-index",
        "forbidden": ["inventar contenido", "search_files como primer recurso"],
    },
    {
        "id": "pixelcore-servidor",
        "question": "Relaciona PixelCore con Servidor_JMP",
        "query": "pixelcore servidor infraestructura",
        "workspaces": ["pixelcore", "servidor-jmp"],
        "expected_workspace": "pixelcore",
        "expected_ref": "40-infraestructura",
        "forbidden": ["session_search", "leer exports primero"],
    },
]


def load_store(name: str) -> WorkspaceStore:
    store = WorkspaceStore(WORKSPACES_DIR / name)
    if not store.exists():
        store.migrate_from_markdown(force=False)
    else:
        store.ensure_schema()
    return store


def find_best_nodes(case: dict) -> list[tuple[str, dict]]:
    found: list[tuple[str, dict]] = []
    for workspace in case["workspaces"]:
        store = load_store(workspace)
        results = store.search_nodes(case["query"], limit=3, include_index=False)
        if not results:
            results = store.search_nodes(case["query"], limit=2, include_index=True)
        for node in results[:2]:
            found.append((workspace, node))
    found.sort(key=lambda item: (-float(item[1].get("score", 0.0)), item[0], item[1]["slug"]))
    return found[:3]


def print_case(case: dict) -> None:
    print(f"\n=== {case['id']} ===")
    print(f"Pregunta: {case['question']}")
    print("Tools esperadas:")
    print("  1. workspace_search_nodes")
    print("  2. workspace_get_node")
    print("  3. workspace_list_folder / workspace_read_workspace_file solo si faltan artefactos reales")
    print("Tools que no deberían aparecer primero:")
    for tool in case["forbidden"]:
        print(f"  - {tool}")

    nodes = find_best_nodes(case)
    if not nodes:
        print("Resultado esperado: sin nodo suficiente; el agente debe reconocer el límite y decirlo con honestidad.")
        print(f"Flujo ideal: workspace_search_nodes(query={case['query']!r}) -> sin resultados fuertes -> explicar límite")
        return

    print("Nodos candidatos encontrados:")
    for workspace, node in nodes:
        print(f"  - [{workspace}] {node['slug']} ({node['kind']}) score={float(node.get('score', 0.0)):.4f}")

    expected_workspace = case.get("expected_workspace")
    expected_ref = case.get("expected_ref")
    print("Flujo ideal:")
    if len(case["workspaces"]) == 1 and not expected_workspace:
        print(f"  workspace_search_nodes(query={case['query']!r})")
        print(f"  workspace_get_node(ref={nodes[0][1]['slug']!r})")
    elif expected_workspace == case["workspaces"][0] and len(case["workspaces"]) == 1:
        print(f"  workspace_search_nodes(query={case['query']!r})")
        print(f"  workspace_get_node(ref={expected_ref!r})")
    else:
        target_workspace = expected_workspace or nodes[0][0]
        target_ref = expected_ref or nodes[0][1]["slug"]
        print(f"  workspace_search_nodes(query={case['query']!r}, workspace={target_workspace!r})")
        print(f"  workspace_get_node(ref={target_ref!r}, workspace={target_workspace!r})")
    print("Criterio de fallo:")
    print("  - empieza por session_search o search_files")
    print("  - lee docs/db-export o context/*.md como primer recurso")
    print("  - responde detalles sin haber pasado por búsqueda nodal")


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnóstico del flujo diario DB-first esperado.")
    parser.add_argument("--case", choices=[case["id"] for case in CASES], help="Ejecuta un solo caso")
    args = parser.parse_args()

    if args.case:
        for case in CASES:
            if case["id"] == args.case:
                print_case(case)
                return
        return

    available = ", ".join(path.name for path in WORKSPACES_DIR.iterdir() if path.is_dir() and not path.name.startswith("."))
    print("Diagnóstico DB-first")
    print(f"Workspaces detectados: {available}")
    for case in CASES:
        print_case(case)


if __name__ == "__main__":
    main()
