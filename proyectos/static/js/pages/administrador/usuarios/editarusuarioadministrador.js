$(document).ready(function () {

        const formulario = $("#frm_editar_usuario_admin");
        const fotoUsuario = $("#foto_usuario");

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
            "Ingrese un teléfono institucional válido"
        );

        fotoUsuario.fileinput({
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

            maxFileSize: 5120,

            dropZoneTitle:
                "Arrastra una imagen aquí o selecciónala desde tu equipo",

            fileActionSettings: {
                showUpload: false,
                showRemove: true,
                showZoom: true,
                showDrag: false
            }
        });

        const validador = formulario.validate({

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
                    minlength: 6,
                    maxlength: 12
                },

                admin_cargo: {
                    required: true,
                    minlength: 2,
                    maxlength: 100
                },

                admin_codigo_interno: {
                    required: true,
                    minlength: 3,
                    maxlength: 50,
                    codigoAdmin: true
                },

                admin_telefono_institucional: {
                    required: true,
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
                    minlength: "La contraseña debe tener al menos 6 caracteres",
                    maxlength: "Máximo 12 caracteres"
                },

                admin_cargo: {
                    required: "El cargo es obligatorio",
                    minlength: "Ingrese al menos 2 caracteres",
                    maxlength: "Máximo 100 caracteres"
                },

                admin_codigo_interno: {
                    required: "El código interno es obligatorio",
                    minlength: "Ingrese al menos 3 caracteres",
                    maxlength: "Máximo 50 caracteres",
                    codigoAdmin: "Use solo letras, números, guion o guion bajo"
                },

                admin_telefono_institucional: {
                    required: "El teléfono institucional es obligatorio",
                    telefonoAdmin: "Ingrese entre 7 y 20 dígitos"
                },

                foto_usuario: {
                    extension: "Solo se permiten imágenes PNG, JPG o JPEG",
                    tamanioArchivo: "La imagen no puede superar los 5 MB"
                }
            },

            errorPlacement: function (error, element) {
                if (element.attr("name") === "foto_usuario") {
                    $("#errorFotoUsuario")
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
                $("#btnGuardar")
                    .prop("disabled", true)
                    .html(
                        '<span class="spinner-border spinner-border-sm"></span> ' +
                        "Guardando..."
                    );

                form.submit();
            }
        });

        fotoUsuario.on("change", function () {
            $(this).valid();
        });

        $("#btnLimpiar").on("click", function () {
            setTimeout(function () {

                validador.resetForm();

                formulario
                    .find(".form-control")
                    .removeClass("error valid");

                $("#errorFotoUsuario").empty();

                try {
                    fotoUsuario.fileinput("clear");
                } catch (error) {
                    console.log(error);
                }

            }, 0);
        });

    });
