"""All 14 tab panes for the v2 control center.

Kept in one module on purpose — each pane is ~40 LOC, and threading
them into 14 separate files would multiply imports without giving any
isolation benefit. When a pane outgrows ~150 LOC (typically because it
gains modals or complex state), it moves to its own module.

Panes (12 parity + 2 new):
  dashboard, users, containers, jobs, logs, audit, errors, system,
  marketplace, areas, cost, laia, scheduled, childruns.
"""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, RichLog, Static

from ..client import ApiError
from .base import RefreshingPane, rows_into_table, table_widget


def _fmt_age(ts: str | None) -> str:
    if not ts:
        return "-"
    from datetime import datetime, timezone
    try:
        when = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return ts[:19]
    delta = datetime.now(timezone.utc) - when
    s = int(delta.total_seconds())
    if s < 60: return f"{s}s"
    if s < 3600: return f"{s // 60}m"
    if s < 86400: return f"{s // 3600}h"
    return f"{s // 86400}d"


# ── 1) Dashboard ──────────────────────────────────────────────────────


class DashboardPane(RefreshingPane):
    REFRESH_SECONDS = 5.0

    def compose(self) -> ComposeResult:
        yield Static("Cargando…", id="dash_summary")
        yield Static("", id="dash_health")

    async def update_data(self) -> None:
        try:
            health = await self.client.health()
            status = (await self.client.status()).get("status") or {}
        except ApiError as exc:
            self.query_one("#dash_summary", Static).update(f"[red]API: {exc}[/red]")
            return
        users = status.get("users", []) or []
        cont = status.get("containers", []) or []
        running = sum(1 for c in cont if (c.get("state") or "").lower() == "running")
        lines = [
            f"[bold]AGORA[/]   {self.client.api_url}",
            f"  users: [b]{len(users)}[/]   containers running: [b]{running}/{len(cont)}[/]",
            f"  default LLM: [b]{health.get('default_llm_provider')}[/]",
            f"  auth.json: {health.get('auth_json_status')}   db: {health.get('db')}",
        ]
        self.query_one("#dash_summary", Static).update("\n".join(lines))
        self.query_one("#dash_health", Static).update(
            f"[dim]uptime: {health.get('time', '')}[/dim]"
        )


# ── 2) Users ──────────────────────────────────────────────────────────


class UsersPane(RefreshingPane):
    REFRESH_SECONDS = 10.0

    def compose(self) -> ComposeResult:
        yield table_widget("ID", "Username", "Role", "Active", "LLM", "Agent")

    async def update_data(self) -> None:
        try:
            body = await self.client.users()
        except ApiError as exc:
            self.notify(f"users: {exc}", severity="error")
            return
        rows = [
            (u.get("id"), u.get("username"), u.get("role"),
             "✓" if u.get("active") else "✗",
             u.get("llm_provider") or "—",
             u.get("agent_id") or "—")
            for u in body.get("users", [])
        ]
        rows_into_table(self.query_one(DataTable), rows)


# ── 3) Containers ─────────────────────────────────────────────────────


class ContainersPane(RefreshingPane):
    REFRESH_SECONDS = 10.0

    def compose(self) -> ComposeResult:
        yield table_widget("Name", "State", "IPv4", "Profile")

    async def update_data(self) -> None:
        try:
            body = await self.client.containers_list()
        except ApiError as exc:
            self.notify(f"containers: {exc}", severity="error")
            return
        rows = [
            (c.get("name"), c.get("state"), c.get("ipv4") or "—",
             c.get("profile") or "—")
            for c in body.get("containers", [])
        ]
        rows_into_table(self.query_one(DataTable), rows)


# ── 4) Jobs ───────────────────────────────────────────────────────────


class JobsPane(RefreshingPane):
    REFRESH_SECONDS = 5.0

    def compose(self) -> ComposeResult:
        yield table_widget("ID", "Kind", "Status", "Actor", "Age")

    async def update_data(self) -> None:
        try:
            body = await self.client.jobs()
        except ApiError as exc:
            self.notify(f"jobs: {exc}", severity="error")
            return
        rows = [
            (j.get("id", "")[:18], j.get("kind"), j.get("status"),
             j.get("actor_id", "")[:18], _fmt_age(j.get("created_at")))
            for j in body.get("jobs", [])
        ]
        rows_into_table(self.query_one(DataTable), rows)


