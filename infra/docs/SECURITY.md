# Seguridad — LAIA Agent Runtime

## Checklist de seguridad

### Contenedor LXD (por agente)

| Control | Estado | Notas |
|---------|--------|-------|
| Sin socket Docker | ✅ | El perfil `laia-employee` no monta `/var/run/docker.sock` |
| Sin `privileged: true` | ✅ | Profile usa `security.privileged=false` (default LXD) |
| Sin nesting por defecto | ✅ | `security.nesting=false` salvo uso explícito |
| Sin mount de `/home/laia-hermes` | ✅ | Solo se monta el rootfs del contenedor |
| Runtime no corre como root | ✅ | `systemd` lanza el servicio como `laia-agent` |
| Permisos mínimos `/opt/laia` | ✅ | Ver tabla de permisos abajo |
| Token por agente en `agent.json` | ✅ | Generado en `install-agent-runtime` |

### Permisos de directorios

```
/opt/laia/agent.json    → 0644  root:root       (config, solo lectura para runtime)
/opt/laia/agent/        → 0755  laia-agent      (código, solo lectura/ejecución)
/opt/laia/runtime/      → 0755  laia-agent      (venv, solo lectura/ejecución)
/opt/laia/data/         → 0755  laia-agent      (escritura del runtime)
/opt/laia/logs/         → 0755  laia-agent      (escritura del runtime)
/opt/laia/workspaces/   → 0755  laia-agent      (workspace personal, escritura)
```

### AGORA Backend

| Control | Estado | Notas |
|---------|--------|-------|
| Endpoints de agentes requieren `agora_admin` | ✅ | `require_roles("agora_admin")` en todos los endpoints de control |
| laiactl: solo comandos de allowlist | ✅ | `orchestrator.py` no acepta comandos arbitrarios |
| Slug validado con regex | ✅ | `^[a-z0-9][a-z0-9-]{1,30}$` |
| Snapshot name validado | ✅ | `^[a-z0-9][a-z0-9-]{0,40}$` |
| Task type validado | ✅ | `^[a-z_]{1,40}$` |
| Subprocess sin `shell=True` | ✅ | Siempre lista de args, nunca string |
| Timeout en llamadas laiactl | ✅ | 15-600s según comando |

## Amenazas consideradas

### 1. Inyección de comandos via slug
- **Vector**: slug controlado por usuario en URL → pasa a subprocess
- **Mitigación**: validación con `SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,30}$")` antes de cualquier llamada
- **Mitgación adicional**: subprocess usa lista de args, no `shell=True`

### 2. Escalado de privilegios dentro del contenedor
- **Vector**: runtime compromete el sistema host via `/proc`, `/sys`, etc.
- **Mitigación**: LXD sin `privileged`, sin AppArmor bypass, sin capabilities extras

### 3. Acceso a otros contenedores
- **Vector**: contenedor `laia-jorge` accede a red interna del host o a `laia-otro`
- **Mitigación**: red LXD bridge aislada, sin rutas explícitas entre contenedores
- **Pendiente**: aplicar `nftables` reglas de aislamiento inter-contenedor si se necesita

### 4. Exfiltración de datos del host
- **Vector**: proceso dentro del contenedor lee archivos del host
- **Mitigación**: no se montan directorios del host dentro del contenedor (ver perfil)
- **Verificación**: `lxc config show laia-jorge | grep -i path`

### 5. Token de agente expuesto
- **Vector**: `agent.json` contiene token; si se compromete el contenedor, el token fuga
- **Mitigación**: el token solo da acceso al propio agente (scope limitado)
- **Mejora futura**: rotación de tokens via AGORA backend

## Perfil LXD recomendado (`laia-employee`)

```yaml
config:
  security.privileged: "false"
  security.nesting: "false"
  limits.cpu: "2"
  limits.memory: "1GB"
  limits.memory.enforce: "hard"
description: LAIA employee agent profile
devices:
  eth0:
    name: eth0
    network: lxdbr0
    type: nic
  root:
    path: /
    pool: default
    type: disk
    size: 10GB
```

Nota: sin `unix.socket` device, sin `disk` adicional apuntando a rutas del host.
