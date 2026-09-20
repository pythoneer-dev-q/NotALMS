#!/usr/bin/env bash
# ! scripts/ntlms.sh — алиас ntlms: up/down/restart/status/logs/certs/renew/edit-env/edit/update
# ставится install.sh строкой: source "<путь>/scripts/ntlms.sh"

NTLMS_ROOT="${NTLMS_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
NTLMS_MODE_FILE="$NTLMS_ROOT/.ntlms-mode"
NTLMS_MODE="$(cat "$NTLMS_MODE_FILE" 2>/dev/null || echo docker)"
NTLMS_EDITOR="${EDITOR:-nano}"

# docker без sudo, если группа подхватилась; иначе через sudo
if [ "$NTLMS_MODE" = docker ]; then
  if docker info >/dev/null 2>&1; then NTLMS_DOCKER="docker"; else NTLMS_DOCKER="sudo docker"; fi
fi

ntlms_help() {
  cat <<EOF
ntlms — управление notalms (режим: $NTLMS_MODE)

  ntlms up              поднять всё
  ntlms down            остановить
  ntlms restart         перезапустить
  ntlms status          что живо
  ntlms logs [svc]      хвост логов; svc = back|front|bot|mongo (docker) / back|front|bot (venv)
  ntlms certs           что с сертификатами и когда истекают
  ntlms renew           продлить letsencrypt и перезапустить
  ntlms edit-env        открыть .env в редакторе
  ntlms edit            открыть docker-compose.yml (docker) или редактор юнитов (venv)
  ntlms update          git pull + пересобрать/перезапустить
  ntlms help            эта шпаргалка
EOF
}

# docker-команды
d_up()      { (cd "$NTLMS_ROOT" && $NTLMS_DOCKER compose up -d); }
d_down()    { (cd "$NTLMS_ROOT" && $NTLMS_DOCKER compose down); }
d_restart() { (cd "$NTLMS_ROOT" && $NTLMS_DOCKER compose restart "$@"); }
d_status()  { (cd "$NTLMS_ROOT" && $NTLMS_DOCKER compose ps); }
d_logs()    { (cd "$NTLMS_ROOT" && $NTLMS_DOCKER compose logs -f --tail=100 "$@"); }

# venv/systemd-команды
v_svc() { echo "notalms-$1"; }
v_up()      { for s in back front bot; do sudo systemctl start "$(v_svc "$s")"; done; }
v_down()    { for s in back front bot; do sudo systemctl stop "$(v_svc "$s")"; done; }
v_restart() { for s in back front bot; do sudo systemctl restart "$(v_svc "$s")"; done; }
v_status()  { systemctl status notalms-back notalms-front notalms-bot --no-pager "$@"; }
v_logs()    { [ -n "${1:-}" ] && sudo journalctl -u "$(v_svc "$1")" -f -n 100 || sudo journalctl -u notalms-back -u notalms-front -u notalms-bot -f -n 50; }

# подрежимы: отдельный сервис или всё сразу
svc_or_all() { # $1 = сервис, $2 = действие "все"
  case "$1" in
    back|front|bot) echo "$1" ;;
    mongo) [ "$NTLMS_MODE" = docker ] && echo mongo || { echo "mongo нет в venv-режиме, он у тебя на хосте" >&2; return 1; } ;;
    "") echo "$2" ;;
    *) echo "не знаю сервис '$1' (back/front/bot/mongo)" >&2; return 1 ;;
  esac
}

ntlms() {
  local cmd="${1:-help}"; shift || true
  case "$cmd" in
    up)      [ "$NTLMS_MODE" = docker ] && d_up || v_up ;;
    down)    [ "$NTLMS_MODE" = docker ] && d_down || v_down ;;
    restart)
      if [ -n "${1:-}" ]; then
        s="$(svc_or_all "$1" '')" || return 1
        [ "$NTLMS_MODE" = docker ] && d_restart "$s" || sudo systemctl restart "$(v_svc "$s")"
      else
        [ "$NTLMS_MODE" = docker ] && d_restart || v_restart
      fi ;;
    status)  [ "$NTLMS_MODE" = docker ] && d_status || v_status ;;
    certs)
      local c="$NTLMS_ROOT/certs/cert.pem"
      if [ ! -f "$c" ]; then echo "сертов нет ($c) — поднимаемся по http"; return 0; fi
      echo "серт: $c"
      openssl x509 -in "$c" -noout -subject -issuer -dates 2>/dev/null || echo "не смог прочитать серт"
      ;;
    renew)
      command -v certbot >/dev/null 2>&1 || { echo "certbot не установлен — серт не letsencrypt?"; return 1; }
      sudo certbot renew --quiet && echo "продлил" || { echo "нечего продлевать или ошибка"; return 1; }
      if [ "$NTLMS_MODE" = docker ]; then d_restart back front; else v_restart; fi
      ;;
    logs)
      s="$(svc_or_all "${1:-}" all)" || return 1
      [ "$NTLMS_MODE" = docker ] && d_logs "$s" || v_logs "$( [ "$s" = all ] && echo '' || echo "$s" )" ;;
    edit-env) "$NTLMS_EDITOR" "$NTLMS_ROOT/.env" && echo "env изменен, не забудь: ntlms restart" ;;
    edit)
      if [ "$NTLMS_MODE" = docker ]; then
        "$NTLMS_EDITOR" "$NTLMS_ROOT/docker-compose.yml" && echo "compose изменен, не забудь: ntlms up"
      else
        sudo systemctl edit notalms-back notalms-front notalms-bot
      fi ;;
    update)
      (cd "$NTLMS_ROOT" && git pull --ff-only) || return 1
      if [ "$NTLMS_MODE" = docker ]; then d_up; else
        "$NTLMS_ROOT/.venv/bin/pip" install --quiet -r "$NTLMS_ROOT/required.txt"
        v_restart
      fi
      echo "обновлено" ;;
    help|--help|-h) ntlms_help ;;
    *) ntlms_help; echo; echo "не знаю команду '$cmd'" ;;
  esac
}