# ── 5) Logs ───────────────────────────────────────────────────────────


class LogsPane(RefreshingPane):
    REFRESH_SECONDS = 3.0
    DEFAULT_CSS = """
    LogsPane > RichLog { height: 1fr; }
    """

    source: str = "agora-backend"

    def compose(self) -> ComposeResult:
        yield Static(f"[dim]source: {self.source}[/dim]", id="logs_src")
        yield RichLog(id="logs_view", highlight=True, markup=False, wrap=False)

    async def update_data(self) -> None:
        try:
            body = await self.client.logs(self.source, lines=200)
        except ApiError as exc:
            self.notify(f"logs: {exc}", severity="error")
            return
        lines = (body.get("logs") or {}).get("lines", []) or []
        log = self.query_one("#logs_view", RichLog)
        log.clear()
        for ln in lines[-200:]:
            log.write(ln)


# ── 6) Audit ──────────────────────────────────────────────────────────


class AuditPane(RefreshingPane):
    REFRESH_SECONDS = 8.0

    def compose(self) -> ComposeResult:
        yield table_widget("Time", "Phase", "Tool", "User", "Slug", "Result")

    async def update_data(self) -> None:
        try:
            body = await self.client.audit(limit=200)
        except ApiError as exc:
            self.notify(f"audit: {exc}", severity="error")
            return
        rows = []
        for c in body.get("tool_calls", []):
            rows.append((
                _fmt_age(c.get("ts")),
                c.get("phase", "")[:8],
                c.get("tool", "")[:20],
                (c.get("user_id") or "")[:14],
                (c.get("agent_slug") or "")[:14],
                str(c.get("result_len") or "")[:6],
            ))
        rows_into_table(self.query_one(DataTable), rows)


# ── 7) Errors ─────────────────────────────────────────────────────────


class ErrorsPane(RefreshingPane):
    REFRESH_SECONDS = 8.0

    def compose(self) -> ComposeResult:
        yield table_widget("Time", "Level", "Source", "Message")

    async def update_data(self) -> None:
        try:
            body = await self.client.errors(limit=100)
        except ApiError as exc:
            self.notify(f"errors: {exc}", severity="error")
            return
        rows = []
        for e in body.get("errors", []):
            rows.append((
                _fmt_age(e.get("ts")),
                e.get("level", "")[:6],
                (e.get("logger") or e.get("source") or "")[:20],
                (e.get("message") or "")[:80],
            ))
        rows_into_table(self.query_one(DataTable), rows)


# ── 8) System ─────────────────────────────────────────────────────────


class SystemPane(RefreshingPane):
    REFRESH_SECONDS = 15.0

    def compose(self) -> ComposeResult:
        yield Static("Cargando…", id="sys_block")

    async def update_data(self) -> None:
        try:
            s = (await self.client.status()).get("status") or {}
            health = await self.client.health()
        except ApiError as exc:
            self.query_one("#sys_block", Static).update(f"[red]API: {exc}[/red]")
            return
        image = s.get("image") or {}
        auth = s.get("auth_json") or {}
        lines = [
            f"[bold]System[/]",
            f"  data_dir       : {health.get('data_dir')}",
            f"  default LLM    : {health.get('default_llm_provider')}",
            f"  auth.json      : {auth.get('path')} status={auth.get('status')} ready={auth.get('ready')}",
            f"  LXD available  : {health.get('lxd_available')}",
            f"  image          : {'stale' if image.get('stale') else 'fresh'}  drift={image.get('drift_seconds')}s",
            f"  laia-agora ts  : {health.get('time')}",
        ]
        self.query_one("#sys_block", Static).update("\n".join(lines))


# ── 9) Marketplace ────────────────────────────────────────────────────


