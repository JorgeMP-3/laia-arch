# LAIA services

Servicios backend propios del ecosistema LAIA.

## Convencion oficial

Los backends productivos nuevos viven aqui. La primera pieza prevista es:

```text
services/agora-backend/
```

## AGORA backend

Responsabilidades iniciales:

- autenticacion;
- usuarios/empleados;
- tareas;
- eventos;
- workspace colectivo AGORA;
- modulo interno `coordinator`;
- registro y proxy hacia agentes personales LXD.

No debe montar rutas admin del host como `.hermes`, `~/LAIA` ni Docker socket.

