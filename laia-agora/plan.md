# Plan: Ecosistema LAIA — laia-arch (admin) + laia-agora (usuarios)

> Resumen ejecutivo. Ver ARQUITECTURA_ECOSISTEMA.md y PLAN_IMPLEMENTACION.md para detalle.

---

## Contexto

Servidor Xeon + 32GB en camino. 10 empleados. La idea:
- **laia-arch**: instancia admin con control total del host (solo Jorge, acceso por VPN)
- **laia-agora**: instancia aislada por empleado, herramientas restringidas, sin acceso al host

---

## Acceso

| Quién | Cómo accede |
|-------|-------------|
| Jorge (admin) | VPN → host → UI local de laia-arch |
| Empleados | https://laiajmp.org → login → su agente personal |
| Empleados (escritorio) | App Tauri → conecta a laiajmp.org |
| Empleados (móvil) | Navegador → laiajmp.org (responsive) |

---

## Arquitectura en una línea por capa

- **laia-arch**: host nativo, todas las herramientas, ~8-10GB RAM
- **LAIA coordinador**: contenedor propio, opera 24/7, toolset especial, ~2GB RAM
- **AGORA**: 10 contenedores (puertos 9200-9209), ~1.5GB RAM cada uno, datos en `/opt/agora/{usuario}`
- **Frontend**: Una sola app React nueva (diseño limpio) + Tauri para escritorio
- **nginx**: laiajmp.org → auth → proxy al contenedor del usuario

---

## Fases de implementación

0. Migrar app actual de laiajmp.org
1. Toolset `agora` en toolsets.py
2. Dockerfile agora
3. docker-compose.agora.yml
4. agora-manager.sh
5. nginx routing + htpasswd
6. Frontend React (login + UI de agente)
7. Tauri packaging

**Tiempo estimado total: ~4-5 horas** (sin contar desarrollo del frontend)
