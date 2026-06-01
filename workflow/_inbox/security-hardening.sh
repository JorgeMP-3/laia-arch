#!/usr/bin/env bash
#
# LAIA · Script de hardening de seguridad — host `doyouwin-server`
# ----------------------------------------------------------------
# Acompaña a: workflow/_inbox/security-hardening-plan.md
# Autor: Claude (Opus 4.8) · 2026-06-01
#
# QUÉ HACE (los pasos P0/P1.1 del plan — rápidos y seguros):
#   1) Cierra permisos de secretos en ~/.laia (idempotente)
#   2) Desactiva PasswordAuthentication SSH + endurece (con red anti-autobloqueo)
#   3) Instala y activa Fail2Ban (jail sshd)
#   4) Revisa / opcionalmente resetea el password admin de Nextcloud
#   5) Imprime un informe de verificación final
#
# QUÉ NO HACE (decisiones — ver el plan §P1.2/P1.3/P2):
#   · Rebind del proxy AGORA :8088   · TLS/reverse-proxy   · Backups restic   · 2FA/ACLs Tailscale
#   (Internet YA está bloqueado por UFW; esos pasos son hardening adicional, no urgentes.)
#
# USO:
#   bash security-hardening.sh          # interactivo, confirma cada bloque (recomendado)
#   AUTO=1 bash security-hardening.sh   # sin preguntar (salvo el reset de Nextcloud)
#
# REQUISITOS: ejecutar como laia-arch; usa sudo (pedirá la contraseña una vez).
# SEGURIDAD : valida `sshd -t` antes de recargar y NO cierra password-auth si no hay
#             ni sesión Tailscale ni clave en authorized_keys (evita dejarte fuera).

set -uo pipefail

# ---------- helpers ----------
b(){ printf '\033[1m%s\033[0m' "$*"; }
ok(){   printf '  \033[32m\xe2\x9c\x93\033[0m %s\n' "$*"; }
warn(){ printf '  \033[33m\xe2\x9a\xa0\033[0m %s\n' "$*"; }
err(){  printf '  \033[31m\xe2\x9c\x97\033[0m %s\n' "$*" >&2; }
sect(){ printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }
ask(){  # ask "texto"  -> 0 = sí
  [ "${AUTO:-0}" = "1" ] && return 0
  local a; read -r -p "  ¿$1? [y/N] " a; [ "$a" = y ] || [ "$a" = Y ]
}
ts(){ date +%Y%m%d-%H%M%S; }

[ "$(id -un)" = laia-arch ] || { err "Ejecútalo como laia-arch (no root, no otro usuario)."; exit 1; }
printf '\n%s — %s\n' "$(b 'LAIA · Hardening de doyouwin-server')" "$(date '+%F %T')"

# ---------- preflight: ruta de rescate SSH ----------
sect "Preflight"
RESCUE=0
if tailscale status >/dev/null 2>&1; then ok "Tailscale activo -> ruta de rescate SSH disponible"; RESCUE=1
else warn "Tailscale NO responde"; fi
if [ -s "$HOME/.ssh/authorized_keys" ]; then ok "authorized_keys con claves -> ruta de rescate por clave"; RESCUE=1
else warn "authorized_keys vacio"; fi
[ "$RESCUE" = 1 ] || warn "Sin ruta de rescate: el bloque SSH NO recargara (para no dejarte fuera)."

# ---------- 1) Secretos (F1/F2) ----------
sect "1) Permisos de secretos (F1/F2)"
if ask "cerrar permisos de \$HOME, ~/.laia y secretos (0700/0600)"; then
  chmod 700 "$HOME" "$HOME/.laia" 2>/dev/null && ok "0700 en \$HOME y ~/.laia" || warn "no pude chmod los directorios"
  for f in "$HOME/.laia/auth.json" "$HOME/.laia/atlas.yaml" "$HOME/.laia/config.yaml" \
           "$HOME/.laia/atlas.yaml.bak-pre-pr1" "$HOME/LAIA-ARCH/.env.paths"; do
    [ -e "$f" ] && { chmod 600 "$f" && ok "0600 ${f/#$HOME/~}"; }
  done
  bad=$(find "$HOME/.laia" "$HOME/LAIA-ARCH" /srv/laia -maxdepth 3 \
        \( -name 'auth.json' -o -name '.env' -o -name '*.key' \) 2>/dev/null \
        -exec stat -c '%A %n' {} \; | grep -vE '^-rw-------' || true)
  [ -z "$bad" ] && ok "barrido: 0 secretos legibles por otros" || { warn "revisar:"; printf '    %s\n' "$bad"; }
else warn "saltado"; fi

