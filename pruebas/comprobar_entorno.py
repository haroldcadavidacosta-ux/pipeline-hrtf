"""Comprueba que el intérprete es el del .venv y que los paquetes de
requirements.txt se importan correctamente."""
import importlib
import sys

PAQUETES = ["streamlit", "plotly", "trimesh", "scipy", "numpy", "nicegui", "pymeshlab", "pyvista",
            "sofar", "pyfar", "spharpy", "psutil", "mesh2hrtf"]

print(f"Python {sys.version.split()[0]}")
print(f"sys.executable: {sys.executable}")
print("Entorno .venv:", "SI" if ".venv" in sys.executable else "NO (¡ojo!)")
print()

fallos = 0
for nombre in PAQUETES:
    try:
        modulo = importlib.import_module(nombre)
        version = getattr(modulo, "__version__", "?")
        print(f"  OK     {nombre:<10} {version}")
    except Exception as e:  # noqa: BLE001
        fallos += 1
        print(f"  FALLO  {nombre:<10} {e}")

print()
if fallos:
    print(f"{fallos} paquete(s) con problemas.")
    sys.exit(1)
print("Todo en orden.")
