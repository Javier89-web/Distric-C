(function () {
    "use strict";

    const LOCK_ATTRIBUTE = "data-distric-submitting";
    const DEFAULT_TEXT = "Procesando…";

    function submitControls(form) {
        return Array.from(
            form.querySelectorAll('button[type="submit"], input[type="submit"]')
        );
    }

    function originalState(control) {
        if (!control.dataset.districOriginalDisabled) {
            control.dataset.districOriginalDisabled = control.disabled ? "1" : "0";
        }
        if (control.tagName === "BUTTON" && !control.dataset.districOriginalHtml) {
            control.dataset.districOriginalHtml = control.innerHTML;
        }
        if (control.tagName === "INPUT" && !control.dataset.districOriginalValue) {
            control.dataset.districOriginalValue = control.value;
        }
    }

    function loadingText(form, submitter, explicitText) {
        return (
            explicitText ||
            (submitter && submitter.dataset.loadingText) ||
            form.dataset.loadingText ||
            DEFAULT_TEXT
        );
    }

    function lock(form, submitter, explicitText) {
        if (!(form instanceof HTMLFormElement)) {
            return false;
        }
        if (form.getAttribute(LOCK_ATTRIBUTE) === "1") {
            return false;
        }

        form.setAttribute(LOCK_ATTRIBUTE, "1");
        form.setAttribute("aria-busy", "true");

        const text = loadingText(form, submitter, explicitText);
        submitControls(form).forEach(function (control) {
            originalState(control);
            control.disabled = true;
            control.setAttribute("aria-disabled", "true");
            if (control === submitter || submitControls(form).length === 1) {
                if (control.tagName === "BUTTON") {
                    control.innerHTML = '<i class="bi bi-hourglass-split"></i> ' + text;
                } else {
                    control.value = text;
                }
            }
        });
        return true;
    }

    function unlock(form) {
        if (!(form instanceof HTMLFormElement)) {
            return;
        }

        form.removeAttribute(LOCK_ATTRIBUTE);
        form.removeAttribute("aria-busy");

        submitControls(form).forEach(function (control) {
            if (control.dataset.districOriginalDisabled === "1") {
                control.disabled = true;
            } else {
                control.disabled = false;
            }
            control.removeAttribute("aria-disabled");

            if (control.tagName === "BUTTON" && control.dataset.districOriginalHtml) {
                control.innerHTML = control.dataset.districOriginalHtml;
            }
            if (control.tagName === "INPUT" && control.dataset.districOriginalValue) {
                control.value = control.dataset.districOriginalValue;
            }
        });
    }

    function submit(form, explicitText, submitter) {
        if (!lock(form, submitter || null, explicitText)) {
            return false;
        }

        if (
            window.DistricTabLock &&
            typeof window.DistricTabLock.prepareNavigation === "function"
        ) {
            window.DistricTabLock.prepareNavigation(form.action || window.location.href);
        }

        HTMLFormElement.prototype.submit.call(form);
        return true;
    }

    document.addEventListener("submit", function (event) {
        const form = event.target;
        if (!(form instanceof HTMLFormElement) || form.target === "_blank") {
            return;
        }

        if (event.defaultPrevented) {
            return;
        }

        if (form.getAttribute(LOCK_ATTRIBUTE) === "1") {
            event.preventDefault();
            event.stopImmediatePropagation();
            return;
        }

        lock(form, event.submitter || null);
    });

    window.DistricSubmitGuard = Object.freeze({
        isLocked: function (form) {
            return Boolean(form && form.getAttribute(LOCK_ATTRIBUTE) === "1");
        },
        lock: lock,
        unlock: unlock,
        submit: submit
    });
})();
