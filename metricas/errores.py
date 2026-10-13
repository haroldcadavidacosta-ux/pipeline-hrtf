"""Errores de las pistas binaurales (marco teórico, «Error de ITD e ILD»).

    e_ITD(Ω)      = ITD_sim(Ω) − ITD_ref(Ω)
    e_ILD(f_c, Ω) = ΔL_sim(f_c, Ω) − ΔL_ref(f_c, Ω)

Se resumen con el error absoluto medio y el máximo, como pide el marco, y se cuenta la fracción
de direcciones que superan el umbral perceptual. El promedio principal es sin ponderar (el del
marco); el ponderado por el área de Voronoi de cada dirección va aparte, como complemento,
porque la rejilla Default no es uniforme.
"""
import numpy as np
from scipy.spatial import SphericalVoronoi


def unitarios(pos: np.ndarray) -> np.ndarray:
    """Vectores unitarios (x adelante, y izquierda, z arriba) desde [azimut °, elevación °, r]."""
    az, el = np.radians(pos[:, 0]), np.radians(pos[:, 1])
    return np.column_stack([np.cos(el) * np.cos(az), np.cos(el) * np.sin(az), np.sin(el)])


def pesos_voronoi(pos: np.ndarray) -> np.ndarray:
    """Área de la celda de Voronoi esférica de cada dirección, normalizada a suma 1."""
    a = SphericalVoronoi(unitarios(pos), radius=1.0).calculate_areas()
    return a / a.sum()


def resumen(e: np.ndarray, umbral: float, pesos: np.ndarray | None = None) -> dict:
    """Resumen de un error por dirección (1-D). Ignora NaN."""
    e = np.asarray(e, dtype=float)
    ok = np.isfinite(e)
    a = np.abs(e[ok])
    out = {"n": int(ok.sum()),
           "media_abs": float(a.mean()),
           "max_abs": float(a.max()),
           "indice_max": int(np.flatnonzero(ok)[np.argmax(a)]),
           "sesgo": float(e[ok].mean()),
           "p95_abs": float(np.percentile(a, 95)),
           "frac_sobre_umbral": float((a > umbral).mean())}
    if pesos is not None:
        w = np.asarray(pesos)[ok]
        out["media_abs_ponderada"] = float((w * a).sum() / w.sum())
    return out
