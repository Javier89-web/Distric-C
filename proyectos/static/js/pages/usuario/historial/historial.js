(function () {
    "use strict";

    document.querySelectorAll(".delete-trip-form").forEach(function (form) {
        form.addEventListener("submit", function (event) {
            event.preventDefault();
            Swal.fire({
                title: "¿Eliminar este viaje del historial?",
                text: "Se eliminarán sus tramos, entregas y puntos GPS asociados.",
                icon: "warning",
                showCancelButton: true,
                confirmButtonText: "Eliminar",
                cancelButtonText: "Cancelar",
                confirmButtonColor: "#d71920",
                cancelButtonColor: "#23262b",
                reverseButtons: true,
            }).then(function (result) {
                if (result.isConfirmed) HTMLFormElement.prototype.submit.call(form);
            });
        });
    });
})();
