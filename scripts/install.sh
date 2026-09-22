#!/usr/bin/env bash
# scripts/install.sh — умная установка и обновление NotALMS
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
  Проверяет окружение, серты, порты и восстанавливает конфиги.

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

# ============ шаг 2: окружение ============
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
  command -v python3 >/dev/null || die "python3 не найден"
  command -v systemctl >/dev/null || die "systemd не найден"
  command -v openssl >/dev/null || die "openssl не найден"

  if ! python3 -m venv --help >/dev/null 2>&1; then
    warn "python3-venv не найден, пробую установить..."
    $SUDO apt-get update && $SUDO apt-get install -y python3-venv python3-pip || die "Установите: sudo apt install python3-venv python3-pip"
  fi

  if [ -f "$VENV_DIR/bin/uvicorn" ] && [ -f "$VENV_DIR/bin/python" ]; then
    ok "venv уже инициализирован ($VENV_DIR)"
  else
    info "создаю venv в $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --upgrade pip setuptools wheel
    "$VENV_DIR/bin/pip" install fastapi uvicorn motor python-dotenv "passlib[bcrypt]" "python-jose[cryptography]" slowapi redis aiogram pydantic-settings httpx
    ok "venv и зависимости установлены"
  fi
fi

# ============ шаг 3: автогенерация модулей и конфигов ============
say "шаг 3/8 — проверка локальных модулей"
mkdir -p "$ROOT/back/auth/bot/config"
mkdir -p "$ROOT/back/server/server_configs"
touch "$ROOT/back/__init__.py" 2>/dev/null || true
touch "$ROOT/back/auth/__init__.py" 2>/dev/null || true
touch "$ROOT/back/auth/bot/__init__.py" 2>/dev/null || true
touch "$ROOT/back/auth/bot/config/__init__.py" 2>/dev/null || true
touch "$ROOT/back/server/__init__.py" 2>/dev/null || true
touch "$ROOT/back/server/server_configs/__init__.py" 2>/dev/null || true

# Проверяем authConfig.py на наличие обязательных экспортов
AUTH_CONF="$ROOT/back/auth/bot/config/authConfig.py"
NEED_AUTH_GEN=0
if [ ! -f "$AUTH_CONF" ]; then
  NEED_AUTH_GEN=1
elif ! grep -q "MONGO_URI" "$AUTH_CONF" || ! grep -q "MONGO_DB_NAME" "$AUTH_CONF"; then
  warn "В $AUTH_CONF отсутствуют обязательные переменные, пересоздаю..."
  NEED_AUTH_GEN=1
fi

if [ "$NEED_AUTH_GEN" = 1 ]; then
  cat << 'EOF' > "$AUTH_CONF"
import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parents[4] / ".env"
load_dotenv(dotenv_path=env_path)

try:
    from back.server.server_configs.settings import settings
    TOKEN = getattr(settings, "bot_token", os.getenv("BOT_TOKEN", ""))
    MONGO_URI = getattr(settings, "mongo_uri", os.getenv("MONGO_URI", "mongodb://localhost:27017/"))
    MONGO_DB_NAME = getattr(settings, "bot_db_name", os.getenv("BOT_DB_NAME", "ntlmsauth"))
    OTPLEN = int(getattr(settings, "otplen", os.getenv("OTPLEN", 6)))
except Exception:
    TOKEN = os.getenv("BOT_TOKEN", "")
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    MONGO_DB_NAME = os.getenv("BOT_DB_NAME", "ntlmsauth")
    OTPLEN = int(os.getenv("OTPLEN", 6))
EOF
  ok "сконфигурирован $AUTH_CONF (TOKEN, MONGO_URI, MONGO_DB_NAME, OTPLEN)"
else
  ok "$AUTH_CONF корректен"
fi

# ============ шаг 4: домены и порты ============
say "шаг 4/8 — домены и порты"
PREV_FRONT_PORT="$(grep -E '^FRONT_PORT=' "$ROOT/.env" 2>/dev/null | cut -d= -f2 || true)"
PREV_BACK_PORT="$(grep -E '^PORT=' "$ROOT/.env" 2>/dev/null | cut -d= -f2 || true)"
DETECT_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
[ -n "${DETECT_IP:-}" ] || DETECT_IP='127.0.0.1'

