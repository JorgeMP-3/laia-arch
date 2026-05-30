from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
KNOWN_PROFILES = {"ci", "host", "vm"}
KNOWN_LEVELS = {"unit", "integration", "e2e"}


@dataclass(frozen=True)
class IntegrityTest:
    id: str
    name: str
    path: Path
    level: str
    layers: list[str]
    profiles: list[str]
    requires: list[str]
    timeout_s: int


def split_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def parse_metadata(path: Path) -> dict[str, str]:
    meta: dict[str, str] = {}
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.strip()
            if not line.startswith("# integrity:"):
                continue
            item = line.removeprefix("# integrity:").strip()
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            meta[key.strip()] = value.strip()
    return meta


def discover_tests(root: Path) -> list[IntegrityTest]:
    tests: list[IntegrityTest] = []
    for path in sorted(root.rglob("test_*.sh")):
        if path.name == "run_integrity.sh":
            continue
        meta = parse_metadata(path)
        test_id = meta.get("id") or path.stem.removeprefix("test_")
        level = meta.get("level", "integration")
        if level not in KNOWN_LEVELS:
            level = "integration"
        layers = split_csv(meta.get("layers", "unknown"))
        profiles = split_csv(meta.get("profiles", "ci,host,vm"))
        profiles = [p for p in profiles if p in KNOWN_PROFILES] or ["ci", "host", "vm"]
        requires = split_csv(meta.get("requires", ""))
        try:
            timeout_s = int(meta.get("timeout", "300"))
        except ValueError:
            timeout_s = 300
        tests.append(
            IntegrityTest(
                id=test_id,
                name=meta.get("name", test_id),
                path=path,
                level=level,
                layers=layers,
                profiles=profiles,
                requires=requires,
                timeout_s=timeout_s,
            )
        )
    return tests


def command_ok(cmd: list[str], timeout_s: int = 3) -> bool:
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout_s,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def detect_environment(repo_root: Path) -> dict[str, bool]:
    lxc_available = shutil.which("lxc") is not None and command_ok(
        ["lxc", "list", "--format", "csv", "-c", "n"]
    )
    return {
        "ci_env": bool(os.environ.get("CI")),
        "lxd_available": lxc_available,
        "curl_available": shutil.which("curl") is not None,
        "sqlite3_available": shutil.which("sqlite3") is not None,
        "jq_available": shutil.which("jq") is not None,
        "python3_available": shutil.which("python3") is not None,
        "atlas_available": shutil.which("atlas") is not None or (repo_root / "bin/atlas").exists(),
    }


def resolve_profile(requested: str, env: dict[str, bool]) -> str:
    if requested != "auto":
        return requested
    if env["ci_env"] and not env["lxd_available"]:
        return "ci"
    if env["lxd_available"]:
        return "host"
    return "ci"


def requirement_available(requirement: str, env: dict[str, bool]) -> bool:
    if requirement.startswith("optional_"):
        return True
    if requirement == "lxd":
        return env["lxd_available"]
    if requirement == "curl":
        return env["curl_available"]
    if requirement == "sqlite3":
        return env["sqlite3_available"]
    if requirement == "jq":
        return env["jq_available"]
    if requirement == "atlas":
        return env["atlas_available"]
    if requirement == "python3":
        return env["python3_available"]
    return True


def skip_reason(
    test: IntegrityTest,
    *,
    profile: str,
    level_filter: str | None,
    layer_filters: set[str],
    env: dict[str, bool],
) -> str | None:
    if profile not in test.profiles:
        return f"profile {profile} not in {','.join(test.profiles)}"
    if level_filter and test.level != level_filter:
        return f"level {test.level} not selected"
    if layer_filters and not (set(test.layers) & layer_filters):
        return f"layers {','.join(test.layers)} not selected"
    missing = [req for req in test.requires if not requirement_available(req, env)]
    if missing:
        return f"missing requirement(s): {','.join(missing)}"
    return None


