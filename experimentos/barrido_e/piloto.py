"""Barrido de -e, piloto: tiempo de pared y RAM pico REALES de NumCalc en dos frecuencias
(12 kHz y 24 kHz), para cada -e, antes de lanzar la noche.

Se trabaja sobre copias de los proyectos de diagnóstico (piloto/e_<valor>/), así los
proyectos de la fase 2 quedan sin resultados. Las simulaciones van de una en una (para
medir sin interferencias) y de la más barata a la más cara. Antes de cada una se exige
RAM libre >= estimación de NumCalc x 1.05 (el mismo margen que manage_numcalc): si no
alcanza, se marca "pendiente" en vez de arrancarla, porque con paginación a disco el
tiempo medido no serviría. Volver a correr el script solo hace lo pendiente.

Uso:  .venv/Scripts/python.exe experimentos/barrido_e/piloto.py <carpeta del barrido> <NumCalc.exe>
Escribe piloto/piloto.json.
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
from malla.gradado import sin_ventanas_de_error   # noqa: E402

VALORES_E = ("3", "2", "1", "0.7", "0.5")     # de la más barata a la más cara
FRECUENCIAS = (12000.0, 24000.0)
MARGEN_RAM = 1.05


def convergencia(salida: Path) -> dict:
    """NumCalc sale con código 0 aunque el solver no converja: hay que leerlo de NC*.out
    (malla/convergencia.py). Sin línea del solver cuenta como no convergido."""
    pasos = leer_salida(salida) if salida.exists() else {}
    c = next((r for r in pasos.values() if r["convergio"] is not None), {})
    return {"convergio": bool(c.get("convergio")), "iteraciones": c.get("iteraciones"),
            "factor_reduccion_residuo": c.get("factor_reduccion_residuo"),
            "alcanzo_tope": c.get("alcanzo_tope"), "ilu_fallido": c.get("ilu_fallido")}


def principal() -> None:
    sin_ventanas_de_error()   # si falta una DLL, que termine con un código en vez de colgarse
    carpeta, numcalc = Path(sys.argv[1]), sys.argv[2]
    piloto = carpeta / "piloto"
    ruta_json = piloto / "piloto.json"
    datos = json.loads(ruta_json.read_text(encoding="utf-8")) if ruta_json.exists() else \
        {"numcalc": numcalc, "ram_total_gb": round(psutil.virtual_memory().total / 2**30, 2), "corridas": {}}

    for f in FRECUENCIAS:
        for e in VALORES_E:
            clave = f"e{e}_{int(f)}Hz"
            if datos["corridas"].get(clave, {}).get("estado", "").startswith(("hecha", "no convergió")):
                continue   # ya medida (también si divergió): no se repite sola
            origen = carpeta / f"e_{e}" / f"DIAGNOSTICO_proyecto_L_e{e}"
            proyecto = piloto / f"e_{e}"
            if not proyecto.exists():
                shutil.copytree(origen, proyecto, ignore=shutil.ignore_patterns("*.out", "Memory.txt", "*.blend"))
            fuente = proyecto / "NumCalc" / "source_1"
            frecuencias = json.loads((proyecto / "parameters.json").read_text(encoding="utf-8"))["frequencies"]
            paso = frecuencias.index(f) + 1                         # NumCalc numera los pasos desde 1
            M = np.loadtxt(origen / "NumCalc" / "source_1" / "Memory.txt", ndmin=2)   # sin cabecera
            estimada = float(M[M[:, 0] == paso, 2][0])
            libre = psutil.virtual_memory().available / 2**30
            r = {"e": e, "frecuencia_hz": f, "paso": paso, "ram_estimada_gb": estimada,
                 "ram_libre_al_empezar_gb": round(libre, 2)}
            if libre < estimada * MARGEN_RAM:
                datos["corridas"][clave] = r | {"estado": "pendiente: RAM libre insuficiente"}
                print(f"{clave}: PENDIENTE (libre {libre:.1f} GB < {estimada * MARGEN_RAM:.1f} GB)", flush=True)
                ruta_json.write_text(json.dumps(datos, indent=2), encoding="utf-8")
                continue
            print(f"{clave}: simulando (estimada {estimada:.2f} GB, libre {libre:.1f} GB)...", flush=True)
            t0 = time.time()
            (fuente / f"NC{paso}-{paso}.out").unlink(missing_ok=True)   # nunca leer la salida de otra corrida
            with open(proyecto / f"numcalc_{int(f)}Hz.log", "w", encoding="utf-8") as log:
                proc = subprocess.Popen([numcalc, "-istart", str(paso), "-iend", str(paso)], cwd=fuente,
                                        stdout=log, stderr=subprocess.STDOUT)
                ps = psutil.Process(proc.pid)
                pico = 0
                while proc.poll() is None:
                    try:
                        pico = max(pico, ps.memory_info().peak_wset)   # pico de memoria física (Windows)
                    except psutil.Error:
                        pass
                    time.sleep(1)
            r |= {"estado": "hecha" if proc.returncode == 0 else f"falló (código {proc.returncode})",
                  "segundos": round(time.time() - t0, 1), "ram_pico_real_gb": round(pico / 2**30, 3),
                  "caras": int((proyecto / "ObjectMeshes" / "Reference" / "Elements.txt").open().readline())}
            r |= convergencia(fuente / f"NC{paso}-{paso}.out")
            if r["estado"] == "hecha" and not r["convergio"]:
                r["estado"] = "no convergió (el tiempo no es representativo)"
            datos["corridas"][clave] = r
            ruta_json.write_text(json.dumps(datos, indent=2), encoding="utf-8")
            print(f"{clave}: {r['estado']}, {r['segundos'] / 60:.1f} min, RAM real {r['ram_pico_real_gb']:.2f} GB "
                  f"(estimada {estimada:.2f})", flush=True)


if __name__ == "__main__":
    principal()
