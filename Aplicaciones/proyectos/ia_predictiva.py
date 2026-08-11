"""Capa de inteligencia artificial predictiva para consumo de combustible.

El modelo principal es RandomForestRegressor. La predicción se integra con
Dijkstra: el consumo predicho de cada arista se transforma en un costo dinámico
y el algoritmo de grafos busca la combinación de menor costo total.

El conjunto inicial incluido es simulado y controlado. Cuando existan datos
reales, el comando ``entrenar_modelo_consumo`` permite reemplazarlo por un CSV
con viajes medidos sin cambiar las vistas ni el algoritmo de rutas.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from django.utils import timezone

try:
    import joblib
    import numpy as np
    import pandas as pd
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    from sklearn.model_selection import train_test_split
except Exception:  # pragma: no cover - respaldo si falta una dependencia
    joblib = None
    np = None
    pd = None
    RandomForestRegressor = None


APP_DIR = Path(__file__).resolve().parent
DATOS_DIR = APP_DIR / "ml" / "datos"
MODELOS_DIR = APP_DIR / "ml" / "modelos"
DATASET_INICIAL = DATOS_DIR / "consumo_entrenamiento_inicial.csv"
MODELO_PATH = MODELOS_DIR / "random_forest_consumo.joblib"
METADATA_PATH = MODELOS_DIR / "random_forest_consumo_metadata.json"

MODELO_NOMBRE = "Random Forest Regressor híbrido v1"
MODELO_VERSION = "rf-consumo-1.0"

FEATURES = [
    "distancia_km",
    "tiempo_min",
    "velocidad_kmh",
    "carga_kg",
    "peso_vehiculo_kg",
    "capacidad_kg",
    "cilindraje_l",
    "rendimiento_km_l",
    "factor_trafico",
    "factor_clima",
    "hora_sin",
    "hora_cos",
    "tipo_via_codigo",
    "detenciones_estimadas",
    "pendiente_pct",
    "consumo_base_l",
]

TIPO_VIA_CODIGO = {
    "PRINCIPAL": 0,
    "RURAL": 1,
    "URBANA": 2,
    "SECUNDARIA": 3,
    "": 2,
    None: 2,
}

_BUNDLE: dict[str, Any] | None = None


@dataclass
class PrediccionTramo:
    consumo_base_l: float
    consumo_predicho_l: float
    costo_dijkstra: float
    detalle: dict[str, Any]


def _numero(valor: Any, defecto: float = 0.0) -> float:
    try:
        if valor is None:
            return defecto
        return float(valor)
    except (TypeError, ValueError):
        return defecto


def _peso_vehiculo_kg(vehiculo: Any) -> float:
    peso_ton = _numero(getattr(vehiculo, "peso_auto", 0), 0)
    return max(peso_ton * 1000.0, 0.0)


def _cilindraje(vehiculo: Any) -> float:
    return max(_numero(getattr(vehiculo, "cilindraje", 0), 0), 0.0)


def _hora_codificada(fecha_hora=None) -> tuple[float, float, int]:
    actual = fecha_hora or timezone.localtime()
    hora = int(actual.hour)
    angulo = 2 * math.pi * hora / 24.0
    return math.sin(angulo), math.cos(angulo), hora


def _velocidad(distancia_km: float, tiempo_min: float) -> float:
    if tiempo_min <= 0:
        return 0.0
    return max((distancia_km / tiempo_min) * 60.0, 0.0)


def _consumo_base(distancia_km: float, rendimiento_km_l: float) -> float:
    if rendimiento_km_l <= 0:
        return 0.0
    return max(distancia_km / rendimiento_km_l, 0.0)


def _registro_features(
    *,
    distancia_km: float,
    tiempo_min: float,
    carga_kg: float,
    peso_vehiculo_kg: float,
    capacidad_kg: float,
    cilindraje_l: float,
    rendimiento_km_l: float,
    factor_trafico: float,
    factor_clima: float,
    tipo_via: str | None = "URBANA",
    detenciones_estimadas: int | float = 0,
    pendiente_pct: float = 0.0,
    fecha_hora=None,
) -> dict[str, float]:
    distancia_km = max(_numero(distancia_km), 0.001)
    tiempo_min = max(_numero(tiempo_min), 0.01)
    rendimiento_km_l = max(_numero(rendimiento_km_l), 0.1)
    factor_trafico = min(max(_numero(factor_trafico, 1.0), 0.90), 1.90)
    factor_clima = min(max(_numero(factor_clima, 1.0), 0.90), 1.25)
    hora_sin, hora_cos, _ = _hora_codificada(fecha_hora)
    consumo_base = _consumo_base(distancia_km, rendimiento_km_l)

    return {
        "distancia_km": distancia_km,
        "tiempo_min": tiempo_min,
        "velocidad_kmh": _velocidad(distancia_km, tiempo_min),
        "carga_kg": max(_numero(carga_kg), 0.0),
        "peso_vehiculo_kg": max(_numero(peso_vehiculo_kg), 0.0),
        "capacidad_kg": max(_numero(capacidad_kg), 1.0),
        "cilindraje_l": max(_numero(cilindraje_l), 0.0),
        "rendimiento_km_l": rendimiento_km_l,
        "factor_trafico": factor_trafico,
        "factor_clima": factor_clima,
        "hora_sin": hora_sin,
        "hora_cos": hora_cos,
        "tipo_via_codigo": float(TIPO_VIA_CODIGO.get(tipo_via, 2)),
        "detenciones_estimadas": max(_numero(detenciones_estimadas), 0.0),
        "pendiente_pct": max(_numero(pendiente_pct), 0.0),
        "consumo_base_l": consumo_base,
    }


def entrenar_modelo_consumo(
    dataset_path: str | Path | None = None,
    guardar: bool = True,
) -> dict[str, Any]:
    """Entrena Random Forest con un CSV y devuelve modelo + métricas."""
    if RandomForestRegressor is None or pd is None or np is None or joblib is None:
        raise RuntimeError(
            "Faltan dependencias de IA. Instala scikit-learn, pandas, numpy y joblib."
        )

    ruta = Path(dataset_path) if dataset_path else DATASET_INICIAL
    if not ruta.exists():
        raise FileNotFoundError(f"No existe el dataset de entrenamiento: {ruta}")

    datos = pd.read_csv(ruta)
    faltantes = [columna for columna in FEATURES + ["consumo_real_l"] if columna not in datos.columns]
    if faltantes:
        raise ValueError(f"El CSV no contiene estas columnas: {', '.join(faltantes)}")

    datos = datos.dropna(subset=FEATURES + ["consumo_real_l"]).copy()
    if len(datos) < 80:
        raise ValueError("Se necesitan al menos 80 registros válidos para entrenar el modelo.")

    x = datos[FEATURES].astype(float)
    y = datos["consumo_real_l"].astype(float)

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.20,
        random_state=42,
    )

    modelo = RandomForestRegressor(
        n_estimators=220,
        max_depth=16,
        min_samples_leaf=2,
        max_features=0.85,
        random_state=42,
        n_jobs=-1,
    )
    modelo.fit(x_train, y_train)
    estimado = modelo.predict(x_test)

    metricas = {
        "mae_litros": round(float(mean_absolute_error(y_test, estimado)), 5),
        "rmse_litros": round(float(math.sqrt(mean_squared_error(y_test, estimado))), 5),
        "r2": round(float(r2_score(y_test, estimado)), 5),
        "registros": int(len(datos)),
        "registros_entrenamiento": int(len(x_train)),
        "registros_prueba": int(len(x_test)),
    }

    importancias = sorted(
        [
            {"variable": variable, "importancia": round(float(valor), 6)}
            for variable, valor in zip(FEATURES, modelo.feature_importances_)
        ],
        key=lambda item: item["importancia"],
        reverse=True,
    )

    fuente = (
        "DATOS_REALES"
        if "fuente" in datos.columns and datos["fuente"].astype(str).str.contains("REAL").any()
        else "SIMULADO_CONTROLADO"
    )

    metadata = {
        "nombre": MODELO_NOMBRE,
        "version": MODELO_VERSION,
        "algoritmo": "RandomForestRegressor",
        "tipo_ia": "IA predictiva - aprendizaje supervisado - regresión",
        "entrenado_en": datetime.utcnow().isoformat() + "Z",
        "dataset": str(ruta.name),
        "fuente_datos": fuente,
        "features": FEATURES,
        "metricas": metricas,
        "importancias": importancias,
        "advertencia": (
            "El conjunto inicial es simulado y controlado. Debe reemplazarse o "
            "complementarse con consumos reales para la validación final de la tesis."
        ),
    }

    bundle = {"modelo": modelo, "metadata": metadata, "features": FEATURES}

    if guardar:
        MODELOS_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(bundle, MODELO_PATH)
        METADATA_PATH.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    global _BUNDLE
    _BUNDLE = bundle
    return bundle


def asegurar_modelo_entrenado(forzar: bool = False) -> dict[str, Any] | None:
    global _BUNDLE

    if _BUNDLE is not None and not forzar:
        return _BUNDLE

    if joblib is None:
        return None

    if MODELO_PATH.exists() and not forzar:
        try:
            bundle = joblib.load(MODELO_PATH)
            if bundle.get("features") == FEATURES:
                _BUNDLE = bundle
                return bundle
        except Exception:
            pass

    try:
        return entrenar_modelo_consumo(guardar=True)
    except Exception:
        return None


def _prediccion_formula_respaldo(features: dict[str, float]) -> float:
    """Respaldo conservador si scikit-learn no está disponible."""
    carga_ratio = features["carga_kg"] / max(features["capacidad_kg"], 1.0)
    factor = (
        features["factor_trafico"]
        * features["factor_clima"]
        * (1.0 + min(max(carga_ratio, 0.0), 1.5) * 0.20)
        * (1.0 + min(features["detenciones_estimadas"], 20.0) * 0.006)
        * (1.0 + min(features["pendiente_pct"], 12.0) * 0.009)
    )
    return max(features["consumo_base_l"] * factor, 0.001)


def predecir_registro(features: dict[str, float]) -> tuple[float, dict[str, Any]]:
    bundle = asegurar_modelo_entrenado()

    if bundle is not None and pd is not None:
        frame = pd.DataFrame([[features[c] for c in FEATURES]], columns=FEATURES)
        prediccion = max(float(bundle["modelo"].predict(frame)[0]), 0.001)
        metadata = bundle.get("metadata", {})
        detalle = {
            "modelo": metadata.get("nombre", MODELO_NOMBRE),
            "version": metadata.get("version", MODELO_VERSION),
            "fuente_datos": metadata.get("fuente_datos", "DESCONOCIDA"),
            "metricas": metadata.get("metricas", {}),
            "importancias": metadata.get("importancias", [])[:6],
            "modo": "RANDOM_FOREST",
        }
        return prediccion, detalle

    return _prediccion_formula_respaldo(features), {
        "modelo": "Fórmula de respaldo",
        "version": "fallback-1.0",
        "fuente_datos": "SIN_MODELO",
        "metricas": {},
        "importancias": [],
        "modo": "RESPALDO_MATEMATICO",
    }


def predecir_consumo_combustible(
    distancia_km,
    tiempo_min,
    consumo_base=None,
    consumo_ajustado_peso=None,
    factor_peso=1.0,
    factores_google=None,
    *,
    carga_kg=0.0,
    peso_vehiculo_kg=0.0,
    capacidad_kg=1.0,
    cilindraje_l=0.0,
    rendimiento_km_l=None,
    tipo_via="URBANA",
    detenciones_estimadas=0,
    pendiente_pct=0.0,
    fecha_hora=None,
):
    """Predice litros consumidos y conserva compatibilidad con la firma anterior."""
    factores_google = factores_google or {}
    trafico = factores_google.get("trafico", {}) or {}
    clima = factores_google.get("clima", {}) or {}

    if rendimiento_km_l is None:
        if consumo_base and _numero(consumo_base) > 0:
            rendimiento_km_l = _numero(distancia_km) / _numero(consumo_base)
        else:
            rendimiento_km_l = 10.0

    features = _registro_features(
        distancia_km=_numero(distancia_km),
        tiempo_min=_numero(tiempo_min),
        carga_kg=_numero(carga_kg),
        peso_vehiculo_kg=_numero(peso_vehiculo_kg),
        capacidad_kg=max(_numero(capacidad_kg, 1.0), 1.0),
        cilindraje_l=_numero(cilindraje_l),
        rendimiento_km_l=max(_numero(rendimiento_km_l, 10.0), 0.1),
        factor_trafico=_numero(trafico.get("factor_trafico"), 1.0),
        factor_clima=_numero(clima.get("factor_clima"), 1.0),
        tipo_via=tipo_via,
        detenciones_estimadas=detenciones_estimadas,
        pendiente_pct=pendiente_pct,
        fecha_hora=fecha_hora,
    )

    predicho, detalle_modelo = predecir_registro(features)
    base = features["consumo_base_l"]
    incremento = predicho - base
    porcentaje = (incremento / base * 100.0) if base > 0 else 0.0

    if porcentaje >= 35:
        riesgo = "ALTO"
    elif porcentaje >= 15:
        riesgo = "MEDIO"
    else:
        riesgo = "BAJO"

    _, _, hora = _hora_codificada(fecha_hora)

    return {
        "consumo_base_litros": round(base, 3),
        "consumo_referencia_litros": round(_numero(consumo_ajustado_peso, base), 3),
        "consumo_predicho_litros": round(predicho, 3),
        "incremento_litros": round(incremento, 3),
        "porcentaje_incremento": round(porcentaje, 2),
        "factor_peso": round(_numero(factor_peso, 1.0), 2),
        "factor_trafico": round(features["factor_trafico"], 2),
        "factor_clima": round(features["factor_clima"], 2),
        "descripcion_horario": f"hora local {hora:02d}:00",
        "riesgo": riesgo,
        "trafico": trafico,
        "clima": clima,
        "features": {clave: round(float(valor), 5) for clave, valor in features.items()},
        "modelo": detalle_modelo,
        "resumen": (
            "Random Forest estima el consumo a partir de distancia, tiempo, carga, "
            "vehículo, tráfico, clima, horario, tipo de vía, detenciones y pendiente topográfica."
        ),
    }


def predecir_costos_tramos(
    tramos: Iterable[Any],
    *,
    vehiculo: Any,
    carga_kg: float,
    capacidad_kg: float,
    rendimiento_km_l: float,
    factores_google: dict[str, Any] | None = None,
    fecha_hora=None,
) -> dict[tuple[int, int], PrediccionTramo]:
    """Predice en lote cada arista y genera el peso dinámico para Dijkstra."""
    factores_google = factores_google or {}
    trafico = factores_google.get("trafico", {}) or {}
    clima = factores_google.get("clima", {}) or {}
    factor_trafico = _numero(trafico.get("factor_trafico"), 1.0)
    factor_clima = _numero(clima.get("factor_clima"), 1.0)
    peso_vehiculo = _peso_vehiculo_kg(vehiculo)
    cilindraje = _cilindraje(vehiculo)

    registros = []
    claves = []
    bases = []

    for tramo in tramos:
        distancia = max(_numero(getattr(tramo, "distancia_km", 0)), 0.001)
        tiempo_base = max(_numero(getattr(tramo, "tiempo_base_min", 0)), 0.01)
        tiempo = tiempo_base * max(factor_trafico, 1.0)
        tipo_via = getattr(tramo, "tipo_via", "URBANA") or "URBANA"
        detenciones = max(1, round(distancia * (1.7 if tipo_via in {"URBANA", "SECUNDARIA"} else 0.7)))
        features = _registro_features(
            distancia_km=distancia,
            tiempo_min=tiempo,
            carga_kg=carga_kg,
            peso_vehiculo_kg=peso_vehiculo,
            capacidad_kg=capacidad_kg,
            cilindraje_l=cilindraje,
            rendimiento_km_l=rendimiento_km_l,
            factor_trafico=factor_trafico,
            factor_clima=factor_clima,
            tipo_via=tipo_via,
            detenciones_estimadas=detenciones,
            pendiente_pct=0.0,
            fecha_hora=fecha_hora,
        )
        claves.append((int(tramo.origen_id), int(tramo.destino_id)))
        registros.append(features)
        bases.append(features["consumo_base_l"])

    bundle = asegurar_modelo_entrenado()
    predicciones = None
    metadata = {
        "modelo": "Fórmula de respaldo",
        "version": "fallback-1.0",
        "fuente_datos": "SIN_MODELO",
        "modo": "RESPALDO_MATEMATICO",
    }

    if bundle is not None and pd is not None and registros:
        frame = pd.DataFrame(
            [[registro[c] for c in FEATURES] for registro in registros],
            columns=FEATURES,
        )
        predicciones = bundle["modelo"].predict(frame)
        model_meta = bundle.get("metadata", {})
        metadata = {
            "modelo": model_meta.get("nombre", MODELO_NOMBRE),
            "version": model_meta.get("version", MODELO_VERSION),
            "fuente_datos": model_meta.get("fuente_datos", "DESCONOCIDA"),
            "metricas": model_meta.get("metricas", {}),
            "modo": "RANDOM_FOREST",
        }

    resultado: dict[tuple[int, int], PrediccionTramo] = {}

    for indice, clave in enumerate(claves):
        features = registros[indice]
        predicho = (
            max(float(predicciones[indice]), 0.001)
            if predicciones is not None
            else _prediccion_formula_respaldo(features)
        )
        tiempo = features["tiempo_min"]

        # Conversión a un costo común: 65 % combustible y 35 % tiempo.
        # Un litro se expresa como 60 unidades equivalentes para que la escala
        # no quede anulada por los minutos de recorrido.
        costo_dijkstra = (predicho * 60.0 * 0.65) + (tiempo * 0.35)

        resultado[clave] = PrediccionTramo(
            consumo_base_l=bases[indice],
            consumo_predicho_l=predicho,
            costo_dijkstra=max(costo_dijkstra, 0.0001),
            detalle={
                **metadata,
                "features": {k: round(float(v), 5) for k, v in features.items()},
            },
        )

    return resultado


def resumen_modelo() -> dict[str, Any]:
    bundle = asegurar_modelo_entrenado()
    if bundle:
        return bundle.get("metadata", {})
    return {
        "nombre": "Fórmula de respaldo",
        "version": "fallback-1.0",
        "fuente_datos": "SIN_MODELO",
        "metricas": {},
    }
