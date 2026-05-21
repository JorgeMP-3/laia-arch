#!/usr/bin/env python3
"""Host-side CLI for the AGORA marketplace (marketplace-v0.1).

Lets you publish, install, list and uninstall plugins/skills against the
AGORA backend. Used to validate the v0.1 flow alongside the control
center TUI; not a substitute for the agent UI the user will build later.

Auth resolution order (first match wins):
  1. ``AGORA_TOKEN`` env var (raw Bearer token).
  2. ``AGORA_USERNAME``/``AGORA_PASSWORD`` env vars (login on the fly).
  3. State file at ``~/.laia/state/laia-state-<slug>.json`` for the
     ``--slug`` argument; logs in with the saved password.

API base URL: ``AGORA_API_URL`` (default ``http://127.0.0.1:8088``).
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import sys
import tarfile
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_API = os.environ.get("AGORA_API_URL", "http://127.0.0.1:8088")
STATE_DIR = Path(os.environ.get("LAIA_STATE_DIR", str(Path.home() / ".laia" / "state")))


def _die(msg: str, code: int = 2) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def _read_json(url: str, token: str | None = None, *, method: str = "GET",
               body: dict | None = None, timeout: float = 15.0) -> dict[str, Any] | list[Any]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        _die(f"HTTP {exc.code} {method} {url}: {body}", code=exc.code if exc.code < 256 else 2)
    except URLError as exc:
        _die(f"network: {exc.reason}")
    return json.loads(raw) if raw else {}


def _resolve_token(args: argparse.Namespace) -> str:
    if os.environ.get("AGORA_TOKEN"):
        return os.environ["AGORA_TOKEN"]
    if os.environ.get("AGORA_USERNAME") and os.environ.get("AGORA_PASSWORD"):
        r = _read_json(
            f"{args.api}/api/login", method="POST",
            body={"username": os.environ["AGORA_USERNAME"],
                  "password": os.environ["AGORA_PASSWORD"]},
        )
        return str(r["access_token"])
    if args.slug:
        state_path = STATE_DIR / f"laia-state-{args.slug}.json"
        if not state_path.exists():
            _die(f"state file {state_path} missing; pass --slug or set AGORA_USERNAME/PASSWORD")
        state = json.loads(state_path.read_text())
        username = state.get("username") or args.slug
        password = state.get("password")
        if not password:
            _die(f"state file {state_path} has no password; cannot login")
        r = _read_json(
            f"{args.api}/api/login", method="POST",
            body={"username": username, "password": password},
        )
        return str(r["access_token"])
    _die("no auth: set AGORA_TOKEN, AGORA_USERNAME+PASSWORD, or pass --slug")


def _pack_dir(path: Path, slug: str) -> bytes:
    """Build a tar.gz with single top-level dir matching slug."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for entry in sorted(path.rglob("*")):
            rel = entry.relative_to(path)
            arcname = f"{slug}/{rel.as_posix()}" if rel.parts else slug
            if entry.is_dir():
                continue
            tf.add(str(entry), arcname=arcname, recursive=False)
        # ensure top-level dir entry exists
        if not any(slug == m.name.split("/")[0] for m in tf.getmembers()):
            info = tarfile.TarInfo(name=f"{slug}/")
            info.type = tarfile.DIRTYPE
            tf.addfile(info)
    return buf.getvalue()


def _load_yaml(text: str) -> dict[str, Any]:
    # Stdlib has no yaml — use a one-shot tolerant parser since manifests
    # are tiny (slug/version/kind/name fields, flat keys).
    out: dict[str, Any] = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        out[key.strip()] = val.strip().strip('"').strip("'")
    return out


# ── Commands ────────────────────────────────────────────────────────────


