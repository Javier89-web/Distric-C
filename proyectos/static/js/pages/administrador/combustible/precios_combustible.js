$(document).ready(function () {
    const LITROS_POR_GALON = 3.785411784;
    const $inputs = $(".fuel-input-wrap input");
    let unidad = $("input[name='unidad_precio']:checked").val() || "GALON";

    function numero(value) {
        const n = Number(String(value || "").replace(",", "."));
        return Number.isFinite(n) ? n : 0;
    }

    function formatoPrecio(value) {
        return `$${numero(value).toFixed(3)}`;
    }

    function actualizarActuales() {
        $("[data-fuel-card]").each(function () {
            const current = this.querySelector(".fuel-current-value");
            const label = this.querySelector(".fuel-current-unit");
            if (!current || !label) return;
            const value = unidad === "GALON" ? numero(current.dataset.gallon) : numero(current.dataset.liter);
            if (value > 0) {
                current.textContent = formatoPrecio(value);
                label.textContent = unidad === "GALON" ? "USD por galón" : "USD por litro";
            }
        });
    }

    function actualizarPreview(input) {
        const valor = numero(input.value);
        const output = document.querySelector(`[data-equivalent-for="${input.id}"]`);
        if (!output) return;
        if (valor <= 0) { output.textContent = "Ingrese el nuevo valor"; return; }
        output.textContent = unidad === "GALON"
            ? `Equivalente: $${(valor / LITROS_POR_GALON).toFixed(4)} / L`
            : `Equivalente: $${(valor * LITROS_POR_GALON).toFixed(4)} / gal`;
    }

    function cambiarUnidad(nueva) {
        if (nueva === unidad) return;
        $inputs.each(function () {
            const actual = numero(this.value);
            if (actual > 0) {
                this.value = (nueva === "GALON" ? actual * LITROS_POR_GALON : actual / LITROS_POR_GALON).toFixed(4);
            }
        });
        unidad = nueva;
        $("[data-unit-suffix]").text(unidad === "GALON" ? "USD/gal" : "USD/L");
        $("#fuelUnitHelp").html(
            unidad === "GALON"
                ? '<i class="bi bi-info-circle"></i> Ejemplo: 3.260 significa USD 3,260 por cada galón.'
                : '<i class="bi bi-info-circle"></i> El valor se interpreta como dólares por cada litro.'
        );
        actualizarActuales();
        $inputs.each(function () { actualizarPreview(this); });
    }

    $("input[name='unidad_precio']").on("change", function () { cambiarUnidad(this.value); });
    $inputs.on("input", function () { actualizarPreview(this); }).each(function () { actualizarPreview(this); });
    actualizarActuales();

    if ($.fn.DataTable && $("#tablaHistorialPrecios tbody tr").length) {
        const tabla = $("#tablaHistorialPrecios").DataTable({
            pageLength: 4,
            lengthChange: false,
            searching: true,
            ordering: true,
            order: [],
            info: true,
            autoWidth: false,
            dom: "rt<'history-table-footer'ip>",
            language: {
                emptyTable: "Todavía no existen ajustes registrados",
                info: "Mostrando _START_ a _END_ de _TOTAL_ ajustes",
                infoEmpty: "Sin ajustes",
                zeroRecords: "No se encontraron ajustes",
                paginate: { previous: "Anterior", next: "Siguiente" }
            }
        });
        $("#buscarHistorialPrecios").on("input", function () { tabla.search(this.value).draw(); });
    }

    $("#frmPreciosCombustible").validate({
        rules: {
            precio_EXTRA: {required:true, number:true, min:0.0001, max:1000},
            precio_DIESEL: {required:true, number:true, min:0.0001, max:1000},
            precio_SUPER: {required:true, number:true, min:0.0001, max:1000},
            precio_ECOPAIS: {required:true, number:true, min:0.0001, max:1000}
        },
        messages: {
            precio_EXTRA: "Ingrese un precio válido",
            precio_DIESEL: "Ingrese un precio válido",
            precio_SUPER: "Ingrese un precio válido",
            precio_ECOPAIS: "Ingrese un precio válido"
        },
        errorPlacement: function (error, element) { error.insertAfter(element.closest(".fuel-input-wrap")); },
        submitHandler: function (form) {
            $("#btnGuardarPrecios").prop("disabled", true).html('<span class="spinner-border spinner-border-sm"></span> Guardando...');
            form.submit();
        }
    });
});
