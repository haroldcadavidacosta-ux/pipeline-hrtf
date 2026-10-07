"""Frecuencia máxima útil de una malla graduada, predicha de sus aristas sin simular.

Regla: el BEM necesita unos ELEMENTOS_POR_LAMBDA elementos por longitud de onda, así que una
región cuya arista típica es h deja de estar bien discretizada por encima de

    f_util = c / (ELEMENTOS_POR_LAMBDA · h)

Como arista típica se toma la mediana, sobre las caras de la región, de la arista más larga de
cada cara. Se reporta por región: la oreja (esfera alrededor del canal) y el resto de la cabeza.

Estado (2026-10-07): es la regla práctica de λ/6, no validada en este proyecto. En el barrido de -e
predice el mismo orden de las condiciones que la subida de la distorsión espectral, pero el codo
medido depende de la ventana de ajuste. La corrida -e 1 -y 5 no la falsó: la mediana predice que
afinar la cabeza no cambia la banda alta, y no la cambió; la estadística de cola (percentil 90)
predecía una mejora que no apareció, así que se mantiene la mediana
(datos/experimentos/barrido_e/fase3/y5/informe_y5.md).
"""
from pathlib import Path

import numpy as np

C_MS = 343.0
ELEMENTOS_POR_LAMBDA = 6.0
RADIO_OREJA_MM = 40.0


def arista_maxima_por_cara(vertices: np.ndarray, caras: np.ndarray) -> np.ndarray:
    v = vertices[caras]                                   # (caras, 3, 3)
    lados = np.linalg.norm(v - np.roll(v, -1, axis=1), axis=2)
    return lados.max(axis=1)


def frecuencia_util_hz(arista_mm: float, elementos: float = ELEMENTOS_POR_LAMBDA, c: float = C_MS) -> float:
    return c / (elementos * arista_mm / 1000.0)


def predecir(vertices: np.ndarray, caras: np.ndarray, canal_mm, radio_oreja_mm: float = RADIO_OREJA_MM,
             elementos: float = ELEMENTOS_POR_LAMBDA, c: float = C_MS) -> dict:
    """Aristas y frecuencia útil por región. Malla en mm, en el sistema anatómico."""
    mx = arista_maxima_por_cara(vertices, caras)
    centros = vertices[caras].mean(axis=1)
    oreja = np.linalg.norm(centros - np.asarray(canal_mm, dtype=float), axis=1) < radio_oreja_mm
    r = {"elementos_por_lambda": elementos, "c_ms": c, "radio_oreja_mm": radio_oreja_mm}
    for nombre, sel in (("oreja", oreja), ("resto_de_la_cabeza", ~oreja)):
        h = float(np.median(mx[sel]))
        r[nombre] = {"caras": int(sel.sum()), "arista_mediana_mm": h, "frecuencia_util_hz": frecuencia_util_hz(h, elementos, c)}
    r["frecuencia_util_hz"] = min(r["oreja"]["frecuencia_util_hz"], r["resto_de_la_cabeza"]["frecuencia_util_hz"])
    return r


def predecir_archivo(ruta: Path, canal_mm, **kw) -> dict:
    import trimesh
    m = trimesh.load(ruta, process=False)
    return predecir(np.asarray(m.vertices), np.asarray(m.faces), canal_mm, **kw)
