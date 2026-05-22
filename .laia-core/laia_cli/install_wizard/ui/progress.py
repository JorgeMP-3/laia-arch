"""Renderer for ``ProgressEvent``s emitted during ``engine.execute()``.

Strategy
--------

The engine yields a stream of small events. Rendering them with a full-blown
``rich.live.Live`` display would require sharing state across calls, which
fights the simple per-event API. Instead we render each event as one or two
visually distinct lines, using glyphs, colors and indentation so the eye can
follow long operations naturally:

```
▸  Phase H: agora data                ← step_start
   · running rsync                    ← log_line (dim)
   · ...                              ← log_line
✓  Phase H: agora data OK             ← step_done
≡  Resumen                            ← summary  (followed by a key/value table)
■  Operación completada con éxito.    ← finished
```

Long log lines are clipped so a noisy command can't blow up the terminal.
"""

from __future__ import annotations

from rich.console import Console
from rich.text import Text

from ..contract import ProgressEvent
from . import components as comp
from .theme import THEME

# Maximum visible characters for a single log_line.
_LOG_LINE_CLIP = 200


def render_progress(event: ProgressEvent, console: Console | None = None) -> None:
    """Print one event in a single visually distinct line (or block)."""
    from .console import get_console  # local import keeps __init__ light
    console = console or get_console()

    if event.type == "step_start":
        console.print(Text.assemble(
            (f"  {THEME.g_arrow}  ", THEME.accent),
            (event.label, THEME.primary),
        ))
        if event.extra and event.extra.get("log_path"):
            console.print(Text.assemble(
                ("       Ver log completo: ", THEME.muted),
                (str(event.extra["log_path"]), THEME.field_value),
            ))
        return

    if event.type == "step_progress":
        # Sub-step / phase boundary — visually less prominent than step_start
        # so the eye can group everything between two boundaries.
        console.print(Text.assemble(
            (f"     {THEME.g_dot} ", THEME.muted),
            (event.label, THEME.secondary),
        ))
        return

    if event.type == "step_done":
        console.print(Text.assemble(
            (f"  {THEME.g_ok}  ", THEME.success),
            (event.label, THEME.field_value),
            (f"   ({event.elapsed_s:.1f}s)", THEME.muted) if event.elapsed_s else ("", ""),
        ))
        if event.extra and event.extra.get("log_path"):
            console.print(Text.assemble(
                ("       Log: ", THEME.muted),
                (str(event.extra["log_path"]), THEME.muted),
            ))
        return

    if event.type == "step_error":
        text = Text.assemble(
            (f"  {THEME.g_err}  ", THEME.error),
            (event.label, THEME.error),
        )
        console.print(text)
        if event.extra and event.extra.get("hint"):
            console.print(Text.assemble(
                ("       ", ""),
                (f"{THEME.g_arrow} {event.extra['hint']}", THEME.muted),
            ))
        if event.extra and event.extra.get("log_path"):
            console.print(Text.assemble(
                ("       Ver log completo: ", THEME.muted),
                (str(event.extra["log_path"]), THEME.field_value),
            ))
        tail = list((event.extra or {}).get("tail") or [])
        if tail:
            console.print(Text("       Últimas líneas:", style=THEME.muted))
            for line in tail[-12:]:
                msg = str(line)
                if len(msg) > _LOG_LINE_CLIP:
                    msg = msg[:_LOG_LINE_CLIP - 1] + "…"
                console.print(Text.assemble(
                    ("         ", ""),
                    (msg, THEME.muted),
                ))
        return

    if event.type == "log_line":
        # Clip long lines + dim them so they recede visually.
        msg = event.label
        if len(msg) > _LOG_LINE_CLIP:
            msg = msg[:_LOG_LINE_CLIP - 1] + "…"
        console.print(Text.assemble(
            ("       ", ""),
            (msg, THEME.muted),
        ))
        return

    if event.type == "info":
        console.print(Text.assemble(
            (f"  {THEME.g_info}  ", THEME.secondary),
            (event.label, THEME.secondary),
        ))
        return

    if event.type == "warning":
        console.print(Text.assemble(
            (f"  {THEME.g_warn}  ", THEME.warning),
            (event.label, THEME.warning),
        ))
        return

    if event.type == "summary":
        # Two-column key/value table inside a soft panel.
        rows: list[tuple[str, str]] = []
        next_steps: list[str] = []
        if event.extra:
            rows = list(event.extra.get("rows") or [])
            next_steps = list(event.extra.get("next_steps") or [])
        console.print()
        console.print(comp.panel(
            comp.summary_table(rows),
            title_text=f"{THEME.g_check}  {event.label}",
            border_style=THEME.secondary,
        ))
        if next_steps:
            console.print(Text("  Siguientes pasos:", style=THEME.field_label))
            for step in next_steps:
                console.print(Text.assemble(
                    ("       ", ""),
                    (f"{THEME.bullet} ", THEME.accent),
                    (step, THEME.field_value),
                ))
        return

    if event.type == "finished":
        ok = bool((event.extra or {}).get("ok", True))
        glyph = THEME.g_ok if ok else THEME.g_err
        style = THEME.success if ok else THEME.error
        elapsed = f"   (total: {event.elapsed_s:.1f}s)" if event.elapsed_s else ""
        console.print()
        console.print(Text.assemble(
            (f"  {glyph}  ", style),
            (event.label, style),
            (elapsed, THEME.muted),
        ))
        return

    # Fallback for any unknown event type — keep something visible so we
    # never silently drop information.
    console.print(Text.assemble(
        ("  ·  ", THEME.muted),
        (f"[{event.type}] {event.label}", THEME.muted),
    ))


__all__ = ["render_progress"]
