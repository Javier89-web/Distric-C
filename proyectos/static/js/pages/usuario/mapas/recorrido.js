(function () {
    "use strict";

    const config = document.getElementById("tripTrackingConfig");
    if (!config) return;

    const state = {
        map: null,
        vehicleMarker: null,
        watchId: null,
        running: false,
        lastPosition: null,
        queueKey: `distric_gps_queue_${location.pathname}`,
    };

    const origin = JSON.parse(config.dataset.origen || "{}");
    const destination = JSON.parse(config.dataset.destino || "{}");
    const paths = JSON.parse(config.dataset.rutas || "[]");
    const arrivalRadius = Number(config.dataset.arrivalRadius || 120);

    const els = {
        start: document.getElementById("btnStartTracking"),
        pause: document.getElementById("btnPauseTracking"),
        finish: document.getElementById("btnFinishSegment"),
        center: document.getElementById("btnCentrarVehiculo"),
        status: document.getElementById("trackingStatusBadge"),
        accuracy: document.getElementById("gpsAccuracy"),
        realDistance: document.getElementById("realDistance"),
        realTime: document.getElementById("realTime"),
        distanceDestination: document.getElementById("distanceToDestination"),
        message: document.getElementById("trackingMessage"),
    };

    function csrfToken() {
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : "";
    }

    function setMessage(text, mode) {
        els.message.textContent = text;
        els.message.classList.remove("is-success", "is-warning", "is-error");
        if (mode) els.message.classList.add(`is-${mode}`);
    }

    function setStatus(status) {
        const labels = {
            PREPARADO: "Preparado",
            EN_RUTA: "En ruta",
            PAUSADO: "Pausado",
            COMPLETADO: "Completado",
        };
        const classes = {
            PREPARADO: "ready",
            EN_RUTA: "active",
            PAUSADO: "paused",
            COMPLETADO: "completed",
        };
        els.status.textContent = labels[status] || status;
        els.status.className = `tracking-status tracking-status-${classes[status] || "ready"}`;
    }

    async function postJson(url, payload) {
        const response = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken(),
                "X-Requested-With": "XMLHttpRequest",
            },
            body: JSON.stringify(payload || {}),
        });
        const data = await response.json();
        if (!response.ok || data.ok === false) throw new Error(data.mensaje || "No se completó la operación.");
        return data;
    }

    function saveQueuedPoint(payload) {
        let queue = [];
        try { queue = JSON.parse(localStorage.getItem(state.queueKey) || "[]"); } catch (_) { queue = []; }
        queue.push(payload);
        localStorage.setItem(state.queueKey, JSON.stringify(queue.slice(-150)));
    }

    async function flushQueue() {
        let queue = [];
        try { queue = JSON.parse(localStorage.getItem(state.queueKey) || "[]"); } catch (_) { return; }
        if (!queue.length || !navigator.onLine) return;
        const pending = [];
        for (const point of queue) {
            try { await postJson(config.dataset.locationUrl, point); }
            catch (_) { pending.push(point); }
        }
        if (pending.length) localStorage.setItem(state.queueKey, JSON.stringify(pending));
        else localStorage.removeItem(state.queueKey);
    }

    function updateVehicleMarker(position) {
        const coords = { lat: position.latitude, lng: position.longitude };
        if (!state.vehicleMarker) {
            state.vehicleMarker = new google.maps.Marker({
                map: state.map,
                position: coords,
                title: "Vehículo en movimiento",
                icon: {
                    path: google.maps.SymbolPath.FORWARD_CLOSED_ARROW,
                    scale: 7,
                    rotation: Number.isFinite(position.heading) ? position.heading : 0,
                    fillColor: "#2563eb",
                    fillOpacity: 1,
                    strokeColor: "#ffffff",
                    strokeWeight: 3,
                },
                zIndex: 20,
            });
        } else {
            state.vehicleMarker.setPosition(coords);
            const icon = state.vehicleMarker.getIcon();
            if (icon && Number.isFinite(position.heading)) {
                icon.rotation = position.heading;
                state.vehicleMarker.setIcon(icon);
            }
        }
        state.lastPosition = coords;
    }

    function updateMetrics(data, coords) {
        if (data.distancia_real_km !== undefined) els.realDistance.textContent = `${Number(data.distancia_real_km).toFixed(3)} km`;
        if (data.tiempo_real_min !== undefined) els.realTime.textContent = `${Number(data.tiempo_real_min).toFixed(1)} min`;
        if (data.distancia_destino_m !== undefined) {
            const meters = Number(data.distancia_destino_m);
            els.distanceDestination.textContent = meters >= 1000 ? `${(meters / 1000).toFixed(2)} km` : `${meters.toFixed(0)} m`;
            if (data.cerca_destino) setMessage("Ya te encuentras dentro del radio de llegada. Puedes finalizar el tramo.", "success");
            else setMessage(`Seguimiento activo. Faltan aproximadamente ${meters.toFixed(0)} m hasta el destino.`, "");
        }
        if (coords) updateVehicleMarker(coords);
    }

    async function sendPosition(position) {
        const payload = {
            latitud: position.coords.latitude,
            longitud: position.coords.longitude,
            precision: position.coords.accuracy,
            velocidad: Number.isFinite(position.coords.speed) ? position.coords.speed : null,
            rumbo: Number.isFinite(position.coords.heading) ? position.coords.heading : null,
            fecha_dispositivo: new Date(position.timestamp).toISOString(),
        };
        const coords = {
            latitude: payload.latitud,
            longitude: payload.longitud,
            accuracy: payload.precision,
            heading: payload.rumbo,
        };
        els.accuracy.textContent = `Precisión ${Math.round(payload.precision || 0)} m`;
        updateVehicleMarker(coords);

        try {
            const data = await postJson(config.dataset.locationUrl, payload);
            updateMetrics(data, coords);
        } catch (error) {
            saveQueuedPoint(payload);
            setMessage("Sin conexión: el punto quedó guardado en el dispositivo y se enviará al recuperar internet.", "warning");
        }
    }

    function geolocationError(error) {
        state.running = false;
        els.start.disabled = false;
        els.pause.disabled = true;
        const messages = {
            1: "Debes permitir la ubicación para registrar el recorrido.",
            2: "El dispositivo no logró determinar la ubicación.",
            3: "El GPS tardó demasiado en responder.",
        };
        setMessage(messages[error.code] || "No se pudo iniciar el GPS.", "error");
        Swal.fire({
            title: "GPS no disponible",
            text: messages[error.code] || "Comprueba la ubicación del dispositivo.",
            icon: "error",
            confirmButtonColor: "#23262b",
        });
    }

    function startWatch() {
        if (!navigator.geolocation) {
            geolocationError({ code: 0 });
            return;
        }
        if (state.watchId !== null) return;
        state.watchId = navigator.geolocation.watchPosition(
            sendPosition,
            geolocationError,
            { enableHighAccuracy: true, maximumAge: 2000, timeout: 20000 }
        );
    }

    function stopWatch() {
        if (state.watchId !== null) {
            navigator.geolocation.clearWatch(state.watchId);
            state.watchId = null;
        }
    }

    async function startTracking() {
        try {
            els.start.disabled = true;
            const data = await postJson(config.dataset.startUrl, {});
            state.running = true;
            setStatus(data.estado || "EN_RUTA");
            els.pause.disabled = false;
            els.start.innerHTML = '<i class="bi bi-broadcast"></i> Seguimiento activo';
            setMessage("GPS activo. El marcador azul se actualizará con el movimiento del dispositivo.", "success");
            localStorage.setItem(`distric_tracking_${location.pathname}`, "1");
            startWatch();
            flushQueue();
        } catch (error) {
            els.start.disabled = false;
            setMessage(error.message, "error");
        }
    }

    async function pauseTracking() {
        try {
            els.pause.disabled = true;
            const data = await postJson(config.dataset.pauseUrl, {});
            stopWatch();
            state.running = false;
            localStorage.removeItem(`distric_tracking_${location.pathname}`);
            setStatus(data.estado || "PAUSADO");
            els.start.disabled = false;
            els.start.innerHTML = '<i class="bi bi-play-circle"></i> Reanudar seguimiento';
            setMessage("Seguimiento pausado. Puedes reanudarlo sin perder el tramo.", "warning");
        } catch (error) {
            els.pause.disabled = false;
            setMessage(error.message, "error");
        }
    }

    function confirmFinish(event) {
        event.preventDefault();
        const distanceText = els.distanceDestination.textContent;
        Swal.fire({
            title: "¿Finalizar este tramo?",
            text: `Distancia mostrada al destino: ${distanceText}. A continuación registrarás los productos entregados.`,
            icon: "question",
            showCancelButton: true,
            confirmButtonText: "Continuar a la entrega",
            cancelButtonText: "Seguir en ruta",
            confirmButtonColor: "#d71920",
            cancelButtonColor: "#23262b",
            reverseButtons: true,
        }).then(function (result) {
            if (result.isConfirmed) {
                stopWatch();
                localStorage.removeItem(`distric_tracking_${location.pathname}`);
                window.location.href = config.dataset.finishUrl;
            }
        });
    }

    window.initDistricTrackingMap = function () {
        const originPosition = { lat: Number(origin.latitud), lng: Number(origin.longitud) };
        const destinationPosition = { lat: Number(destination.latitud), lng: Number(destination.longitud) };
        state.map = new google.maps.Map(document.getElementById("mapa"), {
            center: originPosition,
            zoom: 16,
            mapTypeControl: true,
            streetViewControl: true,
            fullscreenControl: true,
            gestureHandling: "greedy",
        });

        const rawPath = (paths[0] || []).map(function (point) {
            return Array.isArray(point)
                ? { lat: Number(point[0]), lng: Number(point[1]) }
                : { lat: Number(point.lat), lng: Number(point.lng) };
        });
        const routeColor = config.dataset.colorRuta || "#2563eb";

        // Doble trazo visual: borde claro + color de la alternativa.
        // No modifica la geometría ni el cálculo; solo hace más legible el recorrido.
        new google.maps.Polyline({
            map: state.map,
            path: rawPath,
            strokeColor: "#ffffff",
            strokeOpacity: 0.95,
            strokeWeight: 11,
            zIndex: 9,
        });
        new google.maps.Polyline({
            map: state.map,
            path: rawPath,
            strokeColor: routeColor,
            strokeOpacity: 1,
            strokeWeight: 7,
            zIndex: 10,
            icons: [{
                icon: {
                    path: google.maps.SymbolPath.FORWARD_CLOSED_ARROW,
                    scale: 2,
                    fillColor: routeColor,
                    fillOpacity: 1,
                    strokeColor: "#ffffff",
                    strokeOpacity: 1,
                    strokeWeight: 1,
                },
                offset: "8%",
                repeat: "95px",
            }],
        });
        new google.maps.Marker({
            map: state.map,
            position: destinationPosition,
            title: destination.nombre || "Destino",
            icon: {
                path: google.maps.SymbolPath.CIRCLE,
                scale: 10,
                fillColor: "#d71920",
                fillOpacity: 1,
                strokeColor: "#ffffff",
                strokeWeight: 4,
            },
        });
        updateVehicleMarker({ latitude: originPosition.lat, longitude: originPosition.lng, heading: 0 });
        const bounds = new google.maps.LatLngBounds();
        (rawPath.length ? rawPath : [originPosition, destinationPosition]).forEach(function (point) { bounds.extend(point); });
        state.map.fitBounds(bounds, 45);

        const initial = config.dataset.initialStatus;
        setStatus(initial);
        if (initial === "EN_RUTA" || localStorage.getItem(`distric_tracking_${location.pathname}`) === "1") {
            startTracking();
        } else if (initial === "PAUSADO") {
            els.start.innerHTML = '<i class="bi bi-play-circle"></i> Reanudar seguimiento';
        }
    };

    els.start.addEventListener("click", startTracking);
    els.pause.addEventListener("click", pauseTracking);
    els.finish.addEventListener("click", confirmFinish);
    els.center.addEventListener("click", function () {
        if (state.lastPosition) {
            state.map.panTo(state.lastPosition);
            state.map.setZoom(18);
        }
    });
    window.addEventListener("online", flushQueue);
    window.addEventListener("beforeunload", stopWatch);
    document.addEventListener("visibilitychange", function () {
        if (!document.hidden && state.running && state.watchId === null) startWatch();
    });

    const script = document.createElement("script");
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(config.dataset.googleMapsKey)}&v=weekly&callback=initDistricTrackingMap`;
    script.async = true;
    script.defer = true;
    document.head.appendChild(script);
})();
