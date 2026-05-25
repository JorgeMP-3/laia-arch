# VM smoke — install + clone end-to-end

- **Fecha**: 2026-05-25
- **Owner**: jorge (operador), claude-code (autor del script)
- **Estado**: aprobado — Jorge corre cuando quiera validación real

## Contexto

Tras el hardening pre-Fase-5 (5 CRITICAL + 4 HIGH fixes en commits
`9c20c3fe` y `a1fd7546`), la suite `tests/installer/run_all.sh` da 30/30
verde. Pero los tests bash son shallow: mockean LXD, sshpass, rsync. La
única forma de tener **100% de garantía** de que installer + cloner
funcionan profesional y completamente es correrlos en una VM Ubuntu
limpia.

Este documento es la guía para que Jorge corra el smoke real, qué
verificar, y dónde mirar si algo va mal.

## Setup VM

Recomendado: **Multipass** o **LXC** con perfil bridged (LXD-inside-LXD
puede tener fricciones; Multipass usa qemu/kvm y aísla limpio).

```bash
# Multipass (Ubuntu 26.04 LTS, 4 GB RAM, 30 GB disk):
multipass launch 26.04 --name laia-smoke --memory 4G --disk 30G --cpus 2

# Entrar:
multipass shell laia-smoke

# Dentro de la VM, instala git y curl si no están:
sudo apt-get update && sudo apt-get install -y git curl
```

## Smoke 1 — Install end-to-end (~10-15 min)

Dentro de la VM:

```bash
# Bootstrap completo desde el repo. Usa la rama feat/installer-wizard
# hasta que mergees a main.
curl -fsSL \
  https://raw.githubusercontent.com/JorgeMP-3/laia-arch/feat/installer-wizard/install.sh \
  | sudo -E bash -s -- --mode install --yes
```

**Verificaciones (qué debe haber pasado)**:

1. `/opt/laia` existe como symlink → `/opt/laia-vX.Y.Z`.
2. `/srv/laia/agora/agora.db` existe con ≥ 10 tablas:
   ```bash
   sudo sqlite3 /srv/laia/agora/agora.db ".tables" | tr ' ' '\n' | wc -l
   ```
3. `lxc list` muestra el container `laia-agora` con state RUNNING.
4. `curl -fsS http://127.0.0.1:8088/api/health` retorna JSON con `"ok": true`.
5. `cat ~/.laia/.admin-credentials` muestra usuario + password generados.
6. `bin/laia --version` imprime una versión válida.
7. `bin/laia diagnose` no reporta errores.

**Si algo falla a mitad**:
- El rollback automático debería haber restaurado el symlink al estado
  pre-install (si había uno) o haberlo borrado.
- Mira `/tmp/build-*.log` (logs de LXD image build).
- Mira `~/.cache/laia-wizard.log` (log del wizard).

## Smoke 2 — Clone desde la VM smoke a una segunda VM (~15-20 min)

**Atención a los placeholders**: cada `<algo>` en los snippets de abajo
es una variable que tienes que sustituir por un valor real ANTES de
pegar el comando. Pegar literal `<algo>` te dará errores de bash
("No such file or directory"). Si dudas, copia la línea a un editor,
sustituye, y pega después.

### Paso 1: asegúrate de tener una SSH key

```bash
ls -la ~/.ssh/id_ed25519.pub ~/.ssh/id_rsa.pub 2>/dev/null
```

Si no hay ninguna, genera una nueva (sin passphrase para automatizar):

```bash
ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519
```

Toma nota de cuál usas (la mayoría usará `~/.ssh/id_ed25519.pub`).

### Paso 2: averigua la IP de la VM origen

```bash
multipass info laia-smoke | grep IPv4
```

Te dará algo tipo `IPv4: 10.151.42.50`. Apunta esa IP — la usarás en
el paso 4 sustituyendo `<IP-LAIA-SMOKE>`.

### Paso 3: levanta la VM destino y copia tu key a la origen

