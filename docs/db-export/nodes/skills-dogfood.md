# Dogfood QA Skill

## Metadata

- ID: `96`
- Slug: `skills-dogfood`
- Kind: `doc`
- Status: `active`
- Filename: `skills-dogfood.md`
- Parent: `hermes`
- Source kind: `manual`
- Created at: `2026-05-08T08:34:02.479935+00:00`
- Updated at: `2026-05-08T08:34:02.479935+00:00`
- Aliases: `skills-dogfood`

## Summary

Skill de testing exploratorio QA sistematico de aplicaciones web. Encuentra bugs, captura evidencia 

## Body

# Dogfood QA Skill

# Integrated Tools — Dogfood QA

## Resumen

Skill de testing exploratorio QA sistematico de aplicaciones web. Encuentra bugs, captura evidencia y genera reportes estructurados.

**Ubicacion:** `skills/dogfood/SKILL.md`

## Cuando usar

- El usuario pide hacer QA testing de una web
- Encontrar bugs, inconsistencias, problemas de UX
- Generar reportes de calidad

## Herramientas usadas

- `browser_navigate` — ir a URL
- `browser_snapshot` — snapshot del DOM (accessibility tree)
- `browser_click` — click por ref (`@eN`) o texto
- `browser_type` — escribir en input
- `browser_scroll` — scroll up/down
- `browser_back` — ir atras en historial
- `browser_press` — tecla de teclado
- `browser_vision` — screenshot + AI analysis; `annotate=true` para labels
- `browser_console` — output y errores de JS console

## Workflow de 5 fases

### Phase 1: Plan

1. Crear estructura de directorios:
```
{output_dir}/
├── screenshots/
└── report.md
```
2. Identificar scope de testing
3. Planear sitemap: landing, nav, flows, forms, edge cases

### Phase 2: Explore

Para cada pagina/feature:
1. `browser_navigate(url="...")`
2. `browser_snapshot()`
3. `browser_console(clear=true)`
4. `browser_vision(question="...", annotate=true)`
5. Test interactivo: click, type, scroll, keyboard
6. Despues de cada interaccion: `browser_console()` + `browser_vision()`

### Phase 3: Collect Evidence

Para cada bug:
1. `browser_vision(question="...", annotate=false)` — screenshot
2. Guardar `screenshot_path`
3. Registrar: URL, pasos, esperado, actual, console errors
4. Clasificar severidad: Critical / High / Medium / Low
5. Clasificar categoria: Functional / Visual / Accessibility / Console / UX / Content

### Phase 4: Categorize

1. De-duplicar bugs
2. Asignar severidad y categoria final
3. Ordenar: Critical primero
4. Contar por severidad y categoria

### Phase 5: Report

Generar desde plantilla `templates/dogfood-report-template.md`:

1. **Executive summary** — total, breakdown, scope
2. **Per-issue** — numero, titulo, badges, URL, descripcion, pasos, expected vs actual, screenshots, console errors
3. **Summary table**
4. **Testing notes**

Guardar en `{output_dir}/report.md`

## Taxonomy de issues

### Severidad

| Nivel | Descripcion |
|---|---|
| Critical | Bloquea funcionalidad core, data loss, security |
| High | Funcionalidad principal rota, workaround complicado |
| Medium | Funcionalidad secundaria rota, workaround facil |
| Low | Minor UI/UX, typo, contenido |

### Categorias

- Functional — boton no funciona, form no envia
- Visual — layout roto, colores mal
- Accessibility — contrast, keyboard nav, screen reader
- Console — JS errors en console
- UX — confuso, flow roto
- Content — texto incorrecto, falta info

## Tips importantes

- **Siempre** check `browser_console()` despues de navegar y cada interaccion significativa
- Usar `annotate=true` con `browser_vision` cuando necesites razonar sobre posiciones de elementos
- Testear con inputs validos E invalidos — validation bugs son comunes
- Scroll por paginas largas — content below the fold puede tener issues
- Testear edge cases: empty states, text largo, special chars, rapid clicking
- Para reportar screenshots: usar `MEDIA:<screenshot_path>` para enviar inline

