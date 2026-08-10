document.addEventListener("DOMContentLoaded", function () {
        const formFiltro = document.getElementById("formFiltroCargas");
        const fechaFiltro = document.getElementById("fechaFiltroCarga");

        if (formFiltro && fechaFiltro) {
            fechaFiltro.addEventListener("change", function () {
                if (fechaFiltro.value) {
                    formFiltro.submit();
                }
            });
        }
    });
