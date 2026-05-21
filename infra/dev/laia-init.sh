#!/usr/bin/env bash
# laia-init.sh — interactive wizard that takes a clean host from
# "LXD installed + repo cloned" to "AGORA + LAIA + first user provisioned".
#
# Orchestrates:
#   1) host pre-flight (laia-init-checks.sh)
#   2) LXD defaults    (infra/lxd/scripts/init-defaults.sh)
#   3) auth.json check (optional copy / placeholder / skip)
#   4) admin + LLM provider + first agent slug prompts
#   5) rebuild-2 build images   (skippable with --skip-images)
#   6) rebuild-3 provision agora
#   7) seed-base-skills.sh + rebuild-4 first user
#   8) preflight + smoke-test verification
#
# Modes:
#   --non-interactive   Read inputs from env vars; fail on missing required ones.
#   --dry-run           Print the plan and run only the checks; skip every
#                       destructive step.
#   --skip-images       Assume rebuild-2 already ran; skip it.
#   --skip-first-user   Stop after rebuild-3 (no provisioning a first user).
#
# Required env vars in --non-interactive mode:
#   AGORA_ADMIN_USERNAME, AGORA_ADMIN_PASSWORD,
#   AGORA_LLM_PROVIDER, AGORA_FIRST_SLUG
#   AGORA_TELEGRAM_TOKEN is optional.

set -uo pipefail

# Defaults.
NON_INTERACTIVE=0
DRY_RUN=0
SKIP_IMAGES=0
SKIP_FIRST_USER=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --non-interactive) NON_INTERACTIVE=1; shift;;
    --dry-run)         DRY_RUN=1; shift;;
    --skip-images)     SKIP_IMAGES=1; shift;;
    --skip-first-user) SKIP_FIRST_USER=1; shift;;
    -h|--help)
      sed -n '1,28p' "$0"; exit 0;;
    *) echo "Unknown arg: $1" >&2; exit 2;;
  esac
done

ORIG_USER="${SUDO_USER:-${LAIA_ADMIN_USER:-${USER:-}}}"
if [[ -z "$ORIG_USER" || "$ORIG_USER" == "root" ]]; then
  ORIG_USER=$(getent passwd | awk -F: '$3 >= 1000 && $3 < 65534 {print $1; exit}')
fi
[[ -n "$ORIG_USER" ]] || { echo "Cannot determine ORIG_USER (set SUDO_USER or LAIA_ADMIN_USER)" >&2; exit 1; }
ORIG_HOME=$(getent passwd "$ORIG_USER" 2>/dev/null | cut -d: -f6)
[[ -z "$ORIG_HOME" ]] && ORIG_HOME="/home/$ORIG_USER"

REPO="${LAIA_ROOT:-$ORIG_HOME/LAIA}"
[[ -d "$REPO" ]] || { echo "[laia-init] $REPO no existe (LAIA_ROOT)" >&2; exit 1; }

if [[ -t 1 ]]; then
  # ANSI-C quoting: real ESC chars in the var so `cat <<EOF` also renders.
  GRN=$'\033[1;32m'; YEL=$'\033[1;33m'; RED=$'\033[1;31m'
  CYN=$'\033[1;36m'; BLD=$'\033[1m'; RST=$'\033[0m'
else
  GRN=''; YEL=''; RED=''; CYN=''; BLD=''; RST=''
fi

section() {
  printf "\n${BLD}${CYN}== %s ==${RST}\n" "$*"
}
ok()   { printf "  ${GRN}✓${RST} %s\n" "$*"; }
warn() { printf "  ${YEL}⚠${RST} %s\n" "$*"; }
err()  { printf "  ${RED}✗${RST} %s\n" "$*" >&2; }

ask() {
  # $1=prompt $2=default(optional); echoes value. In non-interactive,
  # falls back to default and prints a one-line summary.
  local prompt="$1" default="${2:-}"
  if [[ $NON_INTERACTIVE -eq 1 ]]; then
    printf "%s: %s\n" "$prompt" "${default:-<empty>}" >&2
    echo "$default"
    return
  fi
  local val
  if [[ -n "$default" ]]; then
    read -r -p "$prompt [$default]: " val
    echo "${val:-$default}"
  else
    read -r -p "$prompt: " val
    echo "$val"
  fi
}

