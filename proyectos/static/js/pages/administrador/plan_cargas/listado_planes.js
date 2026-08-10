document.addEventListener("DOMContentLoaded",function(){
    const search=document.getElementById("buscarVehiculoCarga");
    const cards=document.querySelectorAll(".vehicle-card");
    if(search){search.addEventListener("input",function(){const value=this.value.toLowerCase().trim();cards.forEach(function(card){card.hidden=!card.dataset.busqueda.toLowerCase().includes(value);});});}
    document.querySelectorAll(".js-progress-width").forEach(function(bar){const value=Math.max(0,Math.min(100,Number.parseFloat(bar.dataset.progress||"0")));bar.style.width=`${value}%`;});

    const queryForm=document.getElementById("formFechaCarga");const queryDate=document.getElementById("fechaPlanCarga");const queryError=document.getElementById("errorFechaPlanCarga");
    function fieldError(input,error,message){input.classList.toggle("input-error",Boolean(message));error.textContent=message||"";error.classList.toggle("visible",Boolean(message));}
    if(queryForm&&queryDate){queryForm.addEventListener("submit",function(event){if(!queryDate.value){event.preventDefault();fieldError(queryDate,queryError,"Selecciona una fecha para consultar.");}});queryDate.addEventListener("change",function(){fieldError(queryDate,queryError,"");if(queryDate.value&&!window.DistricSubmitGuard?.isLocked(queryForm))queryForm.requestSubmit();});}

    const createForm=document.getElementById("formCrearCarga");const vehicle=document.getElementById("vehiculoNuevaCarga");const createDate=document.getElementById("fechaNuevaCarga");const vehicleError=document.getElementById("errorVehiculoNuevaCarga");const createDateError=document.getElementById("errorFechaNuevaCarga");
    if(createForm){createForm.addEventListener("submit",function(event){let valid=true;fieldError(vehicle,vehicleError,"");fieldError(createDate,createDateError,"");if(!vehicle.value){fieldError(vehicle,vehicleError,"Selecciona el vehículo que llevará la carga.");valid=false;}if(!createDate.value){fieldError(createDate,createDateError,"Selecciona la fecha de la nueva carga.");valid=false;}else if(createDate.value<createDate.min||createDate.value>createDate.max){fieldError(createDate,createDateError,"La fecha debe estar entre hoy y los próximos seis meses.");valid=false;}if(!valid)event.preventDefault();});[vehicle,createDate].forEach(function(input){input.addEventListener("input",function(){if(input===vehicle)fieldError(vehicle,vehicleError,"");else fieldError(createDate,createDateError,"");});});}
});
