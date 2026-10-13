"""ILD por banda de tercio de octava (marco teórico, «Estimación de ILD»).

    ΔL_1/3(f_c, Ω) = 20·log10 sqrt( Σ_{f∈B(f_c)} |H_L|² / Σ_{f∈B(f_c)} |H_R|² )   [dB]

con B(f_c) las líneas espectrales en f_c·2^(-1/6) ≤ f < f_c·2^(1/6). Centros exactos en base 2
alrededor de 1 kHz (f_c = 1000·2^(k/3)), rotulados con su valor nominal de la IEC 61260.
Convención: ΔL > 0 cuando el nivel es mayor en el oído izquierdo.
"""
import numpy as np

import config

# Centros nominales de tercio de octava (IEC 61260) y su índice k respecto de 1 kHz
NOMINALES_HZ = [25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800,
                1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500,
                16000, 20000]
_K_1KHZ = NOMINALES_HZ.index(1000)


def bandas(f_min: float = config.ILD_BANDAS_HZ[0],
           f_max: float = config.ILD_BANDAS_HZ[1]) -> list[dict]:
    """Bandas con centro nominal entre f_min y f_max: nominal, centro exacto y bordes."""
    out = []
    for i, nom in enumerate(NOMINALES_HZ):
        if f_min <= nom <= f_max:
            fc = 1000.0 * 2.0 ** ((i - _K_1KHZ) / 3.0)
            out.append({"nominal": float(nom), "fc": fc,
                        "inf": fc * 2.0 ** (-1 / 6), "sup": fc * 2.0 ** (1 / 6)})
    return out


def lineas_por_banda(f: np.ndarray, bs: list[dict]) -> np.ndarray:
    """Número de líneas espectrales de f que caen en cada banda."""
    return np.array([np.count_nonzero((f >= b["inf"]) & (f < b["sup"])) for b in bs])


def ild_bandas(H: np.ndarray, f: np.ndarray, bs: list[dict] | None = None) -> np.ndarray:
    """ILD en dB por dirección y banda: (direcciones, bandas). NaN en bandas sin líneas.

    H: (direcciones, 2, frecuencias) complejo, oreja 0 izquierda y 1 derecha.
    """
    if bs is None:
        bs = bandas()
    P = np.abs(np.asarray(H)) ** 2
    out = np.full((P.shape[0], len(bs)), np.nan)
    for j, b in enumerate(bs):
        sel = (f >= b["inf"]) & (f < b["sup"])
        if sel.any():
            out[:, j] = 10.0 * np.log10(P[:, 0, sel].sum(axis=-1) / P[:, 1, sel].sum(axis=-1))
    return out
