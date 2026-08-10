(function () {
    "use strict";

    const config = document.getElementById("selectorRutaConfig");
    if (!config) return;

    const adminMode = config.dataset.adminMode === "true";

    const state = {
        map: null,
        geocoder: null,
        infoWindow: null,
        originMarker: null,
        destinationMarker: null,
        origin: null,
        destination: null,
        selectingDestination: false,
        navigating: false,
        searchTimer: null,
        searchController: null,
    };

    const els = {
        map: document.getElementById("map"),
        input: document.getElementById("buscarDestinoTexto"),
        results: document.getElementById("resultadosDestino"),
        btnSearch: document.getElementById("btnBuscarDestino"),
        btnClear: document.getElementById("limpiarBusquedaDestino"),
        btnMyLocation: document.getElementById("btnMiUbicacion"),
        btnSelectDestination: document.getElementById("btnSeleccionarDestino"),
        btnContinue: document.getElementById("btnContinuarDestino"),
        notice: document.getElementById("mapModeNotice"),
        status: document.getElementById("estadoBusquedaDestino"),
        error: document.getElementById("routeSearchError"),
        originSummary: document.getElementById("origenResumen"),
        originCoords: document.getElementById("origenCoordenadas"),
        destinationSummary: document.getElementById("destinoResumen"),
        destinationCoords: document.getElementById("destinoCoordenadas"),
    };

    function number(value) {
        const parsed = Number.parseFloat(value);
        return Number.isFinite(parsed) ? parsed : null;
    }

    function escapeHtml(value) {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function showError(message) {
        els.error.textContent = message;
        els.error.hidden = false;
    }

    function clearError() {
        els.error.textContent = "";
        els.error.hidden = true;
    }

    function markerIcon(color, scale) {
        return {
            path: google.maps.SymbolPath.CIRCLE,
            scale: scale || 10,
            fillColor: color,
            fillOpacity: 1,
            strokeColor: "#ffffff",
            strokeWeight: 4,
        };
    }

    function updateContinueState() {
        els.btnContinue.disabled = !(state.origin && state.destination);
    }

    function updateOrigin(point) {
        state.origin = point;
        els.originSummary.textContent = point.name || "Usted está aquí";
        els.originCoords.textContent = `${point.lat.toFixed(6)}, ${point.lng.toFixed(6)}`;
        updateContinueState();
    }

    function updateDestination(point, centerMap) {
        state.destination = point;
        const position = { lat: point.lat, lng: point.lng };
        if (!state.destinationMarker) {
            state.destinationMarker = new google.maps.Marker({
                map: state.map,
                position: position,
                draggable: true,
                title: "Destino seleccionado",
                icon: markerIcon("#d71920", 10),
                zIndex: 8,
            });
            state.destinationMarker.addListener("dragend", function (event) {
                reverseGeocodeDestination(event.latLng.lat(), event.latLng.lng(), "Destino ajustado");
            });
        } else {
            state.destinationMarker.setPosition(position);
        }

        els.destinationSummary.textContent = point.name || "Destino seleccionado";
        els.destinationCoords.textContent = `${point.lat.toFixed(6)}, ${point.lng.toFixed(6)}`;
        if (centerMap) {
            state.map.panTo(position);
            state.map.setZoom(17);
        }
        updateContinueState();
    }

    function reverseGeocodeDestination(lat, lng, fallback) {
        state.geocoder.geocode({ location: { lat: lat, lng: lng } }, function (results, status) {
            const name = status === "OK" && results && results[0]
                ? results[0].formatted_address
                : fallback;
            updateDestination({ lat: lat, lng: lng, name: name }, false);
        });
    }

    function reverseGeocodeOrigin(lat, lng, fallback) {
        state.geocoder.geocode({ location: { lat: lat, lng: lng } }, function (results, status) {
            const name = status === "OK" && results && results[0]
                ? results[0].formatted_address
                : fallback;
            updateOrigin({ lat: lat, lng: lng, name: name });
            els.status.textContent = adminMode
                ? "Punto de inicio de la prueba ajustado. Selecciona ahora el destino."
                : "Punto de inicio ajustado. Selecciona ahora el destino.";
        });
    }

    function renderOriginMarker(point, accuracy) {
        const position = { lat: point.lat, lng: point.lng };
        if (!state.originMarker) {
            state.originMarker = new google.maps.Marker({
                map: state.map,
                position: position,
                draggable: true,
                title: adminMode ? "Inicio de la prueba" : "Usted está aquí",
                icon: markerIcon("#2563eb", 10),
                zIndex: 7,
            });
            state.originMarker.addListener("dragend", function (event) {
                reverseGeocodeOrigin(
                    event.latLng.lat(),
                    event.latLng.lng(),
                    adminMode ? "Inicio ajustado de la prueba" : "Inicio ajustado"
                );
            });
            state.originMarker.addListener("click", function () {
                state.infoWindow.setContent(
                    `<div class="dc-map-info"><strong>${adminMode ? "Inicio de la prueba" : "Usted está aquí"}</strong><span>${escapeHtml(state.origin ? state.origin.name : "Ubicación del dispositivo")}</span></div>`
                );
                state.infoWindow.open({ map: state.map, anchor: state.originMarker });
            });
        } else {
            state.originMarker.setPosition(position);
        }
        updateOrigin(point);
        const precisionText = Number.isFinite(accuracy) ? `Precisión aproximada: ${Math.round(accuracy)} m.` : "";
        state.infoWindow.setContent(
            `<div class="dc-map-info"><strong>${adminMode ? "Inicio de la prueba" : "Usted está aquí"}</strong><span>${escapeHtml(point.name || "Ubicación del dispositivo")}</span><small>${escapeHtml(precisionText)}</small></div>`
        );
        state.infoWindow.open({ map: state.map, anchor: state.originMarker });
    }

    function requestLocation(centerMap) {
        clearError();
        if (!navigator.geolocation) {
            showError("Este navegador no admite geolocalización.");
            return;
        }
        els.btnMyLocation.disabled = true;
        navigator.geolocation.getCurrentPosition(
            function (position) {
                const point = {
                    lat: position.coords.latitude,
                    lng: position.coords.longitude,
                    name: "Ubicación actual del vehículo",
                };
                renderOriginMarker(point, position.coords.accuracy);
                if (centerMap) {
                    state.map.panTo(point);
                    state.map.setZoom(17);
                }
                els.btnMyLocation.disabled = false;
            },
            function (error) {
                els.btnMyLocation.disabled = false;
                const messages = {
                    1: "El permiso de ubicación fue rechazado. Puedes continuar con el origen del tramo anterior o habilitar el permiso.",
                    2: "El dispositivo no pudo determinar la ubicación.",
                    3: "La solicitud de ubicación tardó demasiado.",
                };
                showError(messages[error.code] || "No se pudo obtener la ubicación.");
            },
            { enableHighAccuracy: true, maximumAge: 3000, timeout: 20000 }
        );
    }

    function hideResults() {
        els.results.hidden = true;
        els.results.innerHTML = "";
    }

    function renderResults(results) {
        if (!results.length) {
            els.results.innerHTML = '<div class="destination-result-empty">No se encontraron coincidencias.</div>';
            els.results.hidden = false;
            return;
        }
        els.results.innerHTML = results.map(function (item, index) {
            return `
                <button type="button" class="destination-result-item" data-index="${index}">
                    <i class="bi bi-geo-alt"></i>
                    <span><strong>${escapeHtml(item.nombre)}</strong><small>${escapeHtml(item.direccion)}</small></span>
                    <em>${escapeHtml(item.tipo || "Lugar")}</em>
                </button>`;
        }).join("");
        els.results.hidden = false;
        els.results.querySelectorAll(".destination-result-item").forEach(function (button) {
            button.addEventListener("click", function () {
                const item = results[Number(button.dataset.index)];
                updateDestination({
                    lat: Number(item.latitud),
                    lng: Number(item.longitud),
                    name: item.direccion || item.nombre,
                }, true);
                els.input.value = item.nombre;
                els.btnClear.hidden = false;
                els.status.textContent = "Destino marcado. Puedes ajustar el punto en el mapa o continuar a revisar ambos accesos.";
                hideResults();
            });
        });
    }

    async function searchDestination() {
        const query = els.input.value.trim();
        els.btnClear.hidden = !query;
        if (query.length < 2) {
            hideResults();
            els.status.textContent = "Escribe al menos dos caracteres para buscar.";
            return;
        }
        if (state.searchController) state.searchController.abort();
        state.searchController = new AbortController();
        els.btnSearch.disabled = true;
        els.status.textContent = "Buscando destinos con Google Places…";
        clearError();

        const params = new URLSearchParams({ q: query });
        if (state.origin) {
            params.set("lat", state.origin.lat);
            params.set("lon", state.origin.lng);
        }
        try {
            const response = await fetch(`${config.dataset.searchUrl}?${params.toString()}`, {
                headers: { "X-Requested-With": "XMLHttpRequest" },
                signal: state.searchController.signal,
            });
            const data = await response.json();
            if (!response.ok || !data.ok) throw new Error(data.mensaje || "No se pudo completar la búsqueda.");
            renderResults(data.resultados || []);
            els.status.textContent = data.mensaje || "Selecciona un resultado.";
        } catch (error) {
            if (error.name !== "AbortError") {
                hideResults();
                showError(error.message);
                els.status.textContent = "También puedes marcar el destino directamente sobre el mapa.";
            }
        } finally {
            els.btnSearch.disabled = false;
        }
    }

    function toggleDestinationMode() {
        state.selectingDestination = !state.selectingDestination;
        els.notice.hidden = !state.selectingDestination;
        els.btnSelectDestination.classList.toggle("is-active", state.selectingDestination);
        els.btnSelectDestination.innerHTML = state.selectingDestination
            ? '<i class="bi bi-x-circle"></i> Cancelar marca'
            : '<i class="bi bi-cursor"></i> Marcar en mapa';
    }

    function continueToReview() {
        if (state.navigating) return;
        if (!state.origin || !state.destination) {
            showError("Debes definir el punto de inicio y el destino.");
            return;
        }
        state.navigating = true;
        els.btnContinue.disabled = true;
        const base = config.dataset.verLugarBase.replace("/0/0/", `/${state.destination.lat}/${state.destination.lng}/`);
        const params = new URLSearchParams({
            nombre: state.destination.name || "Destino seleccionado",
            origen_lat: state.origin.lat,
            origen_lon: state.origin.lng,
            origen_nombre: state.origin.name || "Punto de inicio",
        });
        if (config.dataset.viajeId) params.set("viaje", config.dataset.viajeId);
        const nextUrl = `${base}?${params.toString()}`;
        if (window.DistricTabLock && typeof window.DistricTabLock.navigate === "function") {
            window.DistricTabLock.navigate(nextUrl);
        } else {
            window.location.assign(nextUrl);
        }
    }

    window.initDistricDestinationMap = function () {
        state.geocoder = new google.maps.Geocoder();
        state.infoWindow = new google.maps.InfoWindow();
        const initialOrigin = {
            lat: number(config.dataset.origenLat),
            lng: number(config.dataset.origenLon),
            name: config.dataset.origenNombre || "Punto de inicio",
        };
        const center = initialOrigin.lat !== null && initialOrigin.lng !== null
            ? initialOrigin
            : { lat: -0.9336, lng: -78.6142 };

        state.map = new google.maps.Map(els.map, {
            center: center,
            zoom: initialOrigin.lat !== null ? 16 : 13,
            mapTypeControl: true,
            fullscreenControl: true,
            streetViewControl: true,
            gestureHandling: "greedy",
        });

        state.map.addListener("click", function (event) {
            if (!state.selectingDestination) return;
            reverseGeocodeDestination(event.latLng.lat(), event.latLng.lng(), "Destino marcado en el mapa");
            toggleDestinationMode();
        });

        if (initialOrigin.lat !== null && initialOrigin.lng !== null) {
            renderOriginMarker(initialOrigin, null);
        } else {
            requestLocation(true);
        }
    };

    els.btnSearch.addEventListener("click", searchDestination);
    els.input.addEventListener("input", function () {
        els.btnClear.hidden = !els.input.value;
        window.clearTimeout(state.searchTimer);
        state.searchTimer = window.setTimeout(searchDestination, 550);
    });
    els.input.addEventListener("keydown", function (event) {
        if (event.key === "Enter") {
            event.preventDefault();
            searchDestination();
        }
    });
    els.btnClear.addEventListener("click", function () {
        els.input.value = "";
        els.btnClear.hidden = true;
        hideResults();
        els.input.focus();
    });
    els.btnMyLocation.addEventListener("click", function () { requestLocation(true); });
    els.btnSelectDestination.addEventListener("click", toggleDestinationMode);
    els.btnContinue.addEventListener("click", continueToReview);
    document.addEventListener("click", function (event) {
        if (!event.target.closest(".destination-search-input-wrap")) hideResults();
    });

    const key = config.dataset.googleMapsKey;
    if (!key) {
        showError("No se configuró GOOGLE_MAPS_API_KEY para cargar el mapa.");
        return;
    }
    const script = document.createElement("script");
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(key)}&v=weekly&callback=initDistricDestinationMap`;
    script.async = true;
    script.defer = true;
    script.onerror = function () {
        showError("No se pudo cargar Google Maps. Revisa la clave web, Maps JavaScript API, facturación y referencias HTTP permitidas.");
    };
    document.head.appendChild(script);
})();
