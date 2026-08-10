$(document).ready(function () {

        /* FILTROS DE ROL Y ESTADO */
        $.fn.dataTable.ext.search.push(
            function (settings, data, dataIndex) {

                if (settings.nTable.id !== "tablaUsuarios") {
                    return true;
                }

                const rolSeleccionado =
                    $("#filtroRol").val();

                const estadoSeleccionado =
                    $("#filtroEstado").val();

                const fila =
                    settings.aoData[dataIndex].nTr;

                const rolFila =
                    $(fila).data("rol");

                const estadoFila =
                    $(fila).data("estado");

                const coincideRol =
                    rolSeleccionado === "" ||
                    rolSeleccionado === rolFila;

                const coincideEstado =
                    estadoSeleccionado === "" ||
                    estadoSeleccionado === estadoFila;

                return coincideRol && coincideEstado;
            }
        );

        const columnaAcciones = parseInt(
            document.getElementById("tablaUsuarios").dataset.columnaAcciones || "-1",
            10
        );

        const columnasExportar = [
            0,
            1,
            2,
            3,
            6,
            7
        ];

        const configuracionColumnas = [];

        if (columnaAcciones >= 0) {
            configuracionColumnas.push({
                targets: columnaAcciones,
                orderable: false,
                searchable: false
            });
        }

        /* DATATABLE */
        const tabla =
            $("#tablaUsuarios").DataTable({

                pageLength: 10,

                lengthMenu: [
                    [5, 10, 25, 50, -1],
                    [5, 10, 25, 50, "Todos"]
                ],

                order: [
                    [0, "asc"]
                ],

                columnDefs:
                    configuracionColumnas,

                dom:
                    "Brt" +
                    "<'table-bottom'<'table-length'l><'table-info'i><'table-page'p>>",

                buttons: [
                    {
                        extend:
                            "csvHtml5",

                        text:
                            '<i class="bi bi-filetype-csv"></i> CSV',

                        title:
                            "Listado de usuarios",

                        filename:
                            "listado_usuarios",

                        charset:
                            "utf-8",

                        bom:
                            true,

                        exportOptions: {
                            columns:
                                columnasExportar
                        }
                    },

                    {
                        extend:
                            "excelHtml5",

                        text:
                            '<i class="bi bi-file-earmark-excel"></i> Excel',

                        title:
                            "Listado de usuarios",

                        filename:
                            "listado_usuarios",

                        className:
                            "btn-excel",

                        exportOptions: {
                            columns:
                                columnasExportar
                        }
                    },

                    {
                        extend:
                            "pdfHtml5",

                        text:
                            '<i class="bi bi-file-earmark-pdf"></i> PDF',

                        title:
                            "Listado de usuarios",

                        filename:
                            "listado_usuarios",

                        className:
                            "btn-pdf",

                        orientation:
                            "landscape",

                        pageSize:
                            "A4",

                        exportOptions: {
                            columns:
                                columnasExportar
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
                            window.DistricPdfBranding?.apply(doc, "Distri C · Usuarios");
                        }
                    }
                ],

                language: {
                    emptyTable:
                        "No existen usuarios registrados.",

                    zeroRecords:
                        "No se encontraron usuarios.",

                    info:
                        "Mostrando _START_ a _END_ de _TOTAL_ usuarios",

                    infoEmpty:
                        "Mostrando 0 usuarios",

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

        /* UBICAR BOTONES */
        tabla
            .buttons()
            .container()
            .appendTo(
                "#botonesExportacion"
            );

        /* BÚSQUEDA */
        $("#buscarUsuario").on(
            "input",
            function () {

                tabla
                    .search(this.value)
                    .draw();
            }
        );

        /* FILTRO POR ROL */
        $("#filtroRol").on(
            "change",
            function () {

                tabla.draw();
            }
        );

        /* FILTRO POR ESTADO */
        $("#filtroEstado").on(
            "change",
            function () {

                tabla.draw();
            }
        );

        /* CONFIRMAR ACTIVACIÓN O INACTIVACIÓN */
        $(document).on(
            "click",
            ".confirmar-estado",
            function (evento) {

                evento.preventDefault();

                const enlace =
                    this.href;

                const boton =
                    $(this);

                Swal.fire({
                    title:
                        boton.data("titulo"),

                    text:
                        boton.data("texto"),

                    icon:
                        "warning",

                    showCancelButton:
                        true,

                    confirmButtonColor:
                        "#d71920",

                    cancelButtonColor:
                        "#23262b",

                    confirmButtonText:
                        boton.data("confirmar"),

                    cancelButtonText:
                        "Cancelar",

                    reverseButtons:
                        true

                }).then(function (resultado) {

                    if (resultado.isConfirmed) {
                        window.location.href = enlace;
                    }
                });
            }
        );

    

        $(document).on("submit", ".form-eliminar-usuario", function (evento) {
            evento.preventDefault();
            const form = this;
            const nombre = form.dataset.usuario || "este usuario";
            Swal.fire({
                title: "¿Eliminar usuario?",
                text: `Se eliminará definitivamente a ${nombre}.`,
                icon: "warning",
                showCancelButton: true,
                confirmButtonColor: "#d71920",
                cancelButtonColor: "#23262b",
                confirmButtonText: "Sí, eliminar",
                cancelButtonText: "Cancelar",
                reverseButtons: true
            }).then(function (resultado) {
                if (resultado.isConfirmed) form.submit();
            });
        });
});
