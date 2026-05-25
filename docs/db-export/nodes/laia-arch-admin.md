# LAIA-ARCH admin — Importante

## Metadata

- ID: `54`
- Slug: `laia-arch-admin`
- Kind: `important`
- Status: `active`
- Filename: `laia-arch-admin.md`
- Parent: `arch`
- Source kind: `manual`
- Created at: `2026-05-08T08:04:29.214654+00:00`
- Updated at: `2026-05-19T11:33:14.566183+00:00`
- Aliases: `laia-arch-admin`

## Summary

Advertencias y comandos críticos de administración

## Body

# LAIA-ARCH admin — Importante

## ⚠️ Advertencias críticas

### Nunca hacer desde AGORA
- Acceder a ~/.laia/ o ~/.laia-arch/
- Modificar config.yaml directamente
- Ejecutar comandos docker desde contenedores
- Acceder a workspaces de otros usuarios

### Siempre hacer desde ARCH
- Cambios en infraestructura
- Actualizaciones de seguridad
- Modificaciones al core de Hermes
- Despliegues a producción

## Comandos críticos (solo ARCH)

```bash
# Reiniciar servicios
systemctl restart hermes.service

# Ver logs
journalctl -u hermes.service -f

# Backup
cp ~/LAIA/state.db ~/LAIA/backups/state.db.$(date +%Y%m%d)

# Health check
python3 ~/LAIA/scripts/health-check.py
```

## Proceso de cambios
1. Proponer cambio
2. Revisar impacto en seguridad
3. Test en entorno sandbox
4. Desplegar en horario de mantenimiento
5. Monitorear 24h post-despliegue


> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `arch` (ARCH — Contexto admin de LAIA) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# LAIA-ARCH admin — Importante

# LAIA-ARCH admin — Importante

## ⚠️ Advertencias críticas

### Nunca hacer desde AGORA
- Acceder a ~/.laia/ o ~/.laia-arch/
- Modificar config.yaml directamente
- Ejecutar comandos docker desde contenedores
- Acceder a workspaces de otros usuarios

### Siempre hacer desde ARCH
- Cambios en infraestructura
- Actualizaciones de seguridad
- Modificaciones al core de Hermes
- Despliegues a producción

## Comandos críticos (solo ARCH)

```bash
# Reiniciar servicios
systemctl restart hermes.service

# Ver logs
journalctl -u hermes.service -f

# Backup
cp ~/LAIA/state.db ~/LAIA/backups/state.db.$(date +%Y%m%d)

# Health check
python3 ~/LAIA/scripts/health-check.py
```

## Proceso de cambios
1. Proponer cambio
2. Revisar impacto en seguridad
3. Test en entorno sandbox
4. Desplegar en horario de mantenimiento
5. Monitorear 24h post-despliegue


> 📅 Documentado: 2026-05-08