def run_test(test: IntegrityTest, profile: str) -> dict[str, Any]:
    env = os.environ.copy()
    env["LAIA_INTEGRITY_PROFILE"] = profile
    started = time.monotonic()
    try:
        proc = subprocess.run(
            ["bash", str(test.path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=test.timeout_s,
            check=False,
            env=env,
        )
        duration_ms = int((time.monotonic() - started) * 1000)
        if proc.returncode == 0:
            status = "pass"
            reason = None
        elif proc.returncode == 77:
            status = "skip"
            reason = "test requested skip"
        else:
            status = "fail"
            reason = None
        return {
            "status": status,
            "exit_code": proc.returncode,
            "duration_ms": duration_ms,
            "reason": reason,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except subprocess.TimeoutExpired as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        return {
            "status": "fail",
            "exit_code": 124,
            "duration_ms": duration_ms,
            "stdout": exc.stdout or "",
            "stderr": f"timeout after {test.timeout_s}s\n{exc.stderr or ''}",
        }


def test_record(test: IntegrityTest) -> dict[str, Any]:
    return {
        "id": test.id,
        "name": test.name,
        "path": str(test.path),
        "level": test.level,
        "layers": test.layers,
        "profiles": test.profiles,
        "requires": test.requires,
        "timeout_s": test.timeout_s,
        "reason": None,
    }


def write_json(report: dict[str, Any], target: str) -> None:
    if target == "-":
        json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_human(report: dict[str, Any]) -> None:
    summary = report["summary"]
    print(
        "LAIA integrity "
        f"profile={report['profile']} "
        f"pass={summary['passed']} fail={summary['failed']} skip={summary['skipped']} "
        f"total={summary['total']}",
        file=sys.stderr,
    )
    for item in report["tests"]:
        suffix = f" ({item['reason']})" if item.get("reason") else ""
        print(f"  {item['status'].upper():4} {item['id']}{suffix}", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run LAIA integrity regression tests")
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[1]),
        help="test discovery root (default: tests/integration)",
    )
    parser.add_argument(
        "--profile",
        choices=["auto", "ci", "host", "vm"],
        default=os.environ.get("LAIA_INTEGRITY_PROFILE", "auto"),
        help="execution profile; auto chooses ci without LXD, host with LXD",
    )
    parser.add_argument("--level", choices=sorted(KNOWN_LEVELS), help="run only this level")
    parser.add_argument(
        "--layer",
        action="append",
        default=[],
        help="run only tests touching this layer; can be passed multiple times",
    )
    parser.add_argument(
        "--json",
        default="-",
        help="write JSON report to path, or '-' for stdout (default)",
    )
    parser.add_argument("--list", action="store_true", help="discover and report tests without running")
    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"test root not found: {root}", file=sys.stderr)
        return 2

    repo_root = Path(__file__).resolve().parents[3]
    env = detect_environment(repo_root)
    profile = resolve_profile(args.profile, env)
    started = time.monotonic()
    tests = discover_tests(root)
    if not tests:
        print(f"no integrity tests discovered under {root}", file=sys.stderr)
        return 2

    layer_filters = set(args.layer or [])
    records: list[dict[str, Any]] = []
    passed = failed = skipped = 0
    runtime_skipped = 0

    for test in tests:
        record = test_record(test)
        reason = skip_reason(
            test,
            profile=profile,
            level_filter=args.level,
            layer_filters=layer_filters,
            env=env,
        )
        if args.list:
            reason = "list mode"
        if reason:
            skipped += 1
            record.update(
                {
                    "status": "skip",
                    "exit_code": None,
                    "duration_ms": 0,
                    "reason": reason,
                    "stdout": "",
                    "stderr": "",
                }
            )
            records.append(record)
            continue

        result = run_test(test, profile)
        record.update(result)
        if result["status"] == "pass":
            passed += 1
        elif result["status"] == "skip":
            skipped += 1
            runtime_skipped += 1
        else:
            failed += 1
        records.append(record)

    duration_ms = int((time.monotonic() - started) * 1000)
    report = {
        "schema_version": SCHEMA_VERSION,
        "runner": "tests/integration/run_integrity.sh",
        "profile": profile,
        "requested_profile": args.profile,
        "environment": env,
        "filters": {
            "level": args.level,
            "layers": sorted(layer_filters),
        },
        "summary": {
            "total": len(records),
            "selected": passed + failed + runtime_skipped,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "runtime_skipped": runtime_skipped,
            "duration_ms": duration_ms,
        },
        "tests": records,
    }
    write_json(report, args.json)
    print_human(report)
    if failed:
        return 1
    if passed + failed + runtime_skipped == 0 and not args.list:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
