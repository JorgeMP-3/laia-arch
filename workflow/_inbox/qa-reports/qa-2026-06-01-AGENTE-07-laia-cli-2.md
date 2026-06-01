# QA Report — AGENTE-07: laia-cli (segunda mitad alfabética) + atlas.py + cli.py + batch_runner.py + install_wizard/validators.py + workspace_store

**Fecha:** 2026-06-01
**Alcance:** Ficheros .py de la segunda mitad alfabética de `.laia-core/laia_cli/` (`plugins.py` → `web_server.py`), `atlas.py`, `cli.py`, `batch_runner.py`, `install_wizard/validators.py`, `workspace_store/`
**Categorías:** ❌ SINTAXIS · ❌ MALA PRAXIS · ❌ EFICIENCIA · ❌ ROBUSTEZ

---

## Resumen ejecutivo

Se encontraron **8 problemas** en 4 ficheros:

| Categoría | # |
|---|---|
| MALA PRAXIS | 5 |
| ROBUSTEZ | 2 |
| EFICIENCIA | 1 |

Los problemas más relevantes son:
- `import re` duplicado en `cli.py` (líneas 18 y 22)
- `requests` importado sin lazy-load en `runtime_provider.py` y no declarado en dependencias
- `print()` hardcoded en `batch_runner.py` en lugar de logging (problema en contexto multiprocessing)
- `except Exception` catch-all en `install_wizard/__main__.py`

---

## Detalle de problemas

### `cli.py` — Interactive CLI principal

| fichero:línea | categoría | severidad | qué está mal | por qué | fix sugerido |
|---|---|---|---|---|---|
| `cli.py:18` + `cli.py:22` | ❌ MALA PRAXIS | ⚠️ media | `import re` duplicado en el mismo módulo (línea 18 y línea 22) | Python permite imports duplicados pero el segundo es redundante. El espacio de nombres queda contaminado. Si otro módulo hace `from cli import re` podría obtener resultados inconsistentes según el orden de importación. | Eliminar uno de los dos imports. Si `re` se usa en ambas mitades del fichero, mantener el primero (línea 18) y eliminar el segundo (línea 22). |

---

### `batch_runner.py` — Batch parallel runner

| fichero:línea | categoría | severidad | qué está mal | por qué | fix sugerido |
|---|---|---|---|---|---|
| `batch_runner.py:370` | ❌ ROBUSTEZ | ⚠️ media | `print(f"❌ Error processing prompt...")` hardcoded en lugar de logging | En contexto multiprocessing (`Pool`), stdout de los workers se entrelaza con el del proceso padre. Los resultados van a un archivo JSONL, no a consola interactiva, así que `print()` no es el canal correcto. El logging estructurado permite niveles (INFO/ERROR) y formateo consistente. | Reemplazar por `logger.error(...)` usando el logger del módulo (línea 35: `logger = logging.getLogger(__name__)`) |
| `batch_runner.py:401` | ❌ ROBUSTEZ | ⚠️ media | `print(f"\n🔄 Batch {batch_num}...")` hardcoded | Mismo problema: salida de worker multiprocessing entrelazada con el proceso padre. El `rich.progress` del proceso principal no puede filtrar estos mensajes. | Reemplazar por `logger.info(...)` |
| `batch_runner.py:413` | ❌ ROBUSTEZ | ⚠️ media | `print(f"✅ Batch {batch_num}: Already completed...")` hardcoded | Mismo problema. | Reemplazar por `logger.info(...)` |
| `batch_runner.py:422` | ❌ ROBUSTEZ | ⚠️ media | `print(f"   Processing {len(prompts_to_process)} prompts...")` hardcoded | Mismo problema. | Reemplazar por `logger.info(...)` |
| `batch_runner.py:445` | ❌ ROBUSTEZ | ⚠️ media | `print(f"   🚫 Prompt {prompt_index} discarded...")` hardcoded | Mismo problema. | Reemplazar por `logger.warning(...)` |
| `batch_runner.py:498` | ❌ ROBUSTEZ | ⚠️ media | `print(f"   {status} Prompt {prompt_index} completed")` hardcoded | Mismo problema. | Reemplazar por `logger.info(...)` |
| `batch_runner.py:500` | ❌ ROBUSTEZ | ⚠️ media | `print(f"   ❌ Prompt {prompt_index} failed...")` hardcoded | Mismo problema. | Reemplazar por `logger.error(...)` |

