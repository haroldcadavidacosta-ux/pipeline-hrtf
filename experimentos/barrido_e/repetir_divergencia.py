"""¿La divergencia de 24 kHz con -e 1 se reproduce? Tres corridas más de esa frecuencia con el
NumCalc de 2022, cada una en una COPIA nueva del proyecto de diagnóstico (el NC78-78.out de la
divergencia original, en piloto/e_1/, queda intacto):

  rep1, rep2   normales (NumCalc es monohilo por diseño: su código no tiene paralelismo)
  un_nucleo    además fijada a un único núcleo de CPU (afinidad), para descartar del todo el
               efecto de la planificación entre núcleos

Se registra también cuántos hilos tiene el proceso y su uso de CPU, para confirmar en
ejecución que es monohilo. La convergencia se lee de NC78-78.out (malla/convergencia.py).

Uso:  .venv/Scripts/python.exe experimentos/barrido_e/repetir_divergencia.py <carpeta del barrido> <NumCalc.exe>
Escribe diagnostico/repeticion_24kHz_e1.json.
"""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from malla.convergencia import leer_salida   # noqa: E402
from malla.gradado import sin_ventanas_de_error          # noqa: E402

CORRIDAS = [("rep1", None), ("rep2", None), ("un_nucleo", [0])]
PASO = 78                                                # 24 kHz en el vector de diagnóstico


def principal() -> None:
    sin_ventanas_de_error()   # si falta una DLL, que termine con un código en vez de colgarse
    carpeta, numcalc = Path(sys.argv[1]), sys.argv[2]
    origen = carpeta / "e_1" / "DIAGNOSTICO_proyecto_L_e1"
    base = carpeta / "diagnostico"
    ruta_json = base / "repeticion_24kHz_e1.json"
    datos = json.loads(ruta_json.read_text(encoding="utf-8")) if ruta_json.exists() else {"numcalc": numcalc, "corridas": {}}
    for nombre, afinidad in CORRIDAS:
        if datos["corridas"].get(nombre, {}).get("estado", "").startswith(("convergió", "no convergió")):
            continue
        proyecto = base / f"e_1_24kHz_{nombre}"
        if proyecto.exists():
            shutil.rmtree(proyecto)
        shutil.copytree(origen, proyecto, ignore=shutil.ignore_patterns("*.out", "Memory.txt", "*.blend"))
        fuente = proyecto / "NumCalc" / "source_1"
        libre = psutil.virtual_memory().available / 2**30
        print(f"{nombre}: simulando 24 kHz (libre {libre:.1f} GB)...", flush=True)
        t0, pico, hilos, cpu = time.time(), 0, set(), []
        with open(proyecto / "numcalc_24000Hz.log", "w", encoding="utf-8") as log:
            proc = subprocess.Popen([numcalc, "-istart", str(PASO), "-iend", str(PASO)], cwd=fuente,
                                    stdout=log, stderr=subprocess.STDOUT)
            ps = psutil.Process(proc.pid)
            if afinidad:
                ps.cpu_affinity(afinidad)
            while proc.poll() is None:
                try:
                    pico = max(pico, ps.memory_info().peak_wset)
                    hilos.add(ps.num_threads())
                    cpu.append(ps.cpu_percent(interval=None))
                except psutil.Error:
                    pass
                time.sleep(2)
        c = leer_salida(fuente / f"NC{PASO}-{PASO}.out").get(PASO, {})
        estado = ("convergió" if c.get("convergio") else "no convergió") if c.get("convergio") is not None \
            else f"sin resultado (código {proc.returncode})"
        r = {"estado": estado, "iteraciones": c.get("iteraciones"), "factor_reduccion_residuo": c.get("factor_reduccion_residuo"),
                  "alcanzo_tope": c.get("alcanzo_tope"), "ilu_fallido": c.get("ilu_fallido"),
             "segundos": round(time.time() - t0, 1), "ram_pico_real_gb": round(pico / 2**30, 3),
             "codigo_salida": proc.returncode, "afinidad": afinidad or "todos los núcleos",
             "hilos_observados": sorted(hilos), "cpu_media_pct_de_un_nucleo": round(sum(cpu[1:]) / max(len(cpu) - 1, 1), 1),
             "ram_libre_al_empezar_gb": round(libre, 2)}
        datos["corridas"][nombre] = r
        ruta_json.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"{nombre}: {estado} ({r['iteraciones']} it, factor {r['factor_reduccion_residuo']}), {r['segundos'] / 60:.1f} min, "
              f"hilos {r['hilos_observados']}, CPU media {r['cpu_media_pct_de_un_nucleo']} % de un núcleo", flush=True)


if __name__ == "__main__":
    principal()
