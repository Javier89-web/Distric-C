document.addEventListener("DOMContentLoaded", function () {
        const modal = document.getElementById("modalAjuste");
        const formAjuste = document.getElementById("formAjuste");
        const formAgregar = document.getElementById("formAgregarProducto");
        const cantidadNueva = document.getElementById("cantidadNueva");
        const productoAjuste = document.getElementById("productoAjuste");
        const motivoAjuste = document.getElementById("motivoAjuste");
        const errorCantidadNueva = document.getElementById("errorCantidadNueva");
        const errorMotivoAjuste = document.getElementById("errorMotivoAjuste");
        let cantidadActualAjuste = 0;
        let maximoAjuste = 0;

        function mostrarErrorCampo(campo, contenedor, mensaje) {
            if (!campo || !contenedor) {
                return;
            }

            campo.classList.add("input-error");
            contenedor.textContent = mensaje;
            contenedor.classList.add("visible");
            campo.focus();
        }

        function limpiarErrorCampo(campo, contenedor) {
            if (!campo || !contenedor) {
                return;
            }

            campo.classList.remove("input-error");
            contenedor.textContent = "";
            contenedor.classList.remove("visible");
        }

        function numeroDecimal(valor) {
            return Number(String(valor || "0").replace(",", "."));
        }

        function inicializarTabla(configuracion) {
            if (!document.querySelector(configuracion.selector)) {
                return;
            }

            const tabla = $(configuracion.selector).DataTable({
                pageLength: 5,
                lengthMenu: [
                    [5, 10, 25, 50, -1],
                    [5, 10, 25, 50, "Todos"]
                ],
                order: [[0, "asc"]],
                columnDefs: configuracion.columnDefs || [],
                dom: "Brt<'table-bottom'<'table-length'l><'table-info'i><'table-page'p>>",
                buttons: [
                    {
                        extend: "csvHtml5",
                        text: '<i class="bi bi-filetype-csv"></i> CSV',
                        title: configuracion.titulo,
                        filename: configuracion.archivo,
                        charset: "utf-8",
                        bom: true,
                        exportOptions: { columns: configuracion.columnasExportar }
                    },
                    {
                        extend: "excelHtml5",
                        text: '<i class="bi bi-file-earmark-excel"></i> Excel',
                        title: configuracion.titulo,
                        filename: configuracion.archivo,
                        className: "btn-excel",
                        exportOptions: { columns: configuracion.columnasExportar }
                    },
                    {
                        extend: "pdfHtml5",
                        text: '<i class="bi bi-file-earmark-pdf"></i> PDF',
                        title: configuracion.titulo,
                        filename: configuracion.archivo,
                        className: "btn-pdf",
                        orientation: "landscape",
                        pageSize: "A4",
                        exportOptions: { columns: configuracion.columnasExportar },
                        customize: function (doc) {
                            doc.defaultStyle.fontSize = 9;
                            doc.styles.tableHeader = {
                                bold: true,
                                color: "#ffffff",
                                fillColor: "#23262b",
                                fontSize: 9
                            };
                            doc.styles.title = {
                                color: "#23262b",
                                fontSize: 16,
                                bold: true,
                                alignment: "center",
                                margin: [0, 0, 0, 15]
                            };
                            window.DistricPdfBranding?.apply(doc, "Distri C · Detalle de carga");
                        }
                    }
                ],
                language: {
                    emptyTable: "No existen registros.",
                    zeroRecords: "No se encontraron coincidencias.",
                    info: "Mostrando _START_ a _END_ de _TOTAL_ registros",
                    infoEmpty: "Mostrando 0 registros",
                    infoFiltered: "(filtrado de _MAX_ registros)",
                    lengthMenu: "Mostrar _MENU_ registros",
                    paginate: { next: "Siguiente", previous: "Anterior" }
                }
            });

            tabla.buttons().container().appendTo(configuracion.botones);
            $(configuracion.buscador).on("input", function () {
                tabla.search(this.value).draw();
            });
        }

        inicializarTabla({
            selector: "#tablaProductosCarga",
            buscador: "#buscarProductosCarga",
            botones: "#botonesProductosCarga",
            titulo: "Productos de la carga",
            archivo: "productos_carga",
            columnasExportar: [0, 1, 2, 3, 4, 5],
            columnDefs: [{ targets: 6, orderable: false, searchable: false }]
        });

        inicializarTabla({
            selector: "#tablaHistorialCarga",
            buscador: "#buscarHistorialCarga",
            botones: "#botonesHistorialCarga",
            titulo: "Historial de ajustes de la carga",
            archivo: "historial_ajustes_carga",
            columnasExportar: [0, 1, 2, 3, 4]
        });

        if (formAgregar) {
            const producto = document.getElementById("producto");
            const cantidad = document.getElementById("cantidad");
            const motivo = document.getElementById("motivo");
            const errorProducto = document.getElementById("errorProducto");
            const errorCantidad = document.getElementById("errorCantidad");
            const errorMotivo = document.getElementById("errorMotivo");

            producto.addEventListener("change", function () {
                limpiarErrorCampo(producto, errorProducto);
                limpiarErrorCampo(cantidad, errorCantidad);
            });
            cantidad.addEventListener("input", function () {
                limpiarErrorCampo(cantidad, errorCantidad);
            });
            motivo.addEventListener("input", function () {
                limpiarErrorCampo(motivo, errorMotivo);
            });

            formAgregar.addEventListener("submit", function (evento) {
                evento.preventDefault();

                limpiarErrorCampo(producto, errorProducto);
                limpiarErrorCampo(cantidad, errorCantidad);
                limpiarErrorCampo(motivo, errorMotivo);

                const cantidadValor = Number(cantidad.value);
                const nota = motivo.value.trim();

                if (!producto.value) {
                    mostrarErrorCampo(
                        producto,
                        errorProducto,
                        "Selecciona el producto que deseas agregar."
                    );
                    return;
                }

                if (!Number.isInteger(cantidadValor) || cantidadValor < 1 || cantidadValor > 9999) {
                    mostrarErrorCampo(
                        cantidad,
                        errorCantidad,
                        "Ingresa una cantidad entera entre 1 y 9999."
                    );
                    return;
                }

                const opcion = producto.options[producto.selectedIndex];
                const pesoUnitario = numeroDecimal(opcion.dataset.peso);
                const disponible = numeroDecimal(formAgregar.dataset.disponible);
                const pesoSolicitado = cantidadValor * pesoUnitario;

                if (pesoUnitario > 0 && pesoSolicitado > disponible + 0.0001) {
                    const maximo = Math.floor(disponible / pesoUnitario);
                    mostrarErrorCampo(
                        cantidad,
                        errorCantidad,
                        `La capacidad disponible permite agregar como máximo ${maximo} unidades de este producto.`
                    );
                    return;
                }

                if (nota.length < 5 || nota.length > 250) {
                    mostrarErrorCampo(
                        motivo,
                        errorMotivo,
                        "Escribe una nota de entre 5 y 250 caracteres."
                    );
                    return;
                }

                HTMLFormElement.prototype.submit.call(formAgregar);
            });
        }

        document.querySelectorAll(".abrir-ajuste").forEach(function (boton) {
            boton.addEventListener("click", function () {
                formAjuste.action = boton.dataset.url;
                cantidadActualAjuste = Number(boton.dataset.actual);
                maximoAjuste = Number(boton.dataset.maximo);

                cantidadNueva.max = maximoAjuste;
                cantidadNueva.value = cantidadActualAjuste;
                productoAjuste.textContent =
                    `${boton.dataset.producto} · asignado originalmente: ${boton.dataset.asignado} · máximo permitido por capacidad: ${maximoAjuste}`;
                motivoAjuste.value = "";
                limpiarErrorCampo(cantidadNueva, errorCantidadNueva);
                limpiarErrorCampo(motivoAjuste, errorMotivoAjuste);
                modal.classList.add("open");
            });
        });

        cantidadNueva.addEventListener("input", function () {
            limpiarErrorCampo(cantidadNueva, errorCantidadNueva);
        });

        motivoAjuste.addEventListener("input", function () {
            limpiarErrorCampo(motivoAjuste, errorMotivoAjuste);
        });

        formAjuste.addEventListener("submit", function (evento) {
            evento.preventDefault();

            limpiarErrorCampo(cantidadNueva, errorCantidadNueva);
            limpiarErrorCampo(motivoAjuste, errorMotivoAjuste);

            const cantidadValor = Number(cantidadNueva.value);
            const nota = motivoAjuste.value.trim();

            if (!Number.isInteger(cantidadValor) || cantidadValor < 0) {
                mostrarErrorCampo(
                    cantidadNueva,
                    errorCantidadNueva,
                    "Ingresa una cantidad entera igual o mayor que cero."
                );
                return;
            }

            if (cantidadValor > maximoAjuste) {
                mostrarErrorCampo(
                    cantidadNueva,
                    errorCantidadNueva,
                    `La capacidad disponible permite un máximo de ${maximoAjuste} unidades.`
                );
                return;
            }

            if (cantidadValor === cantidadActualAjuste) {
                mostrarErrorCampo(
                    cantidadNueva,
                    errorCantidadNueva,
                    "La cantidad nueva debe ser diferente de la cantidad actual."
                );
                return;
            }

            if (nota.length < 5 || nota.length > 250) {
                mostrarErrorCampo(
                    motivoAjuste,
                    errorMotivoAjuste,
                    "Escribe una nota de entre 5 y 250 caracteres."
                );
                return;
            }

            HTMLFormElement.prototype.submit.call(formAjuste);
        });

        document.getElementById("cerrarModal").addEventListener("click", function () {
            modal.classList.remove("open");
        });

        modal.addEventListener("click", function (evento) {
            if (evento.target === modal) {
                modal.classList.remove("open");
            }
        });

        document.querySelectorAll(".confirmar-restauracion").forEach(function (formulario) {
            formulario.addEventListener("submit", function (evento) {
                evento.preventDefault();

                Swal.fire({
                    title: "¿Restaurar cantidad original?",
                    text: "El producto volverá a la cantidad asignada originalmente por el administrador.",
                    icon: "question",
                    showCancelButton: true,
                    confirmButtonColor: "#23262b",
                    cancelButtonColor: "#6b7280",
                    confirmButtonText: "Sí, restaurar",
                    cancelButtonText: "Cancelar",
                    reverseButtons: true
                }).then(function (resultado) {
                    if (resultado.isConfirmed) {
                        HTMLFormElement.prototype.submit.call(formulario);
                    }
                });
            });
        });

        document.querySelectorAll(".confirmar-revision").forEach(function (formulario) {
            formulario.addEventListener("submit", function (evento) {
                evento.preventDefault();

                Swal.fire({
                    title: "¿Confirmar revisión de la carga?",
                    text: "Declara que verificaste los productos y cantidades que permanecen en el vehículo.",
                    icon: "question",
                    showCancelButton: true,
                    confirmButtonColor: "#23262b",
                    cancelButtonColor: "#6b7280",
                    confirmButtonText: "Sí, confirmar",
                    cancelButtonText: "Cancelar",
                    reverseButtons: true
                }).then(function (resultado) {
                    if (resultado.isConfirmed) {
                        HTMLFormElement.prototype.submit.call(formulario);
                    }
                });
            });
        });
    });


document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll(".js-progress-width").forEach(function (barra) {
    const valor = Math.max(0, Math.min(100, parseFloat(barra.dataset.progress || "0")));
    barra.style.width = valor + "%";
  });
});