if [ -f "$ROOT/.env" ] && [ -n "$PREV_FRONT_PORT" ]; then
  info "найдены порты из .env: фронт=$PREV_FRONT_PORT, api=$PREV_BACK_PORT"
  USE_EXISTING_PORTS="$(ask '  использовать их? (Y/n)' 'Y')"
else
  USE_EXISTING_PORTS="n"
fi

if echo "$USE_EXISTING_PORTS" | grep -qi '^y'; then
  FRONT_PORT="$PREV_FRONT_PORT"
  BACK_PORT="$PREV_BACK_PORT"
  FRONT_DOMAIN="$(grep -E '^PUBLIC_URL=' "$ROOT/.env" 2>/dev/null | sed -E 's#^PUBLIC_URL=https?://([^:/]+).*#\1#' || true)"
  [ "$FRONT_DOMAIN" = "$DETECT_IP" ] && FRONT_DOMAIN=""
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
  [ "$BACK_PORT" != "$FRONT_PORT" ] || die "порты совпадают"
fi
ok "порты: api=$BACK_PORT, сайт=$FRONT_PORT"

# ============ шаг 5: сертификаты (https) ============
say "шаг 5/8 — сертификаты (https)"
mkdir -p "$CERT_DIR"
CERT_KIND=""

# Проверяем существующие сертификаты
if [ -f "$CERT_DIR/cert.pem" ] && [ -f "$CERT_DIR/key.pem" ]; then
  if openssl x509 -checkend 86400 -noout -in "$CERT_DIR/cert.pem" 2>/dev/null; then
    ok "найден действующий сертификат в $CERT_DIR"
    KEEP_CERTS="$(ask '  оставить текущие сертификаты? (Y/n)' 'Y')"
    if echo "$KEEP_CERTS" | grep -qi '^y'; then
      CERT_KIND="existing"
    fi
  fi
fi

if [ -z "$CERT_KIND" ]; then
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
  else
    warn "scripts/install_certs.sh не найден"
    CERT_KIND="none"
  fi
fi

if [ "$CERT_KIND" = "none" ] && [ ! -f "$CERT_DIR/cert.pem" ]; then
  SCHEME="http"
  SSL_CERT_ENV=""
  SSL_KEY_ENV=""
else
  SCHEME="https"
  if [ "$MODE" = "docker" ]; then
    SSL_CERT_ENV="/certs/cert.pem"
    SSL_KEY_ENV="/certs/key.pem"
  else
    SSL_CERT_ENV="$CERT_DIR/cert.pem"
    SSL_KEY_ENV="$CERT_DIR/key.pem"
  fi
fi

PUBLIC_URL="$SCHEME://${FRONT_DOMAIN:-$DETECT_IP}"
if [ -z "$FRONT_DOMAIN" ] || { [ "$FRONT_PORT" != 443 ] && [ "$FRONT_PORT" != 80 ]; }; then
  PUBLIC_URL="$SCHEME://${FRONT_DOMAIN:-$DETECT_IP}:$FRONT_PORT"
fi
info "публичный адрес: $PUBLIC_URL"

# ============ шаг 6: .env ============
say "шаг 6/8 — конфигурация (.env)"
GEN_ENV=1
if [ -f "$ROOT/.env" ]; then
  if ask '  .env уже существует. Использовать текущий? (Y/n)' 'Y' | grep -qi '^y'; then
    GEN_ENV=0
    # Синхронизируем обновленные пути сертификатов в текущем .env
    sed -i "s|^SSL_CERTFILE=.*|SSL_CERTFILE=$SSL_CERT_ENV|" "$ROOT/.env"
    sed -i "s|^SSL_KEYFILE=.*|SSL_KEYFILE=$SSL_KEY_ENV|" "$ROOT/.env"
    ok "использую существующий .env (пути сертов обновлены)"
  else
    cp "$ROOT/.env" "$ROOT/.env.bak.$(date +%s)"
    info "резервная копия: .env.bak.*"
  fi
fi

