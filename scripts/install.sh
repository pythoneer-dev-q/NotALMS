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
    for p in "$@"; do
      if ! $SUDO ufw status | grep -qw "$p/tcp"; then
        $SUDO ufw allow "$p"/tcp >/dev/null 2>&1 || true
        ok "ufw: открыт tcp порт $p"
      else
        info "ufw: порт $p уже открыт"
      fi
    done
  fi
}

cat <<'EOF'

  NotALMS — умный инсталлятор
  -----------------------------
  Проверяет существующие настройки и пропускает уже сделанные шаги.

EOF

# ============ шаг 1: способ запуска ============
say "шаг 1/9 — способ запуска"
EXISTING_MODE=""
[ -f "$MODE_FILE" ] && EXISTING_MODE="$(cat "$MODE_FILE" 2>/dev/null || true)"

if [ -n "$EXISTING_MODE" ]; then
  info "Текущий режим: $EXISTING_MODE"
  MODE="$(ask "  Использовать $EXISTING_MODE или сменить? (docker/venv)" "$EXISTING_MODE")"
else
  echo "   docker — всё в контейнерах (mongo и redis тоже), рекомендую"
  echo "   venv   — python-venv на хосте + systemd (mongo нужна своя)"
  MODE="$(ask '  способ (docker/venv)' "${NTLMS_MODE:-docker}")"
fi

case "$MODE" in docker|venv) ;; *) die "не понимаю '$MODE', нужно docker или venv" ;; esac
echo "$MODE" > "$MODE_FILE"
ok "способ: $MODE"

# ============ шаг 2: окружение и зависимости ============
say "шаг 2/9 — окружение и зависимости"
if [ "$MODE" = docker ]; then
  if [ -f "$ROOT/scripts/install_docker.sh" ]; then
    . "$ROOT/scripts/install_docker.sh"
    install_docker_engine
    resolve_docker_cmd
  else
    command -v docker >/dev/null || die "docker не установлен"
    DOCKER="docker"
  fi
else
  command -v python3 >/dev/null || die "python3 не найден (sudo apt install python3 python3-venv)"
  command -v systemctl >/dev/null || die "systemd не найден"
  command -v openssl >/dev/null || die "openssl не найден"

  # Проверка venv пакета
  if ! python3 -m venv --help >/dev/null 2>&1; then
    info "Установка python3-venv..."
    $SUDO apt-get update && $SUDO apt-get install -y python3-venv python3-pip || die "Не удалось установить python3-venv"
  fi

  # Создание venv и установка зависимостей
  if [ -x "$VENV_DIR/bin/uvicorn" ] && [ -x "$VENV_DIR/bin/python" ]; then
    ok "venv уже существует и uvicorn установлен (пропуск сборки)"
    REINSTALL="$(ask '  Переустановить / обновить зависимости pip? (y/N)' 'N')"
  else
    REINSTALL="y"
  fi

  if [[ "$REINSTALL" =~ ^[Yy]$ ]]; then
    [ -d "$VENV_DIR" ] || python3 -m venv "$VENV_DIR"
    info "Обновление pip и установка библиотек проекта..."
    "$VENV_DIR/bin/pip" install --upgrade pip setuptools wheel --quiet
    "$VENV_DIR/bin/pip" install \
      fastapi \
      uvicorn \
      motor \
      python-dotenv \
      "passlib[bcrypt]" \
      "python-jose[cryptography]" \
      slowapi \
      redis \
      aiogram || die "Ошибка установки python-зависимостей"
    ok "Зависимости venv установлены"
  fi
fi

# ============ шаг 3: локальные конфиги пакетов (исправление ModuleNotFoundError) ============
say "шаг 3/9 — локальные конфиги и структуры Python"
# Создание пакета back/auth/bot/config/
mkdir -p "$ROOT/back/auth/bot/config"
touch "$ROOT/back/auth/bot/__init__.py"
touch "$ROOT/back/auth/bot/config/__init__.py"

