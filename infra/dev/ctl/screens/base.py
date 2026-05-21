"""Shared widgets/helpers for the v2 control center screens.

Every tab pane in the App is a :class:`RefreshingPane` subclass that:
  * holds a reference to the shared :class:`ctl.client.AgoraClient` (via ``app.client``),
  * runs ``async def refresh()`` once on mount and every N seconds,
  * exposes ``action_refresh`` bound to ``r`` (App-level binding).

Concrete panes override ``compose()`` and ``refresh()``.
"""

from __future__ import annotations

from typing import Any, Iterable

from textual.containers import Vertical
from textual.widgets import DataTable, Static


class RefreshingPane(Vertical):
    """A Vertical container that auto-refreshes every ``REFRESH_SECONDS``.

    Subclasses override ``async def refresh(self)`` and ``compose()``.
    The App owns the shared :class:`AgoraClient`; access via ``self.app.client``.
    """

    REFRESH_SECONDS: float = 5.0
    DEFAULT_CSS = """
    RefreshingPane { height: 1fr; }
    RefreshingPane > DataTable { height: 1fr; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._refresh_timer = None

    async def on_mount(self) -> None:
        await self.update_data()
        self._refresh_timer = self.set_interval(self.REFRESH_SECONDS, self.update_data)

    async def update_data(self) -> None:
        """Override in subclass. Don't call this ``refresh`` — Textual's
        ``Widget.refresh()`` is used internally with kwargs like ``layout``
        and shadowing it breaks every layout pass."""

    @property
    def client(self) -> Any:
        return self.app.client  # type: ignore[attr-defined]


def table_widget(*columns: str) -> DataTable:
    """Sugar to build a DataTable preconfigured for our usage."""
    t = DataTable(zebra_stripes=True, cursor_type="row")
    t.add_columns(*columns)
    return t


def rows_into_table(table: DataTable, rows: Iterable[Iterable[Any]]) -> None:
    """Wipe + repopulate a DataTable. Cheap re-render for small N (<500)."""
    table.clear()
    for r in rows:
        table.add_row(*(str(c) if c is not None else "" for c in r))
