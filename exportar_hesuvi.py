"""Exporta la HRTF de una carpeta ya simulada a HeSuVi (sonido 7.1 virtual con audífonos en Windows).

La simulación (simular_malla.py) ya deja estos WAV al terminar; este script es para carpetas
simuladas antes o para volver a generarlos. Lee SOFA_myHRTF_project_merged/HRIR_Default_*.sofa
y escribe ahí HeSuVi_<fs>.wav y HeSuVi_DTF_<fs>.wav (48 y 44,1 kHz), y la HRIR ecualizada
HRIR_Default_<fs>_DTF.sofa si todavía no está. La algoritmia está en malla/hesuvi.py y malla/dtf.py.

Ejecutar:
  .venv/Scripts/python.exe exportar_hesuvi.py "datos/salidas/A1"

Para usarlos en HeSuVi: copiar el WAV a la carpeta de HRIR de HeSuVi (dentro de la carpeta de
configuración de Equalizer APO) y elegirlo en la pestaña de virtualización. Recomendado:
HeSuVi_DTF_48000.wav, que suena más neutra.
"""
import argparse
from pathlib import Path

from malla.hesuvi import exportar
from malla.simulacion import CARPETA_SOFA


def principal(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("carpeta", type=Path, help=f"carpeta del escaneo (con {CARPETA_SOFA}) o la carpeta {CARPETA_SOFA}")
    a = ap.parse_args(argv)
    carpeta = a.carpeta / CARPETA_SOFA if (a.carpeta / CARPETA_SOFA).is_dir() else a.carpeta
    if not (carpeta / "HRIR_Default_48000.sofa").is_file():
        ap.error(f"no está {carpeta / 'HRIR_Default_48000.sofa'}: primero hay que simular")
    hecho = exportar(carpeta)
    print(f"WAV para HeSuVi en {carpeta}:")
    for nombre in hecho["archivos"]:
        print(f"  {nombre}")
    raise SystemExit(0 if hecho["archivos"] else 1)


if __name__ == "__main__":
    principal()
