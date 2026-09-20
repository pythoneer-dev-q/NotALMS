#!/usr/bin/env bash
# ! scripts/install_systemd.sh — venv + systemd-юниты, вызывается из install.sh
info "создаю venv и ставлю зависимости"
python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/pip" install --quiet --upgrade pip
"$ROOT/.venv/bin/pip" install --quiet -r "$ROOT/required.txt"
ok "venv готов"

SVC_USER="$(ask '  от какого юзера пускать сервисы' "${SUDO_USER:-$USER}")"
gen_unit() { # gen_unit "имя" "команда"
  cat <<EOF
[Unit]
Description=NotALMS $1
After=network.target

[Service]
Type=simple
User=$SVC_USER
WorkingDirectory=$ROOT
EnvironmentFile=$ROOT/.env
ExecStart=$ROOT/.venv/bin/$2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
}

SUDO=""
[ "$(id -u)" = 0 ] || SUDO="sudo"
echo "  | пишу systemd-юниты (нужен sudo)"
gen_unit back  'python -m back.server.main'   | $SUDO tee /etc/systemd/system/notalms-back.service  >/dev/null
gen_unit front 'python -m front.server.main'  | $SUDO tee /etc/systemd/system/notalms-front.service >/dev/null
gen_unit bot   'python -m back.auth.bot.main' | $SUDO tee /etc/systemd/system/notalms-bot.service   >/dev/null
$SUDO systemctl daemon-reload
$SUDO systemctl enable --now notalms-back notalms-front notalms-bot 2>/dev/null \
  || warn "часть сервисов могла не стартовать (нет mongo?) — смотри: ntlms logs back"
ok "юниты установлены и включены в автозапуск"
