"""laia-pathd — Atlas: a live resolver for LAIA filesystem paths.

This package provides the resolver daemon that watches ~/.laia/config.yaml,
maintains a resolved snapshot in ~/.laia/.env.paths, a symlink atlas in
~/.laia/atlas/, and serves lookups over a Unix domain socket at
~/.laia/pathd.sock.

Modules:
    state    — JSON-on-disk state store (path cache, pending restarts)
    ipc      — JSON-RPC server over Unix socket
    notifier — regenerates .env.paths and symlink farm on changes
    server   — asyncio orchestrator that ties everything together
    cli      — daemon entrypoint (laia-pathd) and path CLI (laia-path)
"""
