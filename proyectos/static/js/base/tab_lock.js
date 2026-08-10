(function () {
    "use strict";

    /*
     * Control global de una sola pestaña.
     *
     * La versión anterior podía interpretar una navegación lenta como si fuera
     * una pestaña diferente. Eso ocurría especialmente en "Guardar y calcular",
     * porque Django tarda algunos segundos en consultar APIs y generar las rutas.
     *
     * Esta versión conserva el control durante toda la navegación y entrega la
     * propiedad a la página siguiente de la MISMA pestaña.
     */
    const LOCK_KEY = "DISTRICC_ACTIVE_TAB_LOCK_V4";
    const TAB_KEY = "DISTRICC_CURRENT_TAB_ID";
    const HANDOFF_KEY = "DISTRICC_TAB_NAVIGATION_HANDOFF_V4";
    const BLOCKED_DESTINATION_KEY = "DISTRICC_BLOCKED_DESTINATION";

    const HEARTBEAT_MS = 1800;
    const EXPIRES_MS = 9000;
    const HANDOFF_MS = 600000;
    const WILDCARD_HANDOFF_MS = 180000;

    const currentPath = window.location.pathname;

    if (
        currentPath.startsWith("/tab-bloqueada/") ||
        currentPath.startsWith("/offline/") ||
        currentPath.startsWith("/service-worker") ||
        currentPath.startsWith("/manifest")
    ) {
        return;
    }

    function createId() {
        if (window.crypto && typeof window.crypto.randomUUID === "function") {
            return window.crypto.randomUUID();
        }
        return Date.now().toString(36) + "-" + Math.random().toString(36).slice(2);
    }

    function now() {
        return Date.now();
    }

    function readJson(storage, key) {
        try {
            return JSON.parse(storage.getItem(key) || "null");
        } catch (error) {
            return null;
        }
    }

    function currentUrl() {
        return window.location.pathname + window.location.search + window.location.hash;
    }

    function normalizeDestination(value) {
        try {
            const parsed = new URL(value || currentUrl(), window.location.origin);
            if (parsed.origin !== window.location.origin) {
                return null;
            }
            return parsed.pathname + parsed.search + parsed.hash;
        } catch (error) {
            return null;
        }
    }

    let tabId = sessionStorage.getItem(TAB_KEY);
    if (!tabId) {
        tabId = createId();
        sessionStorage.setItem(TAB_KEY, tabId);
    }

    const instanceId = createId();
    let redirecting = false;
    let leavingPage = false;
    let heartbeat = null;

    function readLock() {
        return readJson(localStorage, LOCK_KEY);
    }

    function isActive(lock) {
        return Boolean(
            lock &&
            lock.tabId &&
            lock.instanceId &&
            now() - Number(lock.updatedAt || 0) < EXPIRES_MS
        );
    }

    function claimLock(extra) {
        const data = Object.assign({
            tabId: tabId,
            instanceId: instanceId,
            updatedAt: now(),
            url: currentUrl(),
            navigatingTo: null
        }, extra || {});

        localStorage.setItem(LOCK_KEY, JSON.stringify(data));
    }

    function prepareNavigation(destination) {
        const normalized = normalizeDestination(destination) || currentUrl();
        const handoff = {
            tabId: tabId,
            fromInstanceId: instanceId,
            destination: normalized,
            createdAt: now()
        };

        sessionStorage.setItem(HANDOFF_KEY, JSON.stringify(handoff));

        const lock = readLock();
        if (lock && lock.tabId === tabId && lock.instanceId === instanceId) {
            claimLock({ navigatingTo: normalized });
        }

        return normalized;
    }

    function consumeNavigationHandoff() {
        const handoff = readJson(sessionStorage, HANDOFF_KEY);

        if (!handoff) {
            return null;
        }

        const age = now() - Number(handoff.createdAt || 0);
        const wildcard = handoff.destination === "*";
        const destination = wildcard ? null : normalizeDestination(handoff.destination);
        const destinationMatches = wildcard || destination === currentUrl();
        const maximumAge = wildcard ? WILDCARD_HANDOFF_MS : HANDOFF_MS;
        const valid = Boolean(
            handoff.tabId === tabId &&
            age >= 0 &&
            age < maximumAge &&
            destinationMatches
        );

        if (valid || age >= maximumAge || age < 0) {
            sessionStorage.removeItem(HANDOFF_KEY);
        }

        return valid ? handoff : null;
    }

    const navigationHandoff = consumeNavigationHandoff();
    const navigationEntry = (performance.getEntriesByType("navigation") || [])[0];
    const isBackForwardNavigation = Boolean(
        navigationEntry && navigationEntry.type === "back_forward"
    );

    function goToBlockedPage() {
        if (redirecting || leavingPage) {
            return;
        }

        redirecting = true;
        const destination = currentUrl();
        sessionStorage.setItem(BLOCKED_DESTINATION_KEY, destination);
        window.location.replace(
            "/tab-bloqueada/?next=" + encodeURIComponent(destination)
        );
    }

    function verifyOwnership(initialCheck) {
        const lock = readLock();
        const sameInstance = Boolean(
            lock &&
            lock.tabId === tabId &&
            lock.instanceId === instanceId
        );

        const validSameTabNavigation = Boolean(
            initialCheck &&
            navigationHandoff &&
            lock &&
            lock.tabId === tabId &&
            (
                lock.instanceId === navigationHandoff.fromInstanceId ||
                lock.navigatingTo === currentUrl()
            )
        );

        const validBrowserHistoryNavigation = Boolean(
            initialCheck &&
            isBackForwardNavigation &&
            lock &&
            lock.tabId === tabId
        );

        if (!isActive(lock) || sameInstance || validSameTabNavigation || validBrowserHistoryNavigation) {
            claimLock();
            document.documentElement.style.visibility = "visible";
            return true;
        }

        goToBlockedPage();
        return false;
    }

    function sameOriginLink(anchor) {
        if (!anchor || anchor.target === "_blank" || anchor.hasAttribute("download")) {
            return null;
        }

        const href = anchor.getAttribute("href");
        if (!href || href.startsWith("#") || href.startsWith("javascript:")) {
            return null;
        }

        return normalizeDestination(anchor.href);
    }

    function navigate(destination, replace) {
        if (leavingPage) {
            return false;
        }

        const normalized = prepareNavigation(destination);
        leavingPage = true;
        if (heartbeat) {
            window.clearInterval(heartbeat);
        }

        if (replace) {
            window.location.replace(normalized);
        } else {
            window.location.assign(normalized);
        }
        return true;
    }

    window.DistricTabLock = Object.freeze({
        prepareNavigation: prepareNavigation,
        navigate: navigate,
        tabId: tabId
    });

    document.documentElement.style.visibility = "hidden";

    if (!verifyOwnership(true)) {
        return;
    }

    heartbeat = window.setInterval(function () {
        if (leavingPage) {
            return;
        }
        if (!verifyOwnership(false)) {
            window.clearInterval(heartbeat);
        }
    }, HEARTBEAT_MS);

    /*
     * Registra la entrega antes de una navegación normal por enlaces o formularios.
     * Esto protege tanto al módulo de usuario como al módulo administrativo.
     */
    document.addEventListener("click", function (event) {
        if (
            event.defaultPrevented ||
            event.button !== 0 ||
            event.ctrlKey ||
            event.metaKey ||
            event.shiftKey ||
            event.altKey
        ) {
            return;
        }

        const anchor = event.target.closest("a");
        const destination = sameOriginLink(anchor);
        if (destination) {
            prepareNavigation(destination);
        }
    });

    document.addEventListener("submit", function (event) {
        const form = event.target;
        if (
            event.defaultPrevented ||
            !(form instanceof HTMLFormElement) ||
            form.target === "_blank"
        ) {
            return;
        }

        const destination = normalizeDestination(form.action || currentUrl());
        if (destination) {
            prepareNavigation(destination);
        }
    });

    window.addEventListener("storage", function (event) {
        if (event.key !== LOCK_KEY || leavingPage) {
            return;
        }

        const lock = readLock();
        if (
            isActive(lock) &&
            (lock.tabId !== tabId || lock.instanceId !== instanceId)
        ) {
            goToBlockedPage();
        }
    });

    document.addEventListener("visibilitychange", function () {
        if (!document.hidden && !leavingPage) {
            verifyOwnership(false);
        }
    });

    window.addEventListener("pageshow", function (event) {
        if (event.persisted) {
            leavingPage = false;
            const lock = readLock();
            // Volver con el botón Atrás restaura una página de esta misma pestaña
            // desde bfcache. En ese caso el instanceId cambia entre páginas, pero
            // el tabId sigue siendo el mismo y debe recuperar el control.
            if (!isActive(lock) || (lock && lock.tabId === tabId)) {
                claimLock();
                document.documentElement.style.visibility = "visible";
                if (heartbeat) window.clearInterval(heartbeat);
                heartbeat = window.setInterval(function () {
                    if (!leavingPage && !verifyOwnership(false)) {
                        window.clearInterval(heartbeat);
                    }
                }, HEARTBEAT_MS);
                return;
            }
            verifyOwnership(false);
        }
    });

    function handoffCurrentNavigation() {
        if (!leavingPage) {
            sessionStorage.setItem(HANDOFF_KEY, JSON.stringify({
                tabId: tabId,
                fromInstanceId: instanceId,
                destination: "*",
                createdAt: now()
            }));

            const lock = readLock();
            if (lock && lock.tabId === tabId && lock.instanceId === instanceId) {
                claimLock({ navigatingTo: "*" });
            }
        }
        leavingPage = true;
        if (heartbeat) {
            window.clearInterval(heartbeat);
        }
    }

    window.addEventListener("pagehide", handoffCurrentNavigation);
    window.addEventListener("beforeunload", handoffCurrentNavigation);
})();