## Output esperado

```
/dogfood https://example.com full-site ./dogfood-output
```

## Nodos relacionados

- `integrated-tools` — indice maestro
- `integrated-workspace-tools` — skills workspace


> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `hermes` (Hermes — Núcleo técnico) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Dogfood QA Skill

# Dogfood QA Skill

# Integrated Tools — Dogfood QA

## Resumen

Skill de testing exploratorio QA sistematico de aplicaciones web. Encuentra bugs, captura evidencia y genera reportes estructurados.

**Ubicacion:** `skills/dogfood/SKILL.md`

## Cuando usar

- El usuario pide hacer QA testing de una web
- Encontrar bugs, inconsistencias, problemas de UX
- Generar reportes de calidad

## Herramientas usadas

- `browser_navigate` — ir a URL
- `browser_snapshot` — snapshot del DOM (accessibility tree)
- `browser_click` — click por ref (`@eN`) o texto
- `browser_type` — escribir en input
- `browser_scroll` — scroll up/down
- `browser_back` — ir atras en historial
- `browser_press` — tecla de teclado
- `browser_vision` — screenshot + AI analysis; `annotate=true` para labels
- `browser_console` — output y errores de JS console

## Workflow de 5 fases

### Phase 1: Plan

1. Crear estructura de directorios:
```
{output_dir}/
├── screenshots/
└── report.md
```
2. Identificar scope de testing
3. Planear sitemap: landing, nav, flows, forms, edge cases

### Phase 2: Explore

Para cada pagina/feature:
1. `browser_navigate(url="...")`
2. `browser_snapshot()`
3. `browser_console(clear=true)`
4. `browser_vision(question="...", annotate=true)`
5. Test interactivo: click, type, scroll, keyboard
6. Despues de cada interaccion: `browser_console()` + `browser_vision()`

### Phase 3: Collect Evidence

Para cada bug:
1. `browser_vision(question="...", annotate=false)` — screenshot
2. Guardar `screenshot_path`
3. Registrar: URL, pasos, esperado, actual, console errors
4. Clasificar severidad: Critical / High / Medium / Low
5. Clasificar categoria: Functional / Visual / Accessibility / Console / UX / Content

### Phase 4: Categorize

1. De-duplicar bugs
2. Asignar severidad y categoria final
3. Ordenar: Critical primero
4. Contar por severidad y categoria

### Phase 5: Report

Generar desde plantilla `templates/dogfood-report-template.md`:

1. **Executive summary** — total, breakdown, scope
2. **Per-issue** — numero, titulo, badges, URL, descripcion, pasos, expected vs actual, screenshots, console errors
3. **Summary table**
4. **Testing notes**

Guardar en `{output_dir}/report.md`

## Taxonomy de issues

### Severidad

| Nivel | Descripcion |
|---|---|
| Critical | Bloquea funcionalidad core, data loss, security |
| High | Funcionalidad principal rota, workaround complicado |
| Medium | Funcionalidad secundaria rota, workaround facil |
| Low | Minor UI/UX, typo, contenido |

### Categorias

- Functional — boton no funciona, form no envia
- Visual — layout roto, colores mal
- Accessibility — contrast, keyboard nav, screen reader
- Console — JS errors en console
- UX — confuso, flow roto
- Content — texto incorrecto, falta info

## Tips importantes

- **Siempre** check `browser_console()` despues de navegar y cada interaccion significativa
- Usar `annotate=true` con `browser_vision` cuando necesites razonar sobre posiciones de elementos
- Testear con inputs validos E invalidos — validation bugs son comunes
- Scroll por paginas largas — content below the fold puede tener issues
- Testear edge cases: empty states, text largo, special chars, rapid clicking
- Para reportar screenshots: usar `MEDIA:<screenshot_path>` para enviar inline

## Output esperado

```
/dogfood https://example.com full-site ./dogfood-output
```

## Nodos relacionados

- `integrated-tools` — indice maestro
- `integrated-workspace-tools` — skills workspace


> 📅 Documentado: 2026-05-08
