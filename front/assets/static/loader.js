// Общий индикатор загрузки для страниц.
// Использование: showLoader('загрузка...') / hideLoader().
// Разметка и стиль совпадают с уже существующими лоадерами (dash/admin/edit_course),
// поэтому страницы с новыми загрузками выглядят одинаково.
(function () {
    var CSS = ''
        + '#page-loader{position:fixed;inset:0;z-index:9600;display:flex;align-items:center;justify-content:center;'
        + 'background:rgba(5,5,15,.55);-webkit-backdrop-filter:blur(4px);backdrop-filter:blur(4px);'
        + 'opacity:0;pointer-events:none;transition:opacity .18s ease}'
        + '#page-loader.visible{opacity:1;pointer-events:auto}'
        + '#page-loader .page-loader__wrap{display:flex;flex-direction:column;align-items:center;gap:10px}'
        + '#page-loader .page-loader__svg{width:58px;height:58px;fill:var(--loader-color,var(--acc1,var(--primary,#818cf8)))}'
        + '#page-loader .page-loader__text{font-size:.85rem;color:var(--muted,#94a3b8);font-family:inherit}';

    var head = document.head || document.getElementsByTagName('head')[0];
    var style = document.createElement('style');
    style.textContent = CSS;
    head.appendChild(style);

    var SVG = '<svg class="page-loader__svg" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        + '<path d="M12,1A11,11,0,1,0,23,12,11,11,0,0,0,12,1Zm0,19a8,8,0,1,1,8-8A8,8,0,0,1,12,20Z" opacity=".25"/>'
        + '<path d="M10.72,19.9a8,8,0,0,1-6.5-9.79A7.77,7.77,0,0,1,10.4,4.16a8,8,0,0,1,9.49,6.52A1.54,1.54,0,0,0,21.38,12h.13a1.37,1.37,0,0,0,1.38-1.54,11,11,0,1,0-12.7,12.39A1.54,1.54,0,0,0,12,21.34h0A1.47,1.47,0,0,0,10.72,19.9Z">'
        + '<animateTransform attributeName="transform" type="rotate" dur="0.75s" values="0 12 12;360 12 12" repeatCount="indefinite"/>'
        + '</path></svg>';

    function ensure() {
        var el = document.getElementById('page-loader');
        if (!el) {
            el = document.createElement('div');
            el.id = 'page-loader';
            el.setAttribute('role', 'status');
            el.setAttribute('aria-live', 'polite');
            el.innerHTML = '<div class="page-loader__wrap">' + SVG
                + '<div class="page-loader__text">загрузка...</div></div>';
            (document.body || document.documentElement).appendChild(el);
        }
        return el;
    }

    window.showLoader = function (text) {
        var el = ensure();
        var t = el.querySelector('.page-loader__text');
        if (t) t.textContent = text || 'загрузка...';
        el.classList.add('visible');
    };

    window.hideLoader = function () {
        var el = document.getElementById('page-loader');
        if (el) el.classList.remove('visible');
    };

    // небольшой хелпер для inline-спиннера внутри кнопок/блоков
    window.inlineLoaderHtml = function (text) {
        return '<span class="inline-loader">' + SVG.replace('page-loader__svg', 'inline-loader__svg')
            + '<span>' + (text || 'загрузка...') + '</span></span>';
    };
})();
