document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll(".js-offline-link").forEach(function (boton) {
    boton.addEventListener("click", function () { window.location.href = boton.dataset.url || "/"; });
  });
});
