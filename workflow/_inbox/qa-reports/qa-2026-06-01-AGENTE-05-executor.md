# QA Report — services/laia-executor/src
**Auditoría READ-ONLY** | Fecha: 2026-06-01 | Agente: AGENTE-05

---

## Resumen

| fichero | resultados |
|---|---|
| `__init__.py` | Sin hallazgos. |
| `__main__.py` | 1 hallazgo menor. |
| `api.py` | 2 hallazgos (1 media, 1 menor). |
| `auth.py` | Sin hallazgos. |
| `config.py` | Sin hallazgos. |
| `registry.py` | 1 hallazgo menor. |
| `bash_tool.py` | 1 hallazgo menor. |
| `cron_tools.py` | 2 hallazgos (1 alto, 1 medio). |
| `file_ops.py` | Sin hallazgos. |
| `private_workspace.py` | Sin hallazgos. |
| `process_tools.py` | Sin hallazgos. |
| `python_exec.py` | Sin hallazgos. |

**Total: 5 hallazgos** (1 alto, 2 medios, 2 menores).

---

## Detalle de hallazgos

---

### api.py

| fichero:línea | categoría | severidad | qué está mal | por qué | fix sugerido |
|---|---|---|---|---|---|
| `api.py:126` | EFICIENCIA | media | `p.iterdir()` se consume dos veces: en el `sorted()` y dentro del bucle. El key lambda llama `x.is_dir()` para cada entrada durante la comparación, lo que resulta en múltiples stat syscalls. | Para 1000 entradas se hacen ~2000 stat en vez de ~1000. Peor aún: `entry.is_dir()` se llama N log N veces durante el sort. | Materializar la lista primero con un list comprehension que precompute is_dir: `entries = [(e, e.is_dir()) for e in p.iterdir()]; entries.sort(key=lambda x: (not x[1], x[0].name))`. |
| `api.py:120` | MALA PRAXIS | menor | `Path(os.path.expanduser(path))` no limita el acceso al workspace del usuario. Un usuario podría pedir `path="/etc/passwd"` y获 access. | El endpoint `/workspace/files` es para exploración del workspace, pero no hay restricciones de sandboxing. Si la intención es que solo vea su `/home/user`, falta validación. | Validar que `p` esté dentro de `cfg.workspace_root` (que es `/var/lib/laia/workspace` por defecto). Usar `p.resolve().relative_to(workspace_root)` y capturar `ValueError` si no es un subpath. |

---

### __main__.py

| fichero:línea | categoría | severidad | qué está mal | por qué | fix sugerido |
|---|---|---|---|---|---|
| `__main__.py:17` | MALA PRAXIS | menor | `print(f"FATAL: {exc}", file=sys.stderr)` en vez de logging estructurado. | En producción es difícil filtrar/alertar sobre prints. Pero es aceptable para un error fatal de startup antes de que el logging esté configurado. | Considerar `logging.error(f"FATAL: {exc}")` o mantener print si es startup pre-config. No es crítico. |

---

### registry.py

| fichero:línea | categoría | severidad | qué está mal | por qué | fix sugerido |
|---|---|---|---|---|---|
| `registry.py:31` | EFICIENCIA | menor | `inspect.iscoroutinefunction` se evalúa en cada llamada a `call`. | No es cacheado; llamada en cada `/exec`. Para handlers síncronos registrados que nunca cambian de tipo, podría calcularse una vez en `register`. | Guardar en `_handlers` una tupla `(handler, is_coro)` en registro, o precomputar `is_coro` en `register` y almacenar ambos. |

---

### bash_tool.py

| fichero:línea | categoría | severidad | qué está mal | por qué | fix sugerido |
|---|---|---|---|---|---|
| `bash_tool.py:23-32` | ROBUSTEZ | menor | `shell=True` con `subprocess.run` captura stdout+stderr combinados. Si el comando produce binary output mixto con text, `text=True` (encoding utf-8) podría fallar en silencio en ciertos flujos. | El flag `text=True` usa errores de reemplazo, así que no crashea pero podría producir output corrupto displayed como Replacement character (). No es crítica para el caso de uso, pero worth noting. | Documentar la limitación o usar `subprocess.Popen` con `errors="replace"` explícito si binary mixed output es esperado. |

---

### cron_tools.py

| fichero:línea | categoría | severidad | qué está mal | por qué | fix sugerido |
|---|---|---|---|---|---|
| `cron_tools.py:149-152` | MALA PRAXIS | alto | `except Exception as exc: return ...` en write del unit file; luego líneas 156-169 hacen daemon-reload y enable sin validar que las escrituras fueron ok más allá de try/except. | Si `write_text` succeeds pero `daemon-reload` falla (línea 158), el código continúa a enable (línea 160). Si enable falla, hace rollback (líneas 163-168) pero el rollback usa `except Exception: pass` silencioso. State final de systemd unpredictible. | Añadir validación explícita después de cada escritura: `if not service_path.exists(): return error`. En rollback, no silenciar excepciones — al menos logearlas. |
| `cron_tools.py:212-226` | ROBUSTEZ | medio | Lectura de archivos `.timer` y `.service` con `except Exception: pass` silencia errores de permisos, archivos corruptos, symlinks rotos. El resultado puede ser información parcial o vacía que se retorna como válida. | Un archivo de unidad corrupto o sin permisos de lectura produciría schedule="", command="" sin feedback al usuario. | Reemplazar `except Exception: pass` con `except Exception as exc: description = f"<error: {exc}>"` para que al menos el output refleje el problema. Log también: `logger.warning("could not read %s: %s", tpath, exc)`. |

---

## Sin hallazgos (confirmado limpio)

- **`__init__.py`**: Trivial, solo version.
- **`auth.py`**: HMAC timing-safe comparison, validación correcta del header, código simple y correcto.
- **`config.py`**: Carga correcta con fallbacks, RuntimeError en token vacío (buen fail-fast), lectura de JSON con validation.
- **`file_ops.py`**: Límites de lectura, проверка существования файлов, обработка ошибок, нет mutable defaults, нет secret hardcoding.
- **`private_workspace.py`**: Lazy import con múltiples fallback paths, retry with exponential backoff para SQLite locks, threading locks correctamente usados, errores capturados y retornados como JSON.
- **`process_tools.py`**: Process group kill correcto, log file handle management, graceful degradation en `_tail_log`, `_resolve` con both name y PID lookup, no except:pass silenciosos en paths críticos.
- **`python_exec.py`**: Timeout capping correcto, output truncation preventiva para evitar OOM, fallback de CWD a `/tmp` si bind mount falta, subprocess spawn con timeout y proper error handling.

---

## Notas para el auditor posterior (no findings)

1. **`cron_tools.py:62-74`**: `_systemctl` usa `timeout=15` hardcodeado. Está bien — operations son locales y 15s es razonable para daemon-reload/enable. No es mágico number，因为它 es una constante con nombre (no se necesita extracción a config porque no hay escenario de override).

2. **`process_tools.py:265`**: `popen.wait(timeout=2)` tras SIGKILL es correcto — el proceso está guaranteed muerto por el kill, el wait es solo para recolectar el exit status. No es un timeout funcional.

3. **`api.py:54`**: El `pass` en el ValueError del content-length parsing es correcto — si el header está malformado, dejamos que downstream (FastAPI body parsing) maneje el error con un 422 o similar. No necesitamos responder 400 nosotros.
