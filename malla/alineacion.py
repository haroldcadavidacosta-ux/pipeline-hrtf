"""Alineación de una malla de cabeza por tres puntos. Solo matemática, sin interfaz.

Sistema de destino: +x adelante, +y hacia la izquierda del sujeto, +z arriba,
origen en el punto medio entre las dos entradas del canal auditivo.
"""
import numpy as np


def matriz_alineacion(p_izq, p_der, p_nariz):
    """Devuelve (T, aid): matriz homogénea 4x4 y distancia interaural.

    T lleva la malla original al sistema de destino. Se aplica a un punto p
    como T @ [p, 1].
    """
    p_izq = np.asarray(p_izq, dtype=float)
    p_der = np.asarray(p_der, dtype=float)
    p_nariz = np.asarray(p_nariz, dtype=float)

    origen = (p_izq + p_der) / 2
    v_y = p_izq - p_der
    aid = float(np.linalg.norm(v_y))
    if aid == 0:
        raise ValueError("Las dos orejas están en el mismo punto.")
    y = v_y / aid

    v = p_nariz - origen
    x = v - np.dot(v, y) * y          # quitar la componente sobre el eje interaural
    norma_x = np.linalg.norm(x)
    if norma_x == 0:
        raise ValueError("La nariz está sobre el eje interaural.")
    x = x / norma_x
    z = np.cross(x, y)                # sistema derecho

    R = np.vstack([x, y, z])
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = -R @ origen
    return T, aid


def aplicar_transformacion(T, puntos):
    """Aplica T (4x4) a un punto (3,) o a un conjunto de puntos (n, 3)."""
    p = np.asarray(puntos, dtype=float)
    R, t = T[:3, :3], T[:3, 3]
    return p @ R.T + t


def residuo_alineacion(T, p_izq, p_der, p_nariz, aid):
    """Máxima desviación respecto de la posición esperada tras aplicar T.

    Oreja izquierda → (0, +aid/2, 0); oreja derecha → (0, -aid/2, 0);
    nariz → z = 0. Debe ser prácticamente cero (orden de 1e-14).

    Nota: la nariz NO queda en y = 0, sino en y = (p_nariz - origen)·y, que es
    lo que se desvía de la mitad entre las orejas. Por construcción de x
    (se le quita la componente interaural) la nariz cae en el plano z = 0.
    """
    izq, der, nariz = aplicar_transformacion(T, [p_izq, p_der, p_nariz])
    desviaciones = [
        np.abs(izq - [0, aid / 2, 0]).max(),
        np.abs(der - [0, -aid / 2, 0]).max(),
        abs(nariz[2]),
    ]
    return float(max(desviaciones))
