"""Profiles for ephemeral sub-AIAgents spawned by ``spawn_child`` (Fase C).

Each profile narrows the parent's toolset to what the child actually
needs. The child NEVER has the agent_self / agent_scheduler / agent_delegation
toolsets (no recursion, no scheduling, no self-editing). ``max_iters``
caps the agent loop so a runaway child can't spend the parent's budget.
"""

from __future__ import annotations

from typing import Any


CHILD_PROFILES: dict[str, dict[str, Any]] = {
    "general": {
        "toolsets": ["clarify", "todo"],
        "max_iters": 5,
        "extra_prompt": (
            "Eres un sub-agente delegado por otro agente para una tarea "
            "concreta. Responde de forma directa y útil; no inicies "
            "conversación con el usuario."
        ),
    },
    "coder": {
        "toolsets": ["file", "terminal", "clarify"],
        "max_iters": 10,
        "extra_prompt": (
            "Eres un sub-agente especializado en código. Lee/escribe archivos "
            "y ejecuta comandos cuando sean necesarios. Tu output debe ser "
            "código limpio + un breve resumen."
        ),
    },
    "researcher": {
        "toolsets": ["web", "fetch_url", "clarify"],
        "max_iters": 10,
        "extra_prompt": (
            "Eres un sub-agente investigador. Usa web/fetch_url para "
            "recopilar fuentes y devuelve un resumen con citas."
        ),
    },
    "writer": {
        "toolsets": ["clarify", "todo"],
        "max_iters": 5,
        "extra_prompt": (
            "Eres un sub-agente especializado en escritura clara y concisa. "
            "No buscas en la web ni ejecutas código — solo redactas."
        ),
    },
}

DEFAULT_PROFILE = "general"

# Maximum number of concurrent children a parent session can have. Hard
# limit to prevent fan-out abuse.
MAX_CONCURRENT_CHILDREN = 3

# How long a child can run before being killed. Synchronous spawn_child
# blocks the parent's turn — keep this aggressive.
CHILD_TIMEOUT_SECONDS = 5 * 60
