"""Textual UI for the LAIA install wizard.

Public entry point: :func:`run_textual_wizard`. Selected by
``__main__.py`` when the environment variable ``LAIA_UI=textual`` is set
(or when ``--ui textual`` is passed). The legacy ``rich.prompt`` UI in
``..ui`` keeps working as the default while this module matures.

Architecture in one paragraph: a single :class:`LaiaWizardApp` is the
host. Its :meth:`on_mount` spins up a thread worker that drives the
existing :class:`~laia_cli.install_wizard.engine.WizardEngine` exactly
like ``__main__._run`` does — but instead of synchronous ``input()``,
each screen is pushed onto Textual's screen stack via
``push_screen_wait`` (called through ``call_from_thread`` so the worker
thread blocks until the user dismisses it). Progress events are
streamed into :class:`ExecuteScreen` via the same bridge. The wizard's
contract (``WizardScreen`` / ``ProgressEvent`` from ``contract.py``) is
the same shape the rich UI consumes, so flows don't need to know which
UI is on the other side.
"""

from __future__ import annotations

from .app import run_textual_wizard, is_textual_available

__all__ = ["run_textual_wizard", "is_textual_available"]
