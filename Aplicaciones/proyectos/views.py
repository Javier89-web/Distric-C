"""
Vistas principales de la aplicación Distric C.

Incluye la administración de usuarios, vehículos, productos, cargas,
mapas y rutas. Las validaciones sensibles se realizan también en el
servidor para no depender únicamente de JavaScript.
"""
import calendar
import json
import random
import re
from datetime import datetime, timedelta
from decimal import Decimal

import requests
from django.conf import settings
from django.core.cache import cache
from django.contrib import messages
from django.core.files.storage import default_storage
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Count, Max, Prefetch, Q, Sum
from django.db.models.deletion import ProtectedError
from django.db.models.functions import Round, TruncMonth
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time
from django.utils.timezone import now
from django.views.decorators.http import require_GET, require_POST

# >>> IA PREDICTIVA / GOOGLE API
# Import seguro: si falta alguno de estos archivos, views.py no se rompe.
try:
    from Aplicaciones.proyectos.servicios_google import obtener_factores_google
except Exception:
    obtener_factores_google = None

try:
    from Aplicaciones.proyectos.ia_predictiva import predecir_consumo_combustible
except Exception:
    predecir_consumo_combustible = None
# <<< IA PREDICTIVA / GOOGLE API


# ==========================================================
# GOOGLE ROUTES API COMO RESPALDO DE RUTA VEHICULAR
# ==========================================================
GOOGLE_ROUTES_CACHE_SEGUNDOS = 600


def _api_key_google_servidor():
    """
    Usa la clave de servidor para Google Routes API.
    Si no existe, intenta usar GOOGLE_MAPS_API_KEY como respaldo local.
    """
    return (
        getattr(settings, "GOOGLE_MAPS_SERVER_API_KEY", "")
        or getattr(settings, "GOOGLE_MAPS_API_KEY", "")
        or ""
    )


def _redondear_coord_google(valor, decimales=4):
    try:
        return round(float(valor), decimales)
    except Exception:
        return valor


def _duracion_google_a_segundos(valor):
    """
    Convierte duraciones de Google tipo '325s' o '325.5s' a segundos.
    """
    if not valor:
        return 0.0

    valor = str(valor).strip().lower().replace("s", "")

    try:
        return float(valor)
    except Exception:
        return 0.0


def decodificar_polyline_google(encoded):
    """
    Decodifica una polilínea encodedPolyline de Google.
    Devuelve coordenadas en formato [[lat, lon], [lat, lon], ...].
    """
    if not encoded:
        return []

    coords = []
    index = 0
    lat = 0
    lon = 0

    try:
        while index < len(encoded):
            result = 0
            shift = 0

            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break

            dlat = ~(result >> 1) if (result & 1) else (result >> 1)
            lat += dlat

            result = 0
            shift = 0

            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break

            dlng = ~(result >> 1) if (result & 1) else (result >> 1)
            lon += dlng

            coords.append([lat / 1e5, lon / 1e5])
    except Exception:
        return []

    return coords


def obtener_ruta_google_respaldo(lat_origen, lon_origen, lat_destino, lon_destino):
    """
    Calcula una ruta vehicular con Google Routes API.
    Se usa únicamente como respaldo cuando Dijkstra/OSMnx genera una ruta exagerada.
    """
    api_key = _api_key_google_servidor()

    if not api_key:
        return {
            "disponible": False,
            "mensaje": "No existe GOOGLE_MAPS_SERVER_API_KEY ni GOOGLE_MAPS_API_KEY.",
            "coords": [],
            "distancia_km": None,
            "tiempo_min": None,
        }

    cache_key = (
        "google_routes_respaldo:"
        f"{_redondear_coord_google(lat_origen)}:{_redondear_coord_google(lon_origen)}:"
        f"{_redondear_coord_google(lat_destino)}:{_redondear_coord_google(lon_destino)}"
    )

    cacheado = cache.get(cache_key)
    if cacheado:
        cacheado["desde_cache"] = True
        return cacheado

    url = "https://routes.googleapis.com/directions/v2:computeRoutes"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline",
    }

    payload = {
        "origin": {
            "location": {
                "latLng": {
                    "latitude": float(lat_origen),
                    "longitude": float(lon_origen),
                }
            }
        },
        "destination": {
            "location": {
                "latLng": {
                    "latitude": float(lat_destino),
                    "longitude": float(lon_destino),
                }
            }
        },
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
        "computeAlternativeRoutes": False,
        "languageCode": "es-419",
        "units": "METRIC",
        "polylineQuality": "HIGH_QUALITY",
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)

        if response.status_code != 200:
            return {
                "disponible": False,
                "mensaje": f"Google Routes API respondió {response.status_code}: {response.text[:200]}",
                "coords": [],
                "distancia_km": None,
                "tiempo_min": None,
            }

        data = response.json()
        routes = data.get("routes", [])

        if not routes:
            return {
                "disponible": False,
                "mensaje": "Google no devolvió rutas.",
                "coords": [],
                "distancia_km": None,
                "tiempo_min": None,
            }

        route = routes[0]

        distancia_m = float(route.get("distanceMeters") or 0)
        duracion_seg = _duracion_google_a_segundos(route.get("duration"))
        encoded_polyline = route.get("polyline", {}).get("encodedPolyline")
        coords = decodificar_polyline_google(encoded_polyline)

        if not coords:
            return {
                "disponible": False,
                "mensaje": "Google devolvió ruta, pero no se pudo decodificar la polilínea.",
                "coords": [],
                "distancia_km": None,
                "tiempo_min": None,
            }

        resultado = {
            "disponible": True,
            "fuente": "Google Routes API",
            "desde_cache": False,
            "coords": coords,
            "distancia_km": round(distancia_m / 1000, 3),
            "tiempo_min": round(duracion_seg / 60, 2),
            "consultado_en": timezone.localtime().strftime("%Y-%m-%d %H:%M"),
            "mensaje": "Ruta obtenida correctamente con Google Routes API.",
        }

        cache.set(cache_key, resultado, GOOGLE_ROUTES_CACHE_SEGUNDOS)
        return resultado

    except Exception as e:
        return {
            "disponible": False,
            "mensaje": f"Error consultando Google Routes API: {str(e)}",
            "coords": [],
            "distancia_km": None,
            "tiempo_min": None,
        }


def ruta_local_es_exagerada(distancia_local_km, tiempo_local_min, ruta_google):
    """
    Decide si la ruta de Dijkstra/OSMnx salió demasiado larga frente a Google.

    Reglas:
    - Google debe estar disponible.
    - La ruta local debe superar por 35% la distancia de Google.
    - Además debe haber al menos 0.50 km de diferencia.
    - También se valida si el tiempo local supera mucho al tiempo Google.
    """
    if not ruta_google or not ruta_google.get("disponible"):
        return False

    distancia_google = ruta_google.get("distancia_km")
    tiempo_google = ruta_google.get("tiempo_min")

    if not distancia_google or not tiempo_google:
        return False

    if distancia_local_km <= 0 or tiempo_local_min <= 0:
        return False

    diferencia_km = float(distancia_local_km) - float(distancia_google)
    factor_distancia = float(distancia_local_km) / float(distancia_google)
    factor_tiempo = float(tiempo_local_min) / float(tiempo_google) if tiempo_google > 0 else 1

    if diferencia_km >= 0.50 and factor_distancia >= 1.35:
        return True

    if factor_tiempo >= 1.60 and diferencia_km >= 0.30:
        return True

    return False

from .catalogo_inventario import (
    catalogo_productos,
    codigo_catalogo_por_nombre,
    marcas_catalogo,
    producto_catalogo_por_codigo,
    peso_estimado_presentacion,
)

from .pdf_branding import draw_pdf_logos, draw_pdf_watermark, draw_simple_pdf_branding
from .reportes_combustible import construir_pdf_historial_precios

from .models import (
    Administrador,
    AjusteCargaUsuario,
    AsignacionEvento,
    CargaVehiculo,
    ChecklistVehiculo,
    DetallePedido,
    DetallePlanCarga,
    EntregaPlanCarga,
    EventoAdmin,
    Factura,
    Lugarguardado,
    NodoMapa,
    TramoVial,
    Pago,
    ParadaPlanCarga,
    PlanCarga,
    Pedido,
    PrecioCombustible,
    HistorialPrecioCombustible,
    ProductoCarga,
    Proveedor,
    RendimientoVehiculoTipo,
    RutaOpcion,
    Salvoconducto,
    UbicacionVehiculo,
    Usuario,
    Vehiculo,
    Viaje,
)
from .rutas_utils import (
    construir_grafo,
    dijkstra,
    nodo_mas_cercano,
    nodos_mas_cercanos,
    k_mejores_rutas,
    calcular_metricas_ruta,
    seleccionar_mejor_enganche_ruta,
)




# =============================================================================
# SEGURIDAD / LOGIN
# =============================================================================
def login_usuario(request):

    if request.session.get('usuario_id'):
        if request.session.get('usuario_tiporol') == 'ADMINISTRADOR':
            return redirect('/adminpanel/')
        return redirect('/inicio')

    if request.method == 'POST':
        usuario_in = request.POST.get('usuario', '').strip()
        contrasena = request.POST.get('contrasena', '').strip()

        if not usuario_in or not contrasena:
            messages.error(request, "Debes ingresar correo y contraseña.")
            return render(request, 'seguridad/login.html')

        try:
            usuario = Usuario.objects.get(
                correo_usuario=usuario_in,
                contrasena_usuario=contrasena
            )

            # Verificar si está activo
            if not usuario.activo:
                messages.error(request, "Tu usuario está inactivo. Comunícate con el administrador.")
                return render(request, 'seguridad/login.html')


            if usuario.tiporol == "ADMINISTRADOR":
                try:
                    admin = Administrador.objects.get(usuario=usuario)
                except Administrador.DoesNotExist:
                    messages.error(request, "Este usuario NO tiene perfil de administrador.")
                    return render(request, 'seguridad/login.html')

            request.session['usuario_id'] = usuario.id_usuario
            request.session['usuario_nombre'] = usuario.nombre_usuario
            request.session['usuario_apellido'] = usuario.apellido_usuario
            request.session['usuario_tiporol'] = usuario.tiporol

            messages.success(request, "Inicio de sesión exitoso")

            if usuario.tiporol == 'ADMINISTRADOR':
                return redirect('/adminpanel/')
            else:
                return redirect('/inicio')

        except Usuario.DoesNotExist:
            messages.error(request, "Usuario o contraseña incorrectos")

    return render(request, 'seguridad/login.html')






# =============================================================================
# CIERRE DE SESIÓN
# =============================================================================
def logout_usuario(request):
    request.session.flush()
    messages.success(request, "Sesión cerrada correctamente")
    return redirect('/login') #devuelve la pantalla en login





# =============================================================================
# USUARIO
# =============================================================================
def inicio(request):
    # Proteger el inicio: solo usuarios logueados
    if not request.session.get('usuario_id'):
        return redirect('/login')
    
    usuario_id = request.session.get('usuario_id')
    vehiculo = Vehiculo.objects.filter(usuario_id=usuario_id).first()
    return render(request, 'usuario/dashboard/inicio.html', {
        'vehiculo': vehiculo,

        # >>> CAMBIO GOOGLE MAPS
        'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY,
        # <<< CAMBIO GOOGLE MAPS
    })



def _normalizar_espacios(valor):
    return re.sub(r'\s+', ' ', (valor or '').strip())


def _cedula_ecuatoriana_valida(cedula):
    if not re.fullmatch(r'\d{10}', cedula or ''):
        return False

    provincia = int(cedula[:2])
    tercer_digito = int(cedula[2])

    if provincia < 1 or provincia > 24 or tercer_digito >= 6:
        return False

    coeficientes = [2, 1, 2, 1, 2, 1, 2, 1, 2]
    total = 0

    for digito, coeficiente in zip(cedula[:9], coeficientes):
        resultado = int(digito) * coeficiente
        total += resultado - 9 if resultado >= 10 else resultado

    verificador = (10 - (total % 10)) % 10
    return verificador == int(cedula[9])


def _validar_foto_usuario(foto):
    if not foto:
        return None

    extensiones = ('.png', '.jpg', '.jpeg')

    if not foto.name.lower().endswith(extensiones):
        return 'La fotografía debe estar en formato PNG, JPG o JPEG.'

    if foto.size > 5 * 1024 * 1024:
        return 'La fotografía no puede superar los 5 MB.'

    return None


