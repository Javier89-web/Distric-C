document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("formConsultaCargas");
    const date = document.getElementById("fechaConsultaCarga");
    const error = document.getElementById("errorFechaConsultaCarga");
    const search = document.getElementById("buscarCargaConsulta");
    const cards = document.querySelectorAll(".consulta-card");

    function showError(message) {
        if (!date || !error) return;
        date.classList.toggle("input-error", Boolean(message));
        error.textContent = message || "";
        error.classList.toggle("visible", Boolean(message));
    }

    if (form && date) {
        form.addEventListener("submit", function (event) {
            if (!date.value) {
                event.preventDefault();
                showError("Selecciona una fecha para consultar.");
            }
        });

        date.addEventListener("change", function () {
            showError("");
        });
    }

    if (search) {
        search.addEventListener("input", function () {
            const value = this.value.toLowerCase().trim();
            cards.forEach(function (card) {
                card.hidden = !card.dataset.busqueda.toLowerCase().includes(value);
            });
        });
    }

    document.querySelectorAll(".js-consulta-progress").forEach(function (bar) {
        const value = Math.max(0, Math.min(100, Number.parseFloat(bar.dataset.progress || "0")));
        bar.style.width = `${value}%`;
        if (value >= 80) bar.style.background = "#d71920";
    });
});
