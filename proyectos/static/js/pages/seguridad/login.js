(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", function () {
        const swUrl = document.body && document.body.dataset.serviceWorkerUrl;
        if ("serviceWorker" in navigator && swUrl) {
            navigator.serviceWorker.register(swUrl).catch(function () {
                // La aplicación puede seguir funcionando en navegador aunque falle el registro PWA.
            });
        }

        const formulario = document.getElementById("loginForm");
        const correo = document.getElementById("usuario");
        const contrasena = document.getElementById("contrasena");
        const mostrar = document.getElementById("chkMostrar");
        const errorCorreo = document.getElementById("errorUsuario");
        const errorContrasena = document.getElementById("errorContrasena");

        if (!formulario || !correo || !contrasena) {
            return;
        }

        function establecerError(campo, contenedor, mensaje) {
            campo.classList.toggle("is-invalid", Boolean(mensaje));
            contenedor.textContent = mensaje || "";
            campo.setAttribute("aria-invalid", mensaje ? "true" : "false");
        }

        function validarCorreo() {
            const valor = correo.value.trim();
            if (!valor) {
                establecerError(correo, errorCorreo, "Ingresa tu correo electrónico.");
                return false;
            }

            const patron = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
            if (!patron.test(valor)) {
                establecerError(correo, errorCorreo, "Ingresa un correo electrónico válido.");
                return false;
            }

            establecerError(correo, errorCorreo, "");
            return true;
        }

        function validarContrasena() {
            const valor = contrasena.value;
            if (!valor) {
                establecerError(contrasena, errorContrasena, "Ingresa tu contraseña.");
                return false;
            }

            if (valor.length < 6 || valor.length > 12) {
                establecerError(contrasena, errorContrasena, "La contraseña debe tener entre 6 y 12 caracteres.");
                return false;
            }

            establecerError(contrasena, errorContrasena, "");
            return true;
        }

        correo.addEventListener("blur", validarCorreo);
        correo.addEventListener("input", function () {
            if (correo.classList.contains("is-invalid")) {
                validarCorreo();
            }
        });

        contrasena.addEventListener("blur", validarContrasena);
        contrasena.addEventListener("input", function () {
            if (contrasena.classList.contains("is-invalid")) {
                validarContrasena();
            }
        });

        if (mostrar) {
            mostrar.addEventListener("change", function () {
                contrasena.type = mostrar.checked ? "text" : "password";
            });
        }

        formulario.addEventListener("submit", function (evento) {
            const correoValido = validarCorreo();
            const contrasenaValida = validarContrasena();

            if (!correoValido || !contrasenaValida) {
                evento.preventDefault();
                const primerError = formulario.querySelector(".is-invalid");
                if (primerError) {
                    primerError.focus();
                }
            }
        });
    });
})();
