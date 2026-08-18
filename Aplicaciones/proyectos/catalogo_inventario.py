"""Catálogo controlado de inventario de agosto para los productos de carga.

Los registros provienen de la hoja ``FORMATO PRECIOS`` del archivo
``reporte inventario AGOSTO.xlsx`` entregado para el proyecto.  Se mantienen
las descripciones originales para que el administrador seleccione un producto
válido y el servidor derive automáticamente su marca y precio de referencia.
"""
from decimal import Decimal
import re

CATALOGO_INVENTARIO_AGOSTO = [
    ("AGO-003", 'Coca Cola de 3 litros Negra para $3.10', Decimal('16.0')),
    ("AGO-004", 'Coca Cola 3 Ltr. SPRITE/FIORA/FANTA para $3.10', Decimal('16.45')),
    ("AGO-005", 'Guitig 3000ml para $2,00', Decimal('10.5')),
    ("AGO-006", 'Cifrut de 3 litros para $1.80', Decimal('9.4')),
    ("AGO-007", 'Big Cola  de 3.05 litros para $1.50', Decimal('7.6')),
    ("AGO-008", 'Coca Cola de 1350 ml Negra para $1,60', Decimal('16.75')),
    ("AGO-009", 'Coca Cola 1350 ml SPRITE/ FIORA/ FANTA para $1,15', Decimal('12.35')),
    ("AGO-010", 'Coca Cola de 1000 ml Negra para $1,10', Decimal('11.7')),
    ("AGO-011", 'Guitig 1500ml para $1,00', Decimal('5.1')),
    ("AGO-012", 'Cifrut de 1700ml para $1.00', Decimal('5.1')),
    ("AGO-013", 'Pepsi / Quintuples / Tropical de 1000 ml  de $0,50', Decimal('5.1')),
    ("AGO-014", 'Tesalia Galon 6 litros para $1.75', Decimal('6.0')),
    ("AGO-015", 'Tesalia 500ml para $0.25', Decimal('2.4')),
    ("AGO-016", 'Big cola de 1.10 litros para $0,50', Decimal('5.1')),
    ("AGO-017", 'Big cola de 300 ml para $0.25', Decimal('4.95')),
    ("AGO-018", 'Cielo de valvula 1.2 litros para $0.50', Decimal('4.85')),
    ("AGO-019", 'Guitig 500ml para $0,70', Decimal('7.25')),
    ("AGO-020", 'Energizante 220V 600ml para $1.00', Decimal('9.9')),
    ("AGO-021", 'Gatorade de 750ml $1.00', Decimal('10.25')),
    ("AGO-022", 'Big cola de 2.25 litros  para $1.00', Decimal('5.1')),
    ("AGO-023", 'Pepsi / Quintuple 2000 litros para $1.00', Decimal('5.25')),
    ("AGO-024", 'Cifrut de 1 litro para $0.50', Decimal('5.1')),
    ("AGO-025", 'Energizante 220V 330ml para $0.50', Decimal('5.25')),
    ("AGO-026", 'Frut/Pep /Trop/Quint de 300 ML para $0.25', Decimal('2.6')),
    ("AGO-027", 'Sporade de 500ml para $0.50', Decimal('5.15')),
    ("AGO-028", 'Gatorade de 500 ml $0.50', Decimal('5.25')),
    ("AGO-029", 'Coca Cola de 330 ml Negra para $0,50', Decimal('5.3')),
    ("AGO-030", 'Coca Cola de 500ml Negra para $0,80', Decimal('8.5')),
    ("AGO-031", 'Power de 350 para $0.50', Decimal('5.0')),
    ("AGO-032", 'Power de 1 litro para $1.15', Decimal('5.8')),
    ("AGO-033", 'Vive 100 de 475ml para $1.00', Decimal('5.1')),
    ("AGO-034", 'Vive 100 de 300ml para $0.50', Decimal('2.6')),
    ("AGO-035", 'Saviloe de 320ml para $1.00', Decimal('5.0')),
    ("AGO-036", 'Fuzetea de 1 litro para $1.20', Decimal('6.25')),
    ("AGO-037", 'Switch de 1.5 litros para $3.00', Decimal('14.5')),
    ("AGO-038", 'Cubata de 1.5 litros para $2.98', Decimal('13.0')),
    ("AGO-039", 'Tropical / Quintuple de Galon 3.785 litros $1,99', Decimal('7.0')),
    ("AGO-040", 'Amper Energy de 473ml para$1.00', Decimal('5.1')),
    ("AGO-041", 'Pulp de145ml para $0.30', Decimal('6.1')),
    ("AGO-042", 'Pulp de 250ml para $0.40', Decimal('8.4')),
    ("AGO-043", 'Pulp de 1 litro para $1.30', Decimal('6.7')),
    ("AGO-044", 'Pulp Vidrio 285ml para $0.50', Decimal('2.5')),
    ("AGO-045", 'Tesalia 1.2 litros para $0.50', Decimal('3.7')),
    ("AGO-046", 'Cielo de 625ml para $0.35', Decimal('3.85')),
    ("AGO-047", 'Ponny Malta de 1.5 litros para $1.15', Decimal('6.5')),
    ("AGO-048", 'Ponny Malta de 330 cm para $0,50', Decimal('10.5')),
    ("AGO-049", 'Ponny Malta de 200 cm para $0,35', Decimal('7.5')),
    ("AGO-050", 'Sporade de 1.2 litros para $1.00', Decimal('5.15')),
    ("AGO-051", 'Cerveza pilsener de 1 litro para $2.25', Decimal('27.0')),
    ("AGO-052", 'Cerveza Club de 850 cm para $2.55', Decimal('27.75')),
    ("AGO-053", 'Cerveza pilsener de 600 cm para $1.50', Decimal('16.5')),
    ("AGO-055", 'Retornable Coca Cola de 2 litros para $1.50', Decimal('12.0')),
    ("AGO-056", 'Retornable Coca Cola de 1000 ml para $0,50', Decimal('5.2')),
    ("AGO-057", 'Retornable Coca Sin Azucar/Fiora/ Fanta/ Sprite 2 Ltr. Para $1,00', Decimal('8.0')),
    ("AGO-058", 'Retornable Coca Cola de 1250ml para $1,00', Decimal('8.7')),
    ("AGO-059", 'Retornable Coca Cola de 300ml para $0,30', Decimal('6.3')),
    ("AGO-060", 'Fuzetea de 550ml para $0.75', Decimal('7.3')),
    ("AGO-061", 'Jugo del Valle de 950ml para $0.50', Decimal('2.5')),
    ("AGO-062", 'Agua Dassani de 1200 ml para $0.70', Decimal('3.5')),
    ("AGO-063", 'Jugos cotopaxi 350 ml para $0,25', Decimal('5.0')),
    ("AGO-064", 'Inca Kola de 1 litro para $0.50', Decimal('5.25')),
    ("AGO-065", 'Power de 600ml para 0.75', Decimal('7.6')),
    ("AGO-066", 'Cifrut de 400ml para $0.30', Decimal('3.75')),
    ("AGO-067", 'Tesalia Botellon de $3,25', Decimal('3.25')),
    ("AGO-068", 'San Felipe Botellon de $2.50', Decimal('2.5')),
    ("AGO-069", 'San Felipe 1500ml para $1,00', Decimal('4.9')),
    ("AGO-070", 'Coca Cola de 250ml SIN AZUCAR para $0.25', Decimal('2.65')),
    ("AGO-071", 'Coca cola sabores 300ml para $0,30', Decimal('3.2')),
    ("AGO-072", 'Cielo saborizada  2000 ml para $1,00', Decimal('5.0')),
    ("AGO-073", 'Cielo saborizada  600 ml para $0,35', Decimal('1.75')),
    ("AGO-074", 'Coca cola original de 2000 ml para  $2,00', Decimal('10.5')),
    ("AGO-075", 'Coca cola sabores Sprite/Fiora /Fanta 500 ml $0,50', Decimal('5.3')),
    ("AGO-076", 'Guitig de 355 ml para  $0,50', Decimal('5.0')),
    ("AGO-077", 'Coca cola sin azucar 500 ml para $0,40', Decimal('4.3')),
    ("AGO-078", 'Pepsi cola 3000 ml para $1.50', Decimal('7.5')),
    ("AGO-079", 'Coca cola sin azucar de 1800ml para $1.00', Decimal('5.3')),
]


