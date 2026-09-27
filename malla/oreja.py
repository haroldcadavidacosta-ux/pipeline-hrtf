"""Métricas de calidad de la oreja sobre una malla alineada (canales en (0, ±AID/2, 0)).

- profundidad_concha: cuánto está el punto del canal por debajo de la envolvente convexa de
  la oreja (radio RADIO_PABELLON). Concha mal capturada -> poca profundidad.
- facetado: ángulo medio (grados) entre normales de caras vecinas en la oreja. Más alto = más
  "escalonado".
"""
import numpy as np
from scipy.spatial import ConvexHull

RADIO_PABELLON = 0.25   # AID

# Puntos del JSON de landmarks que definen el largo de cada oreja (hélix -> lóbulo),
# la misma medida que se toma con una regla en la persona para la escala.
PUNTOS_LARGO = {"izq": ("helix_izquierdo", "lobulo_izquierdo"),
                "der": ("helix_derecho", "lobulo_derecho")}


def largos(puntos):
    """Largo de cada oreja (unidades del modelo) a partir de los puntos del JSON de
    landmarks; solo las orejas que tienen marcados sus dos puntos."""
    out = {}
    for lado, (arriba, abajo) in PUNTOS_LARGO.items():
        if arriba in puntos and abajo in puntos:
            out[lado] = float(np.linalg.norm(np.subtract(puntos[arriba]["xyz"], puntos[abajo]["xyz"])))
    return out


def metricas(V, F, aid):
    out = {}
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    fn /= np.linalg.norm(fn, axis=1)[:, None] + 1e-30
    E = np.r_[F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]
    cara = np.tile(np.arange(len(F)), 3)
    clave = np.sort(E, axis=1)
    orden = np.lexsort(clave.T[::-1])
    k, c = clave[orden], cara[orden]
    par = np.flatnonzero((k[1:] == k[:-1]).all(axis=1))
    f1, f2 = c[par], c[par + 1]
    ang = np.degrees(np.arccos(np.clip(np.sum(fn[f1] * fn[f2], axis=1), -1, 1)))
    centro_cara = V[F].mean(axis=1)
    for nombre, lado in (("izq", 1), ("der", -1)):
        canal = np.array([0.0, lado * aid / 2, 0.0])
        cerca = np.linalg.norm(V - canal, axis=1) < RADIO_PABELLON * aid
        eq = ConvexHull(V[cerca]).equations
        prof = -np.max(eq[:, :3] @ canal + eq[:, 3])
        en_oreja = np.linalg.norm(centro_cara[f1] - canal, axis=1) < RADIO_PABELLON * aid
        out[nombre] = {"profundidad_concha_AID": round(float(prof / aid), 4),
                       "facetado_grados": round(float(ang[en_oreja].mean()), 2)}
    return out