if [ "$GEN_ENV" = 1 ]; then
  BOT_TOKEN="$(ask '  токен бота @BotFather' "${NTLMS_BOT_TOKEN:-}")"
  MONGO_WHERE="$(ask '  mongo где? (compose/atlas/custom)' 'compose')"
  case "$MONGO_WHERE" in
    atlas)  MONGO_URI="$(ask '  строка atlas' '')" ;;
    custom) MONGO_URI="$(ask '  uri mongo' 'mongodb://localhost:27017/')" ;;
    *)      MONGO_URI='mongodb://localhost:27017/' ;;
  esac

  ADMIN_SECRET="$(ask '  пароль админки (enter = сгенерировать)' "${NTLMS_ADMIN_SECRET:-}")"
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

  TURNSTILE_SITE_KEY="$(ask '  Turnstile site key (enter = отключить CAPTCHA)' "${NTLMS_TURNSTILE_SITE_KEY:-}")"
  TURNSTILE_SECRET_KEY=""
  if [ -n "$TURNSTILE_SITE_KEY" ]; then
    TURNSTILE_SECRET_KEY="$(ask '  Turnstile secret key' "${NTLMS_TURNSTILE_SECRET_KEY:-}")"
  fi

  LOGGING_ENABLED="$(ask '  включить журналы приложения? (Y/n)' 'Y')"
  ACCESS_LOG_ENABLED="$(ask '  журналировать каждый HTTP-запрос? (y/N)' 'N')"
  case "$LOGGING_ENABLED" in [Yy]*) LOGGING_ENABLED=true ;; *) LOGGING_ENABLED=false ;; esac
  case "$ACCESS_LOG_ENABLED" in [Yy]*) ACCESS_LOG_ENABLED=true ;; *) ACCESS_LOG_ENABLED=false ;; esac

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
LOGGING_ENABLED=$LOGGING_ENABLED
ACCESS_LOG_ENABLED=$ACCESS_LOG_ENABLED
LOG_LEVEL=info
EXPECTED_DISCONNECT_LOG_LEVEL=debug
DISCONNECT_LOG_INTERVAL_SECONDS=60
CAPTCHA_SUSPICIOUS_RPS=15
TURNSTILE_SITE_KEY=$TURNSTILE_SITE_KEY
TURNSTILE_SECRET_KEY=$TURNSTILE_SECRET_KEY
REDIS_URL=$REDIS_URL
EOF
  ok ".env сохранен"
fi

# Обновление старой .env: новые функции получают безопасные фоллбеки,
# существующие значения никогда не затираются.
ensure_env_var() {
  local key="$1" value="$2"
  grep -q "^${key}=" "$ROOT/.env" 2>/dev/null || echo "${key}=${value}" >> "$ROOT/.env"
}

install_mongodb_local() {
  if command -v mongod >/dev/null 2>&1; then
    ok "MongoDB уже установлена: $(mongod --version 2>/dev/null | head -n 1)"
  else
    info "MongoDB не найдена, устанавливаю..."
    [ -f /etc/os-release ] || die "не удалось определить Linux для установки MongoDB"
    # shellcheck disable=SC1091
    . /etc/os-release
    case "${ID:-} ${ID_LIKE:-}" in
      *ubuntu*|*debian*)
        $SUDO apt-get update -qq
        $SUDO apt-get install -y -qq curl gnupg ca-certificates
        curl -fsSL https://pgp.mongodb.com/server-8.0.asc \
          | $SUDO gpg --dearmor --yes -o /usr/share/keyrings/mongodb-server-8.0.gpg
        local mongo_family="debian"
        local mongo_component="main"
        if [ "${ID:-}" = "ubuntu" ]; then
          mongo_family="ubuntu"
          mongo_component="multiverse"
        fi
        local mongo_codename="${VERSION_CODENAME:-}"
        [ -n "$mongo_codename" ] || die "не удалось определить codename дистрибутива"
        echo "deb [signed-by=/usr/share/keyrings/mongodb-server-8.0.gpg] https://repo.mongodb.org/apt/$mongo_family $mongo_codename/mongodb-org/8.0 $mongo_component" \
          | $SUDO tee /etc/apt/sources.list.d/mongodb-org-8.0.list >/dev/null
        $SUDO apt-get update -qq
        $SUDO apt-get install -y mongodb-org
        ;;
      *rhel*|*centos*|*fedora*|*almalinux*|*rocky*)
        local rpm_major="${VERSION_ID%%.*}"
        [ -n "$rpm_major" ] || rpm_major=9
        $SUDO tee /etc/yum.repos.d/mongodb-org-8.0.repo >/dev/null <<EOF
