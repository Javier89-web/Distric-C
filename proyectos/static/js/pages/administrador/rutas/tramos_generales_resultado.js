(function(){
  "use strict";
  const mapNode=document.getElementById("generalResultMap");if(!mapNode)return;
  let routes=[],points=[];
  try{routes=JSON.parse(document.getElementById("generalResultRoutes").textContent||"[]");}catch(_e){}
  try{points=JSON.parse(document.getElementById("generalResultPoints").textContent||"[]");}catch(_e){}
  const colors=["#d71920","#7c3aed","#0f766e","#d97706","#2563eb","#0891b2","#23262b"];

  function validPoint(value){
    if(!value)return null;
    const lat=Number(value.lat!==undefined?value.lat:value[0]);
    const lng=Number(value.lon!==undefined?value.lon:(value.lng!==undefined?value.lng:value[1]));
    if(!Number.isFinite(lat)||!Number.isFinite(lng))return null;
    return {lat,lng};
  }

  function distanceSquaredMeters(a,b,latRef){
    const dy=(a.lat-b.lat)*110574;
    const cos=Math.max(Math.abs(Math.cos((latRef||a.lat)*Math.PI/180)),0.2);
    const dx=(a.lng-b.lng)*111320*cos;
    return dx*dx+dy*dy;
  }

  function projectOnSegment(point,a,b){
    const latRef=point.lat;
    const cos=Math.max(Math.abs(Math.cos(latRef*Math.PI/180)),0.2);
    const ax=a.lng*111320*cos, ay=a.lat*110574;
    const bx=b.lng*111320*cos, by=b.lat*110574;
    const px=point.lng*111320*cos, py=point.lat*110574;
    const dx=bx-ax, dy=by-ay;
    const den=dx*dx+dy*dy;
    let t=den<=1e-12?0:((px-ax)*dx+(py-ay)*dy)/den;
    t=Math.max(0,Math.min(1,t));
    const projected={lat:a.lat+t*(b.lat-a.lat),lng:a.lng+t*(b.lng-a.lng)};
    return {point:projected,t,d2:distanceSquaredMeters(point,projected,latRef)};
  }

  function nearestProjection(path,point){
    if(!point||path.length<2)return null;
    let best=null;
    for(let i=0;i<path.length-1;i++){
      const candidate=projectOnSegment(point,path[i],path[i+1]);
      candidate.index=i;
      candidate.progress=i+candidate.t;
      if(!best||candidate.d2<best.d2-0.01||(Math.abs(candidate.d2-best.d2)<=0.01&&candidate.progress<best.progress)){
        best=candidate;
      }
    }
    return best;
  }

  function appendUnique(target,point){
    if(!point)return;
    const last=target[target.length-1];
    if(!last||distanceSquaredMeters(last,point,point.lat)>0.16)target.push({lat:point.lat,lng:point.lng});
  }

  function clipPathToStops(path,startStop,endStop){
    if(path.length<2)return path;
    const start=nearestProjection(path,startStop);
    const end=nearestProjection(path,endStop);
    const maxSnapDistanceM=80;
    if(!start||!end||Math.sqrt(start.d2)>maxSnapDistanceM||Math.sqrt(end.d2)>maxSnapDistanceM)return path;
    if(start.progress>end.progress+0.000001)return path;

    const clipped=[];
    appendUnique(clipped,start.point);
    for(let i=start.index+1;i<=end.index;i++)appendUnique(clipped,path[i]);
    appendUnique(clipped,end.point);
    return clipped.length>=2?clipped:path;
  }

  window.initDistricGeneralRoutesResultMap=function(){
    const map=new google.maps.Map(mapNode,{center:{lat:-0.9352,lng:-78.6155},zoom:13,mapTypeControl:true,streetViewControl:false,fullscreenControl:true});
    const bounds=new google.maps.LatLngBounds();let has=false;
    const displayRoutes=[];

    routes.forEach((coords,index)=>{
      let visiblePath=(coords||[]).map(validPoint).filter(Boolean);
      if(visiblePath.length<2){displayRoutes.push(visiblePath);return;}

      // Corrección exclusivamente visual: si una geometría histórica conserva
      // una pequeña "cola" antes o después del punto numerado, la línea mostrada
      // se recorta exactamente entre los puntos compartidos del tramo. No se
      // modifica la ruta guardada, sus métricas ni el cálculo de Dijkstra.
      const startStop=validPoint(points[index]);
      const endStop=validPoint(points[index+1]);
      if(startStop&&endStop){
        visiblePath=clipPathToStops(visiblePath,startStop,endStop);
      }

      if(displayRoutes.length){
        const previous=displayRoutes[displayRoutes.length-1];
        if(previous&&previous.length){
          const previousEnd=previous[previous.length-1];
          const gap=Math.sqrt(distanceSquaredMeters(previousEnd,visiblePath[0],previousEnd.lat));
          if(gap<=12){
            visiblePath[0]={lat:previousEnd.lat,lng:previousEnd.lng};
          }
        }
      }
      displayRoutes.push(visiblePath);

      visiblePath.forEach(p=>{bounds.extend(p);has=true;});
      new google.maps.Polyline({
        path:visiblePath,
        map,
        strokeColor:colors[index%colors.length],
        strokeOpacity:.95,
        strokeWeight:5
      });
    });

    points.forEach((point)=>{
      const pos=validPoint(point);if(!pos)return;
      bounds.extend(pos);has=true;
      new google.maps.Marker({
        position:pos,
        map,
        label:{text:String(point.numero),color:"#ffffff",fontWeight:"700"},
        title:point.nombre||`Punto ${point.numero}`
      });
    });
    if(has)map.fitBounds(bounds,55);
  };

  const tabs=Array.from(document.querySelectorAll("[data-result-segment-tab]"));
  const panels=Array.from(document.querySelectorAll("[data-result-segment-panel]"));
  function showSegment(index){
    tabs.forEach((tab,i)=>{
      const active=i===index;
      tab.classList.toggle("active",active);
      tab.setAttribute("aria-selected",active?"true":"false");
    });
    panels.forEach((panel,i)=>{panel.hidden=i!==index;});
  }
  tabs.forEach((tab,index)=>tab.addEventListener("click",()=>showSegment(index)));
  if(tabs.length)showSegment(0);

  const key=mapNode.dataset.googleMapsKey;if(!key)return;const script=document.createElement("script");script.src=`https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(key)}&v=weekly&callback=initDistricGeneralRoutesResultMap`;script.async=true;script.defer=true;document.head.appendChild(script);
})();
