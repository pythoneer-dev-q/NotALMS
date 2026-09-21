// Общий рендер контент-блоков урока.
// Используется и на странице курса (course.html), и в превью редактора (edit_course.html),
// поэтому блоки выглядят одинаково везде. Разметка и классы — как в course.html.
(function () {
    function escapeHtml(s) {
        if (s === null || s === undefined) return '';
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function decodeEntities(s) {
        var ta = document.createElement('textarea');
        ta.innerHTML = s;
        return ta.value;
    }

    function safeUrl(u) {
        if (u === null || u === undefined) return '';
        var s = String(u).trim();
        if (!s) return '';
        if (s.indexOf('&amp;') !== -1 || s.indexOf('&quot;') !== -1 || s.indexOf('&#') !== -1) {
            s = decodeEntities(s);
        }
        if (/^\s*javascript:/i.test(s)) return '';
        return s
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }

    function renderImage(block) {
        var src = block.src || block.url || block.value || block.image || '';
        if (src && typeof src === 'object') {
            src = src.src || src.url || '';
        }
        var alt = block.alt || block.caption || block.title || '';
        if (!src) {
            return '<div class="lesson-warning">изображение не указано</div>';
        }
        return '<img class="lesson-img" src="' + safeUrl(src) + '" alt="' + escapeHtml(alt)
            + '" loading="lazy" decoding="async" referrerpolicy="no-referrer"'
            + ' onerror="this.style.display=\'none\';this.insertAdjacentHTML(\'afterend\',\''
            + '&lt;div class=&quot;lesson-warning&quot;&gt;не удалось загрузить изображение&lt;/div&gt;\')" />';
    }

    function videoEmbedUrl(url) {
        try {
            var u = new URL(url);
            var host = u.hostname.replace(/^www\./, '');
            if (host === 'youtu.be') return 'https://www.youtube.com/embed/' + u.pathname.slice(1);
            if (host.endsWith('youtube.com')) {
                if (u.pathname.indexOf('/watch') === 0) return 'https://www.youtube.com/embed/' + (u.searchParams.get('v') || '');
                if (u.pathname.indexOf('/shorts/') === 0) return 'https://www.youtube.com/embed/' + u.pathname.split('/')[2];
                if (u.pathname.indexOf('/embed/') === 0) return url;
            }
            if (host.endsWith('vk.com') || host.endsWith('vkvideo.ru')) {
                var m = u.pathname.match(/\/video(-?\d+)_(\d+)/);
                if (m) return 'https://vk.com/video_ext.php?oid=' + m[1] + '&id=' + m[2];
            }
            if (host.endsWith('rutube.ru')) {
                var r = u.pathname.match(/\/video\/([a-z0-9]+)/i);
                if (r) return 'https://rutube.ru/play/embed/' + r[1];
            }
            return null;
        } catch (e) { return null; }
    }

    function renderVideo(block) {
        var attrs = ' allow="autoplay; encrypted-media; fullscreen; picture-in-picture" allowfullscreen frameborder="0"';
        if (block && block.embed) {
            if (block.embed_type === 'script') {
                return '<div class="lesson-video-embed" data-embed-script="' + escapeHtml(block.embed) + '"></div>';
            }
            return '<div class="lesson-video"><iframe src="' + safeUrl(block.embed) + '"' + attrs + '></iframe></div>';
        }
        var url = block && (block.url || block.src);
        if (!url) return '<div class="lesson-warning">видео не указано</div>';
        var embed = videoEmbedUrl(url);
        if (embed) {
            return '<div class="lesson-video"><iframe src="' + safeUrl(embed) + '"' + attrs + '></iframe></div>';
        }
        return '<video class="lesson-video-file" controls src="' + safeUrl(url) + '"></video>';
    }

    function renderText(value) {
        var text = escapeHtml(value || '');
        text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
        text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        text = text.replace(/\*([^*]+)\*/g, '<em>$1</em>');
        return text.replace(/\n/g, '<br>');
    }

    function renderLessonContent(blocks) {
        if (!Array.isArray(blocks) || !blocks.length) {
            return '<p class="lesson-text">нет контента</p>';
        }
        var html = '';
        blocks.forEach(function (block) {
            if (typeof block === 'string') {
                html += '<div class="lesson-text">' + escapeHtml(block) + '</div>';
                return;
            }
            if (!block) return;
            switch (block.type) {
                case 'text':
                    html += '<div class="lesson-text">' + renderText(block.value || '') + '</div>';
                    break;
                case 'formula':
                    html += '<div class="lesson-formula">\\[' + escapeHtml(block.value || '') + '\\]</div>';
                    break;
                case 'image':
                    html += renderImage(block);
                    break;
                case 'video':
                    html += renderVideo(block);
                    break;
                case 'list':
                    if (Array.isArray(block.items) && block.items.length) {
                        html += '<ul class="lesson-list">'
                            + block.items.map(function (i) { return '<li>' + escapeHtml(i) + '</li>'; }).join('')
                            + '</ul>';
                    }
                    break;
                case 'code':
                    html += '<pre class="lesson-code"><code>' + escapeHtml(block.value || '') + '</code></pre>';
                    break;
                case 'warning':
                    html += '<div class="lesson-warning">' + escapeHtml(block.value || '') + '</div>';
                    break;
                default:
                    html += '<div class="lesson-text">' + escapeHtml(JSON.stringify(block)) + '</div>';
            }
        });
        return html;
    }

    function mountEmbedScripts(root) {
        if (!root || !root.querySelectorAll) return;
        root.querySelectorAll('.lesson-video-embed[data-embed-script]').forEach(function (box) {
            if (box.dataset.mounted) return;
            box.dataset.mounted = '1';
            var s = document.createElement('script');
            s.src = box.dataset.embedScript;
            box.appendChild(s);
        });
        mountMath(root);
    }

    function mountMath(root) {
        if (!root.querySelector('.lesson-formula')) return;
        var typeset = function () {
            if (window.MathJax && window.MathJax.typesetPromise) window.MathJax.typesetPromise([root]);
        };
        if (window.MathJax && window.MathJax.typesetPromise) { typeset(); return; }
        if (window.__notalmsMathLoading) {
            document.addEventListener('notalms-math-ready', typeset, { once: true });
            return;
        }
        window.__notalmsMathLoading = true;
        window.MathJax = { tex: { inlineMath: [['\\(', '\\)']], displayMath: [['\\[', '\\]']] }, startup: { typeset: false } };
        var script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js';
        script.async = true;
        script.onload = function () { window.__notalmsMathLoading = false; typeset(); document.dispatchEvent(new Event('notalms-math-ready')); };
        script.onerror = function () { window.__notalmsMathLoading = false; };
        document.head.appendChild(script);
    }

    window.LessonBlocks = {
        escapeHtml: escapeHtml,
        safeUrl: safeUrl,
        renderImage: renderImage,
        renderVideo: renderVideo,
        renderText: renderText,
        videoEmbedUrl: videoEmbedUrl,
        renderLessonContent: renderLessonContent,
        mountEmbedScripts: mountEmbedScripts,
        mountMath: mountMath,
    };
    // короткие глобальные имена — страницы вызывают их как раньше
    window.escapeHtml = escapeHtml;
    window.safeUrl = safeUrl;
    window.renderVideo = renderVideo;
    window.renderLessonContent = renderLessonContent;
    window.mountEmbedScripts = mountEmbedScripts;
})();
