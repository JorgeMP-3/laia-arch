"""Entry point: `python -m laia_executor` or installed `laia-executor` script."""

from __future__ import annotations

import sys

import uvicorn

from laia_executor.api import build_app
from laia_executor.config import ExecutorConfig


def main() -> int:
    try:
        cfg = ExecutorConfig.load()
    except RuntimeError as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        return 2
    app = build_app(cfg)
    uvicorn.run(app, host=cfg.bind_host, port=cfg.bind_port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
