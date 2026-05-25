# LAIA wizard — theming

Todo lo cosmético del wizard vive en un solo archivo:
`.laia-core/laia_cli/install_wizard/ui/theme.py`.

Esto incluye paleta de colores, glifos, copy del banner, número de líneas
visibles de log durante la ejecución, etc. Cambiar el aspecto del wizard es
editar ese archivo o exportar variables de entorno antes de ejecutarlo.

---

## Variables de entorno

| Variable | Efecto |
|----------|--------|
| `NO_COLOR=1` | Monocromo total. Estándar [no-color.org](https://no-color.org/). |
| `LAIA_WIZARD_THEME=mono` | Igual que `NO_COLOR=1` pero explícito. |
| `LAIA_WIZARD_THEME=default` | Tema con colores (default). |
| `FORCE_COLOR=1` | Forzar color aunque stdout no sea un TTY (útil para tests / CI). |

---

## Dónde se aplican los tokens

Cada `Theme` define:

```python
primary: "bold cyan"           # títulos, choice labels
secondary: "bright_blue"       # sub-pasos, info secundaria
accent: "bold magenta"         # acciones / números de opción
success: "bold green"          # ✓ y panel "Listo"
warning: "bold yellow"         # ⚠ y panel "Aviso"
error: "bold red"              # ✗ y panel "Error"
danger: "bold red on black"    # acciones destructivas (reset)
muted: "dim white"             # descripciones, log_line clipped
title: "bold bright_white on blue"
panel_border: "cyan"
field_label: "bold"
field_value: "bright_white"
field_placeholder: "italic dim white"
```

Los glifos:

```python
g_ok = "✓"      g_err = "✗"       g_warn = "⚠"      g_info = "ℹ"
g_arrow = "▸"   g_busy = "⏳"      g_check = "■"     g_dot = "·"
g_run = "▶"     g_back = "←"      g_next = "→"      g_quit = "✕"
```

Copy / textos visibles:

```python
brand = "LAIA"
tagline = "Setup Wizard"
bullet = "•"
```

---

## Crear un tema custom

Como aún no soportamos plug-ins externos, lo más limpio es editar
`theme.py` y añadir tu propio `Theme` literal:

```python
# theme.py

_PASTEL = Theme(
    primary="bold rgb(155,89,182)",     # purple
    success="rgb(46,204,113)",          # mint
    warning="rgb(241,196,15)",          # mustard
    error="rgb(231,76,60)",             # coral
    accent="rgb(52,152,219)",           # sky
    muted="dim rgb(149,165,166)",
    panel_border="rgb(155,89,182)",
)


def get_theme(name=None):
    if os.environ.get("NO_COLOR"):
        return _MONO
    chosen = name or os.environ.get("LAIA_WIZARD_THEME") or "default"
    if chosen == "mono":
        return _MONO
    if chosen == "pastel":
        return _PASTEL
    return Theme()
```

Luego:

```
$ LAIA_WIZARD_THEME=pastel sudo laia-wizard
```

---

## Ajustar el banner ASCII

El banner está hardcoded en `components.py`:

```python
_BANNER_ART = r"""
 _      _    ___    _
| |    / \  |_ _|  / \
...
"""
```

Sustitúyelo por el que quieras (figlet / toilet / dibujo a mano). Mantén el
ancho ≤ 80 columnas si quieres compatibilidad con SSH default.

---

## Snapshots ASCII para tests

Si añades nuevos componentes y quieres tests snapshot, sigue el patrón de
`tests/wizard/test_ui_components.py`:

```python
def _capture(width: int = 80) -> tuple[Console, StringIO]:
    buf = StringIO()
    return Console(file=buf, width=width, no_color=True,
                   force_terminal=False), buf

def test_mi_widget():
    console, buf = _capture()
    comp.mi_widget(console, "foo")
    out = buf.getvalue()
    assert "foo" in out
    assert THEME.g_ok in out
```

Evita comparar contra fixtures byte-a-byte: la versión de `rich` se mueve
y eso te dará tests frágiles. Asserta sobre **tokens visibles**: textos,
glifos del tema, presencia de borde.

---

## Cómo el resto del código accede al tema

Importa el singleton:

```python
from laia_cli.install_wizard.ui.theme import THEME

console.print(f"[{THEME.success}]hecho[/]")
console.print(THEME.g_ok)
```

`THEME` es global. Si en tests cambias `$NO_COLOR` y quieres releer:

```python
from laia_cli.install_wizard.ui.theme import refresh_theme
refresh_theme()
```
