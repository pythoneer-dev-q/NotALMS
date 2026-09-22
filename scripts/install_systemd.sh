#!/usr/bin/env bash
# ! scripts/install_systemd.sh — systemd-юниты, вызывается из install.sh
# MODE=docker -> notalms-compose.service (весь стек compose)
# MODE=venv   -> notalms-back/front/bot.service (python из .venv)
# ждет переменные: MODE, ROOT, SVC_USER, DOCKER, SUDO

units_dir=/etc/systemd/system

write_unit() { # write_unit <имя файла> (юнит приходит на stdin)
  $SUDO tee "$units_dir/$1" >/dev/null
}

if [ "$MODE" = docker ]; then
  info "пишу systemd-юнит для docker compose (нужен sudo)"
  write_unit notalms-compose.service <<EOF
[Unit]
Description=NotALMS (docker compose)
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$ROOT
ExecStart=$DOCKER compose up -d --remove-orphans
ExecStop=$DOCKER compose down
ExecReload=$DOCKER compose restart
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF
  $SUDO systemctl daemon-reload
  $SUDO systemctl enable notalms-compose.service >/dev/null 2>&1 \
    && ok "notalms-compose.service в автозапуске (стек поднимется при загрузке)" \
    || warn "не смог включить notalms-compose.service"
  $SUDO systemctl start notalms-compose.service >/dev/null 2>&1 \
    && ok "notalms-compose.service запущен" \
    || warn "старт юнита не прошел — проверь: systemctl status notalms-compose"
else
  SVC_USER="${SVC_USER:-${SUDO_USER:-$USER}}"
  if [ ! -x "$ROOT/.venv/bin/python" ]; then
    info "создаю venv и ставлю зависимости (может занять минуту)"
    python3 -m venv "$ROOT/.venv"
    "$ROOT/.venv/bin/pip" install --quiet --upgrade pip
    "$ROOT/.venv/bin/pip" install --quiet -r "$ROOT/required.txt"
    ok "venv готов: $ROOT/.venv"
  else
    ok "venv уже есть, обновляю зависимости"
    "$ROOT/.venv/bin/pip" install --quiet -r "$ROOT/required.txt" || warn "часть зависимостей не встала"
  fi

  gen_unit() { # gen_unit <имя> <модуль>
    cat <<EOF
[Unit]
Description=NotALMS $1
After=network.target

[Service]
Type=simple
User=$SVC_USER
WorkingDirectory=$ROOT
EnvironmentFile=$ROOT/.env
ExecStart=$ROOT/.venv/bin/python -m $2
Restart=always
RestartSec=5
LogRateLimitIntervalSec=30s
LogRateLimitBurst=200

[Install]
WantedBy=multi-user.target
EOF
  }

  info "пишу systemd-юниты (нужен sudo)"
  gen_unit back  'back.server.main'      | write_unit notalms-back.service
  gen_unit front 'front.server.main'     | write_unit notalms-front.service
  gen_unit bot   'back.auth.bot.main'    | write_unit notalms-bot.service
  $SUDO systemctl daemon-reload
  $SUDO systemctl enable --now notalms-back notalms-front notalms-bot 2>/dev/null \
    || warn "часть сервисов могла не стартовать (mongo поднята? смотри: ntlms logs back)"
  ok "юниты установлены и включены в автозапуск (юзер: $SVC_USER)"
fi

