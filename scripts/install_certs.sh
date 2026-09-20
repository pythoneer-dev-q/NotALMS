#!/usr/bin/env bash
# ! scripts/install_certs.sh — сертификаты: self-signed / letsencrypt / свои файлы
# вызывается из install.sh; ждет переменные ROOT, FRONT_DOMAIN, BACK_DOMAIN, CERT_EMAIL, SUDO, MODE

CERT_DIR="$ROOT/certs"

# какие домены попадут в SAN сертификата
cert_san() {
  local san="DNS:localhost,IP:127.0.0.1"
  [ -n "${FRONT_DOMAIN:-}" ] && san="DNS:$FRONT_DOMAIN,$san"
  if [ -n "${BACK_DOMAIN:-}" ] && [ "$BACK_DOMAIN" != "$FRONT_DOMAIN" ]; then
    san="DNS:$BACK_DOMAIN,$san"
  fi
  echo "$san"
}

certs_selfsigned() {
  mkdir -p "$CERT_DIR"
  local san; san="$(cert_san)"
  info "генерирую self-signed (SAN: $san, 365 дней)"
  openssl req -x509 -newkey rsa:2048 -sha256 -days 365 -nodes \
    -keyout "$CERT_DIR/key.pem" -out "$CERT_DIR/cert.pem" \
    -subj "/CN=${FRONT_DOMAIN:-localhost}" \
    -addext "subjectAltName=$san" >/dev/null 2>&1 \
    || die "openssl не смог сгенерировать сертификат"
  chmod 644 "$CERT_DIR/cert.pem"; chmod 600 "$CERT_DIR/key.pem"
  ok "серты готовы: certs/cert.pem + certs/key.pem (браузер поругается на недоверенный — это норм)"
}

certs_existing() {
  local c k
  c="$(ask '  путь к сертификату (fullchain/cert .pem)' '')"
  k="$(ask '  путь к приватному ключу (.pem)' '')"
  [ -n "$c" ] && [ -f "$c" ] || die "файл сертификата не найден: $c"
  [ -n "$k" ] && [ -f "$k" ] || die "файл ключа не найден: $k"
  mkdir -p "$CERT_DIR"
  cp "$c" "$CERT_DIR/cert.pem"; cp "$k" "$CERT_DIR/key.pem"
  chmod 644 "$CERT_DIR/cert.pem"; chmod 600 "$CERT_DIR/key.pem"
  ok "серты скопировал в certs/cert.pem + certs/key.pem"
}

# копирование выданного LE-серта в проект
copy_le_cert() { # $1 = домен (папка /etc/letsencrypt/live)
  mkdir -p "$CERT_DIR"
  $SUDO cp "/etc/letsencrypt/live/$1/fullchain.pem" "$CERT_DIR/cert.pem"
  $SUDO cp "/etc/letsencrypt/live/$1/privkey.pem" "$CERT_DIR/key.pem"
  $SUDO chown "$(id -u):$(id -g)" "$CERT_DIR/cert.pem" "$CERT_DIR/key.pem" 2>/dev/null || true
  chmod 644 "$CERT_DIR/cert.pem"; chmod 600 "$CERT_DIR/key.pem"
}

# продление: certbot сам обновит и вызовет deploy-hook — он скопирует серты и перезапустит сервис
le_install_renew_hook() { # $1 = домен
  local hook=/etc/letsencrypt/renewal-hooks/deploy/ntlms.sh
  info "прописываю deploy-hook на продление серта"
  $SUDO mkdir -p /etc/letsencrypt/renewal-hooks/deploy
  $SUDO tee "$hook" >/dev/null <<EOF
#!/bin/sh
# автопродление letsencrypt для notalms
cp /etc/letsencrypt/live/$1/fullchain.pem "$CERT_DIR/cert.pem" 2>/dev/null || exit 0
cp /etc/letsencrypt/live/$1/privkey.pem "$CERT_DIR/key.pem" 2>/dev/null || exit 0
chmod 644 "$CERT_DIR/cert.pem"; chmod 600 "$CERT_DIR/key.pem"
if [ "\$(cat "$ROOT/.ntlms-mode" 2>/dev/null)" = docker ]; then
  cd "$ROOT" && docker compose restart back front
else
  systemctl restart notalms-back notalms-front
fi
EOF
  $SUDO chmod +x "$hook"
  if command -v systemctl >/dev/null 2>&1; then
    $SUDO systemctl enable --now certbot.timer >/dev/null 2>&1 \
      && ok "certbot.timer включен (серт будет продлеваться сам)" \
      || warn "включи продление сам: systemctl enable --now certbot.timer"
  fi
}

certs_letsencrypt() {
  [ -n "${FRONT_DOMAIN:-}" ] || die "для Let's Encrypt нужен домен (домен спрошу на шаге домены/порты)"
  if [ -z "${CERT_EMAIL:-}" ]; then
    CERT_EMAIL="$(ask '  email для Let'"'"'s Encrypt (важен для писем об истечении)' '')"
  fi
  [ -n "$CERT_EMAIL" ] || die "без email letsencrypt не выдаст сертификат"

  if ! command -v certbot >/dev/null 2>&1; then
    if [ "${PKG_FAM:-}" = apt ]; then
      info "ставлю certbot"
      $SUDO apt-get update -qq && $SUDO apt-get install -y -qq certbot
    elif [ "${PKG_FAM:-}" = dnf ]; then
      info "ставлю certbot"
      $SUDO dnf -y install certbot
    else
      die "certbot не найден — поставь его руками (apt/dnf/snap install certbot)"
    fi
  fi

  local domains=(-d "$FRONT_DOMAIN")
  if [ -n "${BACK_DOMAIN:-}" ] && [ "$BACK_DOMAIN" != "$FRONT_DOMAIN" ]; then
    domains+=(-d "$BACK_DOMAIN")
  fi

  info "выписываю серт: certbot --standalone ${domains[*]}"
  info "порт 80 должен быть свободен, а домен уже смотреть на этот сервер"
  $SUDO certbot certonly --standalone "${domains[@]}" \
    --agree-tos -m "$CERT_EMAIL" --non-interactive --keep-until-expiring \
    || die "certbot не смог выписать серт: проверь dns домена и что 80 порт свободен"

  copy_le_cert "$FRONT_DOMAIN"
  le_install_renew_hook "$FRONT_DOMAIN"
  ok "серт Let's Encrypt выписан: certs/cert.pem + certs/key.pem"
}

# спрашиваем что делать с сертами и возвращаем имя варианта
ask_certs() {
  echo "   варианты:" >&2
  echo "     1) http без сертов (проще всего)" >&2
  echo "     2) self-signed (локально/тесты, браузер поругается)" >&2
  echo "     3) Let's Encrypt (нужен домен и свободный 80 порт)" >&2
  echo "     4) у меня уже есть серты" >&2
  local v; v="$(ask '  что делаем с https? (1-4)' '1')"
  case "$v" in
    1|http|нет|no|n) echo none ;;
    2|self|self-signed) echo selfsigned ;;
    3|le|letsencrypt|lets) echo letsencrypt ;;
    4|own|есть|my) echo existing ;;
    *) echo none ;;
  esac
}
