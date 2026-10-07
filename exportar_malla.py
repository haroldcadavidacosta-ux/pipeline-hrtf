"""Exportación de los proyectos de Mesh2HRTF. Cuarta pieza del pipeline HRTF, después del gradado.

Toma la carpeta de salida de la limpieza y el gradado (con 3Dmesh_graded_left.ply y
3Dmesh_graded_right.ply) y deja en ella myHRTF_project_L/, myHRTF_project_R/ (listos
para NumCalc) e informe_exportacion.json. Hace falta tener Blender instalado. La
algoritmia está en malla/exportacion.py. Lo mismo se puede hacer desde app.py.

Ejecutar:
  .venv/Scripts/python.exe exportar_malla.py "datos/salidas/B"
  .venv/Scripts/python.exe exportar_malla.py --diagnostico     (¿Blender y el exportador cargan?)

Sale con código 0 si todo salió bien y 1 si no.
"""
import argparse
from pathlib import Path

from malla.exportacion import comprobar_blender, exportar


def principal(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("carpeta", type=Path, nargs="?", help="carpeta de salida de la limpieza y el gradado")
    ap.add_argument("--diagnostico", action="store_true",
                    help="solo comprobar que Blender existe y carga el exportador de Mesh2HRTF")
    a = ap.parse_args(argv)

    if a.diagnostico:
        ok, mensaje = comprobar_blender(completo=True)
        print(("OK: " if ok else "ERROR: ") + mensaje)
        raise SystemExit(0 if ok else 1)
    if a.carpeta is None:
        ap.error("falta la carpeta de salida de la limpieza y el gradado")
    if not a.carpeta.is_dir():
        ap.error(f"no existe la carpeta {a.carpeta}")

    informe = exportar(a.carpeta)
    sep = "\n  - "
    print(f"Resultados en {a.carpeta}")
    print("EXPORTACIÓN OK" if informe["aprobado"] else "EXPORTACIÓN FALLIDA:" + sep + sep.join(informe["fallas"]))
    if informe["avisos"]:
        print("AVISOS:" + sep + sep.join(informe["avisos"]))
    raise SystemExit(0 if informe["aprobado"] else 1)


if __name__ == "__main__":
    principal()
