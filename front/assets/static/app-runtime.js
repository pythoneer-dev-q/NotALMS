(function () {
    'use strict';

    var REQUEST_TIMEOUT_MS = 45000;
    var PAGE_LOAD_TIMEOUT_MS = 75000;
    var FAILURE_WINDOW_MS = 30000;
    var failureCount = 0;
    var lastFailureAt = 0;
    var nativeFetch = window.fetch.bind(window);

    function serviceError() {
        if (location.pathname !== '/error') {
            location.replace('/error');
        }
    }

    function recordFailure() {
        var now = Date.now();
        failureCount = now - lastFailureAt <= FAILURE_WINDOW_MS ? failureCount + 1 : 1;
        lastFailureAt = now;
        if (failureCount >= 3) serviceError();
    }

    function clearFailures() {
        failureCount = 0;
        lastFailureAt = 0;
    }

    function isPlatformRequest(input) {
        try {
            var raw = typeof input === 'string' ? input : input.url;
            return new URL(raw, location.href).hostname === location.hostname;
        } catch (_) {
            return false;
        }
    }

    function hasAuthorization(init) {
        var headers = init && init.headers;
        if (!headers) return false;
        if (typeof headers.get === 'function') return Boolean(headers.get('Authorization'));
        if (Array.isArray(headers)) {
            return headers.some(function (pair) { return String(pair[0]).toLowerCase() === 'authorization'; });
        }
        return Boolean(headers.Authorization || headers.authorization);
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
            if (isPlatformRequest(input) && response.status >= 500) recordFailure();
            else if (isPlatformRequest(input)) clearFailures();
            if (isPlatformRequest(input) && response.status === 401 && hasAuthorization(init)) {
                localStorage.removeItem('token');
                if (location.pathname !== '/' && location.pathname !== '/login') location.replace('/');
            }
            return response;
        }).catch(function (error) {
            if (isPlatformRequest(input) && (error instanceof TypeError || error?.name === 'AbortError')) {
                recordFailure();
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
        }
    });
})();