class MarketplacePane(RefreshingPane):
    REFRESH_SECONDS = 10.0

    def compose(self) -> ComposeResult:
        yield Static("", id="mkt_summary")
        yield table_widget("Section", "Kind", "Slug", "Version", "Owner", "Status")

    async def update_data(self) -> None:
        try:
            pending = await self.client.marketplace_pending()
            plugins_cat = (await self.client.plugins_catalog()).get("data") or []
            skills_cat = (await self.client.skills_catalog()).get("data") or []
        except ApiError as exc:
            self.notify(f"marketplace: {exc}", severity="error")
            return
        prows: list[tuple] = []
        for p in pending.get("plugins") or []:
            prows.append(("pending", "plugin", p.get("slug"), p.get("version"),
                          p.get("owner_user_id"), p.get("status")))
        for s in pending.get("skills") or []:
            prows.append(("pending", "skill", s.get("slug"), "—",
                          s.get("owner_user_id"), s.get("status")))
        for p in plugins_cat:
            prows.append(("catalog", "plugin", p.get("slug"), p.get("version"),
                          p.get("owner_user_id"), p.get("status")))
        for s in skills_cat:
            prows.append(("catalog", "skill", s.get("slug"), "—",
                          s.get("owner_user_id"), s.get("status")))
        rows_into_table(self.query_one(DataTable), prows)
        self.query_one("#mkt_summary", Static).update(
            f"[bold]Pending[/]: {len(pending.get('plugins', []) or []) + len(pending.get('skills', []) or [])}   "
            f"[bold]Plugins catalog[/]: {len(plugins_cat)}   "
            f"[bold]Skills catalog[/]: {len(skills_cat)}"
        )


# ── 10) Areas ─────────────────────────────────────────────────────────


class AreasPane(RefreshingPane):
    """Lists per-user agent_area summary. Uses ``users-overview`` to
    avoid the N+1 of the legacy curses TUI; per-row full content is
    fetched lazily when the user opens the detail (Phase C)."""
    REFRESH_SECONDS = 20.0

    def compose(self) -> ComposeResult:
        yield table_widget("User", "Display name", "Skills", "Updated")

    async def update_data(self) -> None:
        try:
            ov = await self.client.users_overview(window="day")
        except ApiError as exc:
            self.notify(f"areas: {exc}", severity="error")
            return
        # Re-use users-overview row but pull display_name from the
        # already-present field. We won't fetch full agent_area per user
        # on refresh (lazy detail panel will).
        rows = [
            (u.get("username"), u.get("display_name"),
             str(u.get("learnings_count", 0)),
             _fmt_age(None))  # placeholder; full area_for_user has updated_at
            for u in ov.get("users", [])
        ]
        rows_into_table(self.query_one(DataTable), rows)


# ── 11) Cost ──────────────────────────────────────────────────────────


class CostPane(RefreshingPane):
    """Per-user usage + budget caps. Phase B uses
    ``/api/admin/users-overview`` so 50 users = 1 request, not 51."""
    REFRESH_SECONDS = 10.0

    window: str = "day"

    def compose(self) -> ComposeResult:
        yield Static(f"[dim]window: {self.window}  (press W to cycle)[/]",
                     id="cost_summary")
        yield table_widget("User", "Calls", "Tok in/out", "Coste USD",
                           "Caps", "Status")

    async def update_data(self) -> None:
        try:
            ov = await self.client.users_overview(window=self.window)
        except ApiError as exc:
            self.notify(f"cost: {exc}", severity="error")
            return
        rows = []
        for u in ov.get("users", []):
            usage = u.get("usage") or {}
            budget = u.get("budget") or {}
            cost = float(usage.get("cost_usd") or 0.0)
            calls = int(usage.get("calls") or 0)
            tin = int(usage.get("tokens_input") or 0)
            tout = int(usage.get("tokens_output") or 0)
            cap_strs = []
            for k, label in (("daily_usd", "D"), ("monthly_usd", "M"),
                              ("tokens_daily", "T")):
                v = budget.get(k)
                if v is not None:
                    cap_strs.append(f"{label}≤{v}")
            caps = " ".join(cap_strs) or "—"
            status = "✓"
            if self.window == "day" and budget.get("daily_usd") is not None:
                cap_d = float(budget["daily_usd"])
                if cost >= cap_d: status = "✗"
                elif cost >= 0.8 * cap_d: status = "⚠"
            elif self.window == "month" and budget.get("monthly_usd") is not None:
                cap_m = float(budget["monthly_usd"])
                if cost >= cap_m: status = "✗"
                elif cost >= 0.8 * cap_m: status = "⚠"
            rows.append((u.get("username"), calls, f"{tin}/{tout}",
                         f"${cost:.4f}", caps, status))
        rows_into_table(self.query_one(DataTable), rows)

    def cycle_window(self) -> None:
        nxt = {"day": "week", "week": "month", "month": "day"}
        self.window = nxt.get(self.window, "day")
        self.query_one("#cost_summary", Static).update(
            f"[dim]window: {self.window}  (press W to cycle)[/]"
        )
        # Force-refresh now.
        self.app.run_worker(self.update_data(), exclusive=True)


