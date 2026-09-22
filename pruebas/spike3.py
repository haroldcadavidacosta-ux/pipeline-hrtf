"""Spike 3 — clic sobre la malla real con NiceGUI. Sin alineación, sin guardar nada.

Equivalente a spike2.py pero con un visor three.js (ui.scene), cuyo on_click
devuelve el punto exacto (x, y, z) donde el rayo del clic toca la malla.

Ejecutar:  .venv/Scripts/python.exe pruebas/spike3.py
Abre http://localhost:8080 en el navegador.
"""
from pathlib import Path

import numpy as np
import trimesh
from nicegui import app, events, ui
from scipy.spatial import cKDTree

RAIZ = Path(__file__).resolve().parent.parent
RUTA_MALLA = RAIZ / "datos" / "entrada" / "3Dmesh_orig.stl"

# NiceGUI carga el STL en el navegador desde una URL, así que hay que servir
# la carpeta datos/ como archivos estáticos. Solo se sirve en localhost.
app.add_static_files("/datos", RAIZ / "datos")

# La misma malla se carga en Python para la caja envolvente y el vértice más
# cercano, igual que en spike2.
m = trimesh.load(RUTA_MALLA, process=False)
vert = np.asarray(m.vertices, dtype=float)
arbol = cKDTree(vert)
vmin, vmax = vert.min(0), vert.max(0)
centro = (vmin + vmax) / 2
dim = vmax - vmin
diag = float(np.linalg.norm(dim))

ui.label("Prueba 3 — clic sobre la malla real (NiceGUI)").classes("text-2xl")
ui.label(f"Vértices: {len(vert):,}  ·  caja envolvente: "
         f"{dim[0]:.1f} × {dim[1]:.1f} × {dim[2]:.1f}")
ui.label("Arrastra para girar, rueda para acercar, clic sobre la oreja.")
resultado = ui.label("Todavía no hay clic.").classes("text-lg")

marcador = None


def al_clic(e: events.SceneClickEventArguments) -> None:
    global marcador
    if not e.hits:
        resultado.set_text("Clic fuera de la malla.")
        return
    h = e.hits[0]  # el impacto más cercano a la cámara
    xyz = np.array([h.x, h.y, h.z])
    dist, i = arbol.query(xyz)
    resultado.set_text(
        f"Clic en {np.round(xyz, 3)}  →  vértice {i} "
        f"en {np.round(vert[i], 3)}  (a {dist:.4f} de distancia)")
    if marcador is not None:
        marcador.delete()
    with escena:
        marcador = escena.sphere(radius=diag / 150).material("#ff0000").move(h.x, h.y, h.z)


camara = ui.scene.perspective_camera(fov=60, near=diag / 1000, far=diag * 50)
with ui.scene(width=1000, height=650, grid=False, camera=camara,
              on_click=al_clic) as escena:
    escena.stl(f"/datos/entrada/{RUTA_MALLA.name}").material("#c8c8c8")
    escena.move_camera(x=centro[0] + 1.5 * diag, y=centro[1], z=centro[2],
                       look_at_x=centro[0], look_at_y=centro[1], look_at_z=centro[2],
                       up_x=0, up_y=0, up_z=1, duration=0)

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="Spike 3", port=8080, reload=False, show=True,
           show_welcome_message=False)
