"""Screen modules used by the v2 control center App.

Each screen is a self-contained Textual ``Screen`` (or pane/widget)
returning a ``Widget`` that the App embeds inside a ``TabbedContent``.
The base helpers (auto-refresh, table-from-rows) live in :mod:`._base`.
"""

from .base import RefreshingPane, table_widget  # noqa: F401
