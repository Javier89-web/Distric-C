(function () {
    "use strict";

    const form = document.getElementById("finishSegmentForm");
    if (!form) return;

    const inputs = Array.from(
        form.querySelectorAll('.delivery-product-input input[type="number"]')
    );
    const total = document.getElementById("deliveryWeightTotal");
    const note = document.getElementById("nota_finalizacion");
    const evidenceInput = document.getElementById("evidencia_entrega");
    const evidencePreview = document.getElementById("evidencePreview");
    const evidencePreviewImage = document.getElementById("evidencePreviewImage");
    const evidencePreviewName = document.getElementById("evidencePreviewName");
    let confirmationOpen = false;

    function parseValue(value) {
        const number = Number.parseFloat(String(value || "0").replace(",", "."));
        return Number.isFinite(number) ? number : 0;
    }

    function updateTotal() {
        let weight = 0;
        inputs.forEach(function (input) {
            const quantity = Math.max(0, parseValue(input.value));
            const max = parseValue(input.max);
            if (quantity > max) input.value = max;
            weight += Math.min(quantity, max) * parseValue(input.dataset.unitWeight);
        });
        total.textContent = `${weight.toFixed(2).replace(".", ",")} kg`;
        return weight;
    }

    inputs.forEach(function (input) {
        input.addEventListener("input", updateTotal);
    });
    updateTotal();

    const deliverySearch = document.getElementById("deliveryProductSearch");
    if (deliverySearch) {
        const productRows = Array.from(form.querySelectorAll(".delivery-product-row"));
        deliverySearch.addEventListener("input", function () {
            const term = deliverySearch.value.toLowerCase().trim();
            productRows.forEach(function (row) {
                row.hidden = Boolean(term) && !row.textContent.toLowerCase().includes(term);
            });
        });
    }

    if (evidenceInput) {
        evidenceInput.addEventListener("change", function () {
            const file = evidenceInput.files && evidenceInput.files[0];
            if (!file) {
                if (evidencePreview) evidencePreview.hidden = true;
                return;
            }
            if (evidencePreviewName) evidencePreviewName.textContent = file.name;
            if (evidencePreviewImage) {
                evidencePreviewImage.src = URL.createObjectURL(file);
            }
            if (evidencePreview) evidencePreview.hidden = false;
        });
    }

    form.addEventListener("submit", async function (event) {
        event.preventDefault();
        if (confirmationOpen || window.DistricSubmitGuard?.isLocked(form)) return;

        confirmationOpen = true;

        const evidenceFile = evidenceInput && evidenceInput.files && evidenceInput.files[0];
        if (!evidenceFile) {
            confirmationOpen = false;
            if (evidenceInput) evidenceInput.focus();
            if (window.Swal) {
                await Swal.fire({
                    title: "Falta la evidencia",
                    text: "Adjunta una fotografía de la entrega antes de finalizar el tramo.",
                    icon: "warning",
                    confirmButtonColor: "#23262b"
                });
            }
            return;
        }

        if (evidenceFile.size > 8 * 1024 * 1024) {
            confirmationOpen = false;
            if (window.Swal) {
                await Swal.fire({
                    title: "Imagen demasiado grande",
                    text: "La evidencia no puede superar los 8 MB.",
                    icon: "warning",
                    confirmButtonColor: "#23262b"
                });
            }
            return;
        }

        const weight = updateTotal();
        if (weight <= 0 && !note.value.trim()) {
            confirmationOpen = false;
            note.focus();
            if (window.Swal) {
                await Swal.fire({
                    title: "Falta una observación",
                    text: "Explica por qué no se entregaron productos en este destino.",
                    icon: "warning",
                    confirmButtonColor: "#23262b"
                });
            }
            return;
        }

        const result = window.Swal
            ? await Swal.fire({
                title: "¿Finalizar este tramo?",
                text: `Se descontarán ${weight.toFixed(2)} kg de la carga y se guardarán los resultados.`,
                icon: "question",
                showCancelButton: true,
                confirmButtonText: "Sí, finalizar",
                cancelButtonText: "Revisar",
                confirmButtonColor: "#d71920",
                cancelButtonColor: "#23262b",
                reverseButtons: true
            })
            : { isConfirmed: window.confirm("¿Finalizar este tramo?") };

        if (result.isConfirmed) {
            window.DistricSubmitGuard.submit(
                form,
                "Finalizando tramo…",
                event.submitter || null
            );
        } else {
            confirmationOpen = false;
        }
    });
})();
