# Migración familiamp → laia-arch

**Fecha:** Mayo 2026  
**Estado:** ✅ Completada

---

## Qué se migró

El servidor arrancó con usuario `familiamp` y hostname `familiamp-OptiPlex-9020`. Tras renombrar el usuario a `laia-arch` y el hostname a `laia-server`, todos los archivos de configuración del sistema seguían apuntando a las rutas antiguas.

---

## Cambios aplicados

### Hostname
```bash
sudo hostnamectl set-hostname laia-server
sudo sed -i 's/familiamp-OptiPlex-9020/laia-server/g' /etc/hosts
```

### Usuario (vía systemd al arranque)
Servicio one-shot que ejecutó durante el boot:
```bash
usermod -l laia-arch familiamp
usermod -d /home/laia-arch -m laia-arch
groupmod -n laia-arch familiamp
```

### ecryptfs
Carpeta del sistema renombrada:
```bash
sudo mv /home/.ecryptfs/familiamp /home/.ecryptfs/laia-arch
```
Permisos del home corregidos:
```bash
sudo chown laia-arch:laia-arch /home/laia-arch
sudo chmod 700 /home/laia-arch
```
`~/.ecryptfs/Private.mnt` actualizado:
```bash
echo '/home/laia-arch' > ~/.ecryptfs/Private.mnt
```
Symlinks físicos (capa pre-mount) corregidos vía bind mount para que PAM monte automáticamente en cada login:
```bash
sudo mkdir -p /tmp/home-phys
sudo mount --bind /home /tmp/home-phys
sudo ln -sfn /home/.ecryptfs/laia-arch/.Private  /tmp/home-phys/laia-arch/.Private
sudo ln -sfn /home/.ecryptfs/laia-arch/.ecryptfs /tmp/home-phys/laia-arch/.ecryptfs
sudo umount /tmp/home-phys
```

### Servicios systemd
Archivos en `/etc/systemd/system/` actualizados con `User=laia-arch` y paths `/home/laia-arch/`:

| Servicio | Cambio |
|---|---|
| `hermes.service` | User= y paths corregidos |
| `workspace-ui.service` | User= y paths corregidos |
| `pm2-familiamp.service` | **Reemplazado** por `pm2-laia-arch.service` |

> **Nota PM2:** PM2 6.x ya no escribe `pm2.pid`, así que el servicio usa `Type=oneshot` + `RemainAfterExit=yes` en lugar de `Type=forking`.

Los archivos fuente están en `~/servidor/`. Para aplicar cambios:
```bash
sudo cp ~/servidor/hermes.service /etc/systemd/system/
sudo cp ~/servidor/workspace-ui.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl restart hermes workspace-ui
```

### nginx
`/etc/nginx/sites-available/laia` — `root` del frontend corregido:
```
root /home/laia-arch/servidor/arete/frontend/dist;
```
Permiso de traversal para www-data:
```bash
sudo chmod o+x /home/laia-arch
```

### Python venv (hermes-agent)
El venv fue creado con el usuario antiguo: todos los scripts tenían shebangs con `/home/familiamp/`.

Corrección de shebangs en `venv/bin/`:
```bash
find ~/laia-arch/hermes-agent/venv/bin/ -type f | xargs grep -l "/home/familiamp" | xargs sed -i 's|/home/familiamp|/home/laia-arch|g'
```

El finder del paquete editable también tenía rutas hardcodeadas:
```bash
# Archivo: venv/lib/python3.12/site-packages/__editable___hermes_agent_0_11_0_finder.py
sed -i 's|/home/familiamp|/home/laia-arch|g' venv/lib/python3.12/site-packages/__editable___hermes_agent_0_11_0_finder.py
# Borrar .pyc para forzar recompilación
find venv/lib/python3.12/site-packages/__pycache__ -name "__editable___hermes_agent*" -delete
```

> **Lección:** al renombrar un usuario con venvs de `pip install -e .`, hay que corregir tanto los shebangs de `venv/bin/` como el archivo `__editable__*_finder.py` en site-packages, que contiene un `MAPPING` con todas las rutas del paquete hardcodeadas.

### PM2 dump
`~/.pm2/dump.pm2` corregido con sed:
```bash
sed -i 's|/home/familiamp|/home/laia-arch|g' ~/.pm2/dump.pm2
```

### ~/.bashrc
PATH hardcodeado corregido:
```bash
# Antes:
export PATH=/home/familiamp/.opencode/bin:$PATH
# Después:
[ -d "$HOME/.opencode/bin" ] && export PATH="$HOME/.opencode/bin:$PATH"
```

### Symlinks en ~/bin/
Tres symlinks apuntaban a `/home/familiamp/`:
```bash
ln -sfn /home/laia-arch/laia-arch/hermes-agent/venv/bin/hermes ~/bin/hermes
ln -sfn /home/laia-arch/laia-arch/hermes-agent/venv/bin/hermes ~/bin/laia-arch
ln -sfn /home/laia-arch/bin/serverpanel/serverpanel ~/bin/laia-panel
```

---

## Estado final verificado

```
nginx        → active ✅
postgresql   → active ✅
cloudflared  → active ✅
hermes       → active ✅
workspace-ui → active ✅
pm2-laia-arch → active ✅

arete-backend :8000 → 200 ✅
workspace-ui  :8077 → 200 ✅
wordpress     :9000 → 301 ✅ (redirect HTTPS esperado)
nginx laiajmp :80   → 200 ✅
nginx tienda  :80   → 200 ✅
```

Sin referencias a `familiamp` en `/etc/systemd/system/` (excepto `pm2-familiamp.service` deshabilitado y sin usar) ni en `/etc/nginx/`.
