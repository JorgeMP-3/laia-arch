from __future__ import annotations

import logging
import os
import signal
import time

from . import __version__
from .config import AgentConfig, load_config
from .status import utc_now, write_json
from .tasks import ensure_task_dirs, process_once
from .profile import ensure_profile


STOP = False


def _handle_stop(_signum: int, _frame: object) -> None:
    global STOP
    STOP = True


def configure_logging(config: AgentConfig) -> None:
    config.logs_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(config.logs_dir / "agent.log"),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def ensure_layout(config: AgentConfig) -> None:
    for path in (config.agent_dir, config.data_dir, config.logs_dir, config.profile_dir, config.workspace_dir):
        path.mkdir(parents=True, exist_ok=True)
    ensure_task_dirs(config)
    ensure_profile(config)


def write_status(config: AgentConfig, status: str = "running") -> None:
    write_json(
        config.data_dir / "status.json",
        {
            "status": status,
            "employee": config.employee,
            "container": config.container,
            "version": __version__,
            "pid": os.getpid(),
            "updated_at": utc_now(),
            "workspace": str(config.workspace_db),
            "profile": str(config.profile_dir),
        },
    )


def run_forever() -> int:
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)
    config = load_config()
    ensure_layout(config)
    configure_logging(config)
    logging.info("LAIA agent runtime starting employee=%s container=%s", config.employee, config.container)
    while not STOP:
        write_status(config)
        processed = process_once(config)
        if processed:
            logging.info("processed_tasks=%s", processed)
        time.sleep(config.heartbeat_interval)
    write_status(config, "stopped")
    logging.info("LAIA agent runtime stopped")
    return 0
