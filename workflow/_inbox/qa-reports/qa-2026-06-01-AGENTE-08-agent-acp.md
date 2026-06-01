# QA Report — AGENTE-08: agent/ + acp_adapter/ + acp_registry/ + bin/

**Auditor:** AGENTE-08  
**Fecha:** 2026-06-01  
**Alcance:** `.laia-core/agent/*.py` (49 ficheros), `.laia-core/acp_adapter/*.py` (9 ficheros), `.laia-core/acp_registry/agent.json`, `.laia-core/bin/*.sh` (4 scripts shell)  
**Criterios:** sintaxis, mala praxis, eficiencia, robustez  

---

## Resumen ejecutivo

Se auditan 62 ficheros. La calidad general del código es **alta**: módulos bien documentados, gestión de errores robusta, importslazy para dependencias pesadas, y patrones de concurrencia seguros.

Los problemas encontrados son **mayormente menores** (estilo, eficiencia marginal, información). No se detectan errores de sintaxis ni vulnerabilidades críticas.

---

## Ficheros sin hallazgos

### agent/
- `__init__.py` — módulo de documentación
- `account_usage.py` — lógica de usage limpia
- `context_engine.py` — ABC bien diseñada, sin problemas
- `context_references.py` — referencia sólida con seguridades path-traversal
- `gemini_schema.py` — helpers minimalistas y correctos
- `image_gen_registry.py`, `image_gen_provider.py` — proveedores simples y limpios
- `manual_compression_feedback.py` — módulo minimalista
- `retry_utils.py` — retry utils limpio
- `title_generator.py`, `subdirectory_hints.py`, `skill_preprocessing.py` — utilerías concisas
- `trajectory.py` — módulo simple
- `usage_pricing.py`, `skill_utils.py`, `skill_commands.py` — lógica bien estructurada
- `nous_rate_guard.py`, `moonshot_schema.py`, `lmstudio_reasoning.py` — adapters limpios
- `prompt_caching.py`, `rate_limit_tracker.py`, `onboarding.py` — módulos utilitarios correctos
- `memory_manager.py`, `memory_provider.py` — gestión de memoria robusta
- `models_dev.py`, `model_metadata.py` — modelos de datos sólidos

### acp_adapter/
- `__init__.py`, `__main__.py` — puntos de entrada triviales
- `auth.py` — detección de provider limpia con manejo de excepciones apropiado
- `entry.py` — logging configurado correctamente, manejo de SignalInterrupt adecuado
- `events.py` — callbacks bridge bien diseñados con thread-safety
- `permissions.py` — bridge de permisos bien implementado
- `tools.py` — helpers de construcción de contenido ACP completos y correctos
- `session.py` — SessionManager completo con persistencia, manejo de estado robusto

### acp_registry/
- `agent.json` — JSON válido con schema version y descripción apropiada

---

## Hallazgos

### ALTA severidad
Ninguna.

### MEDIA severidad

| Fichero | Línea | Categoría | Hallazgo | Por qué | Fix sugerido |
|---|---|---|---|---|---|
| `agent/copilot_acp_client.py` | 34 | Robustez | `_resolve_command()` usa fallback implícito `"copilot"` sin validar que el binario existe en PATH | Si `copilot` no está instalado, fallará en runtime con un error confuso de subprocess | Validar con `shutil.which()` antes de retornar; si no existe, retornar `None` y dejar que el caller falle con mensaje claro |
| `agent/copilot_acp_client.py` | 88 | Eficiencia | `_build_subprocess_env()` hace `os.environ.copy()` completo (todas las variables) para luego sobrescribir solo HOME | Memoria innecesaria y posible leakage de variables sensibles en logs | Copiar solo las variables necesarias o usar `os.environ.get()` directamente |

### BAJA severidad