ask_secret() {
  local prompt="$1" default="${2:-}"
  if [[ $NON_INTERACTIVE -eq 1 ]]; then
    echo "$default"
    return
  fi
  local val
  # ``read -s`` swallows the Enter keystroke; without an explicit newline
  # to stderr the next prompt collides with this one on the same line.
  # stdout is captured by ``$(ask_secret ...)`` so we must write to stderr.
  read -r -s -p "$prompt: " val
  printf '\n' >&2
  echo "${val:-$default}"
}

# ── 1/8 Preflight checks ────────────────────────────────────────────────────
section "1/8 Preflight checks"
if ! bash "$REPO/infra/dev/laia-init-checks.sh"; then
  err "blockers detectados arriba; soluciona y reintenta"
  exit 1
fi

# ── 2/8 LXD defaults ────────────────────────────────────────────────────────
section "2/8 LXD defaults (network + storage + profiles)"
if [[ $DRY_RUN -eq 1 ]]; then
  ok "[dry-run] saltando init-defaults.sh"
else
  if [[ -x "$REPO/infra/lxd/scripts/init-defaults.sh" ]]; then
    sudo bash "$REPO/infra/lxd/scripts/init-defaults.sh" || {
      err "init-defaults.sh falló"; exit 1;
    }
  else
    warn "init-defaults.sh no encontrado (saltando)"
  fi
fi

# ── 3/8 auth.json ───────────────────────────────────────────────────────────
section "3/8 OAuth admin (~/.laia/auth.json)"
AUTH_JSON="$ORIG_HOME/.laia/auth.json"
if [[ -f "$AUTH_JSON" ]]; then
  ok "auth.json presente en $AUTH_JSON"
elif [[ $NON_INTERACTIVE -eq 1 ]]; then
  warn "auth.json ausente (modo no-interactivo: continuamos sin tocarlo)"
else
  echo "  No se encontró $AUTH_JSON."
  echo "    [1] Copiar desde otra ruta"
  echo "    [2] Generar placeholder vacío"
  echo "    [3] Skip (configurarás más tarde con \`laia auth\`)"
  choice="$(ask 'Opción' '3')"
  case "$choice" in
    1)
      src="$(ask 'Ruta del auth.json a copiar' '')"
      if [[ -f "$src" ]]; then
        mkdir -p "$(dirname "$AUTH_JSON")"
        cp "$src" "$AUTH_JSON" && ok "auth.json copiado"
      else
        err "$src no es un fichero — saltando"
      fi
      ;;
    2)
      mkdir -p "$(dirname "$AUTH_JSON")"
      printf '{}\n' > "$AUTH_JSON"
      ok "placeholder vacío creado en $AUTH_JSON"
      ;;
    *)
      warn "saltando — recuerda correr 'laia auth' antes del primer chat"
      ;;
  esac
fi

# ── 4/8 Configuración ───────────────────────────────────────────────────────
section "4/8 Configuración"
if [[ $NON_INTERACTIVE -eq 1 ]]; then
  ADMIN_USERNAME="${AGORA_ADMIN_USERNAME:-}"
  ADMIN_PASSWORD="${AGORA_ADMIN_PASSWORD:-}"
  LLM_PROVIDER="${AGORA_LLM_PROVIDER:-}"
  TELEGRAM_TOKEN="${AGORA_TELEGRAM_TOKEN:-}"
  FIRST_SLUG="${AGORA_FIRST_SLUG:-}"
  for var in ADMIN_USERNAME ADMIN_PASSWORD LLM_PROVIDER FIRST_SLUG; do
    if [[ -z "${!var}" ]]; then
      err "$var requerido en modo --non-interactive"
      exit 1
    fi
  done
else
  ADMIN_USERNAME="$(ask 'Username admin' 'jorge')"
  ADMIN_PASSWORD="$(ask_secret 'Password admin' 'dev-admin')"
  LLM_PROVIDER="$(ask 'LLM provider' 'openai-codex')"
  TELEGRAM_TOKEN="$(ask 'Telegram bot token (opcional)' '')"
  FIRST_SLUG="$(ask 'Slug del primer agente' "$ADMIN_USERNAME-dev")"
fi

ok "admin=$ADMIN_USERNAME slug=$FIRST_SLUG provider=$LLM_PROVIDER"