```bash
# Levanta destino (si no la tienes ya):
multipass launch 26.04 --name laia-smoke-clone --memory 4G --disk 30G --cpus 2

# Copia tu key pública a laia-smoke (la VM ORIGEN) para que clone pueda
# autenticarse por SSH sin password. Sustituye id_ed25519.pub por la
# que tengas si es distinta:
multipass exec laia-smoke -- bash -c \
  'mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys' \
  < ~/.ssh/id_ed25519.pub

# Verifica que SSH funciona desde tu host (NO desde la VM):
ssh -o StrictHostKeyChecking=accept-new ubuntu@<IP-LAIA-SMOKE> "hostname"
# Debe imprimir 'laia-smoke' sin pedirte password.
```

### Paso 4: entra a laia-smoke-clone y lanza el clone

```bash
multipass shell laia-smoke-clone
```

Dentro de la VM destino, sustituye `<IP-LAIA-SMOKE>` por la IP del
paso 2 (ejemplo: `10.151.42.50`):

```bash
curl -fsSL \
  https://raw.githubusercontent.com/JorgeMP-3/laia-arch/feat/installer-wizard/install.sh \
  | sudo -E bash -s -- --mode clone --source ubuntu@<IP-LAIA-SMOKE> --yes
```

Si el `<IP-LAIA-SMOKE>` queda literal el comando falla con
`bash: IP-LAIA-SMOKE: No such file or directory`. Sustituye SIEMPRE
antes de pegar.

**Verificaciones**:

1. Las mismas que el smoke 1 (LAIA instalado y health OK).
2. Adicional: `/srv/laia/agora/agora.db` debe tener los mismos `users` y
   `agents` que el origen (chequea `sqlite3 select count(*) from users;`
   en ambos hosts).
3. `~/.laia/.clone-state/*.done` existe — markers de fases completadas.
4. `bin/laia diagnose` no reporta inconsistencias.
5. **No debe haber password expuesto** en `ps -ef` durante el clone
   (regression guard del fix de SSHPASS).

## Smoke 3 — Resume tras Ctrl+C (~5 min)

Sustituye `<IP-LAIA-SMOKE>` por la IP real de la VM origen.

```bash
# Dentro de laia-smoke-clone, lanza un clone y mata con Ctrl+C tras 30s.
# El kill simula una caída de red o el operador cancelando.
sudo bash -c '
  /home/ubuntu/LAIA/bin/laia clone --source ubuntu@<IP-LAIA-SMOKE> --yes &
  pid=$!
  sleep 30
  kill -INT "$pid"
  wait "$pid" 2>/dev/null
'

# Las phases que SÍ completaron deben tener marker (archivo vacío .done):
ls -la ~/.laia/.clone-state/ 2>/dev/null || sudo ls -la /root/.laia/.clone-state/

# Re-ejecuta con --resume — debe saltar las phases ya marcadas:
sudo /home/ubuntu/LAIA/bin/laia clone --source ubuntu@<IP-LAIA-SMOKE> --yes --resume

# El log debe mostrar, para cada phase con marker:
#   "Phase H xxx data already complete (resume); skipping"
```

## Cómo reportar resultados

Si algo falla:

1. Captura el log de pantalla (`script` o copy/paste).
2. Adjunta `~/.cache/laia-wizard.log`.
3. Para clone: adjunta `~/.cache/laia-wizard/runs/*.log` (logs por
   step_id).
4. Abre una entrada en `workflow/problems.md` con la repro.

Si todo va bien:

1. Anótalo en `workflow/changelog.md`.
2. Cierra la entrada `clone-ssh-setup-mode-continues` si confirmamos la
   semántica final.
3. Pasamos a Fase 5 (headless TOML + pirámide de tests pytest-first).

## Notas

- Las VMs se pueden destruir y recrear:
  `multipass delete laia-smoke laia-smoke-clone && multipass purge`.
- Si tu firewall/VPN bloquea SSH entre VMs, usa `multipass info` para
  ver IPs y ejecuta `ssh ubuntu@<ip>` desde la VM cliente para validar
  conectividad antes del smoke 2.
