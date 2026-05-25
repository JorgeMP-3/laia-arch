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

Levanta una segunda VM (`laia-smoke-clone`) limpia, copia tu SSH key de
la VM cliente a la VM `laia-smoke` (origen), y dentro de la nueva VM:

```bash
# En la VM cliente, copia tu key a la VM origen:
multipass exec laia-smoke -- bash -c 'mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys' < ~/.ssh/id_ed25519.pub

# Dentro de laia-smoke-clone:
curl -fsSL \
  https://raw.githubusercontent.com/JorgeMP-3/laia-arch/feat/installer-wizard/install.sh \
  | sudo -E bash -s -- --mode clone --source ubuntu@<IP-de-laia-smoke> --yes
```

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

```bash
# Lanza un clone y mata con Ctrl+C tras 30 s:
sudo bash -c '
  /home/ubuntu/LAIA/bin/laia clone --source ubuntu@<IP-origen> --yes &
  sleep 30
  kill -INT $!
  wait $! 2>/dev/null
'

# Las phases que SÍ completaron deben tener marker:
ls ~/.laia/.clone-state/

# Re-ejecuta con --resume:
sudo /home/ubuntu/LAIA/bin/laia clone --source ubuntu@<IP-origen> --yes --resume

# El log debe mostrar:
#   "Phase H xxx data already complete (resume); skipping"
# para cada phase que YA estaba marcada.
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
