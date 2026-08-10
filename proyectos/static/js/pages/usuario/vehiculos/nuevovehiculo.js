$(document).ready(function () {

        const formulario = $("#formVehiculo");

        const validador = formulario.validate({

            rules: {
                txt_tipo_vehiculo: {
                    required: true
                },

                txt_tipo_combustible: {
                    required: true
                },

                txt_matricula: {
                    required: true,
                    pattern: /^[A-Z]{3}-[0-9]{4}$/
                },

                txt_modelo: {
                    maxlength: 50,
                    pattern: /^[A-Za-zÁÉÍÓÚÑáéíóúñ0-9 .-]*$/
                },

                txt_numero_cedula: {
                    required: true,
                    digits: true,
                    minlength: 10,
                    maxlength: 10
                },

                txt_numero_motor: {
                    required: true,
                    minlength: 5,
                    maxlength: 12,
                    pattern: /^[A-Z0-9-]+$/
                },

                txt_numero_chasis: {
                    required: true,
                    minlength: 17,
                    maxlength: 17,
                    pattern: /^[A-HJ-NPR-Z0-9]{17}$/
                },

                txt_peso_auto: {
                    required: true,
                    number: true,
                    min: 0.1,
                    max: 8
                },

                txt_cilindraje: {
                    required: true,
                    number: true,
                    min: 1,
                    max: 5000
                }
            },

            messages: {
                txt_tipo_vehiculo: {
                    required: "Seleccione el tipo de vehículo"
                },

                txt_tipo_combustible: {
                    required: "Seleccione el tipo de combustible"
                },

                txt_matricula: {
                    required: "Ingrese la placa del vehículo",
                    pattern: "Utilice el formato ABC-1234"
                },

                txt_modelo: {
                    maxlength: "El modelo no puede superar los 50 caracteres",
                    pattern: "El modelo contiene caracteres no permitidos"
                },

                txt_numero_cedula: {
                    required: "Ingrese la cédula del propietario",
                    digits: "La cédula solamente puede contener números",
                    minlength: "La cédula debe tener 10 dígitos",
                    maxlength: "La cédula debe tener 10 dígitos"
                },

                txt_numero_motor: {
                    required: "Ingrese el número de motor",
                    minlength: "Debe contener al menos 5 caracteres",
                    maxlength: "No puede superar los 12 caracteres",
                    pattern: "Solo se permiten letras, números y guiones"
                },

                txt_numero_chasis: {
                    required: "Ingrese el número de chasis",
                    minlength: "El chasis debe tener 17 caracteres",
                    maxlength: "El chasis debe tener 17 caracteres",
                    pattern: "Formato inválido: no se permiten I, O ni Q"
                },

                txt_peso_auto: {
                    required: "Ingrese el peso del vehículo",
                    number: "Ingrese un número válido",
                    min: "El peso debe ser mayor o igual a 0.1 toneladas",
                    max: "El peso máximo permitido es 8 toneladas"
                },

                txt_cilindraje: {
                    required: "Ingrese el cilindraje",
                    number: "Ingrese un número válido",
                    min: "El cilindraje debe ser mayor que cero",
                    max: "El cilindraje máximo permitido es 5000"
                }
            },

            errorPlacement: function (error, element) {
                error.insertAfter(element);
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
                $("#btnGuardarVehiculo")
                    .prop("disabled", true)
                    .html(
                        '<span class="spinner-border spinner-border-sm"></span> ' +
                        "Guardando..."
                    );

                form.submit();
            }
        });

        /* Placa en mayúsculas y con guion automático */
        $("#txt_matricula").on("input", function () {
            let valor = this.value
                .toUpperCase()
                .replace(/[^A-Z0-9]/g, "");

            if (valor.length > 3) {
                valor = valor.slice(0, 3) + "-" + valor.slice(3, 7);
            }

            this.value = valor;
        });

        /* Cédula: únicamente números */
        $("#txt_numero_cedula").on("input", function () {
            this.value = this.value
                .replace(/\D/g, "")
                .slice(0, 10);
        });

        /* Motor en mayúsculas */
        $("#txt_numero_motor").on("input", function () {
            this.value = this.value
                .toUpperCase()
                .replace(/[^A-Z0-9-]/g, "")
                .slice(0, 12);
        });

        /* Chasis en mayúsculas y sin I, O, Q */
        $("#txt_numero_chasis").on("input", function () {
            this.value = this.value
                .toUpperCase()
                .replace(/[^A-HJ-NPR-Z0-9]/g, "")
                .slice(0, 17);
        });

        /* Validar campos conforme se modifican */
        formulario
            .find("input, select")
            .on("change blur", function () {
                $(this).valid();
            });

    });
