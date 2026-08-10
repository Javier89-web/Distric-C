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



def _volumen_litros_estimado(descripcion):
    """Estima el contenido de una unidad física a partir de la descripción del catálogo.

    Es una ayuda inicial para calcular carga. El administrador puede corregir el peso
    antes de guardar el producto.
    """
    texto = (descripcion or "").lower().replace(",", ".")

    # Botellones comerciales de agua suelen estar alrededor de 20 L.
    if "botellon" in texto or "botellón" in texto:
        return Decimal("20.0")

    patrones = [
        (r"(\d+(?:\.\d+)?)\s*(?:litros?|ltr\.?|l\b)", Decimal("1")),
        (r"(\d+(?:\.\d+)?)\s*(?:ml|cm\b)", Decimal("0.001")),
    ]
    for patron, factor in patrones:
        m = re.search(patron, texto, flags=re.I)
        if m:
            valor = Decimal(m.group(1)) * factor
            # El registro AGO-023 dice "2000 litros" en la fuente, pero por su
            # presentación/precio corresponde razonablemente a 2000 ml.
            if factor == Decimal("1") and valor > Decimal("50"):
                valor = valor / Decimal("1000")
            return max(valor, Decimal("0.10"))

    # Descripciones como "Power de 350" omiten ml.
    m = re.search(r"\bde\s+(\d{2,4})\b", texto)
    if m:
        valor = Decimal(m.group(1))
        if valor >= Decimal("100"):
            return valor / Decimal("1000")

    return Decimal("1.0")


def _peso_base_estimado(descripcion):
    """Peso aproximado de una unidad individual, incluyendo envase básico."""
    volumen = _volumen_litros_estimado(descripcion)
    # Para bebidas, 1 L ≈ 1 kg. Agregamos un pequeño margen de envase.
    empaque = Decimal("0.03") if volumen <= Decimal("2") else Decimal("0.08")
    return (volumen + empaque).quantize(Decimal("0.01"))


MULTIPLICADOR_PRESENTACION = {
    "UNIDAD": Decimal("1"),
    "BOTELLA": Decimal("1"),
    "GALON": Decimal("1"),
    "FUNDA": Decimal("6"),
    "PAQUETE": Decimal("6"),
    "CAJA": Decimal("12"),
    "JABA": Decimal("12"),
}


def peso_estimado_presentacion(item_catalogo, presentacion):
    if not item_catalogo:
        return None
    base = Decimal(str(item_catalogo.get("peso_base_kg") or "1"))
    multiplicador = MULTIPLICADOR_PRESENTACION.get((presentacion or "").upper(), Decimal("1"))
    return (base * multiplicador).quantize(Decimal("0.01"))

def catalogo_productos():
    return [
        {
            "codigo": codigo,
            "descripcion": descripcion,
            "nombre": _nombre_limpio(descripcion),
            "marca": _marca_desde_descripcion(descripcion),
            "precio_referencia": precio,
            "volumen_litros_estimado": _volumen_litros_estimado(descripcion),
            "peso_base_kg": _peso_base_estimado(descripcion),
        }
        for codigo, descripcion, precio in CATALOGO_INVENTARIO_AGOSTO
    ]


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
