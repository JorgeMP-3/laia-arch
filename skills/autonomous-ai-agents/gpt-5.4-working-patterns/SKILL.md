---
name: gpt-5.4-working-patterns
description: Patrones de trabajo observados en sesiones gpt-5.4 en este entorno Hermes/Mac mini. Aprendidos de la auditoría Docker paralela y la gestión de 10 subagentes MiniMax.
version: 1.0.0
author: Hermes Agent (learned from gpt-5.4 session)
license: MIT
---

# Patrones de trabajo gpt-5.4 en Hermes

## 1. Lanzamiento de agentes paralelos — siempre con probe primero

Nunca lanzar un batch sin verificar que el modelo responde:

```bash
hermes chat -q 'Responde solo: OK' -m MiniMax-M2.7 --provider minimax -Q
```

Solo si esto succeede → proceed con el batch.

## 2. Batch paralelo real — procesos hermes chat en background

```bash
mkdir -p /tmp/workdir
hermes chat -q "TAREA" -m MiniMax-M2.7 --provider minimax -Q > /tmp/workdir/agent1.txt 2>&1 &
echo "Launched agent 1 PID=$!"
```

- Cada agente → su propio archivo de salida
- `&` para background real
- Recoger PIDs para verificar

## 3. Polling manual de resultados

```bash
sleep 20 && for i in 1 2 3; do
  echo "--- AGENT $i ---"
  grep -E "AGENT_${i}_MINIMAX|DONE_${i}" /tmp/workdir/agent_${i}.txt
done
```

No asumir que terminó → verificar con process poll o leyendo el archivo.

## 4. Verificación cruzada de contradicciones

Cuando un agente contradice a otro:
- No aceptar el resultado dudoso sin más
- Verificar manualmente con tool directa
- En el ejemplo: agent9 dijo "Areté crash loop", pero gpt-5.4 hizo:
  ```bash
  docker inspect arete_backend --format '{{json .State}}'
  docker exec arete_backend node -e "fetch('http://127.0.0.1:8000/health')..."
  docker exec arete_postgres psql -U arete -d arete -c '\dt'
  ```
- Resultado: invalidate findings no verificados, confirm the ground truth

## 5. Reporte incremental vs esperar todo

gpt-5.4 no esperaba a los 10 agentes. Reportaba cuando tenía 2-3-6 resultados:
- Resumen provisional a los primeros resultados
- Estado actualizado con cada nuevo resultado
- Informe final solo cuando todos completaron

Esto es mejor que silencio hasta el final.

## 6. Corrección explícita de errores propios

Cuando el usuario señaló "no estás usando MiniMax":
- No excuses, reconocer el fallo
- Explicar qué pasó técnicamente (config session inheritance)
- Verificar con probe explícito
- Relanzar correctamente

## 7. Distinguir hechos de hallazgos probables

En el reporte final gpt-5.4 separaba:
- Hechos verificados (Docker estable, RAM justa, puertos expuestos)
- Hallazgos probables (cloudflared errors, permisos WP)
- Falsos positivos corregidos (Areté crash loop era incorrecto)

## 8. Config delegation NO se aplica en sesión activa

Después de `hermes config set delegation.*`:
- En CLI: hay que salir y volver a entrar, o hacer /reset
- En sesión existente: delegat_task ignora el cambio
- Solución robusta: flags `-m <model> --provider <provider>` en cada lanzamiento

## 9. Contenido de respuesta — estructura visible

gpt-5.4 respondía con:
- Tablas cuando hay datos comparables
- Secciones P1/P2/P3 claras
- Lista numerada de acciones
- Separación entre hechos y recomendaciones

## 10. Guardado de skills y memoria

Después de un patrón que funcione:
- Crear skill para reutilizarlo
- Actualizar memory con lecciones aprendidas no obvias
- No guardar estado de tareas (para eso es session_search)