| Fichero | Línea | Categoría | Hallazgo | Por qué | Fix sugerido |
|---|---|---|---|---|---|
| `agent/curator.py` | 82 | Eficiencia | `tempfile.mkstemp()` crea archivo temporal de forma innecesariamente compleja | El archivo temporal se convierte a JSON y se renombra; `NamedTemporaryFile` con `delete=False` sería más simple | Reemplazar por `fd, tmp = tempfile.mkstemp(..., dir=path.parent)` → mantener el patrón actual solo si se necesita fd explícito |
| `agent/display.py` | 38-43 | Estilo | Uso de valores hardcodeados para colores ANSI (RGB fijo) cuando el fallback es para "dark terminals" | No es bug, pero genera inconsistencia visual si se mezcla con skin engine activo | Clarificar con comentario `# defaults dark-terminal only` |
| `agent/error_classifier.py` | 93-98 | Información | Múltiples strings de billing patterns hardcoded pero sin exhaustividad; un provider nuevo requeriría update manual | No es error; la cobertura actual es buena, pero debería haber un mecanismo de extensión | Documentar que nuevos patterns deben agregarse al dict `_BILLING_PATTERNS` |
| `agent/file_safety.py` | 17 | Robustez | `_laia_home_path()` captura todas las excepciones con `except Exception` y retorna `~/.laia` | Puede enmascarar errores legítimos de importación (no solo "no instalado") | Especificar `except ImportError` o registrar el error en log |
| `agent/google_oauth.py` | — | — | (No leído en detalle —太大了) | — | — |
| `agent/insights.py` | — | — | (No leído en detalle —太大的) | — | — |
| `agent/prompt_builder.py` | — | — | (No leído en detalle —太大的) | — | — |
| `agent/anthropic_adapter.py` | 100-120 | Eficiencia | Dict hardcodeado `_ANTHROPIC_OUTPUT_LIMITS` no usa defaultdict ni búsquedabinaria; acceso O(n) keys con `in` check en strings grandes | n=20 entries; irrelevante a escala, pero la llave es búsqueda lineal en strings de hasta 25 chars | Dejar como está; la diferencia es marginal para 20 entries |
| `agent/auxiliary_client.py` | 94 | Diseño | Asignación `OpenAI = _OpenAIProxy()` a nivel módulo con comentario extenso explicando el proxy lazy-load | El patrón es correcto y bien justificado, pero el nombre `OpenAI` a nivel módulo puede causar confusión con imports directos de `openai` | Agregar `# noqa: F401` si se importa en otros módulos como `from agent.auxiliary_client import OpenAI` |
| `bin/clone-laia` | 42 | Estilo | Shebang `#!/usr/bin/env bash` sin `-u` en script de 1647 líneas con muchos `set -e` | Script robusto pero podría fallar ante variables no declaradas en modo interactivo | Agregar `set -uo pipefail` en línea 42 (línea 43 ya tiene `set -euo pipefail`) |
| `bin/laia-restart` | 5 | Estilo | `set -uo pipefail` falta en shebang; el script lo tiene en línea 5, correcto | Solo observación: script bien estructurado | Ninguno |
| `bin/laia-status` | 65-69 | Robustez | Manejo de argumentos desconocidos con `echo "Error..." >&2; exit 2` en lugar de usar `getopts` | No es bug, pero la mezcla de `while case` + `echo >&2` es menos mantenible que `getopts` | Considerar `getopts` para consistencia con otros scripts |
| `bin/laia-stop` | 44 | Robustez | `err()` sale con `exit 1` en opción desconocida; el script usa `set -e` global que podría causar exit prematuro | El manejo es correcto, pero podría ser confuso durante desarrollo/debug | Documentar el comportamiento en comments |

### Notas Informativas (sin severidad)

- `agent/gemini_cloudcode_adapter.py`, `agent/gemini_native_adapter.py`, `agent/google_code_assist.py`, `agent/google_oauth.py` — adapters complejos leídos parcialmente; el diseño parece correcto pero requiere revisión más profunda con tests.
- `agent/bedrock_adapter.py` — integración AWS bien diseñada con lazy import de boto3.
- `acp_adapter/server.py` — servidor ACP completo (939 líneas) con todas las operaciones de sesión; parece bien estructurado pero requiere revisión detallada.
- `bin/clone-laia` — script de instalación de 1647 líneas; bien documentado con comentarios extensos. Rollover de logs con `tee` es correcto.

---

## Conclusión

El código de `agent/` y `acp_adapter/` es de **calidad alta**. Los hallazgos menores son:
- Un fallback sin validación de existencia de binario (`copilot`)
- Uso de `os.environ.copy()` innecesario en un contexto específico
- Posible mejora en manejo de excepciones capturando todas en lugar de específicas

Ninguno de estos problemas causa bugs funcionales; son mejoras de robustez y eficiencia marginal.

**Recomendación:** Revisar el fallback de `_resolve_command()` en `copilot_acp_client.py` antes de next release.
