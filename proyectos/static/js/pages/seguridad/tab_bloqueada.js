document.addEventListener("DOMContentLoaded", function () {
    "use strict";
    const LOCK_KEY = "DISTRICC_ACTIVE_TAB_LOCK_V5";
    const TAB_KEY = "DISTRICC_CURRENT_TAB_ID";
    const HANDOFF_KEY = "DISTRICC_TAB_NAVIGATION_HANDOFF_V5";
    const BLOCKED_DESTINATION_KEY = "DISTRICC_BLOCKED_DESTINATION";
    const EXPIRES_MS = 9000;
    const notice = document.getElementById("tabLockNotice");
    const retryButton = document.getElementById("btnRetryTab");
    const useButton = document.getElementById("btnUseThisTab");

    function createId() {
        return window.crypto?.randomUUID ? window.crypto.randomUUID() : Date.now().toString(36) + "-" + Math.random().toString(36).slice(2);
    }
    let tabId = sessionStorage.getItem(TAB_KEY);
    if (!tabId) { tabId = createId(); sessionStorage.setItem(TAB_KEY, tabId); }

    function safeNextUrl() {
        const raw = document.body.dataset.nextUrl || sessionStorage.getItem(BLOCKED_DESTINATION_KEY) || "/";
        try {
            const parsed = new URL(raw, window.location.origin);
            if (parsed.origin !== window.location.origin || parsed.pathname.startsWith("/tab-bloqueada/")) return "/";
            return parsed.pathname + parsed.search + parsed.hash;
        } catch (_) { return "/"; }
    }
    function readLock() { try { return JSON.parse(localStorage.getItem(LOCK_KEY) || "null"); } catch (_) { return null; } }
    function active(lock) { return Boolean(lock?.tabId && lock?.instanceId && Date.now() - Number(lock.updatedAt || 0) < EXPIRES_MS); }
    function show(message, ready) { if (notice) { notice.textContent = message; notice.classList.toggle("is-ready", Boolean(ready)); } }
    function enterApplication() {
        const destination = safeNextUrl();
        const instanceId = createId();
        sessionStorage.setItem(HANDOFF_KEY, JSON.stringify({tabId, fromInstanceId:instanceId, destination, createdAt:Date.now()}));
        localStorage.setItem(LOCK_KEY, JSON.stringify({tabId, instanceId, updatedAt:Date.now(), url:destination, navigatingTo:destination}));
        sessionStorage.removeItem(BLOCKED_DESTINATION_KEY);
        window.location.replace(destination);
    }

    retryButton?.addEventListener("click", function () {
        const lock = readLock();
        if (!active(lock) || lock.tabId === tabId) { enterApplication(); return; }
        show("La otra pestaña sigue activa. Si deseas continuar aquí, usa esta pestaña.", false);
    });
    useButton?.addEventListener("click", function () { show("Abriendo la aplicación en esta pestaña…", true); enterApplication(); });
    window.setInterval(function () {
        if (!active(readLock())) show("La otra pestaña ya no está activa. Puedes volver a intentar.", true);
    }, 1800);
});
