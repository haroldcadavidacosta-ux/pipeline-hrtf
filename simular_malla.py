"""Simulación con NumCalc y armado de la HRTF. Quinta pieza del pipeline HRTF, después de la exportación.

Toma la carpeta con myHRTF_project_L y myHRTF_project_R (exportación aprobada), simula las dos
orejas con NumCalc, verifica la convergencia de cada frecuencia y deja la HRTF de las dos orejas
en SOFA_myHRTF_project_merged/ (HRTF y HRIR) e informe_simulacion.json. NumCalc viene con la app
(numcalc/). La algoritmia está en malla/simulacion.py. Lo mismo se puede hacer desde app.py.

Tarda horas. Se puede cortar (Ctrl+C o cerrando la ventana) y volver a lanzar con el mismo
comando: las frecuencias ya terminadas no se repiten.

Ejecutar:
  .venv/Scripts/python.exe simular_malla.py "datos/salidas/A1"
  .venv/Scripts/python.exe simular_malla.py --diagnostico     (¿NumCalc está y arranca?)

Sale con código 0 si hay HRTF válida y 1 si no.
"""
import argparse
from pathlib import Path

from malla.simulacion import comprobar_numcalc, simular


def principal(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("carpeta", type=Path, nargs="?", help="carpeta con los dos proyectos exportados")
    ap.add_argument("--diagnostico", action="store_true", help="solo comprobar que NumCalc está y arranca")
    a = ap.parse_args(argv)

    if a.diagnostico:
        ok, mensaje = comprobar_numcalc()
        print(("OK: " if ok else "ERROR: ") + mensaje)
        raise SystemExit(0 if ok else 1)
    if a.carpeta is None:
        ap.error("falta la carpeta con los proyectos exportados")
    if not a.carpeta.is_dir():
        ap.error(f"no existe la carpeta {a.carpeta}")

    informe = simular(a.carpeta)
    sep = "\n  - "
    print(f"Resultados en {a.carpeta}")
    print("SIMULACIÓN OK: HRTF en " + informe["sofa"]["carpeta"] if informe["aprobado"]
          else "SIMULACIÓN FALLIDA:" + sep + sep.join(informe["fallas"]))
    if informe["avisos"]:
        print("AVISOS:" + sep + sep.join(informe["avisos"]))
    raise SystemExit(0 if informe["aprobado"] else 1)


if __name__ == "__main__":
    principal()
