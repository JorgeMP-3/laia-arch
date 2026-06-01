# QA Report — chat_engine.py, laia_chat.py, llm_config.py, pricing.py, child_profiles.py

Auditor: audit-only (read-only)  
Fecha: 2026-06-01  
Área: services/agora-backend/app — chat / LLM  

---

## Resumen

| fichero | issues |
|---|---|
| chat_engine.py | 1 silencioso (except:pass), 1 catch-all impreciso |
| laia_chat.py | 2 silenciosos (except:pass) |
| llm_config.py | sin observaciones |
| pricing.py | 1 lógica innecesaria (no afecta correctness) |
| child_profiles.py | sin observaciones |

---

## Detalle

| fichero:línea | categoría | severidad | qué está mal | por qué | fix sugerido |
|---|---|---|---|---|---|
| chat_engine.py:354-355 | MALA PRAXIS | media | `except Exception: pass` al asignar callbacks al AIAgent | Silencia cualquier error al vincular `stream_delta_callback`, `tool_start_callback`, `tool_complete_callback`. Si el slot no existe o la asignación falla por cualquier razón razôn, el flujo continúa sin tokens ni tool events sin que nadie se entere. El comentario "placeholder agents may not have these slots" no justifica ocultar el error — al menos habrÃ­a que loguear en DEBUG. | Reemplazar `except Exception: pass` por `except Exception: logger.debug("placeholder agent: callback assignment skipped: %s", exc)` o eliminar el try/except si los slots son contractuales. |
| chat_engine.py:212-213 | MALA PRAXIS / ROBUSTEZ | media | `except Exception: exceeded, reason = False, None` | Si `store.budget_exceeded()` lanza cualquier excepciÃ³n (p.ej. timeout de DB, error de conexiÃ³n), se trata como "presupuesto no excedido" y se permite el turno. Esto es un verde falso: un error de infraestructura se traduce en acceso cuando debÃ­a estar bloqueado. | Separar la consulta de budget de su manejo: consultar el budget dentro del try, y sÃ³lo en el except definir `exceeded=False, reason="budget_check_failed"`. El llamante recibe la seÃ±al de que no se pudo verificar. |
| laia_chat.py:176-177 | MALA PRAXIS | media | `except Exception: pass` idÃ©ntico a chat_engine.py:354 | Mismo problema: asignar `stream_delta_callback`, `tool_start_callback`, `tool_complete_callback` falla en silencio si el AIAgent placeholder no tiene esos atributos. | Igual que arriba: loguear en DEBUG o eliminar el try/except. |
| laia_chat.py:189-190 | MALA PRAXIS | media | `except Exception: pass` tras `record_usage_for_session` | Si el registro de uso falla, se ignora sin traza. `record_usage_for_session` es una operaciÃ³n de facturaciÃ³n — fallar en silencio significa que el uso no se facturarÃ¡ nunca sin que el operador se dÃ© cuenta. | `except Exception: logger.warning("record_usage_for_session failed: %s", exc)` |
| pricing.py:72 | MALA PRAXIS | baja | `_OVERRIDES_CACHE is not None and mtime == _OVERRIDES_MTIME` | La condiciÃ³n `_OVERRIDES_CACHE is not None` es redundante: si existe el path pero aÃºn no se ha cacheado nada, `_OVERRIDES_CACHE` es `None` y la funciÃ³n llegarÃ­a a la lÃ­nea 71 donde se lee el mtime. El flujo real no tiene ruta que llegue a la lÃ­nea 72 con `_OVERRIDES_CACHE is None`. No afecta correctness, pero confunde al lector. | Simplificar a: `if _OVERRIDES_CACHE is not None and mtime == _OVERRIDES_MTIME:` (ya es asÃ­) o `_OVERRIDES_MTIME and mtime == _OVERRIDES_MTIME:` |

---

## Sin problemas

- **llm_config.py**: sin hallazgos. Los imports conditionally fallidos son intencionales (modo fallback). No hay except:pass silenciosos, ni hardcoded secrets, ni mutable defaults, ni N+1, ni anidamiento profundo.
- **child_profiles.py**: diccionario estÃ¡tico puro, 59 lÃ­neas. Sin hallazgos.
