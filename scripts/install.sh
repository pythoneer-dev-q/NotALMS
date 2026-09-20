#!/usr/bin/env bash
# scripts/install.sh — установка notalms
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODE_FILE="$ROOT/.ntlms-mode"
VENV_DIR="$ROOT/.venv"

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

  NotALMS — установка
  -------------------
  шаги: способ -> окружение (docker/venv) -> домены и порты -> сертификаты ->
        .env -> запуск -> systemd -> алиас ntlms
  на любом шаге можно прервать ctrl+c, ничего необратимого не делается.

EOF

# ============ шаг 1: способ запуска ============
say "шаг 1/8 — способ запуска"
echo "   docker — всё в контейнерах (mongo и redis тоже), рекомендую"
echo "   venv   — python-venv на хосте + systemd (mongo нужна своя)"
MODE="$(ask '  способ (docker/venv)' "${NTLMS_MODE:-docker}")"
case "$MODE" in docker|venv) ;; *) die "не понимаю '$MODE', нужно docker или venv" ;; esac
echo "$MODE" > "$MODE_FILE"
info "способ: $MODE (записал в .ntlms-mode, оттуда читает алиас ntlms)"

# ============ шаг 2: окружение ============
say "шаг 2/8 — окружение"
if [ "$MODE" = docker ]; then
  if [ -f "$ROOT/scripts/install_docker.sh" ]; then
    . "$ROOT/scripts/install_docker.sh"
    install_docker_engine
    resolve_docker_cmd
  else
    command -v docker >/dev/null || die "docker не установлен и scripts/install_docker.sh отсутствует"
    DOCKER="docker"
  fi
else
  command -v python3 >/dev/null || die "python3 не найден. Установите: sudo apt install python3 python3-venv"
  command -v systemctl >/dev/null || die "systemd не найден, venv-режим рассчитан на linux+systemd"
  command -v openssl >/dev/null || die "openssl не найден (sudo apt install openssl)"

  # Проверка работоспособности venv
  if ! python3 -m venv --help >/dev/null 2>&1; then
    warn "Модуль python3-venv не установлен!"
    if [ -n "$SUDO" ] || [ "$(id -u)" = 0 ]; then
      info "Пробую установить python3-venv..."
      $SUDO apt-get update && $SUDO apt-get install -y python3-venv python3-pip || die "Не удалось поставить python3-venv"
    else
      die "Установите python3-venv вручную: sudo apt install python3-venv python3-pip"
    fi
  fi

  info "Создание виртуального окружения в $VENV_DIR..."
  python3 -m venv "$VENV_DIR"
  ok "venv создан"

  info "Установка зависимостей проекта..."
  "$VENV_DIR/bin/pip" install --upgrade pip setuptools wheel
  "$VENV_DIR/bin/pip" install \
    fastapi \
    uvicorn \
    motor \
    python-dotenv \
    "passlib[bcrypt]" \
    "python-jose[cryptography]" \
    slowapi \
    redis \
    aiogram || die "Сбой установки python-зависимостей"

  ok "Зависимости успешно установлены"
fi

# ============ шаг 3: домены и порты ============
say "шаг 3/8 — домены и порты"
info "домена нет? жми enter — тогда адреса будут по ip и выбранному порту"
DETECT_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
[ -n "${DETECT_IP:-}" ] || DETECT_IP='127.0.0.1'
FRONT_DOMAIN="$(ask "  домен сайта (enter = ip $DETECT_IP)" "${NTLMS_FRONT_DOMAIN:-}")"
BACK_DOMAIN="$(ask '  домен api (пусто = api на том же домене/ip)' "${NTLMS_BACK_DOMAIN:-}")"

DEF_BACK=8004
DEF_FRONT=8005
[ -n "$FRONT_DOMAIN" ] && { DEF_BACK=8443; DEF_FRONT=443; }
BACK_PORT="$(ask '  порт api наружу' "${NTLMS_BACK_PORT:-$DEF_BACK}")"
FRONT_PORT="$(ask '  порт сайта наружу' "${NTLMS_FRONT_PORT:-$DEF_FRONT}")"
[[ "$BACK_PORT" =~ ^[0-9]+$ ]] || die "порт api не число: $BACK_PORT"
[[ "$FRONT_PORT" =~ ^[0-9]+$ ]] || die "порт сайта не число: $FRONT_PORT"
[ "$BACK_PORT" != "$FRONT_PORT" ] || die "порты api и сайта совпадают, разведи их"
ok "домены: сайт=${FRONT_DOMAIN:-<ip>} api=${BACK_DOMAIN:-$FRONT_DOMAIN}; порты: api=$BACK_PORT сайт=$FRONT_PORT"

# ============ шаг 4: сертификаты ============
say "шаг 4/8 — сертификаты (https)"
CERT_KIND="none"
CERT_DIR="$ROOT/certs"
if [ -f "$ROOT/scripts/install_certs.sh" ]; then
  . "$ROOT/scripts/install_certs.sh"
  CERT_KIND="$(ask_certs)"
  case "$CERT_KIND" in
    none)        ok "остаемся на http" ;;
    selfsigned)  certs_selfsigned ;;
    letsencrypt)
      [ -n "$FRONT_DOMAIN" ] || die "для Let's Encrypt нужен домен — укажите домен"
      open_firewall_ports 80
      certs_letsencrypt
      ;;
    existing)    certs_existing ;;
  esac