[mongodb-org-8.0]
name=MongoDB Repository
baseurl=https://repo.mongodb.org/yum/redhat/$rpm_major/mongodb-org/8.0/x86_64/
gpgcheck=1
enabled=1
gpgkey=https://pgp.mongodb.com/server-8.0.asc
EOF
        $SUDO dnf install -y mongodb-org
        ;;
      *) die "автоустановка MongoDB поддерживает Debian, Ubuntu и RHEL-подобные системы" ;;
    esac
  fi

  if command -v systemctl >/dev/null 2>&1; then
    $SUDO systemctl enable --now mongod || die "MongoDB установлена, но mongod не запустился"
  fi
  command -v mongosh >/dev/null 2>&1 && mongosh --quiet --eval "db.adminCommand('ping')" >/dev/null \
    || warn "MongoDB запущена, но проверка через mongosh не выполнена"
}
ACTIVE_MONGO_URI="$(grep -E '^MONGO_URI=' "$ROOT/.env" 2>/dev/null | cut -d= -f2- || true)"
if [ "$MODE" = venv ]; then
  case "$ACTIVE_MONGO_URI" in
    mongodb://localhost*|mongodb://127.0.0.1*) install_mongodb_local ;;
    *) ok "используется внешняя MongoDB, локальная установка не требуется" ;;
  esac
fi
ensure_env_var "CAPTCHA_SUSPICIOUS_RPS" "15"
ensure_env_var "LOGGING_ENABLED" "true"
ensure_env_var "ACCESS_LOG_ENABLED" "false"
ensure_env_var "LOG_LEVEL" "info"
ensure_env_var "EXPECTED_DISCONNECT_LOG_LEVEL" "debug"
ensure_env_var "DISCONNECT_LOG_INTERVAL_SECONDS" "60"
ensure_env_var "TURNSTILE_SITE_KEY" ""
ensure_env_var "TURNSTILE_SECRET_KEY" ""
ok "проверены фоллбеки CAPTCHA в .env"

# ============ шаг 7: запуск и systemd ============
say "шаг 7/8 — запуск сервисов"
open_firewall_ports "$FRONT_PORT" "$BACK_PORT"

if [ "$MODE" = docker ]; then
  info "запуск контейнеров..."
  (cd "$ROOT" && $DOCKER compose up -d --build) || die "docker compose упал"
  ok "контейнеры запущены"
else
  if command -v systemctl >/dev/null 2>&1 && [ -f "$ROOT/scripts/install_systemd.sh" ]; then
    . "$ROOT/scripts/install_systemd.sh"
    $SUDO systemctl daemon-reload
    $SUDO systemctl restart notalms-back notalms-front notalms-bot 2>/dev/null || true
    ok "сервисы systemd перезапущены"
  fi
fi

# ============ шаг 8: алиас ============
say "шаг 8/8 — алиас"
if [ -f "$ROOT/scripts/ntlms.sh" ]; then
  if ! grep -q 'scripts/ntlms.sh' "$HOME/.bashrc" 2>/dev/null; then
    echo "source \"$ROOT/scripts/ntlms.sh\"" >> "$HOME/.bashrc"
  fi
fi

if [ -f "$HOME/.bashrc" ]; then
  set +u
  # shellcheck disable=SC1090
  . "$HOME/.bashrc" || true
  set -u
fi

say "Готово!"
echo "   сайт:     $PUBLIC_URL"
echo "   api:      $SCHEME://${FRONT_DOMAIN:-$DETECT_IP}:$BACK_PORT/v1"
echo "   режим:    $MODE"
echo "   серты:    $CERT_DIR"
