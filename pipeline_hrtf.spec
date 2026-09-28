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
- La limpieza y el gradado corren en procesos aparte: el .exe se relanza a sí mismo con
  el subcomando "limpiar" o "gradar" (ver app.py).
"""
import os
from pathlib import Path

import nicegui
from PyInstaller.utils.hooks import collect_all, collect_data_files

datas = [
    (str(Path(nicegui.__file__).parent), "nicegui"),     # lo mismo que hace nicegui-pack
    (os.path.join(SPECPATH, "grading"), "grading"),       # binario del gradado + DLL, sin tocar
]
datas += collect_data_files("trimesh")
binaries = []
hiddenimports = ["limpiar_malla", "gradar_malla"]
d, b, h = collect_all("pymeshlab")                         # sus plugins y DLL de Qt/MeshLab
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
    excludes=["config_local", "streamlit", "plotly", "pyvista", "vtk", "vtkmodules",
              "matplotlib", "tkinter", "PyInstaller"],
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
