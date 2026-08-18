from django.urls import path

from . import views
from . import views_rutas_predictivas as rutas_views
from .views import ManifestView, ServiceWorkerView, offline


urlpatterns = [

    # ==========================================================
    # SEGURIDAD / LOGIN
    # ==========================================================
    path(
        '',
        views.login_usuario,
        name='login'
    ),

    path(
        'login/',
        views.login_usuario
    ),

    path(
        'logout/',
        views.logout_usuario,
        name='logout'
    ),

    path(
        'tab-bloqueada/',
        views.tab_bloqueada,
        name='tab_bloqueada'
    ),

    # ==========================================================
    # PANEL ADMINISTRADOR
    # ==========================================================
    path(
        'adminpanel/',
        views.admin_panel,
        name='admin_panel'
    ),

    # ==========================================================
    # USUARIOS
    # ==========================================================
    path(
        'inicio/',
        views.inicio,
        name='inicio'
    ),

    path(
        'nuevousuario/',
        views.nuevousuario,
        name='nuevousuario'
    ),

    path(
        'perfilusuario/',
        views.perfilusuario,
        name='perfilusuario'
    ),

    path(
        'guardarusuario/',
        views.guardarusuario,
        name='guardarusuario'
    ),

    path(
        'api/administracion/validar-clave-superusuario/',
        views.api_validar_clave_superusuario,
        name='api_validar_clave_superusuario'
    ),

    path(
        'api/administracion/validar-codigo-administrador/',
        views.api_validar_codigo_administrador,
        name='api_validar_codigo_administrador'
    ),

    path(
        'api/cedula/<str:cedula>/',
        views.api_consultar_cedula,
        name='api_consultar_cedula'
    ),

    path(
        'editarusuario/<int:id>/',
        views.editarusuario,
        name='editarusuario'
    ),

    path(
        'procesareditarusuario/',
        views.procesareditarusuario,
        name='procesareditarusuario'
    ),

    path(
        'listadousuario/',
        views.listadousuario,
        name='listadousuario'
    ),

    path(
        'editarusuarioadministrador/<int:id>/',
        views.editarusuarioadministrador,
        name='editarusuarioadministrador'
    ),

    path(
        'procesareditarusuarioadministrador/',
        views.procesareditarusuarioadministrador,
        name='procesareditarusuarioadministrador'
    ),

    path(
        'eliminarusuarioadministrador/<int:id>/',
        views.eliminarusuarioadministrador,
        name='eliminarusuarioadministrador'
    ),

    path(
        'activarusuarioadministrador/<int:id>/',
        views.activarusuarioadministrador,
        name='activarusuarioadministrador'
    ),

    path(
        'inactivarusuarioadministrador/<int:id>/',
        views.inactivarusuarioadministrador,
        name='inactivarusuarioadministrador'
    ),

    # ==========================================================
    # DOCUMENTOS / CHECKLIST
    # ==========================================================
    path(
        'creardocumento/',
        views.creardocumento,
        name='creardocumento'
    ),

    # ==========================================================
    # VEHÍCULOS DEL ADMINISTRADOR
    # ==========================================================
    path(
        'listadocarros/',
        views.listadocarros,
        name='listadocarros'
    ),

    path(
        'vehiculos/nuevo/',
        views.nuevovehiculoadmin,
        name='nuevovehiculoadmin'
    ),

    path(
        'vehiculos/guardar/',
        views.guardarvehiculoadmin,
        name='guardarvehiculoadmin'
    ),

    path(
        'vehiculos/detalle/<int:id>/',
        views.detallevehiculoadmin,
        name='detallevehiculoadmin'
    ),

    path(
        'vehiculos/editar/<int:id>/',
        views.editarvehiculoadmin,
        name='editarvehiculoadmin'
    ),

    path(
        'vehiculos/procesar-edicion/',
        views.procesareditarvehiculoadmin,
        name='procesareditarvehiculoadmin'
    ),

    path(
        'vehiculos/asignar/<int:id>/',
        views.asignarvehiculoadmin,
        name='asignarvehiculoadmin'
    ),

    path(
        'vehiculos/desasignar/<int:id>/',
        views.desasignarvehiculoadmin,
        name='desasignarvehiculoadmin'
    ),

    path(
        'vehiculos/eliminar/<int:id>/',
        views.eliminarvehiculoadmin,
        name='eliminarvehiculoadmin'
    ),

    # ==========================================================
    # VEHÍCULOS DEL USUARIO
    # ==========================================================
    path(
        'nuevovehiculo/<int:id_usuario>/',
        views.nuevovehiculo,
        name='nuevovehiculo'
    ),

    path(
        'guardarvehiculo/',
        views.guardarvehiculo,
        name='guardarvehiculo'
    ),

    path(
        'listadovehiculo/',
        views.listadovehiculo,
        name='listadovehiculo'
    ),

    path(
        'listadovista/<int:id_usuario>/',
        views.listadovista,
        name='listadovista'
    ),

    path(
        'eliminarvehiculo/<int:id>/',
        views.eliminarvehiculo,
        name='eliminarvehiculo'
    ),

    path(
        'editarvehiculo/<int:id>/',
        views.editarvehiculo,
        name='editarvehiculo'
    ),

    path(
        'procesareditarvehiculo/',
        views.procesareditarvehiculo,
        name='procesareditarvehiculo'
    ),

# ==========================================================
# CATÁLOGO DE PRODUCTOS PARA CARGA - ADMINISTRADOR
# ==========================================================
path(
    'productos-carga/',
    views.listadoproductoscarga,
    name='listadoproductoscarga'
),

path(
    'productos-carga/nuevo/',
    views.nuevoproductocarga,
    name='nuevoproductocarga'
),

path(
    'productos-carga/guardar/',
    views.guardarproductocarga,
    name='guardarproductocarga'
),

path(
    'productos-carga/editar/<int:id>/',
    views.editarproductocarga,
    name='editarproductocarga'
),

path(
    'productos-carga/procesar-edicion/',
    views.procesareditarproductocarga,
    name='procesareditarproductocarga'
),

path(
    'productos-carga/cambiar-estado/<int:id>/',
    views.cambiarestadoproductocarga,
    name='cambiarestadoproductocarga'
),

path(
    'productos-carga/eliminar/<int:id>/',
    views.eliminarproductocarga,
    name='eliminarproductocarga'
),

path(
    'combustible/precios/',
    views.precioscombustibleadmin,
    name='precioscombustibleadmin'
),

path(
    'combustible/precios/historial/pdf/',
    views.historialprecioscombustiblepdf,
    name='historialprecioscombustiblepdf'
),

# ==========================================================
# CONSULTA DE CARGAS - ADMINISTRADOR
# ==========================================================
path(
    'consulta-cargas/',
    views.consultacargasadmin,
    name='consultacargasadmin'
),

# ==========================================================
# PLANIFICACIÓN DE CARGAS - ADMINISTRADOR
# ==========================================================
path(
    'plan-cargas/',
    views.listadoplanescarga,
    name='listadoplanescarga'
),

path(
    'plan-cargas/crear/',
    views.crearplancargadesdeformulario,
    name='crearplancargadesdeformulario'
),

path(
    'plan-cargas/crear/<int:id_vehiculo>/',
    views.crearplancarga,
    name='crearplancarga'
),

path(
    'plan-cargas/preparar/<int:id>/',
    views.prepararplancarga,
    name='prepararplancarga'
),

path(
    'plan-cargas/guardar/<int:id>/',
    views.guardarplancarga,
    name='guardarplancarga'
),

path(
    'plan-cargas/detalle/<int:id>/',
    views.detalleplancarga,
    name='detalleplancarga'
),

path(
    'plan-cargas/detalle/<int:id>/pdf/',
    views.pdfplancarga,
    name='pdfplancarga'
),

path(
    'plan-cargas/cancelar/<int:id>/',
    views.cancelarplancarga,
    name='cancelarplancarga'
),

path(
    'plan-cargas/reactivar/<int:id>/',
    views.reactivarplancarga,
    name='reactivarplancarga'
),

path(
    'plan-cargas/<int:id>/paradas/',
    views.gestionarparadasplancarga,
    name='gestionarparadasplancarga'
),

path(
    'plan-cargas/<int:id>/paradas/agregar/',
    views.agregarparadaplancarga,
    name='agregarparadaplancarga'
),

path(
    'plan-cargas/paradas/<int:id>/editar/',
    views.editarparadaplancarga,
    name='editarparadaplancarga'
),

path(
    'plan-cargas/paradas/<int:id>/eliminar/',
    views.eliminarparadaplancarga,
    name='eliminarparadaplancarga'
),

path(
    'plan-cargas/paradas/<int:id>/guardar-entrega/',
    views.guardarentregaparada,
    name='guardarentregaparada'
),

path(
    'plan-cargas/entregas/<int:id>/eliminar/',
    views.eliminarentregaparada,
    name='eliminarentregaparada'
),

path(
    'plan-cargas/<int:id>/marcar-listo/',
    views.marcarplancargalisto,
    name='marcarplancargalisto'
),

path(
    'plan-cargas/<int:id>/volver-borrador/',
    views.volverplancargaborrador,
    name='volverplancargaborrador'
),

path(
    'plan-cargas/<int:id>/confirmar/',
    views.confirmarplancargaadmin,
    name='confirmarplancargaadmin'
),

path(
    'plan-cargas/<int:id>/reabrir-confirmada/',
    views.reabrirplancargaconfirmada,
    name='reabrirplancargaconfirmada'
),

    # ==========================================================
    # CARGAS ASIGNADAS - USUARIO
    # ==========================================================
    path(
        'listadocarga/',
        views.listadocarga,
        name='listadocarga'
    ),

    path(
        'carga-asignada/<int:id>/',
        views.detallecargausuario,
        name='detallecargausuario'
    ),

    path(
        'carga-asignada/<int:id>/agregar-producto/',
        views.agregarproductocargausuario,
        name='agregarproductocargausuario'
    ),

    path(
        'carga-detalle/<int:id>/ajustar/',
        views.ajustardetallecargausuario,
        name='ajustardetallecargausuario'
    ),

    path(
        'carga-detalle/<int:id>/restaurar/',
        views.restaurardetallecargausuario,
        name='restaurardetallecargausuario'
    ),

    path(
        'carga-asignada/<int:id>/confirmar/',
        views.confirmarcargausuario,
        name='confirmarcargausuario'
    ),

    path(
        'carga-entrega/<int:id>/ajustar/',
        views.ajustarentregacargausuario,
        name='ajustarentregacargausuario'
    ),

    path(
        'carga-entrega/<int:id>/restaurar/',
        views.restaurarentregacargausuario,
        name='restaurarentregacargausuario'
    ),

    # ==========================================================
    # PLANIFICACIÓN Y REPORTES DE RUTAS - ADMINISTRADOR
    # ==========================================================
    path(
        'administrador/rutas/tramos-generales/',
        rutas_views.admin_tramos_generales,
        name='admin_tramos_generales'
    ),

    path(
        'administrador/rutas/tramos-generales/calcular/',
        rutas_views.admin_calcular_tramos_generales,
        name='admin_calcular_tramos_generales'
    ),

    path(
        'administrador/rutas/tramos-generales/<int:id_viaje>/',
        rutas_views.admin_detalle_tramos_generales,
        name='admin_detalle_tramos_generales'
    ),

    path(
        'administrador/rutas/tramos-generales/<int:id_viaje>/pdf/',
        rutas_views.admin_pdf_tramos_generales,
        name='admin_pdf_tramos_generales'
    ),

    path(
        'administrador/rutas/planificacion/',
        rutas_views.admin_planificacion_rutas,
        name='admin_planificacion_rutas'
    ),

    path(
        'administrador/rutas/planificacion/iniciar/',
        rutas_views.admin_iniciar_prueba_rutas,
        name='admin_iniciar_prueba_rutas'
    ),

    path(
        'administrador/rutas/planificacion/salir/',
        rutas_views.admin_salir_prueba_rutas,
        name='admin_salir_prueba_rutas'
    ),

    path(
        'administrador/rutas/reportes/',
        rutas_views.admin_reportes_viajes,
        name='admin_reportes_viajes'
    ),

    path(
        'administrador/rutas/reportes/<int:id_viaje>/',
        rutas_views.admin_detalle_viaje,
        name='admin_detalle_viaje'
    ),

    path(
        'administrador/rutas/reportes/<int:id_viaje>/pdf/',
        rutas_views.admin_reporte_pdf_viaje,
        name='admin_reporte_pdf_viaje'
    ),

    # ==========================================================
    # MAPA / LUGARES GUARDADOS
    # ==========================================================
    path(
        'buscarlugares/',
        rutas_views.buscarlugares,
        name='buscarlugares'
    ),

    path(
        'lugar/<str:lat>/<str:lon>/',
        rutas_views.ver_lugar,
        name='ver_lugar'
    ),

    path(
        'guardar_lugar/<str:lat>/<str:lon>/<path:nombre>/',
        rutas_views.guardar_lugar,
        name='guardar_lugar'
    ),

    path(
        'eliminar_lugar/<int:id>/',
        rutas_views.eliminar_lugar,
        name='eliminar_lugar'
    ),

    # ==========================================================
    # RUTAS / RECORRIDO / HISTORIAL
    # ==========================================================
    path(
        'rutas/',
        rutas_views.rutas,
        name='rutas'
    ),

    path(
        'api/ruta-optima/',
        rutas_views.api_ruta_optima,
        name='api_ruta_optima'
    ),

    path(
        'recorrido/',
        rutas_views.recorrido,
        name='recorrido'
    ),

    path(
        'historial/',
        rutas_views.historial,
        name='historial'
    ),

    path(
        'historial/eliminar/<int:id_viaje>/',
        rutas_views.eliminar_viaje_historial,
        name='eliminar_viaje_historial'
    ),

    path(
        'api/lugares/buscar/',
        rutas_views.api_buscar_destinos,
        name='api_buscar_destinos'
    ),

    path(
        'api/lugares/guardar/',
        rutas_views.api_guardar_lugar,
        name='api_guardar_lugar'
    ),

    path(
        'rutas/opcion/<int:id_ruta>/iniciar/',
        rutas_views.iniciar_ruta_seleccionada,
        name='iniciar_ruta_seleccionada'
    ),

    path(
        'rutas/tramo/<int:id_tramo>/cancelar/',
        rutas_views.cancelar_generacion_ruta,
        name='cancelar_generacion_ruta'
    ),

    path(
        'recorrido/<int:id_tramo>/',
        rutas_views.recorrido_tramo,
        name='recorrido_tramo'
    ),

    path(
        'api/tramos/<int:id_tramo>/iniciar/',
        rutas_views.api_iniciar_tramo,
        name='api_iniciar_tramo'
    ),

    path(
        'api/tramos/<int:id_tramo>/pausar/',
        rutas_views.api_pausar_tramo,
        name='api_pausar_tramo'
    ),

    path(
        'api/tramos/<int:id_tramo>/ubicacion/',
        rutas_views.api_registrar_ubicacion_tramo,
        name='api_registrar_ubicacion_tramo'
    ),

    path(
        'tramos/<int:id_tramo>/finalizar/',
        rutas_views.finalizar_tramo,
        name='finalizar_tramo'
    ),

    path(
        'tramos/<int:id_tramo>/resumen/',
        rutas_views.resumen_tramo,
        name='resumen_tramo'
    ),

    path(
        'viajes/<int:id_viaje>/nueva-ruta/',
        rutas_views.nueva_ruta_viaje,
        name='nueva_ruta_viaje'
    ),

    path(
        'viajes/<int:id_viaje>/nueva-ruta-prueba/',
        rutas_views.nueva_ruta_viaje_prueba,
        name='nueva_ruta_viaje_prueba'
    ),

    path(
        'viajes/<int:id_viaje>/finalizar/',
        rutas_views.finalizar_viaje,
        name='finalizar_viaje'
    ),

    path(
        'historial/viaje/<int:id_viaje>/pdf/',
        rutas_views.reporte_pdf_viaje,
        name='reporte_pdf_viaje'
    ),

    path(
        'historial/viaje/<int:id_viaje>/',
        rutas_views.detalle_historial_viaje,
        name='detalle_historial_viaje'
    ),

    # ==========================================================
    # CALENDARIO ADMINISTRADOR
    # ==========================================================
    path(
        'panel/calendario/',
        views.admin_calendario,
        name='admin_calendario'
    ),

    path(
        'panel/calendario/eventos/',
        views.admin_eventos_json,
        name='admin_eventos_json'
    ),

    path(
        'panel/calendario/crear/',
        views.admin_evento_crear,
        name='admin_evento_crear'
    ),

    path(
        'panel/calendario/lista/',
        views.listar_eventos_admin,
        name='lista_eventos_admin'
    ),

    path(
        'panel/calendario/editar/<int:id_evento>/',
        views.editar_evento_admin,
        name='editar_evento_admin'
    ),

    path(
        'panel/calendario/eliminar/<int:id_evento>/',
        views.eliminar_evento_admin,
        name='eliminar_evento_admin'
    ),

    # ==========================================================
    # ASIGNACIONES
    # ==========================================================
    path(
        'lista_asignaciones/',
        views.lista_asignaciones,
        name='lista_asignaciones'
    ),

    path(
        'crear_asignacion/',
        views.crear_asignacion,
        name='crear_asignacion'
    ),

    path(
        'asignaciones/editar/<int:id>/',
        views.editar_asignacion,
        name='editar_asignacion'
    ),

    path(
        'asignaciones/eliminar/<int:id>/',
        views.eliminar_asignacion,
        name='eliminar_asignacion'
    ),

    # ==========================================================
    # PROVEEDORES
    # ==========================================================
    path(
        'listadoproveedor/',
        views.listadoproveedor,
        name='listadoproveedor'
    ),

    path(
        'nuevoproveedor/',
        views.nuevoproveedor,
        name='nuevoproveedor'
    ),

    path(
        'guardarproveedor/',
        views.guardarproveedor,
        name='guardarproveedor'
    ),

    path(
        'eliminarproveedor/<int:id>/',
        views.eliminarproveedor,
        name='eliminarproveedor'
    ),

    path(
        'editarproveedor/<int:id>/',
        views.editarproveedor,
        name='editarproveedor'
    ),

    path(
        'procesareditarproveedor/',
        views.procesareditarproveedor,
        name='procesareditarproveedor'
    ),

    # ==========================================================
    # PEDIDOS
    # ==========================================================
    path(
        'listadopedido/',
        views.listadopedido,
        name='listadopedido'
    ),

    path(
        'nuevopedido/',
        views.nuevopedido,
        name='nuevopedido'
    ),

    path(
        'guardarpedido/',
        views.guardarpedido,
        name='guardarpedido'
    ),

    path(
        'editarpedido/<int:id>/',
        views.editarpedido,
        name='editarpedido'
    ),

    path(
        'procesareditarpedido/',
        views.procesareditarpedido,
        name='procesareditarpedido'
    ),

    path(
        'eliminarpedido/<int:id>/',
        views.eliminarpedido,
        name='eliminarpedido'
    ),

    # ==========================================================
    # DETALLES DE PEDIDO
    # ==========================================================
    path(
        'listadodetalle/<int:id_pedido>/',
        views.listadodetalle,
        name='listadodetalle'
    ),

    path(
        'nuevodetalle/<int:id_pedido>/',
        views.nuevodetalle,
        name='nuevodetalle'
    ),

    path(
        'guardardetalle/',
        views.guardardetalle,
        name='guardardetalle'
    ),

    path(
        'editardetalle/<int:id>/',
        views.editardetalle,
        name='editardetalle'
    ),

    path(
        'procesareditardetalle/',
        views.procesareditardetalle,
        name='procesareditardetalle'
    ),

    path(
        'eliminardetalle/<int:id>/',
        views.eliminardetalle,
        name='eliminardetalle'
    ),

    path(
        'agregarproducto/',
        views.seleccionar_pedido_detalle,
        name='agregarproducto'
    ),

    path(
        'redirigir_detalle/lista/',
        views.redirigir_detalle_lista,
        name='redirigir_detalle_lista'
    ),

    path(
        'redirigir_detalle/nuevo/',
        views.redirigir_detalle_nuevo,
        name='redirigir_detalle_nuevo'
    ),

    # ==========================================================
    # NOTIFICACIONES / USUARIO
    # ==========================================================
    path(
        'pedidosusuario/',
        views.pedidosusuario,
        name='pedidosusuario'
    ),

    path(
        'panel/usuario/eventos/',
        views.usuario_eventos_json,
        name='usuario_eventos_json'
    ),

    path(
        'panel/notificacion/evento/',
        views.usuario_toast_evento,
        name='usuario_toast_evento'
    ),

    path(
        'usuario/asignacion/<int:asig_id>/estado/',
        views.usuario_cambiar_estado,
        name='usuario_cambiar_estado'
    ),

    path(
        'usuario/asignacion/<int:asig_id>/motivo-atrasado/',
        views.usuario_motivo_atrasado,
        name='usuario_motivo_atrasado'
    ),

    path(
        'usuario/asignacion/<int:asig_id>/motivo-no-completado/',
        views.usuario_motivo_no_completado,
        name='usuario_motivo_no_completado'
    ),

    # ==========================================================
    # REPORTES DE ASIGNACIONES
    # ==========================================================
    path(
        'panel/asignaciones/reporte/',
        views.reporte_asignaciones,
        name='reporte_asignaciones'
    ),

    path(
        'panel/asignaciones/<int:asig_id>/motivo/',
        views.reporte_ver_motivo,
        name='reporte_ver_motivo'
    ),

    # ==========================================================
    # REPORTES GENERALES
    # ==========================================================
    path(
        'reporteviaje/',
        views.reporteviaje,
        name='reporteviaje'
    ),

    path(
        'reportehistorial/',
        views.reportehistorial,
        name='reportehistorial'
    ),

    # ==========================================================
    # FACTURAS
    # ==========================================================
    path(
        'nuevafactura/',
        views.nuevafactura,
        name='nuevafactura'
    ),

    path(
        'crear_factura/',
        views.crear_factura,
        name='crear_factura'
    ),

    path(
        'ver_factura/<int:id_factura>/',
        views.ver_factura,
        name='ver_factura'
    ),

    path(
        'listadofacturas/',
        views.listado_facturas,
        name='listado_facturas'
    ),

    path(
        'eliminarfactura/<int:id>/',
        views.eliminar_factura,
        name='eliminar_factura'
    ),

    path(
        'factura/pdf/<int:id_factura>/',
        views.factura_pdf,
        name='factura_pdf'
    ),

    # ==========================================================
    # SALVOCONDUCTOS
    # ==========================================================
    path(
        'salvoconductos/',
        views.salvoconductos,
        name='salvoconductos'
    ),

    path(
        'nuevosalvoconducto/',
        views.nuevosalvoconducto,
        name='nuevosalvoconducto'
    ),

    path(
        'editarsalvoconducto/<int:id>/',
        views.editarsalvoconducto,
        name='editarsalvoconducto'
    ),

    path(
        'eliminarsalvoconducto/<int:id>/',
        views.eliminarsalvoconducto,
        name='eliminarsalvoconducto'
    ),

    path(
        'salvoconducto/pdf/<int:id>/',
        views.generar_pdf_salvoconducto,
        name='pdf_salvoconducto'
    ),

    path(
        'validar/salvoconducto/<int:id>/',
        views.validar_salvoconducto,
        name='validar_salvoconducto'
    ),

    # ==========================================================
    # PAGOS
    # ==========================================================
    path(
        'pago/<int:id_factura>/',
        views.registrar_pago,
        name='registrar_pago'
    ),

    path(
        'guardar_pago/',
        views.guardar_pago,
        name='guardar_pago'
    ),

    path(
        'pagos/',
        views.listado_pagos,
        name='listado_pagos'
    ),

    path(
        'pagos/ver/<int:id_pago>/',
        views.ver_pago,
        name='ver_pago'
    ),

    path(
        'pagos/editar/<int:id_pago>/',
        views.editar_pago,
        name='editar_pago'
    ),

    path(
        'pagos/eliminar/<int:id_pago>/',
        views.eliminar_pago,
        name='eliminar_pago'
    ),

    # ==========================================================
    # PWA
    # ==========================================================
    path(
        'manifest.webmanifest',
        ManifestView.as_view(),
        name='manifest'
    ),

    path(
        'service-worker.js',
        ServiceWorkerView.as_view(),
        name='service-worker'
    ),

    path(
        'offline/',
        offline,
        name='offline'
    ),
]