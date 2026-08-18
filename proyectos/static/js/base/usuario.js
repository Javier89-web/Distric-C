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


    function activarMenuAdministradorDeRutas() {
        const panel = document.querySelector(".admin-route-offcanvas");
        if (!panel) return;

        const ruta = window.location.pathname;
        const parametros = new URLSearchParams(window.location.search);
        const tipoReporte = (parametros.get("tipo") || "").toUpperCase();
        const enlaces = [
            ["routeAdminMenuInicio", ["/adminpanel/"]],
            ["routeAdminMenuUsuarios", ["/listadousuario/", "/nuevousuario/", "/editarusuario/"]],
            ["routeAdminMenuVehiculos", ["/listadocarros/", "/nuevocarro/", "/editarcarro/", "/vehiculos/"]],
            ["routeAdminMenuProductos", ["/productos-carga/"]],
            ["routeAdminMenuPlanCargas", ["/plan-cargas/"]],
            ["routeAdminMenuConsultaCargas", ["/consulta-cargas/"]],
            ["routeAdminMenuTramos", ["/administrador/rutas/tramos-generales/"]],
            ["routeAdminMenuPlanificacion", [
                "/administrador/rutas/planificacion/",
                "/buscarlugares/",
                "/lugar/",
                "/rutas/",
                "/recorrido/",
                "/tramos/",
                "/viajes/"
            ]]
        ];

        enlaces.forEach(function (grupo) {
            const enlace = document.getElementById(grupo[0]);
            if (enlace && grupo[1].some(function (prefijo) { return ruta.startsWith(prefijo); })) {
                enlace.classList.add("active");
            }
        });

        if (ruta.startsWith("/administrador/rutas/reportes/")) {
            const idReporte = tipoReporte === "GENERAL"
                ? "routeAdminMenuReportesGenerales"
                : "routeAdminMenuReportesTramos";
            const enlaceReporte = document.getElementById(idReporte);
            if (enlaceReporte) enlaceReporte.classList.add("active");
        }

        const grupos = Array.from(panel.querySelectorAll(".admin-route-menu-group"));

        function cambiarGrupo(grupo, abrir) {
            const boton = grupo.querySelector(".admin-route-menu-group-toggle");
            const submenu = grupo.querySelector(".admin-route-menu-subgroup");
            if (!boton || !submenu) return;
            grupo.classList.toggle("is-open", abrir);
            boton.setAttribute("aria-expanded", abrir ? "true" : "false");
            submenu.hidden = !abrir;
        }

        grupos.forEach(function (grupo) {
            const boton = grupo.querySelector(".admin-route-menu-group-toggle");
            if (!boton) return;
            boton.addEventListener("click", function () {
                const abrir = !grupo.classList.contains("is-open");
                grupos.forEach(function (otro) {
                    cambiarGrupo(otro, otro === grupo ? abrir : false);
                });
            });
        });

        const activo = grupos.find(function (grupo) {
            return Boolean(grupo.querySelector(".admin-route-menu-link.active"));
        });
        if (activo) cambiarGrupo(activo, true);
    }

    registrarServiceWorker();

    document.addEventListener("DOMContentLoaded", function () {
        registrarValidacionesComunes();
        mostrarMensajesDjango();
        activarNotificacionesDeEventos();
        activarMenuAdministradorDeRutas();
    });
})();
