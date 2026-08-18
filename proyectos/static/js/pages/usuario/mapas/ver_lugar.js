(function () {
    "use strict";

    const config = document.getElementById("routePointsConfig");
    if (!config) return;

    const state = {origin:null,destination:null,originMap:null,destinationMap:null,originMarker:null,destinationMarker:null,geocoder:null,saving:false};
    const els = {
        originAddress:document.getElementById("originAddress"),originCoords:document.getElementById("originCoords"),
        destinationAddress:document.getElementById("destinationAddress"),destinationCoords:document.getElementById("destinationCoords"),
        originTitle:document.getElementById("originTitle"),destinationTitle:document.getElementById("destinationTitle"),
        errorBox:document.getElementById("routePointErrors"),btnGps:document.getElementById("btnActualizarGps"),
        btnCenterDestination:document.getElementById("btnCentrarDestino"),btnBack:document.getElementById("btnVolverSeleccion"),
        btnSaveCalculate:document.getElementById("btnGuardarCalcular"),loading:document.getElementById("routeAlternativesLoading")
    };

    function n(value){const result=Number.parseFloat(value);return Number.isFinite(result)?result:null;}
    function csrfToken(){const match=document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);return match?decodeURIComponent(match[1]):"";}
    function showError(message){els.errorBox.textContent=message;els.errorBox.hidden=false;}
    function clearError(){els.errorBox.textContent="";els.errorBox.hidden=true;}
    function markerIcon(color){return{path:google.maps.SymbolPath.CIRCLE,scale:10,fillColor:color,fillOpacity:1,strokeColor:"#ffffff",strokeWeight:4};}
    function reverseGeocode(point,fallback,callback){state.geocoder.geocode({location:{lat:point.lat,lng:point.lng}},function(results,status){callback(status==="OK"&&results&&results[0]?results[0].formatted_address:fallback);});}
    function updateOrigin(point,resolve){state.origin=point;state.originMarker.setPosition({lat:point.lat,lng:point.lng});els.originCoords.textContent=`${point.lat.toFixed(6)}, ${point.lng.toFixed(6)}`;els.originAddress.textContent=point.name||"Punto de inicio";els.originTitle.textContent=point.name||"Ubicación del vehículo";if(resolve){reverseGeocode(point,point.name||"Punto de inicio",function(address){state.origin.name=address;els.originAddress.textContent=address;els.originTitle.textContent=address;});}}
    function updateDestination(point,resolve){state.destination=point;state.destinationMarker.setPosition({lat:point.lat,lng:point.lng});els.destinationCoords.textContent=`${point.lat.toFixed(6)}, ${point.lng.toFixed(6)}`;els.destinationAddress.textContent=point.name||"Destino";els.destinationTitle.textContent=point.name||"Destino";if(resolve){reverseGeocode(point,point.name||"Destino",function(address){state.destination.name=address;els.destinationAddress.textContent=address;els.destinationTitle.textContent=address;});}}
    function getGps(){clearError();if(!navigator.geolocation){showError("Este navegador no admite geolocalización.");return;}els.btnGps.disabled=true;navigator.geolocation.getCurrentPosition(function(position){const point={lat:position.coords.latitude,lng:position.coords.longitude,name:"Ubicación actual del vehículo"};updateOrigin(point,true);state.originMap.panTo(point);state.originMap.setZoom(18);els.btnGps.disabled=false;},function(){els.btnGps.disabled=false;showError("No se obtuvo el GPS. Revisa el permiso o ajusta manualmente el marcador azul.");},{enableHighAccuracy:true,maximumAge:3000,timeout:20000});}
    function validPoints(){if(!state.origin||!state.destination){showError("Debes definir el punto de inicio y el destino.");return false;}const same=Math.abs(state.origin.lat-state.destination.lat)<.00001&&Math.abs(state.origin.lng-state.destination.lng)<.00001;if(same){showError("El origen y el destino no pueden ser el mismo punto.");return false;}clearError();return true;}

    function showLoading(){if(!els.loading)return;els.loading.hidden=false;els.loading.setAttribute("aria-hidden","false");document.body.classList.add("route-processing-active");}
    function hideLoading(){if(!els.loading)return;els.loading.hidden=true;els.loading.setAttribute("aria-hidden","true");document.body.classList.remove("route-processing-active");}

    async function saveAndCalculate(){
        if(state.saving||!validPoints())return;
        state.saving=true;
        els.btnSaveCalculate.disabled=true;
        const originalButton=els.btnSaveCalculate.innerHTML;
        const result=await Swal.fire({
            title:"¿Guardar el destino y calcular rutas?",
            text:"Se guardará el acceso seleccionado y luego se generarán las alternativas con Dijkstra e IA predictiva.",
            icon:"question",showCancelButton:true,confirmButtonText:"Guardar y calcular",cancelButtonText:"Revisar puntos",
            confirmButtonColor:"#d71920",cancelButtonColor:"#23262b",reverseButtons:true
        });
        if(!result.isConfirmed){state.saving=false;els.btnSaveCalculate.disabled=false;return;}
        els.btnSaveCalculate.innerHTML='<span class="spinner-border spinner-border-sm" aria-hidden="true"></span> Calculando…';
        showLoading();
        try{
            const response=await fetch(config.dataset.guardarUrl,{method:"POST",headers:{"Content-Type":"application/json","X-CSRFToken":csrfToken(),"X-Requested-With":"XMLHttpRequest"},body:JSON.stringify({nombre:state.destination.name,latitud:state.destination.lat,longitud:state.destination.lng})});
            const data=await response.json();
            if(!response.ok||!data.ok)throw new Error(data.mensaje||"No se pudo guardar el destino.");
            const params=new URLSearchParams({origen_lat:state.origin.lat,origen_lon:state.origin.lng,origen_nombre:state.origin.name||"Punto de inicio",destino_lat:state.destination.lat,destino_lon:state.destination.lng,destino_nombre:state.destination.name||"Destino"});
            if(config.dataset.viajeId)params.set("viaje",config.dataset.viajeId);
            const nextUrl=`${config.dataset.rutasUrl}?${params.toString()}`;
            if(window.DistricTabLock&&typeof window.DistricTabLock.navigate==="function"){
                window.DistricTabLock.navigate(nextUrl);
            }else{
                window.location.assign(nextUrl);
            }
        }catch(error){hideLoading();showError(error.message);state.saving=false;els.btnSaveCalculate.disabled=false;els.btnSaveCalculate.innerHTML=originalButton;}
    }

    window.initDistricPointsReviewMap=function(){
        state.geocoder=new google.maps.Geocoder();
        const destination={lat:n(config.dataset.destinoLat),lng:n(config.dataset.destinoLon),name:config.dataset.destinoNombre||"Destino"};
        let origin={lat:n(config.dataset.origenLat),lng:n(config.dataset.origenLon),name:config.dataset.origenNombre||"Punto de inicio"};
        if(origin.lat===null||origin.lng===null)origin={lat:destination.lat,lng:destination.lng,name:"Ubicación por confirmar"};
        state.originMap=new google.maps.Map(document.getElementById("mapaOrigen"),{center:origin,zoom:17,mapTypeControl:true,fullscreenControl:true,streetViewControl:true,gestureHandling:"greedy"});
        state.destinationMap=new google.maps.Map(document.getElementById("mapaDestino"),{center:destination,zoom:17,mapTypeControl:true,fullscreenControl:true,streetViewControl:true,gestureHandling:"greedy"});
        state.originMarker=new google.maps.Marker({map:state.originMap,position:origin,draggable:true,icon:markerIcon("#2563eb"),title:"Punto de inicio"});
        state.destinationMarker=new google.maps.Marker({map:state.destinationMap,position:destination,draggable:true,icon:markerIcon("#d71920"),title:"Destino"});
        updateOrigin(origin,Boolean(config.dataset.origenLat));updateDestination(destination,false);
        state.originMarker.addListener("dragend",function(event){updateOrigin({lat:event.latLng.lat(),lng:event.latLng.lng(),name:"Inicio ajustado"},true);});
        state.destinationMarker.addListener("dragend",function(event){updateDestination({lat:event.latLng.lat(),lng:event.latLng.lng(),name:"Destino ajustado"},true);});
        state.originMap.addListener("click",function(event){updateOrigin({lat:event.latLng.lat(),lng:event.latLng.lng(),name:"Inicio ajustado"},true);});
        state.destinationMap.addListener("click",function(event){updateDestination({lat:event.latLng.lat(),lng:event.latLng.lng(),name:"Destino ajustado"},true);});
        if(!config.dataset.origenLat||!config.dataset.origenLon)getGps();
    };
    els.btnGps.addEventListener("click",getGps);
    els.btnCenterDestination.addEventListener("click",function(){state.destinationMap.panTo(state.destination);state.destinationMap.setZoom(18);});
    els.btnBack.addEventListener("click",function(){if(window.history.length>1)window.history.back();else window.location.href="/buscarlugares/";});
    els.btnSaveCalculate.addEventListener("click",saveAndCalculate);
    const key=config.dataset.googleMapsKey;if(!key){showError("No se configuró GOOGLE_MAPS_API_KEY.");return;}
    const script=document.createElement("script");script.src=`https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(key)}&v=weekly&callback=initDistricPointsReviewMap`;script.async=true;script.defer=true;script.onerror=function(){showError("No se pudo cargar Google Maps. Revisa la clave web y Maps JavaScript API.");};document.head.appendChild(script);
})();
