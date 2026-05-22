"""Frozen JSON contract between the wizard engine (C1) and the TUI layer (C2).

The whole point of this file: every screen, every input field, every progress
event the user sees flows through one of these dataclasses. C1 produces them,
C2 renders them. Neither side touches the other's internals.

Rules
-----
* C2 NEVER invokes ``bin/laia-*`` or any subprocess. It receives a
  :class:`WizardScreen`, asks the user, and returns a dict (or ``"back"`` /
  ``"quit"`` sentinel) to C1.
* C1 NEVER prints to stdout. Anything the user must see is either a
  :class:`WizardScreen` or a :class:`ProgressEvent` yielded from
  :func:`engine.WizardEngine.execute`.
* Changes to this file are a CONTRACT version bump. Bump :data:`CONTRACT_VERSION`
  and coordinate via PR; both Claudes must agree.

JSON serialization
------------------
Every dataclass below is JSON-friendly via :func:`to_dict` / :func:`from_dict`.
This matters for: checkpointing (``state.py``), inter-process testing (C2's
snapshot fixtures), and the optional ``--headless`` mode that consumes a script
of values.

Style note
----------
Frozen dataclasses make accidental mutation in flow code an error rather than
a silent bug. The only place mutation is allowed is the in-progress ``values``
dict held by the engine's state, which is plain mutable on purpose.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

# Bump on any schema-breaking change. C2 reads this; if it doesn't match its
# expected version, it refuses to render rather than guess.
CONTRACT_VERSION = "0.1.0"


# --- Field types ---------------------------------------------------------------

FieldType = Literal[
    "text",       # free-form single-line input
    "password",   # text but C2 must mask it
    "choice",     # single-select from `choices`
    "checklist",  # multi-select from `choices`
    "yesno",      # boolean prompt
    "path",       # filesystem path (validator may check existence)
    "info",       # read-only label / paragraph; no input
]


@dataclass(frozen=True)
class Choice:
    """One option inside a ``choice`` / ``checklist`` field."""

    value: str
    label: str
    description: str | None = None
    recommended: bool = False


@dataclass(frozen=True)
class Field:
    """An individual input the user fills in on a screen."""

    name: str
    type: FieldType
    label: str
    placeholder: str | None = None
    default: Any = None
    choices: tuple[Choice, ...] | None = None
    # Name of a validator from :mod:`validators`. Engine resolves the symbol.
    validator: str | None = None
    # Show this field only when the named other field has the given value.
    # ``{"source_kind": "tailscale"}`` reads "show me only if source_kind ==
    # tailscale". For "any non-empty", use ``"*"``.
    depends_on: dict[str, Any] | None = None
    secret: bool = False
    help_text: str | None = None


# --- Action buttons ------------------------------------------------------------

ActionKind = Literal["next", "back", "quit", "submit", "skip", "custom"]


@dataclass(frozen=True)
class Action:
    """A button at the bottom of a screen."""

    name: str            # "next" | "back" | "quit" | "wipe-now" | ...
    label: str           # what the user sees
    kind: ActionKind = "custom"
    danger: bool = False  # C2 may render destructive actions in red


# Convenience constants — every flow uses these.
ACTION_NEXT = Action(name="next", label="Continuar", kind="next")
ACTION_BACK = Action(name="back", label="Atrás", kind="back")
ACTION_QUIT = Action(name="quit", label="Salir", kind="quit")


# --- Screens -------------------------------------------------------------------

@dataclass(frozen=True)
class WizardScreen:
    """One full screen the user sees. C1 hands it to C2.

    ``id`` is a stable identifier — flows use it for branching, tests use it
    for snapshot fixtures, the checkpoint refers back to the screen the user
    bailed out from.
    """

    id: str
    title: str
    description: str | None = None
    fields: tuple[Field, ...] = ()
    actions: tuple[Action, ...] = (ACTION_NEXT,)
    help_text: str | None = None
    # Banner / theme overrides. Free-form so C2 can extend without breaking C1.
    style: dict[str, Any] | None = None


# --- Validation results --------------------------------------------------------

@dataclass(frozen=True)
class ValidationResult:
    """Result of submitting field values for a screen.

    ``ok=False`` means the user must stay on the same screen. ``errors`` is
    keyed by field name and contains the human-readable message C2 should
    show next to the field.

    ``ok=True`` means transition. ``next_screen`` is either another screen
    (the user continues filling forms), ``None`` (the engine reached the end
    of an interactive part — usually right before ``execute()``), or
    ``ready_action`` is set (engine wants C2 to confirm before execution).
    """

    ok: bool
    errors: dict[str, str] = field(default_factory=dict)
    next_screen: WizardScreen | None = None
    ready_action: str | None = None  # e.g. "run-install" → engine.execute it


# --- Execution events ----------------------------------------------------------

ProgressEventType = Literal[
    "step_start",     # a labelled step began
    "step_progress",  # progress update on the current step (percent or counts)
    "step_done",      # step finished OK
    "step_error",     # step finished with error; ``extra["hint"]`` may guide
    "log_line",       # a raw log line (tail-style display)
    "info",           # informational, non-fatal note for the user
    "warning",        # non-fatal warning
    "summary",        # post-run summary (key/value table)
    "finished",       # whole execution finished; payload says ok|failed
]


@dataclass(frozen=True)
class ProgressEvent:
    """Streamed by ``engine.execute()`` during long-running operations.

    ``percent`` is in [0.0, 100.0] when known, ``None`` for indeterminate.
    ``elapsed_s`` is wall-clock seconds since the action started.
    ``extra`` carries free-form payload — e.g. for ``summary`` it's a dict
    of rows; for ``step_error`` it may contain ``hint`` and ``log_path``.
    """

    type: ProgressEventType
    step_id: str | None
    label: str
    percent: float | None = None
    elapsed_s: float = 0.0
    extra: dict[str, Any] | None = None


# --- Serialization helpers -----------------------------------------------------

def to_dict(obj: Any) -> Any:
    """Deep-convert any contract dataclass (or list/dict thereof) to plain JSON.

    Used by the checkpoint, by C2's fixture writer, and by ``--headless`` to
    emit a transcript.
    """
    if hasattr(obj, "__dataclass_fields__"):
        # asdict leaves nested tuples as tuples; we want JSON arrays.
        return to_dict(asdict(obj))
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_dict(v) for v in obj]
    return obj


def screen_to_dict(screen: WizardScreen) -> dict[str, Any]:
    """Same as :func:`to_dict` but typed for C2's call sites."""
    return to_dict(screen)  # type: ignore[return-value]


