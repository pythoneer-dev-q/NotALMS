\#!/usr/bin/env bash
# scripts/install.sh — установка и обновление notalms
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODE_FILE="$ROOT/.ntlms-mode"
VENV_DIR="$ROOT/.venv"
CERT_DIR="$ROOT/certs"

say()  { echo -e "\n\033[1;36m== $1\033[0m"; }
info() { echo "   $1"; }
ok()   { echo -e "   \033[0;32m+ $1\033[0m"; }
warn() { echo -e "   \033[0;33m! $1\033[0m"; }
die()  { echo -e "\033[0;31mERROR: $1\033[0m"; exit 1; }

ask() {
  local q="$1" d="${2:-}"
  read -rp "$q${d:+ [$d]}: " a
  echo "${a:-$d}"
}

SUDO="$( [ "$(id -u)" = 0 ] && echo '' || echo sudo )"

open_firewall_ports() {
  if command -v ufw >/dev/null 2>&1 && $SUDO ufw status 2>/dev/null | grep -qi active; then
    for p in "$@"; do $SUDO ufw allow "$p"/tcp >/dev/null 2>&1 || true; done
    ok "ufw: открыл tcp $*"
  fi
}

cat <<'EOF'

  NotALMS — умный установщик
  ---------------------------
  Автоматически подтягивает существующую конфигурацию,
  генерирует недостающие модули и настраивает систему.

EOF

# ============ шаг 1: способ запуска ============
say "шаг 1/8 — способ запуска"
EXISTING_MODE=""
[ -f "$MODE_FILE" ] && EXISTING_MODE="$(cat "$MODE_FILE" 2>/dev/null || true)"

if [ -n "$EXISTING_MODE" ]; then
  MODE="$(ask "  способ запуска (docker/venv)" "$EXISTING_MODE")"
else
  MODE="$(ask "  способ запуска (docker/venv)" "${NTLMS_MODE:-docker}")"
fi
case "$MODE" in docker|venv) ;; *) die "не понимаю '$MODE', нужно docker или venv" ;; esac
echo "$MODE" > "$MODE_FILE"
ok "способ: $MODE"

# ============ шаг 2: окружение и зависимости ============
say "шаг 2/8 — окружение"
if [ "$MODE" = docker ]; then
  if [ -f "$ROOT/scripts/install_docker.sh" ]; then
    . "$ROOT/scripts/install_docker.sh"
    install_docker_engine
    resolve_docker_cmd
  else
    command -v docker >/dev/null || die "docker не найден"
    DOCKER="docker"
  fi
  ok "docker готов"
else
  command -v python3 >/dev/null || die "python3 не найден (sudo apt install python3 python3-venv)"
  command -v systemctl >/dev/null || die "systemd не найден"
  command -v openssl >/dev/null || die "openssl не найден"

  # проверка python3-venv
  if ! python3 -m venv --help >/dev/null 2>&1; then
    warn "python3-venv не найден, пытаюсь установить..."
    $SUDO apt-get update && $SUDO apt-get install -y python3-venv python3-pip || die "Установите вручную: sudo apt install python3-venv python3-pip"
  fi

  # Создание/пропуск venv
  if [ -f "$VENV_DIR/bin/uvicorn" ] && [ -f "$VENV_DIR/bin/python" ]; then
    ok "venv уже существует и инициализирован ($VENV_DIR)"
    if ask "  переустановить зависимости заново? (y/N)" "N" | grep -qi '^y'; then
      info "обновляю зависимости..."
      "$VENV_DIR/bin/pip" install --upgrade pip setuptools wheel
      "$VENV_DIR/bin/pip" install fastapi uvicorn motor python-dotenv "passlib[bcrypt]" "python-jose[cryptography]" slowapi redis aiogram pydantic-settings
      ok "зависимости обновлены"
    fi
  else
    info "создаю venv в $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --upgrade pip setuptools wheel
    "$VENV_DIR/bin/pip" install fastapi uvicorn motor python-dotenv "passlib[bcrypt]" "python-jose[cryptography]" slowapi redis aiogram pydantic-settings
    ok "venv и зависимости установлены"
  fi
fi

# ============ шаг 3: автогенерация локальных модулей ============
say "шаг 3/8 — проверка локальных модулей python"

# Гарантируем структуру папок и пакетов
mkdir -p "$ROOT/back/auth/bot/config"
mkdir -p "$ROOT/back/server/server_configs"
touch "$ROOT/back/__init__.py" 2>/dev/null || true
touch "$ROOT/back/auth/__init__.py" 2>/dev/null || true
touch "$ROOT/back/auth/bot/__init__.py" 2>/dev/null || true
touch "$ROOT/back/auth/bot/config/__init__.py" 2>/dev/null || true
touch "$ROOT/back/server/__init__.py" 2>/dev/null || true
touch "$ROOT/back/server/server_configs/__init__.py" 2>/dev/null || true

# Создаем authConfig.py, если отсутствует
if [ ! -f "$ROOT/back/auth/bot/config/authConfig.py" ]; then
  cat << 'EOF' > "$ROOT/back/auth/bot/config/authConfig.py"