if [ ! -f "$ROOT/back/auth/bot/config/authConfig.py" ]; then
  cat <<'EOF' > "$ROOT/back/auth/bot/config/authConfig.py"
import os
from pathlib import Path
from dotenv import load_dotenv

# Ищем .env в корне проекта
env_path = Path(__file__).resolve().parents[4] / '.env'
load_dotenv(dotenv_path=env_path)

TOKEN = os.getenv("BOT_TOKEN", "")
EOF
  ok "Создан back/auth/bot/config/authConfig.py (читает BOT_TOKEN из .env)"
else
  ok "back/auth/bot/config/authConfig.py уже существует"
fi

# Создание пакета back/server/server_configs/
mkdir -p "$ROOT/back/server/server_configs"
touch "$ROOT/back/server/__init__.py"
touch "$ROOT/back/server/handlers/__init__.py"
touch "$ROOT/back/server/server_configs/__init__.py"

if [ ! -f "$ROOT/back/server/server_configs/server_mainConfig.py" ]; then
  cat <<'EOF' > "$ROOT/back/server/server_configs/server_mainConfig.py"
import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parents[3] / '.env'
load_dotenv(dotenv_path=env_path)
EOF
  ok "Создан back/server/server_configs/server_mainConfig.py"
else
  ok "back/server/server_configs/server_mainConfig.py уже существует"
fi

# ============ шаг 4: домены и порты ============
say "шаг 4/9 — домены и порты"
# Считываем имеющиеся значения из .env, если он есть
OLD_FRONT_PORT=""
OLD_BACK_PORT=""
OLD_FRONT_DOMAIN=""
if [ -f "$ROOT/.env" ]; then
  OLD_FRONT_PORT="$(grep -E '^FRONT_PORT=' "$ROOT/.env" | cut -d= -f2 || true)"
  OLD_BACK_PORT="$(grep -E '^BACK_PORT=' "$ROOT/.env" | cut -d= -f2 || true)"
  OLD_FRONT_DOMAIN="$(grep -E '^PUBLIC_URL=' "$ROOT/.env" | sed -E 's#https?://([^:/]+).*#\1#' || true)"
fi

DETECT_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
[ -n "${DETECT_IP:-}" ] || DETECT_IP='127.0.0.1'

DEF_BACK="${OLD_BACK_PORT:-8004}"
DEF_FRONT="${OLD_FRONT_PORT:-8005}"

FRONT_DOMAIN="$(ask "  домен сайта (enter = ip $DETECT_IP)" "${OLD_FRONT_DOMAIN:-${NTLMS_FRONT_DOMAIN:-}}")"
BACK_DOMAIN="$(ask '  домен api (пусто = тот же домен/ip)' "${NTLMS_BACK_DOMAIN:-}")"

[ -n "$FRONT_DOMAIN" ] && [ -z "$OLD_FRONT_PORT" ] && { DEF_BACK=8443; DEF_FRONT=443; }

BACK_PORT="$(ask '  порт api наружу' "$DEF_BACK")"
FRONT_PORT="$(ask '  порт сайта наружу' "$DEF_FRONT")"
[[ "$BACK_PORT" =~ ^[0-9]+$ ]] || die "порт api не число: $BACK_PORT"
[[ "$FRONT_PORT" =~ ^[0-9]+$ ]] || die "порт сайта не число: $FRONT_PORT"
[ "$BACK_PORT" != "$FRONT_PORT" ] || die "порты api и сайта не должны совпадать"
ok "домены: ${FRONT_DOMAIN:-<ip>} / порты: api=$BACK_PORT сайт=$FRONT_PORT"

# ============ шаг 5: сертификаты ============
say "шаг 5/9 — сертификаты (https)"
CERT_KIND="none"

