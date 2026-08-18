document.addEventListener("DOMContentLoaded", function () {
    const page = document.querySelector(".prepare-page");
    if (!page) return;
    const capacidad = Number(page.dataset.capacidad || 0);
    const inputs = Array.from(document.querySelectorAll(".cantidad-producto"));
    const barra = document.getElementById("barraCarga");
    const mensaje = document.getElementById("mensajePeso");
    const guardar = document.getElementById("btnGuardarProductos");

    function cantidad(input) {
        let value = parseInt(input.value || "0", 10);
        if (!Number.isFinite(value) || value < 0) value = 0;
        value = Math.min(value, 9999);
        input.value = value;
        return value;
    }

    function etiquetaCantidad(input, qty) {
        const porPresentacion = Math.max(1, parseInt(input.dataset.unidadesPresentacion || "1", 10) || 1);
        const singular = (input.dataset.unidadCarga || "unidad").trim() || "unidad";
        const plural = (input.dataset.unidadCargaPlural || `${singular}s`).trim() || `${singular}s`;
        const nombrePresentacion = qty === 1 ? singular : plural;
        const unidadesTotales = qty * porPresentacion;
        if (porPresentacion === 1) return `${qty} ${nombrePresentacion}`;
        return `${qty} ${nombrePresentacion} · ${unidadesTotales} unidad${unidadesTotales === 1 ? "" : "es"}`;
    }

    function recalcular() {
        let pesoTotal = 0;
        let unidades = 0;
        inputs.forEach(function (input) {
            const qty = cantidad(input);
            const peso = Number(input.dataset.peso || 0);
            const subtotal = qty * peso;
            pesoTotal += subtotal;
            unidades += qty;
            const id = input.id.replace("cantidad_", "");
            const out = document.getElementById("subtotal_" + id);
            if (out) out.textContent = subtotal.toFixed(2) + " kg";
            const unidadesOut = document.getElementById("unidades_" + id);
            if (unidadesOut) unidadesOut.textContent = etiquetaCantidad(input, qty);
        });
        const porcentaje = capacidad > 0 ? (pesoTotal / capacidad) * 100 : 0;
        if (barra) {
            barra.style.width = Math.min(porcentaje, 100) + "%";
            barra.classList.toggle("warning", porcentaje >= 80);
        }
        const excede = pesoTotal > capacidad;
        if (mensaje) {
            mensaje.classList.toggle("error", excede);
            mensaje.textContent = excede
                ? `Carga: ${pesoTotal.toFixed(2)} kg · Exceso: ${(pesoTotal-capacidad).toFixed(2)} kg`
                : `Carga: ${pesoTotal.toFixed(2)} kg · Disponible: ${Math.max(capacidad-pesoTotal,0).toFixed(2)} kg · ${porcentaje.toFixed(1)}%`;
        }
        if (guardar) guardar.disabled = excede || unidades === 0;
    }

    inputs.forEach(input => input.addEventListener("input", recalcular));
    document.querySelectorAll(".sumar,.restar").forEach(function (button) {
        button.addEventListener("click", function () {
            const input = document.getElementById(button.dataset.input);
            if (!input) return;
            const next = cantidad(input) + (button.classList.contains("sumar") ? 1 : -1);
            input.value = Math.max(0, next);
            recalcular();
        });
    });

    const search = document.getElementById("buscarProductoCarga");
    const rows = Array.from(document.querySelectorAll(".product-row"));
    if (search) search.addEventListener("input", function () {
        const text = search.value.toLowerCase().trim();
        rows.forEach(row => row.hidden = !row.dataset.busqueda.toLowerCase().includes(text));
    });
    recalcular();
});
