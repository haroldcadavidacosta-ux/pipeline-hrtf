"""Distorsión espectral por dirección (marco teórico, «Distorsión espectral»).

    SD(Ω) = sqrt( (1/|F|) · Σ_{f∈F} ( 20·log10 |H_ref(f,Ω)| / |H(f,Ω)| )² )   [dB]

con F las líneas espectrales de la banda evaluada. Se calcula por dirección y por oreja; el
promedio sobre direcciones se da sin ponderar (el del marco) y ponderado por el área de
Voronoi de cada dirección (la rejilla no es uniforme).
"""
import numpy as np

# Bandas del barrido: la de la pina decide; la alta indica el ancho de banda útil
BANDAS_SD_HZ = {"4-11": (4000.0, 11000.0), "12-16": (12000.0, 16000.0)}


def magnitud_db(H: np.ndarray) -> np.ndarray:
    return 20.0 * np.log10(np.abs(H))


def sd_direccion(db_ref: np.ndarray, db: np.ndarray, f: np.ndarray, banda: tuple) -> np.ndarray:
    """SD por dirección y oreja: (direcciones, orejas). db_*: (direcciones, orejas, frecuencias)."""
    sel = (f >= banda[0]) & (f <= banda[1])
    D = db_ref[..., sel] - db[..., sel]
    return np.sqrt((D ** 2).mean(axis=-1))


def promedios(sd: np.ndarray, pesos: np.ndarray) -> dict:
    """Media sobre direcciones (y las dos orejas): sin ponderar y ponderada por área."""
    return {"media": float(sd.mean()),
            "media_ponderada": float((pesos[:, None] * sd).sum() / (pesos.sum() * sd.shape[1]))}
