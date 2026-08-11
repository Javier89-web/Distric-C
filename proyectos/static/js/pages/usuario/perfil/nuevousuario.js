$(document).ready(function () {

        $.validator.addMethod(
            "soloLetras",

            function (value, element) {
                return this.optional(element) ||
                    /^[A-Za-zÁÉÍÓÚÑáéíóúñÜü\s'-]+$/.test(value);
            },

            "Este campo solo permite letras"
        );

        $.validator.addMethod(
            "cedulaEcuador",
            function (value, element) {
                if (this.optional(element)) {
                    return true;
                }

                if (!/^\d{10}$/.test(value)) {
                    return false;
                }

                const provincia = parseInt(value.substring(0, 2), 10);
                const tercerDigito = parseInt(value.charAt(2), 10);

                if (provincia < 1 || provincia > 24 || tercerDigito >= 6) {
                    return false;
                }

                const coeficientes = [2, 1, 2, 1, 2, 1, 2, 1, 2];
                let total = 0;

                for (let indice = 0; indice < 9; indice++) {
                    let resultado = parseInt(value.charAt(indice), 10) * coeficientes[indice];
                    total += resultado >= 10 ? resultado - 9 : resultado;
                }

                const verificador = (10 - (total % 10)) % 10;
                return verificador === parseInt(value.charAt(9), 10);
            },
            "Ingrese una cédula ecuatoriana válida"
        );

        $.validator.addMethod(
            "tamanioArchivo",

            function (value, element, maximo) {
                if (
                    !element.files ||
                    element.files.length === 0
                ) {
                    return true;
                }

                return element.files[0].size <= maximo;
            },

            "La imagen supera el tamaño permitido"
        );

        $.validator.addMethod(
            "codigoAdmin",
            function (value, element) {
                return this.optional(element) || /^[A-Za-z0-9_-]+$/.test(value);
            },
            "Solo se permiten letras, números, guion y guion bajo"
        );

        $.validator.addMethod(
            "telefonoAdmin",
            function (value, element) {
                return this.optional(element) || /^\+?\d{7,20}$/.test(value);
            },
            "Ingrese un teléfono válido"
        );

        const esAdministrador = function () {
            return $("#tipo_rol").val() === "ADMINISTRADOR";
        };

        const validarCodigoAdminUrl = $("#admin_codigo_interno").data("validar-codigo-url");

        function actualizarCamposAdministrador() {
            const admin = esAdministrador();
            const contenedor = $("#camposAdministrador");
            const cargo = $("#admin_cargo");
            const codigo = $("#admin_codigo_interno");
            const telefono = $("#admin_telefono_institucional");

            contenedor.prop("hidden", !admin);
            $("#clave_superusuario").val("");

            // El cargo es fijo para todas las cuentas administrativas.
            cargo.val("Administrador General").removeClass("error valid");
            cargo.next("label.error").remove();

            // Al volver a Usuario se limpian solo los datos editables de administrador.
            if (!admin) {
                codigo.val("").removeClass("error valid");
                telefono.val("").removeClass("error valid");
                codigo.next("label.error").remove();
                telefono.next("label.error").remove();
            } else {
                // Mostrar los campos sin disparar mensajes rojos antes de guardar.
                codigo.removeClass("error valid");
                telefono.removeClass("error valid");
                codigo.next("label.error").remove();
                telefono.next("label.error").remove();
            }

            $("#btnGuardar").html(
                admin
                    ? '<i class="bi bi-check-circle"></i> Guardar administrador'
                    : '<i class="bi bi-check-circle"></i> Guardar usuario'
            );
        }

        $("#foto_usuario").fileinput({
            language: "es",

            allowedFileExtensions: [
                "png",
                "jpg",
                "jpeg"
            ],

            showCaption: false,
            showUpload: false,
            showClose: false,
            showRemove: true,
            dropZoneEnabled: true,

            browseLabel: "Seleccionar imagen",
            removeLabel: "Quitar",

            dropZoneTitle:
                "Arrastra una imagen del usuario aquí o selecciónala desde tu equipo",

            maxFileSize: 5120,

            fileActionSettings: {
                showUpload: false,
                showRemove: true,
                showZoom: true,
                showDrag: false
            }
        });

        const validador = $("#frm_crear_usuario").validate({

            ignore: [],

            rules: {
                txt_cedula: {
                    required: true,
                    digits: true,
                    minlength: 10,
                    maxlength: 10,
                    cedulaEcuador: true
                },

                txt_telefono: {
                    required: true,
                    digits: true,
                    minlength: 7,
                    maxlength: 15
                },

                txt_nombre: {
                    required: true,
                    soloLetras: true,
                    minlength: 2,
                    maxlength: 50
                },

                txt_apellido: {
                    required: true,
                    soloLetras: true,
                    minlength: 2,
                    maxlength: 50
                },

                txt_correo: {
                    required: true,
                    email: true,
                    maxlength: 100
                },

                txt_contrasena: {
                    required: true,
                    minlength: 6,
                    maxlength: 12
                },

                tipo_rol: {
                    required: true
                },

                admin_codigo_interno: {
                    required: esAdministrador,
                    minlength: 3,
                    maxlength: 50,
                    codigoAdmin: true,
                    remote: {
                        url: validarCodigoAdminUrl,
                        type: "get",
                        data: {
                            codigo: function () {
                                return $("#admin_codigo_interno").val().trim().toUpperCase();
                            }
                        }
                    }
                },

                admin_telefono_institucional: {
                    required: esAdministrador,
                    telefonoAdmin: true
                },

                foto_usuario: {
                    extension: "png|jpg|jpeg",
                    tamanioArchivo: 5242880
                }
            },

            messages: {
                txt_cedula: {
                    required: "La cédula es obligatoria",
                    digits: "La cédula solo puede contener números",
                    minlength: "La cédula debe tener 10 dígitos",
                    maxlength: "La cédula debe tener 10 dígitos",
                    cedulaEcuador: "Ingrese una cédula ecuatoriana válida"
                },

                txt_telefono: {
                    required: "El teléfono es obligatorio",
                    digits: "El teléfono solo puede contener números",
                    minlength: "Ingrese al menos 7 dígitos",
                    maxlength: "Máximo 15 dígitos"
                },

                txt_nombre: {
                    required: "Los nombres son obligatorios",
                    soloLetras: "Los nombres solo pueden contener letras",
                    minlength: "Ingrese al menos 2 caracteres",
                    maxlength: "Máximo 50 caracteres"
                },

                txt_apellido: {
                    required: "Los apellidos son obligatorios",
                    soloLetras: "Los apellidos solo pueden contener letras",
                    minlength: "Ingrese al menos 2 caracteres",
                    maxlength: "Máximo 50 caracteres"
                },

                txt_correo: {
                    required: "El correo electrónico es obligatorio",
                    email: "Ingrese un correo electrónico válido",
                    maxlength: "Máximo 100 caracteres"
                },

                txt_contrasena: {
                    required: "La contraseña es obligatoria",
                    minlength: "La contraseña debe tener al menos 6 caracteres",
                    maxlength: "Máximo 12 caracteres"
                },

                tipo_rol: {
                    required: "Seleccione el tipo de cuenta"
                },

                admin_codigo_interno: {
                    required: "El código interno es obligatorio",
                    minlength: "Ingrese al menos 3 caracteres",
                    maxlength: "Máximo 50 caracteres",
                    codigoAdmin: "Use solo letras, números, guion o guion bajo",
                    remote: "Este código interno ya está asignado a otro administrador"
                },

                admin_telefono_institucional: {
                    required: "El teléfono es obligatorio",
                    telefonoAdmin: "Ingrese entre 7 y 20 dígitos"
                },

                foto_usuario: {
                    extension: "Solo se permiten imágenes PNG, JPG o JPEG",
                    tamanioArchivo: "La imagen no puede superar los 5 MB"
                }
            },

            errorPlacement: function (error, element) {
                if (element.attr("name") === "foto_usuario") {
                    $("#errorFoto")
                        .empty()
                        .append(error);
                } else {
                    error.insertAfter(element);
                }
            },

            highlight: function (element) {
                $(element)
                    .removeClass("valid")
                    .addClass("error");
            },

            unhighlight: function (element) {
                $(element)
                    .removeClass("error")
                    .addClass("valid");
            },

            submitHandler: function (form) {
                const enviarFormulario = function () {
                    $("#btnGuardar")
                        .prop("disabled", true)
                        .html(
                            '<span class="spinner-border spinner-border-sm"></span> ' +
                            "Guardando..."
                        );

                    // Envío nativo: evita volver a disparar jQuery Validate.
                    HTMLFormElement.prototype.submit.call(form);
                };

                if (!esAdministrador()) {
                    $("#clave_superusuario").val("");
                    enviarFormulario();
                    return false;
                }

                const validarClave = async function (clave) {
                    const url = form.dataset.validarSuperusuarioUrl;
                    const csrf = form.querySelector('[name="csrfmiddlewaretoken"]').value;
                    const cuerpo = new URLSearchParams();
                    cuerpo.append("clave", clave);

                    const response = await fetch(url, {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                            "X-CSRFToken": csrf,
                            "Accept": "application/json"
                        },
                        body: cuerpo.toString(),
                        credentials: "same-origin"
                    });

                    let data = {};
                    try {
                        data = await response.json();
                    } catch (error) {
                        data = {};
                    }

                    if (!response.ok || !data.ok) {
                        throw new Error(
                            data.mensaje ||
                            "No se pudo validar la contraseña de superusuario."
                        );
                    }

                    return clave;
                };

                if (window.Swal) {
                    Swal.fire({
                        title: "Autorización para crear administrador",
                        text: "Ingresa la contraseña de superusuario para confirmar la creación de esta cuenta administrativa.",
                        input: "password",
                        inputLabel: "Contraseña de superusuario",
                        inputPlaceholder: "Ingresa la contraseña",
                        showCancelButton: true,
                        confirmButtonText: "Autorizar y guardar",
                        cancelButtonText: "Cancelar",
                        confirmButtonColor: "#d71920",
                        cancelButtonColor: "#23262b",
                        reverseButtons: true,
                        allowOutsideClick: false,
                        showLoaderOnConfirm: true,
                        preConfirm: async function (value) {
                            if (!value) {
                                Swal.showValidationMessage(
                                    "Ingresa la contraseña de superusuario."
                                );
                                return false;
                            }

                            try {
                                return await validarClave(value);
                            } catch (error) {
                                Swal.showValidationMessage(error.message);
                                return false;
                            }
                        }
                    }).then(function (resultado) {
                        if (!resultado.isConfirmed || !resultado.value) {
                            return;
                        }

                        $("#clave_superusuario").val(resultado.value);
                        enviarFormulario();
                    });
                } else {
                    const clave = window.prompt("Contraseña de superusuario:");
                    if (!clave) {
                        return false;
                    }

                    validarClave(clave)
                        .then(function () {
                            $("#clave_superusuario").val(clave);
                            enviarFormulario();
                        })
                        .catch(function (error) {
                            window.alert(error.message);
                        });
                }

                // Impide el envío inicial mientras se solicita y valida la clave.
                return false;
            }
        });


        $("#tipo_rol").on("change", function () {
            actualizarCamposAdministrador();
        });

        actualizarCamposAdministrador();

        let consultaCedulaTimer = null;
        let ultimaCedulaConsultada = "";

        function mostrarEstadoCedula(mensaje, clase) {
            $("#estadoConsultaCedula")
                .removeClass("is-loading is-success is-warning is-error")
                .addClass(clase || "")
                .text(mensaje || "");
        }

        function consultarCedulaSiCorresponde() {
            const campo = $("#txt_cedula");
            const cedula = campo.val().trim();

            if (!/^\d{10}$/.test(cedula) || !campo.valid()) {
                ultimaCedulaConsultada = "";
                mostrarEstadoCedula("");
                return;
            }

            if (cedula === ultimaCedulaConsultada) {
                return;
            }

            ultimaCedulaConsultada = cedula;
            const patron = campo.data("lookup-url");
            const url = String(patron || "").replace("0000000000", cedula);
            if (!url) return;

            mostrarEstadoCedula("Consultando datos disponibles...", "is-loading");

            fetch(url, { headers: { "Accept": "application/json" } })
                .then(function (response) {
                    return response.json().then(function (data) {
                        return { status: response.status, data: data };
                    });
                })
                .then(function (resultado) {
                    const data = resultado.data || {};
                    if (data.ok && data.existente) {
                        mostrarEstadoCedula("Cédula existente.", "is-warning");
                        return;
                    }

                    if (data.ok && data.nombres && data.apellidos) {
                        $("#txt_nombre").val(data.nombres).valid();
                        $("#txt_apellido").val(data.apellidos).valid();
                        mostrarEstadoCedula("Cédula válida.", "is-success");
                        return;
                    }

                    mostrarEstadoCedula(
                        data.valida ? "Cédula válida." : (data.mensaje || "Cédula no válida."),
                        data.valida ? "is-success" : "is-error"
                    );
                })
                .catch(function () {
                    mostrarEstadoCedula(
                        "Cédula válida.",
                        "is-success"
                    );
                });
        }

        $("#txt_cedula").on("input blur", function () {
            clearTimeout(consultaCedulaTimer);
            consultaCedulaTimer = setTimeout(consultarCedulaSiCorresponde, 450);
        });

        $("#foto_usuario").on("change", function () {
            $(this).valid();
        });

        $("#btnLimpiar").on("click", function () {
            setTimeout(function () {

                validador.resetForm();

                $("#frm_crear_usuario")
                    .find(".form-control")
                    .removeClass("error valid");

                $("#errorFoto").empty();
                ultimaCedulaConsultada = "";
                mostrarEstadoCedula("");
                $("#tipo_rol").val("USUARIO");
                actualizarCamposAdministrador();

                try {
                    $("#foto_usuario").fileinput("clear");
                } catch (error) {
                    console.log(error);
                }

            }, 0);
        });

    });