# ---------- 2) Hardening SSH (F3/F4) ----------
sect "2) Hardening SSH (F3/F4)"
echo "  Estado actual:"; sudo sshd -T 2>/dev/null | grep -Ei 'passwordauthentication|permitrootlogin|allowusers' | sed 's/^/    /' || true
if ask "desactivar PasswordAuthentication + endurecer SSH"; then
  CI=/etc/ssh/sshd_config.d/50-cloud-init.conf
  DROPIN=/etc/ssh/sshd_config.d/99-laia-hardening.conf
  [ -f "$CI" ] && sudo cp -a "$CI" "$CI.bak-$(ts)" && ok "backup de 50-cloud-init.conf"
  # Gotcha: sshd usa el PRIMER valor de cada clave; 50-cloud-init.conf se lee antes que 99-*
  # -> hay que apagar password-auth en el propio 50, no solo en un drop-in 99.
  if [ -f "$CI" ] && sudo grep -qiE '^[[:space:]]*PasswordAuthentication' "$CI"; then
    sudo sed -i 's/^[[:space:]]*PasswordAuthentication.*/PasswordAuthentication no/I' "$CI" \
      && ok "50-cloud-init.conf -> PasswordAuthentication no"
  fi
  sudo tee "$DROPIN" >/dev/null <<'EOF'
# LAIA hardening — gestionado por security-hardening.sh, no editar a mano
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
AllowUsers laia-arch
MaxAuthTries 3
X11Forwarding no
EOF
  ok "escrito $DROPIN"
  if sudo sshd -t; then
    ok "sshd -t OK (sintaxis valida)"
    if [ "$RESCUE" = 1 ]; then
      sudo systemctl reload ssh && ok "ssh recargado"
    else
      err "Sin ruta de rescate -> NO recargo. Anade una clave a ~/.ssh/authorized_keys y: sudo systemctl reload ssh"
    fi
  else
    err "sshd -t FALLO -> revierto el drop-in para no romper SSH"; sudo rm -f "$DROPIN"
  fi
  echo "  Resultado:"; sudo sshd -T | grep -Ei 'passwordauthentication|permitrootlogin|allowusers|x11forwarding' | sed 's/^/    /'
else warn "saltado"; fi

# ---------- 3) Fail2Ban (F10) ----------
sect "3) Fail2Ban (F10)"
if ask "instalar y activar Fail2Ban (jail sshd)"; then
  sudo apt-get update -qq && sudo apt-get install -y fail2ban >/dev/null && ok "fail2ban instalado"
  sudo tee /etc/fail2ban/jail.d/sshd.local >/dev/null <<'EOF'
[sshd]
enabled  = true
backend  = systemd
maxretry = 4
findtime = 10m
bantime  = 1h
EOF
  sudo systemctl enable --now fail2ban >/dev/null 2>&1 && ok "fail2ban activo"
  sleep 1; sudo fail2ban-client status sshd 2>/dev/null | sed 's/^/    /' || warn "jail sshd aun inicializando"
else warn "saltado"; fi

# ---------- 4) Nextcloud (F11) ----------
sect "4) Nextcloud admin (F11)"
if command -v nextcloud.occ >/dev/null 2>&1 || [ -x /snap/bin/nextcloud.occ ]; then
  sudo nextcloud.occ user:lastlogin admin 2>/dev/null | sed 's/^/    /' || true
  if ask "resetear el password admin de Nextcloud AHORA (interactivo)"; then
    sudo nextcloud.occ user:resetpassword admin
  fi
else warn "nextcloud.occ no encontrado -> saltado"; fi

# ---------- 5) Informe ----------
sect "5) Informe de verificacion"
echo "  SSH:"; sudo sshd -T 2>/dev/null | grep -Ei 'passwordauthentication|permitrootlogin|allowusers' | sed 's/^/    /'
echo "  Fail2Ban:"; printf '    %s\n' "$(systemctl is-active fail2ban 2>/dev/null)"
echo "  UFW:"; sudo ufw status 2>/dev/null | head -n1 | sed 's/^/    /'
echo "  Secretos legibles por otros:"
bad=$(find "$HOME/.laia" /srv/laia -maxdepth 3 \( -name 'auth.json' -o -name '.env' \) 2>/dev/null -exec stat -c '%A %n' {} \; | grep -vE '^-rw-------' || true)
[ -z "$bad" ] && echo "    ninguno (ok)" || printf '    %s\n' "$bad"

cat <<'NOTE'

------------------------------------------------------------------
Pendiente (decisiones — ver workflow/_inbox/security-hardening-plan.md):
  - P1.2  Rebind proxy AGORA :8088 fuera de 0.0.0.0   (¿quien lo consume?)
  - P1.3  TLS (tailscale serve | Caddy)
  - P2.1  Backups restic a remoto inmutable
  - P2.2  Tailscale: 2FA + ACLs + key-expiry (consola web)
Internet YA esta bloqueado por UFW; lo de arriba es hardening adicional, no urgente.
------------------------------------------------------------------
NOTE
