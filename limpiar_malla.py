"""Limpieza automática de una malla de KIRI Engine. Segunda pieza del pipeline HRTF.

Necesita la malla y el JSON de landmarks que guarda app_alineacion.py (por defecto se
busca <malla>_landmarks.json al lado de la malla). La algoritmia está en malla/limpieza.py
y las decisiones de diseño en malla/LIMPIEZA.md.

Ejecutar:
  .venv/Scripts/python.exe limpiar_malla.py RUTA/3DModel.obj --aid-mm 148
  .venv/Scripts/python.exe limpiar_malla.py RUTA/3DModel.obj --circunferencia-mm 572

Sale con código 0 si la malla pasa el control de calidad y 1 si hay que repetir el escaneo.
"""
import argparse
from pathlib import Path

import config
from malla.limpieza import SIGMA_CASCO, limpiar_auto


def principal() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("malla", type=Path, help="malla original de KIRI (.obj)")
    ap.add_argument("--landmarks", type=Path, help="JSON de app_alineacion.py (defecto: <malla>_landmarks.json)")
    ap.add_argument("--salida", type=Path,
                    help="carpeta de resultados (defecto: RUTA_DATOS/salidas/<carpeta de la malla>)")
    ap.add_argument("--aid-mm", type=float, help="distancia entre tragos medida con calibrador, en mm")
    ap.add_argument("--circunferencia-mm", type=float, help="circunferencia de la cabeza con cinta, en mm")
    ap.add_argument("--suavizar", type=float, default=SIGMA_CASCO, metavar="SIGMA",
                    help=f"ancho del alisado del casco en AID (defecto {SIGMA_CASCO}); 0 = no alisar")
    a = ap.parse_args()

    landmarks = a.landmarks or a.malla.with_name(f"{a.malla.stem}_landmarks.json")
    if not landmarks.exists():
        ap.error(f"no existe {landmarks}: primero marcar los tres puntos con app_alineacion.py")
    salida = a.salida or Path(config.RUTA_DATOS) / "salidas" / a.malla.resolve().parent.name

    informe = limpiar_auto(a.malla, landmarks, salida, a.suavizar, a.aid_mm, a.circunferencia_mm)
    cc = informe["control_calidad"]
    sep = "\n  - "
    print(f"Resultados en {salida}")
    print("APROBADA" if cc["aprobado"] else "RECHAZADA:" + sep + sep.join(cc["fallas"]))
    if cc["avisos"]:
        print("AVISOS:" + sep + sep.join(cc["avisos"]))
    raise SystemExit(0 if cc["aprobado"] else 1)


if __name__ == "__main__":
    principal()
