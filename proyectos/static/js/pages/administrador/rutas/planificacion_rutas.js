(function () {
    "use strict";
    document.addEventListener("DOMContentLoaded", function () {
        const form = document.getElementById("adminRoutePlanningForm");
        const vehicle = document.getElementById("routeVehicleSelect");
        const load = document.getElementById("routeLoadSelect");
        const preview = document.getElementById("planningPreview");
        if (!form || !vehicle || !load) return;
        const vehicleError = document.getElementById("routeVehicleError");
        const loadError = document.getElementById("routeLoadError");

        function setError(select, box, message) {
            select.classList.toggle("is-invalid", Boolean(message));
            if (box) box.textContent = message || "";
        }
        function filterLoads() {
            const id = vehicle.value;
            load.value = "";
            load.options[0].textContent = id ? "Seleccione una carga" : "Seleccione primero el vehículo";
            Array.from(load.options).slice(1).forEach(option => option.hidden = option.dataset.vehicle !== id);
            load.disabled = !id;
            preview.hidden = true;
            setError(vehicle, vehicleError, "");
            setError(load, loadError, "");
        }
        function showPreview() {
            const option = load.options[load.selectedIndex];
            if (!load.value || !option) { preview.hidden = true; return; }
            document.getElementById("previewDate").textContent = option.dataset.date || "—";
            document.getElementById("previewWeight").textContent = (option.dataset.weight || "0") + " kg";
            document.getElementById("previewProducts").textContent = option.dataset.products || "0";
            document.getElementById("previewStatus").textContent = option.dataset.status || "—";
            document.getElementById("previewToday").hidden = option.dataset.today !== "1";
            preview.hidden = false;
            setError(load, loadError, "");
        }
        vehicle.addEventListener("change", filterLoads);
        load.addEventListener("change", showPreview);
        form.addEventListener("submit", function (event) {
            if (window.DistricSubmitGuard?.isLocked(form)) { event.preventDefault(); return; }
            let valid = true;
            if (!vehicle.value) { setError(vehicle, vehicleError, "Selecciona un vehículo con conductor."); valid = false; }
            if (!load.value) { setError(load, loadError, "Selecciona una carga."); valid = false; }
            if (!valid) event.preventDefault();
        });
    });
})();
