from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


@dataclass
class Result:
    args: Sequence[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class CommandError(RuntimeError):
    def __init__(self, result: Result):
        self.result = result
        cmd = " ".join(result.args)
        message = f"Command failed ({result.returncode}): {cmd}"
        if result.stderr.strip():
            message += f"\n{result.stderr.strip()}"
        super().__init__(message)


def run(
    args: Sequence[str],
    *,
    check: bool = True,
    capture: bool = True,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> Result:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    completed = subprocess.run(
        list(args),
        cwd=str(cwd) if cwd else None,
        env=merged_env,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )
    result = Result(
        args=args,
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )
    if check and not result.ok:
        raise CommandError(result)
    return result


def print_result(result: Result) -> None:
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n")