def cmd_plugin_publish(args: argparse.Namespace) -> int:
    path = Path(args.path).resolve()
    if not path.is_dir():
        _die(f"{path} is not a directory")
    manifest_path = next(
        (path / n for n in ("plugin.yaml", "plugin.yml") if (path / n).exists()),
        None,
    )
    if not manifest_path:
        _die(f"{path} has no plugin.yaml")
    init_path = path / "__init__.py"
    if not init_path.exists():
        _die(f"{path} has no __init__.py")

    manifest = _load_yaml(manifest_path.read_text())
    slug = (manifest.get("slug") or manifest.get("name") or path.name)
    version = manifest.get("version") or "0.1.0"
    kind = manifest.get("kind") or "standalone"
    forward_tools = []
    if args.forward_tools:
        forward_tools = [t.strip() for t in args.forward_tools.split(",") if t.strip()]

    blob = _pack_dir(path, slug)
    token = _resolve_token(args)
    body = {
        "slug": slug,
        "version": version,
        "kind": kind,
        "forward_tools": forward_tools,
        "blob_b64": base64.b64encode(blob).decode("ascii"),
    }
    res = _read_json(f"{args.api}/api/me/plugins/upload", token=token,
                     method="POST", body=body)
    print(json.dumps(res, indent=2))
    plugin_id = res.get("id")
    if args.publish and plugin_id:
        res2 = _read_json(f"{args.api}/api/me/plugins/{plugin_id}/publish",
                          token=token, method="POST")
        print(json.dumps(res2, indent=2))
    return 0


def cmd_plugin_install(args: argparse.Namespace) -> int:
    token = _resolve_token(args)
    body: dict[str, Any] = {"slug": args.slug_or_id}
    if args.version:
        body["version"] = args.version
    res = _read_json(f"{args.api}/api/me/plugins/install", token=token,
                     method="POST", body=body)
    print(json.dumps(res, indent=2))
    return 0


def cmd_plugin_uninstall(args: argparse.Namespace) -> int:
    token = _resolve_token(args)
    # Need plugin_id. If a slug was given, look it up first.
    installs = _read_json(f"{args.api}/api/me/plugins/installs", token=token)
    target_id = None
    for it in installs:  # type: ignore[union-attr]
        if it["slug"] == args.slug_or_id or it["plugin_id"] == args.slug_or_id:
            target_id = it["plugin_id"]
            break
    if not target_id:
        _die(f"no install for {args.slug_or_id}")
    res = _read_json(f"{args.api}/api/me/plugins/installs/{target_id}",
                     token=token, method="DELETE")
    print(json.dumps(res, indent=2))
    return 0


def cmd_plugin_list(args: argparse.Namespace) -> int:
    token = _resolve_token(args)
    if args.mine:
        res = _read_json(f"{args.api}/api/me/plugins", token=token)
    elif args.installed:
        res = _read_json(f"{args.api}/api/me/plugins/installs", token=token)
    else:
        res = _read_json(f"{args.api}/api/plugins/catalog", token=token)
    print(json.dumps(res, indent=2))
    return 0


def cmd_skill_publish(args: argparse.Namespace) -> int:
    md_path = Path(args.path).resolve()
    if not md_path.is_file():
        _die(f"{md_path} not a file")
    manifest_md = md_path.read_text(encoding="utf-8")
    slug = args.skill_slug or md_path.stem
    token = _resolve_token(args)
    res = _read_json(f"{args.api}/api/me/skills/upload", token=token,
                     method="POST",
                     body={"slug": slug, "manifest_md": manifest_md})
    print(json.dumps(res, indent=2))
    skill_id = res.get("id")
    if args.publish and skill_id:
        res2 = _read_json(f"{args.api}/api/me/skills/{skill_id}/publish",
                          token=token, method="POST")
        print(json.dumps(res2, indent=2))
    return 0


def cmd_skill_install(args: argparse.Namespace) -> int:
    token = _resolve_token(args)
    res = _read_json(f"{args.api}/api/me/skills/install", token=token,
                     method="POST", body={"slug": args.skill_slug})
    print(json.dumps(res, indent=2))
    return 0


def cmd_skill_list(args: argparse.Namespace) -> int:
    token = _resolve_token(args)
    if args.mine:
        res = _read_json(f"{args.api}/api/me/skills", token=token)
    elif args.installed:
        res = _read_json(f"{args.api}/api/me/skills/installs", token=token)
    else:
        res = _read_json(f"{args.api}/api/skills/catalog", token=token)
    print(json.dumps(res, indent=2))
    return 0


