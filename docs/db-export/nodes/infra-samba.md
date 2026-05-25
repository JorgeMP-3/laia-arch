# Acceso SMB/Samba

## Metadata

- ID: `113`
- Slug: `infra-samba`
- Kind: `doc`
- Status: `active`
- Filename: `infra-samba.md`
- Parent: `servidores-red`
- Source kind: `manual`
- Created at: `2026-05-08T08:35:13.278486+00:00`
- Updated at: `2026-05-08T08:35:13.278486+00:00`
- Aliases: `infra-samba`

## Summary

Permite montar `/home/laia-arch` como unidad de red desde el Mac (o cualquier cliente SMB), para ges

## Body

# Samba — Acceso desde Mac al home

## Para qué sirve

Permite montar `/home/laia-arch` como unidad de red desde el Mac (o cualquier cliente SMB), para gestionar archivos directamente sin necesidad de SSH/SCP.

## Datos de conexión

| Campo | Valor |
|---|---|
| Share | `laia-arch` |
| Path servidor | `/home/laia-arch` |
| Usuario | `laia-arch` |
| Puerto | 445 (SMB) |

**Direcciones para conectar desde el Mac:**

| Red | URL |
|---|---|
| Tailscale | `smb://100.95.125.76/laia-arch` |
| WiFi local | `smb://192.168.100.194/laia-arch` |
| Cable (eno1) | `smb://10.10.10.2/laia-arch` |

En el Mac: **Finder → Ir → Conectar al servidor** (⌘K), pegar la URL y usar usuario `laia-arch` con la contraseña Samba.

---

## Gestión del servicio

```bash
sudo systemctl start|stop|restart smbd nmbd
sudo systemctl status smbd nmbd

# Ver usuarios Samba registrados
sudo pdbedit -L

# Cambiar contraseña Samba de laia-arch
sudo smbpasswd laia-arch

# Añadir usuario Samba nuevo (si hiciera falta)
sudo smbpasswd -a <usuario>
```

---

## Configuración

**Archivo:** `/etc/samba/smb.conf`  
**Share fuente:** `~/servidor/setup-samba.sh` (script de instalación)

### Sección [global] relevante

```ini
interfaces = lo eno1 wlxd03745b3f808
hosts allow = 127.0.0.1 10.10.10.0/24 192.168.100.0/24 100.64.0.0/10
```

- `interfaces` — Samba escucha en todas las interfaces (`0.0.0.0`) pero solo acepta conexiones de las redes listadas en `hosts allow`.
- `100.64.0.0/10` — cubre todo el rango CGNAT de Tailscale (100.x.x.x).
- **No se usa `bind interfaces only = yes`** porque Tailscale usa prefijo `/32` sin broadcast y Samba no puede hacer bind por nombre de interfaz ni por IP `/32`.

### Sección [laia-arch]

```ini
[laia-arch]
   comment = Home laia-arch
   path = /home/laia-arch
   valid users = laia-arch
   read only = no
   browseable = yes
   create mask = 0644
   directory mask = 0755
```

---

## Nota importante: ecryptfs

La share muestra el home **descifrado solo mientras ecryptfs esté montado**, es decir, mientras haya una sesión activa en el servidor. Si el servidor se reinicia y nadie ha iniciado sesión aún, la share mostrará solo los archivos de la capa física (`README.txt`, `Access-Your-Private-Data.desktop`).

Para montar manualmente si hace falta:
```bash
ecryptfs-mount-private   # desde una sesión SSH como laia-arch
```


> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `servidores-red` (Servidores y Red) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Acceso SMB/Samba

# Samba — Acceso desde Mac al home

## Para qué sirve

Permite montar `/home/laia-arch` como unidad de red desde el Mac (o cualquier cliente SMB), para gestionar archivos directamente sin necesidad de SSH/SCP.

## Datos de conexión

| Campo | Valor |
|---|---|
| Share | `laia-arch` |
| Path servidor | `/home/laia-arch` |
| Usuario | `laia-arch` |
| Puerto | 445 (SMB) |

**Direcciones para conectar desde el Mac:**

| Red | URL |
|---|---|
| Tailscale | `smb://100.95.125.76/laia-arch` |
| WiFi local | `smb://192.168.100.194/laia-arch` |
| Cable (eno1) | `smb://10.10.10.2/laia-arch` |

En el Mac: **Finder → Ir → Conectar al servidor** (⌘K), pegar la URL y usar usuario `laia-arch` con la contraseña Samba.

---

## Gestión del servicio

```bash
sudo systemctl start|stop|restart smbd nmbd
sudo systemctl status smbd nmbd

# Ver usuarios Samba registrados
sudo pdbedit -L

# Cambiar contraseña Samba de laia-arch
sudo smbpasswd laia-arch

# Añadir usuario Samba nuevo (si hiciera falta)
sudo smbpasswd -a <usuario>
```

---

## Configuración

**Archivo:** `/etc/samba/smb.conf`  
**Share fuente:** `~/servidor/setup-samba.sh` (script de instalación)

### Sección [global] relevante

```ini
interfaces = lo eno1 wlxd03745b3f808
hosts allow = 127.0.0.1 10.10.10.0/24 192.168.100.0/24 100.64.0.0/10
```

- `interfaces` — Samba escucha en todas las interfaces (`0.0.0.0`) pero solo acepta conexiones de las redes listadas en `hosts allow`.
- `100.64.0.0/10` — cubre todo el rango CGNAT de Tailscale (100.x.x.x).
- **No se usa `bind interfaces only = yes`** porque Tailscale usa prefijo `/32` sin broadcast y Samba no puede hacer bind por nombre de interfaz ni por IP `/32`.

### Sección [laia-arch]

```ini
[laia-arch]
   comment = Home laia-arch
   path = /home/laia-arch
   valid users = laia-arch
   read only = no
   browseable = yes
   create mask = 0644
   directory mask = 0755
```

---

## Nota importante: ecryptfs

La share muestra el home **descifrado solo mientras ecryptfs esté montado**, es decir, mientras haya una sesión activa en el servidor. Si el servidor se reinicia y nadie ha iniciado sesión aún, la share mostrará solo los archivos de la capa física (`README.txt`, `Access-Your-Private-Data.desktop`).

Para montar manualmente si hace falta:
```bash
ecryptfs-mount-private   # desde una sesión SSH como laia-arch
```


> 📅 Documentado: 2026-05-08
