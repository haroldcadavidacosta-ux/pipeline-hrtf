"""Gradado de la malla para Mesh2HRTF. Tercera pieza del pipeline HRTF, después de la limpieza.

Toma la carpeta de salida de la limpieza (con malla_final_mm.ply: hace falta haber dado
alguna medida de la persona) y deja en ella 3Dmesh_orig.stl, 3Dmesh_graded_left.ply,
3Dmesh_graded_right.ply e informe_gradado.json. La algoritmia está en malla/gradado.py.
Lo mismo se puede hacer desde app.py.

Ejecutar:
  .venv/Scripts/python.exe gradar_malla.py "datos/salidas/B"
  .venv/Scripts/python.exe gradar_malla.py --diagnostico     (¿el binario existe y arranca?)

Sale con código 0 si todo salió bien y 1 si no.
"""
import argparse
from pathlib import Path

from malla.gradado import comprobar_binario, gradar


def principal(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("carpeta", type=Path, nargs="?", help="carpeta de salida de la limpieza")
    ap.add_argument("--diagnostico", action="store_true",
                    help="solo comprobar que el binario del gradado existe y arranca")
    a = ap.parse_args(argv)

    if a.diagnostico:
        ok, mensaje = comprobar_binario()
        print(("OK: " if ok else "ERROR: ") + mensaje)
        raise SystemExit(0 if ok else 1)
    if a.carpeta is None:
        ap.error("falta la carpeta de salida de la limpieza")
    if not a.carpeta.is_dir():
        ap.error(f"no existe la carpeta {a.carpeta}")

    informe = gradar(a.carpeta)
    sep = "\n  - "
    print(f"Resultados en {a.carpeta}")
    print("GRADADO OK" if informe["aprobado"] else "GRADADO FALLIDO:" + sep + sep.join(informe["fallas"]))
    if informe["avisos"]:
        print("AVISOS:" + sep + sep.join(informe["avisos"]))
    raise SystemExit(0 if informe["aprobado"] else 1)


if __name__ == "__main__":
    principal()
