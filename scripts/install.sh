#!/usr/bin/env bash
# ! scripts/install.sh — установка notalms:
# спрашивает способ/домены/порты/серты, сам ставит docker, поднимает стек,
# прописывает автозапуск через systemd и алиас ntlms
# запуск: bash scripts/install.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODE_FILE="$ROOT/.ntlms-mode"

say()  { echo -e "\n\033[1;36m== $1\033[0m"; }
info() { echo "   $1"; }
ok()   { echo -e "   \033[0;32m+ $1\033[0m"; }
warn() { echo -e "   \033[0;33m! $1\033[0m"; }
die()  { echo -e "\033[0;31mERROR: $1\033[0m"; exit 1; }

ask() { # ask "вопрос" "дефолт" -> ответ
  local q="$1" d="${2:-}"
  read -rp "$q${d:+ [$d]}: " a
  echo "${a:-$d}"
}

SUDO="$( [ "$(id -u)" = 0 ] && echo '' || echo sudo )"

# ufw, если включен — открываем нужные порты
open_firewall_ports() {
  if command -v ufw >/dev/null 2>&1 && $SUDO ufw status 2>/dev/null | grep -qi active; then
    for p in "$@"; do $SUDO ufw allow "$p"/tcp >/dev/null 2>&1 || true; done
    ok "ufw: открыл tcp $*"
  fi
}

cat <<'EOF'

  NotALMS — установка
  -------------------
  шаги: способ -> окружение (docker) -> домены и порты -> сертификаты ->
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
  . "$ROOT/scripts/install_docker.sh"
  install_docker_engine
  resolve_docker_cmd
else
  command -v python3 >/dev/null || die "python3 не найден (apt install python3 python3-venv)"
  command -v systemctl >/dev/null || die "systemd не найден, venv-режим рассчитан на linux+systemd"
  command -v openssl >/dev/null || die "openssl не найден (нужен для сертов)"
  info "python3: $(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
  ok "python3 и systemd на месте"
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
. "$ROOT/scripts/install_certs.sh"
CERT_KIND="$(ask_certs)"
CERT_DIR="$ROOT/certs"
case "$CERT_KIND" in
  none)
    ok "остаемся на http"
    ;;
  selfsigned)
    certs_selfsigned
    ;;
  letsencrypt)
    [ -n "$FRONT_DOMAIN" ] || die "для Let's Encrypt нужен домен — перезапусти и укажи домен"
    open_firewall_ports 80
    certs_letsencrypt
    ;;
  existing)
    certs_existing
    ;;
esac

if [ "$CERT_KIND" = none ]; then
  SCHEME=http; SSL_CERT_ENV=''; SSL_KEY_ENV=''
else
  SCHEME=https
  if [ "$MODE" = docker ]; then
    # в контейнер ./certs монтируется в /certs
    SSL_CERT_ENV=/certs/cert.pem
    SSL_KEY_ENV=/certs/key.pem
  else
    SSL_CERT_ENV="$CERT_DIR/cert.pem"
    SSL_KEY_ENV="$CERT_DIR/key.pem"
  fi
fi

# публичный адрес фронта — из него бот строит ссылки входа (порт опускаем для 443/80)
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
    info "старый сохранил в .env.bak.*"
  else
    GEN_ENV=0
    ok "использую существующий .env (значения портов/сертов в нём не меняю)"
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
            [ "$MODE" = docker ] && info "в контейнерах compose сам подставит mongodb://mongo:27017/" ;;
  esac

  ADMIN_SECRET="$(ask '  пароль админки /adminSecret (enter = сгенерить)' "${NTLMS_ADMIN_SECRET:-}")"
  if [ -z "$ADMIN_SECRET" ]; then
    ADMIN_SECRET="$(openssl rand -hex 8 2>/dev/null || head -c 8 /dev/urandom | od -An -tx1 | tr -d ' \n')"
    warn "пароль админки сгенерирован, запиши его: $ADMIN_SECRET"
  fi
  SECRET="$(openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"

  # публичный адрес уже посчитан на шаге сертов
  if [ -n "$FRONT_DOMAIN" ]; then
    CORS_ORIGINS="$SCHEME://$FRONT_DOMAIN,http://localhost:$FRONT_PORT"
  else
    CORS_ORIGINS='*'
  fi

  if [ "$MODE" = docker ]; then
    REDIS_URL='redis://redis:6379/0'
    WORKERS="${WORKERS:-2}"
    # внутри контейнеров порты фиксированы, наружу — выбранные
    PORTS_BLOCK="PORT=8004
