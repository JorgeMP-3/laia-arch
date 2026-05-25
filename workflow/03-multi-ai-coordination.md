# Coordinación multi-IA

LAIA se desarrolla con varias IAs agénticas en paralelo (Claude Code, Codex, OpenCode,
Cursor, agentes propios). Este archivo explica cómo evitar que se pisen.

## Principios

1. **Una IA = una branch.** Ninguna trabaja en `main` directamente.
2. **Una tarea no-trivial = un plan en `workflow/plans/`.** Antes de tocar código, el
   plan existe en disco.
3. **Comunicación asíncrona vía archivos.** Nada de chat efímero — todo lo importante
   se escribe en `workflow/`.

## Convenciones

### Branches por agente

Patrón: `wip/<agente>/<tarea>`. Deja claro quién está haciendo qué.

### Locks suaves

Si vas a trabajar en un subsistema durante varios turnos, crea
`workflow/locks/<subsistema>.md` con:

```
owner: claude-2026-05-25T10:00Z
task: refactor agora-backend auth
expires: 2026-05-26T10:00Z
```

Otra IA que vea ese lock debe abstenerse de tocar ese subsistema hasta que expire o
el owner lo libere. No es atómico, es convención visible. Suficiente cuando la cadencia
es minutos, no milisegundos.

### Inbox para drafts

Si vas a proponer un cambio grande a `LAIA_ECOSYSTEM.md`, `workflow/*` o cualquier
archivo "vivo" donde el conflicto sea probable, deja primero el draft en
`workflow/_inbox/YYYY-MM-DD-<slug>.md`. Jorge o el scribe del día lo integra.

### Scribe rotativo

Una IA por sesión asume el rol de **scribe**: responsabilidad extra de mantener
`changelog.md`, `problems.md` y los planes al día. Las demás IAs dejan drafts en
`_inbox/` si afecta a archivos del scribe.

En la práctica: la primera IA que Jorge abre ese día es scribe.

## Handoff entre sesiones

Última acción de cualquier sesión: añadir una entrada en `workflow/changelog.md` con:

- Qué se hizo.
- Qué quedó abierto.
- Qué se descubrió que vale la pena saber mañana.

Esto sustituye la memoria privada de cada IA por una memoria compartida en git.
