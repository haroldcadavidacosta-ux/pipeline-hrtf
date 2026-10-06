"""Barrido de -e, fase 1: geometría de las mallas graduadas, sin simular.

Para cada -e (carpetas e_<valor>/ con 3Dmesh_graded_left_e<valor>.ply y grading_verbose.txt):
  - caras, vértices y comprobación de F = 2V - 4 (cerrada y de genus 0)
  - arista mínima, máxima, media y mediana (toda la malla y dentro de la esfera de la oreja)
  - Hausdorff contra la malla original SOLO dentro de una esfera de 40 mm alrededor del canal
    izquierdo, en los dos sentidos (original -> graduada: lo que se pierde; graduada ->
    original: lo que se inventa); máximo y RMS
  - la salida -v del gradado, parseada

Uso:  .venv/Scripts/python.exe experimentos/barrido_e/fase1_geometria.py <carpeta del barrido>
La carpeta tiene 3Dmesh_orig.stl, informe_limpieza.json y las e_<valor>/. Escribe fase1/geometria.json.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pymeshlab
import trimesh

VALORES_E = ("0.5", "0.7", "1", "2", "3")
RADIO_OREJA_MM = 40.0


def malla_pymeshlab(ruta: Path, centro=None) -> pymeshlab.Mesh:
    """Copia (el MeshSet se libera al salir) de la malla, recortada a la esfera si hay centro."""
    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(str(ruta))
    if centro is not None:
        cx, cy, cz = centro
        ms.compute_selection_by_condition_per_vertex(
            condselect=f"((x-{cx})*(x-{cx}) + (y-{cy})*(y-{cy}) + (z-{cz})*(z-{cz})) > {RADIO_OREJA_MM ** 2}")
        ms.meshing_remove_selected_vertices()
    m = ms.current_mesh()
    return pymeshlab.Mesh(vertex_matrix=m.vertex_matrix(), face_matrix=m.face_matrix())


def hausdorff(muestreada: pymeshlab.Mesh, destino: pymeshlab.Mesh) -> dict:
    ms = pymeshlab.MeshSet()
    ms.add_mesh(muestreada)
    ms.add_mesh(destino)
    r = ms.get_hausdorff_distance(sampledmesh=0, targetmesh=1, samplevert=True, sampleface=True,
                                  samplenum=500000)
    return {"max_mm": round(float(r["max"]), 4), "rms_mm": round(float(r["RMS"]), 4),
            "media_mm": round(float(r["mean"]), 4), "muestras": int(r["n_samples"])}


def aristas(m: trimesh.Trimesh, caras=None) -> dict:
    E = m.faces if caras is None else m.faces[caras]
    L = np.linalg.norm(m.vertices[E[:, [1, 2, 0]]] - m.vertices[E], axis=2).ravel()
    return {"min_mm": round(float(L.min()), 4), "max_mm": round(float(L.max()), 4),
            "media_mm": round(float(L.mean()), 4), "mediana_mm": round(float(np.median(L)), 4)}


def leer_verbose(texto: str) -> dict:
    campos = {"arista_min": r"min\. edge length:\s*([\d.]+)", "arista_max": r"max\. edge length:\s*([\d.]+)",
              "error_max": r"max\. error:\s*([\d.]+)", "gamma": r"gamma scaling left/right:\s*(\S+)",
              "canal_estimado_izq_y_mm": r"entrance left:\s*([-\d.]+)/",
              "canal_estimado_der_y_mm": r"entrance right:\s*([-\d.]+)/",
              "caras_antes": r"Faces before remeshing:\s*(\d+)", "caras_despues": r"Faces after remeshing:\s*(\d+)"}
    out = {}
    for clave, patron in campos.items():
        m = re.search(patron, texto)
        out[clave] = m.group(1) if m else None
    out["nota"] = "este binario (2022) no imprime AID ni centro con -v"
    return out


def principal() -> None:
    carpeta = Path(sys.argv[1])
    aid = json.loads((carpeta / "informe_limpieza.json").read_text(encoding="utf-8"))["escala"]["aid_mm"]
    canal = (0.0, aid / 2, 0.0)
    original = carpeta / "3Dmesh_orig.stl"
    orig_entera, orig_oreja = malla_pymeshlab(original), malla_pymeshlab(original, canal)
    resultados = {"entrada": str(original), "canal_izq_mm": canal, "radio_esfera_mm": RADIO_OREJA_MM, "e": {}}
    for e in VALORES_E:
        ruta = carpeta / f"e_{e}" / f"3Dmesh_graded_left_e{e}.ply"
        g = trimesh.load(ruta, process=False)
        V, F = len(g.vertices), len(g.faces)
        en_oreja = np.linalg.norm(g.triangles_center - canal, axis=1) < RADIO_OREJA_MM
        r = {"vertices": V, "caras": F, "F_igual_2V_menos_4": F == 2 * V - 4,
             "cerrada": bool(g.is_watertight), "piezas": len(g.split(only_watertight=False)),
             "aristas_toda": aristas(g), "aristas_oreja": aristas(g, en_oreja), "caras_oreja": int(en_oreja.sum()),
             "hausdorff_oreja_original_a_graduada": hausdorff(orig_oreja, malla_pymeshlab(ruta)),
             "hausdorff_oreja_graduada_a_original": hausdorff(malla_pymeshlab(ruta, canal), orig_entera),
             "verbose": leer_verbose((carpeta / f"e_{e}" / "grading_verbose.txt").read_text(encoding="utf-8", errors="replace"))}
        resultados["e"][e] = r
        print(f"e={e}: {F} caras, {V} vértices, F=2V-4 {r['F_igual_2V_menos_4']}, "
              f"Hausdorff oreja orig->grad {r['hausdorff_oreja_original_a_graduada']}", flush=True)
    (carpeta / "fase1").mkdir(exist_ok=True)
    (carpeta / "fase1" / "geometria.json").write_text(json.dumps(resultados, indent=2, ensure_ascii=False),
                                                      encoding="utf-8")


if __name__ == "__main__":
    principal()