# ! back/auth/bot/config/authConfig.py
# локальный конфиг бота, значения берутся из .env (файл gitignored по правилу config/)
from back.server.server_configs.settings import settings

TOKEN = settings.bot_token
MONGO_URI = settings.mongo_uri
MONGO_DB_NAME = settings.bot_db_name
OTPLEN = settings.otplen
EOF
  ok "сгенерирован недостающий back/auth/bot/config/authConfig.py"
else
  ok "back/auth/bot/config/authConfig.py на месте"
fi

# ============ шаг 4: домены и порты ============
say "шаг 4/8 — домены и порты"
PREV_FRONT_PORT="$(grep -E '^FRONT_PORT=' "$ROOT/.env" 2>/dev/null | cut -d= -f2 || true)"
PREV_BACK_PORT="$(grep -E '^PORT=' "$ROOT/.env" 2>/dev/null | cut -d= -f2 || true)"

DETECT_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
[ -n "${DETECT_IP:-}" ] || DETECT_IP='127.0.0.1'

if [ -f "$ROOT/.env" ] && [ -n "$PREV_FRONT_PORT" ]; then
  info "найдены сохраненные порты: фронт=$PREV_FRONT_PORT, api=$PREV_BACK_PORT"
  USE_EXISTING_PORTS="$(ask '  использовать их? (Y/n)' 'Y')"
else
  USE_EXISTING_PORTS="n"
fi

if echo "$USE_EXISTING_PORTS" | grep -qi '^y'; then
  FRONT_PORT="$PREV_FRONT_PORT"
  BACK_PORT="$PREV_BACK_PORT"
  FRONT_DOMAIN=""
  BACK_DOMAIN=""
else
  FRONT_DOMAIN="$(ask "  домен сайта (enter = ip $DETECT_IP)" "${NTLMS_FRONT_DOMAIN:-}")"
  BACK_DOMAIN="$(ask '  домен api (пусто = api на том же домене/ip)' "${NTLMS_BACK_DOMAIN:-}")"

  DEF_BACK=8004
  DEF_FRONT=8005
  [ -n "$FRONT_DOMAIN" ] && { DEF_BACK=8443; DEF_FRONT=443; }

  BACK_PORT="$(ask '  порт api наружу' "${NTLMS_BACK_PORT:-$DEF_BACK}")"
  FRONT_PORT="$(ask '  порт сайта наружу' "${NTLMS_FRONT_PORT:-$DEF_FRONT}")"
  [[ "$BACK_PORT" =~ ^[0-9]+$ ]] || die "порт api не число: $BACK_PORT"
  [[ "$FRONT_PORT" =~ ^[0-9]+$ ]] || die "порт сайта не число: $FRONT_PORT"
  [ "$BACK_PORT" != "$FRONT_PORT" ] || die "порты api и сайта совпадают"
fi
ok "порты: api=$BACK_PORT, фронт=$FRONT_PORT"

# ============ шаг 5: сертификаты ============
say "шаг 5/8 — сертификаты (https)"
CERT_KIND="none"
mkdir -p "$CERT_DIR"

if [ -f "$CERT_DIR/cert.pem" ] && [ -f "$CERT_DIR/key.pem" ]; then
  if openssl x509 -checkend 86400 -noout -in "$CERT_DIR/cert.pem" 2>/dev/null; then
    ok "обнаружен действующий сертификат в $CERT_DIR — шаг сертификатов пропущен"
    CERT_KIND="existing"
  else
    warn "сертификат в $CERT_DIR найден, но его срок истекает/истек"
  fi
fi

if [ "$CERT_KIND" != "existing" ]; then
  if [ -f "$ROOT/scripts/install_certs.sh" ]; then
    . "$ROOT/scripts/install_certs.sh"
    CERT_KIND="$(ask_certs)"
    case "$CERT_KIND" in
      none)        ok "остаемся на http" ;;
      selfsigned)  certs_selfsigned ;;
      letsencrypt)
        [ -n "$FRONT_DOMAIN" ] || die "для Let's Encrypt нужен домен"
        open_firewall_ports 80
        certs_letsencrypt
        ;;
      existing)    certs_existing ;;
    esac
  fi
fi

if [ "$CERT_KIND" = none ] && [ ! -f "$CERT_DIR/cert.pem" ]; then
  SCHEME=http; SSL_CERT_ENV=''; SSL_KEY_ENV=''
else
  SCHEME=https
  if [ "$MODE" = docker ]; then
    SSL_CERT_ENV=/certs/cert.pem
    SSL_KEY_ENV=/certs/key.pem
  else
    SSL_CERT_ENV="$CERT_DIR/cert.pem"
    SSL_KEY_ENV="$CERT_DIR/key.pem"
  fi
fi

PUBLIC_URL="$SCHEME://${FRONT_DOMAIN:-$DETECT_IP}"
if [ -z "$FRONT_DOMAIN" ] || { [ "$FRONT_PORT" != 443 ] && [ "$FRONT_PORT" != 80 ]; }; then
  PUBLIC_URL="$SCHEME://${FRONT_DOMAIN:-$DETECT_IP}:$FRONT_PORT"
fi

