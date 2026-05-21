"""Textual ``App`` entry point for the AGORA Control Center v2.

Phase B: tabbed UI with 14 panes (12 parity + 2 new — Scheduled +
Childruns). Each pane is a :class:`RefreshingPane` subclass that
auto-refreshes async via the shared :class:`ctl.client.AgoraClient`.
Login persists to ``~/.laia/admin-session.json`` (same file the legacy
curses TUI uses, so the operator doesn't have to re-auth when switching).
"""

from __future__ import annotations

import os
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button, Footer, Header, Input, Label, Static, TabbedContent, TabPane,
)

from .client import (
    AgoraClient, ApiError, DEFAULT_API_URL,
    clear_session_token, load_session_token, save_session_token,
)
from .screens.panes import (
    AreasPane, AuditPane, ChildrunsPane, ContainersPane, CostPane,
    DashboardPane, ErrorsPane, JobsPane, LaiaPane, LogsPane,
    MarketplacePane, ScheduledPane, SystemPane, UsersPane,
)


# (tab_id, label, pane_cls)
TABS: list[tuple[str, str, type]] = [
    ("dashboard", "Panel", DashboardPane),
    ("users", "Usuarios", UsersPane),
    ("containers", "Containers", ContainersPane),
    ("jobs", "Jobs", JobsPane),
    ("logs", "Logs", LogsPane),
    ("audit", "Audit", AuditPane),
    ("errors", "Errores", ErrorsPane),
    ("system", "Sistema", SystemPane),
    ("marketplace", "Marketplace", MarketplacePane),
    ("areas", "Areas", AreasPane),
    ("cost", "Coste", CostPane),
    ("laia", "LAIA", LaiaPane),
    ("scheduled", "Scheduled", ScheduledPane),
    ("childruns", "Childruns", ChildrunsPane),
]


class LoginModal(ModalScreen[bool]):
    """Inline login: username + password → POST /api/login."""

    DEFAULT_CSS = """
    LoginModal { align: center middle; }
    LoginModal > Container {
        width: 60; height: auto; padding: 1 2;
        border: round $primary; background: $panel;
    }
    LoginModal Input { margin-bottom: 1; }
    LoginModal #error { color: $error; }
    """

    def compose(self) -> ComposeResult:
        with Container():
            yield Label("AGORA Control Center — login")
            yield Input(placeholder="username",
                        value=os.environ.get("AGORA_ADMIN_USERNAME", "jorge"),
                        id="username")
            yield Input(placeholder="password", password=True, id="password")
            yield Static("", id="error")
            with Horizontal():
                yield Button("Login", variant="primary", id="login")
                yield Button("Cancel", id="cancel")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(False)
            return
        if event.button.id != "login":
            return
        username = (self.query_one("#username", Input).value or "").strip()
        password = self.query_one("#password", Input).value or ""
        client: AgoraClient = self.app.client  # type: ignore[attr-defined]
        try:
            await client.login(username, password)
        except ApiError as exc:
            self.query_one("#error", Static).update(f"[red]Login fallo: {exc}[/red]")
            return
        save_session_token(client.token or "")
        self.dismiss(True)


class MainScreen(Screen):
    """Main UI: tabbed view over the 14 panes."""

    BINDINGS = [
        Binding("r", "refresh_active", "Refrescar"),
        Binding("w", "cycle_window", "Window (Coste)"),
        Binding("L", "logout", "Logout"),
        Binding("q", "quit", "Salir"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(initial="tab-dashboard"):
            for tab_id, label, cls in TABS:
                with TabPane(label, id=f"tab-{tab_id}"):
                    yield cls()
        yield Footer()

    async def action_refresh_active(self) -> None:
        tabs = self.query_one(TabbedContent)
        active = tabs.active_pane
        if active is None:
            return
        for child in active.children:
            update = getattr(child, "update_data", None)
            if callable(update):
                # Run async update in worker so we don't block.
                self.app.run_worker(update(), exclusive=True)
                break

    async def action_cycle_window(self) -> None:
        tabs = self.query_one(TabbedContent)
        active = tabs.active_pane
        if active is None:
            return
        for child in active.children:
            cycle = getattr(child, "cycle_window", None)
            if callable(cycle):
                cycle()
                return

    async def action_logout(self) -> None:
        clear_session_token()
        client: AgoraClient = self.app.client  # type: ignore[attr-defined]
        client.token = None
        ok = await self.app.push_screen_wait(LoginModal())
        if not ok:
            self.app.exit(0)


class CtlApp(App):
    """Top-level Textual app."""

    CSS = """
    Screen { background: $surface; }
    TabbedContent { height: 1fr; }
    TabPane { padding: 1 1; }
    DataTable { height: 1fr; }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Salir", priority=True),
    ]

    def __init__(self, api_url: str = DEFAULT_API_URL) -> None:
        super().__init__()
        self.client = AgoraClient(api_url=api_url, token=load_session_token())

    async def on_mount(self) -> None:
        if not self.client.token:
            ok = await self.push_screen_wait(LoginModal())
            if not ok:
                self.exit(0)
                return
        await self.push_screen(MainScreen())

    async def on_unmount(self) -> None:
        await self.client.close()


def main() -> int:
    """Console entry point. ``python -m ctl`` calls this."""
    import argparse
    parser = argparse.ArgumentParser(
        prog="ctl",
        description="AGORA Control Center v2 (Textual)",
    )
    parser.add_argument("--api", default=DEFAULT_API_URL,
                        help=f"AGORA backend URL (default: {DEFAULT_API_URL})")
    parser.add_argument("--version", action="store_true")
    args = parser.parse_args()
    if args.version:
        from . import __version__
        print(__version__)
        return 0
    app = CtlApp(api_url=args.api)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
