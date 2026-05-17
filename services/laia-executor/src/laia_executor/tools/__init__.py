"""Native tool handlers for the executor.

These are intentionally simple: each handler accepts a dict of args and returns
a JSON-serializable string (the AIAgent in AGORA expects strings back).

No `.laia-core` dependency. No sandbox. The user is root inside the container.
"""

from laia_executor.tools.registry import ToolRegistry, default_registry  # noqa: F401
