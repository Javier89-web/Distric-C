(function () {
    "use strict";

    const config = document.getElementById("routeOptionsConfig");
    if (!config) return;

    let map = null;
    let polylines = [];
    let activeIndex = 1;
    const routes = JSON.parse(config.dataset.rutas || "[]");
    const origin = JSON.parse(config.dataset.origen || "{}");
    const destination = JSON.parse(config.dataset.destino || "{}");
    const selectorButtons = Array.from(document.querySelectorAll(".route-selector-item"));
    const detailCards = Array.from(document.querySelectorAll(".route-detail"));
    const startForms = Array.from(document.querySelectorAll(".start-route-form"));

    function lineColor(index) {
        const indicator = document.querySelector(`.route-selector-item[data-route-index="${index}"] .route-color-indicator`);
        return indicator ? indicator.dataset.routeColor : "#d71920";
    }

    function pathFor(index) {
        const raw = routes[index - 1] || [];
        return raw.map(function (point) {
            if (Array.isArray(point)) return { lat: Number(point[0]), lng: Number(point[1]) };
            return { lat: Number(point.lat || point.latitude), lng: Number(point.lng || point.longitude) };
        }).filter(function (point) { return Number.isFinite(point.lat) && Number.isFinite(point.lng); });
    }

    function drawAllRoutes() {
        polylines.forEach(function (line) { line.setMap(null); });
        polylines = routes.map(function (_, routeIndex) {
            const index = routeIndex + 1;
            const line = new google.maps.Polyline({
                map: map,
                path: pathFor(index),
                strokeColor: lineColor(index),
                strokeOpacity: index === activeIndex ? 1 : 0.32,
                strokeWeight: index === activeIndex ? 7 : 4,
                zIndex: index === activeIndex ? 20 : 5,
                clickable: true,
            });
            line.addListener("click", function () { selectRoute(index); });
            return line;
        });
    }

    function fitRoute(index) {
        const path = pathFor(index);
        if (!path.length) return;
        const bounds = new google.maps.LatLngBounds();
        path.forEach(function (point) { bounds.extend(point); });
        map.fitBounds(bounds, 45);
    }

    function selectRoute(index) {
        activeIndex = Number(index);
        selectorButtons.forEach(function (button) {
            button.classList.toggle("is-active", Number(button.dataset.routeIndex) === activeIndex);
        });
        detailCards.forEach(function (detail) {
            detail.classList.toggle("is-active", Number(detail.dataset.routeDetail) === activeIndex);
        });
        startForms.forEach(function (form) {
            form.hidden = Number(form.dataset.startForm) !== activeIndex;
        });
        polylines.forEach(function (line, lineIndex) {
            const active = lineIndex + 1 === activeIndex;
            line.setOptions({
                strokeOpacity: active ? 1 : 0.26,
                strokeWeight: active ? 7 : 4,
                zIndex: active ? 20 : 5,
            });
        });
        fitRoute(activeIndex);
    }

    function confirmStart(form) {
        form.addEventListener("submit", function (event) {
            if (!window.Swal) return;
            event.preventDefault();
            if (form.dataset.confirming === "1" || window.DistricSubmitGuard?.isLocked(form)) return;
            form.dataset.confirming = "1";
            Swal.fire({
                title: `¿Iniciar por la ruta ${activeIndex}?`,
                text: "Se abrirá el seguimiento GPS del tramo. La carga y la predicción quedarán asociadas a esta alternativa.",
                icon: "question",
                showCancelButton: true,
                confirmButtonText: "Iniciar viaje",
                cancelButtonText: "Seguir comparando",
                confirmButtonColor: "#d71920",
                cancelButtonColor: "#23262b",
                reverseButtons: true,
            }).then(function (result) {
                if (result.isConfirmed) {
                    window.DistricSubmitGuard.submit(form, "Iniciando viaje…", event.submitter || null);
                } else {
                    form.dataset.confirming = "0";
                }
            });
        });
    }

    window.initDistricRouteOptionsMap = function () {
        const originPosition = { lat: Number(origin.latitud), lng: Number(origin.longitud) };
        const destinationPosition = { lat: Number(destination.latitud), lng: Number(destination.longitud) };
        map = new google.maps.Map(document.getElementById("mapa"), {
            center: originPosition,
            zoom: 14,
            mapTypeControl: true,
            streetViewControl: true,
            fullscreenControl: true,
            gestureHandling: "greedy",
        });

        new google.maps.Marker({
            map: map,
            position: originPosition,
            title: origin.nombre || "Inicio",
            icon: {
                path: google.maps.SymbolPath.CIRCLE,
                scale: 9,
                fillColor: "#2563eb",
                fillOpacity: 1,
                strokeColor: "#ffffff",
                strokeWeight: 4,
            },
        });
        new google.maps.Marker({
            map: map,
            position: destinationPosition,
            title: destination.nombre || "Destino",
            icon: {
                path: google.maps.SymbolPath.CIRCLE,
                scale: 9,
                fillColor: "#d71920",
                fillOpacity: 1,
                strokeColor: "#ffffff",
                strokeWeight: 4,
            },
        });
        drawAllRoutes();
        selectRoute(activeIndex);
    };

    selectorButtons.forEach(function (button) {
        const indicator = button.querySelector(".route-color-indicator");
        if (indicator) indicator.style.backgroundColor = indicator.dataset.routeColor;
        button.addEventListener("click", function () { selectRoute(button.dataset.routeIndex); });
    });
    startForms.forEach(confirmStart);

    const routeSearch = document.getElementById("routeSelectorSearch");
    if (routeSearch) {
        routeSearch.addEventListener("input", function () {
            const term = routeSearch.value.toLowerCase().trim();
            selectorButtons.forEach(function (button) {
                button.hidden = Boolean(term) && !button.textContent.toLowerCase().includes(term);
            });
        });
    }

    const cancelForm = document.getElementById("cancelRouteForm");
    if (cancelForm) {
        cancelForm.addEventListener("submit", function (event) {
            if (!window.Swal) return;
            event.preventDefault();
            if (cancelForm.dataset.confirming === "1" || window.DistricSubmitGuard?.isLocked(cancelForm)) return;
            cancelForm.dataset.confirming = "1";
            Swal.fire({
                title: "¿Cambiar el origen o destino?",
                text: "Las alternativas calculadas para este tramo se descartarán.",
                icon: "warning",
                showCancelButton: true,
                confirmButtonText: "Sí, cambiar puntos",
                cancelButtonText: "Continuar aquí",
                confirmButtonColor: "#23262b",
                cancelButtonColor: "#6b7280",
                reverseButtons: true,
            }).then(function (result) {
                if (result.isConfirmed) {
                    window.DistricSubmitGuard.submit(cancelForm, "Regresando…", event.submitter || null);
                } else {
                    cancelForm.dataset.confirming = "0";
                }
            });
        });
    }

    const script = document.createElement("script");
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(config.dataset.googleMapsKey)}&v=weekly&callback=initDistricRouteOptionsMap`;
    script.async = true;
    script.defer = true;
    document.head.appendChild(script);
})();
