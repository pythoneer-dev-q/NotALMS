(function () {
    'use strict';

    var REQUEST_TIMEOUT_MS = 15000;
    var PAGE_LOAD_TIMEOUT_MS = 20000;
    var nativeFetch = window.fetch.bind(window);

    function serviceError() {
        if (location.pathname !== '/error') {
            location.replace('/error');
        }
    }

    function isPlatformRequest(input) {
        try {
            var raw = typeof input === 'string' ? input : input.url;
            return new URL(raw, location.href).hostname === location.hostname;
        } catch (_) {
            return false;
        }
    }

    window.fetch = function (input, init) {
        init = init ? Object.assign({}, init) : {};
        var controller = new AbortController();
        var callerSignal = init.signal;
        var timer = setTimeout(function () { controller.abort(); }, REQUEST_TIMEOUT_MS);

        if (callerSignal) {
            if (callerSignal.aborted) controller.abort();
            else callerSignal.addEventListener('abort', function () { controller.abort(); }, { once: true });
        }
        init.signal = controller.signal;

        return nativeFetch(input, init).then(function (response) {
            if (isPlatformRequest(input) && response.status >= 500) serviceError();
            return response;
        }).catch(function (error) {
            if (isPlatformRequest(input) && (error instanceof TypeError || error?.name === 'AbortError')) {
                serviceError();
            }
            throw error;
        }).finally(function () { clearTimeout(timer); });
    };

    function hasBlockingLoader() {
        return Boolean(
            document.querySelector('#page-loader.visible') ||
            document.querySelector('#global-loader:not(.hidden)') ||
            document.querySelector('.loading-screen.visible')
        );
    }

    window.addEventListener('DOMContentLoaded', function () {
        setTimeout(function () {
            if (hasBlockingLoader()) serviceError();
        }, PAGE_LOAD_TIMEOUT_MS);
    });

    window.addEventListener('unhandledrejection', function (event) {
        var reason = event.reason;
        if (hasBlockingLoader() && (reason instanceof TypeError || reason?.name === 'AbortError')) {
            event.preventDefault();
            serviceError();
        }
    });
})();
