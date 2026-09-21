# Cloudflare Turnstile

1. Откройте [Cloudflare Turnstile](https://dash.cloudflare.com/?to=/:account/turnstile), войдите или создайте бесплатный аккаунт.
2. Создайте widget типа `Managed`, добавьте домен платформы и сохраните два ключа.
3. В `.env` рядом с проектом задайте:

```env
TURNSTILE_SITE_KEY=публичный_site_key
TURNSTILE_SECRET_KEY=секретный_secret_key
CAPTCHA_SUSPICIOUS_RPS=15
```

`TURNSTILE_SITE_KEY` попадает в браузер и используется только для показа виджета.
`TURNSTILE_SECRET_KEY` остаётся на сервере: он проверяется через Cloudflare Siteverify
для каждого входа и регистрации. Не добавляйте `.env` в git.

Пока один из ключей пустой, Turnstile отключён для локальной разработки. После
превышения 15 запросов в секунду с одного IP API возвращает `captcha_required`,
а форма входа открывает проверку. Токен Turnstile одноразовый и живёт пять минут,
поэтому при ошибке виджет нужно пройти повторно.