FRONT_PORT=8005
BACK_PORT=$BACK_PORT
FRONT_PORT_HOST=$FRONT_PORT"
  else
    REDIS_URL="$(ask '  redis url (пусто = кэш в памяти процесса)' '')"
    WORKERS="${WORKERS:-1}"
    # venv слушает выбранные порты напрямую
    PORTS_BLOCK="PORT=$BACK_PORT
FRONT_PORT=$FRONT_PORT
BACK_PORT=$BACK_PORT
FRONT_PORT_HOST=$FRONT_PORT"
    if [ "$FRONT_PORT" -lt 1024 ] || [ "$BACK_PORT" -lt 1024 ]; then
      warn "порт меньше 1024: systemd-сервис работает не под root — дай права (setcap) или выбери порт выше"
    fi
  fi

  cat > "$ROOT/.env" <<EOF
# сгенерировано scripts/install.sh
# PORT/FRONT_PORT — порты прослушивания приложения, BACK_PORT/FRONT_PORT_HOST — публикуемые (docker)
HOST=127.0.0.1
FRONT_HOST=127.0.0.1
$PORTS_BLOCK
PUBLIC_URL=$PUBLIC_URL

# ssl: пусто = http
SSL_CERTFILE=$SSL_CERT_ENV
SSL_KEYFILE=$SSL_KEY_ENV
DEV_CERTS=

CORS_ORIGINS=$CORS_ORIGINS

MONGO_URI=$MONGO_URI
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
  ok ".env записан (SECRET_KEY и ADMIN_SECRET сгенерированы)"
  [ -n "$BOT_TOKEN" ] || warn "BOT_TOKEN пуст — подключишь позже: ntlms edit-env"
  info "публичный адрес фронта: $PUBLIC_URL"
fi


# ============ шаг 6: запуск ============
say "шаг 6/8 — запуск"
if [ "$MODE" = docker ]; then
  open_firewall_ports "$FRONT_PORT" "$BACK_PORT"
  info "собираю образы и поднимаю контейнеры (mongo, redis, back, front, bot) — пара минут"
  (cd "$ROOT" && $DOCKER compose up -d --build) || die "docker compose упал, смотри вывод выше"

  info "жду, пока сервисы поднимутся"
  for i in $(seq 1 30); do
    RUNNING="$(cd "$ROOT" && $DOCKER compose ps --status running --services 2>/dev/null | tr '\n' ' ')"
    echo "$RUNNING" | grep -q back && echo "$RUNNING" | grep -q front && break
    sleep 2
  done

  # проверяем, что фронт отвечает
  WAIT_SCHEME="$SCHEME"
  CHECK_URL="$WAIT_SCHEME://127.0.0.1:$FRONT_PORT/"
  if curl -sk --max-time 5 -o /dev/null "$CHECK_URL"; then
    ok "фронт отвечает: $CHECK_URL"
  else
    warn "фронт пока не ответил — глянь логи: ntlms logs front"
  fi
  ok "подняты сервисы: $(cd "$ROOT" && $DOCKER compose ps --services | tr '\n' ' ')"
else
  info "venv-режим поднимается через systemd — это следующий шаг"
fi

# ============ шаг 7: systemd ============
say "шаг 7/8 — автозапуск (systemd)"
if command -v systemctl >/dev/null 2>&1; then
  . "$ROOT/scripts/install_systemd.sh"
  ok "автозапуск настроен"
else
  warn "systemd не найден — автозапуск пропускаю, поднимай руками: ntlms up"
fi

# ============ шаг 8: алиас ============
say "шаг 8/8 — алиас ntlms"
if ! grep -q 'scripts/ntlms.sh' "$HOME/.bashrc" 2>/dev/null; then
  echo "source \"$ROOT/scripts/ntlms.sh\"" >> "$HOME/.bashrc"
  ok "добавил source в ~/.bashrc"
else
  ok "алиас уже был в ~/.bashrc"
fi
ok "команды: ntlms up|down|restart|status|logs [svc]|certs|renew|edit-env|edit|update|help"

say "готово"
echo "   сайт:     $PUBLIC_URL"
echo "   api:      $SCHEME://${FRONT_DOMAIN:-127.0.0.1}:$BACK_PORT/v1"
echo "   админка:  $PUBLIC_URL/adminSecret"
echo "   https:    $([ "$CERT_KIND" = none ] && echo 'нет (http)' || echo "$CERT_KIND, серты в $CERT_DIR")"
echo "   режим:    $MODE  (systemd: $([ "$MODE" = docker ] && echo notalms-compose.service || echo notalms-back/front/bot.service))"
echo
echo "   чтобы алиас заработал: source ~/.bashrc (или новый терминал)"
if [ "$CERT_KIND" = selfsigned ]; then
  echo "   self-signed: браузер попросит принять сертификат — это норм"
fi

