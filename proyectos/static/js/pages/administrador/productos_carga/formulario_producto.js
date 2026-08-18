$(document).ready(function () {
    const $form = $("#frmProductoCarga");
    if (!$form.length) return;

    const $catalog = $("#catalogSection");
    const $custom = $("#customSection");
    const $presentation = $("#presentationSection");
    const $observation = $("#observationField");
    const $pageDescription = $("#pageDescription");
    const $btnText = $("#btnGuardarTexto");

    const $marcaCatalogo = $("#txt_marca_catalogo");
    const $producto = $("#txt_catalogo_producto");
    const $marcaPropia = $("#txt_marca_personalizada_select");
    const $otraMarca = $("#otraMarcaGroup");

    const $contenido = $("#txt_contenido_unitario");
    const $unidad = $("#txt_unidad_contenido");
    const $presentacion = $("#txt_presentacion_producto");
    const $unidades = $("#txt_unidades_presentacion");
    const $peso = $("#txt_peso_unitario_kg");

    const $contenidoPropio = $("#txt_contenido_catalogo_personalizado");
    const $unidadPropia = $("#txt_unidad_catalogo_personalizado");

    const FACTOR_KG = {
        ML: 0.001,
        L: 1,
        G: 0.001,
        KG: 1
    };

    const catalogOptions = $producto.find("option").slice(1).map(function () {
        return {
            value: this.value,
            text: this.textContent.trim(),
            nombre: this.dataset.nombre || "",
            marca: this.dataset.marca || "",
            precio: this.dataset.precio || "",
            contenido: this.dataset.contenido || "",
            unidad: this.dataset.unidad || "",
            legacy: this.dataset.legacy || "",
            selected: this.selected
        };
    }).get();

    function personalizado() {
        return $("input[name='txt_modo_producto']:checked").val() === "PERSONALIZADO";
    }

    function actualizarModo() {
        const propio = personalizado();

        $catalog.prop("hidden", propio);
        $custom.prop("hidden", !propio);
        $presentation.prop("hidden", propio);
        $observation.prop("hidden", propio);

        if (propio) {
            $pageDescription.text("Agrega la información base de un producto nuevo al catálogo.");
            $btnText.text("Agregar al catálogo");
            $peso.val("");
        } else {
            $pageDescription.text("Selecciona un producto del catálogo y define su presentación.");
            $btnText.text($form.find("input[name='id_producto_carga']").length ? "Guardar cambios" : "Guardar producto");
            cargarContenidoCatalogo(false);
            calcularPeso();
        }

        actualizarOtraMarca();
        $form.find(".is-invalid").removeClass("is-invalid");
    }

    function crearOption(item) {
        const option = document.createElement("option");
        option.value = item.value;
        option.textContent = item.text;
        option.dataset.nombre = item.nombre;
        option.dataset.marca = item.marca;
        option.dataset.precio = item.precio;
        option.dataset.contenido = item.contenido;
        option.dataset.unidad = item.unidad;
        if (item.legacy) option.dataset.legacy = item.legacy;
        return option;
    }

    function filtrarProductos(conservarSeleccion) {
        const marca = $marcaCatalogo.val();
        const actual = conservarSeleccion ? $producto.val() : "";

        $producto.empty().append(
            new Option(marca ? "Seleccione un producto" : "Seleccione una marca", "")
        );

        catalogOptions.forEach(function (item) {
            if (item.legacy || (marca && item.marca === marca)) {
                $producto[0].appendChild(crearOption(item));
            }
        });

        const seleccionadoOriginal = catalogOptions.find(function (item) {
            return item.selected;
        });
        const objetivo = actual || (seleccionadoOriginal ? seleccionadoOriginal.value : "");

        if (objetivo) {
            const existe = $producto.find("option").filter(function () {
                return this.value === objetivo;
            }).length;
            if (existe) $producto.val(objetivo);
        }

        actualizarVista();
    }

    function obtenerOptionSeleccionada() {
        if (!$producto.length || !$producto.val()) return null;
        return $producto[0].options[$producto[0].selectedIndex] || null;
    }

    function actualizarVista() {
        const option = obtenerOptionSeleccionada();

        if (!option) {
            $("#vistaNombreProducto").text("Seleccione un producto");
            $("#vistaDetalleProducto").text("—");
            return;
        }

        $("#vistaNombreProducto").text(option.dataset.nombre || option.textContent);

        const detalles = [];
        if (option.dataset.marca) detalles.push(option.dataset.marca);
        if (option.dataset.contenido && option.dataset.unidad) {
            const etiqueta = option.dataset.unidad === "ML" ? "ml" : option.dataset.unidad;
            detalles.push(`${option.dataset.contenido} ${etiqueta}`);
        }
        if (option.dataset.precio !== "") {
            const precio = Number(option.dataset.precio);
            if (Number.isFinite(precio)) detalles.push(`Ref. $${precio.toFixed(2)}`);
        }

        $("#vistaDetalleProducto").text(detalles.join(" · ") || "—");
    }

    function cargarContenidoCatalogo(forzar) {
        if (personalizado()) return;

        const option = obtenerOptionSeleccionada();
        if (!option) {
            if (forzar) {
                $contenido.val("");
                $unidad.val("");
            }
            calcularPeso();
            return;
        }

        if (forzar) {
            $contenido.val(option.dataset.contenido || "");
            $unidad.val(option.dataset.unidad || "");
        } else {
            if (option.dataset.contenido && !$contenido.val()) {
                $contenido.val(option.dataset.contenido);
            }
            if (option.dataset.unidad && !$unidad.val()) {
                $unidad.val(option.dataset.unidad);
            }
        }

        calcularPeso();
    }

    function actualizarOtraMarca() {
        if (!$otraMarca.length) return;
        $otraMarca.prop("hidden", $marcaPropia.val() !== "OTRA");
    }

    function formatearCantidad(valor, decimales = 2) {
        if (!Number.isFinite(valor)) return "—";
        return valor.toLocaleString("es-EC", {
            minimumFractionDigits: decimales,
            maximumFractionDigits: decimales
        });
    }

    function etiquetaUnidad(unidad) {
        const etiquetas = { ML: "ml", L: "L", G: "g", KG: "kg" };
        return etiquetas[unidad] || unidad;
    }

    function calcularPeso() {
        if (personalizado()) {
            $peso.val("");
            return;
        }

        const contenido = Number(String($contenido.val() || "").replace(",", "."));
        const unidad = String($unidad.val() || "").toUpperCase();
        const unidades = Number.parseInt($unidades.val(), 10);
        const factor = FACTOR_KG[unidad];

        if (
            !Number.isFinite(contenido) ||
            contenido <= 0 ||
            factor === undefined ||
            !Number.isInteger(unidades) ||
            unidades <= 0
        ) {
            $peso.val("");
            $("#pesoCalculadoVista").text("0,00 kg");
            $("#pesoCalculadoDetalle").text("Ingresa el contenido y la cantidad.");
            return;
        }

        const pesoTotalKg = contenido * unidades * factor;

        $peso.val(pesoTotalKg.toFixed(2));
        $("#pesoCalculadoVista").text(`${formatearCantidad(pesoTotalKg)} kg`);
        $("#pesoCalculadoDetalle").text(
            `${formatearCantidad(contenido, contenido % 1 === 0 ? 0 : 3)} ${etiquetaUnidad(unidad)} × ${unidades} ${unidades === 1 ? "unidad" : "unidades"}`
        );
    }

    $("input[name='txt_modo_producto']").on("change", actualizarModo);

    $marcaCatalogo.on("change", function () {
        filtrarProductos(false);
        cargarContenidoCatalogo(true);
    });

    $producto.on("change", function () {
        actualizarVista();
        cargarContenidoCatalogo(true);
    });

    $contenido.on("input change", calcularPeso);
    $unidad.on("change", calcularPeso);
    $presentacion.on("change", calcularPeso);
    $unidades.on("input change", calcularPeso);
    $marcaPropia.on("change", actualizarOtraMarca);

    $.validator.addMethod("decimalPositivo", function (value, element) {
        if (this.optional(element)) return true;
        const numero = Number(String(value).replace(",", "."));
        return Number.isFinite(numero) && numero > 0;
    }, "Ingrese un valor mayor que 0");

    $.validator.addMethod("enteroPresentacion", function (value, element) {
        if (this.optional(element)) return true;
        const numero = Number(value);
        return Number.isInteger(numero) && numero >= 1 && numero <= 500;
    }, "Ingrese entre 1 y 500 unidades");

    $form.validate({
        ignore: ":hidden",
        rules: {
            txt_contenido_unitario: {
                required: { depends: function () { return !personalizado(); } },
                decimalPositivo: true
            },
            txt_unidad_contenido: {
                required: { depends: function () { return !personalizado(); } }
            },
            txt_presentacion_producto: {
                required: { depends: function () { return !personalizado(); } }
            },
            txt_unidades_presentacion: {
                required: { depends: function () { return !personalizado(); } },
                enteroPresentacion: true
            },
            txt_nombre_personalizado: {
                required: { depends: personalizado },
                minlength: 2,
                maxlength: 100
            },
            txt_contenido_catalogo_personalizado: {
                required: { depends: personalizado },
                decimalPositivo: true
            },
            txt_unidad_catalogo_personalizado: {
                required: { depends: personalizado }
            },
            txt_nota_producto: { maxlength: 250 }
        },
        messages: {
            txt_unidad_contenido: "Seleccione una unidad",
            txt_presentacion_producto: "Seleccione una presentación",
            txt_unidad_catalogo_personalizado: "Seleccione una unidad"
        },
        submitHandler: function (form) {
            let valido = true;

            if (personalizado()) {
                if (!$marcaPropia.val()) {
                    $marcaPropia.addClass("is-invalid");
                    valido = false;
                }

                if (
                    $marcaPropia.val() === "OTRA" &&
                    !$("#txt_marca_personalizada").val().trim()
                ) {
                    $("#txt_marca_personalizada").addClass("is-invalid");
                    valido = false;
                }

                if (!$("#txt_nombre_personalizado").val().trim()) {
                    $("#txt_nombre_personalizado").addClass("is-invalid");
                    valido = false;
                }

                if (!$contenidoPropio.val() || !$unidadPropia.val()) {
                    if (!$contenidoPropio.val()) $contenidoPropio.addClass("is-invalid");
                    if (!$unidadPropia.val()) $unidadPropia.addClass("is-invalid");
                    valido = false;
                }
            } else {
                if (!$marcaCatalogo.val()) {
                    $marcaCatalogo.addClass("is-invalid");
                    valido = false;
                }
                if (!$producto.val()) {
                    $producto.addClass("is-invalid");
                    valido = false;
                }

                calcularPeso();
                const pesoCalculado = Number($peso.val());
                if (!Number.isFinite(pesoCalculado) || pesoCalculado <= 0 || pesoCalculado > 2000) {
                    Swal.fire({
                        icon: "warning",
                        title: "Revisa el peso calculado",
                        text: "La presentación debe pesar más de 0 kg y máximo 2000 kg."
                    });
                    valido = false;
                }
            }

            if (!valido) return false;

            $contenido.val(String($contenido.val() || "").replace(",", "."));
            $contenidoPropio.val(String($contenidoPropio.val() || "").replace(",", "."));
            $("#txt_precio_referencia").val(
                String($("#txt_precio_referencia").val() || "").replace(",", ".")
            );

            $("#btnGuardarProducto")
                .prop("disabled", true)
                .html('<span class="spinner-border spinner-border-sm"></span> Guardando...');

            form.submit();
        }
    });

    filtrarProductos(true);
    actualizarOtraMarca();
    actualizarModo();
    actualizarVista();
    if (!personalizado()) cargarContenidoCatalogo(false);
    calcularPeso();
});
