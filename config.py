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
# Vienen con la app (carpetas grading/, mesh2hrtf_1.3.0/ y numcalc/): no hace falta configurarlos
GRADING_EXE = str(CARPETA_RECURSOS / "grading" / "hrtf_mesh_grading.exe")
MESH2HRTF_PATH = str(CARPETA_RECURSOS / "mesh2hrtf_1.3.0" / "mesh2hrtf")
NUMCALC_EXE = str(CARPETA_RECURSOS / "numcalc" / "NumCalc.exe")

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

# --- Simulación con NumCalc (manage_numcalc de Mesh2HRTF) -------------------
# Factor sobre la RAM que NumCalc estima para cada frecuencia antes de lanzarla. 1.05 es el de
# manage_numcalc; el barrido usó 1.0 porque -e 0,5 no cabía con más (ver experimentos/barrido_e).
SIMULACION_MARGEN_RAM = 1.05
CARPETA_SOFA = "sofa"             # dentro de la carpeta del escaneo: la HRTF de las dos orejas

# --- Geometría ------------------------------------------------------------
CORTE_CUELLO_MM = -115.0          # respecto del eje interaural
# Si la malla termina por encima del corte a no más de esto, se corta un poco más arriba (ver
# malla/LIMPIEZA.md, paso 8) en vez de rechazarla. Decidido el 2026-11-04 con C1 (termina en
# −114,2 mm con la escala bitragial), después de ver ese caso.
CORTE_CUELLO_TOLERANCIA_MM = 2.0
AID_MIN_MM, AID_MAX_MM = 120.0, 200.0

# --- Estimadores ----------------------------------------------------------
FC_ITD = 1500.0                   # Hz
ITD_ORDEN_FILTRO = 4              # Butterworth paso bajo de la ITD, aplicado ida y vuelta (fase cero)
ILD_BANDAS_HZ = (500.0, 16000.0)  # centros nominales de tercio de octava que se reportan
ILD_INTERPRETAR_DESDE_HZ = 1000.0 # por debajo, con Δf = 150 Hz, hay 0 o 1 línea por banda
UMBRAL_ITD_S = 16e-6              # umbral perceptual de referencia del marco (≈ 16 µs)
UMBRAL_ILD_DB = 1.0               # ídem para la ILD por tercio de octava

# --- Capturas -------------------------------------------------------------
# En el repositorio las capturas se nombran solo con el código del participante (A1, A3, B,
# C1…), nunca con su nombre. Si en una máquina las carpetas de datos/ se llaman de otra forma,
# la correspondencia va en config_local.py (que no se sube); sin ella, la carpeta se llama
# como el código.
CARPETAS_CAPTURAS: dict[str, str] = {}     # código -> carpeta en datos/salidas
PREFIJOS_BARRIDO: dict[str, str] = {}      # código -> prefijo de sus condiciones en datos/experimentos/barrido_e


def carpeta_captura(codigo: str) -> str:
    """Nombre de la carpeta de una captura en datos/salidas."""
    return CARPETAS_CAPTURAS.get(codigo, codigo)


def condicion_barrido(codigo: str, e: str) -> str:
    """Nombre de una condición del barrido de -e para una captura (carpeta e_<condición>)."""
    return f"{PREFIJOS_BARRIDO.get(codigo, codigo)}_{e}"


# --- Sobreescritura local -------------------------------------------------
try:
    from config_local import *    # noqa: F401,F403
except ImportError:
    pass
