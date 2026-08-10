document
        .getElementById("buscarUsuario")
        .addEventListener("input", function() {

            const filtro = this.value
                .toLowerCase()
                .trim();

            const filas = document.querySelectorAll(
                "#tablaVehiculos tbody tr:not(.fila-vacia)"
            );

            filas.forEach(function(fila) {

                const nombreElemento =
                    fila.querySelector(".usuario-nombre");

                if (!nombreElemento) {
                    return;
                }

                const nombre = nombreElemento
                    .textContent
                    .toLowerCase()
                    .trim();

                if (nombre.includes(filtro)) {
                    fila.style.display = "";
                }

                else {
                    fila.style.display = "none";
                }

            });

        });
