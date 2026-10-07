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
# None = se busca solo en C:\Program Files\Blender Foundation (la versión más alta).
# Solo hace falta ponerlo si Blender está instalado en otro sitio.
BLENDER_EXE = None
# Vienen con la app (carpetas grading/ y mesh2hrtf_1.3.0/): no hace falta configurarlos
GRADING_EXE = str(CARPETA_RECURSOS / "grading" / "hrtf_mesh_grading.exe")
MESH2HRTF_PATH = str(CARPETA_RECURSOS / "mesh2hrtf_1.3.0" / "mesh2hrtf")

# --- Gradado (hrtf_mesh_grading) --------------------------------------------
# -e 1 -y 5: elegido para producción en el barrido de -e (fase 4, 2026-10-07; ver
# experimentos/barrido_e/fase4_sujeto_A_2026-10-05.md). La regla del barrido dice que -e 2 es el más
# grueso aceptable, pero -e 2 corre las muescas de la pina hacia arriba de forma sistemática (+87 a +165 Hz en
# tres capturas) y -e 1 mucho menos; -y 5 hace que converja en todas las frecuencias con el NumCalc de 2022.
GRADING_X_MM = 0.5                # arista mínima (en la oreja)
GRADING_E_MM = 1.0                # error geométrico máximo (-e); antes no se pasaba (el binario usa 0.5)
GRADING_Y_MM = 5.0                # arista máxima (lejos de la oreja); antes 10

# --- Exportación a Mesh2HRTF (operador mesh2input.inp de Blender) ------------
PROYECTOS_MESH2HRTF = {"left": "myHRTF_project_L", "right": "myHRTF_project_R"}
EXPORTACION_MESH2HRTF = {
    "minFrequency": 0,
    "maxFrequency": 24000,
    "frequencyVectorType": "Step size",
    "frequencyVectorValue": 150,
    "evaluationGrids": "Default; ARI",
    "materialSearchPaths": "None",
    "pictures": False,
    "reference": True,
    "computeHRIRs": True,
    "method": "ML-FMM BEM",
    "unit": "mm",                 # las mallas graduadas están en mm
    "speedOfSound": "343",
    "densityOfMedium": "1.1839",
}
DISTANCIA_CANAL_MAX_MM = 2.0      # la cara de la fuente debe quedar así de cerca del canal marcado

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
