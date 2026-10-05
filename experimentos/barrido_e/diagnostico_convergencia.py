"""Diagnóstico de la divergencia de 24 kHz con -e 1 (binario de NumCalc de 2022).

  - perfil en frecuencia: -e 1 en 20,1 / 21 / 21,9 / 23,1 kHz (24 kHz ya está en el piloto);
    son las frecuencias del vector de diagnóstico más cercanas a 20, 21, 22, 23 kHz
  - sensibilidad: -e 0,98 y -e 1,02 (misma cabeza, mismo gradado) a 24 kHz

Cada simulación va sola, sobre una copia del proyecto (diagnostico/<nombre>/), con la misma
regla de RAM libre que el piloto. La convergencia se lee de NC*.out (malla/convergencia.py),
nunca del código de salida. Volver a correrlo solo hace lo que falte.

Uso:  .venv/Scripts/python.exe experimentos/barrido_e/diagnostico_convergencia.py <carpeta del barrido> <NumCalc.exe>
Escribe diagnostico/diagnostico.json.
"""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import psutil

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from malla.convergencia import leer_salida   # noqa: E402
from malla.gradado import sin_ventanas_de_error          # noqa: E402

TRABAJOS = [   # (nombre, proyecto relativo a la carpeta del barrido, frecuencias)
    ("e_1", "e_1/DIAGNOSTICO_proyecto_L_e1", [20100.0, 21000.0, 21900.0, 23100.0]),
    ("e_0.98", "sensibilidad/e_0.98/DIAGNOSTICO_proyecto_L_e0.98", [24000.0]),
    ("e_1.02", "sensibilidad/e_1.02/DIAGNOSTICO_proyecto_L_e1.02", [24000.0]),
]
MARGEN_RAM = 1.05


def principal() -> None:
    sin_ventanas_de_error()   # si falta una DLL, que termine con un código en vez de colgarse
    carpeta, numcalc = Path(sys.argv[1]), sys.argv[2]
    base = carpeta / "diagnostico"
    base.mkdir(exist_ok=True)
    ruta_json = base / "diagnostico.json"
    datos = json.loads(ruta_json.read_text(encoding="utf-8")) if ruta_json.exists() else {"numcalc": numcalc, "corridas": {}}
    for nombre, relativo, frecuencias in TRABAJOS:
        origen, proyecto = carpeta / relativo, base / nombre
        if not proyecto.exists():
            shutil.copytree(origen, proyecto, ignore=shutil.ignore_patterns("*.out", "Memory.txt", "*.blend"))
        fuente = proyecto / "NumCalc" / "source_1"
        todas = json.loads((proyecto / "parameters.json").read_text(encoding="utf-8"))["frequencies"]
        M = np.loadtxt(origen / "NumCalc" / "source_1" / "Memory.txt", ndmin=2)     # sin cabecera
        for f in frecuencias:
            clave = f"{nombre}_{int(f)}Hz"
            if datos["corridas"].get(clave, {}).get("estado", "").startswith(("convergió", "no convergió")):
                continue
            paso = todas.index(f) + 1
            estimada = float(M[M[:, 0] == paso, 2][0])
            libre = psutil.virtual_memory().available / 2**30
            r = {"malla": nombre, "frecuencia_hz": f, "paso": paso, "ram_estimada_gb": estimada,
                 "ram_libre_al_empezar_gb": round(libre, 2)}
            if libre < estimada * MARGEN_RAM:
                datos["corridas"][clave] = r | {"estado": "pendiente: RAM libre insuficiente"}
                print(f"{clave}: PENDIENTE (libre {libre:.1f} GB)", flush=True)
                ruta_json.write_text(json.dumps(datos, indent=2), encoding="utf-8")
                continue
            print(f"{clave}: simulando (estimada {estimada:.2f} GB, libre {libre:.1f} GB)...", flush=True)
            t0, pico = time.time(), 0
            (fuente / f"NC{paso}-{paso}.out").unlink(missing_ok=True)   # nunca leer la salida de otra corrida
            with open(proyecto / f"numcalc_{int(f)}Hz.log", "w", encoding="utf-8") as log:
                proc = subprocess.Popen([numcalc, "-istart", str(paso), "-iend", str(paso)], cwd=fuente,
                                        stdout=log, stderr=subprocess.STDOUT)
                ps = psutil.Process(proc.pid)
                while proc.poll() is None:
                    try:
                        pico = max(pico, ps.memory_info().peak_wset)
                    except psutil.Error:
                        pass
                    time.sleep(1)
            c = leer_salida(fuente / f"NC{paso}-{paso}.out").get(paso, {})
            estado = ("convergió" if c.get("convergio") else "no convergió") if c.get("convergio") is not None \
                else f"sin resultado (código {proc.returncode})"
            r |= {"estado": estado, "iteraciones": c.get("iteraciones"), "factor_reduccion_residuo": c.get("factor_reduccion_residuo"),
                  "alcanzo_tope": c.get("alcanzo_tope"), "ilu_fallido": c.get("ilu_fallido"),
                  "segundos": round(time.time() - t0, 1), "ram_pico_real_gb": round(pico / 2**30, 3),
                  "codigo_salida": proc.returncode}
            datos["corridas"][clave] = r
            ruta_json.write_text(json.dumps(datos, indent=2), encoding="utf-8")
            print(f"{clave}: {estado} ({r['iteraciones']} it, factor {r['factor_reduccion_residuo']}), "
                  f"{r['segundos'] / 60:.1f} min, RAM real {r['ram_pico_real_gb']:.2f} GB", flush=True)


if __name__ == "__main__":
    principal()
