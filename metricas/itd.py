"""Estimación de la ITD por correlación cruzada (marco teórico, «Estimación de ITD»).

1. Las HRIR izquierda y derecha se filtran paso bajo con un Butterworth de orden
   `config.ITD_ORDEN_FILTRO` y corte `config.FC_ITD`, aplicado ida y vuelta (sosfiltfilt) para
   que sea de fase cero y no añada retardo propio.
2. r[ℓ] = Σ_n h̃_L[n+ℓ]·h̃_R[n]; ℓ̂ = argmax |r[ℓ]| sobre todos los desfases.
3. Refinado sub-muestra con una parábola por |r| en ℓ̂-1, ℓ̂, ℓ̂+1:
   ε = ½·(y₋₁ − y₊₁)/(y₋₁ − 2y₀ + y₊₁);  ITD = (ℓ̂ + ε)/fs.

Convención: ITD > 0 cuando el sonido llega al oído izquierdo DESPUÉS que al derecho, es decir,
fuentes del hemicampo derecho (azimut 270°) dan valores positivos.
"""
import numpy as np
from scipy.signal import butter, sosfiltfilt

import config


def filtrar_paso_bajo(ir: np.ndarray, fs: float, fc: float = config.FC_ITD,
                      orden: int = config.ITD_ORDEN_FILTRO) -> np.ndarray:
    """Butterworth paso bajo de fase cero sobre el último eje."""
    sos = butter(orden, fc, btype="low", fs=fs, output="sos")
    return sosfiltfilt(sos, ir, axis=-1)


def interpolar_pico(y_m1: float, y_0: float, y_p1: float) -> float:
    """Desplazamiento ε del vértice de la parábola por tres puntos equiespaciados, en muestras."""
    den = y_m1 - 2.0 * y_0 + y_p1
    if den == 0.0:
        return 0.0
    return 0.5 * (y_m1 - y_p1) / den


def itd_par(h_izq: np.ndarray, h_der: np.ndarray, fs: float) -> float:
    """ITD en segundos de un par de HRIR ya filtradas (un solo par, 1-D)."""
    n = len(h_der)
    r = np.abs(np.correlate(h_izq, h_der, mode="full"))   # r[k] ↔ ℓ = k - (n-1)
    k = int(np.argmax(r))
    eps = interpolar_pico(r[k - 1], r[k], r[k + 1]) if 0 < k < len(r) - 1 else 0.0
    return (k - (n - 1) + eps) / fs


def itd(ir: np.ndarray, fs: float, fc: float = config.FC_ITD,
        orden: int = config.ITD_ORDEN_FILTRO) -> np.ndarray:
    """ITD en segundos por dirección.

    ir: (direcciones, 2, muestras), oreja 0 izquierda y 1 derecha (como en los SOFA).
    """
    ir = np.asarray(ir, dtype=float)
    f = filtrar_paso_bajo(ir, fs, fc, orden)
    return np.array([itd_par(f[i, 0], f[i, 1], fs) for i in range(f.shape[0])])


def itd_max_kuhn(aid_m: float, c: float = 343.0) -> float:
    """ITD máxima de la esfera rígida a baja frecuencia (Kuhn): 3·AID/(2c), en segundos.

    Solo como comprobación de orden de magnitud, no como predicción (ver el marco teórico).
    """
    return 3.0 * aid_m / (2.0 * c)
