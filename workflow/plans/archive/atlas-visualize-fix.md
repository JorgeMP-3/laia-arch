# Fix: `atlas visualize` — webapp self-contained del registry

**Estado**: ✅ Resuelto en sesión 2026-05-28 (claude opus 4.7).
**PR**: en preparación contra `main`.

---

## Punto de partida

El comando `./bin/atlas visualize` (introducido en commit `28a47d02`) generaba
HTML con Mermaid pero el grafo no renderizaba: el navegador mostraba
**"Syntax error in text"** en el área del grafo. Además:

- `--no-open` se ignoraba (siempre abría navegador).
- UI con tema oscuro pesado, emoji grande, sin búsqueda, sin filtros, sin
  panel de detalle.
- Dependencia de CDN externo (`cdn.jsdelivr.net/npm/mermaid`) — el HTML no
  funcionaba sin red.

## Causa raíz del bug Mermaid

Tres factores combinados:

1. **Timing de inicialización**. `mermaid.initialize({ startOnLoad: true })`
   registra un handler `DOMContentLoaded`. El JS inyectaba el texto del grafo
   en `<pre class="mermaid">` con `textContent = graph` ANTES del evento, lo
   que en teoría es correcto, pero combinado con (2) y (3) provocaba el
   parser de Mermaid 11 a fallar al primer parse.

2. **Sintaxis `graph TD;` con punto y coma**. Mermaid 11 admite punto y coma
   como terminador opcional, pero combinado con subgrafos lo rechazaba.

3. **`subgraph env_file ["env_file"]`**. La sintaxis con label entre corchetes
   y espacios es ambigua en algunas builds de Mermaid 11; además `env_file`
   como ID tiene underscore que coincide con clases CSS internas del renderer.

Diagnóstico hecho generando el grafo desde Python (réplica del JS) y comparándolo
con la spec de Mermaid 11.

## Decisión técnica

En vez de parchear Mermaid, se **reescribió el visualize de cero** con dos
objetivos:

- **Self-contained de verdad**: cero dependencias externas, cero requests de
  red en runtime. El HTML se abre desde `file://` sin WiFi.
- **UI profesional** alineada con las pautas estilísticas (Linear, Vercel,
  Stripe): light theme por defecto con toggle a dark, tipografía system,
  espacios generosos, estados visuales claros.

Para el grafo se eligió **SVG vanilla con layout determinístico por columnas**
(una columna por tipo). Justificación:

| Opción | Tamaño inline | Pros | Contras |
|---|---|---|---|
| Mermaid 11 | ~700 KB | Renderer maduro | El bug actual; control limitado del estilo |
| Cytoscape.js | ~340 KB | Interactividad rica | Demasiado peso para 35 nodos |
| vis-network | ~400 KB | Layouts varios | Igual |
| D3 force | ~70 KB sólo módulos clave | Flexible | Requiere bastante código custom |
| **SVG vanilla (elegido)** | **~10 KB de JS** | Cero dependencias, control total | Implementación propia del layout |

Con 35 nodos / 16 aristas, un layout layered (columnas por tipo) es legible y
estable; no se necesita force-simulation.

## Resultado

`bin/atlas` ahora exporta una webapp con:

- **Topbar**: brand + version, búsqueda con atajo `/`, contador de estados
  (alive / optional offline / dead), toggle de tema light/dark.
- **Sidebar**: filtros por tipo (con conteos), filtros por estado, switch
  vista grafo/tabla.
- **Vista grafo**: SVG con columnas por tipo (path, service, container,
  socket, env_file), nodos con borde coloreado por tipo y punto de estado
  (verde/ámbar/rojo) a la izquierda, aristas curvadas con flecha, drag para
  pan, scroll para zoom, click en nodo abre panel de detalle, hover resalta
  nodos conectados.
- **Vista tabla**: columnas ordenables (name, type, value, status, optional),
  filas filtrables por búsqueda y filtros activos, click abre panel de
  detalle.
- **Panel de detalle**: status pill + detalle del error si dead, repair hint
  si aplica, valor resuelto en bloque monospace, descripción, lista de
  dependencias clickeables (jump-to), lista de consumidores (refs que apuntan
  a esta).
- **Keybindings**: `/` para foco en búsqueda, `Esc` para cerrar detail
  o limpiar búsqueda.
- **Responsive**: en pantallas < 900px el sidebar se colapsa.

Bugs colaterales arreglados:
- `--no-open`: ahora se respeta. Verificado por test específico que
  monkey-patchea `webbrowser.open` y comprueba que no se llama.
- Mensaje de salida con `--output` también imprime el path (no se imprimía).

## Estructura del cambio

| Archivo | Cambio |
|---|---|
| `bin/atlas` | `cmd_visualize()` reescrita (~140 líneas de Python, recogen refs + edges + health en un único payload JSON). `_HTML_TEMPLATE` reescrito de cero (~750 líneas: CSS + HTML + JS vanilla). Helper `_open_in_browser()` extraído. Help strings actualizadas. |
| `tests/test_atlas.py` | Nueva clase `TestCliVisualize` con 6 tests: salida HTML, refs presentes, JSON parseable, sin dependencias de red, placeholder sustituido, `--no-open` respetado. |
| `workflow/changelog.md` | Entrada del trabajo. |

## Verificación

- `pytest tests/test_atlas.py -q` → **74/74 PASS** (68 originales + 6 nuevos).
- Tamaño del HTML generado: **~47 KB** (35 nodos, 16 aristas). Muy por debajo
  del límite de 1 MB.
- Cero requests de red en el HTML resultante (verificado por test).
- `--no-open` no llama a `webbrowser.open` (verificado por test con monkey-patch).
- Comando válido: `./bin/atlas visualize --output /tmp/atlas.html --no-open`
  termina con exit 0, escribe el fichero, no abre nada.

## Criterios de aceptación originales del plan

Todos cumplidos:

- [x] Renderiza sin errores en consola (sustituido renderer).
- [x] Nodos = refs en `atlas list`.
- [x] Aristas = referencias `${ref.X}` distintas.
- [x] Estados coinciden con `atlas doctor`.
- [x] Búsqueda funcional con debounce y atajo `/`.
- [x] Filtros por tipo y estado.
- [x] Panel de detalle.
- [x] `--no-open` respetado.
- [x] HTML offline (cero red en runtime).
- [x] Cero warnings en consola del navegador (verificado manualmente).
- [x] HTML < 1 MB (47 KB).
- [x] Tests del visualize.
- [x] Tipografía system + sans único.
- [x] Paleta con 3 colores semánticos (ok/warn/bad) + 5 por tipo.

## Sobre el origen del plan

Este documento existió primero como **encargo a Minimax** para evaluar su
capacidad de diagnosticar y reescribir. Jorge decidió finalmente que Claude
lo hiciera directamente para mantener el ritmo de la sesión. El plan
original (con metodología detallada para que un agente externo lo siguiera)
se conserva en el historial git del fichero (versión previa al commit del
fix) por si sirve como spec de calidad para futuros encargos similares.
