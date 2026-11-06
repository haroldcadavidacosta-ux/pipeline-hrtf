"""Costo real de repetir el piso de ruido (protocolo del barrido) en C1, C3, E1 y E2. No simula nada: lee
los tiempos de la prueba hecha en A1 y A3, en la torre. Usa los tiempos medidos de cada frecuencia y la
duración de cada corrida. Las claves de salida usan los códigos de captura.

Uso:  .venv\\Scripts\\python.exe experimentos\\repetibilidad\\costo_piso_ruido.py
Escribe <carpeta de las capturas>/resultados/costo_piso_ruido.json.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
import config  # noqa: E402

BARRIDO = RAIZ / "datos" / "experimentos" / "barrido_e"
SALIDA = RAIZ.parent / "PRUEBA REPETIBILIDAD" / "resultados" / "costo_piso_ruido.json"
PASADAS = {"2": "fase4_e2", "1": "fase4_e1", "0.5": "fase4_e0.5"}
N_CAPTURAS = 4


def principal() -> None:
    res = {"equipo": "torre", "protocolo": "vector de diagnóstico, oreja izquierda, -x 0,5, -y 10", "pasadas": {}}
    for e, carpeta in PASADAS.items():
        prog = json.loads((BARRIDO / carpeta / "progreso.json").read_text(encoding="utf-8"))["condiciones"]
        por_captura = {}
        for codigo in ("A1", "A3"):
            pasos = prog[config.condicion_barrido(codigo, e)]["pasos"].values()
            ini = [datetime.fromisoformat(p["inicio"]) for p in pasos if p.get("inicio")]
            fin = [datetime.fromisoformat(p["fin"]) for p in pasos if p.get("fin")]
            suma = sum((datetime.fromisoformat(p["fin"]) - datetime.fromisoformat(p["inicio"])).total_seconds()
                       for p in pasos if p.get("inicio") and p.get("fin"))
            por_captura[codigo] = {"frecuencias": len(fin), "horas_suma": round(suma / 3600, 2),
                                   "horas_de_primera_a_ultima": round((max(fin) - min(ini)).total_seconds() / 3600, 2)}
        horas = [v["horas_de_primera_a_ultima"] for v in por_captura.values()]
        res["pasadas"][e] = {**por_captura, "horas_por_captura_media": round(sum(horas) / len(horas), 2)}
    por_captura = sum(v["horas_por_captura_media"] for v in res["pasadas"].values())
    definitiva = res["pasadas"]["0.5"]["horas_por_captura_media"]
    res["completo_por_captura_h"] = round(por_captura, 1)
    res["completo_cuatro_capturas_h"] = round(N_CAPTURAS * por_captura, 1)
    res["solo_definitiva_cuatro_capturas_h"] = round(N_CAPTURAS * definitiva, 1)
    res["nota"] = ("Horas de la torre con una simulación a la vez, sin contar gradado, exportación ni análisis. La pasada "
                   "-e 0,5 llega a 18,9 kHz por la memoria. Estimación a partir de A1 y A3: el tamaño de la malla de cada "
                   "captura puede cambiarla.")
    SALIDA.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    principal()
