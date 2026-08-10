(function () {
    "use strict";

    const config = document.getElementById("segmentSummaryConfig");

    function csrfToken() {
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : "";
    }

    function guardedConfirmation(form, options, loadingText) {
        form.addEventListener("submit", async function (event) {
            event.preventDefault();
            if (
                form.dataset.confirming === "1" ||
                window.DistricSubmitGuard?.isLocked(form)
            ) {
                return;
            }

            form.dataset.confirming = "1";
            const result = window.Swal
                ? await Swal.fire(options)
                : { isConfirmed: window.confirm(options.title || "¿Confirmar acción?") };

            if (result.isConfirmed) {
                window.DistricSubmitGuard.submit(
                    form,
                    loadingText,
                    event.submitter || null
                );
            } else {
                form.dataset.confirming = "0";
            }
        });
    }

    document.querySelectorAll(".next-route-form").forEach(function (form) {
        guardedConfirmation(form, {
            title: "¿Generar el siguiente tramo?",
            text: "El origen será el destino que acabas de completar y la predicción usará la carga restante.",
            icon: "question",
            showCancelButton: true,
            confirmButtonText: "Sí, continuar",
            cancelButtonText: "Cancelar",
            confirmButtonColor: "#23262b",
            cancelButtonColor: "#6b7280",
            reverseButtons: true
        }, "Preparando siguiente tramo…");
    });

    const finish = document.querySelector(".finish-trip-form");
    if (finish) {
        guardedConfirmation(finish, {
            title: "¿Finalizar el viaje completo?",
            text: "Se consolidarán todos los tramos y la carga quedará cerrada.",
            icon: "warning",
            showCancelButton: true,
            confirmButtonText: "Sí, finalizar viaje",
            cancelButtonText: "Continuar viaje",
            confirmButtonColor: "#d71920",
            cancelButtonColor: "#23262b",
            reverseButtons: true
        }, "Finalizando viaje…");
    }

    const testButton = document.getElementById("btnNuevaRutaPrueba");
    let testRequestActive = false;
    if (testButton && config) {
        testButton.addEventListener("click", async function () {
            if (testRequestActive) return;
            testRequestActive = true;
            testButton.disabled = true;

            const prompt = await Swal.fire({
                title: "Autorización administrativa",
                text: "Esta opción permite generar la siguiente ruta sin validar la llegada por GPS. Ingresa la contraseña administrativa para continuar.",
                input: "password",
                inputLabel: "Contraseña",
                inputPlaceholder: "Contraseña administrativa",
                showCancelButton: true,
                confirmButtonText: "Generar ruta",
                cancelButtonText: "Cancelar",
                confirmButtonColor: "#23262b",
                cancelButtonColor: "#6b7280",
                preConfirm: function (value) {
                    if (!value) {
                        Swal.showValidationMessage("Ingresa la contraseña.");
                        return false;
                    }
                    return value;
                }
            });

            if (!prompt.isConfirmed) {
                testRequestActive = false;
                testButton.disabled = false;
                return;
            }

            try {
                const response = await fetch(config.dataset.testUrl, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": csrfToken(),
                        "X-Requested-With": "XMLHttpRequest"
                    },
                    body: JSON.stringify({ clave: prompt.value })
                });
                const data = await response.json();
                if (!response.ok || !data.ok) {
                    throw new Error(data.mensaje || "No se pudo autorizar la generación sin GPS.");
                }

                if (
                    window.DistricTabLock &&
                    typeof window.DistricTabLock.navigate === "function"
                ) {
                    window.DistricTabLock.navigate(data.redirect);
                } else {
                    window.location.assign(data.redirect);
                }
            } catch (error) {
                testRequestActive = false;
                testButton.disabled = false;
                await Swal.fire({
                    title: "Acceso no autorizado",
                    text: error.message,
                    icon: "error",
                    confirmButtonColor: "#23262b"
                });
            }
        });
    }
})();