def _marca_desde_descripcion(descripcion):
    texto = (descripcion or "").lower()
    reglas = [
        (("coca cola", "coca sin", "coca cola"), "Coca-Cola"),
        (("guitig",), "Güitig"),
        (("cifrut",), "Cifrut"),
        (("big cola",), "Big Cola"),
        (("pepsi", "quintuple", "quintuples", "tropical"), "Pepsi / Tropical / Quintuple"),
        (("tesalia",), "Tesalia"),
        (("cielo",), "Cielo"),
        (("220v",), "220V"),
        (("gatorade",), "Gatorade"),
        (("sporade",), "Sporade"),
        (("power",), "Power"),
        (("vive 100",), "Vive 100"),
        (("saviloe",), "Saviloe"),
        (("fuzetea",), "Fuze Tea"),
        (("switch",), "Switch"),
        (("cubata",), "Cubata"),
        (("amper energy",), "Amper Energy"),
        (("pulp",), "Pulp"),
        (("ponny malta", "pony malta"), "Pony Malta"),
        (("pilsener",), "Pilsener"),
        (("cerveza club",), "Club"),
        (("jugo del valle",), "Del Valle"),
        (("dassani", "dasani"), "Dasani"),
        (("jugos cotopaxi",), "Jugos Cotopaxi"),
        (("inca kola",), "Inca Kola"),
        (("san felipe",), "San Felipe"),
        (("frut/pep",), "Frut / Pepsi / Tropical / Quintuple"),
    ]
    for palabras, marca in reglas:
        if any(palabra in texto for palabra in palabras):
            return marca
    return "Marca definida por catálogo"


