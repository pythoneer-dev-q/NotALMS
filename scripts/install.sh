#!/usr/bin/env bash
# ! scripts/install.sh — интерактивная установка notalms (docker или venv+systemd)
# запуск: bash scripts/install.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODE_FILE="$ROOT/.ntlms-mode"

say()  { echo -e "\n\033[1;36m== $1\033[0m"; }
info() { echo "   $1"; }
ok()   { echo -e "   \033[0;32m+ $1\033[0m"; }
warn() { echo -e "   \033[0;33m! $1\033[0m"; }
die()  { echo -e "\033[0;31mERROR: $1\033[0m"; exit 1; }

ask() { # ask "вопрос" "дефолт" -> ответ в stdout
  local q="$1" d="${2:-}"
  read -rp "$q${d:+ [$d]}: " a
  echo "${a:-$d}"
}

banner() {
  cat <<'EOF'

  NotALMS — установка
  -------------------
  скрипт проведет по шагам: env, серты, запуск, systemd, алиас ntlms.
  каждый шаг можно прервать ctrl+c, ничего необратимого не делается.

EOF
}

banner
say "шаг 1/6 — способ запуска"
echo "   docker      — всё в контейнерах (mongo тоже), рекомендую для начала"
echo "   venv        — python-venv на хосте + systemd-юниты (mongo нужна своя)"
MODE="$(ask 'способ (docker/venv)' 'docker')"
case "$MODE" in docker|venv) ;; *) die "не понимаю '$MODE', нужно docker или venv" ;; esac
echo "$MODE" > "$MODE_FILE"
info "способ: $MODE (записал в .ntlms-mode, его читает алиас ntlms)"

say "шаг 2/6 — проверка зависимостей"
if [ "$MODE" = docker ]; then
  command -v docker >/dev/null || die "docker не найден, поставь с https://docs.docker.com/engine/install/"
  docker compose version >/dev/null 2>&1 || die "docker compose plugin не найден"
  ok "docker и compose на месте"
else
  command -v python3 >/dev/null || die "python3 не найден"
  PY_VER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
  ok "python3 $PY_VER"
  command -v systemctl >/dev/null || die "systemd не найден, venv-режим рассчитан на linux+systemd"
  ok "systemd на месте"
fi

say "шаг 3/6 — .env"
GEN_ENV=0
if [ -f "$ROOT/.env" ]; then
  if ask '  .env уже есть, перезаписать? (y/N)' 'N' | grep -qi '^y'; then
    cp "$ROOT/.env" "$ROOT/.env.bak.$(date +%s)" && info "старый сохранил в .env.bak.*"
    GEN_ENV=1
  else
    ok "использую существующий .env"
  fi
else
  GEN_ENV=1
fi

if [ "$GEN_ENV" = 1 ]; then
  source "$ROOT/scripts/install_env.sh"
fi

say "шаг 4/6 — сертификаты (https)"
USE_SSL="$(ask '  включить https? (y/N)' 'N')"
if echo "$USE_SSL" | grep -qi '^y'; then
  SSL_KIND="$(ask '  серты какие? (self-signed/real)' 'self-signed')"
  mkdir -p "$ROOT/certs"
  if [ "$SSL_KIND" = self-signed ]; then
    info "генерирую self-signed в ./certs"
    openssl req -x509 -newkey rsa:2048 -sha256 -days 365 -nodes \
      -keyout "$ROOT/certs/key.pem" -out "$ROOT/certs/cert.pem" \
      -subj "/CN=$(hostname)" \
      -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
    CERT=cert.pem; KEY=key.pem
    ok "сертификаты готовы (браузер скажет 'не доверенный' — норм для self-signed)"
  else
    info "скопируй cert.pem и key.pem в $ROOT/certs"
    CERT="$(ask '  имя файла сертификата' 'cert.pem')"
    KEY="$(ask '  имя файла ключа' 'key.pem')"
    [ -f "$ROOT/certs/$CERT" ] || die "$ROOT/certs/$CERT не найден, положи файл и перезапусти"
  fi
  # включаем ssl в .env
  sed -i "s|^SSL_CERTFILE=.*|SSL_CERTFILE=$ROOT/certs/$CERT|" "$ROOT/.env"
  sed -i "s|^SSL_KEYFILE=.*|SSL_KEYFILE=$ROOT/certs/$KEY|" "$ROOT/.env"
  ok "ssl прописан в .env"
else
  ok "остаемся на http"
fi

say "шаг 5/6 — запуск"
if [ "$MODE" = docker ]; then
  info "собираю и поднимаю контейнеры (mongo, back, front, bot) — может занять пару минут"
  (cd "$ROOT" && docker compose up -d --build) || die "docker compose упал, смотри вывод выше"
  ok "контейнеры подняты: $(cd "$ROOT" && docker compose ps --services | tr '\n' ' ')"
else
  . "$ROOT/scripts/install_systemd.sh"
fi

say "шаг 6/6 — алиас ntlms"
if ! grep -q 'scripts/ntlms.sh' "$HOME/.bashrc" 2>/dev/null; then
  echo "source \"$ROOT/scripts/ntlms.sh\"" >> "$HOME/.bashrc"
  ok "добавил source в ~/.bashrc"
else
  ok "алиас уже был в ~/.bashrc"
fi
ok "команды: ntlms up | down | restart | status | logs [back|front|bot|mongo] | edit-env | edit | update | help"

say "готово"
if [ "$MODE" = docker ]; then
  echo "   фронт:  http://localhost:${FRONT_PORT:-8005}/  (или https, если включал серты)"
  echo "   api:    http://localhost:${BACK_PORT:-8004}/v1"
else
  echo "   фронт:  http://localhost:8005/   api: http://localhost:8004/v1"
  echo "   статус: ntlms status"
fi
echo "   чтобы алиас заработал: source ~/.bashrc (или просто открой новый терминал)"
