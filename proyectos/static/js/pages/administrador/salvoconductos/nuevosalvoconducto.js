$(document).ready(function () {
    $('#tbl_viajes').DataTable({
      dom: 'Bfrtip',
      buttons: [
        { extend: 'copy', text: 'Copiar' },
        { extend: 'excel', text: 'Excel' },
        { extend: 'csv', text: 'CSV' },
        { extend: 'pdf', text: 'PDF', orientation: 'landscape', pageSize: 'A4', customize: function (doc) { window.DistricPdfBranding?.apply(doc, 'Distri C · Viajes para salvoconducto'); } }
      ],
      language: {
        url: "//cdn.datatables.net/plug-ins/1.13.6/i18n/es-ES.json"
      }
    });
  });