def _nombre_limpio(descripcion):
    # La descripción completa se conserva como nombre para no inventar datos del Excel.
    return (descripcion or "").strip()



def _contenido_desde_descripcion(descripcion):
    """Obtiene el contenido de UNA unidad cuando la descripción lo indica.

    Se conserva la unidad original (ml o L) para que el formulario resulte
    natural al administrador. Si la fuente no informa el contenido, no se
    inventa un valor y el usuario deberá completarlo.
    """
    texto = (descripcion or "").lower().replace(",", ".")

    patrones = [
        (r"(\d+(?:\.\d+)?)\s*(?:litros?|ltr\.?|l\b)", "L"),
        (r"(\d+(?:\.\d+)?)\s*(?:ml|cm\b)", "ML"),
    ]

    for patron, unidad in patrones:
        coincidencia = re.search(patron, texto, flags=re.I)
        if not coincidencia:
            continue

        valor = Decimal(coincidencia.group(1))

        # En la fuente AGO-023 aparece "2000 litros", pero el producto y
        # precio corresponden a una presentación de 2000 ml. Se conserva la
        # corrección que ya manejaba el proyecto.
        if unidad == "L" and valor > Decimal("50"):
            return valor, "ML"

        return valor, unidad

    # Algunas descripciones, como "Power de 350", omiten explícitamente ml.
    coincidencia = re.search(r"\bde\s+(\d{2,4})\b", texto)
    if coincidencia:
        valor = Decimal(coincidencia.group(1))
        if valor >= Decimal("100"):
            return valor, "ML"

    return None, ""


def contenido_a_kg(contenido, unidad):
    """Convierte contenido por unidad a kg para planificación de carga.

    En bebidas se usa la equivalencia operativa 1 L ≈ 1 kg. No pretende
    sustituir un dato de densidad del fabricante; sirve para la estimación de
    carga que utiliza el sistema.
    """
    if contenido in (None, ""):
        return None

    valor = Decimal(str(contenido))
    unidad = (unidad or "").upper()

    factores = {
        "ML": Decimal("0.001"),
        "L": Decimal("1"),
        "G": Decimal("0.001"),
        "KG": Decimal("1"),
    }

    factor = factores.get(unidad)
    if factor is None:
        return None

    return valor * factor


# Solo se usa como sugerencia inicial. El administrador puede indicar la
# cantidad real de unidades que contiene una caja, paquete o jaba.
UNIDADES_SUGERIDAS_PRESENTACION = {
    "UNIDAD": 1,
    "BOTELLA": 1,
    "GALON": 1,
    "PAQUETE": 6,
    "CAJA": 12,
    "JABA": 12,
}


def peso_estimado_presentacion(item_catalogo, presentacion, unidades=None):
    """Calcula el peso estimado de una presentación del catálogo."""
    if not item_catalogo:
        return None

    contenido = item_catalogo.get("contenido_unitario")
    unidad = item_catalogo.get("unidad_contenido")
    peso_unidad_kg = contenido_a_kg(contenido, unidad)
    if peso_unidad_kg is None:
        return None

    cantidad = unidades
    if cantidad in (None, ""):
        cantidad = UNIDADES_SUGERIDAS_PRESENTACION.get(
            (presentacion or "").upper(),
            1,
        )

    return (peso_unidad_kg * Decimal(str(cantidad))).quantize(Decimal("0.01"))


def catalogo_productos():
    productos = []

    for codigo, descripcion, precio in CATALOGO_INVENTARIO_AGOSTO:
        contenido, unidad = _contenido_desde_descripcion(descripcion)
        productos.append(
            {
                "codigo": codigo,
                "descripcion": descripcion,
                "nombre": _nombre_limpio(descripcion),
                "marca": _marca_desde_descripcion(descripcion),
                "precio_referencia": precio,
                "contenido_unitario": contenido,
                "unidad_contenido": unidad,
                # Se conservan estas claves por compatibilidad con cualquier
                # parte antigua del proyecto que todavía las consulte.
                "volumen_litros_estimado": (
                    contenido_a_kg(contenido, unidad)
                    if unidad in ("ML", "L")
                    else None
                ),
                "peso_base_kg": contenido_a_kg(contenido, unidad),
            }
        )

    return productos


def producto_catalogo_por_codigo(codigo):
    codigo = (codigo or "").strip().upper()
    for producto in catalogo_productos():
        if producto["codigo"] == codigo:
            return producto
    return None


def codigo_catalogo_por_nombre(nombre):
    objetivo = (nombre or "").strip().casefold()
    for producto in catalogo_productos():
        if producto["nombre"].casefold() == objetivo:
            return producto["codigo"]
    return ""


def marcas_catalogo():
    """Devuelve las marcas disponibles sin duplicados para separar la selección."""
    marcas = {
        producto["marca"]
        for producto in catalogo_productos()
        if producto.get("marca")
    }
    return sorted(marcas, key=lambda valor: valor.casefold())