def field_visible(f: Field, current_values: dict[str, Any]) -> bool:
    """C2 helper: should this field be shown given what the user already filled?

    Honors :attr:`Field.depends_on`. Supported semantics for ``dep_value``:

    * ``"*"``          — show when the dependency has ANY non-empty value.
    * a string         — show when the dependency equals that string.
    * ``list``/``tuple`` — show when the dependency is in the collection.
    * ``True``/``False`` — show when truthy/falsy (handy for yes/no toggles).
    """
    if not f.depends_on:
        return True
    for dep_name, dep_value in f.depends_on.items():
        actual = current_values.get(dep_name)
        if dep_value == "*":
            if not actual:
                return False
        elif isinstance(dep_value, (list, tuple)):
            if actual not in dep_value:
                return False
        elif isinstance(dep_value, bool):
            if bool(actual) != dep_value:
                return False
        elif actual != dep_value:
            return False
    return True


__all__ = [
    "CONTRACT_VERSION",
    "Choice",
    "Field",
    "FieldType",
    "Action",
    "ActionKind",
    "ACTION_NEXT",
    "ACTION_BACK",
    "ACTION_QUIT",
    "WizardScreen",
    "ValidationResult",
    "ProgressEvent",
    "ProgressEventType",
    "to_dict",
    "screen_to_dict",
    "field_visible",
]
