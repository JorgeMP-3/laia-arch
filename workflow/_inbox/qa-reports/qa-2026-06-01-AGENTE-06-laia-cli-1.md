# QA Report: .laia-core/laia_cli (primera mitad alfabética)

**Agente:** AGENTE-06  
**Fecha:** 2026-06-01  
**Ficheros auditados (14):** `auth.py`, `auth_commands.py`, `azure_detect.py`, `backup.py`, `banner.py`, `browser_connect.py`, `callbacks.py`, `claw.py`, `cli_output.py`, `clipboard.py`, `codex_models.py`, `colors.py`, `commands.py`, `completion.py`

---

## Resumen ejecutivo

No se encontraron errores de **SINTAXIS** (typos, imports inexistentes, código inalcanzable tras return, paréntesis sin cerrar).

Se encontraron varios patrones de **MALA PRAXIS** y algunas observaciones de **ROBUSTEZ/EFICIENCIA** que se detallan abajo.

---

## Hallazgos

### alta severidad

| fichero:línea | categoría | severidad | qué está mal | por qué | fix sugerido |
|---|---|---|---|---|---|
| `backup.py:142` | MALA PRAXIS | alta | Uso de `Path.home()` en lugar de `get_laia_home()` para el path por defecto del backup | Cuando un usuario tiene un perfil activo, `laia backup` guarda el zip en `~/laia-backup-{stamp}.zip` (home del SO) en lugar de dentro del `LAIA_HOME` del perfil activo. Esto rompe la encapsulación de perfiles — si el usuario tiene perfil "work" y hace backup sin `--output`, el archivo queda en ~/ en lugar de en ~/.laia/profiles/work/ o similar. | Cambiar `Path.home()` por `get_laia_home()` y Documentar que `--output` es el mecanismo para especificar ubicaciones externas. |

---

### media severidad

| fichero:línea | categoría | severidad | qué está mal | por qué | fix sugerido |
|---|---|---|---|---|---|
| `banner.py:134` | MALA PRAXIS | media | Asunción hardcoded de estructura de repo: `laia_home / "laia-agent"` | El código asume que el repo está instalado como submódulo/git checkout dentro de `~/.laia/laia-agent`. En instalaciones de desarrollo (clone directo del repo en otra ubicación) o cuando `LAIA_HOME` apunta a un perfil, esto puede devolver un path que no existe o no es un git repo. El fallback (línea 139) lo corrige, pero el path por defecto es incorrecto para configuraciones comunes de desarrollo. | Usar `get_laia_home()` consistentemente y detectar la ubicación real del checkout desde el propio `.laia-core/` (el directorio donde vive el código). O documentar que `laia-agent` debe estar instalado dentro de `LAIA_HOME` como `laia-agent/`. |
| `banner.py:582` | EFICIENCIA | media | Llamada a `shutil.get_terminal_size()` en el hot path de construcción del banner | `build_welcome_banner()` se llama en cada inicio de sesión. `shutil.get_terminal_size()` consulta el terminal real en cada invocación, lo cual es una syscall innecesaria cuando el resultado podría cachearse o pasarse como parámetro. | Cachear el ancho del terminal en un módulo-level lazy global o recibirlo como parámetro de `build_welcome_banner()`. |
| `azure_detect.py:45-48` | MALA PRAXIS | media | Números mágicos en API version fallback | `_AZURE_OPENAI_PROBE_API_VERSIONS = ("2025-04-01-preview", "2024-10-21")` — magic numbers sin explicación de por qué se prueban именно эти versiones. Si Azure cambia las versiones soportadas, este código queda obsoleto sin notificación. | Extraer a constantes con comentario解释了 qué representa cada versión (GA vs preview). O hacer que el probe sea dinámico (solo fallback cuando el request sin api-version falla). |
| `auth.py:744-755` | ROBUSTEZ | media | Protección PYTEST_CURRENT_TEST con lógica compleja | El código lanza `RuntimeError` cuando detecta que está corriendo en un test que involuntariamente apunta al auth store real del usuario. La lógica de resolución de paths (líneas 744-755) tiene many edge cases (`strict=False`, try/except/finally) que podrían fallar de formas inesperadas en producción. | Considerar simplificar: si `PYTEST_CURRENT_TEST` está set, exigir `LAIA_HOME` override siempre (fail-fast en vez de la resolución actual). Documentar la restricción para los desarrolladores. |

---

### baja severidad / observaciones

