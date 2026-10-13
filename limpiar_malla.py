"""Limpieza automática de una malla de KIRI Engine. Segunda pieza del pipeline HRTF.

Necesita la malla y el JSON de landmarks que guarda app.py (por defecto se busca
<malla>_landmarks.json al lado de la malla). La algoritmia está en malla/limpieza.py
y las decisiones de diseño en malla/LIMPIEZA.md. Lo mismo se puede hacer desde app.py.

Ejecutar:
  .venv/Scripts/python.exe limpiar_malla.py RUTA/3DModel.obj --oreja-izq-mm 63 --oreja-der-mm 62
  .venv/Scripts/python.exe limpiar_malla.py RUTA/3DModel.obj --circunferencia-mm 572
  .venv/Scripts/python.exe limpiar_malla.py RUTA/3DModel.obj --bitrago-mm 148 --oreja-izq-mm 63

Sale con código 0 si la malla pasa el control de calidad y 1 si hay que repetir el escaneo.
"""
import argparse
from pathlib import Path

import config
from malla.limpieza import SIGMA_CASCO, limpiar_auto


def principal(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("malla", type=Path, help="malla original de KIRI (.obj)")
    ap.add_argument("--landmarks", type=Path, help="JSON de app.py (defecto: <malla>_landmarks.json)")
    ap.add_argument("--salida", type=Path,
                    help="carpeta de resultados (defecto: RUTA_DATOS/salidas/<carpeta de la malla>)")
    ap.add_argument("--oreja-izq-mm", type=float,
                    help="largo de la oreja izquierda con regla, de lo alto del hélix a lo bajo del lóbulo, en mm")
    ap.add_argument("--oreja-der-mm", type=float, help="ídem, oreja derecha")
    ap.add_argument("--circunferencia-mm", type=float,
                    help="circunferencia de la cabeza con cinta, con el gorro del escaneo, por encima de "
                         "cejas y orejas y paralela a la línea oreja-punta de la nariz, en mm")
    ap.add_argument("--bitrago-mm", type=float,
                    help="ancho bitragial con pie de rey, de tragion a tragion (la muesca justo encima de "
                         "cada trago), en mm. Necesita los dos tragos marcados en app.py. Si se da, manda "
                         "sobre las orejas y la circunferencia, que quedan de control")
    ap.add_argument("--aid-mm", type=float,
                    help="distancia entre las ENTRADAS de los canales auditivos, en mm (no trago a trago, "
                         "que es más ancha); ver LIMPIEZA.md")
    ap.add_argument("--suavizar", type=float, default=SIGMA_CASCO, metavar="SIGMA",
                    help=f"ancho del alisado del casco en AID (defecto {SIGMA_CASCO}); 0 = no alisar")
    a = ap.parse_args(argv)

    landmarks = a.landmarks or a.malla.with_name(f"{a.malla.stem}_landmarks.json")
    if not landmarks.exists():
        ap.error(f"no existe {landmarks}: primero marcar los puntos con app.py")
    salida = a.salida or Path(config.RUTA_DATOS) / "salidas" / a.malla.resolve().parent.name

    informe = limpiar_auto(a.malla, landmarks, salida, a.suavizar, a.aid_mm, a.circunferencia_mm,
                           (a.oreja_izq_mm, a.oreja_der_mm), a.bitrago_mm)
    cc = informe["control_calidad"]
    sep = "\n  - "
    print(f"Resultados en {salida}")
    print("APROBADA" if cc["aprobado"] else "RECHAZADA:" + sep + sep.join(cc["fallas"]))
    if cc["avisos"]:
        print("AVISOS:" + sep + sep.join(cc["avisos"]))
    raise SystemExit(0 if cc["aprobado"] else 1)


if __name__ == "__main__":
    principal()
