$(document).ready(function () {
    const $form = $("#frmProductoCarga");
    if (!$form.length) return;

    const $catalog = $("#catalogSection");
    const $custom = $("#customSection");
    const $marcaCatalogo = $("#txt_marca_catalogo");
    const $producto = $("#txt_catalogo_producto");
    const $marcaPropia = $("#txt_marca_personalizada_select");
    const $otraMarca = $("#otraMarcaGroup");
    const $presentacion = $("#txt_presentacion_producto");
    const $peso = $("#txt_peso_unitario_kg");
    const MULTIPLICADOR = {UNIDAD:1, BOTELLA:1, GALON:1, FUNDA:6, PAQUETE:6, CAJA:12, JABA:12};

    // Guardamos todas las opciones para reconstruir el select por marca sin listas enormes.
    const catalogOptions = $producto.find("option").slice(1).map(function () {
        return {
            value: this.value,
            text: this.textContent.trim(),
            nombre: this.dataset.nombre || "",
            marca: this.dataset.marca || "",
            precio: this.dataset.precio || "",
            pesoBase: this.dataset.pesoBase || "",
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
        actualizarOtraMarca();
    }

    function optionHtml(item) {
        const option = document.createElement("option");
        option.value = item.value;
        option.textContent = item.text;
        option.dataset.nombre = item.nombre;
        option.dataset.marca = item.marca;
        option.dataset.precio = item.precio;
        option.dataset.pesoBase = item.pesoBase;
        if (item.legacy) option.dataset.legacy = item.legacy;
        return option;
    }

    function filtrarProductos(conservarSeleccion) {
        const marca = $marcaCatalogo.val();
        const actual = conservarSeleccion ? $producto.val() : "";
        $producto.empty().append(new Option(marca ? "Seleccione un producto" : "Seleccione una marca", ""));
        catalogOptions.forEach(function (item) {
            if (item.legacy || (marca && item.marca === marca)) {
                $producto[0].appendChild(optionHtml(item));
            }
        });
        const seleccionadoOriginal = catalogOptions.find(i => i.selected);
        const objetivo = actual || (seleccionadoOriginal ? seleccionadoOriginal.value : "");
        if (objetivo && $producto.find(`option[value="${CSS.escape(objetivo)}"]`).length) {
            $producto.val(objetivo);
        }
        actualizarVista();
    }

    function actualizarVista() {
        const option = $producto[0]?.options[$producto[0].selectedIndex];
        if (!option || !$producto.val()) {
            $("#vistaNombreProducto").text("Seleccione un producto");
            $("#vistaDetalleProducto").text("—");
            return;
        }
        $("#vistaNombreProducto").text(option.dataset.nombre || option.textContent);
        const precio = Number(option.dataset.precio || "");
        $("#vistaDetalleProducto").text(
            (option.dataset.marca || "Sin marca") + (Number.isFinite(precio) ? ` · Ref. $${precio.toFixed(2)}` : "")
        );
    }

    function actualizarOtraMarca() {
        $otraMarca.prop("hidden", $marcaPropia.val() !== "OTRA");
    }

    function estimarPeso(forzar) {
        if (personalizado()) return;
        const option = $producto[0]?.options[$producto[0].selectedIndex];
        const base = Number(option?.dataset.pesoBase || "");
        const presentacion = $presentacion.val();
        if (!Number.isFinite(base) || base <= 0 || !presentacion) return;
        const estimado = base * (MULTIPLICADOR[presentacion] || 1);
        if (forzar || !$peso.val()) $peso.val(estimado.toFixed(2));
        $("#pesoEstimadoAyuda").text(`Estimado: ${estimado.toFixed(2)} kg. Puedes corregirlo antes de guardar. Máximo 2000 kg.`);
    }

    $("input[name='txt_modo_producto']").on("change", actualizarModo);
    $marcaCatalogo.on("change", function(){ filtrarProductos(false); });
    $producto.on("change", function(){ actualizarVista(); estimarPeso(true); });
    $presentacion.on("change", function(){ estimarPeso(true); });
    $marcaPropia.on("change", actualizarOtraMarca);

    actualizarModo();
    filtrarProductos(true);
    actualizarOtraMarca();
    estimarPeso(false);

    $.validator.addMethod("decimalPositivo", function (value, element) {
        if (this.optional(element)) return true;
        const numero = Number(String(value).replace(",", "."));
        return Number.isFinite(numero) && numero > 0 && numero <= 2000;
    }, "Ingrese un peso mayor que 0 y máximo 2000 kg");

    $form.validate({
        ignore: ":hidden:not(select)",
        rules: {
            txt_presentacion_producto: {required: true},
            txt_peso_unitario_kg: {required: true, decimalPositivo: true},
            txt_nota_producto: {maxlength: 250}
        },
        submitHandler: function (form) {
            let valido = true;
            if (!personalizado()) {
                if (!$marcaCatalogo.val()) { $marcaCatalogo.addClass("is-invalid"); valido = false; }
                if (!$producto.val()) { $producto.addClass("is-invalid"); valido = false; }
            } else {
                if (!$marcaPropia.val()) { $marcaPropia.addClass("is-invalid"); valido = false; }
                if (!$marcaPropia.val() || ($marcaPropia.val() === "OTRA" && !$("#txt_marca_personalizada").val().trim())) valido = false;
                if (!$("#txt_nombre_personalizado").val().trim()) { $("#txt_nombre_personalizado").addClass("is-invalid"); valido = false; }
            }
            if (!valido) return false;
            $peso.val(String($peso.val()).replace(",", "."));
            $("#txt_precio_referencia").val(String($("#txt_precio_referencia").val()).replace(",", "."));
            $("#btnGuardarProducto").prop("disabled", true).html('<span class="spinner-border spinner-border-sm"></span> Guardando...');
            form.submit();
        }
    });
});