| fichero:línea | categoría | severidad | qué está mal | por qué | fix sugerido |
|---|---|---|---|---|---|
| `auth_commands.py:204` | MALA PRAXIS | baja | `print()` en lugar de `logger.info()` para output de comando | Cuando se añade una credencial exitosamente (`print(f'Added {provider} credential...')`) se usa `print()` en vez del sistema de logging. Esto significa que en contextos donde la salida está silenciada o redirigida (scripts, CI), no queda registro. | Reemplazar `print()` por `logger.info()` o un уровень de log específico para CLI feedback. |
| `clipboard.py:207` | MALA PRAXIS | baja | `b64_data` puede ser string vacía y se intenta decodificar | En `_write_base64_image`, si `b64_data` es `""` (línea 234-235 del flujo), `base64.b64decode("", validate=True)` retorna `b""` vacío, y `dest.write_bytes(b"")` crea un archivo vacío de 0 bytes. El check `dest.exists() and dest.stat().st_size > 0` en línea 209 lo detecta, pero el archivo vacío se crea antes de borrar. En sistemas con quotas o disco lleno, esto puede fallar silenciosamente. | early return si `b64_data` está vacío antes de intentar decodificar/escribir. |
| `commands.py:1241` | EFICIENCIA | baja | `subprocess.TimeoutExpired` importado pero no usado | El import `subprocess.TimeoutExpired` está en el scope pero no se referencia en el código visible del archivo (línea 1241 `except (subprocess.TimeoutExpired, OSError):` — aunque este es de la sección de completado de archivos donde sí se usa). Verificado: se usa en línea 1241. Marcar como OK. | — (no issue) |
| `browser_connect.py:95-100` | MALA PRAXIS | baja | Lógica de fallback con hardcoded paths para Chrome | `get_chrome_debug_candidates` prueba ejecutables en un orden fijo. En Linux, si el primer candidato (`google-chrome`) no existe, pasa al siguiente sin considerar si el usuario tiene otro browser como Brave configurado como default. El usuario podría preferir Brave pero el código probará Chrome primero. | Considerar usar `shutil.which()` para detectar el browser por defecto del sistema antes de probar la lista hardcodeada. |
| `auth.py:2803-2804` | MALA PRAXIS | baja | Expresión ternaria redundante | `timeout = httpx.Timeout(timeout_seconds if timeout_seconds else 15.0)` — si `timeout_seconds` es `0.0` (falsy), el fallback es 15.0, pero si es `0.0` el efecto es el mismo. Peor: si alguien pasa `0.0` intencionalmente para "sin timeout", el código lo convierte a 15.0 silenciosamente. | Usar `timeout_seconds if timeout_seconds is not None else 15.0` para manejar `None` vs `0` explícitamente. |
| `banner.py:533-546` | ROBUSTEZ | baja | Try/except/pass en 获取 perfil activo | En `build_welcome_banner` se hace try/except/pass para obtener el nombre del perfil activo, para no romper el banner si `profiles.py` falla. El except esmuy amplio (`except Exception`) y el pass silencia cualquier error, incluyendo errores de import, bugs en `get_active_profile_name()`, etc. No hay logging. | Añadir `logger.debug()` o `logger.warning()` en el except para que problemas reales no queden invisibles. |
| `claw.py:627` | MALA PRAXIS | baja | List comprehension con `and` mixto en comprensión de filtro | Línea 627: `and any((d / name).exists() for name in ("todo.json", "SOUL.md", "MEMORY.md", "USER.md"))` — mezcla `d.is_dir()` con la condición `any()` en una list comprehension que ya tiene `d.is_dir() and not d.name.startswith(".")`. Funciona, pero es difícil de leer. | Extraer la condición `any(...)` a una helper function con nombre descriptivo. |

---

## Ficheros sin hallazgos

- **`colors.py`**: Código mínimo y limpio (38 líneas). Sin issues.
- **`completion.py`**: Lógica de shell completion bien隔离ada. Sin issues.
- **`callbacks.py`**: Interfaz de callbacks para terminal_tool. Ligeramente frágil (muchos `hasattr` checks), pero funciona y es idiomático para código que要和 prompt_toolkit y CLI state interop.
- **`cli_output.py`**: Helper puro de display. Sin issues.
- **`codex_models.py`**: Lógica de descubrimiento de modelos Codex. Sin issues significativos.
- **`azure_detect.py`**: Visión general sólida — error handling defensivo, timeouts correctos, sin except:pass silencioso en paths críticos.

---

## Conclusión

El código es de calidad general alta. Los problemas encontrados son de severity baja a media excepto `backup.py:142` que es un bug de encapsulación de perfiles. El resto son oportunidades de mejora, no defectos críticos.

**Recomendación:** Priorizar la corrección de `backup.py:142` y la mejora de `banner.py:134`. El resto pueden abordarse en siguientes iteraciones.

