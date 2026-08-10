$(document).ready(function () {
    $('#tabla_facturas').DataTable({
      dom: 'Bfrtip',
      buttons: [
        { extend: 'copy', text: 'Copiar' },
        { extend: 'excel', text: 'Excel' },
        { extend: 'csv', text: 'CSV' },
        { extend: 'pdf', text: 'PDF', orientation: 'landscape', pageSize: 'A4', customize: function (doc) { window.DistricPdfBranding?.apply(doc, 'Distri C · Facturas'); } }
      ],
      language: {
        url: "//cdn.datatables.net/plug-ins/1.13.6/i18n/es-ES.json",
        search: "Buscar:",
        lengthMenu: "Mostrar _MENU_ registros",
        info: "Mostrando _START_ a _END_ de _TOTAL_ registros",
        infoEmpty: "Mostrando 0 a 0 de 0 registros",
        infoFiltered: "(filtrado de _MAX_ registros totales)",
        paginate: {
          previous: "Anterior",
          next: "Siguiente"
        },
        zeroRecords: "No se encontraron resultados"
      }
    });
  });