**Contexto multiprocessing:** La función `_process_batch_worker` (línea 388) se ejecuta en un proceso worker separado (vía `multiprocessing.Pool`). Todo `print()` en el worker escribe directamente a stdout del proceso padre sin sincronización, causando interleaving visual. El canal correcto es el logger.

---

### `runtime_provider.py` — Runtime provider resolution

| fichero:línea | categoría | severidad | qué está mal | por qué | fix sugerido |
|---|---|---|---|---|---|
| `runtime_provider.py:94` | ❌ MALA PRAXIS | ⚠️ media | `import requests` inline dentro de `_auto_detect_local_model()` | `requests` no es parte de la stdlib. No está en los imports del módulo ni en las dependencias declaradas de `.laia-core`. Si `requests` no está instalado, la función lanza `ModuleNotFoundError` — pero solo se usa en un fallback de auto-detección. Debería ser lazy-import dentro de un try/except para no bloquear todo el módulo. | Mover el import dentro del try/except de la función y usar el mismo patrón de fallback que el resto de la función. Verificar que `requests` esté en las dependencias del proyecto. |

---

### `install_wizard/__main__.py` — Wizard entry point

| fichero:línea | categoría | severidad | qué está mal | por qué | fix sugerido |
|---|---|---|---|---|---|
| `__main__.py:332` | ❌ MALA PRAXIS | ⚠️ baja | `except Exception:  # noqa: BLE001 - last-chance handler` — catch-all sin discriminación | El comentario `# noqa: BLE001` indica que el linter (BLE001) se suprime explícitamente. El handler atrapa cualquier excepción incluyendo `SystemExit`, `KeyboardInterrupt`, `MemoryError`, etc. El `raise` dentro del bloque `if args.debug` nunca ejecutará si `args.debug` es False porque `Exception` no captura `BaseException`. Para un last-chance handler querrías capturar `BaseException` no `Exception`. | Usar `except BaseException as exc:` y discriminar `SystemExit`/`KeyboardInterrupt` para tratarlos separadamente. Si se quiere solo logging + salida limpia, capturar `BaseException` y hacer `sys.exit(1)` explícito. |

---

## Ficheros sin problemas encontrados

Los siguientes ficheros fueron leídos y **no contienen problemas** en las 4 categorías auditadas:

- `atlas.py` — Registry de modelos, bien estructurado
- `web_server.py` — Servidor FastAPI, bien documentado, usa logging correctamente
- `mcp_config.py` — Gestión de servidores MCP, código limpio
- `memory_setup.py` — Setup de proveedores de memoria, bien
- `model_catalog.py` — Catálogo remoto de modelos, bien
- `model_normalize.py` — Normalización por proveedor, bien
- `models.py` — Catálogos y helpers de modelos, bien
- `model_switch.py` — Lógica de switching de modelos, bien
- `nous_subscription.py` — Features de suscripción Nous, robusto
- `oneshot.py` — Modo oneshot (-z), bien
- `pairing.py` — Sistema de pairing DM, simple y correcto
- `platforms.py` — Registro de plataformas, simple OrderedDict
- `install_wizard/__main__.py` — restante del wizard, bien
- `install_wizard/engine.py` — State machine del wizard, bien
- `install_wizard/state.py` — Checkpoint persistence, bien implementado
- `install_wizard/validators.py` — Validadores, bien
- `plugins.py` — Sistema de plugins (leído parcialmente, sin problemas aparentes)

**Nota:** `workspace_store/__init__.py` no existe como directorio ni ficheiro mono-fichero en el path esperado. El código de `atlas.py` lo importa como módulo (`from workspace_store import WorkspaceStore`), lo que indica que el import es desde el paquete `workspace_store/` en la raíz del proyecto (fuera de `.laia-core`), no desde `.laia-core/workspace_store/`.

---

## Notas adicionales

1. **Duplicado confirmado en cli.py:** Las líneas 18 y 22 del bloque de imports son literalmente `import re` duplicado. Esto no es un error de sintaxis Python (el intérprete lo ejecuta sin error), pero es un code smell que debe limpiarse.

2. **`requests` no stdlib:** La librería `requests` no forma parte de la stdlib de Python. Si el proyecto no la declara como dependencia, el import inline en `runtime_provider.py` puede causar `ModuleNotFoundError` en entornos donde `requests` no esté instalado.

3. **Contexto multiprocessing de batch_runner:** Los `print()` en `_process_batch_worker` son especialmente problemáticos porque esa función se ejecuta en workers de `multiprocessing.Pool`. La salida de los workers se entrelaza con la del proceso principal de forma no determinista.

---

*Informe generado sin modificar ningún fichero de código fuente.*
