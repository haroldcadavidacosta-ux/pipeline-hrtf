"""Barrido de -e, fase 1: renders de la oreja izquierda en alambre, uno por -e, con el mismo
ángulo y la misma escala (proyección paralela, encuadre fijo en mm alrededor del canal).

Uso:  .venv/Scripts/python.exe experimentos/barrido_e/fase1_renders.py <carpeta del barrido> "<nombre>"
Escribe fase1/orejas_alambre.png (la original y los cuatro -e, con rótulos) y cada panel suelto.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pyvista as pv
from PIL import Image, ImageDraw, ImageFont

VALORES_E = ("0.5", "0.7", "1", "2", "3")
MEDIA_ALTURA_MM = 48.0                     # encuadre: 96 mm de alto en todas las vistas
DESDE_CANAL = np.array([-6.0, 0.0, 12.0])  # el centro de la oreja queda algo detrás y encima del canal
ANCHO, ALTO = 760, 900                     # píxeles de cada panel


def camara(plotter, canal):
    centro = canal + DESDE_CANAL
    plotter.camera_position = [tuple(centro + [0, 400, 0]), tuple(centro), (0, 0, 1)]
    plotter.camera.parallel_projection = True
    plotter.camera.parallel_scale = MEDIA_ALTURA_MM


def panel(malla: pv.PolyData, canal, destino: Path, alambre: bool) -> Image.Image:
    p = pv.Plotter(off_screen=True, window_size=(ANCHO, ALTO))
    p.set_background("white")
    if alambre:
        p.add_mesh(malla, color="#dedede", show_edges=True, edge_color="#2b2b2b", line_width=0.6)
    else:
        p.add_mesh(malla, color="#dedede", smooth_shading=True)
    camara(p, canal)
    p.screenshot(destino)
    return Image.open(destino)


def miles(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def principal() -> None:
    carpeta, nombre = Path(sys.argv[1]), sys.argv[2]
    aid = json.loads((carpeta / "informe_limpieza.json").read_text(encoding="utf-8"))["escala"]["aid_mm"]
    canal = np.array([0.0, aid / 2, 0.0])
    geo = json.loads((carpeta / "fase1" / "geometria.json").read_text(encoding="utf-8"))["e"]
    salida = carpeta / "fase1"

    paneles = [(panel(pv.read(carpeta / "3Dmesh_orig.stl"), canal, salida / "panel_original.png", False),
                ["Original (entrada del gradado)", "sin graduar", ""])]
    for e in VALORES_E:
        g = geo[e]
        h = g["hausdorff_oreja_original_a_graduada"]
        img = panel(pv.read(carpeta / f"e_{e}" / f"3Dmesh_graded_left_e{e}.ply"), canal, salida / f"panel_e{e}.png", True)
        paneles.append((img, [f"-e {e} mm", f"{miles(g['caras'])} caras ({miles(g['caras_oreja'])} en la oreja)",
                              f"Hausdorff en la oreja: máx {h['max_mm']:.2f} mm, RMS {h['rms_mm']:.3f} mm"]))

    fuente = ImageFont.truetype("arial.ttf", 22)
    negrita = ImageFont.truetype("arialbd.ttf", 26)
    franja, pie = 120, 50
    figura = Image.new("RGB", (ANCHO * len(paneles), franja + ALTO + pie), "white")
    dibujo = ImageDraw.Draw(figura)
    for i, (img, lineas) in enumerate(paneles):
        figura.paste(img, (i * ANCHO, franja))
        dibujo.text((i * ANCHO + 20, 14), lineas[0], font=negrita, fill="black")
        for k, linea in enumerate(lineas[1:]):
            dibujo.text((i * ANCHO + 20, 50 + 30 * k), linea, font=fuente, fill="#333333")
    dibujo.text((20, franja + ALTO + 12),
                f"{nombre}: oreja izquierda, vista lateral. Misma cámara y escala en todos los paneles "
                f"({2 * MEDIA_ALTURA_MM:.0f} mm de alto). Hausdorff: original -> graduada, dentro de 40 mm del canal.",
                font=fuente, fill="#333333")
    figura.save(salida / "orejas_alambre.png")


if __name__ == "__main__":
    principal()
