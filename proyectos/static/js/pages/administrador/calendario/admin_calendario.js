document.addEventListener('DOMContentLoaded', function () {
    const calendarEl = document.getElementById('calendar');

    const inicioFecha = document.getElementById('inicio_fecha');
    const inicioHora = document.getElementById('inicio_hora');
    const finFecha = document.getElementById('fin_fecha');
    const finHora = document.getElementById('fin_hora');

    let primerClickDate = null;

    function pad(n) { return String(n).padStart(2, '0'); }
    function formatDate(d) {
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    }
    function addDays(dateObj, days) {
      const d = new Date(dateObj);
      d.setDate(d.getDate() + days);
      return d;
    }

    // defaults de hora (ajústalos a tu gusto)
    if (!inicioHora.value) inicioHora.value = "08:00";
    if (!finHora.value) finHora.value = "18:00";

    const calendar = new FullCalendar.Calendar(calendarEl, {
      initialView: 'dayGridMonth',
      locale: 'es',
      height: 650,
      selectable: true,
      events: '/panel/calendario/eventos/',

      buttonText: {
        today: 'Hoy',
        month: 'Mes',
        week: 'Semana',
        day: 'Día'
      },


      dateClick: function (info) {
        const clicked = new Date(info.date);

        // 1er click -> INICIO
        if (!primerClickDate) {
          primerClickDate = clicked;

          inicioFecha.value = formatDate(clicked);
          finFecha.value = "";
          // finHora.value = "18:00"; // si quieres resetear

          calendar.unselect();
          calendar.select(clicked, addDays(clicked, 1));
          return;
        }

        // 2do click -> FIN
        let start = new Date(primerClickDate);
        let end = new Date(clicked);

        if (end < start) {
          const tmp = start; start = end; end = tmp;
        }

        inicioFecha.value = formatDate(start);
        finFecha.value = formatDate(end);

        calendar.unselect();
        calendar.select(start, addDays(end, 1));

        primerClickDate = null; // reset
      }
    });

    calendar.render();
  });
