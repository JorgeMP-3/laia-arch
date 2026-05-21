# LAIA wizard — backend reference (for C1 / contributors)

> 📅 2026-05-21 — Claude Code 1 — `feat/installer-wizard`
> Audience: anyone touching the engine, the flows, or the JSON contract.
> If you only render screens, see `docs/WIZARD.md` (C2's territory).

---

## 30-second tour

```
sudo laia-wizard
  └─ bin/laia-wizard                       (bash mini-bootstrap)
      └─ python3 -m laia_cli.install_wizard
            ├─ contract.py                 (schemas — frozen ABI)
            ├─ engine.py                   (state machine)
            ├─ state.py                    (checkpoint to ~/LAIA-ARCH/wizard-state.json)
            ├─ validators.py               (named input validators)
            ├─ flows/{install,clone,diagnose,reset,connectivity}.py
            │       ↳ each wraps an existing bin/laia-* binary
            ├─ ui/__init__.py              (C2's TUI — falls back to _dev_ui.py)
            └─ _dev_ui.py                  (input()-only fallback)
```

Engine ↔ UI contract: three calls only.

```python
while not engine.is_done():
    screen = engine.next_screen()                # WizardScreen
    user_input = ui.render(screen)               # dict | "back" | "quit"
    result = engine.submit(user_input)           # ValidationResult
    if result.ready_action:
        for event in engine.execute():           # Iterator[ProgressEvent]
            ui.render_progress(event)
        engine.mark_done()
```

---

## The contract (`contract.py`)

`CONTRACT_VERSION = "0.1.0"`. Bump it on every schema-breaking change. C2
reads it; if its expected version doesn't match, it MUST refuse to render
rather than guess.

### `WizardScreen`

```python
WizardScreen(
    id="clone.source_host",        # stable identifier
    title="Origen",
    description="…",
    fields=(Field(...), ...),      # zero or more inputs
    actions=(ACTION_BACK, ACTION_NEXT),
    help_text="…",
    style={...},                   # free-form theme overrides
)
```

### `Field`

Types: `text`, `password`, `choice`, `checklist`, `yesno`, `path`, `info`.

`info` fields are read-only labels — C2 must render them but not collect a
value. C1 uses them for summary screens.

Conditional visibility:
```python
Field(name="api_key", ..., depends_on={"provider": "*"})    # any non-empty provider
Field(name="key", ..., depends_on={"provider": "openai"})   # exact match
```

`field_visible(field, current_values)` is the helper C2 should consult
before rendering each field.

### `Action`

Buttons. `kind` is one of `next | back | quit | submit | skip | custom`.
`danger=True` lets C2 paint the button red.

The flow signals "ready to execute" by including an action with
`kind="submit"` and a `name` like `"run"`. When C2 sends back
`{"_action": "run"}`, the engine flips `result.ready_action = <screen_id>`
and the caller drives `engine.execute()`.

### `ValidationResult`

```python
ValidationResult(
    ok=False,
    errors={"admin_user": "Username inválido (a-z…)."},
    next_screen=None,
    ready_action=None,
)
```

`ok=True` paths:
* `next_screen` set → render that next screen.
* `ready_action` set → consume `engine.execute()`.
* Both None → top of the loop (mode_select).

### `ProgressEvent`

Streamed from `engine.execute()`. C2 renders them as they arrive.

| `type`           | When                                  | Notable `extra` keys |
|------------------|----------------------------------------|----------------------|
| `step_start`     | Long-running step begins              | `cmd` (argv list)    |
| `step_progress`  | Status update mid-step (no %)         | —                    |
| `step_done`      | Step finished OK                      | `returncode=0`       |
| `step_error`     | Step failed                           | `returncode`, `hint` |
| `log_line`       | Raw output line (tail display)        | —                    |
| `info`           | User-visible note, non-fatal          | —                    |
| `warning`        | Non-fatal warning                     | —                    |
| `summary`        | Post-run key/value table              | `rows`, `next_steps` |
| `finished`       | Whole execute() done; loop terminates | `ok` (bool)          |

---

## State machine (`engine.py`)

The engine owns:

1. A `WizardState` (mode, current screen id, gathered values, history).
2. A reference to the active `Flow` module (set after mode_select).
3. A pending `_ExecPlan` (the flow + start time, set on confirm).

The mode_select screen lives in the engine, not in any flow — every other
screen is owned by a flow.

### Adding a new flow

1. Create `flows/yourmode.py` exporting the `Flow` protocol:
   ```python
   flow_id = "yourmode"
   first_screen_id = "intro"
   screens: dict[str, Any] = {...}        # WizardScreen | callable(state) -> WizardScreen
   def next_screen_id(screen_id, state): ...
   def execute(state): yield ProgressEvent(...)
   ```
2. Register it in `engine._FLOW_MODULES`.
3. Add a `Choice` to `MODE_SELECT_SCREEN.fields[0].choices`.
4. Write `tests/wizard/test_flows_yourmode.py` (mirror the others).

Done. No engine change required for the happy path.

### Checkpointing

State is persisted to `$LAIA_HOME/wizard-state.json` (default
`$HOME/LAIA-ARCH/wizard-state.json`) at mode 0600. Every `submit()` writes
it (unless `WizardEngine(autosave=False)`).

Secrets are scrubbed before disk via `state.SECRET_FIELD_NAMES`. Extend
that frozenset when a new sensitive field appears in a flow — don't rely
on per-flow filtering.

On successful `execute()`, the checkpoint is deleted. On crash / Ctrl-C,
it survives, and `--resume` picks it up.

A checkpoint whose `contract_version` doesn't match `CONTRACT_VERSION` is
silently ignored. Bumping the contract version is therefore an explicit
break with old in-progress sessions.

---

## Subprocess plumbing (`flows/_subprocess.py`)

`stream_command(cmd, step_id, label, ...) -> Iterator[ProgressEvent]`

* Spawns `cmd` with merged stderr→stdout, line-buffered text mode.
* Yields one `step_start`, then `log_line` per output line, with two
  pattern-based promotions:
  - `═══ Phase X ═══` (from `common.sh::log_step`) → `step_progress`.
  - `sigue construyendo …` heartbeat (from `rebuild-2-images.sh`) →
    `step_progress`.
* Ends with `step_done` or `step_error` carrying the return code.

Filtering rules live in `_NOISE_RES`. Extend them rather than hard-coding
checks in flow modules.

`repo_root()` resolves `$LAIA_ROOT` first, then walks up from the file to
find `infra/installer/`, then falls back to `$HOME/LAIA`.

---

## Validators (`validators.py`)

Each entry in `VALIDATORS` is `(value) -> (ok, error_message_or_none)`.

To add one:
1. Write the function below the existing block.
2. Add an entry to `VALIDATORS`.
3. Cover happy + sad in `tests/wizard/test_validators.py` (parametrize).

Flows reference validators **by name** in `Field.validator` so the engine
can call them uniformly. Unknown names return a clean error, not a crash —
this matters during refactors.

---

## Conventions

* C1 never `print()`s. Every user-visible string flows through a
  `WizardScreen` or a `ProgressEvent`.
* Flows are pure-Python modules, no top-level side effects beyond defining
  static screens. `repo_root()` is the only filesystem dependency at
  import time and it's lazy.
* Subprocesses are invoked via `_subprocess.stream_command` so progress
  parsing stays centralized.
* Sensitive values (passwords, tokens) ride in `state.values` like any
  other field but are filtered on save. Don't roll your own persistence.

---

## Tests

```bash
.laia-core/venv/bin/pytest tests/wizard/ -v
```

Coverage as of contract `0.1.0`:

| File                          | Asserts |
|-------------------------------|---------|
| test_contract.py              | 9       |
| test_state.py                 | 7       |
| test_engine.py                | 11      |
| test_flows.py                 | 14      |
| test_validators.py            | 56      |
| **Total**                     | **97**  |

Plus the inherited `tests/installer/run_all.sh` suite — 19 scripts, 288
shell asserts.

---

## Limits / TODO for v0.2.0

* `--headless` flag exists in the CLI but is not yet honored end-to-end.
  Wiring it through means accepting a YAML/JSON answers file and using
  `_dev_ui.render()` short-circuited to read from it.
* Tailscale install flow assumes `curl | sh` — fine for Ubuntu, breaks for
  airgapped hosts. Add an offline path.
* Reset flow's snapshot uses `tar -C / paths…`. For datasets > a few GB
  it should switch to `lxd snapshot` of containers + zstd of bind mounts.
* The diagnose flow parses emoji output — if the installer ever switches
  to JSON logging that becomes nicer.

---

## Hand-off to C2

The contract is frozen at `0.1.0`. Anything you need to render is in
`contract.py`. If you find you can't render something well, open a PR to
extend the contract — don't paper over it on your side, that breaks the
loop's symmetry.

The `_dev_ui.py` fallback exists so the wizard is runnable while you
build the real UI. Once `ui/__init__.py` exposes `render(screen)` and
`render_progress(event)`, `__main__.py` prefers it automatically.

Fixtures: when you need example screens for snapshot tests, take them
from `engine.MODE_SELECT_SCREEN` and the per-flow `screens` dicts.

Good rendering.
