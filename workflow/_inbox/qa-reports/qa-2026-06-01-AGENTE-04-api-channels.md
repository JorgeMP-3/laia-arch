# QA Report — AGENTE-04: API / canales
## Área: services/agora-backend/app

Ficheros auditados: `main.py`, `websocket.py`, `webhooks.py`, `marketplace.py`, `admin.py`, `metrics.py`, `monitor.py`, `telegram_gateway.py`, `telegram_links.py`

---

##hallazgos

| fichero:línea | categoría | severidad | qué está mal | por qué | fix sugerido |
|---|---|---|---|---|---|
| monitor.py:74 | EFICIENCIA / ROBUSTEZ | ALTA | `if not True: continue` tras el bucle `for a in agents_list` hace que todo el código de monitorización de agentes sea inalcanzable. El bucle itera sobre la lista pero luego salta siempre a la siguiente iteración sin procesar ningún agente. | Código muerto: la condición `not True` es una constante `False`, por lo que `continue` se ejecuta en cada iteración. Las alertas de estado de agentes, la llamada a `queue_broadcast`, el `record_event` y la actualización de `_prev_states` nunca se ejecutan. El monitor no detecta caidas ni recuperaciones de agentes. | Eliminar la línea 74 (`if not True: continue`) y la línea 75 (`continue`). Si había intención de saltarse ciertos agentes, usar una condición real (ej. filtrar por estado o configuración). |
| monitor.py:52 | ROBUSTEZ | MEDIA | El bloque `except Exception as exc` dentro del bucle `_loop` come el error y continúa. Si `run_check` falla una vez, el error se loggea pero no se propaga. | Si `run_check` falla críticamente (ej. base de datos no accesible), el error se manifiesta solo como un log. El monitor sigue corriendo con datos potencialmente stale. No hay backoff ni señal de alarma al operador. | En el `except` de `_loop`, considerar marcar el sistema como degraded o incrementar un contador de errores consecutivos que active una alerta si supera un umbral. |
| admin.py:1128-1131 | EFICIENCIA | MEDIA | Bucle O(n²): para cada usuario se itera `reversed(store.events())` hasta encontrar el último evento de chat. | `store.events()` devuelve la lista completa de eventos en memoria. Si hay E eventos y U usuarios, en el peor caso se hacen O(U·E) comparaciones. Con 100 usuarios y 10.000 eventos → 1.000.000 iteraciones. | Añadir un índice en la tabla events por `actor_id` o un método `store.last_chat_for_user(user_id)` que haga la query directamente con `ORDER BY created_at DESC LIMIT 1`. |
| admin.py:249-259 | EFICIENCIA | BAJA | `_tail_file` lee el fichero completo con `read_text()` y luego hace `.splitlines()` para quedarse solo con las últimas `lines`. | Con ficheiros grandes ( logs de producción ), se allocata memoria innecesaria. No es streaming. | Usar un approach de líneas desde el final: abrir en modo "rb", seek al final, leer bloques backwards hasta tener suficientes líneas. O usar `Path(...).open().readlines()` que ya retorna lista, pero sigue siendo completo. Alternativa: `tail -n <lines>` via subprocess si está disponible. |
| admin.py:296 | MALA PRAXIS | BAJA | `if os.environ.get("AGORA_ADMIN_JOBS_INLINE") == "1":` ejecuta `runner()` síncronamente en el thread que maneja la request. Para jobs largos (provisioning, rebuild) esto bloquea el worker de uvicorn. | El intent es claramente para tests, pero el flag es un string comparison sobre env var. Si el job tarda 15 min, la conexión HTTP se mantiene abierta. | Documentar que este flag es SOLO para tests. Alternativamente, devolver 202 inmediatamente y dejar que el job corra en background aunque para inline=1. |
| main.py:327, 1054 | MALA PRAXIS | BAJA | `import subprocess` dentro de funciones (`change_password`, `list_my_agent_tasks`) cuando ya está importado al nivel del módulo (línea 6). | Duplicación de imports en el scope local. No causa errores pero es ruido. | Eliminar los imports locales de `subprocess` en esas funciones. |

---

## Ficheros sin hallazgos

- **websocket.py** — Código limpio. Lock por thread, gestión de conexiones, broadcast. Sin problemas.
- **webhooks.py** — HMAC correcto, validación de tamaño de payload (64KB), manejo de errores, uso de logging. Sin problemas.
- **marketplace.py** — Estructura limpia, validación de inputs, errores mapeados correctamente a HTTPException, auditoría via `_audit`. Sin problemas.
- **metrics.py** — Metrics simple, lock por thread, capped lists. Sin problemas.
- **telegram_gateway.py** — Cliente HTTP con timeout, manejo de deep-links, token store atómico. Sin problemas.
- **telegram_links.py** — Token store thread-safe, TTL con auto-evicción. Sin problemas.

---

## Resumen

| severidad | nº |
|---|---|
| ALTA | 1 |
| MEDIA | 2 |
| BAJA | 3 |

**El hallazgo crítico es monitor.py:74.** Toda la lógica de monitorización de estado de agentes es código muerto unreachable. El monitor itera pero no hace nada con los resultados.
