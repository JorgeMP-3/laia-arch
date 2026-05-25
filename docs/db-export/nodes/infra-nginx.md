# Configuración nginx

## Metadata

- ID: `108`
- Slug: `infra-nginx`
- Kind: `doc`
- Status: `active`
- Filename: `infra-nginx.md`
- Parent: `servidores-red`
- Source kind: `manual`
- Created at: `2026-05-08T08:35:11.828671+00:00`
- Updated at: `2026-05-08T08:35:11.828671+00:00`
- Aliases: `infra-nginx`

## Summary

| Archivo | Descripción |

## Body

# Nginx — Reverse Proxy

## Archivos de configuración

| Archivo | Descripción |
|---|---|
| `~/servidor/nginx/laia.conf` | **Fuente de verdad** — editar aquí |
| `/etc/nginx/sites-available/laia` | Copia activa en nginx |
| `/etc/nginx/sites-enabled/laia` | Symlink al anterior |

Para aplicar cambios:
```bash
sudo cp ~/servidor/nginx/laia.conf /etc/nginx/sites-available/laia
sudo nginx -t && sudo systemctl reload nginx
```

---

## Configuración actual

### laiajmp.org — Arete (app principal)
- Sirve el frontend React como archivos estáticos desde `~/servidor/arete/frontend/dist/`
- Las rutas `/api/*` y `/auth/*` se proxyan al backend en `:8000`
- SPA: cualquier ruta no encontrada devuelve `index.html`

### app.laiajmp.org — API Arete (app escritorio)
- Proxy directo al backend `:8000`
- Usado por la aplicación de escritorio para llamar a la API

### tienda.laiajmp.org — WordPress
- Proxy al contenedor WordPress en `:9000`
- WordPress está configurado para HTTPS (`WP_HOME=https://tienda.laiajmp.org`)

### presentaciones.laiajmp.org
- Devuelve 404 — pendiente de configurar

---

## Nota importante sobre permisos

El directorio home (`/home/laia-arch`) tiene permisos `0700` por defecto.  
Nginx corre como `www-data` y necesita poder atravesar el directorio.  
Se aplicó: `chmod o+x /home/laia-arch`  
Esto da permiso de traversal (entrar) sin dar permiso de lectura (listar).

---

## Config completa actual

```nginx
server {
    listen 80;
    server_name laiajmp.org www.laiajmp.org;

    root /home/laia-arch/servidor/arete/frontend/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /auth/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location = /health {
        proxy_pass http://127.0.0.1:8000/health;
        proxy_set_header Host $host;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}

server {
    listen 80;
    server_name app.laiajmp.org;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name presentaciones.laiajmp.org;
    return 404;
}

server {
    listen 80;
    server_name tienda.laiajmp.org;

    location / {
        proxy_pass http://127.0.0.1:9000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
    }
}
```


> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `servidores-red` (Servidores y Red) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Configuración nginx

# Nginx — Reverse Proxy

## Archivos de configuración

| Archivo | Descripción |
|---|---|
| `~/servidor/nginx/laia.conf` | **Fuente de verdad** — editar aquí |
| `/etc/nginx/sites-available/laia` | Copia activa en nginx |
| `/etc/nginx/sites-enabled/laia` | Symlink al anterior |

Para aplicar cambios:
```bash
sudo cp ~/servidor/nginx/laia.conf /etc/nginx/sites-available/laia
sudo nginx -t && sudo systemctl reload nginx
```

---

## Configuración actual

### laiajmp.org — Arete (app principal)
- Sirve el frontend React como archivos estáticos desde `~/servidor/arete/frontend/dist/`
- Las rutas `/api/*` y `/auth/*` se proxyan al backend en `:8000`
- SPA: cualquier ruta no encontrada devuelve `index.html`

### app.laiajmp.org — API Arete (app escritorio)
- Proxy directo al backend `:8000`
- Usado por la aplicación de escritorio para llamar a la API

### tienda.laiajmp.org — WordPress
- Proxy al contenedor WordPress en `:9000`
- WordPress está configurado para HTTPS (`WP_HOME=https://tienda.laiajmp.org`)

### presentaciones.laiajmp.org
- Devuelve 404 — pendiente de configurar

---

## Nota importante sobre permisos

El directorio home (`/home/laia-arch`) tiene permisos `0700` por defecto.  
Nginx corre como `www-data` y necesita poder atravesar el directorio.  
Se aplicó: `chmod o+x /home/laia-arch`  
Esto da permiso de traversal (entrar) sin dar permiso de lectura (listar).

---

## Config completa actual

```nginx
server {
    listen 80;
    server_name laiajmp.org www.laiajmp.org;

    root /home/laia-arch/servidor/arete/frontend/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /auth/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location = /health {
        proxy_pass http://127.0.0.1:8000/health;
        proxy_set_header Host $host;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}

server {
    listen 80;
    server_name app.laiajmp.org;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name presentaciones.laiajmp.org;
    return 404;
}

server {
    listen 80;
    server_name tienda.laiajmp.org;

    location / {
        proxy_pass http://127.0.0.1:9000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
    }
}
```


> 📅 Documentado: 2026-05-08
