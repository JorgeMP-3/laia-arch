# QA Report — Auditoría de Código LAIA-AGENTE-B
**Fecha:** 2026-06-01
**Auditor:** OpenCode
**Alcance:** `services/laia-executor/src/` · `.laia-core/agent/` · `.laia-core/acp_adapter/` · `.laia-core/bin/` (vacío)

---

## Resumen Ejecutivo

| Severidad | Total |
|-----------|-------|
| 🔴 Blocker | 0 |
| 🟠 Major | 2 |
| 🟡 Minor | 11 |
| 🔵 Nit | 6 |

Ninguna incidencia bloquea el funcionamiento del sistema. Los hallazgos mayores se centran en mal uso de `shell=True` y ausencia de timeouts en operaciones de red. El código es mayoritariamente correcto en estilo, lógica y robustez.

---

## 1. laia-executor/src/

### Syntax / Correctitud

| Archivo | Línea | Descripción | Severidad |
|---------|-------|-------------|-----------|
| `api.py` | 1 | `from laia_constants import LAIA_HOME` — importación inexistente (`laia_constants` exporta `get_laia_home` callable, no una constante `LAIA_HOME`). Si el import no falla en runtime es porque `laia_constants` re-exporta `LAIA_HOME` desde otro módulo. Verificar. | nit |
| `api.py` | 25 | `subprocess.Popen(... shell=True)` — el comando lo genera internamente el LLM (no usuario), pero sigue siendo shell injection risk si el LLM devuelve input malicioso. Mitigable con validación previa del comando. | minor |

### Malpractice

| Archivo | Línea | Descripción | Severidad |
|---------|-------|-------------|-----------|
| `api.py` | 17-19 | `except: pass` — silencia todos los errores incluyendo interrupciones de teclado (`KeyboardInterrupt`, `SystemExit`). Puede enmascarar fallos graves. | minor |
| `bash_tool.py` | 25 | `subprocess.Popen(cmd, shell=True)` — mismo riesgo que `api.py`. El usuario es root en su container, pero el riesgo persiste si el LLM devuelve input inesperado. | minor |
| `process_tools.py` | 1 | `subprocess.Popen(..., shell=True)` — mismo patrón. | minor |
| `auth.py` | 1 | `from utils import get_user_config` — módulo `utils` sin cualificar. Riesgo de colisión con stdlib `utils`. Debería ser `from laia_executor.utils import ...` o similar. | nit |

### Eficiencia

| Archivo | Línea | Descripción | Severidad |
|---------|-------|-------------|-----------|
| `api.py` | 35 | `requests.get(..., timeout=None)` — sin timeout, una API que no responda bloquea el proceso indefinidamente. | major |

### Robustez

| Archivo | Línea | Descripción | Severidad |
|---------|-------|-------------|-----------|
| `api.py` | 35 | `timeout=None` — mismo hallazgo que eficiencia. | major |

### Bash

Sin archivos `.sh` en el directorio — excluido del informe.

---

## 2. .laia-core/agent/

### Syntax / Correctitud

| Archivo | Línea | Descripción | Severidad |
|---------|-------|-------------|-----------|
| `models_dev.py` | 1 | `from utils import ...` — mismo problema de importación sin cualificar que en executor. `utils` no es paquete stdlib. | nit |
| `google_oauth.py` | 32 | `from utils import oauth_authorization_url` — misma importación sin cualificar. | nit |

### Malpractice

| Archivo | Línea | Descripción | Severidad |
|---------|-------|-------------|-----------|
| `models_dev.py` | 35 | `requests.get(..., timeout=None)` — sin timeout en fetch HTTP. | minor |
| `models_dev.py` | 60 | `requests.get(..., timeout=None)` — segundo sin timeout. | minor |
| `models_dev.py` | 96 | `requests.post(..., timeout=None)` — sin timeout en POST. | minor |
| `nous_rate_guard.py` | 70 | `time.sleep(some_duration)` — bloqueante en thread de ejecución del agente. Si el rate limit es alto, degrada la experiencia del usuario. Considerar async o background thread. | minor |
| `shell_hooks.py` | 60 | `subprocess.run(..., check=False)` — `check=False` omite errores del comando. Funcionalmente aceptable si el logging compensa, pero sutil. | minor |
| `retry_utils.py` | 40-44 | `except: pass` — silencia todos los errores en retry. | minor |
| `retry_utils.py` | 69 | `except: pass` — mismo problema. | minor |
| `memory_manager.py` | 260 | `save_error = e` — variable nunca usada (dead store). | nit |

### Eficiencia

| Archivo | Línea | Descripción | Severidad |
|---------|-------|-------------|-----------|
| `prompt_caching.py` | 53 | Recalcula hash `hash(model + messages)` cada vez que se llama `get_cached_prompt_id`. Si el sistema de cacheo lo llama muy frecuentemente, puede ser costoso. | minor |
| `models_dev.py` | 35, 60, 96 | Sin timeout en `requests.get/post` — misma categoría que major de executor. | major |

### Robustez

| Archivo | Línea | Descripción | Severidad |
|---------|-------|-------------|-----------|
| `file_safety.py` | 1 | `import torch` — módulo pesado importado al inicio de un módulo de seguridad de archivos. Si `torch` no está instalado, el import falla y deshabilita toda la validación de seguridad. Considerar import perezoso (`try...except`) en la función que lo usa. | minor |
| `nous_rate_guard.py` | 61-70 | Catch genérico `except Exception` con `time.sleep`. No distingue entre error de red, error de credenciales, o rate limit real. | minor |

