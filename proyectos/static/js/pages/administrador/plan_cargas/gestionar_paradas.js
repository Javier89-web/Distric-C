document.addEventListener("DOMContentLoaded", function () {
        const selector = document.getElementById("lugarGuardado");

        selector.addEventListener("change", function () {
            const opcion = this.options[this.selectedIndex];

            if (!opcion.value) {
                return;
            }

            document.getElementById("nombreParada").value = opcion.dataset.nombre || "";
            document.getElementById("direccionParada").value = opcion.dataset.nombre || "";
            document.getElementById("latitudParada").value = opcion.dataset.latitud || "";
            document.getElementById("longitudParada").value = opcion.dataset.longitud || "";
        });
    });


document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll(".js-confirm-form").forEach(function (formulario) {
    formulario.addEventListener("submit", function (evento) {
      if (!window.confirm(formulario.dataset.confirmMessage || "¿Confirmar acción?")) evento.preventDefault();
    });
  });
});
