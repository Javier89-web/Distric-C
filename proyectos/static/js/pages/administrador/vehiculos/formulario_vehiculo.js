$(document).ready(function () {

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

        $("#foto_vehiculo").fileinput({
            language: "es",

            allowedFileExtensions: [
                "png",
                "jpg",
                "jpeg",
                "webp"
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
                "Arrastra una imagen del vehículo aquí o selecciónala desde tu equipo",

            fileActionSettings: {
                showUpload: false,
                showRemove: true,
                showZoom: true,
                showDrag: false
            }
        });

        $.validator.addMethod(
            "placaValida",
            function (value, element) {
                return this.optional(element) ||
                    /^[A-Z]{3}-[0-9]{4}$/.test(value);
            },
            "Utilice el formato ABC-1234"
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

                const provincia = parseInt(
                    value.substring(0, 2)
                );

                if (provincia < 1 || provincia > 24) {
                    return false;
                }

                if (parseInt(value[2]) >= 6) {
                    return false;
                }

                const coeficientes = [
                    2, 1, 2, 1, 2, 1, 2, 1, 2
                ];

                let suma = 0;

                for (let i = 0; i < 9; i++) {
                    let resultado =
                        parseInt(value[i]) *
                        coeficientes[i];

                    if (resultado >= 10) {
                        resultado -= 9;
                    }

                    suma += resultado;
                }

                const verificador =
                    (10 - (suma % 10)) % 10;

                return verificador === parseInt(value[9]);
            },
            "Ingrese una cédula ecuatoriana válida"
        );

        $.validator.addMethod(
            "motorValido",
            function (value, element) {
                return this.optional(element) ||
                    /^[A-Z0-9-]+$/.test(value);
            },
            "Solo permite letras, números y guiones"
        );

        $.validator.addMethod(
            "chasisValido",
            function (value, element) {
                return this.optional(element) ||
                    /^[A-HJ-NPR-Z0-9]{17}$/.test(value);
            },
            "Debe contener 17 caracteres sin I, O ni Q"
        );

        $.validator.addMethod(
            "decimalRango",
            function (value, element, rango) {
                if (this.optional(element)) {
                    return true;
                }

                const numero = parseFloat(
                    value.replace(",", ".")
                );

                return !isNaN(numero) &&
                    numero >= rango[0] &&
                    numero <= rango[1];
            },
            "Ingrese un valor válido"
        );

        $("#frmVehiculoAdmin").validate({

            ignore: [],

            rules: {
                foto_vehiculo: {
                    extension: "png|jpg|jpeg|webp",
                    tamanioArchivo: 5242880
                },

                txt_tipo_vehiculo: {
                    required: true
                },

                txt_tipo_combustible: {
                    required: true
                },

                txt_matricula: {
                    required: true,
                    placaValida: true
                },

                txt_modelo: {
                    maxlength: 50
                },

                txt_numero_cedula: {
                    required: true,
                    cedulaEcuador: true
                },

                txt_numero_motor: {
                    required: true,
                    minlength: 5,
                    maxlength: 12,
                    motorValido: true
                },

                txt_numero_chasis: {
                    required: true,
                    chasisValido: true
                },

                txt_peso_auto: {
                    required: true,
                    decimalRango: [0.1, 8]
                },

                txt_capacidad_carga_kg: {
                    required: true,
                    decimalRango: [1, 50000]
                },

                txt_cilindraje: {
                    required: true,
                    decimalRango: [1, 5000]
                }
            },

            messages: {
                foto_vehiculo: {
                    extension: "Solo se permiten imágenes PNG, JPG, JPEG o WEBP",
                    tamanioArchivo: "La imagen no puede superar los 5 MB"
                },

                txt_tipo_vehiculo: {
                    required: "Seleccione el tipo de vehículo"
                },

                txt_tipo_combustible: {
                    required: "Seleccione el combustible"
                },

                txt_matricula: {
                    required: "Ingrese la placa"
                },

                txt_modelo: {
                    maxlength: "Máximo 50 caracteres"
                },

                txt_numero_cedula: {
                    required: "Ingrese la cédula"
                },

                txt_numero_motor: {
                    required: "Ingrese el número de motor",
                    minlength: "Mínimo 5 caracteres",
                    maxlength: "Máximo 12 caracteres"
                },

                txt_numero_chasis: {
                    required: "Ingrese el número de chasis"
                },

                txt_peso_auto: {
                    required: "Ingrese el peso propio del vehículo",
                    decimalRango: "Debe estar entre 0.1 y 8 toneladas"
                },

                txt_capacidad_carga_kg: {
                    required: "Ingrese la capacidad máxima de carga",
                    decimalRango: "Debe estar entre 1 y 50000 kg"
                },

                txt_cilindraje: {
                    required: "Ingrese el cilindraje",
                    decimalRango: "Debe estar entre 1 y 5000"
                }
            },

            errorPlacement: function (error, element) {
                if (element.attr("name") === "foto_vehiculo") {
                    $("#errorFotoVehiculo")
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

                $("#txt_peso_auto").val(
                    $("#txt_peso_auto")
                        .val()
                        .replace(",", ".")
                );

                $("#txt_capacidad_carga_kg").val(
                    $("#txt_capacidad_carga_kg")
                        .val()
                        .replace(",", ".")
                );

                $("#txt_cilindraje").val(
                    $("#txt_cilindraje")
                        .val()
                        .replace(",", ".")
                );

                $("#btnGuardarVehiculo")
                    .prop("disabled", true)
                    .html(
                        '<span class="spinner-border spinner-border-sm"></span> Guardando...'
                    );

                form.submit();
            }
        });

        $("#txt_matricula").on("input", function () {
            let valor = this.value
                .toUpperCase()
                .replace(/[^A-Z0-9]/g, "");

            if (valor.length > 3) {
                valor =
                    valor.slice(0, 3) +
                    "-" +
                    valor.slice(3, 7);
            }

            this.value = valor;
        });

        $("#txt_numero_cedula").on("input", function () {
            this.value = this.value
                .replace(/\D/g, "")
                .slice(0, 10);
        });

        $("#txt_numero_motor").on("input", function () {
            this.value = this.value
                .toUpperCase()
                .replace(/[^A-Z0-9-]/g, "")
                .slice(0, 12);
        });

        $("#txt_numero_chasis").on("input", function () {
            this.value = this.value
                .toUpperCase()
                .replace(/[^A-HJ-NPR-Z0-9]/g, "")
                .slice(0, 17);
        });

        $("#foto_vehiculo").on("change", function () {
            $(this).valid();
        });

    });
