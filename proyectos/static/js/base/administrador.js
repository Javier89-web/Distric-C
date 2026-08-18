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
                iziToast.success({ ...configuracion, title: "CONFIRMACIÓN", class: "toast-success-custom", iconColor: "#23262b", progressBarColor: "#d71920" });
            } else if (etiquetas.includes("error")) {
                iziToast.error({ ...configuracion, title: "ERROR", class: "toast-error-custom", iconColor: "#ef4444", progressBarColor: "#b91c1c" });
            } else if (etiquetas.includes("warning")) {
                iziToast.warning({ ...configuracion, title: "ADVERTENCIA", class: "toast-warning-custom", iconColor: "#f59e0b", progressBarColor: "#d97706" });
            } else {
                iziToast.info({ ...configuracion, title: "INFORMACIÓN", class: "toast-info-custom", iconColor: "#2563eb", progressBarColor: "#2563eb" });
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

    function activarMenuActual() {
        const rutaActual = window.location.pathname;
        const parametros = new URLSearchParams(window.location.search);
        const tipoReporte = (parametros.get("tipo") || "").toUpperCase();
        const grupos = [
            ["menuInicio", ["/adminpanel/"]],
            ["menuUsuarios", ["/listadousuario/", "/nuevousuario/", "/editarusuario/"]],
            ["menuVehiculos", ["/listadocarros/", "/nuevocarro/", "/editarcarro/", "/vehiculos/"]],
            ["menuCombustible", ["/combustible/precios/"]],
            ["menuProductosCarga", ["/productos-carga/"]],
            ["menuPlanCargas", ["/plan-cargas/"]],
            ["menuConsultaCargas", ["/consulta-cargas/"]],
            ["menuTramosGenerales", ["/administrador/rutas/tramos-generales/"]],
            ["menuPlanificacionRutas", ["/administrador/rutas/planificacion/"]]
        ];

        grupos.forEach(function (grupo) {
            const enlace = document.getElementById(grupo[0]);
            if (enlace && grupo[1].some(function (ruta) { return rutaActual.startsWith(ruta); })) {
                enlace.classList.add("active");
            }
        });

        if (rutaActual.startsWith("/administrador/rutas/reportes/")) {
            const idReporte = tipoReporte === "GENERAL" ? "menuReportesTramosGenerales" : "menuReportesRutas";
            const enlaceReporte = document.getElementById(idReporte);
            if (enlaceReporte) enlaceReporte.classList.add("active");
        }
    }

    function configurarGruposMenu() {
        const gruposMenu = Array.from(document.querySelectorAll(".admin-menu-group"));
        if (!gruposMenu.length) return;

        function cambiarGrupo(grupo, abrir) {
            const boton = grupo.querySelector(".admin-menu-group-toggle");
            const submenu = grupo.querySelector(".admin-menu-subgroup");
            if (!boton || !submenu) return;

            grupo.classList.toggle("is-open", abrir);
            boton.setAttribute("aria-expanded", abrir ? "true" : "false");
            submenu.hidden = !abrir;
        }

        gruposMenu.forEach(function (grupo) {
            const boton = grupo.querySelector(".admin-menu-group-toggle");
            if (!boton) return;

            boton.addEventListener("click", function () {
                const abrir = !grupo.classList.contains("is-open");
                gruposMenu.forEach(function (otroGrupo) {
                    cambiarGrupo(otroGrupo, otroGrupo === grupo ? abrir : false);
                });
            });
        });

        const grupoActivo = gruposMenu.find(function (grupo) {
            return Boolean(grupo.querySelector(".admin-menu-link.active"));
        });
        if (grupoActivo) {
            cambiarGrupo(grupoActivo, true);
        }
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

    function activarScrollTop() {
        const boton = document.getElementById("scroll-top");
        if (!boton) {
            return;
        }
        boton.addEventListener("click", function (evento) {
            evento.preventDefault();
            window.scrollTo({ top: 0, behavior: "smooth" });
        });
    }

    registrarServiceWorker();

    document.addEventListener("DOMContentLoaded", function () {
        registrarValidacionesComunes();
        mostrarMensajesDjango();
        activarMenuActual();
        configurarGruposMenu();
        activarScrollTop();
    });
})();