else
  warn "scripts/install_certs.sh не найден, остаемся на HTTP"
fi

if [ "$CERT_KIND" = none ]; then
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

# ============ шаг 5: .env ============
say "шаг 5/8 — .env"
GEN_ENV=1
if [ -f "$ROOT/.env" ]; then
  if ask '  .env уже есть, перезаписать? (y/N)' 'N' | grep -qi '^y'; then
    cp "$ROOT/.env" "$ROOT/.env.bak.$(date +%s)"
    info "старый сохранен в .env.bak.*"
  else
    GEN_ENV=0
    ok "использую существующий .env"
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
            [ "$MODE" = docker ] && info "в docker compose сам подставит mongodb://mongo:27017/" ;;
  esac

  ADMIN_SECRET="$(ask '  пароль админки /adminSecret (enter = сгенерить)' "${NTLMS_ADMIN_SECRET:-}")"
  if [ -z "$ADMIN_SECRET" ]; then
    ADMIN_SECRET="$(openssl rand -hex 8 2>/dev/null || head -c 8 /dev/urandom | od -An -tx1 | tr -d ' \n')"
    warn "пароль админки сгенерирован: $ADMIN_SECRET"
  fi
  SECRET="$(openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"

  if [ -n "$FRONT_DOMAIN" ]; then
    CORS_ORIGINS="$SCHEME://$FRONT_DOMAIN,http://localhost:$FRONT_PORT"
  else
    CORS_ORIGINS='*'
  fi

  if [ "$MODE" = docker ]; then
    REDIS_URL='redis://redis:6379/0'
    WORKERS="${WORKERS:-2}"
    PORTS_BLOCK="PORT=8004
FRONT_PORT=8005
BACK_PORT=$BACK_PORT
FRONT_PORT_HOST=$FRONT_PORT"
  else
    REDIS_URL="$(ask '  redis url (пусто = кэш в памяти процесса)' '')"
    WORKERS="${WORKERS:-1}"
    PORTS_BLOCK="PORT=$BACK_PORT
FRONT_PORT=$FRONT_PORT
BACK_PORT=$BACK_PORT
FRONT_PORT_HOST=$FRONT_PORT"
    if [ "$FRONT_PORT" -lt 1024 ] || [ "$BACK_PORT" -lt 1024 ]; then
      warn "порт меньше 1024: не запускайте под root без setcap"
    fi
  fi

  cat > "$ROOT/.env" <<EOF
# сгенерировано scripts/install.sh
HOST=127.0.0.1
FRONT_HOST=127.0.0.1
$PORTS_BLOCK
PUBLIC_URL=$PUBLIC_URL

# ssl
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

# ============ шаг 6: запуск ============
say "шаг 6/8 — запуск"
if [ "$MODE" = docker ]; then
  open_firewall_ports "$FRONT_PORT" "$BACK_PORT"
  info "поднимаю контейнеры..."
  (cd "$ROOT" && $DOCKER compose up -d --build) || die "docker compose упал"

  info "ожидание старта сервисов..."
  for i in $(seq 1 30); do
    RUNNING="$(cd "$ROOT" && $DOCKER compose ps --status running --services 2>/dev/null | tr '\n' ' ')"
    echo "$RUNNING" | grep -q back && echo "$RUNNING" | grep -q front && break
    sleep 2
  done
  ok "сервисы запущены"
else
  open_firewall_ports "$FRONT_PORT" "$BACK_PORT"
  info "venv готов. Сервисы будут запущены через systemd на следующем шаге."
fi

# ============ шаг 7: systemd ============
say "шаг 7/8 — автозапуск (systemd)"
if command -v systemctl >/dev/null 2>&1 && [ -f "$ROOT/scripts/install_systemd.sh" ]; then
  . "$ROOT/scripts/install_systemd.sh"
  ok "автозапуск настроен и запущен"
else
  warn "systemctl или scripts/install_systemd.sh не найден — запуск вручную через: $VENV_DIR/bin/uvicorn"
fi

# ============ шаг 8: алиас ============
say "шаг 8/8 — алиас ntlms"
if [ -f "$ROOT/scripts/ntlms.sh" ]; then
  if ! grep -q 'scripts/ntlms.sh' "$HOME/.bashrc" 2>/dev/null; then
    echo "source \"$ROOT/scripts/ntlms.sh\"" >> "$HOME/.bashrc"
    ok "добавил алиас в ~/.bashrc"
  fi
fi

say "готово!"
echo "   сайт:     $PUBLIC_URL"
echo "   api:      $SCHEME://${FRONT_DOMAIN:-127.0.0.1}:$BACK_PORT/v1"
echo "   админка:  $PUBLIC_URL/adminSecret"
echo "   режим:    $MODE"
echo
echo "   Чтобы применить окружение, выполните: source ~/.bashrc"