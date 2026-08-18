(function () {
  "use strict";

  const dataNode = document.getElementById("generalPlansData");
  const mapNode = document.getElementById("generalRouteMap");
  if (!dataNode || !mapNode) return;

  let plans = {};
  try {
    plans = JSON.parse(dataNode.textContent || "{}");
  } catch (_error) {
    plans = {};
  }

  const vehicleSelect = document.getElementById("generalVehicleSelect");
  const planSelect = document.getElementById("generalPlanSelect");
  const vehicleError = document.getElementById("generalVehicleError");
  const planError = document.getElementById("generalPlanError");
  const preview = document.getElementById("generalSelectionPreview");
  const previewDriver = document.getElementById("generalPreviewDriver");
  const previewVehicle = document.getElementById("generalPreviewVehicle");
  const previewLoad = document.getElementById("generalPreviewLoad");
  const previewProducts = document.getElementById("generalPreviewProducts");
  const setupMessage = document.getElementById("generalSetupMessage");
  const acceptBtn = document.getElementById("generalAcceptSelectionBtn");

  const planningSection = document.getElementById("generalPlanningSection");
  const activeDriver = document.getElementById("generalActiveDriver");
  const activeVehicle = document.getElementById("generalActiveVehicle");
  const activeWeight = document.getElementById("generalActiveWeight");
  const segmentsEditor = document.getElementById("generalSegmentsEditor");
  const segmentTabs = document.getElementById("generalSegmentTabs");
  const currentLocationBtn = document.getElementById("useCurrentLocationBtn");
  const removeLastBtn = document.getElementById("removeLastGeneralPointBtn");
  const clearPointsBtn = document.getElementById("clearGeneralPointsBtn");
  const pointCount = document.getElementById("generalPointCount");
  const mapNote = document.getElementById("generalMapNote");

  const form = document.getElementById("generalRouteForm");
  const planInput = document.getElementById("generalPlanInput");
  const latInput = document.getElementById("generalOriginLat");
  const lonInput = document.getElementById("generalOriginLon");
  const originNameInput = document.getElementById("generalOriginName");
  const pointsInput = document.getElementById("generalStopPoints");
  const adjustmentsInput = document.getElementById("generalDeliveryAdjustments");
  const notesInput = document.getElementById("generalSegmentNotes");
  const calculateBtn = document.getElementById("calculateGeneralRouteBtn");
  const routeLoading = document.getElementById("generalRouteLoading");

  let activePlan = null;
  let map = null;
  let originMarker = null;
  let stopPoints = [];
  let stopMarkers = [];
  let mapsReady = false;
  let activeSegmentIndex = 1;

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>'"]/g, function (char) {
      return {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "'": "&#39;",
        '"': "&quot;"
      }[char];
    });
  }

  function formatCountLabel(count, singular, plural) {
    const safeCount = Number.isFinite(Number(count)) ? Math.max(0, Math.floor(Number(count))) : 0;
    const singularText = String(singular || "unidad").trim() || "unidad";
    const pluralText = String(plural || `${singularText}s`).trim() || `${singularText}s`;
    return `${safeCount} ${safeCount === 1 ? singularText : pluralText}`;
  }

  function formatProductQuantity(product, count) {
    return formatCountLabel(count, product && product.unidad_carga, product && product.unidad_carga_plural);
  }

  function formatProductMeta(product) {
    const parts = [];
    const presentation = String((product && (product.presentacion_resumen || product.presentacion)) || "").trim();
    const content = String((product && product.contenido_formateado) || "").trim();

    if (presentation) parts.push(presentation);
    if (content && content !== "—") parts.push(`${content} c/u`);

    return parts.join(" · ") || "Unidad";
  }


  function setError(select, box, message) {
    if (select) select.classList.toggle("is-invalid", Boolean(message));
    if (box) box.textContent = message || "";
  }

  function clearStopMarkers() {
    stopMarkers.forEach(function (marker) {
      marker.setMap(null);
    });
    stopMarkers = [];
  }

  function clearAllMapMarkers() {
    if (originMarker) {
      originMarker.setMap(null);
      originMarker = null;
    }
    clearStopMarkers();
  }

  function resetPlanning() {
    activePlan = null;
    planInput.value = "";
    latInput.value = "";
    lonInput.value = "";
    pointsInput.value = "";
    adjustmentsInput.value = "";
    notesInput.value = "";
    stopPoints = [];
    planningSection.hidden = true;
    activeSegmentIndex = 1;
    if (segmentTabs) { segmentTabs.innerHTML = ""; segmentTabs.hidden = true; }
    segmentsEditor.innerHTML = '<p class="general-segment-placeholder">Agrega el punto 1 en el mapa para crear el primer tramo.</p>';
    clearAllMapMarkers();
    updatePointCount();
  }

  function filterPlansByVehicle() {
    const vehicleId = String(vehicleSelect.value || "");

    // Reconstruir el selector evita depender de <option hidden>, que puede
    // comportarse distinto entre navegadores y además podía quedar obsoleto
    // por la caché de la PWA. La fuente real es generalPlansData.
    planSelect.innerHTML = "";

    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = vehicleId ? "Seleccione una carga" : "Seleccione primero el vehículo";
    planSelect.appendChild(placeholder);

    const matchingPlans = Object.values(plans)
      .filter(function (plan) {
        return String(plan.vehiculo_id) === vehicleId;
      })
      .sort(function (a, b) {
        return Number(b.id || 0) - Number(a.id || 0);
      });

    matchingPlans.forEach(function (plan) {
      const option = document.createElement("option");
      option.value = String(plan.id);
      option.textContent = `Plan #${plan.id} · ${plan.fecha || "Sin fecha"} · ${Number(plan.peso_kg || 0).toFixed(2)} kg`;
      planSelect.appendChild(option);
    });

    planSelect.value = "";
    planSelect.disabled = !vehicleId || matchingPlans.length === 0;

    preview.hidden = true;
    setError(vehicleSelect, vehicleError, "");
    setError(planSelect, planError, "");
    resetPlanning();

    if (vehicleId && !matchingPlans.length) {
      setError(planSelect, planError, "Este vehículo no tiene cargas disponibles con productos.");
      setupMessage.textContent = "Selecciona otro vehículo o registra una carga válida.";
    } else {
      setupMessage.textContent = vehicleId
        ? "Ahora selecciona la carga que utilizará este vehículo."
        : "Selecciona primero el vehículo y luego una carga.";
    }
  }

  function showSelectionPreview() {
    resetPlanning();
    const plan = plans[String(planSelect.value)] || null;
    if (!plan) {
      preview.hidden = true;
      return;
    }

    const products = Array.isArray(plan.productos) ? plan.productos : [];
    previewDriver.textContent = plan.conductor || "—";
    previewVehicle.textContent = `${plan.vehiculo || "—"} · ${plan.modelo || "Sin modelo"}`;
    previewLoad.textContent = `${Number(plan.peso_kg || 0).toFixed(2)} kg · ${plan.estado || ""}`;
    previewProducts.textContent = `${products.length} producto(s)`;
    preview.hidden = false;
    setError(planSelect, planError, "");
    setupMessage.textContent = plan.revisado
      ? "Carga revisada. Presiona “Aceptar e iniciar”."
      : "Carga disponible. Presiona “Aceptar e iniciar” para definir los puntos.";
  }

  function updatePointCount() {
    if (!pointCount) return;
    const count = stopPoints.length;
    pointCount.textContent = count === 1 ? "1 destino agregado" : `${count} destinos agregados`;
  }

  // Mantener una vista amplia y estable. Al seleccionar, mover o agregar puntos
  // el mapa NO cambia automáticamente el nivel de zoom.
  function centerWithoutZoom(position) {
    if (!map || !position) return;
    map.panTo(position);
  }

  function setOrigin(lat, lon, label) {
    lat = Number(lat);
    lon = Number(lon);
    if (!Number.isFinite(lat) || !Number.isFinite(lon) || !map) return;

    latInput.value = lat.toFixed(7);
    lonInput.value = lon.toFixed(7);
    originNameInput.value = label || "Punto 0";

    if (originMarker) originMarker.setMap(null);
    originMarker = new google.maps.Marker({
      position: { lat: lat, lng: lon },
      map: map,
      draggable: true,
      title: "Punto 0 · ubicación inicial",
      label: { text: "0", color: "#ffffff", fontWeight: "700" },
      icon: {
        path: google.maps.SymbolPath.CIRCLE,
        fillColor: "#2563eb",
        fillOpacity: 1,
        strokeColor: "#ffffff",
        strokeWeight: 3,
        scale: 14
      }
    });

    originMarker.addListener("dragend", function (event) {
      latInput.value = event.latLng.lat().toFixed(7);
      lonInput.value = event.latLng.lng().toFixed(7);
      originNameInput.value = "Punto 0 ajustado";
      mapNote.textContent = "Punto 0 ajustado. Ahora agrega o revisa los destinos 1, 2, 3…";
      centerWithoutZoom(event.latLng);
    });

    centerWithoutZoom({ lat: lat, lng: lon });
    mapNote.textContent = "Punto 0 cargado en azul. Arrástralo si necesitas ajustarlo y haz clic en el mapa para agregar el punto 1.";
  }

  function captureDraft() {
    const draft = { quantities: {}, notes: {} };
    Array.from(segmentsEditor.querySelectorAll(".segment-editor-card")).forEach(function (card) {
      const pointNumber = Number(card.dataset.pointNumber);
      draft.quantities[pointNumber] = {};
      Array.from(card.querySelectorAll(".delivery-quantity")).forEach(function (input) {
        draft.quantities[pointNumber][Number(input.dataset.detailId)] = Number(input.value || 0);
      });
      const note = card.querySelector(".segment-note");
      draft.notes[pointNumber] = note ? note.value : "";
    });
    return draft;
  }

  function renderStopMarkers() {
    if (!map) return;
    clearStopMarkers();

    stopPoints.forEach(function (point, index) {
      const pointNumber = index + 1;
      point.numero = pointNumber;
      point.nombre = `Punto ${pointNumber}`;

      const marker = new google.maps.Marker({
        position: { lat: Number(point.lat), lng: Number(point.lon) },
        map: map,
        draggable: true,
        title: point.nombre,
        label: { text: String(pointNumber), color: "#ffffff", fontWeight: "700" },
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          fillColor: "#d71920",
          fillOpacity: 1,
          strokeColor: "#ffffff",
          strokeWeight: 2,
          scale: 12
        }
      });

      marker.addListener("dragend", function (event) {
        point.lat = event.latLng.lat();
        point.lon = event.latLng.lng();
        mapNote.textContent = `${point.nombre} ajustado manualmente.`;
        centerWithoutZoom(event.latLng);
      });
      stopMarkers.push(marker);
    });

    updatePointCount();
  }

  function addStopPoint(lat, lon) {
    if (!activePlan || !originMarker) {
      mapNote.textContent = "Primero define el punto 0 de inicio.";
      return;
    }

    const draft = captureDraft();
    stopPoints.push({
      numero: stopPoints.length + 1,
      nombre: `Punto ${stopPoints.length + 1}`,
      lat: Number(lat),
      lon: Number(lon)
    });
    activeSegmentIndex = stopPoints.length;
    renderStopMarkers();
    renderSegments(draft);
    mapNote.textContent = `Punto ${stopPoints.length} agregado. Puedes arrastrarlo o agregar el siguiente punto.`;
  }

  function removeLastStopPoint() {
    if (!stopPoints.length) return;
    const draft = captureDraft();
    stopPoints.pop();
    activeSegmentIndex = Math.max(1, Math.min(activeSegmentIndex, stopPoints.length || 1));
    renderStopMarkers();
    renderSegments(draft);
    mapNote.textContent = stopPoints.length
      ? "Último destino eliminado. La secuencia fue renumerada automáticamente."
      : "No hay destinos. Haz clic en el mapa para agregar el punto 1.";
  }

  function clearStopPoints() {
    if (!stopPoints.length) return;
    stopPoints = [];
    activeSegmentIndex = 1;
    renderStopMarkers();
    renderSegments();
    mapNote.textContent = "Destinos eliminados. El punto 0 se mantiene; haz clic en el mapa para agregar el punto 1.";
  }

  function showSegment(index, shouldScroll) {
    const cards = Array.from(segmentsEditor.querySelectorAll(".segment-editor-card"));
    if (!cards.length) return;

    activeSegmentIndex = Math.max(1, Math.min(Number(index) || 1, cards.length));
    cards.forEach(function (card) {
      card.hidden = Number(card.dataset.segmentIndex) !== activeSegmentIndex;
    });

    if (segmentTabs) {
      Array.from(segmentTabs.querySelectorAll(".segment-tab-btn")).forEach(function (button) {
        const selected = Number(button.dataset.segmentIndex) === activeSegmentIndex;
        button.classList.toggle("active", selected);
        button.setAttribute("aria-selected", selected ? "true" : "false");
      });
    }

    if (shouldScroll) {
      const activeCard = cards.find(function (card) {
        return Number(card.dataset.segmentIndex) === activeSegmentIndex;
      });
      if (activeCard) activeCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }

  function renderSegmentTabs() {
    if (!segmentTabs) return;
    if (!stopPoints.length) {
      segmentTabs.innerHTML = "";
      segmentTabs.hidden = true;
      return;
    }

    segmentTabs.hidden = false;
    segmentTabs.innerHTML = stopPoints.map(function (_point, index) {
      const segmentIndex = index + 1;
      return `<button type="button" class="segment-tab-btn" data-segment-index="${segmentIndex}" role="tab" aria-selected="false">
        <span>Tramo</span><strong>${segmentIndex - 1} → ${segmentIndex}</strong>
      </button>`;
    }).join("");

    Array.from(segmentTabs.querySelectorAll(".segment-tab-btn")).forEach(function (button) {
      button.addEventListener("click", function () {
        showSegment(Number(button.dataset.segmentIndex), false);
      });
    });
  }

  function renderSegments(draft) {
    if (!activePlan || !stopPoints.length) {
      if (segmentTabs) { segmentTabs.innerHTML = ""; segmentTabs.hidden = true; }
      segmentsEditor.innerHTML = '<p class="general-segment-placeholder">Agrega el punto 1 en el mapa para crear el primer tramo.</p>';
      return;
    }

    const products = Array.isArray(activePlan.productos) ? activePlan.productos : [];
    draft = draft || { quantities: {}, notes: {} };

    segmentsEditor.innerHTML = stopPoints.map(function (point, index) {
      const pointNumber = index + 1;
      const productRows = products.map(function (product) {
        const saved = draft.quantities[pointNumber] && draft.quantities[pointNumber][product.detalle_id] !== undefined
          ? Number(draft.quantities[pointNumber][product.detalle_id])
          : 0;
        const quantityLabel = formatProductQuantity(product, Number(product.cantidad || 0));
        const metaLabel = formatProductMeta(product);
        return `
          <div class="delivery-row">
            <div class="delivery-copy">
              <strong>${escapeHtml(product.producto)}</strong>
              <span class="delivery-meta">${escapeHtml(metaLabel)}</span>
              <small class="delivery-stock">
                cargado: ${escapeHtml(quantityLabel)} · <b class="product-available"
                  data-detail-available="${product.detalle_id}"
                  data-unit-singular="${escapeHtml(product.unidad_carga || 'unidad')}"
                  data-unit-plural="${escapeHtml(product.unidad_carga_plural || 'unidades')}">disponible: ${escapeHtml(quantityLabel)}</b>
              </small>
            </div>
            <div class="delivery-control">
              <label for="delivery-${pointNumber}-${product.detalle_id}">Dejar</label>
              <input type="number"
                     id="delivery-${pointNumber}-${product.detalle_id}"
                     class="delivery-quantity"
                     min="0"
                     max="${Number(product.cantidad || 0)}"
                     value="${saved}"
                     step="1"
                     data-point-number="${pointNumber}"
                     data-detail-id="${product.detalle_id}"
                     data-unit-weight="${Number(product.peso_unitario_kg || 0)}">
            </div>
          </div>`;
      }).join("");

      return `
        <article class="segment-editor-card" data-point-number="${pointNumber}" data-segment-index="${index + 1}">
          <div class="segment-editor-head">
            <span class="segment-pill">Tramo ${index} → ${index + 1}</span>
            <div>
              <strong>Entrega en punto ${pointNumber}</strong>
              <small>Destino seleccionado directamente en el mapa</small>
            </div>
          </div>
          <div class="delivery-list">${productRows}</div>
          <div class="segment-weight-summary">
            <span>Carga al iniciar <strong class="segment-start-weight">—</strong></span>
            <span>Entrega <strong class="segment-delivery-weight">—</strong></span>
            <span>Restante <strong class="segment-remaining-weight">—</strong></span>
          </div>
          <div class="segment-note-field">
            <label for="segment-note-${pointNumber}">Nota opcional</label>
            <textarea id="segment-note-${pointNumber}" class="segment-note" data-point-number="${pointNumber}" maxlength="1000" rows="2" placeholder="Observación para este tramo">${escapeHtml(draft.notes[pointNumber] || "")}</textarea>
          </div>
        </article>`;
    }).join("");

    recalculateSequenceWeights();
    renderSegmentTabs();
    showSegment(activeSegmentIndex, false);
  }

  function recalculateSequenceWeights() {
    if (!activePlan) return;

    const remainingByProduct = {};
    (activePlan.productos || []).forEach(function (product) {
      remainingByProduct[Number(product.detalle_id)] = Number(product.cantidad || 0);
    });

    let currentWeight = Number(activePlan.peso_kg || 0);

    Array.from(segmentsEditor.querySelectorAll(".segment-editor-card")).forEach(function (card) {
      let deliveredWeight = 0;

      Array.from(card.querySelectorAll(".delivery-quantity")).forEach(function (input) {
        const detailId = Number(input.dataset.detailId);
        const available = Math.max(0, Number(remainingByProduct[detailId] || 0));
        let quantity = Number(input.value || 0);
        if (!Number.isFinite(quantity) || quantity < 0) quantity = 0;
        quantity = Math.floor(quantity);
        if (quantity > available) quantity = available;

        input.max = String(available);
        input.value = String(quantity);
        remainingByProduct[detailId] = available - quantity;
        deliveredWeight += quantity * Number(input.dataset.unitWeight || 0);

        const row = input.closest(".delivery-row");
        const availableText = row ? row.querySelector(`[data-detail-available="${detailId}"]`) : null;
        if (availableText) {
          const singular = availableText.dataset.unitSingular || "unidad";
          const plural = availableText.dataset.unitPlural || `${singular}s`;
          availableText.textContent = `disponible: ${formatCountLabel(available, singular, plural)}`;
        }
      });

      const remainingWeight = Math.max(currentWeight - deliveredWeight, 0);
      card.querySelector(".segment-start-weight").textContent = `${currentWeight.toFixed(2)} kg`;
      card.querySelector(".segment-delivery-weight").textContent = `${deliveredWeight.toFixed(2)} kg`;
      card.querySelector(".segment-remaining-weight").textContent = `${remainingWeight.toFixed(2)} kg`;
      currentWeight = remainingWeight;
    });
  }

  function createMapIfNeeded() {
    if (!mapsReady || !activePlan) return;

    if (!map) {
      map = new google.maps.Map(mapNode, {
        center: { lat: -0.9352, lng: -78.6155 },
        zoom: 13,
        mapTypeControl: true,
        streetViewControl: false,
        fullscreenControl: true
      });

      map.addListener("click", function (event) {
        if (!activePlan) return;
        if (!originMarker) {
          setOrigin(event.latLng.lat(), event.latLng.lng(), "Punto 0 ajustado");
        } else {
          addStopPoint(event.latLng.lat(), event.latLng.lng());
        }
      });
    }

    clearAllMapMarkers();
    stopPoints = [];
    renderSegments();
    google.maps.event.trigger(map, "resize");
    requestCurrentLocation(true);
  }

  function requestCurrentLocation(isInitial) {
    if (!activePlan || !map) return;
    if (!navigator.geolocation) {
      mapNote.textContent = "No se pudo obtener tu ubicación automáticamente. Haz clic en el mapa para fijar el punto 0.";
      return;
    }

    if (currentLocationBtn) currentLocationBtn.disabled = true;
    mapNote.textContent = isInitial ? "Obteniendo tu ubicación actual…" : "Actualizando ubicación…";

    navigator.geolocation.getCurrentPosition(
      function (position) {
        if (currentLocationBtn) currentLocationBtn.disabled = false;
        if (isInitial && originMarker) return;
        setOrigin(position.coords.latitude, position.coords.longitude, "Punto 0 · ubicación actual");
      },
      function () {
        if (currentLocationBtn) currentLocationBtn.disabled = false;
        mapNote.textContent = "No se pudo obtener tu ubicación. Haz clic en el mapa para fijar el punto 0 manualmente.";
      },
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 10000 }
    );
  }

  function startSelection() {
    setError(vehicleSelect, vehicleError, "");
    setError(planSelect, planError, "");

    if (!vehicleSelect.value) {
      setError(vehicleSelect, vehicleError, "Selecciona un vehículo con conductor.");
      return;
    }
    if (!planSelect.value) {
      setError(planSelect, planError, "Selecciona una carga.");
      return;
    }

    const plan = plans[String(planSelect.value)] || null;
    if (!plan) {
      setError(planSelect, planError, "No se pudo leer la carga seleccionada.");
      return;
    }
    if (!Array.isArray(plan.productos) || !plan.productos.length) {
      setError(planSelect, planError, "La carga seleccionada no tiene productos disponibles.");
      return;
    }

    activePlan = plan;
    planInput.value = String(plan.id);
    activeDriver.textContent = plan.conductor || "—";
    activeVehicle.textContent = `${plan.vehiculo || "—"} · ${plan.modelo || "Sin modelo"}`;
    activeWeight.textContent = `${Number(plan.peso_kg || 0).toFixed(2)} kg`;
    planningSection.hidden = false;
    stopPoints = [];
    renderSegments();

    requestAnimationFrame(function () {
      createMapIfNeeded();
      planningSection.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  function serializePlanning() {
    const adjustments = [];
    const notes = {};

    Array.from(segmentsEditor.querySelectorAll(".segment-editor-card")).forEach(function (card) {
      const pointNumber = Number(card.dataset.pointNumber);
      const deliveries = Array.from(card.querySelectorAll(".delivery-quantity")).map(function (input) {
        return {
          detalle_id: Number(input.dataset.detailId),
          cantidad: Number(input.value || 0)
        };
      });
      adjustments.push({ punto_numero: pointNumber, entregas: deliveries });

      const note = card.querySelector(".segment-note");
      notes[String(pointNumber)] = note ? note.value.trim() : "";
    });

    pointsInput.value = JSON.stringify(stopPoints.map(function (point, index) {
      return {
        numero: index + 1,
        nombre: `Punto ${index + 1}`,
        lat: Number(point.lat),
        lon: Number(point.lon)
      };
    }));
    adjustmentsInput.value = JSON.stringify(adjustments);
    notesInput.value = JSON.stringify(notes);
  }

  vehicleSelect.addEventListener("change", filterPlansByVehicle);
  planSelect.addEventListener("change", showSelectionPreview);

  // Cuando se llega desde "Marcar como lista", dejar seleccionados el
  // vehículo y la carga recién preparada. El administrador todavía decide
  // cuándo iniciar el cálculo con el botón "Aceptar e iniciar".
  const preselectedPlanId = String(dataNode.dataset.preselectedPlan || "");
  const preselectedPlan = plans[preselectedPlanId] || null;
  if (preselectedPlan) {
    vehicleSelect.value = String(preselectedPlan.vehiculo_id || "");
    filterPlansByVehicle();
    planSelect.value = preselectedPlanId;
    showSelectionPreview();
  } else if (vehicleSelect.value) {
    // Si el navegador restaura el vehículo seleccionado al recargar,
    // sincronizar también el selector de carga.
    filterPlansByVehicle();
  }
  acceptBtn.addEventListener("click", startSelection);

  segmentsEditor.addEventListener("input", function (event) {
    if (event.target.classList.contains("delivery-quantity")) {
      recalculateSequenceWeights();
    }
  });

  if (currentLocationBtn) {
    currentLocationBtn.addEventListener("click", function () {
      requestCurrentLocation(false);
    });
  }
  if (removeLastBtn) removeLastBtn.addEventListener("click", removeLastStopPoint);
  if (clearPointsBtn) clearPointsBtn.addEventListener("click", clearStopPoints);

  function showRouteLoading() {
    if (!routeLoading) return;
    routeLoading.hidden = false;
    routeLoading.setAttribute("aria-hidden", "false");
    document.body.classList.add("route-processing-active");
  }

  form.addEventListener("submit", async function (event) {
    event.preventDefault();

    if (!activePlan || !planInput.value) {
      setupMessage.textContent = "Selecciona vehículo y carga, luego presiona “Aceptar e iniciar”.";
      return;
    }
    if (!latInput.value || !lonInput.value) {
      mapNote.textContent = "Falta definir el punto 0. Usa tu ubicación o haz clic en el mapa.";
      return;
    }
    if (!stopPoints.length) {
      mapNote.textContent = "Agrega al menos el punto 1 para crear el primer tramo.";
      return;
    }

    serializePlanning();

    const sequence = stopPoints.map(function (_point, index) {
      return `${index} → ${index + 1}`;
    }).join(" · ");

    if (!window.Swal) {
      mapNote.textContent = "No se pudo abrir la confirmación. Recarga la página e inténtalo nuevamente.";
      return;
    }

    const result = await Swal.fire({
      title: "¿Todo está listo?",
      html: `
        <div style="text-align:left; line-height:1.55; color:#4b5563;">
          <p style="margin:0 0 10px;">Se calculará el recorrido completo respetando este orden:</p>
          <div style="padding:10px 12px; border-radius:10px; background:#f5f6f8; font-weight:700; color:#20242a;">${escapeHtml(sequence)}</div>
          <p style="margin:10px 0 0; font-size:13px;">Las entregas se aplicarán secuencialmente y no modificarán la carga original.</p>
        </div>`,
      icon: "warning",
      showCancelButton: true,
      confirmButtonColor: "#d71920",
      cancelButtonColor: "#23262b",
      confirmButtonText: "Sí, calcular recorrido",
      cancelButtonText: "Cancelar",
      reverseButtons: true,
      focusCancel: true
    });

    if (!result.isConfirmed) return;

    calculateBtn.disabled = true;
    calculateBtn.innerHTML = '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span> Calculando…';
    showRouteLoading();

    // Se deja pintar el indicador antes del POST normal.
    // El cálculo del servidor y el endpoint permanecen exactamente iguales.
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        HTMLFormElement.prototype.submit.call(form);
      });
    });
  });

  window.initDistricGeneralRoutesMap = function () {
    mapsReady = true;
    if (activePlan && !planningSection.hidden) createMapIfNeeded();
  };

  const key = mapNode.dataset.googleMapsKey;
  if (!key) {
    mapNote.textContent = "No se configuró GOOGLE_MAPS_API_KEY.";
    return;
  }

  if (window.google && window.google.maps) {
    mapsReady = true;
  } else {
    const script = document.createElement("script");
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(key)}&v=weekly&callback=initDistricGeneralRoutesMap`;
    script.async = true;
    script.defer = true;
    script.onerror = function () {
      mapNote.textContent = "No se pudo cargar Google Maps.";
    };
    document.head.appendChild(script);
  }
})();


/* Historial paginado de planes generales. Solo organiza la visualización. */
(function () {
  "use strict";

  function iniciarHistorialGeneral() {
    if (!window.jQuery || !jQuery.fn || !jQuery.fn.DataTable) return;

    const tabla = document.getElementById("generalHistoryTable");
    if (!tabla || jQuery.fn.DataTable.isDataTable(tabla)) return;

    const buscador = document.getElementById("generalHistorySearch");
    const filtroFecha = document.getElementById("generalHistoryDate");
    const filtroTramos = document.getElementById("generalHistorySegments");
    const limpiar = document.getElementById("generalHistoryClear");

    const instancia = jQuery(tabla).DataTable({
      pageLength: 10,
      lengthMenu: [[10, 25, 50, 100], [10, 25, 50, 100]],
      order: [[0, "desc"]],
      autoWidth: false,
      columnDefs: [
        { targets: 6, orderable: false, searchable: false }
      ],
      dom: "rt<'general-history-footer'<'general-history-length'l><'general-history-info'i><'general-history-page'p>>",
      language: {
        info: "Mostrando _START_ a _END_ de _TOTAL_ cálculos",
        infoEmpty: "Sin cálculos registrados",
        infoFiltered: "(filtrado de _MAX_ registros)",
        lengthMenu: "Mostrar _MENU_ registros",
        zeroRecords: "No se encontraron cálculos con esos filtros",
        emptyTable: "Todavía no existen cálculos generales",
        paginate: {
          previous: "Anterior",
          next: "Siguiente"
        }
      }
    });

    const filtroPersonalizado = function (settings, data, dataIndex) {
      if (settings.nTable !== tabla) return true;

      const fila = instancia.row(dataIndex).node();
      if (!fila) return true;

      const fechaFila = String(fila.dataset.date || "");
      const tramosFila = Number(fila.dataset.tramos || 0);
      const fechaElegida = filtroFecha ? String(filtroFecha.value || "") : "";
      const rango = filtroTramos ? String(filtroTramos.value || "") : "";

      if (fechaElegida && fechaFila !== fechaElegida) return false;
      if (rango === "1-5" && !(tramosFila >= 1 && tramosFila <= 5)) return false;
      if (rango === "6-10" && !(tramosFila >= 6 && tramosFila <= 10)) return false;
      if (rango === "11+" && tramosFila < 11) return false;
      return true;
    };

    jQuery.fn.dataTable.ext.search.push(filtroPersonalizado);

    if (buscador) {
      buscador.addEventListener("input", function () {
        instancia.search(this.value || "").draw();
      });
    }

    if (filtroFecha) {
      filtroFecha.addEventListener("change", function () {
        instancia.draw();
      });
    }

    if (filtroTramos) {
      filtroTramos.addEventListener("change", function () {
        instancia.draw();
      });
    }

    if (limpiar) {
      limpiar.addEventListener("click", function () {
        if (buscador) buscador.value = "";
        if (filtroFecha) filtroFecha.value = "";
        if (filtroTramos) filtroTramos.value = "";
        instancia.search("").page.len(10).draw();
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciarHistorialGeneral);
  } else {
    iniciarHistorialGeneral();
  }
})();
