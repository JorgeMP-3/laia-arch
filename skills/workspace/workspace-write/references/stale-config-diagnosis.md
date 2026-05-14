# Diagnostico de Stale Config en Workspaces

## Sintoma

```
workspace_list_workspaces() -> active_workspaces: ["pixelcore"]
# pero $HERMES_HOME/config.yaml dice: active_workspaces: ['pixelcore', 'laia-arch']
```

## Paso 1: Verificar archivo real

```bash
python3 -c "
import yaml
cfg = yaml.safe_load(open('/home/laia-arch/LAIA/config.yaml'))
ws = cfg.get('plugins', {}).get('workspace-context', {})
print('archivo:', ws.get('active_workspaces'))
"
```

## Paso 2: Verificar cada proceso

### Backend workspace-ui (puerto 8077)
```bash
curl -s http://localhost:8077/api/context-engine/injected | python3 -c "
import sys, json; d = json.load(sys.stdin)
print('backend:', sorted(d.get('nodes_by_workspace', {}).keys()))
"
```

### Gateway (proceso hermes)
```bash
# Identificar proceso
ps aux | grep -E "hermes|gateway" | grep -v grep

# Ver entorno del proceso
cat /proc/<pid>/environ | tr '\0' '\n' | grep HERMES_HOME

# Verificar que lee el proceso via Python del venv
/home/laia-arch/LAIA/.laia-arch/venv/bin/python -c "
import sys; sys.path.insert(0, '/home/laia-arch/LAIA/.laia-arch')
from hermes_constants import get_hermes_home
import yaml
cfg = yaml.safe_load(open(str(get_hermes_home() / 'config.yaml')))
ws = cfg.get('plugins', {}).get('workspace-context', {})
print('venv python:', ws.get('active_workspaces'))
"
```

## Paso 3: Interpretar resultados

| Archivo | Backend | Gateway | Diagnostico |
|---|---|---|---|
| [x] | [x] | [x] | Todo bien; el agente individual tiene caches propias |
| [x] | [x] | [ ] | Gateway stale; necesita reinicio |
| [x] | [ ] | [ ] | HERMES_HOME mal configurado en los procesos |

## Paso 4: Solucionar

### Reiniciar gateway
```bash
# Identificar el proceso padre
ps aux | grep -E "hermes|gateway" | grep -v grep

# Matar y dejar que systemd/restart lo recupere
kill -HUP <pid>
# o si no responde:
kill <pid>
```

### Via API toggle (solo cambia el backend)
```bash
curl -X PUT http://localhost:8077/api/context-engine/config \
  -H "Content-Type: application/json" \
  -d '{"active_workspaces": ["pixelcore", "laia-arch"]}'
```
Esto solo actualiza el backend, NO el gateway. Necesario combinar con Paso 4a.

## Causas comunes

1. **Sesion de agente con config cacheada**: la sesion del agente old cachea
   `active_workspaces` al arrancar y no lo refresca aunque el archivo cambie.
2. **HERMES_HOME diferente**: el gateway puede usar un HERMES_HOME distinto
   al de la shell (`hermes_constants.get_hermes_home()` depende de env).
3. **Dos procesos con mtime distintos**: si config.yaml se editо y se salvу
   mientras el gateway estaba corriendo, puede haber un race condition en
   `_refresh_config_if_changed()`.

## Prevencion

- Tras cambiar `config.yaml`, siempre verificar con la misma sesion que hizo
  el cambio (que comparte proceso con el gateway).
- Para cambios que deben verse inmediatamente, usar API toggle del backend
  (que si tiene hot-reload) + reiniciar el gateway para consistencia.