# ── 12) LAIA ──────────────────────────────────────────────────────────


class LaiaPane(RefreshingPane):
    REFRESH_SECONDS = 15.0

    def compose(self) -> ComposeResult:
        yield Static("[bold]LAIA coordinator[/]", id="laia_title")
        yield table_widget("User", "Unread")
        yield Static("[dim]Chat con LAIA llega en Fase D.[/]",
                     id="laia_chat_hint")

    async def update_data(self) -> None:
        try:
            body = await self.client.laia_inbox_count()
        except ApiError as exc:
            self.notify(f"laia: {exc}", severity="error")
            return
        rows = [(r.get("username") or r.get("user_id"), r.get("unread"))
                for r in body.get("unread_by_user", [])]
        if not rows:
            rows = [("(ninguno pendiente)", "")]
        rows_into_table(self.query_one(DataTable), rows)


# ── 13) Scheduled (NEW) ───────────────────────────────────────────────


class ScheduledPane(RefreshingPane):
    """Scheduled jobs + webhooks across all users.
    Uses ``/api/admin/users-overview`` to enumerate users, then per-user
    fetches ``/api/admin/users/{id}/scheduled-jobs``. The latter is
    cheap (single SELECT) so we accept the N requests; if it ever
    matters we'll add an all-users batch endpoint."""
    REFRESH_SECONDS = 15.0

    def compose(self) -> ComposeResult:
        yield Static("", id="sched_summary")
        yield table_widget("User", "Type", "Name/Slug", "Cron/—", "Next/Status")

    async def update_data(self) -> None:
        try:
            ov = await self.client.users_overview(window="day")
            user_ids = [u["id"] for u in ov.get("users", [])]
        except ApiError as exc:
            self.notify(f"scheduled: {exc}", severity="error")
            return
        rows: list[tuple] = []
        total_jobs = 0
        total_webhooks = 0
        for uid in user_ids:
            try:
                body = await self.client.scheduled_jobs(uid)
            except ApiError:
                continue
            for j in body.get("scheduled_jobs") or []:
                rows.append((uid[:18], "job", j.get("name"),
                             j.get("cron_expr"), j.get("status")))
                total_jobs += 1
            for w in body.get("webhooks") or []:
                rows.append((uid[:18], "webhook", w.get("slug"),
                             "—", w.get("last_status") or "ok"))
                total_webhooks += 1
        self.query_one("#sched_summary", Static).update(
            f"[bold]Jobs[/]: {total_jobs}   [bold]Webhooks[/]: {total_webhooks}"
        )
        rows_into_table(self.query_one(DataTable), rows)


# ── 14) Childruns (NEW) ───────────────────────────────────────────────


class ChildrunsPane(RefreshingPane):
    REFRESH_SECONDS = 12.0

    def compose(self) -> ComposeResult:
        yield Static("", id="cr_summary")
        yield table_widget("Parent", "Profile", "Purpose", "Status",
                           "Tokens", "ms")

    async def update_data(self) -> None:
        try:
            ov = await self.client.users_overview(window="week")
            user_ids = [u["id"] for u in ov.get("users", [])]
        except ApiError as exc:
            self.notify(f"childruns: {exc}", severity="error")
            return
        rows: list[tuple] = []
        for uid in user_ids:
            try:
                body = await self.client.child_runs(uid, limit=10)
            except ApiError:
                continue
            for c in body.get("child_runs") or []:
                rows.append((
                    (c.get("parent_user_id") or "")[:18],
                    c.get("profile"),
                    (c.get("purpose") or "")[:30],
                    c.get("status"),
                    str(c.get("tokens_used") or ""),
                    str(c.get("duration_ms") or ""),
                ))
        self.query_one("#cr_summary", Static).update(
            f"[bold]Child runs (top 10 por parent)[/]: {len(rows)}"
        )
        rows_into_table(self.query_one(DataTable), rows)
