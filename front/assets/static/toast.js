// Shared toast layer for every static page.
// It normalizes older page-local #toast/#toast-card markup and keeps close,
// swipe-dismiss and auto-dismiss behavior intact.
(function () {
    var TOAST_TIMEOUT = 4200;
    var STYLE_ID = 'notalms-toast-style';

    var CSS = ''
        + '#toast.toast{position:fixed!important;top:calc(14px + env(safe-area-inset-top))!important;'
        + 'left:0!important;right:0!important;bottom:auto!important;z-index:9500!important;'
        + 'display:none;flex-direction:column!important;align-items:center!important;justify-content:flex-start!important;'
        + 'gap:10px!important;margin:0!important;padding:0 14px!important;background:transparent!important;'
        + 'border:0!important;box-shadow:none!important;pointer-events:none!important;overflow:visible!important}'
        + '#toast .toast__card,#toast .toast-card{position:relative!important;display:flex!important;'
        + 'align-items:center!important;gap:10px!important;width:min(520px,calc(100vw - 28px))!important;'
        + 'max-width:min(520px,calc(100vw - 28px))!important;min-height:44px!important;'
        + 'padding:11px 44px 11px 14px!important;border-radius:12px!important;'
        + 'font-family:Onest,system-ui,-apple-system,BlinkMacSystemFont,\"Segoe UI\",sans-serif!important;'
        + 'font-size:14px!important;line-height:1.45!important;text-align:left!important;color:var(--text,#e2e8f0)!important;'
        + 'background:linear-gradient(180deg,color-mix(in srgb,var(--primary,#6366f1) 8%,var(--surface2,var(--panel,var(--card,#131019)))),var(--surface2,var(--panel,var(--card,#131019))))!important;'
        + 'border:1px solid var(--line2,rgba(255,255,255,.14))!important;'
        + 'border-left:3px solid var(--acc1,var(--primary,#818cf8))!important;'
        + 'outline:0!important;box-shadow:0 18px 44px -18px rgba(0,0,0,.8)!important;'
        + 'pointer-events:auto!important;touch-action:pan-y!important;overflow:hidden!important;overflow-wrap:anywhere!important;'
        + 'transform:translate3d(0,0,0);animation:notalms-toast-in .24s ease-out!important}'
        + '#toast .toast__card.err,#toast .toast-card.err{border-color:rgba(239,68,68,.55)!important;'
        + 'border-left-color:#ef4444!important}'
        + '#toast .toast__icon{flex:0 0 auto!important;font-size:18px!important;line-height:1!important;color:var(--acc1,var(--primary,#818cf8))!important}'
        + '#toast .err .toast__icon{color:#f87171!important}'
        + '#toast .toast__msg{flex:1 1 auto!important;min-width:0!important}'
        + '#toast .toast__x{position:absolute!important;top:6px!important;right:7px!important;'
        + 'display:inline-flex!important;align-items:center!important;justify-content:center!important;width:30px!important;height:30px!important;'
        + 'padding:0!important;border:0!important;border-radius:8px!important;background:transparent!important;'
        + 'color:var(--muted,rgba(255,255,255,.58))!important;cursor:pointer!important;font:inherit!important;line-height:1!important}'
        + '#toast .toast__x:hover{color:var(--text,#fff)!important;background:rgba(255,255,255,.08)!important}'
        + '#toast .toast__card.out,#toast .toast-card.out{animation:notalms-toast-out .22s ease-in forwards!important}'
        + '@keyframes notalms-toast-in{from{opacity:0;transform:translate3d(0,-10px,0)}to{opacity:1;transform:translate3d(0,0,0)}}'
        + '@keyframes notalms-toast-out{to{opacity:0;transform:translate3d(0,-10px,0)}}'
        + '@media(max-width:700px){#toast.toast{top:calc(10px + env(safe-area-inset-top))!important;padding:0 10px!important}'
        + '#toast .toast__card,#toast .toast-card{width:calc(100vw - 20px)!important;max-width:calc(100vw - 20px)!important;'
        + 'font-size:13.5px!important;padding:10px 40px 10px 12px!important;border-radius:11px!important}}';

    function installStyle() {
        if (document.getElementById(STYLE_ID)) return;
        var style = document.createElement('style');
        style.id = STYLE_ID;
        style.textContent = CSS;
        (document.head || document.documentElement).appendChild(style);
    }

    function ensureContainer() {
        installStyle();
        var box = document.getElementById('toast');
        if (!box) {
            box = document.createElement('div');
            box.id = 'toast';
            (document.body || document.documentElement).appendChild(box);
        }
        box.className = 'toast';
        box.style.display = 'flex';
        return box;
    }

    function hide(card, box) {
        if (!card || card.dataset.closing === '1') return;
        card.dataset.closing = '1';
        card.style.transform = '';
        card.classList.add('out');
        clearTimeout(card._toastTimer);
        setTimeout(function () {
            if (card.parentNode) card.parentNode.removeChild(card);
            if (box && !box.children.length) box.style.display = 'none';
        }, 260);
    }

    function bindSwipe(card, box) {
        var sx = null;
        var sy = null;
        var active = false;

        card.addEventListener('touchstart', function (e) {
            if (!e.touches || !e.touches.length) return;
            sx = e.touches[0].clientX;
            sy = e.touches[0].clientY;
            active = true;
        }, { passive: true });

        card.addEventListener('touchmove', function (e) {
            if (!active || sx === null || !e.touches || !e.touches.length) return;
            var dx = e.touches[0].clientX - sx;
            var dy = e.touches[0].clientY - sy;
            if (Math.abs(dx) > Math.abs(dy)) {
                card.style.transform = 'translate3d(' + dx + 'px,0,0)';
            } else if (dy < 0) {
                card.style.transform = 'translate3d(0,' + dy + 'px,0)';
            }
        }, { passive: true });

        card.addEventListener('touchend', function (e) {
            if (!active) return;
            var t = e.changedTouches && e.changedTouches[0];
            var dx = t ? t.clientX - (sx || 0) : 0;
            var dy = t ? t.clientY - (sy || 0) : 0;
            sx = sy = null;
            active = false;
            if (Math.abs(dx) > 70 || dy < -44) hide(card, box);
            else card.style.transform = '';
        }, { passive: true });
    }

    function buildCard(msg, err) {
        var card = document.createElement('div');
        card.className = 'toast__card' + (err ? ' err' : '');
        card.innerHTML = ''
            + '<span class="toast__icon ti ' + (err ? 'ti-alert-triangle' : 'ti-circle-check') + '" aria-hidden="true"></span>'
            + '<span class="toast__msg"></span>'
            + '<button type="button" class="toast__x" aria-label="закрыть"><i class="ti ti-x"></i></button>';
        card.querySelector('.toast__msg').textContent = String(msg || '');
        return card;
    }

    window.showToast = function (msg, err) {
        var box = ensureContainer();
        box.innerHTML = '';

        var card = buildCard(msg, !!err);
        box.appendChild(card);

        var close = card.querySelector('.toast__x');
        if (close) close.onclick = function (e) {
            e.preventDefault();
            e.stopPropagation();
            hide(card, box);
        };

        bindSwipe(card, box);
        card._toastTimer = setTimeout(function () { hide(card, box); }, TOAST_TIMEOUT);
    };

    window.hideToast = function () {
        var box = document.getElementById('toast');
        if (!box) return;
        Array.prototype.slice.call(box.children).forEach(function (card) {
            hide(card, box);
        });
    };

    if (!window.toast) {
        window.toast = window.showToast;
    }

    // Заблокированный аккаунт не должен оставаться на рабочей странице с
    // устаревшим токеном. Сервер маркирует такой ответ отдельным заголовком.
    var nativeFetch = window.fetch;
    if (nativeFetch && !window.__notalmsBlockedGuard) {
        window.__notalmsBlockedGuard = true;
        window.fetch = function () {
            var requestInit = arguments[1] || {};
            return nativeFetch.apply(this, arguments).then(function (response) {
                if (response.status === 403 && response.headers.get('X-Account-Blocked') === '1') {
                    var blockedToken = response.headers.get('X-Blocked-Token');
                    if (blockedToken) localStorage.setItem('token', blockedToken);
                    if (location.pathname !== '/blocked') location.replace('/blocked');
                } else if (response.status === 401 && location.pathname !== '/' && location.pathname !== '/login') {
                    var headers = requestInit.headers;
                    var authorization = headers && (headers.Authorization || headers.authorization
                        || (typeof headers.get === 'function' && headers.get('Authorization')));
                    if (authorization) {
                        localStorage.removeItem('token');
                        location.replace('/');
                    }
                }
                if (response.headers.get('X-Captcha-Required') === '1' && window.openCaptchaChallenge) {
                    window.openCaptchaChallenge();
                }
                return response;
            });
        };
    }

    installStyle();
})();
