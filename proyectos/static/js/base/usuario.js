(function () {
    "use strict";

    function mostrarMensajesDjango() {
        const contenedor = document.getElementById("django-messages");
        if (!contenedor || typeof window.iziToast === "undefined") {
            return;
        }

        contenedor.querySelectorAll("[data-message]").forEach(function (item) {
            const etiquetas = (item.dataset.tags || "").toLowerCase();
            const configuracion = {
                message: item.dataset.message || "",
                position: "topRight",
                timeout: 5000,
                close: true,
                progressBar: true,
                backgroundColor: "#ffffff",
                titleColor: "#111827",
                messageColor: "#374151"
            };

            if (etiquetas.includes("success")) {
                iziToast.success({
                    ...configuracion,
                    title: "CONFIRMACIÓN",
                    class: "toast-success-custom",
                    iconColor: "#23262b",
                    progressBarColor: "#d71920"
                });
            } else if (etiquetas.includes("error")) {
                iziToast.error({
                    ...configuracion,
                    title: "ERROR",
                    class: "toast-error-custom",
                    iconColor: "#ef4444",
                    progressBarColor: "#b91c1c"
                });
            } else if (etiquetas.includes("warning")) {
                iziToast.warning({
                    ...configuracion,
                    title: "ADVERTENCIA",
                    class: "toast-warning-custom",
                    iconColor: "#f59e0b",
                    progressBarColor: "#d97706"
                });
            } else {
                iziToast.info({
                    ...configuracion,
                    title: "INFORMACIÓN",
                    class: "toast-info-custom",
                    iconColor: "#2563eb",
                    progressBarColor: "#2563eb"
                });
            }
        });
    }

    function registrarValidacionesComunes() {
        if (!window.jQuery || !jQuery.validator) {
            return;
        }

        jQuery.validator.addMethod(
            "letras",
            function (value, element) {
                return this.optional(element) || /^[A-Za-zÁÉÍÓÚÑáéíóúñ ]*$/.test(value);
            },
            "Este campo solo acepta letras"
        );
    }

    function registrarServiceWorker() {
        const url = document.body.dataset.serviceWorkerUrl;
        if (!url || !("serviceWorker" in navigator)) {
            return;
        }

        window.addEventListener("load", function () {
            navigator.serviceWorker.register(url).catch(function (error) {
                console.log("Error al registrar el Service Worker:", error);
            });
        });
    }

    function activarNotificacionesDeEventos() {
        const url = document.body.dataset.eventToastUrl;
        if (!url || typeof window.iziToast === "undefined") {
            return;
        }

        const intervaloMs = 30000;
        let temporizador = null;

        function convertirFechaLocal(valor) {
            if (!valor || !valor.includes("T")) {
                return null;
            }
            const partes = valor.split("T");
            const fecha = partes[0].split("-").map(Number);
            const hora = partes[1].split(":").map(Number);
            return new Date(fecha[0], fecha[1] - 1, fecha[2], hora[0], hora[1], hora[2] || 0);
        }

        async function consultar() {
            try {
                const respuesta = await fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } });
                const datos = await respuesta.json();
                if (!datos.ok) {
                    return;
                }

                const fechaFin = convertirFechaLocal(datos.fin_iso);
                if (fechaFin && new Date() > fechaFin) {
                    if (temporizador) {
                        clearInterval(temporizador);
                        temporizador = null;
                    }
                    return;
                }

                iziToast.info({
                    title: "EVENTO ASIGNADO",
                    message:
                        "<div class='dc-toast-evento'>" +
                        "<div><b>Inicio:</b> " + datos.inicio + "</div>" +
                        "<div><b>Fin:</b> " + datos.fin + "</div>" +
                        "<div><b>Descripción:</b> " + datos.descripcion + "</div>" +
                        "</div>",
                    position: "topRight",
                    timeout: 12000,
                    close: true,
                    progressBar: true,
                    class: "toast-info-custom",
                    backgroundColor: "#ffffff",
                    titleColor: "#111827",
                    messageColor: "#374151",
                    iconColor: "#2563eb",
                    progressBarColor: "#d71920"
                });
            } catch (error) {
                console.log("No se pudieron consultar las notificaciones:", error);
            }
        }

        window.setTimeout(function () {
            consultar();
            temporizador = window.setInterval(consultar, intervaloMs);
        }, intervaloMs);
    }

    registrarServiceWorker();

    document.addEventListener("DOMContentLoaded", function () {
        registrarValidacionesComunes();
        mostrarMensajesDjango();
        activarNotificacionesDeEventos();
    });
})();
