"""Resolución portable de plugins de ``.laia-core`` para los tests.

``.laia-core/`` está en ``.gitignore`` (lo provee la instalación de laia-core,
no el repo). En un checkout limpio —p.ej. el runner de CI— esos plugins no
existen. Históricamente varios tests hardcodeaban la ruta absoluta del host de
dev, lo que daba falsos verdes en local y reventaba en CI (es justo el tipo de
ruta que marca ``scripts/check-hardcoded-paths.py``).

Este helper resuelve la ruta del plugin de forma portable —vía ``LAIA_ROOT`` o
subiendo desde ``__file__``— y hace ``pytest.skip`` limpio cuando el plugin no
está presente, en vez de hardcodear o fallar con ``assert``. Resultado:

* en un host/VM con laia-core instalado → el test corre,
* en un checkout sin ``.laia-core/plugins`` (CI) → el test se skipea con motivo.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _candidate_roots() -> list[Path]:
    roots: list[Path] = []
    env = os.environ.get("LAIA_ROOT")
    if env:
        roots.append(Path(env))
    # Subir desde este archivo cubre worktrees y layouts alternativos.
    roots.extend(Path(__file__).resolve().parents)
    return roots


def find_plugin_init(rel: str) -> Path | None:
    """Devuelve la ruta a ``<root>/.laia-core/plugins/<rel>`` si existe, o None."""
    for root in _candidate_roots():
        cand = root / ".laia-core" / "plugins" / rel
        if cand.exists():
            return cand
    return None


def load_plugin_or_skip(rel: str, mod_name: str) -> ModuleType:
    """Carga el módulo del plugin ``rel`` o hace skip si no está instalado.

    ``rel`` es relativo a ``.laia-core/plugins`` (p.ej.
    ``"agent-delegation/__init__.py"``). ``mod_name`` es el nombre con el que se
    registra en ``sys.modules`` (preserva el comportamiento previo de cada test).
    """
    init_py = find_plugin_init(rel)
    if init_py is None:
        pytest.skip(
            f"plugin .laia-core/plugins/{rel} no presente "
            "(.laia-core gitignored; sólo en host/VM con laia-core instalado)"
        )
    spec = importlib.util.spec_from_file_location(mod_name, init_py)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod
