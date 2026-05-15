#!/usr/bin/env python3
# Regenera scripts/INDEX.md desde scripts globales y workspaces/{ws}/code/scripts/.

from __future__ import annotations

import argparse
import re
from pathlib import Path

import os
from _laia_runtime_paths import laia_home, workspaces_dir

LAIA_HOME = laia_home()
WORKSPACES_DIR = workspaces_dir()
SCRIPTS_DIR = LAIA_HOME / "scripts"
INDEX_PATH = SCRIPTS_DIR / "INDEX.md"

SCRIPT_EXTENSIONS = {".py", ".sh", ".js", ".ts"}
IGNORED_GLOBAL = {"INDEX.md"}


def get_description(path: Path) -> str:
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return path.name

    lines = content.splitlines()
    start = 0
    while start < len(lines) and (not lines[start].strip() or lines[start].strip().startswith("#!")):
        start += 1

    if start < len(lines):
        stripped = lines[start].strip()
        if stripped.startswith('"""') or stripped.startswith("'''"):
            quote = stripped[:3]
            remainder = stripped[3:]
            if quote in remainder:
                inline = remainder.split(quote, 1)[0].strip()
                if inline:
                    return inline
            block = [remainder]
            for line in lines[start + 1:]:
                if quote in line:
                    block.append(line.split(quote, 1)[0])
                    break
                block.append(line)
            first_doc_line = next((line.strip() for line in block if line.strip()), "")
            if first_doc_line:
                return first_doc_line

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#!"):
            continue
        if stripped.startswith("#"):
            comment = stripped.lstrip("#").strip()
            if comment and not re.fullmatch(r"[-_=*─═]{4,}", comment):
                return comment
            continue
        if stripped.startswith("//"):
            comment = stripped.lstrip("/").strip()
            if comment and not re.fullmatch(r"[-_=*─═]{4,}", comment):
                return comment
            continue
        break
    return path.name


def scan_global_scripts() -> list[tuple[str, str]]:
    results = []
    for path in sorted(SCRIPTS_DIR.iterdir()):
        if path.name.startswith(".") or path.name in IGNORED_GLOBAL:
            continue
        if not path.is_file() or path.suffix not in SCRIPT_EXTENSIONS:
            continue
        results.append((f"scripts/{path.name}", get_description(path)))
    return results


def scan_workspace_scripts(ws_name: str) -> list[tuple[str, str]]:
    scripts_dir = WORKSPACES_DIR / ws_name / "code" / "scripts"
    if not scripts_dir.exists():
        return []

    results = []
    for path in sorted(scripts_dir.rglob("*")):
        if path.name.startswith(".") or not path.is_file() or path.suffix not in SCRIPT_EXTENSIONS:
            continue
        rel = f"workspaces/{ws_name}/code/scripts/{path.relative_to(scripts_dir)}"
        results.append((rel, get_description(path)))
    return results


def render_section(name: str, entries: list[tuple[str, str]], empty_label: str) -> list[str]:
    lines = [f"## {name}", "", "| Script | Descripción |", "|--------|-------------|"]
    if entries:
        for rel_path, description in entries:
            safe_description = description.replace("|", "\\|")
            lines.append(f"| `{rel_path}` | {safe_description} |")
    else:
        lines.append(f"| {empty_label} | |")
    lines.append("")
    return lines


def build_index(workspaces: list[str]) -> str:
    lines = [
        "# Scripts Index",
        "",
        "Índice global de los scripts de Hermes. Se regenera automáticamente desde los",
        "scripts globales de `$LAIA_HOME/scripts/` y `workspaces/{ws}/code/scripts/`.",
        "",
    ]

    lines.extend(render_section("global", scan_global_scripts(), "_(vacío — no hay scripts globales detectados)_"))

    for workspace in workspaces:
        lines.extend(render_section(workspace, scan_workspace_scripts(workspace), "_(vacío — añadir scripts en code/scripts/)_"))

    lines.extend(["---", "*Regenerado con `python3 $LAIA_HOME/scripts/index-scripts.py`.*", ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenera scripts/INDEX.md desde el estado real de Hermes.")
    parser.add_argument("--workspace", metavar="NOMBRE", help="Limitar secciones de workspace a uno concreto")
    parser.add_argument("--dry-run", action="store_true", help="Mostrar si cambiaría INDEX.md sin escribirlo")
    args = parser.parse_args()

    if not WORKSPACES_DIR.exists():
        raise SystemExit(f"ERROR: {WORKSPACES_DIR} no existe")

    if args.workspace and not (WORKSPACES_DIR / args.workspace).exists():
        raise SystemExit(f"ERROR: workspace '{args.workspace}' no encontrado")

    workspaces = sorted(path.name for path in WORKSPACES_DIR.iterdir() if path.is_dir() and not path.name.startswith("."))

    content = build_index(workspaces)
    previous = INDEX_PATH.read_text(encoding="utf-8") if INDEX_PATH.exists() else ""

    if args.dry_run:
        if previous == content:
            print("INDEX.md ya está actualizado.")
        else:
            print("INDEX.md cambiaría.")
        return

    INDEX_PATH.write_text(content, encoding="utf-8")
    print(f"INDEX.md regenerado con {1 + len(workspaces)} secciones.")


if __name__ == "__main__":
    main()
