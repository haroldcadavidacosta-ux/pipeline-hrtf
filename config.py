"""Parámetros del pipeline. Única fuente de verdad.

Las rutas de este archivo son de ejemplo. Cada uno pone las suyas en
config_local.py, que no se sube al repositorio y sobreescribe lo de aquí.
"""

# --- Rutas (sobreescribir en config_local.py) -----------------------------
RUTA_DATOS = r"C:\ruta\de\ejemplo\datos"
BLENDER_EXE = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
MESH2HRTF_PATH = r"C:\ruta\de\ejemplo\Mesh2HRTF-1.3.0\mesh2hrtf"
GRADING_EXE = r"C:\ruta\de\ejemplo\bin\hrtf_mesh_grading.exe"

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