if [ -f "$CERT_DIR/cert.pem" ] && [ -f "$CERT_DIR/key.pem" ]; then
  ok "Сертификаты уже найдены в $CERT_DIR"
  REISSUE="$(ask '  Использовать существующие сертификаты? (Y/n)' 'Y')"
  if [[ "$REISSUE" =~ ^[Nn]$ ]]; then
    RE_RUN_CERTS=1
  else
    RE_RUN_CERTS=0
    CERT_KIND="existing"
  fi
else
  RE_RUN_CERTS=1
fi

if [ "$RE_RUN_CERTS" = 1 ]; then
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
    warn "scripts/install_certs.sh не найден, остаемся на HTTP"
    CERT_KIND="none"
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
info "публичный адрес: $PUBLIC_URL"

# ============ шаг 6: .env ============
say "шаг 6/9 — .env"
GEN_ENV=1
if [ -f "$ROOT/.env" ]; then
  if ask '  .env уже существует, оставить его? (Y/n)' 'Y' | grep -qi '^y'; then
    GEN_ENV=0
    ok "использую существующий .env"
  else
    cp "$ROOT/.env" "$ROOT/.env.bak.$(date +%s)"
    info "сохранил резервную копию в .env.bak.*"
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
            [ "$MODE" = docker ] && info "compose сам подставит mongodb://mongo:27017/" ;;
  esac

  ADMIN_SECRET="$(ask '  пароль админки /adminSecret (enter = сгенерить)' "${NTLMS_ADMIN_SECRET:-}")"
  [ -z "$ADMIN_SECRET" ] && ADMIN_SECRET="$(openssl rand -hex 8 2>/dev/null || head -c 8 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  SECRET="$(openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"

  CORS_ORIGINS="*"
  [ -n "$FRONT_DOMAIN" ] && CORS_ORIGINS="$SCHEME://$FRONT_DOMAIN,http://localhost:$FRONT_PORT"

  if [ "$MODE" = docker ]; then
    REDIS_URL='redis://redis:6379/0'
    WORKERS="${WORKERS:-2}"
    PORTS_BLOCK="PORT=8004
FRONT_PORT=8005
BACK_PORT=$BACK_PORT
FRONT_PORT_HOST=$FRONT_PORT"
  else
    REDIS_URL="$(ask '  redis url (пусто = кэш в памяти)' '')"
    WORKERS="${WORKERS:-1}"
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
  ok ".env успешно записан"
fi

# ============ шаг 7: фаервол и порты ============
say "шаг 7/9 — открытие портов"
open_firewall_ports "$FRONT_PORT" "$BACK_PORT"

# ============ шаг 8: запуск / systemd ============
say "шаг 8/9 — запуск сервисов"
if [ "$MODE" = docker ]; then
  info "запуск docker compose..."
  (cd "$ROOT" && $DOCKER compose up -d --build)
  ok "контейнеры запущены"
else
  if command -v systemctl >/dev/null 2>&1 && [ -f "$ROOT/scripts/install_systemd.sh" ]; then
    . "$ROOT/scripts/install_systemd.sh"
    ok "systemd-сервисы настроены и перезапущены"
  else
    warn "systemd не найден, запуск вручную через .venv/bin/uvicorn"
  fi
fi

# ============ шаг 9: алиас ============
say "шаг 9/9 — алиас ntlms"
if [ -f "$ROOT/scripts/ntlms.sh" ]; then
  if ! grep -q 'scripts/ntlms.sh' "$HOME/.bashrc" 2>/dev/null; then
    echo "source \"$ROOT/scripts/ntlms.sh\"" >> "$HOME/.bashrc"
    ok "добавил алиас в ~/.bashrc"
  else
    ok "алиас уже подключен в ~/.bashrc"
  fi
fi

say "Всё готово!"
echo "   Сайт:    $PUBLIC_URL"
echo "   API:     $SCHEME://${FRONT_DOMAIN:-127.0.0.1}:$BACK_PORT/v1"
echo "   Админка: $PUBLIC_URL/adminSecret"
echo "   Режим:   $MODE"
echo
echo "   Чтобы применить алиас прямо сейчас: source ~/.bashrc"