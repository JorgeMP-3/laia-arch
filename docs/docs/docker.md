# Docker — WordPress (Tienda)

## Filosofía

Docker se usa **exclusivamente para WordPress** y su stack de base de datos.  
Todo lo demás corre de forma nativa.

## Stack WordPress

**Compose file:** `~/servidor/tienda/docker-compose.yml`

| Contenedor | Imagen | Puerto host | Descripción |
|---|---|---|---|
| tienda_db | mysql:8.0 | — (interno) | Base de datos MySQL |
| tienda_wordpress | wordpress:latest | 9000→80 | WordPress |
| tienda_phpmyadmin | phpmyadmin/phpmyadmin | 9001→80 | Admin BD |

**Volúmenes Docker:**
- `tienda_db_data` — datos MySQL
- `tienda_wordpress_data` — archivos WordPress

**Red Docker:**
- `tienda_tienda_net` — red interna del stack
- `proxy` — red externa compartida (creada manualmente: `docker network create proxy`)

## Comandos habituales

```bash
# Ver estado
sg docker -c "docker ps"
sg docker -c "docker compose -f ~/servidor/tienda/docker-compose.yml ps"

# Arrancar / parar
sg docker -c "docker compose -f ~/servidor/tienda/docker-compose.yml up -d"
sg docker -c "docker compose -f ~/servidor/tienda/docker-compose.yml down"
sg docker -c "docker compose -f ~/servidor/tienda/docker-compose.yml restart"

# Logs
sg docker -c "docker logs tienda_wordpress"
sg docker -c "docker logs tienda_db"

# Acceso a MySQL
sg docker -c "docker exec -it tienda_db mysql -u wpuser -pwp123456 tienda_smr"
```

> **Nota sobre `sg docker`:** necesario cuando la sesión no tiene el grupo docker activo.  
> Tras hacer `newgrp docker` o reiniciar sesión, se puede usar `docker` directamente.

## Credenciales WordPress/MySQL

| Campo | Valor |
|---|---|
| MySQL user | wpuser |
| MySQL password | wp123456 |
| MySQL database | tienda_smr |
| MySQL root password | root123 |

## WordPress URLs

- `WP_HOME` / `WP_SITEURL` → `https://tienda.laiajmp.org`
- WordPress detecta HTTPS por el header `HTTP_X_FORWARDED_PROTO` de Cloudflare

## Restaurar backup (si hace falta)

```bash
# Parar contenedores
sg docker -c "docker compose -f ~/servidor/tienda/docker-compose.yml down"

# Eliminar volúmenes con datos corruptos
sg docker -c "docker volume rm tienda_db_data tienda_wordpress_data"

# Crear volúmenes frescos y restaurar ANTES de arrancar MySQL
sg docker -c "docker volume create tienda_db_data"
sg docker -c "docker run --rm -v tienda_db_data:/var/lib/mysql \
  -v $HOME/docker-backup:/backup \
  alpine tar xzf /backup/tienda-informatica_db_data.tar.gz -C /var/lib/mysql"

sg docker -c "docker volume create tienda_wordpress_data"
sg docker -c "docker run --rm -v tienda_wordpress_data:/var/www/html \
  -v $HOME/docker-backup:/backup \
  alpine tar xzf /backup/tienda-informatica_wordpress_data.tar.gz -C /var/www/html"

# Arrancar
sg docker -c "docker compose -f ~/servidor/tienda/docker-compose.yml up -d"
```

**Importante:** restaurar el datadir de MySQL ANTES de iniciar el contenedor.  
Si MySQL ya arrancó y se sobreescriben los datos → corrupción del Data Dictionary.
