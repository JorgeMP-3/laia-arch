# WORKHARD — Dashboard

```
╔══════════════════════════════════════════════════════════════╗
║                   🐧 WORKHARD STATUS                        ║
╚══════════════════════════════════════════════════════════════╝

  Proyecto:    [NOMBRE DEL PROYECTO]
  Fase:        [N/5]
  Estado:      [active|paused|complete|aborted]
  Modo:        [normal|super] · [single|dual]
  Siguiente:   Paso [N] — [descripción]

  Progreso:
  ═══════════════════════════════════════════════
  ✅ Completado:   [N]
  🔄 En curso:     [N]
  ⏳ Pendiente:   [N]
  ⏸ Pausado:     [N]
  ❌ Error:       [N]
  ═══════════════════════════════════════════════

  Última acción:
  [timestamp] — [fase] — [acción] — [resultado]

  ───────────────────────────────────────────────
  Rout:
    /workhard status   → estado actual
    /workhard resume   → continuar proyecto
    /workhard log      → historial de acciones
    /workhard abort    → cancelar proyecto
  ───────────────────────────────────────────────

  Archivos del proyecto:
    SESSION.md   → configuración y estado
    TODO.md      → pasos y contrato
    LOG.md       → historial
    CONTEXTO.md  → objetivo y alcance

  Skill: ~/.openclaw/skills/workhard/
  Work:  ~/.openclaw/workspace/workhard/WORK/[proyecto]/
```

## Cómo actualizar este dashboard

```bash
# Ver estado actualizado
~/.openclaw/skills/workhard/scripts/status.sh

# Generar dashboard desde script
cat ~/.openclaw/skills/workhard/scripts/detect.sh | bash

# Ver proyecto activo
cat ~/.openclaw/workspace/workhard/CURRENT_PROJECT
```
