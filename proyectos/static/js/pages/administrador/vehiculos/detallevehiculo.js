document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll(".js-confirm-form").forEach(function (formulario) {
    formulario.addEventListener("submit", function (evento) {
      if (!window.confirm(formulario.dataset.confirmMessage || "¿Confirmar acción?")) evento.preventDefault();
    });
  });
});
