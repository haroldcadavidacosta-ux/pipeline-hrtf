"""Render sombreado de una o varias mallas (ya alineadas) desde 6 ángulos.

Encuadra solo la cabeza: lo que está por encima del origen interaural menos `--bajo`.
Uso: vista_previa.py SALIDA.png MALLA1.ply [MALLA2.ply ...]
"""
import sys

import numpy as np
import pyvista as pv

VISTAS = {"frente": (1, 0, 0.15), "atrás": (-1, 0, 0.3), "izquierda": (0, 1, 0.15),
          "derecha": (0, -1, 0.15), "arriba": (0.25, 0, 1), "atrás-izq": (-0.7, 0.7, 0.35)}
salida, mallas = sys.argv[1], sys.argv[2:]
pl = pv.Plotter(off_screen=True, shape=(len(mallas), len(VISTAS)),
                window_size=(330 * len(VISTAS), 380 * len(mallas)))
for i, ruta in enumerate(mallas):
    m = pv.read(ruta)
    z = m.points[:, 2]
    cabeza = m.points[z > z.max() - 0.55 * np.ptp(m.points[:, 1])]   # franja superior ≈ la cabeza
    c = cabeza.mean(axis=0)
    r = np.linalg.norm(cabeza - c, axis=1).max()
    for j, (nombre, d) in enumerate(VISTAS.items()):
        pl.subplot(i, j)
        pl.add_mesh(m, color="lightgray", smooth_shading=True, specular=0.3)
        pl.add_text(f"{ruta.replace(chr(92), '/').split('/')[-1]} - {nombre}", font_size=7)
        d = np.array(d) / np.linalg.norm(d)
        arriba = (1, 0, 0) if nombre == "arriba" else (0, 0, 1)
        pl.camera_position = [tuple(c + 3.2 * r * d), tuple(c), arriba]
pl.screenshot(salida)