def cmd_mcp_add(args: argparse.Namespace) -> int:
    token = _resolve_token(args)
    headers: dict[str, str] = {}
    for h in args.header or []:
        if "=" not in h:
            _die(f"bad --header {h!r}; expected name=value")
        k, _, v = h.partition("=")
        headers[k.strip()] = v.strip()
    # Merge into existing list — replace by name if already present.
    cur = _read_json(f"{args.api}/api/user/llm-config", token=token)
    servers = list(cur.get("mcp_servers") or []) if isinstance(cur, dict) else []
    servers = [s for s in servers if s.get("name") != args.name]
    servers.append({"name": args.name, "url": args.url, "headers": headers})
    res = _read_json(f"{args.api}/api/user/llm-config", token=token,
                     method="PATCH", body={"mcp_servers": servers})
    print(json.dumps(res, indent=2))
    return 0


def cmd_mcp_remove(args: argparse.Namespace) -> int:
    token = _resolve_token(args)
    cur = _read_json(f"{args.api}/api/user/llm-config", token=token)
    servers = list(cur.get("mcp_servers") or []) if isinstance(cur, dict) else []
    servers = [s for s in servers if s.get("name") != args.name]
    res = _read_json(f"{args.api}/api/user/llm-config", token=token,
                     method="PATCH", body={"mcp_servers": servers or []})
    print(json.dumps(res, indent=2))
    return 0


def _maybe_path_or_text(value: str) -> str:
    """If ``value`` points at an existing file, return its contents. Otherwise
    return ``value`` verbatim. Lets users do either:

        agent-area set-soul ./my-soul.md
        agent-area set-soul "Soy Nombrix..."
    """
    try:
        p = Path(value).expanduser()
        if p.is_file():
            return p.read_text(encoding="utf-8")
    except OSError:
        pass
    return value


def cmd_agent_area_get(args: argparse.Namespace) -> int:
    token = _resolve_token(args)
    res = _read_json(f"{args.api}/api/me/agent-area", token=token)
    if args.field and isinstance(res, dict):
        # Dotted path lookup, e.g. ``area.soul_md`` or ``user.username``.
        cur: Any = res
        for part in args.field.split("."):
            if not isinstance(cur, dict) or part not in cur:
                _die(f"field '{args.field}' not found in response")
            cur = cur[part]
        if isinstance(cur, (dict, list)):
            print(json.dumps(cur, indent=2, ensure_ascii=False))
        else:
            print(cur)
    else:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


def _patch_agent_area(args: argparse.Namespace, payload: dict) -> int:
    token = _resolve_token(args)
    res = _read_json(f"{args.api}/api/me/agent-area", token=token,
                     method="PATCH", body=payload)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


def cmd_agent_area_set_soul(args: argparse.Namespace) -> int:
    return _patch_agent_area(args, {"soul_md": _maybe_path_or_text(args.value)})


def cmd_agent_area_set_instructions(args: argparse.Namespace) -> int:
    return _patch_agent_area(args, {"instructions_md": _maybe_path_or_text(args.value)})


def cmd_agent_area_set_name(args: argparse.Namespace) -> int:
    return _patch_agent_area(args, {"agent_display_name": args.value})


def cmd_agent_area_set_pref(args: argparse.Namespace) -> int:
    token = _resolve_token(args)
    cur = _read_json(f"{args.api}/api/me/agent-area", token=token)
    bucket = f"{args.scope}_preferences"
    if not isinstance(cur, dict) or "area" not in cur:
        _die("could not read current agent-area")
    prefs = dict(cur["area"].get(bucket) or {})
    # Try to JSON-decode the value (lets users pass numbers, booleans, lists).
    try:
        prefs[args.key] = json.loads(args.value)
    except json.JSONDecodeError:
        prefs[args.key] = args.value
    return _patch_agent_area(args, {bucket: prefs})


def cmd_mcp_list(args: argparse.Namespace) -> int:
    token = _resolve_token(args)
    res = _read_json(f"{args.api}/api/user/llm-config", token=token)
    if isinstance(res, dict):
        print(json.dumps(res.get("mcp_servers", []), indent=2))
    else:
        print(json.dumps(res, indent=2))
    return 0


