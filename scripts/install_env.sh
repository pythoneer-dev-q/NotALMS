#!/usr/bin/env bash
# ! scripts/install_env.sh — генерация .env, вызывается из install.sh (не запускай отдельно)
BOT_TOKEN="$(ask '  токен бота от @BotFather (можно пропустить)' '')"
MONGO_WHERE="$(ask '  mongo где? (compose/atlas/custom)' 'compose')"
case "$MONGO_WHERE" in
  atlas)  MONGO_URI="$(ask '  строка подключения mongodb+srv://...' '')" ; [ -n "$MONGO_URI" ] || die "пустая строка atlas" ;;
  custom) MONGO_URI="$(ask '  uri mongo' 'mongodb://localhost:27017/')" ;;
  *)      MONGO_URI='mongodb://localhost:27017/' ; info "compose сам подставит mongodb://mongo:27017/ в контейнеры" ;;
esac
SECRET="$(openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
cat > "$ROOT/.env" <<EOF
# сгенерировано scripts/install.sh
HOST=127.0.0.1
PORT=8004
FRONT_HOST=127.0.0.1
FRONT_PORT=8005
BACK_PORT=8004
SSL_CERTFILE=
SSL_KEYFILE=
CORS_ORIGINS=*
MONGO_URI=$MONGO_URI
SECRET_KEY=$SECRET
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080
BOT_TOKEN=$BOT_TOKEN
BOT_DB_NAME=ntlmsauth
OTPLEN=6
ADMIN_SECRET=
WORKERS=1
MONGO_MAX_POOL=100
CACHE_TTL=60
RATE_LIMIT=20/minute
REDIS_URL=
EOF
ok ".env записан, SECRET_KEY сгенерирован случайный"
[ -n "$BOT_TOKEN" ] || warn "BOT_TOKEN пуст — бота подключишь позже (ntlms edit-env)"