# ============ шаг 6: .env ============
say "шаг 6/8 — конфигурация (.env)"
GEN_ENV=1
if [ -f "$ROOT/.env" ]; then
  if ask '  .env уже существует. Использовать текущий без перезаписи? (Y/n)' 'Y' | grep -qi '^y'; then
    GEN_ENV=0
    ok "использую существующий .env"
  else
    cp "$ROOT/.env" "$ROOT/.env.bak.$(date +%s)"
    info "старый сохранен в .env.bak.*"
  fi
fi

if [ "$GEN_ENV" = 1 ]; then
  BOT_TOKEN="$(ask '  токен бота от @BotFather (можно пропустить)' "${NTLMS_BOT_TOKEN:-}")"
  MONGO_WHERE="$(ask '  mongo где? (compose/atlas/custom)' 'compose')"
  case "$MONGO_WHERE" in
    atlas)  MONGO_URI="$(ask '  строка подключения mongodb+srv://...' '')"
            [ -n "$MONGO_URI" ] || die "пустая строка atlas" ;;
    custom) MONGO_URI="$(ask '  uri mongo' 'mongodb://localhost:27017/')" ;;
    *)      MONGO_URI='mongodb://localhost:27017/'
            [ "$MODE" = docker ] && info "в docker compose подставится mongodb://mongo:27017/" ;;
  esac

  ADMIN_SECRET="$(ask '  пароль админки /adminSecret (enter = автогенерация)' "${NTLMS_ADMIN_SECRET:-}")"
  [ -z "$ADMIN_SECRET" ] && ADMIN_SECRET="$(openssl rand -hex 8 2>/dev/null || head -c 8 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  SECRET="$(openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"

  CORS_ORIGINS="*"
  [ -n "$FRONT_DOMAIN" ] && CORS_ORIGINS="$SCHEME://$FRONT_DOMAIN,http://localhost:$FRONT_PORT"

  if [ "$MODE" = docker ]; then
    REDIS_URL='redis://redis:6379/0'
    WORKERS=2
    PORTS_BLOCK="PORT=8004
FRONT_PORT=8005
BACK_PORT=$BACK_PORT
FRONT_PORT_HOST=$FRONT_PORT"
  else
    REDIS_URL=""
    WORKERS=1
    PORTS_BLOCK="PORT=$BACK_PORT
FRONT_PORT=$FRONT_PORT
BACK_PORT=$BACK_PORT
FRONT_PORT_HOST=$FRONT_PORT"
  fi

  cat > "$ROOT/.env" <<EOF
HOST=127.0.0.1
FRONT_HOST=127.0.0.1
$PORTS_BLOCK
PUBLIC_URL=$PUBLIC_URL

SSL_CERTFILE=$SSL_CERT_ENV
SSL_KEYFILE=$SSL_KEY_ENV
DEV_CERTS=

CORS_ORIGINS=$CORS_ORIGINS

MONGO_URI=$MONGO_URI
MONGO_CLUSTER=ntlms
MONGO_USERS=nt_users
MONGO_COURSES=nt_courses

SECRET_KEY=$SECRET
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080

BOT_TOKEN=$BOT_TOKEN
BOT_DB_NAME=ntlmsauth
OTPLEN=6

ADMIN_SECRET=$ADMIN_SECRET

WORKERS=$WORKERS
MONGO_MAX_POOL=100
CACHE_TTL=60
RATE_LIMIT=20/minute
REDIS_URL=$REDIS_URL
EOF
  ok ".env сохранен"
fi

# ============ шаг 7: запуск и systemd ============
say "шаг 7/8 — запуск сервисов"
open_firewall_ports "$FRONT_PORT" "$BACK_PORT"

if [ "$MODE" = docker ]; then
  info "пересобираю контейнеры..."
  (cd "$ROOT" && $DOCKER compose up -d --build) || die "docker compose упал"
  ok "контейнеры подняты"
else
  if command -v systemctl >/dev/null 2>&1 && [ -f "$ROOT/scripts/install_systemd.sh" ]; then
    . "$ROOT/scripts/install_systemd.sh"
    $SUDO systemctl daemon-reload
    $SUDO systemctl restart notalms-back notalms-front notalms-bot 2>/dev/null || true
    ok "systemd сервисы перезапущены"
  else
    warn "systemctl или install_systemd.sh не найдены"
  fi
fi

# ============ шаг 8: алиас ============
say "шаг 8/8 — алиас"
if [ -f "$ROOT/scripts/ntlms.sh" ]; then
  if ! grep -q 'scripts/ntlms.sh' "$HOME/.bashrc" 2>/dev/null; then
    echo "source \"$ROOT/scripts/ntlms.sh\"" >> "$HOME/.bashrc"
    ok "алиас добавлен в ~/.bashrc"
  else
    ok "алиас уже настроен"
  fi
fi

say "Готово!"
echo "   сайт:     $PUBLIC_URL"
echo "   api:      $SCHEME://${FRONT_DOMAIN:-$DETECT_IP}:$BACK_PORT/v1"
echo "   режим:    $MODE"
echo
echo "   Примените алиасы: source ~/.bashrc"