# Niveles de riesgo

| Nivel | Ejemplos | Comportamiento |
|-------|----------|----------------|
| `low` | Leer, buscar, crear archivos nuevos | Ejecuta automático |
| `medium` | Editar archivos existentes, instalar dependencias | Advierte y confirma si hay TTY |
| `high` | Borrar archivos, cambios con impacto grande | Approval requerido |
| `critical` | Acciones irreversibles o producción | Approval explícito y pausa |

## Guía de asignación

- Si solo crea archivos nuevos y es reversible: `low`
- Si modifica trabajo existente del usuario: `medium`
- Si elimina o altera sistema/proyecto de forma fuerte: `high`
- Si puede causar pérdida irreversible o tocar producción: `critical`
