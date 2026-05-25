# Agentes personales — Docker (Alternativa documentada)

## Metadata

- ID: `131`
- Slug: `agentes-docker-alternativa`
- Kind: `doc`
- Status: `active`
- Filename: `agentes-docker-alternativa.md`
- Parent: `agentes-personales`
- Source kind: `tool`
- Created at: `2026-05-08T15:45:23.469823+00:00`
- Updated at: `2026-05-19T11:33:14.566183+00:00`
- Aliases: `agentes-docker-alternativa`

## Summary

Docker como alternativa a LXD para PA-AGORA

## Body

# PA-AGORA — Docker (Alternativa documentada)

## Contexto

Docker fue la primera opción considerada y está documentada en el workspace. Se mantiene aquí como alternativa conocida por si LXD presenta problemas en el servidor Dell 9020.

## Por qué se descarta como primera opción

Para la visión de "empleado con servidor propio dentro de su agente", Docker tiene limitaciones fundamentales:

- **Sin systemd:** el empleado no puede hacer `systemctl start nginx`
- **Sin nesting seguro:** para que un empleado cree contenedores dentro de su contenedor, necesita acceso al socket Docker del host o Docker-in-Din (Peligroso)
- **Una aplicación por contenedor:** Docker está diseñado para eso, no para un Ubuntu completo
- **Port mapping manual:** cada servicio expuesto necesita configuración en el host

## Alternativa: Docker socket con permisos limitados

Si se decide usar Docker, la única forma segura de permitir "servidores dentro" sería:

```bash
# En el host: crear un socket Docker especial para empleados
# con restricciones de namespace
```

Esto es complejo, frágil y no proporciona la misma experiencia que un SO completo.

## Caso de uso viable para Docker

Docker **sí funciona bien** si el objetivo es:

- Agente ligero de asistencia (no desarrollo)
- Solo herramientas de productividad (calendario, notas, chat)
- Sin necesidad de instalar servicios propios
- Scope limitado a una o dos herramientas

## Configuración original (antes de la evaluación LXD)

```bash
# Crear contenedor para empleado
docker run -d \
  --name laia-{empleado} \
  -v /opt/data/{empleado}:/opt/data \
  -p 127.0.0.1:PORT:8080 \
  laia-agent:latest
```

- Workspace propio en `/opt/data/`
- Sin acceso a ~/.laia/
- Sin acceso a ~/.laia-arch/
- Puerto mapeado solo a localhost

## Conclusión

Docker es la opción más rápida de desplegar y tiene un ecosistema maduro (Portainer, docker-compose, images en DockerHub). Pero para la visión de AGORA donde el empleado necesita libertad para desarrollar, se queda corto.

**Recomendación:** Documentar Docker como backup, priorizar LXD.

> 📅 Documentado: 2026-05-12

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `agentes-personales` (Agentes personales — Hijos de LAIA (v2.1)) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Agentes personales — Docker (Alternativa documentada)

# PA-AGORA — Docker (Alternativa documentada)

## Contexto

Docker fue la primera opción considerada y está documentada en el workspace. Se mantiene aquí como alternativa conocida por si LXD presenta problemas en el servidor Dell 9020.

## Por qué se descarta como primera opción

Para la visión de "empleado con servidor propio dentro de su agente", Docker tiene limitaciones fundamentales:

- **Sin systemd:** el empleado no puede hacer `systemctl start nginx`
- **Sin nesting seguro:** para que un empleado cree contenedores dentro de su contenedor, necesita acceso al socket Docker del host o Docker-in-Din (Peligroso)
- **Una aplicación por contenedor:** Docker está diseñado para eso, no para un Ubuntu completo
- **Port mapping manual:** cada servicio expuesto necesita configuración en el host

## Alternativa: Docker socket con permisos limitados

Si se decide usar Docker, la única forma segura de permitir "servidores dentro" sería:

```bash
# En el host: crear un socket Docker especial para empleados
# con restricciones de namespace
```

Esto es complejo, frágil y no proporciona la misma experiencia que un SO completo.

## Caso de uso viable para Docker

Docker **sí funciona bien** si el objetivo es:

- Agente ligero de asistencia (no desarrollo)
- Solo herramientas de productividad (calendario, notas, chat)
- Sin necesidad de instalar servicios propios
- Scope limitado a una o dos herramientas

## Configuración original (antes de la evaluación LXD)

```bash
# Crear contenedor para empleado
docker run -d \
  --name laia-{empleado} \
  -v /opt/data/{empleado}:/opt/data \
  -p 127.0.0.1:PORT:8080 \
  laia-agent:latest
```

- Workspace propio en `/opt/data/`
- Sin acceso a ~/.laia/
- Sin acceso a ~/.laia-arch/
- Puerto mapeado solo a localhost

## Conclusión

Docker es la opción más rápida de desplegar y tiene un ecosistema maduro (Portainer, docker-compose, images en DockerHub). Pero para la visión de AGORA donde el empleado necesita libertad para desarrollar, se queda corto.

**Recomendación:** Documentar Docker como backup, priorizar LXD.

> 📅 Documentado: 2026-05-12
