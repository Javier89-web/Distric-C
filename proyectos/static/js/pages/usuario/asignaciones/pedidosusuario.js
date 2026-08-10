document.addEventListener('DOMContentLoaded', function () {
    const calendarEl = document.getElementById('calendar');

    const calendar = new FullCalendar.Calendar(calendarEl, {
      initialView: 'dayGridMonth',
      locale: 'es',
      height: 650,
      events: calendarEl.dataset.eventsUrl,

      //  Cambia 17:06 -> 05:06 PM (12h)
      eventTimeFormat: {
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
      },

      //para timeGridWeek/timeGridDay (columna de horas)
      slotLabelFormat: {
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
      },
      buttonText: { today: 'Hoy', month: 'Mes', week: 'Semana', day: 'Día' }
    });

    calendar.render();
  });

  // DATATABLES
  $(document).ready(function () {
    $('#tbl_asignados').DataTable({
      dom: 'Bfrtip',
      buttons: [
        { extend: 'copy', text: 'Copiar' },
        { extend: 'excel', text: 'Excel' },
        { extend: 'csv', text: 'CSV' },
        { extend: 'pdf', text: 'PDF', orientation: 'landscape', pageSize: 'A4', customize: function (doc) { window.DistricPdfBranding?.apply(doc, 'Distri C · Pedidos asignados'); } }
      ],
      language: {
        url: "//cdn.datatables.net/plug-ins/1.13.6/i18n/es-ES.json",
        search: "Buscar:",
        lengthMenu: "Mostrar _MENU_ registros",
        info: "Mostrando _START_ a _END_ de _TOTAL_ registros",
        infoEmpty: "Mostrando 0 a 0 de 0 registros",
        infoFiltered: "(filtrado de _MAX_ registros totales)",
        paginate: { previous: "Anterior", next: "Siguiente" },
        zeroRecords: "No se encontraron resultados"
      }
    });
  });
