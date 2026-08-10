$(document).ready(function () {
        $.fn.dataTable.ext.search.push(function (settings, data, dataIndex) {
            if (settings.nTable.id !== "tablaProductos") {
                return true;
            }

            const estadoSeleccionado = $("#filtroEstado").val();
            const fila = settings.aoData[dataIndex].nTr;
            const estadoFila = $(fila).data("estado");

            return estadoSeleccionado === "" || estadoSeleccionado === estadoFila;
        });

        const tabla = $("#tablaProductos").DataTable({
            pageLength: 10,
            lengthMenu: [[5, 10, 25, 50, -1], [5, 10, 25, 50, "Todos"]],
            order: [[0, "asc"]],
            columnDefs: [
                {
                    targets: 7,
                    orderable: false,
                    searchable: false
                }
            ],
            dom: "Brt" + "<'table-bottom'<'table-length'l><'table-info'i><'table-page'p>>",
            buttons: [
                {
                    extend: "csvHtml5",
                    text: '<i class="bi bi-filetype-csv"></i> CSV',
                    title: "Catálogo de productos",
                    filename: "catalogo_productos",
                    charset: "utf-8",
                    bom: true,
                    exportOptions: { columns: [0, 1, 2, 3, 4, 5, 6] }
                },
                {
                    extend: "excelHtml5",
                    text: '<i class="bi bi-file-earmark-excel"></i> Excel',
                    title: "Catálogo de productos",
                    filename: "catalogo_productos",
                    className: "btn-excel",
                    exportOptions: { columns: [0, 1, 2, 3, 4, 5, 6] }
                },
                {
                    extend: "pdfHtml5",
                    text: '<i class="bi bi-file-earmark-pdf"></i> PDF',
                    title: "Catálogo de productos",
                    filename: "catalogo_productos",
                    className: "btn-pdf",
                    orientation: "landscape",
                    pageSize: "A4",
                    exportOptions: { columns: [0, 1, 2, 3, 4, 5, 6] },
                    customize: function (doc) {
                        doc.defaultStyle.fontSize = 9;
                        doc.styles.tableHeader = {
                            bold: true,
                            color: "#ffffff",
                            fillColor: "#23262b",
                            fontSize: 9
                        };
                        window.DistricPdfBranding?.apply(doc, "Distri C · Catálogo de productos");
                    }
                }
            ],
            language: {
                emptyTable: "No existen productos registrados.",
                zeroRecords: "No se encontraron productos.",
                info: "Mostrando _START_ a _END_ de _TOTAL_ productos",
                infoEmpty: "Mostrando 0 productos",
                infoFiltered: "(filtrado de _MAX_ registros)",
                lengthMenu: "Mostrar _MENU_ registros",
                paginate: {
                    next: "Siguiente",
                    previous: "Anterior"
                }
            }
        });

        tabla.buttons().container().appendTo("#botonesExportacionProductos");

        $("#buscarProducto").on("input", function () {
            tabla.search(this.value).draw();
        });

        $("#filtroEstado").on("change", function () {
            tabla.draw();
        });

        $(document).on("submit", ".form-estado-producto", function (evento) {
            evento.preventDefault();

            const formulario = this;
            const producto = formulario.dataset.producto;
            const accion = formulario.dataset.accion;

            Swal.fire({
                title: `¿${accion.charAt(0).toUpperCase() + accion.slice(1)} producto?`,
                text: `${producto} permanecerá en el historial y solo cambiará su disponibilidad.`,
                icon: "warning",
                showCancelButton: true,
                confirmButtonColor: "#d71920",
                cancelButtonColor: "#23262b",
                confirmButtonText: `Sí, ${accion}`,
                cancelButtonText: "Cancelar",
                reverseButtons: true
            }).then(function (resultado) {
                if (resultado.isConfirmed) {
                    formulario.submit();
                }
            });
        });
    

        $(document).on("submit", ".form-eliminar-producto", function (evento) {
            evento.preventDefault();
            const form = this;
            const nombre = form.dataset.producto || "este producto";
            Swal.fire({
                title: "¿Eliminar producto?",
                text: `Se eliminará ${nombre}. Si ya fue usado en una carga, el sistema conservará el historial y no permitirá borrarlo.`,
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
