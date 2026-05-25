# Release Flow: Dev + Stable

Este documento define cómo Jorge debe separar desarrollo y producción en LAIA.
Es intencionadamente manual: no hay CI/CD todavía.

## Ramas

| Rama | Uso | Dónde corre |
|---|---|---|
| `feat/*`, `wip/*` | Trabajo temporal de Jorge o una IA | VM dev |
| `main` | Integración/desarrollo validado | VM QEMU en Mac |
| `stable` | Producción | Lenovo ThinkStation Ubuntu |

Reglas:

- No se trabaja directo sobre `stable`.
- `stable` solo recibe merges fast-forward desde `main`, salvo hotfix aprobado.
- Los tags `vX.Y.Z` se crean solo sobre `stable`.
- El instalador `curl|bash` por defecto apunta a `stable`.
- Dev debe usar `--branch main` o una rama explícita.

## Máquinas

| Máquina | Rama | Datos |
|---|---|---|
| VM Mac QEMU | `main` o `feat/*` | Sintéticos, regenerables |
| ThinkStation Ubuntu | `stable` | Reales |

Los datos están aislados porque cada máquina tiene su propio `/srv/laia/`.
No compartas `/srv/laia/` entre dev y prod.

## Criterios Antes De Release

Antes de promover una versión a `stable`:

1. La VM dev instala o clona end-to-end.
2. `bash tests/installer/run_all.sh` pasa.
3. Si se tocó Python/backend, `make test` pasa o los fallos quedan documentados.
4. Si se tocó frontend, el typecheck correspondiente pasa.
5. `workflow/changelog.md` está actualizado.
6. No hay secretos nuevos en git.

## Promote Manual

En la VM dev:

```bash
cd /home/jorge/LAIA
git switch main
git pull origin main
bash tests/installer/run_all.sh

git switch stable
git pull origin stable
git merge --ff-only main
git tag -a vX.Y.Z -m "release vX.Y.Z"
git push origin stable vX.Y.Z
```

Si `git merge --ff-only main` falla, no hagas merge normal y no hagas
`push --force`. Para y revisa por qué `stable` diverge.

## Deploy En Producción

En el ThinkStation:

```bash
cd /home/jorge/LAIA
git fetch --all --tags
git switch stable
git pull origin stable
sudo laia-release
```

Verificación mínima:

```bash
readlink -f /opt/laia
sudo /usr/local/bin/laia diagnose
curl -fsS http://127.0.0.1:8088/api/health
```

## Rollback

Si el release falla o degrada producción:

```bash
sudo laia-rollback
readlink -f /opt/laia
sudo /usr/local/bin/laia diagnose
```

`laia-rollback` revierte el symlink `/opt/laia` a la versión anterior en
`/opt/laia-vX.Y.Z`.

## Hotfix

Si producción necesita un fix urgente:

```bash
cd /home/jorge/LAIA
git fetch origin
git switch stable
git pull origin stable
git switch -c fix/<area>

# aplicar fix + test + changelog
git add <files>
git commit -m "fix: <descripcion>"

git switch stable
git merge --ff-only fix/<area>
git tag -a vX.Y.Z -m "release vX.Y.Z"
git push origin stable vX.Y.Z

git switch main
git pull origin main
git merge --ff-only stable
git push origin main
```

## Cambios Que Tocan Containers LXD

Hoy `laia-release` versiona código en `/opt/laia-vX.Y.Z`, pero no versiona ni
reconstruye imágenes LXD automáticamente.

Si un release toca cualquiera de estos paths:

- `services/agora-backend/`
- `services/laia-executor/`
- `.laia-core/`
- `infra/lxd/image-build/`

entonces, en la máquina destino, reconstruye imágenes antes de validar:

```bash
cd /home/jorge/LAIA
sudo LAIA_ROOT=/home/jorge/LAIA bash infra/lxd/scripts/rebuild-2-images.sh
```

Después recrea o verifica los containers que dependan de esas imágenes según
el flujo operativo del momento.

## Primer Install En Prod

En una máquina limpia:

```bash
curl -fsSL https://raw.githubusercontent.com/JorgeMP-3/laia-arch/stable/install.sh \
  | sudo -E bash -s -- --mode install --yes
```

Para dev explícito:

```bash
curl -fsSL https://raw.githubusercontent.com/JorgeMP-3/laia-arch/stable/install.sh \
  | sudo -E bash -s -- --branch main --mode install --yes
```

## Backups

Antes de mover datos reales al ThinkStation, configura backup de `/srv/laia/`.
Este flujo de release no sustituye backups.
