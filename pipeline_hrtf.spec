# -*- mode: python ; coding: utf-8 -*-
"""Empaquetado de la app con PyInstaller (en modo carpeta: arranca rápido y deja las DLL
del gradado tal cual).

Construir (desde la raíz del repo):
  .venv\\Scripts\\python.exe -m pip install -r requirements-empaquetado.txt
  .venv\\Scripts\\python.exe -m PyInstaller pipeline_hrtf.spec --noconfirm

Resultado: dist\\pipeline_hrtf\\ (se reparte la carpeta entera; se abre pipeline_hrtf.exe).
- Los datos van a dist\\pipeline_hrtf\\datos (config.RUTA_DATOS); se puede poner un
  config_local.py al lado del .exe para cambiar rutas.
- grading\\ (binario del gradado y sus DLL) queda en _internal\\grading y la app lo
  encuentra sola (config.CARPETA_RECURSOS).
- mesh2hrtf_1.3.0\ (exportador de Mesh2HRTF) y malla\blender_exportar.py quedan en
  _internal\. Blender NO va dentro: hay que tenerlo instalado (se busca solo).
- numcalc\\ (NumCalc.exe de 2022 y sus DLL) queda en _internal\\numcalc (config.NUMCALC_EXE).
  El paquete de Python de Mesh2HRTF (output2hrtf, manage_numcalc) y sus dependencias (sofar,
  pyfar, spharpy, matplotlib) van dentro.
- La limpieza, el gradado, la exportación y la simulación corren en procesos aparte: el .exe
  se relanza a sí mismo con el subcomando "limpiar", "gradar", "exportar" o "simular" (ver app.py).
- Al terminar, licencias/generar_avisos.py deja junto al .exe LICENSE.txt (GPL-3),
  AVISOS_DE_TERCEROS.md, licencias/ y codigo_fuente_pipeline_hrtf.zip. Repartir la carpeta
  entera, con esos archivos: la GPL-3 (por pymeshlab) exige entregar el código con el binario.
"""
import os
import sys
from pathlib import Path

import nicegui
from PyInstaller.utils.hooks import collect_all, collect_data_files

datas = [
    (str(Path(nicegui.__file__).parent), "nicegui"),     # lo mismo que hace nicegui-pack
    (os.path.join(SPECPATH, "grading"), "grading"),       # binario del gradado + DLL, sin tocar
    (os.path.join(SPECPATH, "mesh2hrtf_1.3.0"), "mesh2hrtf_1.3.0"),   # exportador de Mesh2HRTF
    (os.path.join(SPECPATH, "numcalc"), "numcalc"),       # NumCalc.exe + DLL, sin tocar
    # lo ejecuta el Python de Blender, no el de la app: va como archivo suelto
    (os.path.join(SPECPATH, "malla", "blender_exportar.py"), "malla"),
]
datas += collect_data_files("trimesh")
binaries = []
hiddenimports = ["limpiar_malla", "gradar_malla", "exportar_malla", "simular_malla", "exportar_hesuvi",
                 # las figuras de diagnóstico de la HRTF se guardan en PDF y JPEG; PyInstaller
                 # no ve estos backends porque matplotlib los carga por nombre
                 "matplotlib.backends.backend_pdf", "matplotlib.backends.backend_agg"]
# pymeshlab: sus plugins y DLL de Qt/MeshLab. mesh2hrtf, sofar (convenciones SOFA en .json),
# pyfar y spharpy: la salida de NumCalc a SOFA
for paquete in ("pymeshlab", "mesh2hrtf", "sofar", "pyfar", "spharpy"):
    d, b, h = collect_all(paquete)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    [os.path.join(SPECPATH, "app.py")],
    pathex=[SPECPATH],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    # config_local.py tiene rutas de cada máquina: no se empaqueta. El resto no lo usa la app.
    # matplotlib sí va: pyfar lo importa (y las figuras de diagnóstico de la HRTF lo usan).
    excludes=["config_local", "streamlit", "plotly", "pyvista", "vtk", "vtkmodules",
              "tkinter", "PyInstaller"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="pipeline_hrtf",
    console=True,           # la consola muestra el estado del gradado al arrancar y los errores
)
coll = COLLECT(exe, a.binaries, a.datas, name="pipeline_hrtf")

# Licencias y código fuente junto al .exe (GPL-3 y avisos de terceros): ver licencias/generar_avisos.py
sys.path.insert(0, os.path.join(SPECPATH, "licencias"))
from generar_avisos import generar  # noqa: E402

generar(Path(DISTPATH) / "pipeline_hrtf")
