// общий тост для всех страниц: закрывается крестиком или свайпом
(function () {
    var CSS = '.toast__card{position:relative;padding-right:2.6rem !important;touch-action:pan-y}'
        + '.toast-card{position:relative;padding-right:2.6rem !important;touch-action:pan-y}'
        + '.toast__x{position:absolute;top:.3rem;right:.35rem;background:none;border:0;color:var(--muted);'
        + 'cursor:pointer;font-size:1rem;line-height:1;padding:.25rem .3rem;border-radius:6px}'
        + '.toast__x:hover{color:var(--text);background:rgba(255,255,255,.06)}';

    var head = document.head || document.getElementsByTagName('head')[0];
    var style = document.createElement('style');
    style.textContent = CSS;
    head.appendChild(style);

    function container() {
        var box = document.getElementById('toast');
        if (!box) {
            box = document.createElement('div');
            box.id = 'toast';
            box.className = 'toast';
            document.body.appendChild(box);
        }
        box.style.display = 'flex';
        return box;
    }

    function hide(card, box) {
        if (!card || card.getAttribute('data-closing') === '1') return;
        card.setAttribute('data-closing', '1');
        card.style.transform = '';
        if (card.id === 'toast-card') {
            // разметка админских страниц: прячем контейнер целиком
            box.style.display = 'none';
        } else {
            card.classList.add('out');
            setTimeout(function () {
                if (card.parentNode) card.parentNode.removeChild(card);
            }, 320);
        }
    }

    function bindSwipe(card, box) {
        var sx = null, sy = null;
        card.addEventListener('touchstart', function (e) {
            sx = e.touches[0].clientX;
            sy = e.touches[0].clientY;
        }, { passive: true });
        card.addEventListener('touchmove', function (e) {
            if (sx === null) return;
            var dx = e.touches[0].clientX - sx, dy = e.touches[0].clientY - sy;
            if (Math.abs(dx) > Math.abs(dy)) card.style.transform = 'translateX(' + dx + 'px)';
            else if (dy < 0) card.style.transform = 'translateY(' + dy + 'px)';
        }, { passive: true });
        card.addEventListener('touchend', function (e) {
            var dx = e.changedTouches[0].clientX - (sx || 0);
            var dy = e.changedTouches[0].clientY - (sy || 0);
            sx = sy = null;
            if (Math.abs(dx) > 60 || dy < -40) hide(card, box);
            else card.style.transform = '';
        });
    }

    window.showToast = function (msg, err) {
        var box = container();
        var card = box.querySelector('#toast-card');
        if (card) {
            card.className = 'toast-card' + (err ? ' err' : '');
            card.innerHTML = '<span class="toast__msg"></span><button class="toast__x" aria-label="закрыть">&times;</button>';
            card.querySelector('.toast__msg').textContent = msg;
        } else {
            box.innerHTML = '<div class="toast__card' + (err ? ' err' : '') + '">'
                + '<span class="ti ' + (err ? 'ti-alert-triangle' : 'ti-circle-check')
                + '" style="font-size:1.1rem;color:' + (err ? '#f87171' : 'var(--acc1)') + '"></span>'
                + '<span class="toast__msg"></span>'
                + '<button class="toast__x" aria-label="закрыть"><i class="ti ti-x"></i></button></div>';
            card = box.querySelector('.toast__card');
            card.querySelector('.toast__msg').textContent = msg;
        }
        card.setAttribute('data-closing', '');
        var close = card.querySelector('.toast__x');
        if (close) close.onclick = function (e) { e.stopPropagation(); hide(card, box); };
        if (card.getAttribute('data-swipe') !== '1') {
            card.setAttribute('data-swipe', '1');
            bindSwipe(card, box);
        }
        clearTimeout(window._tt);
        window._tt = setTimeout(function () { hide(card, box); }, 4200);
    };

    window.hideToast = function () {
        var box = document.getElementById('toast');
        if (!box) return;
        var card = box.querySelector('#toast-card') || box.querySelector('.toast__card');
        if (card) hide(card, box);
    };
})();