def _obtener_datos_usuario_formulario(
    request,
    usuario_actual=None,
    requerir_contrasena=False,
    permitir_contrasena=False
):
    cedula = request.POST.get('txt_cedula', '').strip()
    nombre = _normalizar_espacios(request.POST.get('txt_nombre', ''))
    apellido = _normalizar_espacios(request.POST.get('txt_apellido', ''))
    correo = request.POST.get('txt_correo', '').strip().lower()
    telefono = re.sub(
        r'[\s\-()]',
        '',
        request.POST.get('txt_telefono', '').strip()
    )
    contrasena = request.POST.get('txt_contrasena', '').strip()
    foto = request.FILES.get('foto_usuario')

    if not _cedula_ecuatoriana_valida(cedula):
        return None, 'Ingrese una cédula ecuatoriana válida de 10 dígitos.'

    if len(nombre) < 2 or len(nombre) > 100:
        return None, 'Los nombres deben tener entre 2 y 100 caracteres.'

    if not re.fullmatch(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ' -]+", nombre):
        return None, 'Los nombres solo pueden contener letras, espacios, guiones y apóstrofes.'

    if len(apellido) < 2 or len(apellido) > 100:
        return None, 'Los apellidos deben tener entre 2 y 100 caracteres.'

    if not re.fullmatch(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ' -]+", apellido):
        return None, 'Los apellidos solo pueden contener letras, espacios, guiones y apóstrofes.'

    if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', correo):
        return None, 'Ingrese un correo electrónico válido.'

    if not re.fullmatch(r'\+?\d{7,15}', telefono):
        return None, 'Ingrese un teléfono válido de 7 a 15 dígitos.'

    usuarios = Usuario.objects.all()

    if usuario_actual:
        usuarios = usuarios.exclude(id_usuario=usuario_actual.id_usuario)

    if usuarios.filter(cedula_usuario=cedula).exists():
        return None, 'Ya existe un usuario registrado con esa cédula.'

    if usuarios.filter(correo_usuario__iexact=correo).exists():
        return None, 'Ya existe un usuario registrado con ese correo electrónico.'

    if usuarios.filter(
        nombre_usuario__iexact=nombre,
        apellido_usuario__iexact=apellido
    ).exists():
        return None, 'Ya existe un usuario con la misma combinación de nombres y apellidos.'

    if requerir_contrasena and not contrasena:
        return None, 'La contraseña es obligatoria.'

    if contrasena and (len(contrasena) < 6 or len(contrasena) > 12):
        return None, 'La contraseña debe tener entre 6 y 12 caracteres.'

    if contrasena and not permitir_contrasena and not requerir_contrasena:
        contrasena = ''

    error_foto = _validar_foto_usuario(foto)

    if error_foto:
        return None, error_foto

    return {
        'cedula_usuario': cedula,
        'nombre_usuario': nombre,
        'apellido_usuario': apellido,
        'correo_usuario': correo,
        'telefono_usuario': telefono,
        'contrasena_usuario': contrasena,
        'foto_usuario': foto,
    }, None


def perfilusuario(request):
    usuario_id = request.session.get('usuario_id')

    if not usuario_id:
        return redirect('/login')

    try:
        usuario = Usuario.objects.get(id_usuario=usuario_id)
    except Usuario.DoesNotExist:
        request.session.flush()
        messages.error(request, 'La sesión no es válida.')
        return redirect('/login')

    return render(
        request,
        'usuario/perfil/perfilusuario.html',
        {'usuario': usuario}
    )


def editarusuario(request, id):
    usuario_id = request.session.get('usuario_id')

    if not usuario_id:
        return redirect('/login')

    if int(usuario_id) != int(id):
        messages.error(request, 'Solo puedes editar tu propio perfil.')
        return redirect('/perfilusuario/')

    try:
        usuario = Usuario.objects.get(id_usuario=usuario_id)
    except Usuario.DoesNotExist:
        request.session.flush()
        return redirect('/login')

    return render(
        request,
        'usuario/perfil/editarusuario.html',
        {'usuario': usuario}
    )


def _campo_error_perfil_usuario(mensaje):
    mensaje_normalizado = (mensaje or '').lower()

    if 'cédula' in mensaje_normalizado or 'cedula' in mensaje_normalizado:
        return 'txt_cedula'
    if 'nombres' in mensaje_normalizado or 'misma combinación' in mensaje_normalizado:
        return 'txt_nombre'
    if 'apellidos' in mensaje_normalizado:
        return 'txt_apellido'
    if 'correo' in mensaje_normalizado:
        return 'txt_correo'
    if 'teléfono' in mensaje_normalizado or 'telefono' in mensaje_normalizado:
        return 'txt_telefono'
    if 'fotografía' in mensaje_normalizado or 'imagen' in mensaje_normalizado:
        return 'foto_usuario'

    return 'general'


def procesareditarusuario(request):
    usuario_id = request.session.get('usuario_id')

    if not usuario_id:
        return redirect('/login')

    if request.method != 'POST':
        return redirect('/perfilusuario/')

    try:
        usuario = Usuario.objects.get(id_usuario=usuario_id)
    except Usuario.DoesNotExist:
        request.session.flush()
        return redirect('/login')

    id_formulario = request.POST.get('id_usuario', '').strip()

    if id_formulario and id_formulario != str(usuario.id_usuario):
        messages.error(request, 'No puedes modificar la información de otro usuario.')
        return redirect('/perfilusuario/')

    datos, error = _obtener_datos_usuario_formulario(
        request,
        usuario_actual=usuario
    )

    if error:
        campo_error = _campo_error_perfil_usuario(error)
        errores_servidor = {campo_error: error}
        valores_formulario = {
            'txt_cedula': request.POST.get('txt_cedula', '').strip(),
            'txt_telefono': request.POST.get('txt_telefono', '').strip(),
            'txt_nombre': request.POST.get('txt_nombre', '').strip(),
            'txt_apellido': request.POST.get('txt_apellido', '').strip(),
            'txt_correo': request.POST.get('txt_correo', '').strip(),
        }
        return render(
            request,
            'usuario/perfil/editarusuario.html',
            {
                'usuario': usuario,
                'errores_servidor': errores_servidor,
                'valores_formulario': valores_formulario,
            },
            status=400
        )

    usuario.cedula_usuario = datos['cedula_usuario']
    usuario.nombre_usuario = datos['nombre_usuario']
    usuario.apellido_usuario = datos['apellido_usuario']
    usuario.correo_usuario = datos['correo_usuario']
    usuario.telefono_usuario = datos['telefono_usuario']

    if datos['foto_usuario']:
        if usuario.foto_usuario:
            try:
                usuario.foto_usuario.delete(save=False)
            except Exception:
                pass

        usuario.foto_usuario = datos['foto_usuario']

    usuario.save()
    messages.success(request, 'Perfil actualizado correctamente.')
    return redirect('/perfilusuario/')




# =============================================================================
# ADMINISTRADOR
# =============================================================================
def _validar_acceso_admin_usuarios(request):
    if not request.session.get('usuario_id'):
        return redirect('/login')

    if request.session.get('usuario_tiporol') != 'ADMINISTRADOR':
        messages.error(request, 'No tienes permisos para administrar usuarios.')
        return redirect('/inicio')

    return None


def listadousuario(request):
    acceso = _validar_acceso_admin_usuarios(request)

    if acceso:
        return acceso

    usuarios = Usuario.objects.all().order_by(
        'nombre_usuario',
        'apellido_usuario'
    )
    total_usuarios = Usuario.objects.filter(tiporol='USUARIO').count()
    total_admins = Usuario.objects.filter(tiporol='ADMINISTRADOR').count()

    return render(request, 'administrador/usuarios/listadousuario.html', {
        'usuarios': usuarios,
        'total_usuarios': total_usuarios,
        'total_admins': total_admins,
        'es_admin': True
    })






def nuevousuario(request):
    acceso = _validar_acceso_admin_usuarios(request)

    if acceso:
        return acceso

    return render(request, 'usuario/perfil/nuevousuario.html')


def guardarusuario(request):
    acceso = _validar_acceso_admin_usuarios(request)

    if acceso:
        return acceso

    if request.method != 'POST':
        return redirect('/nuevousuario/')

    datos, error = _obtener_datos_usuario_formulario(
        request,
        requerir_contrasena=True,
        permitir_contrasena=True
    )

    if error:
        messages.error(request, error)
        return redirect('/nuevousuario/')

    foto = datos.pop('foto_usuario')
    nuevo = Usuario.objects.create(
        **datos,
        tiporol='USUARIO',
        activo=True
    )

    if foto:
        nuevo.foto_usuario = foto
        nuevo.save(update_fields=['foto_usuario'])

    messages.success(request, 'Usuario creado correctamente.')
    return redirect('/listadousuario/')



@require_GET
def api_consultar_cedula(request, cedula):
    acceso = _validar_acceso_admin_usuarios(request)
    if acceso:
        return JsonResponse({
            'ok': False,
            'mensaje': 'No autorizado.'
        }, status=403)

    cedula = (cedula or '').strip()
    if not _cedula_ecuatoriana_valida(cedula):
        return JsonResponse({
            'ok': False,
            'valida': False,
            'mensaje': 'La cédula no supera la validación ecuatoriana.'
        }, status=400)

    existente = Usuario.objects.filter(cedula_usuario=cedula).first()
    if existente:
        return JsonResponse({
            'ok': True,
            'valida': True,
            'existente': True,
            'nombres': existente.nombre_usuario,
            'apellidos': existente.apellido_usuario,
            'mensaje': 'Cédula existente.'
        })

    url = (getattr(settings, 'CEDULA_LOOKUP_URL', '') or '').strip()
    token = (getattr(settings, 'CEDULA_LOOKUP_TOKEN', '') or '').strip()
    if not url:
        return JsonResponse({
            'ok': False,
            'valida': True,
            'disponible': False,
            'mensaje': 'Cédula válida.'
        })

    headers = {'Accept': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'

    try:
        if '{cedula}' in url:
            respuesta = requests.get(
                url.format(cedula=cedula),
                headers=headers,
                timeout=8
            )
        else:
            respuesta = requests.get(
                url,
                params={'cedula': cedula},
                headers=headers,
                timeout=8
            )
        respuesta.raise_for_status()
        payload = respuesta.json()
    except Exception:
        return JsonResponse({
            'ok': False,
            'valida': True,
            'disponible': False,
            'mensaje': (
                'No fue posible consultar el proveedor externo. '
                'El registro manual sigue disponible.'
            )
        })

    data = payload.get('data') if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        data = payload if isinstance(payload, dict) else {}

    nombres = _normalizar_espacios(
        data.get('nombres') or data.get('nombre') or data.get('first_names') or ''
    )
    apellidos = _normalizar_espacios(
        data.get('apellidos') or data.get('apellido') or data.get('last_names') or ''
    )

    if not nombres or not apellidos:
        return JsonResponse({
            'ok': False,
            'valida': True,
            'disponible': True,
            'mensaje': (
                'El proveedor respondió, pero no devolvió nombres y apellidos en un formato reconocido. '
                'Puede completarlos manualmente.'
            )
        })

    return JsonResponse({
        'ok': True,
        'valida': True,
        'existente': False,
        'nombres': nombres,
        'apellidos': apellidos,
        'mensaje': 'Datos recuperados correctamente.'
    })




def editarusuarioadministrador(request, id):
    if not request.session.get('usuario_id'):
        return redirect('/login')

    if request.session.get('usuario_tiporol') != 'ADMINISTRADOR':
        messages.error(request, 'No tienes permisos para acceder.')
        return redirect('/inicio')

    try:
        usuario = Usuario.objects.get(id_usuario=id)
    except Usuario.DoesNotExist:
        messages.error(request, 'El usuario no existe.')
        return redirect('/listadousuario/')

    return render(
        request,
        'administrador/usuarios/editarusuarioadministrador.html',
        {'usuario': usuario}
    )


def procesareditarusuarioadministrador(request):
    if not request.session.get('usuario_id'):
        return redirect('/login')

    if request.session.get('usuario_tiporol') != 'ADMINISTRADOR':
        messages.error(request, 'No tienes permisos para acceder.')
        return redirect('/inicio')

    if request.method != 'POST':
        return redirect('/listadousuario/')

    try:
        usuario = Usuario.objects.get(
            id_usuario=request.POST.get('id_usuario')
        )
    except Usuario.DoesNotExist:
        messages.error(request, 'El usuario no existe.')
        return redirect('/listadousuario/')

    datos, error = _obtener_datos_usuario_formulario(
        request,
        usuario_actual=usuario,
        permitir_contrasena=True
    )

    if error:
        messages.error(request, error)
        return redirect(
            'editarusuarioadministrador',
            id=usuario.id_usuario
        )

    usuario.cedula_usuario = datos['cedula_usuario']
    usuario.nombre_usuario = datos['nombre_usuario']
    usuario.apellido_usuario = datos['apellido_usuario']
    usuario.correo_usuario = datos['correo_usuario']
    usuario.telefono_usuario = datos['telefono_usuario']

    if datos['contrasena_usuario']:
        usuario.contrasena_usuario = datos['contrasena_usuario']

    if datos['foto_usuario']:
        if usuario.foto_usuario:
            try:
                usuario.foto_usuario.delete(save=False)
            except Exception:
                pass

        usuario.foto_usuario = datos['foto_usuario']

    usuario.save()
    messages.success(request, 'Usuario actualizado correctamente.')
    return redirect('/listadousuario/')




def eliminarusuarioadministrador(request, id):
    if not request.session.get('usuario_id'):
        return redirect('/login')
    if request.session.get('usuario_tiporol') != 'ADMINISTRADOR':
        messages.error(request, "No tienes permisos para acceder.")
        return redirect('/inicio')
    if request.method != 'POST':
        return redirect('/listadousuario/')

    if int(request.session.get('usuario_id')) == int(id):
        messages.error(request, "No puedes eliminar tu propio usuario.")
        return redirect('/listadousuario/')

    try:
        usuario = Usuario.objects.get(id_usuario=id)
    except Usuario.DoesNotExist:
        messages.error(request, "El usuario no existe.")
        return redirect('/listadousuario/')

    if usuario.tiporol == 'ADMINISTRADOR':
        messages.error(request, "Los perfiles de administrador no se eliminan desde este listado.")
        return redirect('/listadousuario/')

    if usuario.foto_usuario and default_storage.exists(usuario.foto_usuario.name):
        try:
            default_storage.delete(usuario.foto_usuario.name)
        except Exception:
            pass

    usuario.delete()
    messages.success(request, "Usuario eliminado correctamente.")
    return redirect('/listadousuario/')



def activarusuarioadministrador(request, id):
    # solo ADMIN
    if not request.session.get('usuario_id'):
        return redirect('/login')
    if request.session.get('usuario_tiporol') != 'ADMINISTRADOR':
        messages.error(request, "No tienes permisos para acceder.")
        return redirect('/inicio')

    try:
        usuario = Usuario.objects.get(id_usuario=id)
    except Usuario.DoesNotExist:
        messages.error(request, "El usuario no existe.")
        return redirect('/listadousuario/')

    usuario.activo = True
    usuario.save()
    messages.success(request, "Usuario activado correctamente.")
    return redirect('/listadousuario/')


def inactivarusuarioadministrador(request, id):
    # solo ADMIN
    if not request.session.get('usuario_id'):
        return redirect('/login')
    if request.session.get('usuario_tiporol') != 'ADMINISTRADOR':
        messages.error(request, "No tienes permisos para acceder.")
        return redirect('/inicio')

    try:
        usuario = Usuario.objects.get(id_usuario=id)
    except Usuario.DoesNotExist:
        messages.error(request, "El usuario no existe.")
        return redirect('/listadousuario/')

    usuario.activo = False
    usuario.save()
    messages.success(request, "Usuario desactivado correctamente.")
    return redirect('/listadousuario/')





# =============================================================================
# DOCUMENTOS / CHECKLIST VEHICULAR
# =============================================================================


# CAMPOS OBLIGATORIOS CHECKLIST
CAMPOS_CHECKLIST = [
    # Documentos
    'licencia_conducir', 'tarjeta_circulacion', 'poliza_impresa',
    'poliza_digital', 'verificacion_vehicular', 'factura_propiedad',

    # Chequeo mecánico
    'llantas', 'frenos', 'luces', 'fluidos_aceite', 'fluido_agua',
    'bateria_general', 'cinturones', 'limpiaparabrisas',

    # Motor
    'motor_aceite', 'motor_refrigerante', 'motor_temperatura',
    'motor_bateria', 'motor_filtro_aire', 'motor_fugas',
    'motor_combustible',

    # Suspensión
    'amortiguadores', 'alineacion', 'soportes_motor', 'caja', 'embrague',

    # Seguridad
    'triangulo', 'chaleco', 'extintor', 'gato_llave', 'botiquin',
    'linterna', 'cables_corriente', 'tacos_ruedas', 'llanta_reparacion'
]



def creardocumento(request):
    id_usuario = request.session.get('usuario_id')
    if not id_usuario:
        return redirect('/login/')  

    usuario = Usuario.objects.get(id_usuario=id_usuario)

    checklist = ChecklistVehiculo.objects.filter(
        usuario=usuario
    ).order_by('-creado_en').first()

    if checklist:
        edit_mode = 'edit' in request.GET
    else:
        edit_mode = True  

    if request.method == 'POST':
        data = request.POST

        faltantes = []

        for campo in CAMPOS_CHECKLIST:
            if not data.get(campo):
                faltantes.append(campo)

        if faltantes:
            messages.error(
                request,
                "Debes completar TODOS los ítems marcando SI o NO antes de guardar."
            )
            return render(request, 'usuario/documentos/creardocumento.html', {
                'usuario': usuario,
                'checklist': checklist,
                'bloqueado': False,
                'edit_mode': True,
            })



        if checklist:
            c = checklist
            c.licencia_conducir = data.get('licencia_conducir')
            c.tarjeta_circulacion = data.get('tarjeta_circulacion')
            c.poliza_impresa = data.get('poliza_impresa')
            c.poliza_digital = data.get('poliza_digital')
            c.verificacion_vehicular = data.get('verificacion_vehicular')
            c.factura_propiedad = data.get('factura_propiedad')

            # Chequeo mecánico
            c.llantas = data.get('llantas')
            c.frenos = data.get('frenos')
            c.luces = data.get('luces')
            c.fluidos_aceite = data.get('fluidos_aceite')
            c.fluido_agua = data.get('fluido_agua')
            c.bateria_general = data.get('bateria_general')
            c.cinturones = data.get('cinturones')
            c.limpiaparabrisas = data.get('limpiaparabrisas')

            # Motor
            c.motor_aceite = data.get('motor_aceite')
            c.motor_refrigerante = data.get('motor_refrigerante')
            c.motor_temperatura = data.get('motor_temperatura')
            c.motor_bateria = data.get('motor_bateria')
            c.motor_filtro_aire = data.get('motor_filtro_aire')
            c.motor_fugas = data.get('motor_fugas')
            c.motor_combustible = data.get('motor_combustible')

            # Suspensión / transmisión
            c.amortiguadores = data.get('amortiguadores')
            c.alineacion = data.get('alineacion')
            c.soportes_motor = data.get('soportes_motor')
            c.caja = data.get('caja')
            c.embrague = data.get('embrague')

            # Equipo de seguridad
            c.triangulo = data.get('triangulo')
            c.chaleco = data.get('chaleco')
            c.extintor = data.get('extintor')
            c.gato_llave = data.get('gato_llave')
            c.botiquin = data.get('botiquin')
            c.linterna = data.get('linterna')
            c.cables_corriente = data.get('cables_corriente')
            c.tacos_ruedas = data.get('tacos_ruedas')
            c.llanta_reparacion = data.get('llanta_reparacion')

            c.save()
            messages.success(request, "Checklist actualizado correctamente.")
        else:
            # CREAR nuevo checklist
            checklist = ChecklistVehiculo.objects.create(
                usuario=usuario,

                # Documentos indispensables
                licencia_conducir=data.get('licencia_conducir'),
                tarjeta_circulacion=data.get('tarjeta_circulacion'),
                poliza_impresa=data.get('poliza_impresa'),
                poliza_digital=data.get('poliza_digital'),
                verificacion_vehicular=data.get('verificacion_vehicular'),
                factura_propiedad=data.get('factura_propiedad'),

                # Chequeo mecánico
                llantas=data.get('llantas'),
                frenos=data.get('frenos'),
                luces=data.get('luces'),
                fluidos_aceite=data.get('fluidos_aceite'),
                fluido_agua=data.get('fluido_agua'),
                bateria_general=data.get('bateria_general'),
                cinturones=data.get('cinturones'),
                limpiaparabrisas=data.get('limpiaparabrisas'),

                # Motor
                motor_aceite=data.get('motor_aceite'),
                motor_refrigerante=data.get('motor_refrigerante'),
                motor_temperatura=data.get('motor_temperatura'),
                motor_bateria=data.get('motor_bateria'),
                motor_filtro_aire=data.get('motor_filtro_aire'),
                motor_fugas=data.get('motor_fugas'),
                motor_combustible=data.get('motor_combustible'),

                # Suspensión / transmisión
                amortiguadores=data.get('amortiguadores'),
                alineacion=data.get('alineacion'),
                soportes_motor=data.get('soportes_motor'),
                caja=data.get('caja'),
                embrague=data.get('embrague'),

                # Equipo de seguridad
                triangulo=data.get('triangulo'),
                chaleco=data.get('chaleco'),
                extintor=data.get('extintor'),
                gato_llave=data.get('gato_llave'),
                botiquin=data.get('botiquin'),
                linterna=data.get('linterna'),
                cables_corriente=data.get('cables_corriente'),
                tacos_ruedas=data.get('tacos_ruedas'),
                llanta_reparacion=data.get('llanta_reparacion'),
            )
            messages.success(request, "Checklist guardado correctamente.")

        # Después de guardar, volvemos en modo lectura
        return redirect('creardocumento')
    bloqueado = bool(checklist) and not edit_mode

    return render(request, 'usuario/documentos/creardocumento.html', {
        'usuario': usuario,
        'checklist': checklist,
        'bloqueado': bloqueado,
        'edit_mode': edit_mode,
    })


# =============================================================================
# VEHÍCULOS: FUNCIONES COMPARTIDAS
# =============================================================================

def _validar_acceso_admin_vehiculos(request):
    if not request.session.get('usuario_id'):
        return redirect('/login')

    if request.session.get('usuario_tiporol') != 'ADMINISTRADOR':
        messages.error(request, "No tienes permisos para administrar vehículos.")
        return redirect('/inicio/')

    return None


def _usuarios_disponibles_vehiculos():
    return Usuario.objects.filter(
        tiporol='USUARIO',
        activo=True,
        vehiculos__isnull=True
    ).order_by(
        'nombre_usuario',
        'apellido_usuario'
    )


def _valor_vehiculo_repetido(campo, valor, vehiculo_actual=None):
    consulta = Vehiculo.objects.filter(**{campo: valor})

    if vehiculo_actual:
        consulta = consulta.exclude(
            id_vehiculo=vehiculo_actual.id_vehiculo
        )

    return consulta.exists()


def _validar_foto_vehiculo(request):
    foto = request.FILES.get('foto_vehiculo')

    if not foto:
        return None, None

    tipos_permitidos = [
        'image/jpeg',
        'image/png',
        'image/webp',
    ]

    if getattr(foto, 'content_type', '') not in tipos_permitidos:
        return None, "La imagen del vehículo debe ser JPG, PNG o WEBP."

    if foto.size > 5 * 1024 * 1024:
        return None, "La imagen del vehículo no puede superar los 5 MB."

    return foto, None


def _obtener_datos_vehiculo(
    request,
    vehiculo_actual=None,
    usuario_obligatorio=False,
    capacidad_obligatoria=False
):
    usuario_id = request.POST.get('usuario', '').strip()
    tipo_vehiculo = request.POST.get('txt_tipo_vehiculo', '').strip().upper()
    tipo_combustible = request.POST.get('txt_tipo_combustible', '').strip().upper()
    matricula = request.POST.get('txt_matricula', '').strip().upper()
    modelo = request.POST.get('txt_modelo', '').strip()
    numero_cedula = request.POST.get('txt_numero_cedula', '').strip()
    numero_motor = request.POST.get('txt_numero_motor', '').strip().upper()
    numero_chasis = request.POST.get('txt_numero_chasis', '').strip().upper()
    peso_texto = request.POST.get('txt_peso_auto', '').strip().replace(',', '.')
    capacidad_texto = request.POST.get(
        'txt_capacidad_carga_kg',
        ''
    ).strip().replace(',', '.')
    cilindraje_texto = request.POST.get('txt_cilindraje', '').strip().replace(',', '.')

    foto_vehiculo, error_foto = _validar_foto_vehiculo(request)

    if error_foto:
        return None, error_foto

    tipos_vehiculo = [opcion[0] for opcion in Vehiculo.TIPOS_VEHICULO]
    tipos_combustible = [opcion[0] for opcion in Vehiculo.TIPOS_COMBUSTIBLE]

    if tipo_vehiculo not in tipos_vehiculo:
        return None, "Seleccione un tipo de vehículo válido."

    if tipo_combustible not in tipos_combustible:
        return None, "Seleccione un tipo de combustible válido."

    if not re.match(r'^[A-Z]{3}-[0-9]{4}$', matricula):
        return None, "Formato de placa inválido. Ejemplo válido: ABC-1234."

    if _valor_vehiculo_repetido(
        'matricula_vehiculo',
        matricula,
        vehiculo_actual
    ):
        return None, "La placa ya está registrada en otro vehículo."

    if not _cedula_ecuatoriana_valida(numero_cedula):
        return None, "La cédula ingresada no es válida."

    if _valor_vehiculo_repetido(
        'numero_cedula',
        numero_cedula,
        vehiculo_actual
    ):
        return None, "La cédula ya está registrada en otro vehículo."

    if len(numero_motor) < 5 or len(numero_motor) > 12:
        return None, "El número de motor debe tener entre 5 y 12 caracteres."

    if not re.match(r'^[A-Z0-9-]+$', numero_motor):
        return None, "El número de motor solo permite letras, números y guiones."

    if _valor_vehiculo_repetido(
        'numero_motor',
        numero_motor,
        vehiculo_actual
    ):
        return None, "El número de motor ya está registrado."

    if not re.match(r'^[A-HJ-NPR-Z0-9]{17}$', numero_chasis):
        return None, (
            "El número de chasis debe tener 17 caracteres "
            "y no puede contener I, O ni Q."
        )

    if _valor_vehiculo_repetido(
        'numero_chasis',
        numero_chasis,
        vehiculo_actual
    ):
        return None, "El número de chasis ya está registrado."

    try:
        peso_auto = Decimal(peso_texto)
    except Exception:
        return None, "El peso debe ser un número válido."

    if peso_auto < Decimal('0.1') or peso_auto > Decimal('8'):
        return None, "El peso debe estar entre 0.1 y 8 toneladas."

    capacidad_carga_kg = None

    if capacidad_texto:
        try:
            capacidad_carga_kg = Decimal(capacidad_texto)
        except Exception:
            return None, "La capacidad de carga debe ser un número válido."

        if (
            capacidad_carga_kg < Decimal('1') or
            capacidad_carga_kg > Decimal('50000')
        ):
            return None, (
                "La capacidad de carga debe estar "
                "entre 1 y 50000 kg."
            )

    elif vehiculo_actual:
        capacidad_carga_kg = (
            vehiculo_actual.capacidad_carga_kg
        )

    if capacidad_obligatoria and not capacidad_carga_kg:
        return None, (
            "Ingrese la capacidad máxima de carga "
            "del vehículo."
        )

    try:
        cilindraje = Decimal(cilindraje_texto)
    except Exception:
        return None, "El cilindraje debe ser un número válido."

    if cilindraje < Decimal('1') or cilindraje > Decimal('5000'):
        return None, "El cilindraje debe estar entre 1 y 5000."

    usuario = None

    if usuario_id:
        try:
            usuario = Usuario.objects.get(id_usuario=usuario_id)
        except Usuario.DoesNotExist:
            return None, "El usuario seleccionado no existe."

        if usuario.tiporol != 'USUARIO':
            return None, "No se puede asignar un vehículo a un administrador."

        if not usuario.activo:
            return None, "El usuario seleccionado está inactivo."

        consulta = Vehiculo.objects.filter(usuario=usuario)

        if vehiculo_actual:
            consulta = consulta.exclude(
                id_vehiculo=vehiculo_actual.id_vehiculo
            )

        if consulta.exists():
            return None, "El usuario ya tiene un vehículo asignado."

    elif usuario_obligatorio:
        return None, "Debe seleccionar un usuario."

    datos = {
        'usuario': usuario,
        'tipovehiculo_vehiculo': tipo_vehiculo,
        'tipocombustible_vehiculo': tipo_combustible,
        'matricula_vehiculo': matricula,
        'modelo_vehiculo': modelo,
        'numero_cedula': numero_cedula,
        'numero_motor': numero_motor,
        'numero_chasis': numero_chasis,
        'peso_auto': peso_auto,
        'capacidad_carga_kg': capacidad_carga_kg,
        'cilindraje': cilindraje,
    }

    if foto_vehiculo:
        datos['foto_vehiculo'] = foto_vehiculo

    return datos, None


def _actualizar_vehiculo(vehiculo, datos):
    vehiculo.usuario = datos['usuario']
    vehiculo.tipovehiculo_vehiculo = datos['tipovehiculo_vehiculo']
    vehiculo.tipocombustible_vehiculo = datos['tipocombustible_vehiculo']
    vehiculo.matricula_vehiculo = datos['matricula_vehiculo']
    vehiculo.modelo_vehiculo = datos['modelo_vehiculo']

    if 'foto_vehiculo' in datos:
        vehiculo.foto_vehiculo = datos['foto_vehiculo']

    vehiculo.numero_cedula = datos['numero_cedula']
    vehiculo.numero_motor = datos['numero_motor']
    vehiculo.numero_chasis = datos['numero_chasis']
    vehiculo.peso_auto = datos['peso_auto']
    vehiculo.capacidad_carga_kg = datos['capacidad_carga_kg']
    vehiculo.cilindraje = datos['cilindraje']
    vehiculo.save()


# =============================================================================
# VEHÍCULOS DEL ADMINISTRADOR
# =============================================================================

def listadocarros(request):
    acceso = _validar_acceso_admin_vehiculos(request)
    if acceso:
        return acceso

    vehiculos = Vehiculo.objects.select_related(
        'usuario'
    ).all().order_by('matricula_vehiculo')

    total_vehiculos = Vehiculo.objects.count()
    total_asignados = Vehiculo.objects.filter(usuario__isnull=False).count()
    total_disponibles = Vehiculo.objects.filter(usuario__isnull=True).count()
    usuarios_disponibles = _usuarios_disponibles_vehiculos()

    return render(
        request,
        'administrador/vehiculos/listadocarros.html',
        {
            'vehiculos': vehiculos,
            'total_vehiculos': total_vehiculos,
            'total_asignados': total_asignados,
            'total_disponibles': total_disponibles,
            'usuarios_disponibles': usuarios_disponibles,
        }
    )


def nuevovehiculoadmin(request):
    acceso = _validar_acceso_admin_vehiculos(request)
    if acceso:
        return acceso

    return render(
        request,
        'administrador/vehiculos/formulario_vehiculo.html',
        {
            'vehiculo': None,
            'usuarios_disponibles': _usuarios_disponibles_vehiculos(),
            'modo': 'crear',
        }
    )


def guardarvehiculoadmin(request):
    acceso = _validar_acceso_admin_vehiculos(request)
    if acceso:
        return acceso

    if request.method != 'POST':
        return redirect('listadocarros')

    datos, error = _obtener_datos_vehiculo(
        request,
        capacidad_obligatoria=True
    )

    if error:
        messages.error(request, error)
        return redirect('nuevovehiculoadmin')

    Vehiculo.objects.create(**datos)
    messages.success(request, "Vehículo registrado correctamente.")
    return redirect('listadocarros')


def detallevehiculoadmin(request, id):
    acceso = _validar_acceso_admin_vehiculos(request)
    if acceso:
        return acceso

    try:
        vehiculo = Vehiculo.objects.select_related('usuario').get(
            id_vehiculo=id
        )
    except Vehiculo.DoesNotExist:
        messages.error(request, "El vehículo no existe.")
        return redirect('listadocarros')

    return render(
        request,
        'administrador/vehiculos/detallevehiculo.html',
        {'vehiculo': vehiculo}
    )


def editarvehiculoadmin(request, id):
    acceso = _validar_acceso_admin_vehiculos(request)
    if acceso:
        return acceso

    try:
        vehiculo = Vehiculo.objects.select_related('usuario').get(
            id_vehiculo=id
        )
    except Vehiculo.DoesNotExist:
        messages.error(request, "El vehículo no existe.")
        return redirect('listadocarros')

    usuarios_disponibles = list(_usuarios_disponibles_vehiculos())

    if vehiculo.usuario:
        encontrado = any(
            usuario.id_usuario == vehiculo.usuario.id_usuario
            for usuario in usuarios_disponibles
        )

        if not encontrado:
            usuarios_disponibles.insert(0, vehiculo.usuario)

    return render(
        request,
        'administrador/vehiculos/formulario_vehiculo.html',
        {
            'vehiculo': vehiculo,
            'usuarios_disponibles': usuarios_disponibles,
            'modo': 'editar',
        }
    )


def procesareditarvehiculoadmin(request):
    acceso = _validar_acceso_admin_vehiculos(request)
    if acceso:
        return acceso

    if request.method != 'POST':
        return redirect('listadocarros')

    id_vehiculo = request.POST.get('id_vehiculo')

    try:
        vehiculo = Vehiculo.objects.get(id_vehiculo=id_vehiculo)
    except Vehiculo.DoesNotExist:
        messages.error(request, "El vehículo no existe.")
        return redirect('listadocarros')

    datos, error = _obtener_datos_vehiculo(
        request,
        vehiculo_actual=vehiculo,
        capacidad_obligatoria=True
    )

    if error:
        messages.error(request, error)
        return redirect(
            'editarvehiculoadmin',
            id=vehiculo.id_vehiculo
        )

    _actualizar_vehiculo(vehiculo, datos)
    messages.success(request, "Vehículo actualizado correctamente.")

    return redirect(
        'detallevehiculoadmin',
        id=vehiculo.id_vehiculo
    )


def asignarvehiculoadmin(request, id):
    acceso = _validar_acceso_admin_vehiculos(request)
    if acceso:
        return acceso

    if request.method != 'POST':
        return redirect('listadocarros')

    try:
        vehiculo = Vehiculo.objects.get(id_vehiculo=id)
    except Vehiculo.DoesNotExist:
        messages.error(request, "El vehículo no existe.")
        return redirect('listadocarros')

    if vehiculo.usuario:
        messages.error(request, "El vehículo ya se encuentra asignado.")
        return redirect('listadocarros')

    usuario_id = request.POST.get('usuario', '').strip()

    if not usuario_id:
        messages.error(request, "Seleccione un usuario.")
        return redirect('listadocarros')

    try:
        usuario = Usuario.objects.get(id_usuario=usuario_id)
    except Usuario.DoesNotExist:
        messages.error(request, "El usuario seleccionado no existe.")
        return redirect('listadocarros')

    if usuario.tiporol != 'USUARIO':
        messages.error(
            request,
            "No se puede asignar el vehículo a un administrador."
        )
        return redirect('listadocarros')

    if not usuario.activo:
        messages.error(request, "El usuario seleccionado está inactivo.")
        return redirect('listadocarros')

    if Vehiculo.objects.filter(usuario=usuario).exists():
        messages.error(request, "El usuario ya tiene un vehículo asignado.")
        return redirect('listadocarros')

    vehiculo.usuario = usuario
    vehiculo.save()

    messages.success(
        request,
        f"El vehículo {vehiculo.matricula_vehiculo} fue asignado correctamente."
    )
    return redirect('listadocarros')


def desasignarvehiculoadmin(request, id):
    acceso = _validar_acceso_admin_vehiculos(request)
    if acceso:
        return acceso

    if request.method != 'POST':
        return redirect('listadocarros')

    try:
        vehiculo = Vehiculo.objects.get(id_vehiculo=id)
    except Vehiculo.DoesNotExist:
        messages.error(request, "El vehículo no existe.")
        return redirect('listadocarros')

    if not vehiculo.usuario:
        messages.error(request, "El vehículo ya se encuentra disponible.")
        return redirect('listadocarros')

    vehiculo.usuario = None
    vehiculo.save()

    messages.success(
        request,
        "El vehículo quedó disponible para una nueva asignación."
    )
    return redirect('listadocarros')


def eliminarvehiculoadmin(request, id):
    acceso = _validar_acceso_admin_vehiculos(request)
    if acceso:
        return acceso

    if request.method != 'POST':
        return redirect('listadocarros')

    try:
        vehiculo = Vehiculo.objects.get(id_vehiculo=id)
    except Vehiculo.DoesNotExist:
        messages.error(request, "El vehículo no existe.")
        return redirect('listadocarros')

    matricula = vehiculo.matricula_vehiculo
    vehiculo.delete()

    messages.success(request, f"El vehículo {matricula} fue eliminado.")
    return redirect('listadocarros')


# =============================================================================
# VEHÍCULOS DEL USUARIO
# =============================================================================

def nuevovehiculo(request, id_usuario):
    usuario_logueado_id = request.session.get('usuario_id')

    if not usuario_logueado_id:
        messages.error(request, "Inicia sesión nuevamente.")
        return redirect('/login')

    try:
        usuario = Usuario.objects.get(id_usuario=id_usuario)
    except Usuario.DoesNotExist:
        messages.error(request, "El usuario seleccionado no existe.")
        return redirect('/listadocarros/')

    if usuario.tiporol != 'USUARIO':
        messages.error(
            request,
            "No se puede registrar un vehículo para un administrador."
        )
        return redirect('/listadocarros/')

    es_admin = request.session.get('usuario_tiporol') == 'ADMINISTRADOR'

    if not es_admin and int(usuario_logueado_id) != usuario.id_usuario:
        messages.error(
            request,
            "No tienes permisos para registrar un vehículo para otro usuario."
        )
        return redirect('/inicio/')

    tiene_vehiculo = Vehiculo.objects.filter(usuario=usuario).exists()

    return render(
        request,
        'usuario/vehiculos/nuevovehiculo.html',
        {
            'usuario': usuario,
            'tiene_vehiculo': tiene_vehiculo,
        }
    )


def guardarvehiculo(request):
    if not request.session.get('usuario_id'):
        messages.error(request, "Inicia sesión nuevamente.")
        return redirect('/login')

    if request.method != 'POST':
        return redirect('/inicio/')

    usuario_id = request.POST.get('usuario', '').strip()
    es_admin = request.session.get('usuario_tiporol') == 'ADMINISTRADOR'

    if not es_admin and usuario_id != str(request.session.get('usuario_id')):
        messages.error(
            request,
            "No tienes permisos para registrar un vehículo para otro usuario."
        )
        return redirect('/inicio/')

    datos, error = _obtener_datos_vehiculo(
        request,
        usuario_obligatorio=True
    )

    if error:
        messages.error(request, error)

        if usuario_id:
            return redirect('nuevovehiculo', id_usuario=usuario_id)

        return redirect('/inicio/')

    Vehiculo.objects.create(**datos)
    messages.success(request, "Vehículo guardado correctamente.")

    if es_admin:
        return redirect('listadocarros')

    return redirect('listadovehiculo')


def listadovehiculo(request):
    usuario_id = request.session.get('usuario_id')

    if not usuario_id:
        messages.error(request, "Inicia sesión nuevamente.")
        return redirect('/login')

    try:
        usuario = Usuario.objects.get(id_usuario=usuario_id)
    except Usuario.DoesNotExist:
        request.session.flush()
        messages.error(
            request,
            "Tu sesión no es válida. Inicia sesión nuevamente."
        )
        return redirect('/login')

    vehiculo = Vehiculo.objects.filter(usuario=usuario).first()

    return render(
        request,
        'usuario/vehiculos/listadovehiculo.html',
        {'vehiculo': vehiculo}
    )


def listadovista(request, id_usuario):
    acceso = _validar_acceso_admin_vehiculos(request)
    if acceso:
        return acceso

    try:
        usuario = Usuario.objects.get(id_usuario=id_usuario)
    except Usuario.DoesNotExist:
        messages.error(request, "El usuario no existe.")
        return redirect('listadocarros')

    vehiculo = Vehiculo.objects.filter(usuario=usuario).first()

    return render(
        request,
        'administrador/vehiculos/listadovista.html',
        {
            'vehiculo': vehiculo,
            'usuario': usuario,
        }
    )


def eliminarvehiculo(request, id):
    usuario_id = request.session.get('usuario_id')

    if not usuario_id:
        messages.error(request, "Inicia sesión nuevamente.")
        return redirect('/login')

    try:
        vehiculo = Vehiculo.objects.get(id_vehiculo=id)
    except Vehiculo.DoesNotExist:
        messages.error(request, "El vehículo no existe.")
        return redirect('/inicio/')

    es_admin = request.session.get('usuario_tiporol') == 'ADMINISTRADOR'
    es_propietario = vehiculo.usuario_id == int(usuario_id)

    if not es_admin and not es_propietario:
        messages.error(request, "No tienes permisos para eliminar este vehículo.")
        return redirect('/inicio/')

    vehiculo.delete()
    messages.success(request, "Vehículo eliminado correctamente.")

    if es_admin:
        return redirect('listadocarros')

    return redirect('/inicio/')


def editarvehiculo(request, id):
    usuario_id = request.session.get('usuario_id')

    if not usuario_id:
        messages.error(request, "Inicia sesión nuevamente.")
        return redirect('/login')

    try:
        vehiculo = Vehiculo.objects.select_related('usuario').get(
            id_vehiculo=id
        )
    except Vehiculo.DoesNotExist:
        messages.error(request, "El vehículo no existe.")
        return redirect('/inicio/')

    es_admin = request.session.get('usuario_tiporol') == 'ADMINISTRADOR'
    es_propietario = vehiculo.usuario_id == int(usuario_id)

    if not es_admin and not es_propietario:
        messages.error(request, "No tienes permisos para editar este vehículo.")
        return redirect('/inicio/')

    usuario_asignado = vehiculo.usuario

    if not usuario_asignado:
        messages.error(request, "El vehículo no tiene un usuario asignado.")

        if es_admin:
            return redirect('listadocarros')

        return redirect('listadovehiculo')

    return render(
        request,
        'usuario/vehiculos/editarvehiculo.html',
        {
            'vehiculo': vehiculo,
            'usuarios': usuario_asignado,
        }
    )


def procesareditarvehiculo(request):
    usuario_id = request.session.get('usuario_id')

    if not usuario_id:
        messages.error(request, "Inicia sesión nuevamente.")
        return redirect('/login')

    if request.method != 'POST':
        return redirect('/inicio/')

    id_vehiculo = request.POST.get('id')

    try:
        vehiculo = Vehiculo.objects.get(id_vehiculo=id_vehiculo)
    except Vehiculo.DoesNotExist:
        messages.error(request, "El vehículo no existe.")
        return redirect('/inicio/')

    es_admin = request.session.get('usuario_tiporol') == 'ADMINISTRADOR'
    es_propietario = vehiculo.usuario_id == int(usuario_id)

    if not es_admin and not es_propietario:
        messages.error(request, "No tienes permisos para editar este vehículo.")
        return redirect('/inicio/')

    usuario_formulario = request.POST.get('usuario', '').strip()

    if not es_admin and usuario_formulario != str(usuario_id):
        messages.error(
            request,
            "No puedes cambiar el usuario asignado al vehículo."
        )
        return redirect('editarvehiculo', id=vehiculo.id_vehiculo)

    datos, error = _obtener_datos_vehiculo(
        request,
        vehiculo_actual=vehiculo,
        usuario_obligatorio=True
    )

    if error:
        messages.error(request, error)
        return redirect('editarvehiculo', id=vehiculo.id_vehiculo)

    _actualizar_vehiculo(vehiculo, datos)
    messages.success(request, "Vehículo editado exitosamente.")

    if es_admin:
        return redirect('listadocarros')

    return redirect('listadovehiculo')


# =============================================================================
# CATÁLOGO DE PRODUCTOS PARA CARGA - ADMINISTRADOR
# =============================================================================

def _validar_acceso_admin_cargas(request):
    if not request.session.get('usuario_id'):
        return redirect('/login')

    if request.session.get('usuario_tiporol') != 'ADMINISTRADOR':
        messages.error(
            request,
            "No tienes permisos para administrar cargas."
        )
        return redirect('/inicio/')

    return None


def _obtener_datos_producto_carga(
    request,
    producto_actual=None
):
    modo_producto = request.POST.get(
        'txt_modo_producto',
        'CATALOGO'
    ).strip().upper()

    codigo_catalogo = request.POST.get(
        'txt_catalogo_producto',
        ''
    ).strip().upper()

    marca_catalogo = request.POST.get(
        'txt_marca_catalogo',
        ''
    ).strip()

    presentacion = request.POST.get(
        'txt_presentacion_producto',
        ''
    ).strip().upper()

    nota = request.POST.get(
        'txt_nota_producto',
        ''
    ).strip()

    peso_texto = request.POST.get(
        'txt_peso_unitario_kg',
        ''
    ).strip().replace(',', '.')

    presentaciones_validas = [
        opcion[0]
        for opcion in ProductoCarga.PRESENTACIONES
    ]

    if modo_producto not in ('CATALOGO', 'PERSONALIZADO'):
        return None, "Seleccione una forma válida de registrar el producto."

    if modo_producto == 'CATALOGO':
        if not marca_catalogo or marca_catalogo not in marcas_catalogo():
            return None, "Seleccione una marca válida del catálogo."

        item_catalogo = producto_catalogo_por_codigo(codigo_catalogo)

        # Compatibilidad con registros anteriores que todavía no tenían código.
        es_legacy = (
            producto_actual is not None
            and codigo_catalogo == f"LEGACY-{producto_actual.id_producto_carga}"
        )

        if item_catalogo:
            if marca_catalogo and marca_catalogo != item_catalogo['marca']:
                return None, (
                    "La marca seleccionada no corresponde al producto del catálogo. "
                    "Seleccione nuevamente la marca y el producto."
                )

            nombre = item_catalogo['nombre']
            marca = item_catalogo['marca']
            precio_referencia = item_catalogo['precio_referencia']
        elif es_legacy:
            nombre = producto_actual.nombre_producto
            marca = producto_actual.marca_producto
            precio_referencia = producto_actual.precio_referencia
            codigo_catalogo = producto_actual.codigo_catalogo or ''
        else:
            return None, (
                "Seleccione una marca y un producto válidos del registro."
            )

    else:
        # Producto propio: se mantiene una selección controlada de marca y solo se
        # permite escribir cuando realmente se necesita registrar una variante nueva.
        codigo_catalogo = ''
        nombre = request.POST.get(
            'txt_nombre_personalizado',
            ''
        ).strip()

        marca_seleccionada = request.POST.get(
            'txt_marca_personalizada_select',
            ''
        ).strip()

        if (
            marca_seleccionada != 'OTRA'
            and marca_seleccionada not in marcas_catalogo()
        ):
            return None, "Seleccione una marca válida para el producto propio."

        if marca_seleccionada == 'OTRA':
            marca = request.POST.get(
                'txt_marca_personalizada',
                ''
            ).strip()
        else:
            marca = marca_seleccionada

        precio_texto = request.POST.get(
            'txt_precio_referencia',
            ''
        ).strip().replace(',', '.')

        if len(nombre) < 2 or len(nombre) > 100:
            return None, (
                "Ingrese un nombre o variante del producto entre 2 y 100 caracteres."
            )

        if len(marca) < 2 or len(marca) > 100:
            return None, (
                "Seleccione una marca o escriba una marca válida para el producto propio."
            )

        precio_referencia = None
        if precio_texto:
            try:
                precio_referencia = Decimal(precio_texto)
            except Exception:
                return None, "Ingrese un precio de referencia válido."

            if precio_referencia < Decimal('0') or precio_referencia > Decimal('9999999.99'):
                return None, "El precio de referencia ingresado no es válido."

    if presentacion not in presentaciones_validas:
        return None, "Seleccione una presentación válida."

    if len(nota) > 250:
        return None, "La observación no puede superar los 250 caracteres."

    if not peso_texto and modo_producto == 'CATALOGO' and item_catalogo:
        peso_estimado = peso_estimado_presentacion(item_catalogo, presentacion)
        peso_texto = str(peso_estimado or '')

    try:
        peso_unitario_kg = Decimal(peso_texto)
    except Exception:
        return None, "Ingrese un peso unitario válido."

    if (
        peso_unitario_kg <= Decimal('0') or
        peso_unitario_kg > Decimal('2000')
    ):
        return None, (
            "El peso unitario debe ser mayor que 0 "
            "y no superar 2000 kg."
        )

    if codigo_catalogo:
        repetido = ProductoCarga.objects.filter(
            codigo_catalogo=codigo_catalogo,
            presentacion_producto=presentacion
        )
    else:
        repetido = ProductoCarga.objects.filter(
            nombre_producto__iexact=nombre,
            marca_producto__iexact=marca,
            presentacion_producto=presentacion
        )

    if producto_actual:
        repetido = repetido.exclude(
            id_producto_carga=producto_actual.id_producto_carga
        )

    if repetido.exists():
        return None, (
            "Ya existe este producto con la misma marca y presentación."
        )

    datos = {
        'codigo_catalogo': codigo_catalogo,
        'nombre_producto': nombre,
        'marca_producto': marca,
        'precio_referencia': precio_referencia,
        'presentacion_producto': presentacion,
        'nota_producto': nota,
        'peso_unitario_kg': peso_unitario_kg,
    }

    return datos, None

def listadoproductoscarga(request):
    acceso = _validar_acceso_admin_cargas(request)

    if acceso:
        return acceso

    productos = ProductoCarga.objects.all()

    return render(
        request,
        'administrador/productos_carga/listado_productos.html',
        {
            'productos': productos,
            'total_productos': productos.count(),
            'total_activos': productos.filter(
                activo=True
            ).count(),
            'total_inactivos': productos.filter(
                activo=False
            ).count(),
        }
    )


def nuevoproductocarga(request):
    acceso = _validar_acceso_admin_cargas(request)

    if acceso:
        return acceso

    return render(
        request,
        'administrador/productos_carga/formulario_producto.html',
        {
            'producto': None,
            'modo': 'crear',
            'presentaciones': (
                ProductoCarga.PRESENTACIONES
            ),
            'catalogo_productos': catalogo_productos(),
            'marcas_catalogo': marcas_catalogo(),
            'codigo_catalogo_actual': '',
            'marca_catalogo_actual': '',
            'modo_producto_actual': 'CATALOGO',
        }
    )


def guardarproductocarga(request):
    acceso = _validar_acceso_admin_cargas(request)

    if acceso:
        return acceso

    if request.method != 'POST':
        return redirect('listadoproductoscarga')

    datos, error = _obtener_datos_producto_carga(
        request
    )

    if error:
        messages.error(request, error)
        return redirect('nuevoproductocarga')

    ProductoCarga.objects.create(**datos, activo=True)

    messages.success(
        request,
        "Producto registrado correctamente."
    )

    return redirect('listadoproductoscarga')


def editarproductocarga(request, id):
    acceso = _validar_acceso_admin_cargas(request)

    if acceso:
        return acceso

    try:
        producto = ProductoCarga.objects.get(
            id_producto_carga=id
        )
    except ProductoCarga.DoesNotExist:
        messages.error(
            request,
            "El producto no existe."
        )
        return redirect('listadoproductoscarga')

    codigo_catalogo_actual = (
        producto.codigo_catalogo
        or codigo_catalogo_por_nombre(producto.nombre_producto)
    )
    item_catalogo_actual = producto_catalogo_por_codigo(
        codigo_catalogo_actual
    )

    return render(
        request,
        'administrador/productos_carga/formulario_producto.html',
        {
            'producto': producto,
            'modo': 'editar',
            'presentaciones': (
                ProductoCarga.PRESENTACIONES
            ),
            'catalogo_productos': catalogo_productos(),
            'marcas_catalogo': marcas_catalogo(),
            'codigo_catalogo_actual': codigo_catalogo_actual,
            'marca_catalogo_actual': (
                item_catalogo_actual['marca']
                if item_catalogo_actual else ''
            ),
            'modo_producto_actual': (
                'CATALOGO' if item_catalogo_actual else 'PERSONALIZADO'
            ),
        }
    )


def procesareditarproductocarga(request):
    acceso = _validar_acceso_admin_cargas(request)

    if acceso:
        return acceso

    if request.method != 'POST':
        return redirect('listadoproductoscarga')

    id_producto = request.POST.get(
        'id_producto_carga'
    )

    try:
        producto = ProductoCarga.objects.get(
            id_producto_carga=id_producto
        )
    except ProductoCarga.DoesNotExist:
        messages.error(
            request,
            "El producto no existe."
        )
        return redirect('listadoproductoscarga')

    datos, error = _obtener_datos_producto_carga(
        request,
        producto_actual=producto
    )

    if error:
        messages.error(request, error)
        return redirect(
            'editarproductocarga',
            id=producto.id_producto_carga
        )

    producto.codigo_catalogo = datos[
        'codigo_catalogo'
    ]

    producto.nombre_producto = datos[
        'nombre_producto'
    ]

    producto.marca_producto = datos[
        'marca_producto'
    ]

    producto.precio_referencia = datos[
        'precio_referencia'
    ]

    producto.presentacion_producto = datos[
        'presentacion_producto'
    ]

    producto.nota_producto = datos[
        'nota_producto'
    ]

    producto.peso_unitario_kg = datos[
        'peso_unitario_kg'
    ]

    producto.save()

    messages.success(
        request,
        "Producto actualizado correctamente."
    )

    return redirect('listadoproductoscarga')


def cambiarestadoproductocarga(request, id):
    acceso = _validar_acceso_admin_cargas(request)

    if acceso:
        return acceso

    if request.method != 'POST':
        return redirect('listadoproductoscarga')

    try:
        producto = ProductoCarga.objects.get(
            id_producto_carga=id
        )
    except ProductoCarga.DoesNotExist:
        messages.error(
            request,
            "El producto no existe."
        )
        return redirect('listadoproductoscarga')

    producto.activo = not producto.activo
    producto.save()

    if producto.activo:
        mensaje = "Producto activado correctamente."
    else:
        mensaje = "Producto inactivado correctamente."

    messages.success(request, mensaje)

    return redirect('listadoproductoscarga')


def eliminarproductocarga(request, id):
    acceso = _validar_acceso_admin_cargas(request)
    if acceso:
        return acceso
    if request.method != 'POST':
        return redirect('listadoproductoscarga')

    try:
        producto = ProductoCarga.objects.get(id_producto_carga=id)
    except ProductoCarga.DoesNotExist:
        messages.error(request, "El producto no existe.")
        return redirect('listadoproductoscarga')

    try:
        nombre = producto.nombre_producto
        producto.delete()
        messages.success(request, f'Producto "{nombre}" eliminado correctamente.')
    except ProtectedError:
        messages.error(
            request,
            "Este producto ya forma parte de una carga y no puede eliminarse. "
            "Puedes inactivarlo para conservar el historial."
        )
    return redirect('listadoproductoscarga')


# =============================================================================
# PRECIOS DE COMBUSTIBLE - ADMINISTRADOR
# =============================================================================

def precioscombustibleadmin(request):
    acceso = _validar_acceso_admin_cargas(request)
    if acceso:
        return acceso

    tipos = list(PrecioCombustible.TIPO_CHOICES)
    litros_por_galon = Decimal('3.785411784')

    if request.method == 'POST':
        unidad = (request.POST.get('unidad_precio') or 'LITRO').strip().upper()
        if unidad not in {'LITRO', 'GALON'}:
            messages.error(request, 'Seleccione una unidad válida para los precios.')
            return redirect('precioscombustibleadmin')

        nuevos = {}
        for tipo, etiqueta in tipos:
            texto = request.POST.get(f'precio_{tipo}', '').strip().replace(',', '.')
            try:
                valor_ingresado = Decimal(texto)
            except Exception:
                messages.error(request, f'Ingrese un precio válido para {etiqueta}.')
                return redirect('precioscombustibleadmin')

            limite = Decimal('1000')
            if valor_ingresado <= Decimal('0') or valor_ingresado > limite:
                messages.error(
                    request,
                    f'El precio de {etiqueta} debe ser mayor que 0 y no superar {limite} USD por unidad.'
                )
                return redirect('precioscombustibleadmin')

            precio_litro = (
                valor_ingresado / litros_por_galon
                if unidad == 'GALON'
                else valor_ingresado
            ).quantize(Decimal('0.0001'))
            nuevos[tipo] = (valor_ingresado.quantize(Decimal('0.0001')), precio_litro)

        admin_id = request.session.get('usuario_id')
        administrador_usuario = None
        if admin_id:
            try:
                administrador_usuario = Usuario.objects.get(id_usuario=admin_id)
            except Usuario.DoesNotExist:
                administrador_usuario = None

        cambios = 0
        with transaction.atomic():
            for tipo, (valor_ingresado, precio_litro) in nuevos.items():
                registro = PrecioCombustible.objects.filter(tipo=tipo).order_by('-id_precio').first()
                anterior = (
                    Decimal(str(registro.precio_por_litro)).quantize(Decimal('0.0001'))
                    if registro else None
                )
                if registro:
                    registro.precio_por_litro = float(precio_litro)
                    registro.save(update_fields=['precio_por_litro'])
                else:
                    PrecioCombustible.objects.create(tipo=tipo, precio_por_litro=float(precio_litro))

                if anterior is None or anterior != precio_litro:
                    HistorialPrecioCombustible.objects.create(
                        tipo=tipo,
                        precio_anterior_litro=anterior,
                        precio_nuevo_litro=precio_litro,
                        valor_ingresado=valor_ingresado,
                        unidad_ingresada=unidad,
                        administrador=administrador_usuario,
                    )
                    cambios += 1

        if cambios:
            unidad_texto = 'galón' if unidad == 'GALON' else 'litro'
            messages.success(
                request,
                f'Precios actualizados en USD/{unidad_texto}. Los nuevos cálculos de ruta ya usan estos valores.'
            )
        else:
            messages.info(request, 'No hubo cambios en los precios configurados.')
        return redirect('precioscombustibleadmin')

    filas = []
    for tipo, etiqueta in tipos:
        registro = PrecioCombustible.objects.filter(tipo=tipo).order_by('-id_precio').first()
        precio = Decimal(str(registro.precio_por_litro)) if registro else Decimal('0')
        filas.append({
            'tipo': tipo,
            'etiqueta': etiqueta,
            'precio_litro': precio.quantize(Decimal('0.0001')),
            'precio_galon': (precio * litros_por_galon).quantize(Decimal('0.0001')),
            'configurado': bool(registro),
        })

    historial = (
        HistorialPrecioCombustible.objects
        .select_related('administrador')
        .all()[:200]
    )

    return render(
        request,
        'administrador/combustible/precios_combustible.html',
        {'precios': filas, 'historial': historial}
    )


@require_GET
def historialprecioscombustiblepdf(request):
    acceso = _validar_acceso_admin_cargas(request)
    if acceso:
        return acceso

    historial = list(
        HistorialPrecioCombustible.objects
        .select_related('administrador')
        .all()[:500]
    )
    contenido = construir_pdf_historial_precios(historial)
    response = HttpResponse(contenido, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="historial_precios_combustible.pdf"'
    return response


# =============================================================================
# PLANIFICACIÓN DE CARGAS - ADMINISTRADOR
# =============================================================================

def _sumar_meses_fecha(fecha_base, meses):
    """Suma meses conservando el día cuando existe en el mes destino."""
    indice_mes = fecha_base.month - 1 + meses
    anio = fecha_base.year + indice_mes // 12
    mes = indice_mes % 12 + 1
    ultimo_dia = calendar.monthrange(anio, mes)[1]
    dia = min(fecha_base.day, ultimo_dia)
    return fecha_base.replace(year=anio, month=mes, day=dia)


def _limites_fecha_plan_carga():
    fecha_minima = timezone.localdate()
    fecha_maxima = _sumar_meses_fecha(fecha_minima, 6)
    return fecha_minima, fecha_maxima


def _fecha_plan_carga_desde_texto(fecha_texto=None):
    fecha_minima, _ = _limites_fecha_plan_carga()

    if not fecha_texto:
        return fecha_minima

    return parse_date(fecha_texto) or fecha_minima


def _fecha_plan_carga_en_rango(fecha):
    fecha_minima, fecha_maxima = _limites_fecha_plan_carga()
    return fecha_minima <= fecha <= fecha_maxima


def _plan_carga_es_historico(plan):
    return bool(plan and plan.fecha_planificada < timezone.localdate())


def _bloquear_modificacion_plan_historico(request, plan):
    if not _plan_carga_es_historico(plan):
        return None
    messages.error(
        request,
        'Los planes anteriores pueden consultarse, pero ya no pueden modificarse.'
    )
    return redirect('detalleplancarga', id=plan.id_plan_carga)


def _reiniciar_revision_y_confirmacion(plan):
    plan.revisado_por_usuario = False
    plan.fecha_revision_usuario = None
    plan.confirmado_por = None
    plan.fecha_confirmacion = None


def _validar_coordenada(valor, minimo, maximo):
    try:
        numero = Decimal(str(valor).replace(',', '.'))
    except Exception:
        return None

    if numero < Decimal(str(minimo)) or numero > Decimal(str(maximo)):
        return None

    return numero


def _validar_plan_para_salida(plan, exigir_revision=False):
    errores = []

    if not plan.vehiculo.usuario:
        errores.append(
            'El vehículo debe tener un usuario asignado.'
        )

    if plan.capacidad_kg <= 0:
        errores.append(
            'El vehículo no tiene una capacidad máxima válida.'
        )

    detalles_activos = [
        detalle
        for detalle in plan.detalles.all()
        if detalle.cantidad_actual > 0
    ]

    if not detalles_activos:
        errores.append(
            'La carga debe contener al menos un producto activo.'
        )

    if plan.peso_total_kg > plan.capacidad_kg:
        errores.append(
            'El peso efectivo supera la capacidad del vehículo.'
        )

    if exigir_revision and not plan.revisado_por_usuario:
        errores.append(
            'El conductor todavía no ha revisado la carga.'
        )

    return errores


def _resumen_distribucion_plan(plan):
    detalles = list(
        plan.detalles.prefetch_related('entregas').all()
    )

    total_unidades = 0
    unidades_distribuidas = 0

    for detalle in detalles:
        detalle.cantidad_distribuida = sum(
            entrega.cantidad_actual
            for entrega in detalle.entregas.all()
        )

        detalle.cantidad_pendiente = max(
            detalle.cantidad_actual -
            detalle.cantidad_distribuida,
            0
        )

        total_unidades += detalle.cantidad_actual
        unidades_distribuidas += detalle.cantidad_distribuida

    return {
        'detalles': detalles,
        'total_unidades': total_unidades,
        'unidades_distribuidas': unidades_distribuidas,
        'unidades_pendientes': max(
            total_unidades - unidades_distribuidas,
            0
        ),
        'peso_distribuido': plan.peso_asignado_paradas_kg,
        'peso_pendiente': plan.peso_sin_destino_kg,
    }


def listadoplanescarga(request):
    acceso = _validar_acceso_admin_cargas(request)
    if acceso:
        return acceso

    fecha_minima, fecha_maxima = _limites_fecha_plan_carga()
    fecha_texto = (request.GET.get('fecha') or '').strip()
    fecha_seleccionada = parse_date(fecha_texto) if fecha_texto else fecha_minima
    if not fecha_seleccionada:
        fecha_seleccionada = fecha_minima

    es_fecha_historica = fecha_seleccionada < fecha_minima
    fecha_editable = fecha_minima <= fecha_seleccionada <= fecha_maxima

    vehiculos = list(
        Vehiculo.objects.select_related('usuario').all().order_by('matricula_vehiculo')
    )
    vehiculos_creacion = [
        vehiculo for vehiculo in vehiculos
        if vehiculo.capacidad_carga_kg and vehiculo.capacidad_carga_kg > 0
    ]

    planes = list(
        PlanCarga.objects.filter(fecha_planificada=fecha_seleccionada)
        .select_related('vehiculo', 'vehiculo__usuario')
        .prefetch_related('detalles')
        .order_by('vehiculo__matricula_vehiculo')
    )
    planes_por_vehiculo = {plan.vehiculo_id: plan for plan in planes}

    peso_total_programado = Decimal('0.00')
    total_listos = total_confirmados = total_borradores = 0

    for vehiculo in vehiculos:
        plan = planes_por_vehiculo.get(vehiculo.id_vehiculo)
        vehiculo.plan_actual = plan
        if not plan:
            continue
        plan.peso_calculado = plan.peso_total_kg
        plan.capacidad_calculada = plan.capacidad_kg
        plan.disponible_calculado = plan.disponible_kg
        plan.porcentaje_calculado = plan.porcentaje_carga
        plan.es_historico = es_fecha_historica
        peso_total_programado += plan.peso_calculado
        if plan.estado == 'LISTO':
            total_listos += 1
        elif plan.estado == 'CONFIRMADO':
            total_confirmados += 1
        elif plan.estado == 'BORRADOR':
            total_borradores += 1

    return render(request, 'administrador/plan_cargas/listado_planes.html', {
        'vehiculos': vehiculos,
        'vehiculos_creacion': vehiculos_creacion,
        'planes': planes,
        'fecha_seleccionada': fecha_seleccionada,
        'fecha_minima': fecha_minima,
        'fecha_maxima': fecha_maxima,
        'fecha_creacion_inicial': fecha_minima,
        'es_fecha_historica': es_fecha_historica,
        'fecha_editable': fecha_editable,
        'total_vehiculos': len(vehiculos),
        'total_planes': len(planes),
        'total_listos': total_listos,
        'total_confirmados': total_confirmados,
        'total_borradores': total_borradores,
        'peso_total_programado': peso_total_programado,
    })


@require_POST
def crearplancargadesdeformulario(request):
    acceso = _validar_acceso_admin_cargas(request)
    if acceso:
        return acceso

    vehiculo_id = (request.POST.get('vehiculo_id') or '').strip()
    fecha_texto = (request.POST.get('fecha_planificada') or '').strip()
    fecha = parse_date(fecha_texto)

    if not vehiculo_id or not fecha:
        messages.error(request, 'Selecciona un vehículo y una fecha válida.')
        return redirect('listadoplanescarga')
    if not _fecha_plan_carga_en_rango(fecha):
        fecha_minima, fecha_maxima = _limites_fecha_plan_carga()
        messages.error(
            request,
            f'La nueva carga debe programarse entre {fecha_minima.strftime("%d/%m/%Y")} '
            f'y {fecha_maxima.strftime("%d/%m/%Y")}.'
        )
        return redirect(f"{reverse('listadoplanescarga')}?fecha={fecha.isoformat()}")

    try:
        vehiculo = Vehiculo.objects.get(id_vehiculo=int(vehiculo_id))
    except (Vehiculo.DoesNotExist, TypeError, ValueError):
        messages.error(request, 'El vehículo seleccionado no existe.')
        return redirect('listadoplanescarga')

    if not vehiculo.capacidad_carga_kg or vehiculo.capacidad_carga_kg <= 0:
        messages.error(request, 'El vehículo necesita una capacidad máxima antes de crear la carga.')
        return redirect('editarvehiculoadmin', id=vehiculo.id_vehiculo)

    url = reverse('crearplancarga', kwargs={'id_vehiculo': vehiculo.id_vehiculo})
    return redirect(f'{url}?fecha={fecha.isoformat()}')



def crearplancarga(request, id_vehiculo):
    acceso = _validar_acceso_admin_cargas(request)

    if acceso:
        return acceso

    try:
        vehiculo = Vehiculo.objects.get(id_vehiculo=id_vehiculo)
    except Vehiculo.DoesNotExist:
        messages.error(request, 'El vehículo no existe.')
        return redirect('listadoplanescarga')

    if not vehiculo.capacidad_carga_kg:
        messages.error(
            request,
            'Primero registra la capacidad máxima de carga del vehículo.'
        )
        return redirect(
            'editarvehiculoadmin',
            id=vehiculo.id_vehiculo
        )

    fecha_planificada = _fecha_plan_carga_desde_texto(
        request.GET.get('fecha')
    )

    if not _fecha_plan_carga_en_rango(fecha_planificada):
        fecha_minima, fecha_maxima = _limites_fecha_plan_carga()
        messages.error(
            request,
            'La fecha de la carga debe estar entre '
            f'{fecha_minima.strftime("%d/%m/%Y")} y '
            f'{fecha_maxima.strftime("%d/%m/%Y")}.'
        )
        return redirect(
            f'/plan-cargas/?fecha={fecha_minima.isoformat()}'
        )

    try:
        creado_por = Usuario.objects.get(
            id_usuario=request.session.get('usuario_id')
        )
    except Usuario.DoesNotExist:
        creado_por = None

    plan, creado = PlanCarga.objects.get_or_create(
        vehiculo=vehiculo,
        fecha_planificada=fecha_planificada,
        defaults={
            'estado': 'BORRADOR',
            'creado_por': creado_por,
        }
    )

    if not creado and plan.estado == 'CANCELADO':
        plan.estado = 'BORRADOR'
        _reiniciar_revision_y_confirmacion(plan)
        plan.save()
        messages.info(
            request,
            'El plan cancelado volvió a estado borrador.'
        )

    return redirect(
        'prepararplancarga',
        id=plan.id_plan_carga
    )


def prepararplancarga(request, id):
    acceso = _validar_acceso_admin_cargas(request)

    if acceso:
        return acceso

    try:
        plan = PlanCarga.objects.select_related(
            'vehiculo',
            'vehiculo__usuario'
        ).prefetch_related(
            'detalles',
            'detalles__producto'
        ).get(id_plan_carga=id)
    except PlanCarga.DoesNotExist:
        messages.error(request, 'El plan de carga no existe.')
        return redirect('listadoplanescarga')

    bloqueo = _bloquear_modificacion_plan_historico(request, plan)
    if bloqueo:
        return bloqueo

    if plan.estado != 'BORRADOR':
        messages.error(
            request,
            'Solo los planes en borrador permiten editar productos.'
        )
        return redirect(
            'detalleplancarga',
            id=plan.id_plan_carga
        )

    if not plan.vehiculo.capacidad_carga_kg:
        messages.error(
            request,
            'El vehículo no tiene una capacidad máxima registrada.'
        )
        return redirect(
            'editarvehiculoadmin',
            id=plan.vehiculo.id_vehiculo
        )

    detalles_actuales = {
        detalle.producto_id: detalle
        for detalle in plan.detalles.all()
    }

    productos = list(
        ProductoCarga.objects.filter(
            Q(activo=True) |
            Q(detalles_plan__plan=plan)
        ).distinct().order_by(
            'nombre_producto',
            'marca_producto'
        )
    )

    for producto in productos:
        detalle = detalles_actuales.get(
            producto.id_producto_carga
        )
        producto.cantidad_plan = (
            detalle.cantidad_actual
            if detalle
            else 0
        )
        producto.subtotal_plan = (
            detalle.peso_actual_kg
            if detalle
            else Decimal('0.00')
        )

    return render(
        request,
        'administrador/plan_cargas/preparar_carga.html',
        {
            'plan': plan,
            'productos': productos,
            'peso_total': plan.peso_total_kg,
            'capacidad': plan.capacidad_kg,
            'disponible': plan.disponible_kg,
            'porcentaje': plan.porcentaje_carga,
        }
    )


def guardarplancarga(request, id):
    acceso = _validar_acceso_admin_cargas(request)

    if acceso:
        return acceso

    if request.method != 'POST':
        return redirect('listadoplanescarga')

    try:
        plan = PlanCarga.objects.select_related(
            'vehiculo',
            'vehiculo__usuario'
        ).prefetch_related('detalles').get(
            id_plan_carga=id
        )
    except PlanCarga.DoesNotExist:
        messages.error(request, 'El plan de carga no existe.')
        return redirect('listadoplanescarga')

    bloqueo = _bloquear_modificacion_plan_historico(request, plan)
    if bloqueo:
        return bloqueo

    if plan.estado != 'BORRADOR':
        messages.error(
            request,
            'Solo los planes en borrador pueden modificarse.'
        )
        return redirect(
            'detalleplancarga',
            id=plan.id_plan_carga
        )

    capacidad = plan.capacidad_kg

    if capacidad <= 0:
        messages.error(
            request,
            'El vehículo no tiene una capacidad de carga válida.'
        )
        return redirect(
            'editarvehiculoadmin',
            id=plan.vehiculo.id_vehiculo
        )

    notas = request.POST.get(
        'notas',
        ''
    ).strip()

    if len(notas) > 1000:
        messages.error(
            request,
            'Las notas no pueden superar 1000 caracteres.'
        )
        return redirect(
            'prepararplancarga',
            id=plan.id_plan_carga
        )

    cantidades = {}

    for clave, valor in request.POST.items():
        if not clave.startswith('cantidad_'):
            continue

        try:
            producto_id = int(
                clave.replace('cantidad_', '', 1)
            )
            cantidad = int(valor or 0)
        except (TypeError, ValueError):
            messages.error(request, 'Existe una cantidad inválida.')
            return redirect(
                'prepararplancarga',
                id=plan.id_plan_carga
            )

        if cantidad < 0 or cantidad > 9999:
            messages.error(
                request,
                'Cada cantidad debe estar entre 0 y 9999.'
            )
            return redirect(
                'prepararplancarga',
                id=plan.id_plan_carga
            )

        if cantidad > 0:
            cantidades[producto_id] = cantidad

    productos = ProductoCarga.objects.filter(
        id_producto_carga__in=cantidades.keys()
    )
    productos_por_id = {
        producto.id_producto_carga: producto
        for producto in productos
    }

    if len(productos_por_id) != len(cantidades):
        messages.error(
            request,
            'Uno de los productos seleccionados no existe.'
        )
        return redirect(
            'prepararplancarga',
            id=plan.id_plan_carga
        )

    productos_anteriores = set(
        plan.detalles.values_list('producto_id', flat=True)
    )
    peso_total = Decimal('0.00')

    for producto_id, cantidad in cantidades.items():
        producto = productos_por_id[producto_id]

        if (
            not producto.activo and
            producto_id not in productos_anteriores
        ):
            messages.error(
                request,
                f'El producto {producto.nombre_producto} está inactivo.'
            )
            return redirect(
                'prepararplancarga',
                id=plan.id_plan_carga
            )

        peso_total += (
            Decimal(cantidad) *
            producto.peso_unitario_kg
        )

    if peso_total > capacidad:
        exceso = peso_total - capacidad
        messages.error(
            request,
            f'La carga alcanza {peso_total:.2f} kg, '
            f'pero la capacidad es {capacidad:.2f} kg. '
            f'Exceso: {exceso:.2f} kg.'
        )
        return redirect(
            'prepararplancarga',
            id=plan.id_plan_carga
        )

    with transaction.atomic():
        plan_bloqueado = PlanCarga.objects.select_for_update().get(
            id_plan_carga=plan.id_plan_carga
        )

        detalles_existentes = {
            detalle.producto_id: detalle
            for detalle in DetallePlanCarga.objects.filter(
                plan=plan_bloqueado
            )
        }

        for producto_id, cantidad in cantidades.items():
            producto = productos_por_id[producto_id]
            detalle = detalles_existentes.pop(producto_id, None)

            if detalle:
                cantidad_cambio = (
                    detalle.cantidad != cantidad or
                    detalle.cantidad_actual != cantidad
                )

                if cantidad_cambio:
                    detalle.entregas.all().delete()

                detalle.cantidad = cantidad
                detalle.cantidad_actual = cantidad
                detalle.origen = 'ADMINISTRADOR'
                detalle.agregado_por = None
                detalle.peso_unitario_kg = producto.peso_unitario_kg
                detalle.save()
            else:
                DetallePlanCarga.objects.create(
                    plan=plan_bloqueado,
                    producto=producto,
                    cantidad=cantidad,
                    cantidad_actual=cantidad,
                    origen='ADMINISTRADOR',
                    peso_unitario_kg=producto.peso_unitario_kg,
                    peso_subtotal_kg=(
                        Decimal(cantidad) *
                        producto.peso_unitario_kg
                    ),
                    peso_actual_kg=(
                        Decimal(cantidad) *
                        producto.peso_unitario_kg
                    )
                )

        for detalle in detalles_existentes.values():
            detalle.delete()

        # Las paradas ya no se administran al preparar la carga.
        # Si este borrador tenía una distribución antigua, se limpia
        # para que posteriormente el conductor la defina durante la ruta.
        plan_bloqueado.paradas.all().delete()

        plan_bloqueado.notas = notas
        plan_bloqueado.estado = 'BORRADOR'
        plan_bloqueado.ajustado_por_usuario = False
        plan_bloqueado.fecha_ultimo_ajuste_usuario = None
        _reiniciar_revision_y_confirmacion(plan_bloqueado)
        plan_bloqueado.save()

    messages.success(
        request,
        'Carga guardada y asignada correctamente al conductor.'
    )

    return redirect(
        'detalleplancarga',
        id=plan.id_plan_carga
    )


def detalleplancarga(request, id):
    acceso = _validar_acceso_admin_cargas(request)

    if acceso:
        return acceso

    try:
        plan = PlanCarga.objects.select_related(
            'vehiculo',
            'vehiculo__usuario',
            'creado_por',
            'confirmado_por'
        ).prefetch_related(
            'detalles',
            'detalles__producto',
            'ajustes_usuario',
            'ajustes_usuario__usuario'
        ).get(id_plan_carga=id)
    except PlanCarga.DoesNotExist:
        messages.error(request, 'El plan de carga no existe.')
        return redirect('listadoplanescarga')

    errores_salida = _validar_plan_para_salida(plan)

    return render(
        request,
        'administrador/plan_cargas/detalle_plan.html',
        {
            'plan': plan,
            'peso_programado': plan.peso_programado_kg,
            'peso_total': plan.peso_total_kg,
            'peso_descartado': plan.peso_descartado_kg,
            'peso_agregado_usuario': plan.peso_agregado_usuario_kg,
            'capacidad': plan.capacidad_kg,
            'disponible': plan.disponible_kg,
            'porcentaje': plan.porcentaje_carga,
            'ajustes': plan.ajustes_usuario.all(),
            'errores_salida': errores_salida,
            'es_historico': _plan_carga_es_historico(plan),
        }
    )


def _redireccion_paradas_reservadas_usuario(request):
    acceso = _validar_acceso_admin_cargas(request)

    if acceso:
        return acceso

    messages.info(
        request,
        'Las paradas y entregas se gestionarán desde el recorrido del conductor.'
    )
    return redirect('listadoplanescarga')


def gestionarparadasplancarga(request, id):
    return _redireccion_paradas_reservadas_usuario(request)

    acceso = _validar_acceso_admin_cargas(request)

    if acceso:
        return acceso

    try:
        plan = PlanCarga.objects.select_related(
            'vehiculo',
            'vehiculo__usuario'
        ).prefetch_related(
            'detalles',
            'detalles__producto',
            'detalles__entregas',
            'paradas',
            'paradas__entregas',
            'paradas__entregas__detalle',
            'paradas__entregas__detalle__producto'
        ).get(id_plan_carga=id)
    except PlanCarga.DoesNotExist:
        messages.error(request, 'El plan de carga no existe.')
        return redirect('listadoplanescarga')

    if plan.estado != 'BORRADOR':
        messages.error(
            request,
            'Vuelve el plan a borrador para modificar las paradas.'
        )
        return redirect(
            'detalleplancarga',
            id=plan.id_plan_carga
        )

    lugares_guardados = Lugarguardado.objects.none()

    if plan.vehiculo.usuario:
        lugares_guardados = Lugarguardado.objects.filter(
            usuario=plan.vehiculo.usuario
        ).order_by('-fecha_guardado')

    resumen = _resumen_distribucion_plan(plan)

    return render(
        request,
        'administrador/plan_cargas/gestionar_paradas.html',
        {
            'plan': plan,
            'paradas': plan.paradas.all(),
            'detalles': resumen['detalles'],
            'lugares_guardados': lugares_guardados,
            'resumen_distribucion': resumen,
        }
    )


def agregarparadaplancarga(request, id):
    return _redireccion_paradas_reservadas_usuario(request)

    acceso = _validar_acceso_admin_cargas(request)

    if acceso:
        return acceso

    if request.method != 'POST':
        return redirect('detalleplancarga', id=id)

    try:
        plan = PlanCarga.objects.select_related(
            'vehiculo__usuario'
        ).get(id_plan_carga=id)
    except PlanCarga.DoesNotExist:
        messages.error(request, 'El plan de carga no existe.')
        return redirect('listadoplanescarga')

    if plan.estado != 'BORRADOR':
        messages.error(request, 'El plan no permite agregar paradas.')
        return redirect('detalleplancarga', id=plan.id_plan_carga)

    lugar_id = request.POST.get('lugar_guardado', '').strip()
    nombre = request.POST.get('nombre_parada', '').strip()
    direccion = request.POST.get('direccion_parada', '').strip()
    latitud_texto = request.POST.get('latitud', '').strip()
    longitud_texto = request.POST.get('longitud', '').strip()
    observaciones = request.POST.get('observaciones', '').strip()

    if lugar_id:
        try:
            lugar = Lugarguardado.objects.get(
                id_Lugarguardado=lugar_id,
                usuario=plan.vehiculo.usuario
            )
        except Lugarguardado.DoesNotExist:
            messages.error(request, 'El lugar guardado no es válido.')
            return redirect('gestionarparadasplancarga', id=plan.id_plan_carga)

        nombre = nombre or lugar.nombre_Lugarguardado[:150]
        direccion = direccion or lugar.nombre_Lugarguardado[:250]
        latitud_texto = str(lugar.latitud_Lugarguardado)
        longitud_texto = str(lugar.longitud_Lugarguardado)

    if len(nombre) < 2 or len(nombre) > 150:
        messages.error(request, 'El nombre debe tener entre 2 y 150 caracteres.')
        return redirect('gestionarparadasplancarga', id=plan.id_plan_carga)

    if len(direccion) < 5 or len(direccion) > 250:
        messages.error(request, 'La dirección debe tener entre 5 y 250 caracteres.')
        return redirect('gestionarparadasplancarga', id=plan.id_plan_carga)

    if len(observaciones) > 250:
        messages.error(request, 'La nota no puede superar 250 caracteres.')
        return redirect('gestionarparadasplancarga', id=plan.id_plan_carga)

    latitud = _validar_coordenada(latitud_texto, -90, 90)
    longitud = _validar_coordenada(longitud_texto, -180, 180)

    if latitud is None or longitud is None:
        messages.error(request, 'Las coordenadas ingresadas no son válidas.')
        return redirect('gestionarparadasplancarga', id=plan.id_plan_carga)

    orden_actual = plan.paradas.aggregate(
        maximo=Max('orden')
    ).get('maximo') or 0

    ParadaPlanCarga.objects.create(
        plan=plan,
        nombre_parada=nombre,
        direccion_parada=direccion,
        latitud=latitud,
        longitud=longitud,
        orden=orden_actual + 1,
        observaciones=observaciones
    )

    messages.success(request, 'Parada agregada correctamente.')
    return redirect('gestionarparadasplancarga', id=plan.id_plan_carga)


def editarparadaplancarga(request, id):
    return _redireccion_paradas_reservadas_usuario(request)

    acceso = _validar_acceso_admin_cargas(request)

    if acceso:
        return acceso

    try:
        parada = ParadaPlanCarga.objects.select_related('plan').get(
            id_parada_plan_carga=id
        )
    except ParadaPlanCarga.DoesNotExist:
        messages.error(request, 'La parada no existe.')
        return redirect('listadoplanescarga')

    plan = parada.plan

    if request.method != 'POST':
        return redirect('gestionarparadasplancarga', id=plan.id_plan_carga)

    if plan.estado != 'BORRADOR':
        messages.error(request, 'El plan no permite editar paradas.')
        return redirect('detalleplancarga', id=plan.id_plan_carga)

    nombre = request.POST.get('nombre_parada', '').strip()
    direccion = request.POST.get('direccion_parada', '').strip()
    latitud = _validar_coordenada(
        request.POST.get('latitud', '').strip(),
        -90,
        90
    )
    longitud = _validar_coordenada(
        request.POST.get('longitud', '').strip(),
        -180,
        180
    )
    observaciones = request.POST.get('observaciones', '').strip()

    if len(nombre) < 2 or len(nombre) > 150:
        messages.error(request, 'El nombre de la parada no es válido.')
        return redirect('gestionarparadasplancarga', id=plan.id_plan_carga)

    if len(direccion) < 5 or len(direccion) > 250:
        messages.error(request, 'La dirección de la parada no es válida.')
        return redirect('gestionarparadasplancarga', id=plan.id_plan_carga)

    if latitud is None or longitud is None:
        messages.error(request, 'Las coordenadas no son válidas.')
        return redirect('gestionarparadasplancarga', id=plan.id_plan_carga)

    try:
        orden = int(request.POST.get('orden', parada.orden))
    except (TypeError, ValueError):
        orden = parada.orden

    if orden <= 0:
        messages.error(request, 'El orden debe ser mayor que cero.')
        return redirect('gestionarparadasplancarga', id=plan.id_plan_carga)

    repetida = ParadaPlanCarga.objects.filter(
        plan=plan,
        orden=orden
    ).exclude(
        id_parada_plan_carga=parada.id_parada_plan_carga
    ).exists()

    if repetida:
        messages.error(request, 'Ya existe otra parada con ese orden.')
        return redirect('gestionarparadasplancarga', id=plan.id_plan_carga)

    parada.nombre_parada = nombre
    parada.direccion_parada = direccion
    parada.latitud = latitud
    parada.longitud = longitud
    parada.orden = orden
    parada.observaciones = observaciones[:250]
    parada.save()

    messages.success(request, 'Parada actualizada correctamente.')
    return redirect('gestionarparadasplancarga', id=plan.id_plan_carga)


def eliminarparadaplancarga(request, id):
    return _redireccion_paradas_reservadas_usuario(request)

    acceso = _validar_acceso_admin_cargas(request)

    if acceso:
        return acceso

    try:
        parada = ParadaPlanCarga.objects.select_related('plan').get(
            id_parada_plan_carga=id
        )
    except ParadaPlanCarga.DoesNotExist:
        messages.error(request, 'La parada no existe.')
        return redirect('listadoplanescarga')

    plan = parada.plan

    if request.method != 'POST':
        return redirect('gestionarparadasplancarga', id=plan.id_plan_carga)

    if plan.estado != 'BORRADOR':
        messages.error(request, 'El plan no permite eliminar paradas.')
        return redirect('detalleplancarga', id=plan.id_plan_carga)

    parada.delete()
    messages.success(request, 'Parada eliminada correctamente.')
    return redirect('gestionarparadasplancarga', id=plan.id_plan_carga)


def guardarentregaparada(request, id):
    return _redireccion_paradas_reservadas_usuario(request)

    acceso = _validar_acceso_admin_cargas(request)

    if acceso:
        return acceso

    try:
        parada = ParadaPlanCarga.objects.select_related('plan').get(
            id_parada_plan_carga=id
        )
    except ParadaPlanCarga.DoesNotExist:
        messages.error(request, 'La parada no existe.')
        return redirect('listadoplanescarga')

    plan = parada.plan

    if request.method != 'POST':
        return redirect('gestionarparadasplancarga', id=plan.id_plan_carga)

    if plan.estado != 'BORRADOR':
        messages.error(request, 'El plan no permite modificar entregas.')
        return redirect('detalleplancarga', id=plan.id_plan_carga)

    detalle_id = request.POST.get('detalle', '').strip()

    try:
        cantidad = int(request.POST.get('cantidad', '0'))
    except (TypeError, ValueError):
        cantidad = 0

    if cantidad <= 0:
        messages.error(request, 'La cantidad debe ser mayor que cero.')
        return redirect('gestionarparadasplancarga', id=plan.id_plan_carga)

    try:
        detalle = DetallePlanCarga.objects.prefetch_related('entregas').get(
            id_detalle_plan_carga=detalle_id,
            plan=plan
        )
    except DetallePlanCarga.DoesNotExist:
        messages.error(request, 'El producto seleccionado no es válido.')
        return redirect('gestionarparadasplancarga', id=plan.id_plan_carga)

    entrega_existente = EntregaPlanCarga.objects.filter(
        parada=parada,
        detalle=detalle
    ).first()

    cantidad_otros = sum(
        entrega.cantidad_actual
        for entrega in detalle.entregas.exclude(
            id_entrega_plan_carga=(
                entrega_existente.id_entrega_plan_carga
                if entrega_existente
                else None
            )
        )
    )

    if cantidad_otros + cantidad > detalle.cantidad_actual:
        disponible = max(
            detalle.cantidad_actual - cantidad_otros,
            0
        )
        messages.error(
            request,
            f'Solo quedan {disponible} unidades disponibles para distribuir.'
        )
        return redirect('gestionarparadasplancarga', id=plan.id_plan_carga)

    if entrega_existente:
        entrega_existente.cantidad_asignada = cantidad
        entrega_existente.cantidad_actual = cantidad
        entrega_existente.save()
    else:
        EntregaPlanCarga.objects.create(
            parada=parada,
            detalle=detalle,
            cantidad_asignada=cantidad,
            cantidad_actual=cantidad,
            peso_unitario_kg=detalle.peso_unitario_kg
        )

    messages.success(request, 'Entrega guardada correctamente.')
    return redirect('gestionarparadasplancarga', id=plan.id_plan_carga)


def eliminarentregaparada(request, id):
    return _redireccion_paradas_reservadas_usuario(request)

    acceso = _validar_acceso_admin_cargas(request)

    if acceso:
        return acceso

    try:
        entrega = EntregaPlanCarga.objects.select_related(
            'parada__plan'
        ).get(id_entrega_plan_carga=id)
    except EntregaPlanCarga.DoesNotExist:
        messages.error(request, 'La entrega no existe.')
        return redirect('listadoplanescarga')

    plan = entrega.parada.plan

    if request.method != 'POST':
        return redirect('gestionarparadasplancarga', id=plan.id_plan_carga)

    if plan.estado != 'BORRADOR':
        messages.error(request, 'El plan no permite eliminar entregas.')
        return redirect('detalleplancarga', id=plan.id_plan_carga)

    entrega.delete()
    messages.success(request, 'Producto retirado de la parada.')
    return redirect('gestionarparadasplancarga', id=plan.id_plan_carga)


def marcarplancargalisto(request, id):
    acceso = _validar_acceso_admin_cargas(request)

    if acceso:
        return acceso

    if request.method != 'POST':
        return redirect('detalleplancarga', id=id)

    try:
        plan = PlanCarga.objects.select_related(
            'vehiculo',
            'vehiculo__usuario'
        ).prefetch_related(
            'detalles',
            'detalles__producto',
            'detalles__entregas',
            'paradas',
            'paradas__entregas'
        ).get(id_plan_carga=id)
    except PlanCarga.DoesNotExist:
        messages.error(request, 'El plan de carga no existe.')
        return redirect('listadoplanescarga')

    bloqueo = _bloquear_modificacion_plan_historico(request, plan)
    if bloqueo:
        return bloqueo

    if plan.estado != 'BORRADOR':
        messages.error(request, 'Solo un borrador puede marcarse como listo.')
        return redirect('detalleplancarga', id=plan.id_plan_carga)

    errores = _validar_plan_para_salida(plan)

    if errores:
        messages.error(request, ' '.join(errores))
        return redirect('detalleplancarga', id=plan.id_plan_carga)

    plan.estado = 'LISTO'
    _reiniciar_revision_y_confirmacion(plan)
    plan.save()

    messages.success(
        request,
        'Plan listo. El conductor ya puede revisar la carga.'
    )
    return redirect('detalleplancarga', id=plan.id_plan_carga)


def volverplancargaborrador(request, id):
    acceso = _validar_acceso_admin_cargas(request)

    if acceso:
        return acceso

    if request.method != 'POST':
        return redirect('detalleplancarga', id=id)

    try:
        plan = PlanCarga.objects.get(id_plan_carga=id)
    except PlanCarga.DoesNotExist:
        messages.error(request, 'El plan de carga no existe.')
        return redirect('listadoplanescarga')

    bloqueo = _bloquear_modificacion_plan_historico(request, plan)
    if bloqueo:
        return bloqueo

    if plan.estado not in ['LISTO', 'CONFIRMADO']:
        messages.error(request, 'El plan no puede volver a borrador.')
        return redirect('detalleplancarga', id=plan.id_plan_carga)

    plan.estado = 'BORRADOR'
    _reiniciar_revision_y_confirmacion(plan)
    plan.save()

    messages.success(
        request,
        'Plan abierto como borrador. El conductor deberá revisarlo otra vez.'
    )
    return redirect('detalleplancarga', id=plan.id_plan_carga)


def confirmarplancargaadmin(request, id):
    acceso = _validar_acceso_admin_cargas(request)

    if acceso:
        return acceso

    if request.method != 'POST':
        return redirect('detalleplancarga', id=id)

    try:
        plan = PlanCarga.objects.select_related(
            'vehiculo',
            'vehiculo__usuario'
        ).prefetch_related(
            'detalles',
            'detalles__entregas',
            'paradas',
            'paradas__entregas'
        ).get(id_plan_carga=id)
    except PlanCarga.DoesNotExist:
        messages.error(request, 'El plan de carga no existe.')
        return redirect('listadoplanescarga')

    bloqueo = _bloquear_modificacion_plan_historico(request, plan)
    if bloqueo:
        return bloqueo

    if plan.estado != 'LISTO':
        messages.error(request, 'El plan debe estar listo antes de confirmarlo.')
        return redirect('detalleplancarga', id=plan.id_plan_carga)

    errores = _validar_plan_para_salida(
        plan,
        exigir_revision=True
    )

    if errores:
        messages.error(request, ' '.join(errores))
        return redirect('detalleplancarga', id=plan.id_plan_carga)

    try:
        administrador = Usuario.objects.get(
            id_usuario=request.session.get('usuario_id')
        )
    except Usuario.DoesNotExist:
        administrador = None

    plan.estado = 'CONFIRMADO'
    plan.confirmado_por = administrador
    plan.fecha_confirmacion = timezone.now()
    plan.save()

    messages.success(
        request,
        'Carga confirmada y bloqueada para el cálculo del viaje.'
    )
    return redirect('detalleplancarga', id=plan.id_plan_carga)


def reabrirplancargaconfirmada(request, id):
    acceso = _validar_acceso_admin_cargas(request)

    if acceso:
        return acceso

    if request.method != 'POST':
        return redirect('detalleplancarga', id=id)

    try:
        plan = PlanCarga.objects.get(id_plan_carga=id)
    except PlanCarga.DoesNotExist:
        messages.error(request, 'El plan de carga no existe.')
        return redirect('listadoplanescarga')

    bloqueo = _bloquear_modificacion_plan_historico(request, plan)
    if bloqueo:
        return bloqueo

    if plan.estado != 'CONFIRMADO':
        messages.error(request, 'Solo una carga confirmada puede reabrirse.')
        return redirect('detalleplancarga', id=plan.id_plan_carga)

    plan.estado = 'LISTO'
    _reiniciar_revision_y_confirmacion(plan)
    plan.save()

    messages.success(
        request,
        'La carga volvió a estado listo y debe ser revisada nuevamente.'
    )
    return redirect('detalleplancarga', id=plan.id_plan_carga)


def cancelarplancarga(request, id):
    acceso = _validar_acceso_admin_cargas(request)

    if acceso:
        return acceso

    if request.method != 'POST':
        return redirect('listadoplanescarga')

    try:
        plan = PlanCarga.objects.get(id_plan_carga=id)
    except PlanCarga.DoesNotExist:
        messages.error(request, 'El plan de carga no existe.')
        return redirect('listadoplanescarga')

    bloqueo = _bloquear_modificacion_plan_historico(request, plan)
    if bloqueo:
        return bloqueo

    if plan.estado in ['EN_RUTA', 'COMPLETADO']:
        messages.error(
            request,
            'No se puede cancelar una carga en ruta o completada.'
        )
        return redirect('detalleplancarga', id=plan.id_plan_carga)

    plan.estado = 'CANCELADO'
    _reiniciar_revision_y_confirmacion(plan)
    plan.save()

    messages.success(request, 'Plan de carga cancelado correctamente.')
    return redirect('detalleplancarga', id=plan.id_plan_carga)


def reactivarplancarga(request, id):
    acceso = _validar_acceso_admin_cargas(request)

    if acceso:
        return acceso

    if request.method != 'POST':
        return redirect('listadoplanescarga')

    try:
        plan = PlanCarga.objects.get(id_plan_carga=id)
    except PlanCarga.DoesNotExist:
        messages.error(request, 'El plan de carga no existe.')
        return redirect('listadoplanescarga')

    bloqueo = _bloquear_modificacion_plan_historico(request, plan)
    if bloqueo:
        return bloqueo

    if plan.estado != 'CANCELADO':
        messages.error(request, 'El plan no está cancelado.')
        return redirect('detalleplancarga', id=plan.id_plan_carga)

    plan.estado = 'BORRADOR'
    _reiniciar_revision_y_confirmacion(plan)
    plan.save()

    messages.success(request, 'Plan reactivado como borrador.')
    return redirect('prepararplancarga', id=plan.id_plan_carga)


# =============================================================================
# CARGAS ASIGNADAS - USUARIO
# =============================================================================

def _usuario_sesion_cargas(request):
    usuario_id = request.session.get('usuario_id')

    if not usuario_id:
        return None, redirect('/login')

    try:
        usuario = Usuario.objects.get(
            id_usuario=usuario_id,
            activo=True
        )
    except Usuario.DoesNotExist:
        request.session.flush()
        messages.error(
            request,
            'La sesión no es válida. Inicia sesión nuevamente.'
        )
        return None, redirect('/login')

    return usuario, None


def _plan_carga_del_usuario(request, id_plan):
    usuario, respuesta = _usuario_sesion_cargas(request)

    if respuesta:
        return None, None, respuesta

    try:
        plan = PlanCarga.objects.select_related(
            'vehiculo',
            'vehiculo__usuario'
        ).prefetch_related(
            'detalles',
            'detalles__producto',
            'ajustes_usuario',
            'ajustes_usuario__usuario'
        ).get(
            id_plan_carga=id_plan,
            vehiculo__usuario=usuario
        )
    except PlanCarga.DoesNotExist:
        messages.error(
            request,
            'La carga no existe o no está asignada a tu vehículo.'
        )
        return usuario, None, redirect('listadocarga')

    return usuario, plan, None


def _plan_permite_cambios_usuario(plan):
    return plan.estado == 'LISTO'


def _marcar_plan_ajustado_usuario(plan):
    plan.ajustado_por_usuario = True
    plan.fecha_ultimo_ajuste_usuario = timezone.now()
    plan.revisado_por_usuario = False
    plan.fecha_revision_usuario = None
    plan.save(
        update_fields=[
            'ajustado_por_usuario',
            'fecha_ultimo_ajuste_usuario',
            'revisado_por_usuario',
            'fecha_revision_usuario',
            'fecha_actualizacion',
        ]
    )


def _nombre_producto_ajuste(producto):
    nombre = producto.nombre_producto

    if producto.marca_producto:
        nombre += f' - {producto.marca_producto}'

    nombre += f' ({producto.get_presentacion_producto_display()})'
    return nombre


def _sincronizar_detalle_desde_entregas(detalle):
    cantidad_actual = sum(
        entrega.cantidad_actual
        for entrega in detalle.entregas.all()
    )

    detalle.cantidad_actual = cantidad_actual
    detalle.save()


def listadocarga(request):
    usuario, respuesta = _usuario_sesion_cargas(request)

    if respuesta:
        return respuesta

    vehiculo = Vehiculo.objects.filter(usuario=usuario).first()

    if not vehiculo:
        messages.error(request, 'No tienes un vehículo asignado.')
        return redirect('listadovehiculo')

    planes = PlanCarga.objects.filter(
        vehiculo=vehiculo
    ).exclude(
        estado='BORRADOR'
    ).select_related(
        'vehiculo'
    ).prefetch_related(
        'detalles'
    ).order_by('-fecha_planificada')

    hoy = timezone.localdate()
    fecha_filtro = parse_date(request.GET.get('fecha', '').strip())

    total_planes = planes.count()
    total_listos = planes.filter(estado='LISTO').count()
    total_revisados = planes.filter(
        revisado_por_usuario=True
    ).count()

    planes_hoy = planes.filter(
        fecha_planificada=hoy
    ).order_by('-id_plan_carga')

    planes_proximos = planes.filter(
        fecha_planificada__gt=hoy
    ).order_by('fecha_planificada', 'id_plan_carga')

    planes_anteriores = planes.filter(
        fecha_planificada__lt=hoy
    ).order_by('-fecha_planificada', '-id_plan_carga')

    planes_fecha = planes.none()
    if fecha_filtro:
        planes_fecha = planes.filter(
            fecha_planificada=fecha_filtro
        ).order_by('-id_plan_carga')

    return render(
        request,
        'usuario/cargas/listadocarga.html',
        {
            'usuario': usuario,
            'vehiculo': vehiculo,
            'planes': planes,
            'planes_hoy': planes_hoy,
            'planes_proximos': planes_proximos,
            'planes_anteriores': planes_anteriores,
            'planes_fecha': planes_fecha,
            'fecha_filtro': fecha_filtro,
            'total_planes': total_planes,
            'total_listos': total_listos,
            'total_revisados': total_revisados,
            'hoy': hoy,
        }
    )


def detallecargausuario(request, id):
    usuario, plan, respuesta = _plan_carga_del_usuario(request, id)

    if respuesta:
        return respuesta

    productos_usados = plan.detalles.values_list(
        'producto_id',
        flat=True
    )

    productos_disponibles = ProductoCarga.objects.filter(
        activo=True
    ).exclude(
        id_producto_carga__in=productos_usados
    ).order_by(
        'nombre_producto',
        'marca_producto'
    )

    detalles = list(
        plan.detalles.select_related(
            'producto'
        ).all()
    )

    # El usuario puede reducir o aumentar la cantidad. El límite real no es
    # la cantidad original, sino la capacidad disponible del vehículo.
    for detalle in detalles:
        peso_sin_detalle = max(
            plan.peso_total_kg - detalle.peso_actual_kg,
            Decimal('0.00')
        )
        capacidad_para_detalle = max(
            plan.capacidad_kg - peso_sin_detalle,
            Decimal('0.00')
        )

        if detalle.peso_unitario_kg > 0:
            maximo_por_capacidad = int(
                capacidad_para_detalle // detalle.peso_unitario_kg
            )
        else:
            maximo_por_capacidad = 0

        detalle.max_cantidad_permitida = max(
            maximo_por_capacidad,
            detalle.cantidad_actual
        )

    ajustes = plan.ajustes_usuario.select_related(
        'usuario'
    ).all()

    return render(
        request,
        'usuario/cargas/detalle_carga.html',
        {
            'usuario': usuario,
            'plan': plan,
            'detalles': detalles,
            'productos_disponibles': productos_disponibles,
            'ajustes': ajustes,
            'peso_programado': plan.peso_programado_kg,
            'peso_total': plan.peso_total_kg,
            'peso_descartado': plan.peso_descartado_kg,
            'peso_agregado_usuario': plan.peso_agregado_usuario_kg,
            'capacidad': plan.capacidad_kg,
            'disponible': plan.disponible_kg,
            'porcentaje': plan.porcentaje_carga,
            'permite_cambios': _plan_permite_cambios_usuario(plan),
        }
    )


def agregarproductocargausuario(request, id):
    usuario, plan, respuesta = _plan_carga_del_usuario(request, id)

    if respuesta:
        return respuesta

    if request.method != 'POST':
        return redirect('detallecargausuario', id=plan.id_plan_carga)

    if not _plan_permite_cambios_usuario(plan):
        messages.error(request, 'Esta carga ya no permite modificaciones.')
        return redirect('detallecargausuario', id=plan.id_plan_carga)

    producto_id = request.POST.get('producto', '').strip()
    motivo = request.POST.get('motivo', '').strip()

    try:
        cantidad = int(request.POST.get('cantidad', '0'))
    except (TypeError, ValueError):
        cantidad = 0

    if cantidad <= 0 or cantidad > 9999:
        messages.error(request, 'La cantidad debe estar entre 1 y 9999.')
        return redirect('detallecargausuario', id=plan.id_plan_carga)

    if len(motivo) < 5 or len(motivo) > 250:
        messages.error(
            request,
            'Escribe una nota de entre 5 y 250 caracteres.'
        )
        return redirect('detallecargausuario', id=plan.id_plan_carga)

    try:
        producto = ProductoCarga.objects.get(
            id_producto_carga=producto_id,
            activo=True
        )
    except ProductoCarga.DoesNotExist:
        messages.error(request, 'El producto seleccionado no está disponible.')
        return redirect('detallecargausuario', id=plan.id_plan_carga)

    if plan.detalles.filter(producto=producto).exists():
        messages.error(
            request,
            'El producto ya forma parte de la carga. Ajusta su cantidad actual.'
        )
        return redirect('detallecargausuario', id=plan.id_plan_carga)

    peso_nuevo = Decimal(cantidad) * producto.peso_unitario_kg
    peso_resultante = plan.peso_total_kg + peso_nuevo

    if peso_resultante > plan.capacidad_kg:
        exceso = peso_resultante - plan.capacidad_kg
        messages.error(
            request,
            f'La carga alcanzaría {peso_resultante:.2f} kg y '
            f'superaría la capacidad por {exceso:.2f} kg.'
        )
        return redirect('detallecargausuario', id=plan.id_plan_carga)

    with transaction.atomic():
        detalle = DetallePlanCarga.objects.create(
            plan=plan,
            producto=producto,
            cantidad=cantidad,
            cantidad_actual=cantidad,
            origen='USUARIO',
            agregado_por=usuario,
            peso_unitario_kg=producto.peso_unitario_kg,
            peso_subtotal_kg=peso_nuevo,
            peso_actual_kg=peso_nuevo
        )

        AjusteCargaUsuario.objects.create(
            plan=plan,
            detalle=detalle,
            usuario=usuario,
            tipo_ajuste='AGREGAR',
            producto_nombre=_nombre_producto_ajuste(producto),
            cantidad_anterior=0,
            cantidad_nueva=cantidad,
            peso_anterior_kg=Decimal('0.00'),
            peso_nuevo_kg=peso_nuevo,
            motivo=motivo
        )

        _marcar_plan_ajustado_usuario(plan)

    messages.success(request, 'Producto agregado correctamente a la carga.')
    return redirect('detallecargausuario', id=plan.id_plan_carga)


def ajustarentregacargausuario(request, id):
    usuario, respuesta = _usuario_sesion_cargas(request)

    if respuesta:
        return respuesta

    try:
        entrega = EntregaPlanCarga.objects.select_related(
            'parada',
            'parada__plan',
            'parada__plan__vehiculo',
            'detalle',
            'detalle__producto'
        ).get(
            id_entrega_plan_carga=id,
            parada__plan__vehiculo__usuario=usuario
        )
    except EntregaPlanCarga.DoesNotExist:
        messages.error(request, 'La entrega no existe o no pertenece a tu carga.')
        return redirect('listadocarga')

    plan = entrega.parada.plan

    if request.method != 'POST':
        return redirect('detallecargausuario', id=plan.id_plan_carga)

    if not _plan_permite_cambios_usuario(plan):
        messages.error(request, 'Esta carga ya no permite modificaciones.')
        return redirect('detallecargausuario', id=plan.id_plan_carga)

    try:
        cantidad_nueva = int(
            request.POST.get('cantidad_nueva', '-1')
        )
    except (TypeError, ValueError):
        cantidad_nueva = -1

    motivo = request.POST.get('motivo', '').strip()

    if cantidad_nueva < 0 or cantidad_nueva > entrega.cantidad_asignada:
        messages.error(
            request,
            f'La cantidad debe estar entre 0 y {entrega.cantidad_asignada}.'
        )
        return redirect('detallecargausuario', id=plan.id_plan_carga)

    if cantidad_nueva == entrega.cantidad_actual:
        messages.error(request, 'La cantidad nueva debe ser diferente.')
        return redirect('detallecargausuario', id=plan.id_plan_carga)

    if len(motivo) < 5 or len(motivo) > 250:
        messages.error(
            request,
            'Escribe un motivo de entre 5 y 250 caracteres.'
        )
        return redirect('detallecargausuario', id=plan.id_plan_carga)

    cantidad_anterior = entrega.cantidad_actual
    peso_anterior = entrega.peso_actual_kg
    peso_nuevo = Decimal(cantidad_nueva) * entrega.peso_unitario_kg
    peso_resultante = plan.peso_total_kg - peso_anterior + peso_nuevo

    if peso_resultante > plan.capacidad_kg:
        messages.error(request, 'El ajuste supera la capacidad del vehículo.')
        return redirect('detallecargausuario', id=plan.id_plan_carga)

    if cantidad_nueva == 0:
        tipo_ajuste = 'DESCARTAR'
    elif cantidad_nueva > cantidad_anterior:
        tipo_ajuste = 'RESTAURAR'
    else:
        tipo_ajuste = 'AJUSTAR'

    with transaction.atomic():
        entrega.cantidad_actual = cantidad_nueva
        entrega.save()
        _sincronizar_detalle_desde_entregas(entrega.detalle)

        AjusteCargaUsuario.objects.create(
            plan=plan,
            detalle=entrega.detalle,
            entrega=entrega,
            parada=entrega.parada,
            parada_nombre=entrega.parada.nombre_parada,
            usuario=usuario,
            tipo_ajuste=tipo_ajuste,
            producto_nombre=_nombre_producto_ajuste(
                entrega.detalle.producto
            ),
            cantidad_anterior=cantidad_anterior,
            cantidad_nueva=cantidad_nueva,
            peso_anterior_kg=peso_anterior,
            peso_nuevo_kg=peso_nuevo,
            motivo=motivo
        )

        _marcar_plan_ajustado_usuario(plan)

    messages.success(request, 'Entrega actualizada correctamente.')
    return redirect('detallecargausuario', id=plan.id_plan_carga)


def restaurarentregacargausuario(request, id):
    usuario, respuesta = _usuario_sesion_cargas(request)

    if respuesta:
        return respuesta

    try:
        entrega = EntregaPlanCarga.objects.select_related(
            'parada',
            'parada__plan',
            'parada__plan__vehiculo',
            'detalle',
            'detalle__producto'
        ).get(
            id_entrega_plan_carga=id,
            parada__plan__vehiculo__usuario=usuario
        )
    except EntregaPlanCarga.DoesNotExist:
        messages.error(request, 'La entrega no existe.')
        return redirect('listadocarga')

    plan = entrega.parada.plan

    if request.method != 'POST':
        return redirect('detallecargausuario', id=plan.id_plan_carga)

    if not _plan_permite_cambios_usuario(plan):
        messages.error(request, 'Esta carga ya no permite modificaciones.')
        return redirect('detallecargausuario', id=plan.id_plan_carga)

    if entrega.cantidad_actual >= entrega.cantidad_asignada:
        messages.info(request, 'La entrega ya tiene su cantidad completa.')
        return redirect('detallecargausuario', id=plan.id_plan_carga)

    peso_anterior = entrega.peso_actual_kg
    peso_nuevo = entrega.peso_asignado_kg
    peso_resultante = plan.peso_total_kg - peso_anterior + peso_nuevo

    if peso_resultante > plan.capacidad_kg:
        messages.error(
            request,
            'No se puede restaurar porque superaría la capacidad.'
        )
        return redirect('detallecargausuario', id=plan.id_plan_carga)

    cantidad_anterior = entrega.cantidad_actual

    with transaction.atomic():
        entrega.cantidad_actual = entrega.cantidad_asignada
        entrega.save()
        _sincronizar_detalle_desde_entregas(entrega.detalle)

        AjusteCargaUsuario.objects.create(
            plan=plan,
            detalle=entrega.detalle,
            entrega=entrega,
            parada=entrega.parada,
            parada_nombre=entrega.parada.nombre_parada,
            usuario=usuario,
            tipo_ajuste='RESTAURAR',
            producto_nombre=_nombre_producto_ajuste(
                entrega.detalle.producto
            ),
            cantidad_anterior=cantidad_anterior,
            cantidad_nueva=entrega.cantidad_asignada,
            peso_anterior_kg=peso_anterior,
            peso_nuevo_kg=peso_nuevo,
            motivo='Producto restaurado por el conductor.'
        )

        _marcar_plan_ajustado_usuario(plan)

    messages.success(request, 'Entrega restaurada correctamente.')
    return redirect('detallecargausuario', id=plan.id_plan_carga)


def ajustardetallecargausuario(request, id):
    usuario, respuesta = _usuario_sesion_cargas(request)

    if respuesta:
        return respuesta

    try:
        detalle = DetallePlanCarga.objects.select_related(
            'plan',
            'plan__vehiculo',
            'producto'
        ).prefetch_related('entregas').get(
            id_detalle_plan_carga=id,
            plan__vehiculo__usuario=usuario
        )
    except DetallePlanCarga.DoesNotExist:
        messages.error(request, 'El producto no pertenece a tu carga.')
        return redirect('listadocarga')

    plan = detalle.plan

    if request.method != 'POST' or not _plan_permite_cambios_usuario(plan):
        return redirect('detallecargausuario', id=plan.id_plan_carga)

    try:
        cantidad_nueva = int(request.POST.get('cantidad_nueva', '-1'))
    except (TypeError, ValueError):
        cantidad_nueva = -1

    motivo = request.POST.get('motivo', '').strip()

    if cantidad_nueva < 0 or cantidad_nueva > 9999:
        messages.error(request, 'La cantidad debe estar entre 0 y 9999.')
        return redirect('detallecargausuario', id=plan.id_plan_carga)

    if cantidad_nueva == detalle.cantidad_actual:
        messages.error(request, 'La cantidad nueva debe ser diferente a la actual.')
        return redirect('detallecargausuario', id=plan.id_plan_carga)

    if len(motivo) < 5 or len(motivo) > 250:
        messages.error(request, 'Escribe una nota de 5 a 250 caracteres.')
        return redirect('detallecargausuario', id=plan.id_plan_carga)

    cantidad_anterior = detalle.cantidad_actual
    peso_anterior = detalle.peso_actual_kg
    peso_nuevo = Decimal(cantidad_nueva) * detalle.peso_unitario_kg
    peso_resultante = (
        plan.peso_total_kg -
        detalle.peso_actual_kg +
        peso_nuevo
    )

    if peso_resultante > plan.capacidad_kg:
        exceso = peso_resultante - plan.capacidad_kg
        messages.error(
            request,
            f'La carga alcanzaría {peso_resultante:.2f} kg y '
            f'superaría la capacidad del vehículo por {exceso:.2f} kg.'
        )
        return redirect('detallecargausuario', id=plan.id_plan_carga)

    if cantidad_nueva == 0:
        tipo_ajuste = 'DESCARTAR'
    elif cantidad_nueva == detalle.cantidad:
        tipo_ajuste = 'RESTAURAR'
    else:
        tipo_ajuste = 'AJUSTAR'

    with transaction.atomic():
        # Las paradas se definirán posteriormente durante la generación
        # de rutas. Se eliminan asignaciones antiguas para mantener una
        # única cantidad efectiva en la carga actual.
        detalle.entregas.all().delete()
        detalle.cantidad_actual = cantidad_nueva
        detalle.save()

        AjusteCargaUsuario.objects.create(
            plan=plan,
            detalle=detalle,
            usuario=usuario,
            tipo_ajuste=tipo_ajuste,
            producto_nombre=_nombre_producto_ajuste(detalle.producto),
            cantidad_anterior=cantidad_anterior,
            cantidad_nueva=cantidad_nueva,
            peso_anterior_kg=peso_anterior,
            peso_nuevo_kg=peso_nuevo,
            motivo=motivo
        )

        _marcar_plan_ajustado_usuario(plan)

    messages.success(request, 'Cantidad actualizada correctamente.')
    return redirect('detallecargausuario', id=plan.id_plan_carga)


def restaurardetallecargausuario(request, id):
    usuario, respuesta = _usuario_sesion_cargas(request)

    if respuesta:
        return respuesta

    try:
        detalle = DetallePlanCarga.objects.select_related(
            'plan',
            'plan__vehiculo',
            'producto'
        ).prefetch_related('entregas').get(
            id_detalle_plan_carga=id,
            plan__vehiculo__usuario=usuario
        )
    except DetallePlanCarga.DoesNotExist:
        messages.error(request, 'El producto no pertenece a tu carga.')
        return redirect('listadocarga')

    plan = detalle.plan

    if request.method != 'POST' or not _plan_permite_cambios_usuario(plan):
        return redirect('detallecargausuario', id=plan.id_plan_carga)

    if detalle.cantidad_actual == detalle.cantidad:
        messages.info(request, 'El producto ya tiene la cantidad originalmente asignada.')
        return redirect('detallecargausuario', id=plan.id_plan_carga)

    peso_resultante = (
        plan.peso_total_kg -
        detalle.peso_actual_kg +
        detalle.peso_subtotal_kg
    )

    if peso_resultante > plan.capacidad_kg:
        messages.error(request, 'La restauración supera la capacidad.')
        return redirect('detallecargausuario', id=plan.id_plan_carga)

    cantidad_anterior = detalle.cantidad_actual
    peso_anterior = detalle.peso_actual_kg

    with transaction.atomic():
        detalle.entregas.all().delete()
        detalle.cantidad_actual = detalle.cantidad
        detalle.save()

        AjusteCargaUsuario.objects.create(
            plan=plan,
            detalle=detalle,
            usuario=usuario,
            tipo_ajuste='RESTAURAR',
            producto_nombre=_nombre_producto_ajuste(detalle.producto),
            cantidad_anterior=cantidad_anterior,
            cantidad_nueva=detalle.cantidad,
            peso_anterior_kg=peso_anterior,
            peso_nuevo_kg=detalle.peso_subtotal_kg,
            motivo='Producto restaurado por el conductor.'
        )

        _marcar_plan_ajustado_usuario(plan)

    messages.success(request, 'Producto restaurado correctamente.')
    return redirect('detallecargausuario', id=plan.id_plan_carga)


def confirmarcargausuario(request, id):
    usuario, plan, respuesta = _plan_carga_del_usuario(request, id)

    if respuesta:
        return respuesta

    if request.method != 'POST':
        return redirect('detallecargausuario', id=plan.id_plan_carga)

    if plan.estado != 'LISTO':
        messages.error(
            request,
            'Solo una carga en estado listo puede revisarse.'
        )
        return redirect('detallecargausuario', id=plan.id_plan_carga)

    errores = _validar_plan_para_salida(plan)

    if errores:
        messages.error(request, ' '.join(errores))
        return redirect('detallecargausuario', id=plan.id_plan_carga)

    plan.revisado_por_usuario = True
    plan.fecha_revision_usuario = timezone.now()
    plan.save(
        update_fields=[
            'revisado_por_usuario',
            'fecha_revision_usuario',
            'fecha_actualizacion',
        ]
    )

    messages.success(request, 'Carga revisada correctamente.')
    return redirect('detallecargausuario', id=plan.id_plan_carga)


# =============================================================================
# MAPA / LUGARES GUARDADOS
# =============================================================================

def buscarlugares(request):
    query = request.GET.get("q", "")  # captura lo que el usuario escribe en el buscador

    resultados = []

    # HISTORIAL DE LUGARES GUARDADOS DEL USUARIO LOGEADO
    usuario_id = request.session.get("usuario_id")

    # Si no hay usuario logueado
    if usuario_id is None:
        messages.error(request, "Debes iniciar sesión")
        return redirect("login")

    historial = Lugarguardado.objects.filter(usuario=usuario_id).order_by('-fecha_guardado')

    if query:
        url = "https://nominatim.openstreetmap.org/search"

        params = {
            "q": query,
            "format": "json",
            "addressdetails": 1,
            "limit": 15,
            "viewbox": "-78.7000,-0.8000,-78.5000,-1.0500",
            "bounded": 1,
        }

        r = requests.get(
            url,
            params=params,
            headers={
                "User-Agent": getattr(settings, "NOMINATIM_USER_AGENT", "DistricC-Tesis/1.0"),
                "Referer": getattr(settings, "PUBLIC_BASE_URL", "") or "http://127.0.0.1:8000"
            }
        )

        resultados = r.json()

    return render(request, "usuario/mapas/buscarlugares.html", {
        "query": query,
        "resultados": resultados,
        "historial": historial,

        # >>> GOOGLE MAPS
        "google_maps_api_key": settings.GOOGLE_MAPS_API_KEY,
        # <<< GOOGLE MAPS
    })


def ver_lugar(request, lat, lon):
    nombre = request.GET.get("nombre", "Ubicación seleccionada")

    return render(request, "usuario/mapas/ver_lugar.html", {
        "lat": lat,
        "lon": lon,
        "nombre": nombre,

        # >>> GOOGLE MAPS
        "google_maps_api_key": settings.GOOGLE_MAPS_API_KEY,
        # <<< GOOGLE MAPS
    })


def guardar_lugar(request, lat, lon, nombre):
    usuario_id = request.session.get("usuario_id")
    usuario = Usuario.objects.get(id_usuario=usuario_id)

    Lugarguardado.objects.create(
        usuario=usuario,
        nombre_Lugarguardado=nombre,
        latitud_Lugarguardado=float(lat),
        longitud_Lugarguardado=float(lon)
    )

    messages.success(request, "Lugar guardado con exito")

    return redirect("ver_lugar", lat=lat, lon=lon)


def eliminar_lugar(request, id):
    usuario_id = request.session.get("usuario_id")

    lugar = Lugarguardado.objects.filter(
        id_Lugarguardado=id,
        usuario_id=usuario_id
    ).first()

    if not lugar:
        messages.error(
            request,
            "El lugar que intentas eliminar ya no existe o no te pertenece."
        )
        return redirect("buscarlugares")

    lugar.delete()

    messages.success(request, "Lugar eliminado correctamente.")

    return redirect("buscarlugares")

# =============================================================================
# RUTAS / DIJKSTRA / CONSUMO
# =============================================================================

# ------------------ CONSTANTES DE PESO ------------------

ALFA_PESO = 0.5      # sensibilidad de consumo al peso


def calcular_factor_peso(vehiculo):
    """
    Devuelve (factor_peso, peso_total_kg, peso_base_kg).
    """
    if vehiculo.peso_auto is None:
        return 1.0, None, None

    try:
        peso_base_ton = float(vehiculo.peso_auto)
    except (TypeError, ValueError):
        return 1.0, None, None

    if peso_base_ton <= 0:
        return 1.0, None, None

    total_carga_kg = vehiculo.cargas.aggregate(
        total=Sum('peso_adicional')
    )['total'] or 0

    peso_base_kg = peso_base_ton * 1000.0
    peso_extra_kg = float(total_carga_kg)
    peso_total_kg = peso_base_kg + peso_extra_kg

    diferencia_rel = peso_extra_kg / peso_base_kg
    factor_peso = 1.0 + ALFA_PESO * diferencia_rel

    if factor_peso < 0.1:
        factor_peso = 0.1

    return factor_peso, peso_total_kg, peso_base_kg

def construir_coords_ruta_visual(ruta_ids):
    """
    Convierte una ruta de IDs de nodos en coordenadas para Google Maps.

    Antes se dibujaba nodo -> nodo en línea recta.
    Ahora se usa la geometría real de cada TramoVial cuando existe.
    """
    if not ruta_ids:
        return []

    ruta_ids = [int(x) for x in ruta_ids]

    ids_nodos = set(ruta_ids)

    nodos_dict = NodoMapa.objects.in_bulk(ids_nodos, field_name="id_nodo")

    tramos = TramoVial.objects.filter(
        origen_id__in=ids_nodos,
        destino_id__in=ids_nodos
    )

    tramos_dict = {
        (int(t.origen_id), int(t.destino_id)): t
        for t in tramos
    }

    coords = []

    for i in range(len(ruta_ids) - 1):
        origen_id = int(ruta_ids[i])
        destino_id = int(ruta_ids[i + 1])

        tramo = tramos_dict.get((origen_id, destino_id))

        if tramo and tramo.geometria:
            geometria = tramo.geometria

            for punto in geometria:
                try:
                    lat = float(punto[0])
                    lon = float(punto[1])
                    coord = [lat, lon]

                    if not coords or coords[-1] != coord:
                        coords.append(coord)
                except Exception:
                    pass

        else:
            nodo_origen = nodos_dict.get(origen_id)
            nodo_destino = nodos_dict.get(destino_id)

            if nodo_origen:
                coord_origen = [float(nodo_origen.latitud), float(nodo_origen.longitud)]
                if not coords or coords[-1] != coord_origen:
                    coords.append(coord_origen)

            if nodo_destino:
                coord_destino = [float(nodo_destino.latitud), float(nodo_destino.longitud)]
                if not coords or coords[-1] != coord_destino:
                    coords.append(coord_destino)

    return coords


# ------------------ VISTA RUTAS (N rutas + Dijkstra) ------------------

MAX_RUTAS = 6   # cuántas rutas alternativas como máximo quieres mostrar

def rutas(request):
    if not request.session.get("usuario_id"):
        return redirect('/login')

    usuario_id = request.session.get("usuario_id")

    # 1) Vehículo del usuario
    vehiculo = Vehiculo.objects.filter(usuario_id=usuario_id).first()
    if not vehiculo:
        messages.error(request, "Debes registrar un vehículo antes de calcular la ruta.")
        return redirect('/inicio')

    # 2) ORIGEN ACTUAL
    # Primero usamos lat/lon enviados desde el navegador.
    # Si no llegan, usamos la última ubicación guardada SOLO si no es vieja.
    lat_get = request.GET.get("lat")
    lon_get = request.GET.get("lon")

    origen_obj = None
    lat_origen = None
    lon_origen = None

    if lat_get and lon_get:
        try:
            lat_origen = float(lat_get)
            lon_origen = float(lon_get)

            # Guardamos esta ubicación nueva para que recorrido() use la misma.
            origen_obj = UbicacionVehiculo.objects.create(
                vehiculo=vehiculo,
                latitud=lat_origen,
                longitud=lon_origen
            )

        except ValueError:
            lat_origen = None
            lon_origen = None
            origen_obj = None

    if lat_origen is None or lon_origen is None:
        origen_obj = UbicacionVehiculo.objects.filter(
            vehiculo=vehiculo
        ).order_by('-fecha_hora').first()

        if not origen_obj:
            messages.error(request, "No se encontró la ubicación actual del vehículo.")
            return redirect('/inicio')

        try:
            tiempo_ubicacion = timezone.now() - origen_obj.fecha_hora

            if tiempo_ubicacion > timedelta(minutes=2):
                messages.error(
                    request,
                    "La ubicación guardada es antigua. Vuelve a calcular la ruta usando tu ubicación actual."
                )
                return redirect('/inicio')
        except Exception:
            pass

        lat_origen = origen_obj.latitud
        lon_origen = origen_obj.longitud

    # Guardamos en sesión la ubicación usada para que recorrido use la misma.
    request.session["origen_actual_lat"] = float(lat_origen)
    request.session["origen_actual_lon"] = float(lon_origen)

    # 3) DESTINO: último lugar guardado
    destino_obj = Lugarguardado.objects.filter(usuario_id=usuario_id).last()
    if not destino_obj:
        messages.error(request, "Debes guardar un lugar primero.")
        return redirect('/buscarlugares')

    lat_dest = destino_obj.latitud_Lugarguardado
    lon_dest = destino_obj.longitud_Lugarguardado

    # 4) Enganche inteligente a la red vial
    grafo = construir_grafo()

    mejor_enganche = seleccionar_mejor_enganche_ruta(
        lat_origen=lat_origen,
        lon_origen=lon_origen,
        lat_destino=lat_dest,
        lon_destino=lon_dest,
        grafo=grafo,
        k=20
    )

    if not mejor_enganche:
        messages.error(
            request,
            "No se pudo calcular una ruta óptima en la red vial."
        )
        return redirect('/inicio')

    nodo_origen = mejor_enganche["nodo_origen"]
    nodo_destino = mejor_enganche["nodo_destino"]

    # 5) Obtenemos hasta MAX_RUTAS rutas distintas
    lista_rutas = k_mejores_rutas(
        grafo,
        nodo_origen.id_nodo,
        nodo_destino.id_nodo,
        k=MAX_RUTAS
    )

    if not lista_rutas:
        messages.error(request, "No se pudo calcular ninguna ruta.")
        return redirect('/inicio')

    # ---------- ELEGIR POSICIÓN VISUAL PARA LA RUTA ÓPTIMA ----------
    pos_optima = 0
    n_rutas = len(lista_rutas)

    if n_rutas > 1:
        pos_optima = random.randint(0, n_rutas - 1)
        lista_rutas[0], lista_rutas[pos_optima] = lista_rutas[pos_optima], lista_rutas[0]

    # Guardamos el orden exacto mostrado en pantalla.
    # Así recorrido() abrirá la misma ruta seleccionada, no otra recalculada.
    request.session["rutas_calculadas_ids"] = [
        ruta_ids for ruta_ids, _ in lista_rutas
    ]

    request.session["ruta_optima_visual"] = pos_optima

    # 6) Rendimiento y precios para calcular combustible
    rend_obj = RendimientoVehiculoTipo.objects.filter(
        tipo=vehiculo.tipovehiculo_vehiculo
    ).first()

    if not rend_obj:
        messages.error(
            request,
            "No se ha configurado el rendimiento para este tipo de vehículo."
        )
        return redirect('/inicio')

    rendimiento_km_litro = rend_obj.km_l_promedio

    precio_obj = PrecioCombustible.objects.filter(
        tipo=vehiculo.tipocombustible_vehiculo
    ).order_by('-id_precio').first()

    precio_litro = precio_obj.precio_por_litro if precio_obj else None

    # Ajuste por peso
    factor_peso, peso_total_kg, peso_base_kg = calcular_factor_peso(vehiculo)

    # 7) Guardamos el viaje origen-destino
    viaje = Viaje.objects.create(
        usuario_id=usuario_id,
        vehiculo=vehiculo,
        origen=origen_obj,
        destino=destino_obj,
    )
    request.session['viaje_id'] = viaje.id_viaje

    # Factores externos Google/API para IA
    factores_google = {
        "trafico": {
            "disponible": False,
            "fuente": "Google Routes API",
            "desde_cache": False,
            "factor_trafico": 1.0,
            "descripcion_trafico": "no disponible",
            "duracion_trafico_min": None,
            "duracion_sin_trafico_min": None,
            "consultado_en": timezone.localtime().strftime("%Y-%m-%d %H:%M"),
            "mensaje": "La consulta de tráfico no se ejecutó.",
        },
        "clima": {
            "disponible": False,
            "fuente": "Google Weather API",
            "desde_cache": False,
            "factor_clima": 1.0,
            "descripcion_clima": "no disponible",
            "temperatura": None,
            "humedad": None,
            "nubosidad": None,
            "consultado_en": timezone.localtime().strftime("%Y-%m-%d %H:%M"),
            "mensaje": "La consulta de clima no se ejecutó.",
        }
    }

    try:
        if obtener_factores_google:
            factores_google = obtener_factores_google(
                lat_origen=lat_origen,
                lon_origen=lon_origen,
                lat_destino=lat_dest,
                lon_destino=lon_dest
            )
    except Exception as e:
        factores_google["trafico"]["mensaje"] = f"No se pudo consultar tráfico: {str(e)}"
        factores_google["clima"]["mensaje"] = f"No se pudo consultar clima: {str(e)}"

    # Google Routes API como respaldo visual/cálculo si Dijkstra sale exagerado.
    ruta_google_respaldo = obtener_ruta_google_respaldo(
        lat_origen=lat_origen,
        lon_origen=lon_origen,
        lat_destino=lat_dest,
        lon_destino=lon_dest
    )

    # Guardamos los factores en sesión por si luego los usamos en recorrido/informe
    request.session["factores_google_actuales"] = factores_google

    # 8) Armamos las tarjetas y las rutas para el mapa
    detalles_rutas = []
    rutas_js = []
    google_respaldo_por_indice = {}

    todos_ids = set()
    for ruta_ids, _ in lista_rutas:
        todos_ids.update(ruta_ids)

    nodos_dict = NodoMapa.objects.in_bulk(todos_ids, field_name='id_nodo')

    for idx, (ruta_ids, costo_tiempo) in enumerate(lista_rutas):
        distancia_km, tiempo_min = calcular_metricas_ruta(ruta_ids)

        es_optima = (idx == pos_optima)
        slug = "optima" if es_optima else "alternativa"

        usar_google_respaldo = False
        motivo_respaldo_google = ""

        # Aplica respaldo en la ruta que se ve primero o en la ruta marcada como óptima.
        # Así no rompe tus alternativas ni gasta más consultas de API.
        if (idx == 0 or es_optima) and ruta_local_es_exagerada(
            distancia_km,
            tiempo_min,
            ruta_google_respaldo
        ):
            usar_google_respaldo = True
            motivo_respaldo_google = (
                "La ruta local calculada con Dijkstra sobre OSMnx fue comparada con Google Routes API. "
                "Como la red local generó una vuelta más larga de lo esperado, se usa Google como respaldo vehicular."
            )
            distancia_km = ruta_google_respaldo["distancia_km"]
            tiempo_min = ruta_google_respaldo["tiempo_min"]

            google_respaldo_por_indice[str(idx + 1)] = {
                "coords": ruta_google_respaldo.get("coords", []),
                "distancia_km": distancia_km,
                "tiempo_min": tiempo_min,
                "motivo": motivo_respaldo_google,
                "fuente": "Google Routes API",
                "consultado_en": ruta_google_respaldo.get("consultado_en"),
            }

        consumo = costo_ruta = None
        consumo_ajustado = delta_litros = None
        prediccion_ia = None

        if rendimiento_km_litro and precio_litro is not None:
            consumo = distancia_km / rendimiento_km_litro
            costo_ruta = consumo * precio_litro

            if factor_peso != 1.0:
                consumo_ajustado = consumo * factor_peso
                delta_litros = consumo_ajustado - consumo

            try:
                if predecir_consumo_combustible:
                    prediccion_ia = predecir_consumo_combustible(
                        distancia_km=distancia_km,
                        tiempo_min=tiempo_min,
                        consumo_base=consumo,
                        consumo_ajustado_peso=consumo_ajustado,
                        factor_peso=factor_peso,
                        factores_google=factores_google
                    )

                if prediccion_ia and precio_litro is not None:
                    consumo_final_estimado = float(
                        prediccion_ia.get("consumo_predicho_litros", 0) or 0
                    )

                    precio_litro_float = float(precio_litro)
                    costo_total_estimado = consumo_final_estimado * precio_litro_float
                    costo_base_estimado = float(costo_ruta or 0)

                    prediccion_ia["costo_total_estimado"] = round(costo_total_estimado, 2)
                    prediccion_ia["incremento_costo_estimado"] = round(
                        costo_total_estimado - costo_base_estimado,
                        2
                    )
                    prediccion_ia["precio_litro"] = round(precio_litro_float, 2)

            except Exception:
                prediccion_ia = None

        detalles_rutas.append({
            "slug": slug,
            "es_optima": es_optima,
            "indice": idx + 1,
            "distancia_km": distancia_km,
            "tiempo_min": tiempo_min,
            "consumo_litros": consumo,
            "costo_ruta": costo_ruta,
            "consumo_litros_ajustado": consumo_ajustado,
            "delta_litros_peso": delta_litros,
            "factor_peso": factor_peso,
            "prediccion_ia": prediccion_ia,

            "usa_google_respaldo": usar_google_respaldo,
            "motivo_respaldo_google": motivo_respaldo_google,
            "fuente_ruta": "Google Routes API" if usar_google_respaldo else "Dijkstra + OSMnx",
            "google_consultado_en": ruta_google_respaldo.get("consultado_en") if usar_google_respaldo else None,
        })

        if usar_google_respaldo and ruta_google_respaldo.get("coords"):
            coords = ruta_google_respaldo["coords"]
        else:
            coords = construir_coords_ruta_visual(ruta_ids)

        if coords:
            punto_inicio_real = [float(lat_origen), float(lon_origen)]
            punto_destino_real = [float(lat_dest), float(lon_dest)]

            if coords[0] != punto_inicio_real:
                coords.insert(0, punto_inicio_real)

            if coords[-1] != punto_destino_real:
                coords.append(punto_destino_real)
        if coords:
            rutas_js.append(coords)

    request.session["google_respaldo_por_indice"] = google_respaldo_por_indice

    return render(request, "usuario/mapas/rutas.html", {
        "origen_real": json.dumps({"latitud": lat_origen, "longitud": lon_origen}),
        "destino_real": json.dumps({
            "latitud": lat_dest,
            "longitud": lon_dest,
            "nombre": destino_obj.nombre_Lugarguardado
        }),
        "rutas_js": json.dumps(rutas_js),
        "detalles_rutas": detalles_rutas,
        "google_maps_api_key": settings.GOOGLE_MAPS_API_KEY,
    })




# =============================================================================
# RECORRIDO
# =============================================================================

COLORES_RUTAS = [
    "#0077ff",  # ruta 1 (óptima)
    "#ff8800",  # ruta 2
    "#00ff88",  # ruta 3
    "#ff00ff",  # ruta 4
    "#000000",  # ruta 5
    "#00ffff",  # ruta 6
    "#ff4444",  # extra
]

def recorrido(request):
    if not request.session.get("usuario_id"):
        return redirect("/login")

    usuario_id = request.session.get("usuario_id")

    tipo_solicitado = request.GET.get("ruta", "optima")
    idx_param = request.GET.get("idx")

    vehiculo = Vehiculo.objects.filter(usuario_id=usuario_id).first()

    # ---------------- ORIGEN ACTUAL ----------------
    lat_get = request.GET.get("lat")
    lon_get = request.GET.get("lon")

    origen_obj = None
    lat_origen = None
    lon_origen = None

    if lat_get and lon_get:
        try:
            lat_origen = float(lat_get)
            lon_origen = float(lon_get)

            if vehiculo:
                origen_obj = UbicacionVehiculo.objects.create(
                    vehiculo=vehiculo,
                    latitud=lat_origen,
                    longitud=lon_origen
                )

        except ValueError:
            lat_origen = None
            lon_origen = None
            origen_obj = None

    # Si no llega por GET, usamos la misma ubicación que se usó en rutas()
    if lat_origen is None or lon_origen is None:
        lat_session = request.session.get("origen_actual_lat")
        lon_session = request.session.get("origen_actual_lon")

        if lat_session is not None and lon_session is not None:
            lat_origen = float(lat_session)
            lon_origen = float(lon_session)

            if vehiculo:
                origen_obj = UbicacionVehiculo.objects.create(
                    vehiculo=vehiculo,
                    latitud=lat_origen,
                    longitud=lon_origen
                )

    # Último respaldo: ubicación guardada, pero solo si no es vieja
    if lat_origen is None or lon_origen is None:
        if vehiculo:
            origen_obj = UbicacionVehiculo.objects.filter(
                vehiculo=vehiculo
            ).order_by("-fecha_hora").first()
        else:
            origen_obj = None

        if not origen_obj:
            messages.error(request, "No se encontró la ubicación actual del vehículo.")
            return redirect("/inicio")

        try:
            tiempo_ubicacion = timezone.now() - origen_obj.fecha_hora

            if tiempo_ubicacion > timedelta(minutes=2):
                messages.error(
                    request,
                    "La ubicación guardada es antigua. Vuelve a calcular la ruta desde tu ubicación actual."
                )
                return redirect("/inicio")
        except Exception:
            pass

        lat_origen = origen_obj.latitud
        lon_origen = origen_obj.longitud

    # ---------------- DESTINO ----------------
    destino_obj = Lugarguardado.objects.filter(usuario_id=usuario_id).last()
    if not destino_obj:
        messages.error(request, "Debes guardar un lugar primero.")
        return redirect("/buscarlugares")

    lat_dest = destino_obj.latitud_Lugarguardado
    lon_dest = destino_obj.longitud_Lugarguardado

    # ---------------- USAR LAS RUTAS YA MOSTRADAS ----------------
    rutas_guardadas = request.session.get("rutas_calculadas_ids")

    lista_rutas_ids = []

    if rutas_guardadas:
        # Si viene desde /rutas/, usamos exactamente las rutas que ya se mostraron.
        # Así recorrido() no recalcula otra ruta diferente.
        lista_rutas_ids = rutas_guardadas
    else:
        # Si alguien entra directo a /recorrido/, calculamos con el mismo
        # enganche inteligente que usa rutas().
        grafo = construir_grafo()

        mejor_enganche = seleccionar_mejor_enganche_ruta(
            lat_origen=lat_origen,
            lon_origen=lon_origen,
            lat_destino=lat_dest,
            lon_destino=lon_dest,
            grafo=grafo,
            k=20
        )

        if not mejor_enganche:
            messages.error(request, "No se pudo calcular una ruta en la red vial.")
            return redirect("/inicio")

        nodo_origen = mejor_enganche["nodo_origen"]
        nodo_destino = mejor_enganche["nodo_destino"]

        lista_rutas = k_mejores_rutas(
            grafo,
            nodo_origen.id_nodo,
            nodo_destino.id_nodo,
            k=MAX_RUTAS
        )

        if not lista_rutas:
            messages.error(request, "No se pudo calcular ninguna ruta.")
            return redirect("/inicio")

        lista_rutas_ids = [ruta_ids for ruta_ids, _ in lista_rutas]

    # -------- Elegir el índice de la ruta seleccionada --------
    indice = 0

    if idx_param:
        try:
            indice = int(idx_param) - 1
        except ValueError:
            indice = 0

    if not idx_param and tipo_solicitado == "alternativa" and len(lista_rutas_ids) > 1:
        indice = 1

    if indice < 0 or indice >= len(lista_rutas_ids):
        indice = 0

    ruta_seleccionada_ids = lista_rutas_ids[indice]

    color_ruta = COLORES_RUTAS[indice % len(COLORES_RUTAS)]
    tipo_bd = "OPTIMA" if tipo_solicitado == "optima" else "ALTERNATIVA"

    # ---------------- RESPALDO GOOGLE SI LA RUTA YA FUE VALIDADA ----------------
    google_respaldo_por_indice = request.session.get("google_respaldo_por_indice", {}) or {}
    respaldo_google = google_respaldo_por_indice.get(str(indice + 1))

    usa_google_respaldo = False

    if respaldo_google and respaldo_google.get("coords"):
        usa_google_respaldo = True
        coords_ruta = respaldo_google.get("coords")
        distancia_km = float(respaldo_google.get("distancia_km") or 0)
        tiempo_min = float(respaldo_google.get("tiempo_min") or 0)
    else:
        # ---------------- COORDENADAS PARA EL MAPA ----------------
        coords_ruta = construir_coords_ruta_visual(ruta_seleccionada_ids)

        # ---------------- MÉTRICAS ----------------
        distancia_km, tiempo_min = calcular_metricas_ruta(ruta_seleccionada_ids)

    rutas_js = [coords_ruta]

    consumo_litros = None
    costo_estimado = None

    if vehiculo:
        rend_obj = RendimientoVehiculoTipo.objects.filter(
            tipo=vehiculo.tipovehiculo_vehiculo
        ).first()

        if rend_obj:
            rendimiento = rend_obj.km_l_promedio

            precio_obj = PrecioCombustible.objects.filter(
                tipo=vehiculo.tipocombustible_vehiculo
            ).order_by('-id_precio').first()

            if precio_obj and rendimiento:
                consumo_litros = distancia_km / rendimiento
                costo_estimado = consumo_litros * precio_obj.precio_por_litro

    # ---------------- VIAJE Y RUTA OPCIÓN ----------------
    viaje = None
    viaje_id = request.session.get("viaje_id")

    if viaje_id:
        viaje = Viaje.objects.filter(id_viaje=viaje_id).first()

    if not viaje:
        viaje = Viaje.objects.create(
            usuario_id=usuario_id,
            vehiculo=vehiculo,
            origen=origen_obj,
            destino=destino_obj,
        )
        request.session["viaje_id"] = viaje.id_viaje

    RutaOpcion.objects.create(
        viaje=viaje,
        tipo=tipo_bd,
        tiempo_min=tiempo_min,
        distancia_km=distancia_km,
        consumo_litros=consumo_litros if consumo_litros is not None else 0,
        costo_estimado=costo_estimado if costo_estimado is not None else 0,
        combustible_tipo=vehiculo.tipocombustible_vehiculo if vehiculo else None,
    )

    return render(request, "usuario/mapas/recorrido.html", {
        "origen_real": json.dumps({"latitud": lat_origen, "longitud": lon_origen}),
        "destino_real": json.dumps({
            "latitud": lat_dest,
            "longitud": lon_dest,
            "nombre": destino_obj.nombre_Lugarguardado
        }),
        "rutas_js": json.dumps(rutas_js),
        "color_ruta": color_ruta,
        "vehiculo": vehiculo,
        "usa_google_respaldo": usa_google_respaldo,
        "google_maps_api_key": settings.GOOGLE_MAPS_API_KEY,
    })



# =============================================================================
# HISTORIAL DE RUTAS
# =============================================================================

def historial(request):
    if not request.session.get('usuario_id'):
        return redirect('/login')

    usuario_id = request.session.get('usuario_id')

    rutas = RutaOpcion.objects.filter(
        viaje__usuario_id=usuario_id
    ).select_related('viaje', 'viaje__vehiculo').order_by('-viaje__fecha_creacion')

    total_distancia = rutas.aggregate(total=Sum('distancia_km'))['total'] or 0
    total_tiempo = rutas.aggregate(total=Sum('tiempo_min'))['total'] or 0
    total_combustible = rutas.aggregate(total=Sum('consumo_litros'))['total'] or 0
    total_costo = rutas.aggregate(total=Sum('costo_estimado'))['total'] or 0

    return render(request, 'usuario/historial/historial.html', {
        'rutas': rutas,
        'chart_labels': json.dumps([
            'Distancia total (km)',
            'Tiempo total (min)',
            'Combustible total (L)',
            'Costo total ($)'
        ]),
        'chart_data': json.dumps([
            round(float(total_distancia), 2),
            round(float(total_tiempo), 2),
            round(float(total_combustible), 2),
            round(float(total_costo), 2),
        ])
    })





def eliminar_ruta_historial(request, id_ruta):
    if not request.session.get('usuario_id'):
        return redirect('/login')

    if request.method != 'POST':
        return redirect('historial')

    usuario_id = request.session.get('usuario_id')
    ruta = RutaOpcion.objects.filter(
        id_ruta_opcion=id_ruta,
        viaje__usuario_id=usuario_id
    ).first()

    if not ruta:
        messages.error(request, "La ruta que intentas eliminar no existe o no te pertenece.")
        return redirect('historial')

    ruta.delete()
    messages.success(request, "Ruta eliminada del historial.")
    return redirect('historial')



# =============================================================================
# API RUTA ÓPTIMA
# =============================================================================

@require_GET
def api_ruta_optima(request):
    """
    Endpoint: devuelve la ruta óptima (mínimo tiempo) entre dos nodos.

    Ejemplo de uso:
    /api/ruta-optima/?origen=8520975411&destino=8520975397
    """
    try:
        origen_id = int(request.GET.get("origen"))
        destino_id = int(request.GET.get("destino"))
    except (TypeError, ValueError):
        return JsonResponse(
            {"error": "Parámetros 'origen' y 'destino' son obligatorios y deben ser enteros."},
            status=400,
        )

    # Verificar que existan los nodos
    try:
        NodoMapa.objects.get(pk=origen_id)
        NodoMapa.objects.get(pk=destino_id)
    except NodoMapa.DoesNotExist:
        return JsonResponse(
            {"error": "Alguno de los nodos (origen o destino) no existe."},
            status=404,
        )

    grafo = construir_grafo()
    ruta_ids, costo = dijkstra(grafo, origen_id, destino_id)

    if not ruta_ids:
        return JsonResponse(
            {"error": "No se encontró ruta entre los nodos indicados."},
            status=404,
        )

    distancia_km, tiempo_min = calcular_metricas_ruta(ruta_ids)

    # Convertir ids de nodos a coordenadas [lon, lat] para el mapa
    nodos = NodoMapa.objects.in_bulk(ruta_ids, field_name="id_nodo")
    coordenadas = []
    for nid in ruta_ids:
        nodo = nodos.get(nid)
        if nodo:
            coordenadas.append([nodo.longitud, nodo.latitud])  # formato típico de mapas

    data = {
        "origen": origen_id,
        "destino": destino_id,
        "ruta_optima": {
            "nodos": ruta_ids,
            "coordenadas": coordenadas,
            "distancia_km": distancia_km,
            "tiempo_min": tiempo_min,
        },
    }

    return JsonResponse(data)



# =============================================================================
# ASIGNACIONES USUARIO
# =============================================================================


def _solo_usuario(request):
    return request.session.get('usuario_tiporol') == 'USUARIO'


def pedidosusuario(request):
    if not _solo_usuario(request):
        messages.error(request, "No tienes permisos.")
        return redirect('/login')

    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return redirect('/login')

    asignaciones = (
        AsignacionEvento.objects
        .filter(usuario_id=usuario_id)
        .select_related('evento', 'evento__creado_por', 'evento__creado_por__usuario')
        .order_by('-fecha_asignacion', '-evento__inicio_fecha', '-evento__inicio_hora')
    )

    return render(request, 'usuario/asignaciones/pedidosusuario.html', {
        'asignaciones': asignaciones
    })


def usuario_eventos_json(request):
    if not _solo_usuario(request):
        return JsonResponse([], safe=False)

    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return JsonResponse([], safe=False)

    tz = timezone.get_current_timezone()

    asignaciones = (
        AsignacionEvento.objects
        .filter(usuario_id=usuario_id)
        .select_related('evento')
        .order_by('evento__inicio_fecha', 'evento__inicio_hora')
    )

    data = []
    for a in asignaciones:
        e = a.evento
        start_dt = timezone.make_aware(datetime.combine(e.inicio_fecha, e.inicio_hora), tz)
        end_dt = None
        if e.fin_fecha and e.fin_hora:
            end_dt = timezone.make_aware(datetime.combine(e.fin_fecha, e.fin_hora), tz)

        data.append({
            "id": e.id_evento,
            "title": e.titulo,
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat() if end_dt else None,
        })

    return JsonResponse(data, safe=False)





def usuario_cambiar_estado(request, asig_id):
    # Cambia el estado: SOLO COMPLETADO desde este endpoint
    if request.method != "POST":
        return redirect("pedidosusuario")

    if not _solo_usuario(request):
        messages.error(request, "No tienes permisos.")
        return redirect("/login")

    usuario_id = request.session.get("usuario_id")
    if not usuario_id:
        messages.error(request, "Sesión no válida.")
        return redirect("/login")

    nuevo_estado = request.POST.get("estado")
    if nuevo_estado != "COMPLETADO":
        messages.error(request, "Solo puedes marcar COMPLETADO desde aquí.")
        return redirect("pedidosusuario")

    asign = (
        AsignacionEvento.objects
        .select_related("evento")
        .filter(id_usuario_evento=asig_id, usuario_id=usuario_id)
        .first()
    )

    if not asign:
        messages.error(request, "Asignación no encontrada.")
        return redirect("pedidosusuario")

    e = asign.evento

    if not (e.fin_fecha and e.fin_hora):
        messages.error(request, "Este evento no tiene fecha/hora fin.")
        return redirect("pedidosusuario")

    ahora = timezone.localtime()
    fin_dt = timezone.make_aware(
        datetime.combine(e.fin_fecha, e.fin_hora),
        timezone.get_current_timezone()
    )

    # Validaciones COMPLETADO
    inicio_dt = timezone.make_aware(
        datetime.combine(e.inicio_fecha, e.inicio_hora),
        timezone.get_current_timezone()
    )

    if ahora < inicio_dt:
        messages.error(request, "El evento aún no ha iniciado.")
        return redirect("pedidosusuario")

    if ahora > fin_dt + timedelta(minutes=5):
        messages.error(request,"El tiempo para marcar como completado ya terminó (5 minutos después del fin).")
        return redirect("pedidosusuario")

    asign.estado = "COMPLETADO"
    asign.estado_fecha = timezone.now()
    asign.save(update_fields=["estado", "estado_fecha"])

    messages.success(request, "Estado actualizado a COMPLETADO.")
    return redirect("pedidosusuario")




def _solo_admin(request):
    return request.session.get('usuario_tiporol') == 'ADMINISTRADOR'


def reporte_asignaciones(request):
    """
    Vista SOLO ADMIN para ver el estado de las asignaciones
    """
    if not _solo_admin(request):
        messages.error(request, "No tienes permisos.")
        return redirect('/login')

    estado_filtro = request.GET.get("estado")  # COMPLETADO / ATRASADO / NO_COMPLETADO / PENDIENTE
    asignaciones = (
        AsignacionEvento.objects
        .select_related("usuario", "evento", "evento__creado_por", "evento__creado_por__usuario")
        .order_by("-fecha_asignacion", "-evento__inicio_fecha", "-evento__inicio_hora")
    )

    if estado_filtro in ["COMPLETADO", "ATRASADO", "NO_COMPLETADO", "PENDIENTE"]:
        asignaciones = asignaciones.filter(estado=estado_filtro)

    total = AsignacionEvento.objects.count()
    total_completados = AsignacionEvento.objects.filter(estado="COMPLETADO").count()
    total_atrasados = AsignacionEvento.objects.filter(estado="ATRASADO").count()
    total_nocomp = AsignacionEvento.objects.filter(estado="NO_COMPLETADO").count()
    total_pendientes = AsignacionEvento.objects.filter(estado="PENDIENTE").count()

    contexto = {
        "asignaciones": asignaciones,
        "estado_filtro": estado_filtro,
        "total": total,
        "total_completados": total_completados,
        "total_atrasados": total_atrasados,
        "total_nocomp": total_nocomp,
        "total_pendientes": total_pendientes,
    }
    return render(request, "administrador/reportes/reporte_asignaciones.html", contexto)





def usuario_motivo_atrasado(request, asig_id):
    if not _solo_usuario(request):
        messages.error(request, "No tienes permisos.")
        return redirect("/login")

    usuario_id = request.session.get("usuario_id")
    if not usuario_id:
        messages.error(request, "Sesión no válida.")
        return redirect("/login")

    asign = (
        AsignacionEvento.objects
        .select_related("evento")
        .filter(id_usuario_evento=asig_id, usuario_id=usuario_id)
        .first()
    )
    if not asign:
        messages.error(request, "Asignación no encontrada.")
        return redirect("pedidosusuario")

    e = asign.evento

    if not (e.fin_fecha and e.fin_hora):
        messages.error(request, "Este evento no tiene fecha/hora fin.")
        return redirect("pedidosusuario")

    tz = timezone.get_current_timezone()
    fin_dt = timezone.make_aware(datetime.combine(e.fin_fecha, e.fin_hora), tz)
    ahora = timezone.localtime()

    if ahora < fin_dt:
        messages.error(request, "Aún no termina el evento.")
        return redirect("pedidosusuario")
    
    if request.method == "GET":
        contexto = {
            "asign": asign,
            "motivo_actual": asign.motivo_atrasado or "",
        }
        return render(request, "usuario/asignaciones/usuario_motivo_atrasado.html", contexto)

    motivo = request.POST.get("motivo", "").strip()
    if not motivo:
        messages.error(request, "Debes escribir un motivo.")
        return redirect(request.path)

    asign.estado = "ATRASADO"
    asign.estado_fecha = timezone.now()
    asign.motivo_atrasado = motivo     
    asign.save(update_fields=["estado", "estado_fecha", "motivo_atrasado"])

    messages.success(request, "Estado actualizado a ATRASADO con motivo registrado.")
    return redirect("pedidosusuario")




# MOTIVO NO COMPLETADO
def usuario_motivo_no_completado(request, asig_id):
    if not _solo_usuario(request):
        messages.error(request, "No tienes permisos.")
        return redirect("/login")

    usuario_id = request.session.get("usuario_id")
    if not usuario_id:
        messages.error(request, "Sesión no válida.")
        return redirect("/login")

    asign = (
        AsignacionEvento.objects
        .select_related("evento")
        .filter(id_usuario_evento=asig_id, usuario_id=usuario_id)
        .first()
    )
    if not asign:
        messages.error(request, "Asignación no encontrada.")
        return redirect("pedidosusuario")

    e = asign.evento

    if not (e.fin_fecha and e.fin_hora):
        messages.error(request, "Este evento no tiene fecha/hora fin.")
        return redirect("pedidosusuario")

    tz = timezone.get_current_timezone()
    fin_dt = timezone.make_aware(datetime.combine(e.fin_fecha, e.fin_hora), tz)
    ahora = timezone.localtime()

    if ahora < fin_dt:
        messages.error(request, "Aún no termina el evento.")
        return redirect("pedidosusuario")

    # GET va a formulario
    if request.method == "GET":
        contexto = {
            "asign": asign,
            # pasamos solo el motivo de NO COMPLETADO
            "motivo_actual": asign.motivo_no_completado or "",
        }
        return render(request, "usuario/asignaciones/usuario_motivo_no_completado.html", contexto)

    # POST va a guardar
    motivo = request.POST.get("motivo", "").strip()
    if not motivo:
        messages.error(request, "Debes escribir un motivo.")
        return redirect(request.path)

    asign.estado = "NO_COMPLETADO"
    asign.estado_fecha = timezone.now()
    asign.motivo_no_completado = motivo  
    asign.save(update_fields=["estado", "estado_fecha", "motivo_no_completado"])

    messages.success(request, "Estado actualizado a NO COMPLETADO con motivo registrado.")
    return redirect("pedidosusuario")



def reporte_ver_motivo(request, asig_id):

    if not _solo_admin(request):
        messages.error(request, "No tienes permisos.")
        return redirect('/login')

    asign = (
        AsignacionEvento.objects
        .select_related("usuario", "evento", "evento__creado_por", "evento__creado_por__usuario")
        .filter(id_usuario_evento=asig_id)
        .first()
    )

    if not asign:
        messages.error(request, "Asignación no encontrada.")
        return redirect("reporte_asignaciones")

    # Determinar estado y motivo a mostrar
    if asign.estado == "ATRASADO":
        estado_label = "Atrasado"
        motivo = asign.motivo_atrasado
    elif asign.estado == "NO_COMPLETADO":
        estado_label = "No completado"
        motivo = asign.motivo_no_completado
    elif asign.estado == "COMPLETADO":
        estado_label = "Completado"
        motivo = asign.estado_motivo
    else:
        estado_label = "Pendiente"
        motivo = asign.estado_motivo

    contexto = {
        "asign": asign,
        "estado_label": estado_label,
        "motivo": motivo,
    }
    return render(request, "administrador/reportes/reporte_ver_motivo.html", contexto)




#noticicaciones---------------------------------------------------------------------------------------------------------

def usuario_toast_evento(request):
    id_usuario = request.session.get("usuario_id")
    if not id_usuario:
        return JsonResponse({"ok": False})

    asign = (
        AsignacionEvento.objects
        .filter(usuario_id=id_usuario)
        .select_related("evento")
        .order_by("-fecha_asignacion")
        .first()
    )

    if not asign:
        return JsonResponse({"ok": False})

    e = asign.evento

    inicio_dt = datetime.combine(e.inicio_fecha, e.inicio_hora)
    inicio_txt = inicio_dt.strftime("%d-%m-%Y %I:%M %p")

    #  si no hay fin, puedes decidir: que nunca se detenga, o que no muestre
    if e.fin_fecha and e.fin_hora:
        fin_dt = datetime.combine(e.fin_fecha, e.fin_hora)
        fin_txt = fin_dt.strftime("%d-%m-%Y %I:%M %p")
        fin_iso = fin_dt.strftime("%Y-%m-%dT%H:%M:%S")
    else:
        fin_txt = "Sin final"
        fin_iso = None

    return JsonResponse({
        "ok": True,
        "inicio": inicio_txt,
        "fin": fin_txt,
        "fin_iso": fin_iso,   
        "descripcion": e.descripcion or "-"
    })





#panel de administrador-------------------------------------------------------------------------------------------------------------

#calendario--------------------------------------------------------------------------------------------------

def admin_calendario(request):
    if not _solo_admin(request):
        messages.error(request, "No tienes permisos.")
        return redirect('/login')
    return render(request, 'administrador/calendario/admin_calendario.html')


def admin_eventos_json(request):
    if not _solo_admin(request):
        return JsonResponse([], safe=False)

    eventos = EventoAdmin.objects.all().order_by('inicio_fecha', 'inicio_hora')
    tz = timezone.get_current_timezone()

    data = []
    for e in eventos:
        start_dt = timezone.make_aware(datetime.combine(e.inicio_fecha, e.inicio_hora), tz)

        end_dt = None
        if e.fin_fecha and e.fin_hora:
            end_dt = timezone.make_aware(datetime.combine(e.fin_fecha, e.fin_hora), tz)

        data.append({
            "id": e.id_evento,
            "title": e.titulo,
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat() if end_dt else None,
        })

    return JsonResponse(data, safe=False)



def admin_evento_crear(request):# Crear evento
    if not _solo_admin(request):
        messages.error(request, "No tienes permisos.")
        return redirect('/login')

    if request.method == 'POST':
        titulo = request.POST.get('titulo', '').strip()
        inicio_fecha = request.POST.get('inicio_fecha', '').strip()
        inicio_hora  = request.POST.get('inicio_hora', '').strip()
        fin_fecha = request.POST.get('fin_fecha', '').strip()
        fin_hora  = request.POST.get('fin_hora', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()

        # Convertir fechas y horas
        d_ini = parse_date(inicio_fecha)
        t_ini = parse_time(inicio_hora)
        d_fin = parse_date(fin_fecha) if fin_fecha else None
        t_fin = parse_time(fin_hora) if fin_hora else None

        if not titulo or not d_ini or not t_ini:
            messages.error(request, "Título, fecha de inicio y hora de inicio son obligatorios.")
            return redirect('/panel/calendario/')

        if (d_fin and not t_fin) or (t_fin and not d_fin):
            d_fin, t_fin = None, None

        # Obtener al usuario logueado
        usuario_id = request.session.get('usuario_id')
        usuario = Usuario.objects.get(id_usuario=usuario_id)

        # Obtener su perfil administrador
        try:
            admin = Administrador.objects.get(usuario=usuario)
        except Administrador.DoesNotExist:
            messages.error(request, "Este usuario no tiene perfil de administrador.")
            return redirect('/panel/calendario/')

        # Crear el evento con el administrador real
        EventoAdmin.objects.create(
            titulo=titulo,
            inicio_fecha=d_ini,
            inicio_hora=t_ini,
            fin_fecha=d_fin,
            fin_hora=t_fin,
            descripcion=descripcion,
            creado_por=admin
        )

        messages.success(request, "Evento creado correctamente.")
        return redirect('/panel/calendario/lista/')

    return redirect('/panel/calendario/')





def listar_eventos_admin(request):
    if not _solo_admin(request):
        messages.error(request, "No tienes permisos.")
        return redirect('/login')

    eventos = EventoAdmin.objects.all().order_by('-inicio_fecha', '-inicio_hora')

    return render(request, 'administrador/calendario/listacalendarios.html', {
        'eventos': eventos
    })



def editar_evento_admin(request, id_evento):
    if not _solo_admin(request):
        messages.error(request, "No tienes permisos.")
        return redirect('/login')

    evento = EventoAdmin.objects.get(id_evento=id_evento)
    if request.method == "POST":
        titulo = request.POST.get('titulo')
        inicio_fecha = parse_date(request.POST.get('inicio_fecha'))
        inicio_hora  = parse_time(request.POST.get('inicio_hora'))
        fin_fecha    = parse_date(request.POST.get('fin_fecha')) if request.POST.get('fin_fecha') else None
        fin_hora     = parse_time(request.POST.get('fin_hora')) if request.POST.get('fin_hora') else None
        descripcion  = request.POST.get('descripcion')

        evento.titulo = titulo
        evento.inicio_fecha = inicio_fecha
        evento.inicio_hora = inicio_hora
        evento.fin_fecha = fin_fecha
        evento.fin_hora = fin_hora
        evento.descripcion = descripcion

        evento.save()

        messages.success(request, "Evento actualizado correctamente.")
        return redirect('/panel/calendario/lista/')

    return render(request, 'administrador/calendario/editar_evento.html', {'evento': evento})



def eliminar_evento_admin(request, id_evento):
    if not _solo_admin(request):
        messages.error(request, "No tienes permisos.")
        return redirect('/login')
    try:
        evento = EventoAdmin.objects.get(id_evento=id_evento)
        evento.delete()
        messages.success(request, "Evento eliminado correctamente.")
    except EventoAdmin.DoesNotExist:
        messages.error(request, "El evento no existe.")

    return redirect('/panel/calendario/lista/')


#cliente-------------------------------------------------------------------------------------------------------------

def lista_asignaciones(request):
    asignaciones = AsignacionEvento.objects.select_related("usuario", "evento")
    return render(request, 'administrador/calendario/lista_asignaciones.html', {
        'asignaciones': asignaciones
    })



def crear_asignacion(request):
    # Solo mostrar usuarios normales (no admin)
    usuarios = Usuario.objects.filter(tiporol="USUARIO")
    eventos = EventoAdmin.objects.all()

    if request.method == "POST":
        usuario_id = request.POST.get("usuario")
        evento_id = request.POST.get("evento")
        descripcion = request.POST.get("descripcion")
        fecha_asignacion = request.POST.get("fecha_asignacion")
        # Evitar duplicados
        if AsignacionEvento.objects.filter(usuario_id=usuario_id, evento_id=evento_id).exists():
            messages.error(request, "El usuario ya está asignado a este evento.")
            return redirect("/crear_asignacion/")

        AsignacionEvento.objects.create(
            usuario_id=usuario_id,
            evento_id=evento_id,
            descripcion_evento=descripcion,
            fecha_asignacion=fecha_asignacion
        )

        messages.success(request, "Asignación creada correctamente.")
        return redirect("/lista_asignaciones/")

    return render(request, 'administrador/calendario/crear_asignacion.html', {
        'usuarios': usuarios,
        'eventos': eventos,
    })


def editar_asignacion(request, id):
    asignacion = AsignacionEvento.objects.get(id_usuario_evento=id)
    usuarios = Usuario.objects.filter(tiporol="USUARIO")   # Solo mostrar usuarios normales (no administradores)
    eventos = EventoAdmin.objects.all()    # Puedes filtrar eventos si deseas, por ahora se mantienen todos:
    if request.method == "POST":
        asignacion.usuario_id = request.POST.get("usuario")
        asignacion.evento_id = request.POST.get("evento")
        asignacion.descripcion_evento = request.POST.get("descripcion")
        asignacion.fecha_asignacion = request.POST.get("fecha_asignacion")
        asignacion.save()

        messages.success(request, "Asignación actualizada correctamente.")
        return redirect("/lista_asignaciones/")

    return render(request, "administrador/calendario/editar_asignacion.html", {
        "asignacion": asignacion,
        "usuarios": usuarios,
        "eventos": eventos
    })



def eliminar_asignacion(request, id):
    asignacion = AsignacionEvento.objects.get(id_usuario_evento=id)
    asignacion.delete()
    messages.success(request, "Asignación eliminada correctamente.")
    return redirect("/lista_asignaciones/")



#provedor--------------------------------------------------------------------------------------------------------------------

def listadoproveedor(request):
    proveedores = Proveedor.objects.all()
    return render(request, 'administrador/proveedores/listadoproveedor.html', {'proveedores': proveedores})


def nuevoproveedor(request):
    return render(request, 'administrador/proveedores/nuevoproveedor.html')


def guardarproveedor(request):
    nombre = request.POST['txt_nombre']
    direccion = request.POST['txt_direccion']
    telefono = request.POST['txt_telefono']
    correo = request.POST['txt_correo']
    ruc = request.POST['txt_ruc']
    estado = request.POST['txt_estado']

    Proveedor.objects.create(
        nombre_proveedor=nombre,
        direccion_proveedor=direccion,
        telefono_proveedor=telefono,
        correo_proveedor=correo,
        ruc_proveedor=ruc,
        estado_proveedor=estado
    )

    messages.success(request, "Proveedor guardado correctamente.")
    return redirect('/listadoproveedor')


def eliminarproveedor(request, id):
    proveedor = Proveedor.objects.get(id_proveedor=id)
    proveedor.delete()
    messages.success(request, "Proveedor eliminado correctamente.")
    return redirect('/listadoproveedor')


def editarproveedor(request, id):
    proveedor = Proveedor.objects.get(id_proveedor=id)
    return render(request, 'administrador/proveedores/editarproveedor.html', {'proveedor': proveedor})


def procesareditarproveedor(request):
    proveedor = Proveedor.objects.get(id_proveedor=request.POST['id'])

    proveedor.nombre_proveedor = request.POST['txt_nombre']
    proveedor.direccion_proveedor = request.POST['txt_direccion']
    proveedor.telefono_proveedor = request.POST['txt_telefono']
    proveedor.correo_proveedor = request.POST['txt_correo']
    proveedor.ruc_proveedor = request.POST['txt_ruc']
    proveedor.estado_proveedor = request.POST['txt_estado']

    proveedor.save()

    messages.success(request, "Proveedor actualizado exitosamente.")
    return redirect('/listadoproveedor')


#pedido--------------------------------------------------------------------------------------------------------------------

def listadopedido(request):
    pedidos = Pedido.objects.select_related("proveedor", "evento").all()
    return render(request, 'administrador/pedidos/listadopedido.html', {'pedidos': pedidos})


def nuevopedido(request):
    proveedores = Proveedor.objects.all()
    eventos = EventoAdmin.objects.all()
    return render(request, 'administrador/pedidos/nuevopedido.html', {
        'proveedores': proveedores,
        'eventos': eventos
    })


def guardarpedido(request):
    descripcion = request.POST['txt_descripcion']
    proveedor_id = request.POST['txt_proveedor'] or None
    evento_id = request.POST['txt_evento']
    fecha_pedido = request.POST['txt_fecha']
    estado = request.POST['txt_estado']

    Pedido.objects.create(
        descripcion_pedido=descripcion,
        proveedor_id=proveedor_id,
        evento_id=evento_id if evento_id != "" else None,
        fecha_pedido=fecha_pedido,
        estado_pedido=estado
    )

    messages.success(request, "Pedido guardado correctamente.")
    return redirect('/listadopedido')


def eliminarpedido(request, id):
    pedido = Pedido.objects.get(id_pedido=id)
    pedido.delete()
    messages.success(request, "Pedido eliminado correctamente.")
    return redirect('/listadopedido')


def editarpedido(request, id):
    pedido = Pedido.objects.get(id_pedido=id)
    proveedores = Proveedor.objects.all()
    eventos = EventoAdmin.objects.all()

    return render(request, 'administrador/pedidos/editarpedido.html', {
        'pedido': pedido,
        'proveedores': proveedores,
        'eventos': eventos
    })



def procesareditarpedido(request):
    pedido = Pedido.objects.get(id_pedido=request.POST['id'])
    pedido.descripcion_pedido = request.POST['txt_descripcion']
    pedido.proveedor_id = request.POST['txt_proveedor']if request.POST['txt_proveedor'] != "" else None
    pedido.evento_id = request.POST['txt_evento'] if request.POST['txt_evento'] != "" else None
    pedido.fecha_pedido = request.POST['txt_fecha']
    pedido.estado_pedido = request.POST['txt_estado']

    pedido.save()

    messages.success(request, "Pedido actualizado exitosamente.")
    return redirect('/listadopedido')


#DetallePedido-----------------------------------------------------------------------------------------------------

def listadodetalle(request, id_pedido):
    pedido = Pedido.objects.get(id_pedido=id_pedido)
    detalles = DetallePedido.objects.filter(pedido_id=id_pedido)
    return render(request, "administrador/pedidos/listadodetalle.html", {
        "pedido": pedido,
        "detalles": detalles
    })


def nuevodetalle(request, id_pedido):
    pedido = Pedido.objects.get(id_pedido=id_pedido)
    return render(request, 'administrador/pedidos/nuevodetalle.html', {'pedido': pedido})

def guardardetalle(request):

    pedido_id = request.POST["pedido_id"]
    descripcion = request.POST["txt_descripcion"]
    cantidad = request.POST["txt_cantidad"]
    precio = request.POST["txt_precio"]

    DetallePedido.objects.create(
        pedido_id=pedido_id,
        descripcion_item=descripcion,
        cantidad=cantidad,
        precio_unitario=precio
    )

    messages.success(request, "Detalle guardado correctamente.")
    return redirect(f'/listadodetalle/{pedido_id}/')


def editardetalle(request, id):
    detalle = DetallePedido.objects.get(id_detalle_pedido=id)
    return render(request, 'administrador/pedidos/editardetalle.html', {
        'detalle': detalle,
        'pedido': detalle.pedido
    })


def procesareditardetalle(request):
    detalle = DetallePedido.objects.get(id_detalle_pedido=request.POST["id"])
    detalle.descripcion_item = request.POST["txt_descripcion"]
    detalle.cantidad = request.POST["txt_cantidad"]
    detalle.precio_unitario = request.POST["txt_precio"]
    detalle.save()

    messages.success(request, "Detalle actualizado correctamente.")
    return redirect(f"/listadodetalle/{detalle.pedido.id_pedido}/")


def eliminardetalle(request, id):
    detalle = DetallePedido.objects.get(id_detalle_pedido=id)
    pedido_id = detalle.pedido.id_pedido
    detalle.delete()

    messages.success(request, "Detalle eliminado correctamente.")
    return redirect(f"/listadodetalle/{pedido_id}/")


def seleccionar_pedido_detalle(request):
    pedidos = Pedido.objects.all()
    return render(request, "administrador/pedidos/seleccionar_pedido.html", {"pedidos": pedidos})


def redirigir_detalle_nuevo(request):
    id_pedido = request.POST["id_pedido"]
    return redirect(f"/nuevodetalle/{id_pedido}/")



def redirigir_detalle_lista(request):
    id_pedido = request.POST["id_pedido"]
    return redirect(f"/listadodetalle/{id_pedido}/")




#factura------------------------------------------------------------------------------------------------------------------------------------

def nuevafactura(request):
    pedidos = Pedido.objects.all()
    return render(request, 'administrador/facturas/nuevafactura.html', {
        'pedidos': pedidos
    })



def crear_factura(request):
    if request.method == "POST":
        cliente_nombre = request.POST["cliente_nombre"]
        pedido_id = request.POST["pedido_id"]
        pedido = Pedido.objects.get(id_pedido=pedido_id)
        ultimo = Factura.objects.count() + 1
        numero_factura = f"001-001-{str(ultimo).zfill(9)}"

        numero_cuenta = request.POST.get("numero_cuenta", "").strip()

        # Crear factura
        factura = Factura.objects.create(
            cliente_nombre=cliente_nombre,
            numero_factura=numero_factura,
            pedido=pedido,
            numero_cuenta=numero_cuenta 
        )
        # Calcular y guardar totales
        factura.recalcular_totales()
        # Redirigir a vista SOLO LECTURA
        return redirect('ver_factura', id_factura=factura.id_factura)



def ver_factura(request, id_factura):
    factura = Factura.objects.get(id_factura=id_factura)
    detalles = factura.pedido.detallepedido_set.all()
    return render(request, 'administrador/facturas/ver_factura.html', {
        'factura': factura,
        'detalles': detalles
    })




def listado_facturas(request):
    facturas = Factura.objects.all().order_by('-fecha_emision')
    return render(request, 'administrador/facturas/listadofacturas.html', {
        'facturas': facturas
    })



def eliminar_factura(request, id):
    factura = Factura.objects.get(id_factura=id)
    if factura.estado_factura == "PAGADA":
        messages.error(request, "No se puede eliminar una factura PAGADA.")
        return redirect('/listadofacturas/')

    factura.delete()
    messages.success(request, "Factura eliminada correctamente.")
    return redirect('/listadofacturas/')




#crea la factura en formato pdf -----------

from django.http import HttpResponse
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib import colors
from decimal import Decimal
from .models import Factura


def factura_pdf(request, id_factura):
    factura = Factura.objects.get(id_factura=id_factura)
    detalles = factura.pedido.detallepedido_set.all()
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = (f'attachment; filename="Factura_{factura.numero_factura}.pdf"')

    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=70,
        bottomMargin=48
    )

    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name='Titulo',
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=20,
        bold=True
    ))

    styles.add(ParagraphStyle(
        name='Derecha',
        alignment=TA_RIGHT
    ))

    elementos = []

    # TÍTULO
    elementos.append(Paragraph("FACTURA", styles['Titulo']))


    # DATOS GENERALES (TABLA)
    info = [
        ["N° Factura:", factura.numero_factura],
        ["Cliente:", factura.cliente_nombre],
        ["Fecha:", factura.fecha_emision.strftime("%Y-%m-%d")],
        ["Estado:", factura.estado_factura],
        ["Numero de cuenta:",factura.numero_cuenta],
    ]

    tabla_info = Table(info, colWidths=[100, 350])
    tabla_info.setStyle(TableStyle([
        ('FONT', (0,0), (-1,-1), 'Helvetica'),
        ('BACKGROUND', (0,0), (0,-1), colors.whitesmoke),
        ('BOX', (0,0), (-1,-1), 0.5, colors.black),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))

    elementos.append(tabla_info)
    elementos.append(Spacer(1, 20))

    # TABLA DE DETALLES
    data = [["Descripción", "Cantidad", "Precio Unitario", "Subtotal"]]

    for d in detalles:
        data.append([
            d.descripcion_item,
            str(d.cantidad),
            f"$ {d.precio_unitario}",
            f"$ {d.subtotal()}"
        ])

    tabla_detalles = Table(
        data,
        colWidths=[230, 70, 100, 100]
    )

    tabla_detalles.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('ALIGN', (1,1), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))

    elementos.append(tabla_detalles)
    elementos.append(Spacer(1, 20))


    # TOTALES (TABLA DERECHA)
    totales = [
        ["Subtotal:", f"$ {factura.subtotal}"],
        ["IVA (15%):", f"$ {factura.iva}"],
        ["TOTAL:", f"$ {factura.total}"],
    ]

    tabla_totales = Table(
        totales,
        colWidths=[100, 120],
        hAlign='RIGHT'
    )

    tabla_totales.setStyle(TableStyle([
        ('FONT', (0,0), (-1,-1), 'Helvetica-Bold'),
        ('BACKGROUND', (0,2), (-1,2), colors.lightgrey),
        ('BOX', (0,0), (-1,-1), 0.5, colors.black),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))

    elementos.append(tabla_totales)

    # CONSTRUIR PDF con identidad institucional y marca de agua.
    branding_factura = lambda canvas, documento: draw_simple_pdf_branding(
        canvas, documento, title="DISTRIC C · FACTURA"
    )
    doc.build(
        elementos,
        onFirstPage=branding_factura,
        onLaterPages=branding_factura,
    )
    return response






#pago----------------------------------------------------------------------------------------------------

def registrar_pago(request, id_factura):
    factura = Factura.objects.get(id_factura=id_factura)
    if factura.estado_factura == 'PAGADA':
        messages.warning(request, "Esta factura ya fue pagada.")
        return redirect('ver_factura', factura.id_factura)

    return render(request, "administrador/pagos/registrar_pago.html", {
        "factura": factura
    })


def guardar_pago(request):
    if request.method != 'POST':
        return redirect('listado_pagos')
    
    factura = Factura.objects.get(id_factura=request.POST['factura_id'])
    monto = Decimal(request.POST['monto'])
    metodo = request.POST['metodo']
    referencia = request.POST.get('referencia')
    comprobante=request.FILES.get('comprobante')
    banco = request.POST.get('banco')

    if monto != factura.total:
        messages.error(request, 'El monto debe ser igual al total de la factura.')
        return redirect('registrar_pago', factura.id_factura)

    Pago.objects.create(
        factura=factura,
        metodo_pago=metodo,
        monto_pagado=monto,
        banco=banco,
        referencia=referencia,
        comprobante=comprobante,
        estado_pago='CONFIRMADO'
    )

    factura.estado_factura = 'PAGADA'
    factura.save()

    messages.success(request, 'Pago registrado correctamente.')
    return redirect('ver_factura', factura.id_factura)




def listado_pagos(request):
    pagos = Pago.objects.select_related('factura').order_by('-fecha_pago')
    return render(request, 'administrador/pagos/listado_pagos.html', {
        'pagos': pagos
    })



def ver_pago(request, id_pago):
    pago = Pago.objects.select_related('factura').get(id_pago=id_pago)
    return render(request, 'administrador/pagos/ver_pago.html', {
        'pago': pago
    })



def editar_pago(request, id_pago):
    pago = Pago.objects.get(id_pago=id_pago)

    if request.method == 'POST':
        pago.metodo_pago = request.POST['metodo_pago']
        pago.monto_pagado = request.POST['monto_pagado']
        pago.banco = request.POST.get('banco')
        pago.referencia = request.POST.get('referencia')
        pago.estado_pago = request.POST['estado_pago']

        if request.FILES.get('comprobante'):
            pago.comprobante = request.FILES['comprobante']

        pago.save()
        messages.success(request, 'Pago actualizado correctamente.')
        return redirect('listado_pagos')

    return render(request, 'administrador/pagos/editar_pago.html', {
        'pago': pago
    })




def eliminar_pago(request, id_pago):
    pago = Pago.objects.get(id_pago=id_pago)
    factura = pago.factura
    pago.delete()
    factura.estado_factura = 'PENDIENTE'
    factura.save()
    messages.success(request, 'Pago eliminado y factura reabierta.')
    return redirect('listado_pagos')



#salcovconducto--------------------------------------------------------------------------------

def salvoconductos(request):
    salvoconductos = Salvoconducto.objects.select_related(
        'usuario', 'vehiculo'
    )
    return render(
        request,
        'administrador/salvoconductos/salvoconductos.html',
        {'salvoconductos': salvoconductos}
    )


def nuevosalvoconducto(request):
    if request.method == 'POST':
        usuario_id = request.POST['usuario']
        vehiculo_id = request.POST['vehiculo']
        viaje_id = request.POST['viaje']
        motivo = request.POST['motivo']
        fecha_inicio = request.POST['fecha_inicio']
        fecha_fin = request.POST['fecha_fin']
        estado = request.POST['estado']

        #  VALIDACIÓN 1: fechas
        if fecha_fin < fecha_inicio:
            messages.error(request, 'La fecha fin no puede ser menor a la fecha inicio.')
            return redirect('nuevosalvoconducto')

        #  VALIDACIÓN 2: checklist del vehículo
        tiene_checklist = ChecklistVehiculo.objects.filter(
            usuario_id=usuario_id
        ).exists()

        if not tiene_checklist:
            messages.error(request, 'El vehículo no tiene checklist registrado.')
            return redirect('nuevosalvoconducto')


        # VALIDACIÓN 3: viaje ya tiene salvoconducto
        existe_salvoconducto = Salvoconducto.objects.filter(
            viaje_id=viaje_id
        ).exists()

        if existe_salvoconducto:
            messages.error(request,' Este viaje ya tiene un salvoconducto registrado.')
            return redirect('nuevosalvoconducto')

        # guardar
        Salvoconducto.objects.create(
            usuario_id=usuario_id,
            vehiculo_id=vehiculo_id,
            viaje_id=viaje_id,
            motivo=motivo,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            estado=estado
        )

        messages.success(request, 'Salvoconducto creado correctamente.')
        return redirect('salvoconductos')

    return render(request, 'administrador/salvoconductos/nuevosalvoconducto.html', {
        'usuarios': Usuario.objects.all(),
        'vehiculos': Vehiculo.objects.all(),
        'viajes': obtener_viajes_formateados(),
    })




def editarsalvoconducto(request, id):
    salvoconducto = Salvoconducto.objects.get(id_salvoconducto=id)
    if request.method == 'POST':
        salvoconducto.usuario_id = request.POST['usuario']
        salvoconducto.vehiculo_id = request.POST['vehiculo']
        salvoconducto.motivo = request.POST['motivo']
        salvoconducto.fecha_inicio = request.POST['fecha_inicio']
        salvoconducto.fecha_fin = request.POST['fecha_fin']
        salvoconducto.estado = request.POST['estado']
        salvoconducto.save()
        return redirect('salvoconductos')

    return render(
        request,
        'administrador/salvoconductos/editarsalvoconducto.html',
        {
            'salvoconducto': salvoconducto,
            'usuarios': Usuario.objects.all(),
            'vehiculos': Vehiculo.objects.all(),
        }
    )


def eliminarsalvoconducto(request, id):
    Salvoconducto.objects.get(id_salvoconducto=id).delete()
    return redirect('salvoconductos')


def obtener_viajes_formateados():
    viajes = (
        Viaje.objects
        .select_related("usuario", "vehiculo", "destino")
        .order_by("-fecha_creacion")
    )

    data = []

    for viaje in viajes:
        data.append({
            "id_viaje": viaje.id_viaje,
            "usuario": f"{viaje.usuario.nombre_usuario} {viaje.usuario.apellido_usuario}",
            "vehiculo": viaje.vehiculo.matricula_vehiculo,
            "tipo_combustible": viaje.vehiculo.tipocombustible_vehiculo,
            "destino": (
                viaje.destino_final_nombre
                or (viaje.destino.nombre_Lugarguardado if viaje.destino else "Destino no especificado")
            ),
            "fecha": viaje.fecha_creacion
        })

    return data




#pdf de salvoconducto--------------------------------------------------
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, black
from reportlab.lib.utils import ImageReader
from django.http import HttpResponse
from django.utils.timezone import now
from django.conf import settings
from django.core.cache import cache
import os

def generar_pdf_salvoconducto(request, id):
    s = Salvoconducto.objects.select_related(
        'usuario','vehiculo','viaje','viaje__origen','viaje__destino'
    ).get(id_salvoconducto=id)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename=salvoconducto_{id}.pdf'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    draw_pdf_watermark(p, A4)
    draw_pdf_logos(p, A4, y_from_top=10)

    azul = HexColor("#1F4FD8")
    gris = HexColor("#444444")


    # ENCABEZADO
    p.setFont("Helvetica-Bold", 16)
    p.setFillColor(azul)
    p.drawString(50, height - 50, "SALVOCONDUCTO DE MOVILIZACIÓN")

    p.setFont("Helvetica", 10)
    p.setFillColor(black)

    # Separador del encabezado institucional.
    p.line(50, height - 105, width - 50, height - 105)


    # CUERPO
    y = height - 120
    label_x = 50
    value_x = 180
    salto = 22

    def campo(etiqueta, valor):
        nonlocal y
        p.setFont("Helvetica-Bold", 10)
        p.drawString(label_x, y, etiqueta)
        p.setFont("Helvetica", 10)
        p.drawString(value_x, y, valor)
        y -= salto

    campo("Conductor:", f"{s.usuario.nombre_usuario} {s.usuario.apellido_usuario}")
    campo("Vehículo:", f"{s.vehiculo.matricula_vehiculo} ({s.vehiculo.tipovehiculo_vehiculo})")
    destino_viaje = (
        s.viaje.destino_final_nombre
        or (s.viaje.destino.nombre_Lugarguardado if s.viaje.destino else "Destino no especificado")
    )
    campo("Destino:", destino_viaje)
    campo("Vigencia:", f"{s.fecha_inicio} al {s.fecha_fin}")
    campo("Estado:", s.estado_actual()) 


    p.setFont("Helvetica-Bold", 10)
    p.drawString(label_x, y, "Motivo:")
    y -= 16
    p.setFont("Helvetica", 10)
    p.drawString(label_x, y, s.motivo)


    # QR REAL
    qr_buffer = generar_qr_salvoconducto(s.id_salvoconducto)
    qr_image = ImageReader(qr_buffer)

    qr_x = width - 170
    qr_y = 130
    qr_size = 120

    p.drawImage(
        qr_image,
        qr_x,
        qr_y,
        width=qr_size,
        height=qr_size,
        mask='auto'
    )

    p.setFont("Helvetica", 8)
    p.drawCentredString(qr_x + qr_size / 2, qr_y - 12, "Escanee para validar")


    # PIE de pagina
    p.line(50, 120, 250, 120)
    p.drawString(50, 105, "Firma responsable")

    p.setFont("Helvetica", 9)
    p.setFillColor(gris)
    p.drawString(50, 80, f"Documento generado el {now().strftime('%Y-%m-%d %H:%M')}")

    p.showPage()
    p.save()

    return response


#qr-------------------------------------------------------------------
import qrcode
from io import BytesIO
def generar_qr_salvoconducto(id):
    base_url = getattr(settings, "PUBLIC_BASE_URL", "") or "http://127.0.0.1:8000"
    url = f"{base_url}/validar/salvoconducto/{id}/"
    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer



def validar_salvoconducto(request, id):
    s = Salvoconducto.objects.get(id_salvoconducto=id)
    estado_real = s.estado_actual()  
    return render(request, "administrador/salvoconductos/validar_salvoconducto.html", {
        "salvoconducto": s,
        "estado_real": estado_real
    })




#reportes----------------------------------------------------------------------------------------------
def reporteviaje(request):
    return render(request,"administrador/reportes/reporteviaje.html",
        {"viajes": obtener_viajes_formateados()})




def reportehistorial(request):
    viajes = (
        Viaje.objects
        .select_related("usuario", "vehiculo", "destino")
        .prefetch_related(
            Prefetch(
                "opciones",
                queryset=RutaOpcion.objects.filter(
                    Q(seleccionada=True) | Q(tramo__isnull=True)
                ),
            )
        )
        .order_by("-fecha_creacion")
    )

    data = []
    for viaje in viajes:
        for ruta in viaje.opciones.all():  
            data.append({
                "id": viaje.id_viaje,
                "usuario": f"{viaje.usuario.nombre_usuario} {viaje.usuario.apellido_usuario}",
                "fecha": viaje.fecha_creacion,
                "destino": (
                viaje.destino_final_nombre
                or (viaje.destino.nombre_Lugarguardado if viaje.destino else "Destino no especificado")
            ),
                "vehiculo": viaje.vehiculo.matricula_vehiculo,

                "ruta": ruta.tipo,               
                "tiempo": ruta.tiempo_min,
                "distancia": ruta.distancia_km,
                "consumo": ruta.consumo_litros,
                "costo": ruta.costo_estimado,
            })

    return render(request, "administrador/reportes/reportehistorial.html", {"viajes": data})





#kpis--------------------------------------------------------------------------

def admin_panel(request):
    acceso = _validar_acceso_admin_usuarios(request)

    if acceso:
        return acceso

    # KPI 1: lugar más repetido por cada usuario
    lugares_agrupados = (
        Lugarguardado.objects
        .values(
            'usuario_id',
            'usuario__nombre_usuario',
            'usuario__apellido_usuario',
            'nombre_Lugarguardado'
        )
        .annotate(total=Count('id_Lugarguardado'))
        .order_by('usuario_id', '-total')
    )

    resultado_por_usuario = []
    usuarios_vistos = set()

    for l in lugares_agrupados:
        uid = l['usuario_id']
        if uid in usuarios_vistos:
            continue
        usuarios_vistos.add(uid)
        resultado_por_usuario.append(l)


    kpi1_labels = []
    for l in resultado_por_usuario:
        etiqueta = (
            l['usuario__nombre_usuario'] + " " +
            l['usuario__apellido_usuario'] + " → " +
            l['nombre_Lugarguardado']
        )
        kpi1_labels.append(etiqueta)

    kpi1_data = [l['total'] for l in resultado_por_usuario]



    # KPI 2 (NUEVO): Scatter por usuario
    # X = Velocidad (km/h)
    # Y = Consumo (L/100km)
    agg = (
        RutaOpcion.objects
        .filter(viaje__usuario__tiporol="USUARIO")
        .filter(Q(seleccionada=True) | Q(tramo__isnull=True))
        .values(
            'viaje__usuario_id',
            'viaje__usuario__nombre_usuario',
            'viaje__usuario__apellido_usuario',
        )
        .annotate(
            dist_total=Sum('distancia_km'),
            tiempo_total=Sum('tiempo_min'),
            litros_total=Sum('consumo_litros'),
        )
    )

    kpi2_points = []
    for row in agg:
        dist = row['dist_total'] or 0
        tmin = row['tiempo_total'] or 0
        litros = row['litros_total'] or 0

        # Evitar división por 0
        if dist <= 0 or tmin <= 0:
            continue

        tiempo_h = Decimal(str(tmin)) / Decimal("60")
        velocidad_kmh = (Decimal(str(dist)) / tiempo_h).quantize(Decimal("0.01"))

        # Consumo L/100km
        consumo_l_100 = ((Decimal(str(litros)) / Decimal(str(dist))) * Decimal("100")).quantize(Decimal("0.01"))

        nombre = f"{row['viaje__usuario__nombre_usuario']} {row['viaje__usuario__apellido_usuario']}"
        kpi2_points.append({
            "x": float(velocidad_kmh),
            "y": float(consumo_l_100),
            "nombre": nombre
        })

    # KPI 3: total consumo (L) por mes (TODOS los usuarios)
    meses_es = {
        1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
        7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"
    }

    kpi3_qs = (
        RutaOpcion.objects
        .filter(viaje__usuario__tiporol="USUARIO")
        .filter(Q(seleccionada=True) | Q(tramo__isnull=True))
        .annotate(mes=TruncMonth('viaje__fecha_creacion'))
        .values('mes')
        .annotate(total_litros=Sum('consumo_litros'))
        .order_by('mes')
    )

    kpi3_labels = []
    kpi3_data = []

    for r in kpi3_qs:
        if not r["mes"]:
            continue
        m = r["mes"]
        total = r["total_litros"] or 0
        kpi3_labels.append(f"{meses_es[m.month]} {m.year}")
        kpi3_data.append(round(float(total), 2))



    # KPI 4: total COSTO ($) por mes (TODOS los usuarios)
    kpi4_qs = (
        RutaOpcion.objects
        .filter(viaje__usuario__tiporol="USUARIO")
        .filter(Q(seleccionada=True) | Q(tramo__isnull=True))
        .filter(costo_estimado__isnull=False)  # evita nulls
        .annotate(mes=TruncMonth('viaje__fecha_creacion'))
        .values('mes')
        .annotate(total_costo=Sum('costo_estimado'))
        .order_by('mes')
    )

    kpi4_labels = []
    kpi4_data = []

    for r in kpi4_qs:
        if not r["mes"]:
            continue
        m = r["mes"]
        total = r["total_costo"] or 0
        kpi4_labels.append(f"{meses_es[m.month]} {m.year}")
        kpi4_data.append(round(float(total), 2))



    # KPI 5: pedidos realizados por día
    dias_labels = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    kpi5_counts = [0, 0, 0, 0, 0, 0, 0]  # lunes=0 ... domingo=6

    pedidos_por_dia = (
        Pedido.objects
        .values('fecha_pedido')
        .annotate(total=Count('id_pedido'))
    )

    for p in pedidos_por_dia:
        fecha = p["fecha_pedido"]
        if not fecha:
            continue
        idx = fecha.weekday()  # lunes=0 ... domingo=6
        kpi5_counts[idx] += p["total"]

    kpi5_labels = dias_labels
    kpi5_data = kpi5_counts


    # KPI 6: Total litros consumidos por tipo de combustible
    kpi6_qs = (
        RutaOpcion.objects
        .filter(viaje__usuario__tiporol="USUARIO")
        .filter(Q(seleccionada=True) | Q(tramo__isnull=True))
        .filter(combustible_tipo__isnull=False, consumo_litros__isnull=False)
        .values('combustible_tipo')
        .annotate(total_litros=Sum('consumo_litros'))
    )
    kpi6_map = {"EXTRA": 0, "DIESEL": 0, "ECOPAIS": 0, "SUPER": 0}

    for r in kpi6_qs:
        tipo = (r["combustible_tipo"] or "").upper()
        if tipo in kpi6_map:
            kpi6_map[tipo] = round(float(r["total_litros"] or 0), 2)

    kpi6_labels = list(kpi6_map.keys())
    kpi6_data = list(kpi6_map.values())



    hoy = timezone.localdate()
    cargas_pendientes_hoy = (
        PlanCarga.objects
        .filter(fecha_planificada=hoy)
        .exclude(estado__in=['COMPLETADO', 'CANCELADO'])
        .count()
    )
    viajes_en_ruta = (
        Viaje.objects
        .filter(fecha_creacion__date=hoy, estado='EN_RUTA', es_prueba_administrativa=False)
        .count()
    )
    rutas_operativas_hoy = (
        RutaOpcion.objects
        .filter(viaje__fecha_creacion__date=hoy, viaje__es_prueba_administrativa=False)
        .filter(Q(seleccionada=True) | Q(tramo__isnull=True))
    )
    resumen_hoy = rutas_operativas_hoy.aggregate(
        litros=Sum('consumo_litros'),
        costo=Sum('costo_estimado'),
    )
    litros_estimados_hoy = round(float(resumen_hoy['litros'] or 0), 2)
    costo_estimado_hoy = round(float(resumen_hoy['costo'] or 0), 2)

    context = {
        'cargas_pendientes_hoy': cargas_pendientes_hoy,
        'viajes_en_ruta': viajes_en_ruta,
        'litros_estimados_hoy': litros_estimados_hoy,
        'costo_estimado_hoy': costo_estimado_hoy,
        # KPI 1
        'kpi1_labels': json.dumps(kpi1_labels),
        'kpi1_data': json.dumps(kpi1_data),
        # KPI 2
        'kpi2_points': json.dumps(kpi2_points),
        # KPI 3
        'kpi3_labels': json.dumps(kpi3_labels),
        'kpi3_data': json.dumps(kpi3_data),
        # KPI 4
        'kpi4_labels': json.dumps(kpi4_labels),
        'kpi4_data': json.dumps(kpi4_data),
        # KPI 5
        'kpi5_labels': json.dumps(kpi5_labels),
        'kpi5_data': json.dumps(kpi5_data),
        # KPI 6
        'kpi6_labels': json.dumps(kpi6_labels),
        'kpi6_data': json.dumps(kpi6_data),

    }

    return render(request, "administrador/dashboard/admin_panel.html", context)


#PWA ------------------------------------------------------------------------
from django.views.generic import TemplateView

class ManifestView(TemplateView):
    template_name = "manifest.webmanifest"
    content_type = "application/manifest+json"


class ServiceWorkerView(TemplateView):
    template_name = "service-worker.js"
    content_type = "application/javascript"



from django.shortcuts import render

def offline(request):
    return render(request, "pwa/offline.html")


#seguridad -------------------------------------------------------------

from django.shortcuts import render

def tab_bloqueada(request):
    next_url = (request.GET.get("next") or "/").strip()
    if not next_url.startswith("/") or next_url.startswith("//") or next_url.startswith("/tab-bloqueada/"):
        next_url = "/"
    return render(
        request,
        "seguridad/tab_bloqueada.html",
        {"next_url": next_url},
    )
