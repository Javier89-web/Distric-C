$(document).ready(function () {

        $.fn.dataTable.ext.search.push(
            function (settings, data, dataIndex) {

                if (settings.nTable.id !== "tablaVehiculos") {
                    return true;
                }

                const filtro =
                    $("#filtroEstado").val();

                const fila =
                    settings.aoData[dataIndex].nTr;

                const estado =
                    $(fila).data("estado");

                return filtro === "" ||
                    filtro === estado;
            }
        );

        const tabla =
            $("#tablaVehiculos").DataTable({

                pageLength: 10,

                lengthMenu: [
                    [5, 10, 25, 50, -1],
                    [5, 10, 25, 50, "Todos"]
                ],

                order: [
                    [0, "asc"]
                ],

                columnDefs: [
                    {
                        targets: 5,
                        orderable: false,
                        searchable: false
                    }
                ],

                dom:
                    "Brt" +
                    "<'table-bottom'<'table-length'l><'table-info'i><'table-page'p>>",

                buttons: [
                    {
                        extend: "csvHtml5",
                        text:
                            '<i class="bi bi-filetype-csv"></i> CSV',
                        title:
                            "Listado de vehículos",
                        filename:
                            "listado_vehiculos",
                        charset:
                            "utf-8",
                        bom:
                            true,
                        exportOptions: {
                            columns: [0, 1, 2, 3, 4]
                        }
                    },

                    {
                        extend: "excelHtml5",
                        text:
                            '<i class="bi bi-file-earmark-excel"></i> Excel',
                        title:
                            "Listado de vehículos",
                        filename:
                            "listado_vehiculos",
                        className:
                            "btn-excel",
                        exportOptions: {
                            columns: [0, 1, 2, 3, 4]
                        }
                    },

                    {
                        extend: "pdfHtml5",
                        text:
                            '<i class="bi bi-file-earmark-pdf"></i> PDF',
                        title:
                            "Listado de vehículos",
                        filename:
                            "listado_vehiculos",
                        className:
                            "btn-pdf",
                        orientation:
                            "landscape",
                        pageSize:
                            "A4",
                        exportOptions: {
                            columns: [0, 1, 2, 3, 4]
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
                            window.DistricPdfBranding?.apply(doc, "Distri C · Vehículos");
                        }
                    }
                ],

                language: {
                    emptyTable:
                        "No existen vehículos registrados.",
                    zeroRecords:
                        "No se encontraron vehículos.",
                    info:
                        "Mostrando _START_ a _END_ de _TOTAL_ vehículos",
                    infoEmpty:
                        "Mostrando 0 vehículos",
                    infoFiltered:
                        "(filtrado de _MAX_ registros)",
                    lengthMenu:
                        "Mostrar _MENU_ registros",
                    paginate: {
                        next:
                            "Siguiente",
                        previous:
                            "Anterior"
                    }
                }
            });

        tabla
            .buttons()
            .container()
            .appendTo(
                "#botonesExportacion"
            );

        $("#buscarVehiculo").on(
            "input",
            function () {
                tabla
                    .search(this.value)
                    .draw();
            }
        );

        $("#filtroEstado").on(
            "change",
            function () {
                tabla.draw();
            }
        );

        $(document).on(
            "click",
            ".abrir-asignacion",
            function () {

                $("#formAsignarVehiculo")
                    .attr(
                        "action",
                        $(this).data("url")
                    );

                $("#placaAsignacion")
                    .text(
                        $(this).data("placa")
                    );

                $("#usuarioAsignacion")
                    .val("");

                $("#errorUsuarioAsignacion")
                    .addClass("d-none");

                $("#usuarioAsignacion")
                    .removeClass("is-invalid");
            }
        );

        $("#usuarioAsignacion").on("change", function () {
            if (this.value) {
                $(this).removeClass("is-invalid");
                $("#errorUsuarioAsignacion").addClass("d-none");
            }
        });

        $("#formAsignarVehiculo").on("submit", function (evento) {
            evento.preventDefault();

            const usuarioSeleccionado = $("#usuarioAsignacion").val();

            if (!usuarioSeleccionado) {
                $("#usuarioAsignacion").addClass("is-invalid");
                $("#errorUsuarioAsignacion").removeClass("d-none");

                Swal.fire({
                    title: "Usuario pendiente",
                    text: "Selecciona el usuario al que se asignará el vehículo.",
                    icon: "warning",
                    confirmButtonColor: "#23262b",
                    confirmButtonText: "Entendido"
                });
                return;
            }

            this.submit();
        });

        $(document).on(
            "submit",
            ".form-confirmar",
            function (evento) {

                evento.preventDefault();

                const formulario = this;

                Swal.fire({
                    title:
                        $(formulario).data("titulo"),
                    text:
                        $(formulario).data("texto"),
                    icon:
                        "warning",
                    showCancelButton:
                        true,
                    confirmButtonColor:
                        "#d71920",
                    cancelButtonColor:
                        "#23262b",
                    confirmButtonText:
                        $(formulario).data("confirmar"),
                    cancelButtonText:
                        "Cancelar",
                    reverseButtons:
                        true
                }).then(function (resultado) {

                    if (resultado.isConfirmed) {
                        formulario.submit();
                    }
                });
            }
        );

    });