# Persist operator-supplied env to /srv/laia/agora/.env so the systemd
# unit inside laia-agora (EnvironmentFile=-/opt/agora/data/.env) loads
# them at boot. Today this carries the Telegram token; future secrets
# (custom default provider, MCP URLs, …) go here too.
HOST_DATA_DIR_DEFAULT="/srv/laia/agora"
ENV_HOST_FILE="${HOST_DATA_DIR:-$HOST_DATA_DIR_DEFAULT}/.env"
if [[ -n "$TELEGRAM_TOKEN" ]]; then
  if [[ $DRY_RUN -eq 1 ]]; then
    ok "[dry-run] escribiría TELEGRAM_TOKEN en $ENV_HOST_FILE"
  else
    sudo mkdir -p "$(dirname "$ENV_HOST_FILE")"
    # Idempotent rewrite — preserve other keys, replace AGORA_TELEGRAM_TOKEN.
    sudo bash -c "
      tmp=\$(mktemp)
      if [[ -f '$ENV_HOST_FILE' ]]; then
        grep -v '^AGORA_TELEGRAM_TOKEN=' '$ENV_HOST_FILE' > \$tmp || true
      fi
      printf 'AGORA_TELEGRAM_TOKEN=%s\n' '$TELEGRAM_TOKEN' >> \$tmp
      mv \$tmp '$ENV_HOST_FILE'
      chmod 600 '$ENV_HOST_FILE'
    "
    ok "Telegram token persistido en $ENV_HOST_FILE (modo 600)"
  fi
fi

# ── 5/8 rebuild-2 build images ─────────────────────────────────────────────
section "5/8 Build images (rebuild-2)"
if [[ $DRY_RUN -eq 1 ]]; then
  ok "[dry-run] saltando rebuild-2"
elif [[ $SKIP_IMAGES -eq 1 ]]; then
  warn "saltando rebuild-2 (--skip-images)"
else
  if ! sudo bash "$REPO/infra/lxd/scripts/rebuild-2-images.sh"; then
    err "rebuild-2 falló — revisa /tmp/build-*.log"
    if [[ $NON_INTERACTIVE -eq 1 ]]; then
      exit 1
    fi
    retry="$(ask 'Reintentar (R), saltar (S), abortar (A)?' 'A')"
    case "${retry^^}" in
      R) sudo bash "$REPO/infra/lxd/scripts/rebuild-2-images.sh" || exit 1;;
      S) warn "saltando, continuamos";;
      *) exit 1;;
    esac
  fi
fi

# ── 6/8 rebuild-3 provision agora ──────────────────────────────────────────
section "6/8 Provision laia-agora"
if [[ $DRY_RUN -eq 1 ]]; then
  ok "[dry-run] saltando rebuild-3"
else
  sudo bash "$REPO/infra/lxd/scripts/rebuild-3-provision-agora.sh" || {
    err "rebuild-3 falló"; exit 1;
  }
fi

# ── 7/8 seed skills + first user ───────────────────────────────────────────
section "7/8 Seed catálogo + provisionar primer user"
if [[ $DRY_RUN -eq 1 ]]; then
  ok "[dry-run] saltando seed + rebuild-4"
elif [[ $SKIP_FIRST_USER -eq 1 ]]; then
  warn "saltando primer user (--skip-first-user)"
else
  bash "$REPO/infra/dev/seed-base-skills.sh" \
    || warn "seed-base-skills.sh devolvió error (catálogo puede tener huecos)"
  sudo bash "$REPO/infra/lxd/scripts/rebuild-4-first-user.sh" \
    --slug "$FIRST_SLUG" --username "$ADMIN_USERNAME" \
    --password "$ADMIN_PASSWORD" --provider "$LLM_PROVIDER" \
    || { err "rebuild-4 falló"; exit 1; }
fi

# ── 8/8 Verification ───────────────────────────────────────────────────────
section "8/8 Verificación"
if [[ $DRY_RUN -eq 1 ]]; then
  ok "[dry-run] saltando preflight + smoke"
else
  bash "$REPO/infra/dev/preflight.sh" || warn "preflight reportó warnings"
  if [[ $SKIP_FIRST_USER -eq 0 ]]; then
    bash "$REPO/infra/dev/smoke-test.sh" --slug "$FIRST_SLUG" \
      || warn "smoke-test reportó fallos"
  fi
fi

cat <<EOF

${BLD}=== Listo ===${RST}
  Backend API:  http://127.0.0.1:8088
  TUI:          python3 $REPO/infra/dev/agora-control-center-tui.py
  Chat:         bash $REPO/infra/dev/chat-with-deployed.sh --slug $FIRST_SLUG
  Hablar con LAIA:
                TUI → pestaña LAIA, o
                curl -sN -H "Authorization: Bearer dev-admin-token" \\
                     -H "Content-Type: application/json" \\
                     -X POST http://127.0.0.1:8088/api/laia/chat \\
                     -d '{"message":"Dame un overview del ecosistema"}'

EOF
