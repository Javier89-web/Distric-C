document.addEventListener("DOMContentLoaded", function () {
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
                order: configuracion.orden,
                autoWidth: false,
                responsive: false,
                dom: "Brt<'carga-table-bottom'<'carga-table-length'l><'carga-table-info'i><'carga-table-page'p>>",
                buttons: (function () {
                    const botones = [
                        {
                            extend: "csvHtml5",
                            text: '<i class="bi bi-filetype-csv"></i> CSV',
                            title: configuracion.titulo,
                            filename: configuracion.archivo,
                            charset: "utf-8",
                            bom: true,
                            exportOptions: {
                                columns: configuracion.columnasExportar
                            }
                        },
                        {
                            extend: "excelHtml5",
                            text: '<i class="bi bi-file-earmark-excel"></i> Excel',
                            title: configuracion.titulo,
                            filename: configuracion.archivo,
                            className: "btn-excel",
                            exportOptions: {
                                columns: configuracion.columnasExportar
                            }
                        }
                    ];

                    if (configuracion.pdfUrl) {
                        botones.push({
                            text: '<i class="bi bi-file-earmark-pdf"></i> PDF',
                            className: "btn-pdf",
                            action: function () {
                                window.location.href = configuracion.pdfUrl;
                            }
                        });
                    } else {
                        botones.push({
                            extend: "pdfHtml5",
                            text: '<i class="bi bi-file-earmark-pdf"></i> PDF',
                            title: configuracion.titulo,
                            filename: configuracion.archivo,
                            className: "btn-pdf",
                            orientation: "landscape",
                            pageSize: "A4",
                            exportOptions: {
                                columns: configuracion.columnasExportar
                            },
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
                                window.DistricPdfBranding?.apply(doc, "Distri C · Plan de carga");
                            }
                        });
                    }

                    return botones;
                })(),
                language: {
                    emptyTable: "No existen registros.",
                    zeroRecords: "No se encontraron coincidencias.",
                    info: "Mostrando _START_ a _END_ de _TOTAL_ registros",
                    infoEmpty: "Mostrando 0 registros",
                    infoFiltered: "(filtrado de _MAX_ registros)",
                    lengthMenu: "Mostrar _MENU_ registros",
                    paginate: {
                        next: "Siguiente",
                        previous: "Anterior"
                    }
                },
                initComplete: function () {
                    const api = this.api();
                    api.columns.adjust();
                }
            });

            tabla.buttons().container().appendTo(configuracion.botones);

            $(configuracion.buscador).on("input", function () {
                tabla.search(this.value).draw();
            });
        }

        inicializarTabla({
            selector: "#tablaProductosAdmin",
            buscador: "#buscarProductosAdmin",
            botones: "#botonesProductosAdmin",
            pdfUrl: document.getElementById("botonesProductosAdmin")?.dataset.pdfUrl || "",
            titulo: "Productos asignados al plan de carga",
            archivo: "productos_plan_carga",
            columnasExportar: [0, 1, 2, 3, 4, 5, 6],
            orden: [[0, "asc"]]
        });

        inicializarTabla({
            selector: "#tablaAjustesAdmin",
            buscador: "#buscarAjustesAdmin",
            botones: "#botonesAjustesAdmin",
            titulo: "Historial de ajustes del conductor",
            archivo: "historial_ajustes_conductor",
            columnasExportar: [0, 1, 2, 3, 4],
            orden: [[0, "desc"]]
        });

        document.querySelectorAll(".confirmar-accion").forEach(function (formulario) {
            formulario.addEventListener("submit", function (evento) {
                evento.preventDefault();
                if (formulario.dataset.confirmando === "1" || window.DistricSubmitGuard?.isLocked(formulario)) {
                    return;
                }

                formulario.dataset.confirmando = "1";
                Swal.fire({
                    title: formulario.dataset.titulo,
                    text: formulario.dataset.texto,
                    icon: "warning",
                    showCancelButton: true,
                    confirmButtonColor: "#d71920",
                    cancelButtonColor: "#23262b",
                    confirmButtonText: formulario.dataset.confirmar,
                    cancelButtonText: "Cancelar",
                    reverseButtons: true
                }).then(function (resultado) {
                    if (resultado.isConfirmed) {
                        window.DistricSubmitGuard.submit(
                            formulario,
                            formulario.dataset.loadingText || "Procesando…",
                            evento.submitter || null
                        );
                    } else {
                        formulario.dataset.confirmando = "0";
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