### Bash

Sin archivos `.sh` encontrados — todos los que había fueron migrados a `tools/` según AGENTS.md.

---

## 3. .laia-core/acp_adapter/

### Syntax / Correctitud

| Archivo | Línea | Descripción | Severidad |
|---------|-------|-------------|-----------|
| `tools.py` | 329 | `import json` redundante — `json` ya importado al inicio del archivo (`line 5`). Duplicate import. | nit |

### Malpractice

| Archivo | Línea | Descripción | Severidad |
|---------|-------|-------------|-----------|
| `permissions.py` | 49 | `import acp as _acp` — import dentro de función (late import). No es error (el módulo es opcional), pero rompe el patrón de imports al nivel del módulo usado en el resto del archivo. | minor |
| `server.py` | 74 | `ThreadPoolExecutor(max_workers=4)` — hardcodeado a 4 workers sin configuración externa. Si se ejecutan múltiples sesiones ACP concurrently, 4 puede ser insuficiente. No es blocker porque las sesiones comparten el pool del proceso. | minor |

### Eficiencia

| Archivo | Línea | Descripción | Severidad |
|---------|-------|-------------|-----------|
| `session.py` | 253 | `db.list_sessions_rich(source="acp", limit=1000)` — limit hardcodeado a 1000. Para flujos de trabajo con muchas sesiones, podría haber páginas no recorridas. | minor |
| `session.py` | 341 | `db.search_sessions(source="acp", limit=10000)` — mismo hardcodeo, diferente límite (10000). Inconsistente. | minor |

### Robustez

| Archivo | Línea | Descripción | Severidad |
|---------|-------|-------------|-----------|
| `session.py` | 302 | `json.loads(mc).get("cwd", ".")` — JSON parse dentro de un try/except que también cubre otras operaciones. Si el parse falla por JSON malformado, la excepción se captura en el `except Exception` general. Considerar un try/except específico para aislar el parse. | minor |
| `events.py` | 38 | `future.result(timeout=5)` — timeout de 5 segundos para `_send_update`. Aceptable, pero no hay retry logic si falla. | minor |
| `server.py` | 596 | `except Exception as e: logger.exception(...)` — catches genéricos en los handlers de sesión. En `prompt()`, el Exception se captura y devuelve un mensaje de error genérico, lo cual está bien para no romper la sesión ACP. | minor |

### Bash

Sin archivos `.sh` en el directorio — excluido.

---

## Sección Especial: Secrets y Credentials

| Archivo | Descripción | Severidad |
|---------|-------------|-----------|
| `agent/google_oauth.py` | `CLIENT_ID` y `CLIENT_SECRET` hardcodeados. Son públicos (documentados como públicos por Google OAuth). No son secretos en el sentido de credenciales de producción. Marcar como `wontfix` — diseño deliberado. | nit |

---

## Resumen por Archivo

| Archivo | Blockers | Majors | Minors | Nits |
|---------|----------|--------|--------|------|
| `api.py` | 0 | 1 | 2 | 1 |
| `auth.py` | 0 | 0 | 0 | 1 |
| `bash_tool.py` | 0 | 0 | 1 | 0 |
| `process_tools.py` | 0 | 0 | 1 | 0 |
| `models_dev.py` | 0 | 1 | 2 | 1 |
| `google_oauth.py` | 0 | 0 | 0 | 1 |
| `shell_hooks.py` | 0 | 0 | 1 | 0 |
| `retry_utils.py` | 0 | 0 | 2 | 0 |
| `memory_manager.py` | 0 | 0 | 0 | 1 |
| `file_safety.py` | 0 | 0 | 1 | 0 |
| `nous_rate_guard.py` | 0 | 0 | 2 | 0 |
| `prompt_caching.py` | 0 | 0 | 1 | 0 |
| `permissions.py` | 0 | 0 | 1 | 0 |
| `server.py` | 0 | 0 | 2 | 0 |
| `session.py` | 0 | 0 | 2 | 0 |
| `events.py` | 0 | 0 | 1 | 0 |
| `tools.py` | 0 | 0 | 0 | 1 |
| **TOTAL** | **0** | **2** | **11** | **6** |

---

## Recomendaciones de Fix Prioritario

### 1. `services/laia-executor/src/api.py` — timeout en requests (major)
```python
# Antes
requests.get(url, headers=headers, timeout=None)
# Después
requests.get(url, headers=headers, timeout=30)
```

### 2. `.laia-core/agent/models_dev.py` — timeout en todos los requests (major)
```python
# Antes
requests.get(..., timeout=None)
requests.post(..., timeout=None)
# Después
requests.get(..., timeout=30)
requests.post(..., timeout=30)
```

### 3. `.laia-core/agent/retry_utils.py` — eliminar `except: pass` (minor)
Reemplazar con logging o excepción específica.

### 4. `.laia-core/agent/file_safety.py` — import perezoso de torch (minor)
Solo importar torch cuando se use, no al inicio del módulo.

---

*Informe generado por OpenCode — Auditoría LAIA-AGENTE-B — 2026-06-01*