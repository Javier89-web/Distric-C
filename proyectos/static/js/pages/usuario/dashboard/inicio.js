let map = null;
    let phoneMarker = null;
    let infoUbicacion = null;
    let accuracyCircle = null;

    let socket = null;
    let socketRetries = 0;
    let socketTimer = null;
    let watchId = null;

    let ubicacionActiva = false;
    let lastGoodPosition = null;

    const MAX_ACCURACY_METERS = 80;
    const MIN_DISTANCE_METERS = 4;

    const mapElement = document.getElementById("map");
    const VEHICULO_ID = parseInt(mapElement.dataset.vehiculoId || "0", 10);

    function iniciarMapaGoogle() {
      const latacunga = {
        lat: -0.9333,
        lng: -78.6167
      };

      map = new google.maps.Map(document.getElementById("map"), {
        center: latacunga,
        zoom: 15,

        mapTypeControl: true,
        mapTypeControlOptions: {
          style: google.maps.MapTypeControlStyle.HORIZONTAL_BAR,
          position: google.maps.ControlPosition.LEFT_BOTTOM
        },

        streetViewControl: false,
        fullscreenControl: true,
        zoomControl: true
      });

      mostrarEstado(
        "Ubicación desactivada. Presiona “Activar ubicación” para obtener tu posición actual.",
        "alerta"
      );

      /*
        IMPORTANTE:
        Ya NO pintamos automáticamente last_lat / last_lon.
        Esos datos pueden ser viejos y por eso antes te aparecía en otro lugar.
      */

      if (localStorage.getItem("ubicacion_activa") === "1") {
        activarUbicacion();
      }
    }

    function mostrarEstado(mensaje, tipo = "ok") {
      const estado = document.getElementById("estadoGPS");

      estado.style.display = "block";
      estado.classList.remove("estado-ok", "estado-alerta", "estado-error");

      if (tipo === "ok") {
        estado.classList.add("estado-ok");
      } else if (tipo === "error") {
        estado.classList.add("estado-error");
      } else {
        estado.classList.add("estado-alerta");
      }

      estado.innerHTML = mensaje;
    }

    function calcularDistanciaMetros(pos1, pos2) {
      const R = 6371000;

      const lat1 = pos1.lat * Math.PI / 180;
      const lat2 = pos2.lat * Math.PI / 180;

      const deltaLat = (pos2.lat - pos1.lat) * Math.PI / 180;
      const deltaLng = (pos2.lng - pos1.lng) * Math.PI / 180;

      const a =
        Math.sin(deltaLat / 2) * Math.sin(deltaLat / 2) +
        Math.cos(lat1) * Math.cos(lat2) *
        Math.sin(deltaLng / 2) * Math.sin(deltaLng / 2);

      const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

      return R * c;
    }

    function paintMarker(lat, lon, accuracy = null, origen = "gps") {
      const coords = {
        lat: parseFloat(lat),
        lng: parseFloat(lon)
      };

      if (!phoneMarker) {
        phoneMarker = new google.maps.Marker({
          position: coords,
          map: map,
          title: "Mi ubicación actual",
          draggable: true,

          icon: {
            path: google.maps.SymbolPath.CIRCLE,
            scale: 12,
            fillColor: "#2563eb",
            fillOpacity: 1,
            strokeColor: "#ffffff",
            strokeWeight: 5
          }
        });

        phoneMarker.addListener("click", function () {
          if (infoUbicacion) {
            infoUbicacion.open(map, phoneMarker);
          }
        });

        phoneMarker.addListener("dragend", function (event) {
          const nuevaLat = event.latLng.lat();
          const nuevaLon = event.latLng.lng();

          lastGoodPosition = {
            lat: nuevaLat,
            lng: nuevaLon
          };

          localStorage.setItem("last_lat", nuevaLat);
          localStorage.setItem("last_lon", nuevaLon);

          mostrarEstado(
            "Ubicación ajustada manualmente y guardada. Esta será usada para calcular rutas.",
            "ok"
          );

          sendLocation(nuevaLat, nuevaLon, 5, true);
        });

      } else {
        phoneMarker.setPosition(coords);
      }

      const textoPrecision = accuracy !== null
        ? `Precisión aproximada: ${Math.round(accuracy)} m`
        : "Precisión no disponible";

      const textoOrigen = origen === "manual"
        ? "Ubicación ajustada manualmente"
        : "Mi ubicación actual";

      if (!infoUbicacion) {
        infoUbicacion = new google.maps.InfoWindow();
      }

      infoUbicacion.setContent(`
        <div style="font-family:Arial; font-size:14px;">
          <b>${textoOrigen}</b><br>
          Latitud: ${coords.lat.toFixed(6)}<br>
          Longitud: ${coords.lng.toFixed(6)}<br>
          ${textoPrecision}<br>
          <small>Si el punto no coincide contigo, puedes arrastrarlo.</small>
        </div>
      `);

      if (accuracy !== null) {
        if (!accuracyCircle) {
          accuracyCircle = new google.maps.Circle({
            strokeColor: "#2563eb",
            strokeOpacity: 0.7,
            strokeWeight: 2,
            fillColor: "#2563eb",
            fillOpacity: 0.15,
            map: map,
            center: coords,
            radius: accuracy
          });
        } else {
          accuracyCircle.setCenter(coords);
          accuracyCircle.setRadius(accuracy);
        }
      }

      map.panTo(coords);
    }

    function wsUrl() {
      return (window.location.protocol === "https:" ? "wss://" : "ws://") +
        window.location.host + "/ws/ubicacion/";
    }

    function connectSocket() {
      if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
        return;
      }

      socket = new WebSocket(wsUrl());

      socket.onopen = () => {
        socketRetries = 0;
        console.log("WS conectado");
      };

      /*
        IMPORTANTE:
        Ya NO usamos el mensaje del WebSocket para pintar el marcador.
        Así evitamos que una ubicación vieja de la BD sobrescriba tu ubicación actual.
      */
      socket.onmessage = (e) => {
        console.log("WS mensaje recibido, ignorado para no sobrescribir GPS:", e.data);
      };

      socket.onclose = () => {
        console.warn("WS cerrado");

        if (ubicacionActiva) {
          scheduleReconnect();
        }
      };

      socket.onerror = () => {
        console.warn("WS error, cerrando...");
        try {
          socket.close();
        } catch (e) { }
      };
    }

    function scheduleReconnect() {
      if (socketTimer) return;

      const delay = Math.min(15000, 1000 * Math.pow(2, socketRetries));
      socketRetries++;

      socketTimer = setTimeout(() => {
        socketTimer = null;
        connectSocket();
      }, delay);
    }

    function startWatch() {
      if (!("geolocation" in navigator)) {
        alert("Tu navegador no soporta geolocalización.");
        return;
      }

      if (watchId !== null) return;

      mostrarEstado("Buscando ubicación actual...", "alerta");

      watchId = navigator.geolocation.watchPosition(
        (pos) => {
          const lat = pos.coords.latitude;
          const lon = pos.coords.longitude;
          const accuracy = pos.coords.accuracy || 9999;

          console.log("GPS recibido:", lat, lon, "Precisión:", accuracy, "m");

          const nuevaPosicion = {
            lat: lat,
            lng: lon
          };

          /*
            Pintamos el punto para que puedas ver dónde te está ubicando el navegador.
            Si está mal, puedes arrastrar el punto azul.
          */
          paintMarker(lat, lon, accuracy, "gps");

          if (accuracy > MAX_ACCURACY_METERS) {
            mostrarEstado(
              `Ubicación detectada, pero con baja precisión (${Math.round(accuracy)} m). 
              Si el punto azul no coincide contigo, arrástralo manualmente.`,
              "alerta"
            );
            return;
          }

          if (lastGoodPosition) {
            const distancia = calcularDistanciaMetros(lastGoodPosition, nuevaPosicion);

            if (distancia < MIN_DISTANCE_METERS) {
              console.log("Movimiento ignorado por ser muy pequeño:", distancia);
              return;
            }
          }

          lastGoodPosition = nuevaPosicion;

          localStorage.setItem("last_lat", lat);
          localStorage.setItem("last_lon", lon);

          mostrarEstado(
            `Ubicación activada. Precisión aproximada: ${Math.round(accuracy)} m. 
            Puedes arrastrar el punto azul si deseas corregirlo.`,
            "ok"
          );

          sendLocation(lat, lon, accuracy, false);
        },
        (err) => {
          console.log("Geo error:", err);

          let mensaje = "No se pudo obtener tu ubicación.";

          if (err.code === 1) {
            mensaje = "Permiso de ubicación denegado. Activa la ubicación en el navegador.";
          } else if (err.code === 2) {
            mensaje = "No se pudo determinar la ubicación actual.";
          } else if (err.code === 3) {
            mensaje = "La ubicación tardó demasiado. Intenta otra vez.";
          }

          mostrarEstado(mensaje, "error");
        },
        {
          enableHighAccuracy: true,
          maximumAge: 0,
          timeout: 20000
        }
      );

      console.log("watchPosition iniciado:", watchId);
    }

    function stopWatch() {
      if (watchId !== null) {
        navigator.geolocation.clearWatch(watchId);
        watchId = null;
        console.log("watchPosition detenido");
      }
    }

    function sendLocation(lat, lon, accuracy = null, manual = false) {
      if (!ubicacionActiva && !manual) {
        return;
      }

      const origen = manual ? "manual" : "gps";

      paintMarker(lat, lon, accuracy, origen);

      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({
          latitud: lat,
          longitud: lon,
          vehiculo_id: VEHICULO_ID,
          guardar: true
        }));

        console.log("Ubicación enviada y guardada:", lat, lon);
      } else {
        console.warn("Socket no conectado. No se pudo guardar todavía.");
      }
    }

    function activarUbicacion() {
      if (ubicacionActiva) return;

      ubicacionActiva = true;

      localStorage.setItem("ubicacion_activa", "1");

      /*
        Borramos posición vieja para no reutilizar coordenadas anteriores.
      */
      localStorage.removeItem("last_lat");
      localStorage.removeItem("last_lon");

      const btn = document.getElementById("btnUbicacion");
      btn.textContent = "Desactivar ubicación";
      btn.style.backgroundColor = "#dc3545";

      mostrarEstado("Activando ubicación actual...", "alerta");

      connectSocket();
      startWatch();
    }

    function desactivarUbicacion() {
      ubicacionActiva = false;

      localStorage.removeItem("ubicacion_activa");
      localStorage.removeItem("last_lat");
      localStorage.removeItem("last_lon");

      stopWatch();

      if (socket) {
        try {
          socket.close();
        } catch (e) { }
        socket = null;
      }

      if (socketTimer) {
        clearTimeout(socketTimer);
        socketTimer = null;
      }

      if (phoneMarker) {
        phoneMarker.setMap(null);
        phoneMarker = null;
      }

      if (accuracyCircle) {
        accuracyCircle.setMap(null);
        accuracyCircle = null;
      }

      lastGoodPosition = null;

      const btn = document.getElementById("btnUbicacion");
      btn.textContent = "Activar ubicación";
      btn.style.backgroundColor = "#007bff";

      mostrarEstado("Ubicación desactivada.", "alerta");
    }

    function onResume(callback) {
      document.addEventListener("visibilitychange", () => {
        if (!document.hidden) callback();
      });

      window.addEventListener("focus", callback);
      window.addEventListener("online", callback);
      window.addEventListener("pageshow", callback);
    }

    document.getElementById("btnUbicacion").addEventListener("click", function () {
      if (ubicacionActiva) {
        desactivarUbicacion();
      } else {
        activarUbicacion();
      }
    });

    onResume(() => {
      if (ubicacionActiva || localStorage.getItem("ubicacion_activa") === "1") {
        console.log("Resume: reactivando GPS y WS");

        if (!ubicacionActiva) {
          activarUbicacion();
        } else {
          connectSocket();

          if (watchId === null) {
            startWatch();
          }
        }
      }
    });
  

    function cargarGoogleMaps() {
      const apiKey = mapElement ? mapElement.dataset.googleMapsKey : "";
      if (!apiKey) {
        mostrarEstado("No se configuró la clave de Google Maps.", "error");
        return;
      }
      window.iniciarMapaGoogle = iniciarMapaGoogle;
      const script = document.createElement("script");
      script.src = "https://maps.googleapis.com/maps/api/js?key=" + encodeURIComponent(apiKey) + "&callback=iniciarMapaGoogle";
      script.async = true;
      script.defer = true;
      document.head.appendChild(script);
    }

    cargarGoogleMaps();
