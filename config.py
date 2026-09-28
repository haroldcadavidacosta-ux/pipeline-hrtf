"""Parámetros del pipeline. Única fuente de verdad.

Las rutas externas de este archivo son de ejemplo. Cada uno pone las suyas en
config_local.py, que no se sube al repositorio y sobreescribe lo de aquí (en la app
empaquetada, config_local.py va al lado del .exe).
"""
import sys
from pathlib import Path

# --- Dónde está instalada la app (se resuelve al ejecutar) -----------------
# En desarrollo, la carpeta del repositorio. Empaquetada con PyInstaller (pipeline_hrtf.spec),
# los recursos van dentro (_internal, sys._MEIPASS) y los datos al lado del .exe.
if getattr(sys, "frozen", False):
    CARPETA_APP = Path(sys.executable).resolve().parent
    CARPETA_RECURSOS = Path(getattr(sys, "_MEIPASS", CARPETA_APP))
    sys.path.insert(0, str(CARPETA_APP))          # para encontrar config_local.py
else:
    CARPETA_APP = CARPETA_RECURSOS = Path(__file__).resolve().parent

# --- Rutas (sobreescribir en config_local.py) -----------------------------
RUTA_DATOS = str(CARPETA_APP / "datos")
BLENDER_EXE = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
MESH2HRTF_PATH = r"C:\ruta\de\ejemplo\Mesh2HRTF-1.3.0\mesh2hrtf"
# Viene con la app (carpeta grading/): no hace falta configurarlo
GRADING_EXE = str(CARPETA_RECURSOS / "grading" / "hrtf_mesh_grading.exe")

# --- Gradado (hrtf_mesh_grading) --------------------------------------------
GRADING_X_MM = 0.5                # arista mínima (en la oreja); -e (error máx.) = -x
GRADING_Y_MM = 10.0               # arista máxima (lejos de la oreja)

# --- Geometría ------------------------------------------------------------
CORTE_CUELLO_MM = -115.0          # respecto del eje interaural
AID_MIN_MM, AID_MAX_MM = 120.0, 200.0

# --- Estimadores ----------------------------------------------------------
FC_ITD = 1500.0                   # Hz

# --- Sobreescritura local -------------------------------------------------
try:
    from config_local import *    # noqa: F401,F403
except ImportError:
    pass