# ── Entrypoint ──────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="laia-marketplace", description=__doc__)
    p.add_argument("--api", default=DEFAULT_API, help=f"AGORA API URL (default {DEFAULT_API})")
    p.add_argument("--slug", default=None,
                   help="state-file slug for auth (e.g. jorge-dev)")
    sub = p.add_subparsers(dest="cmd", required=True)

    plg = sub.add_parser("plugin", help="plugin commands")
    plg_sub = plg.add_subparsers(dest="plugin_cmd", required=True)

    pub = plg_sub.add_parser("publish", help="pack and upload a plugin dir")
    pub.add_argument("path")
    pub.add_argument("--publish", action="store_true", help="also submit for review")
    pub.add_argument("--forward-tools", default="", help="csv of tool names to forward to executor")
    pub.set_defaults(func=cmd_plugin_publish)

    inst = plg_sub.add_parser("install")
    inst.add_argument("slug_or_id")
    inst.add_argument("--version", default=None)
    inst.set_defaults(func=cmd_plugin_install)

    uninst = plg_sub.add_parser("uninstall")
    uninst.add_argument("slug_or_id")
    uninst.set_defaults(func=cmd_plugin_uninstall)

    lst = plg_sub.add_parser("list")
    g = lst.add_mutually_exclusive_group()
    g.add_argument("--mine", action="store_true", help="my owned plugins")
    g.add_argument("--installed", action="store_true", help="plugins I have installed")
    lst.set_defaults(func=cmd_plugin_list)

    skl = sub.add_parser("skill", help="skill commands")
    skl_sub = skl.add_subparsers(dest="skill_cmd", required=True)

    spub = skl_sub.add_parser("publish")
    spub.add_argument("path", help="markdown file path")
    # ``--skill-slug`` avoids colliding with the top-level ``--slug`` (auth).
    spub.add_argument("--skill-slug", "--name", dest="skill_slug", default=None,
                      help="override skill slug (default: file stem)")
    spub.add_argument("--publish", action="store_true")
    spub.set_defaults(func=cmd_skill_publish)

    sinst = skl_sub.add_parser("install")
    # Positional uses a non-colliding name so the top-level --slug (auth) wins.
    sinst.add_argument("skill_slug", help="skill slug to install")
    sinst.set_defaults(func=cmd_skill_install)

    slst = skl_sub.add_parser("list")
    g = slst.add_mutually_exclusive_group()
    g.add_argument("--mine", action="store_true")
    g.add_argument("--installed", action="store_true")
    slst.set_defaults(func=cmd_skill_list)

    mcp = sub.add_parser("mcp", help="MCP server config")
    mcp_sub = mcp.add_subparsers(dest="mcp_cmd", required=True)

    madd = mcp_sub.add_parser("add")
    madd.add_argument("name")
    madd.add_argument("url")
    madd.add_argument("--header", action="append", default=[],
                      help="header name=value (repeatable)")
    madd.set_defaults(func=cmd_mcp_add)

    mlist = mcp_sub.add_parser("list")
    mlist.set_defaults(func=cmd_mcp_list)

    mrm = mcp_sub.add_parser("remove")
    mrm.add_argument("name")
    mrm.set_defaults(func=cmd_mcp_remove)

    # ── agent-area ──────────────────────────────────────────────────────
    area = sub.add_parser("agent-area", help="manage the agent identity area")
    area_sub = area.add_subparsers(dest="area_cmd", required=True)

    a_get = area_sub.add_parser("get", help="print the full agent area")
    a_get.add_argument("--field", default=None,
                       help="dotted path (e.g. area.soul_md, user.username)")
    a_get.set_defaults(func=cmd_agent_area_get)

    a_soul = area_sub.add_parser("set-soul",
                                  help="set soul_md (text or path to .md)")
    a_soul.add_argument("value")
    a_soul.set_defaults(func=cmd_agent_area_set_soul)

    a_inst = area_sub.add_parser("set-instructions",
                                  help="set instructions_md (text or path)")
    a_inst.add_argument("value")
    a_inst.set_defaults(func=cmd_agent_area_set_instructions)

    a_name = area_sub.add_parser("set-name",
                                  help="set the agent_display_name")
    a_name.add_argument("value")
    a_name.set_defaults(func=cmd_agent_area_set_name)

    a_pref = area_sub.add_parser("set-pref",
                                  help="set a preference key=value")
    a_pref.add_argument("key")
    a_pref.add_argument("value", help="value (JSON-decoded if possible)")
    a_pref.add_argument("--scope", choices=("memory", "behavior"),
                        default="behavior",
                        help="which preference bucket (default: behavior)")
    a_pref.set_defaults(func=cmd_agent_area_set_pref)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
