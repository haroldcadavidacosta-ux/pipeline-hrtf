"""Fase 4, réplica del barrido en una segunda cabeza. Escrito ANTES de simular el par a -e 1
(predicciones en fase4_sujeto_A_2026-10-05.md, sección «Par y réplica a -e 1»).

Para cada captura de A (A y C) se compara su versión a -e 1 y a -e 2 contra su propia versión a -e 0,5,
con el mismo código de la fase 3: SD media por bandas (rejilla Default, ponderada por área de Voronoi) y
distribución del primer notch (corrimiento y fracción de muescas perdidas). Al lado, los mismos valores de
B (fase3/metricas.json). La pregunta: ¿el costo de pasar de -e 0,5 a -e 1 o a -e 2 es el mismo en
otra cabeza? En particular, ¿-e 2 corre las muescas hacia arriba también en A (+87 Hz en B) y -e 1
no (−4 Hz)?

No cambia la regla de la fase 4; informa la elección de producción.

Frecuencias: las comunes a las dos versiones (el par a -e 0,5 llega a 18,9 kHz), sin las que no convergieron
en alguna. La banda de 4-11 kHz y la búsqueda de muescas (4-14 kHz) quedan enteras.

Uso:  .venv/Scripts/python.exe experimentos/barrido_e/fase4_replica.py
Escribe datos/experimentos/barrido_e/fase4/replica.json e informe_replica.md.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fase3_analisis as F    # noqa: E402
from fase4_analisis import BANDAS, cargar, SALIDA    # noqa: E402

COMPARADAS = ("1", "2")
REF = "0.5"


def comparar(ref: dict, otra: dict) -> dict:
    comunes = np.intersect1d(ref["f"], otra["f"])
    excl = set(ref["divergidas"]) | set(otra["divergidas"])
    f = np.array([x for x in comunes if x not in excl])
    i_r, i_o = np.searchsorted(ref["f"], f), np.searchsorted(otra["f"], f)
    w = F.pesos_voronoi(ref["pos"])
    y = F.lateral(ref["pos"])
    ipsi, contra = y > F.LATERAL_MIN, y < -F.LATERAL_MIN
    D = otra["db"][:, i_o] - ref["db"][:, i_r]
    sd = {"todas": F.sd_f(D, w), "ipsilateral": F.sd_f(D, w, ipsi), "contralateral": F.sd_f(D, w, contra)}
    bandas = {b: {h: float(v[(f >= lo) & (f <= hi)].mean()) for h, v in sd.items()} for b, (lo, hi) in BANDAS.items()}
    n = F.notch_distribucion(f, ref["db"][:, i_r], otra["db"][:, i_o], np.ones(len(w), bool))
    return {"frecuencias": int(len(f)), "hasta_hz": float(f.max()), "sd_bandas_db": bandas,
            "notch": {k: n[k] for k in ("validas", "sin_notch_emparejado", "fraccion_perdidas", "mediana_hz", "q1_hz", "q3_hz")}}


def principal() -> None:
    C = json.loads((F.BARRIDO / "fase3" / "metricas.json").read_text(encoding="utf-8"))["condiciones"]
    r = {"generado": datetime.now().astimezone().isoformat(timespec="seconds"), "A": {}, "B": {}}
    for captura in ("A", "C"):
        ref = cargar(REF, captura)
        for e in COMPARADAS:
            r["A"][f"{captura}_{e}"] = comparar(ref, cargar(e, captura))
    for e in COMPARADAS:
        s = C[e]
        n = s["notch_distribucion"]["todas"]
        r["B"][e] = {"sd_4_11_db": s["sd_bandas_db"]["4-11"]["todas"], "sd_12_16_db": s["sd_bandas_db"]["12-16"]["todas"],
                            "fraccion_perdidas": n["fraccion_perdidas"], "mediana_hz": n["mediana_hz"],
                            "q1_hz": n["q1_hz"], "q3_hz": n["q3_hz"]}
    SALIDA.mkdir(parents=True, exist_ok=True)
    (SALIDA / "replica.json").write_text(json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")
    num = F.num
    L = ["# Fase 4: réplica del barrido en A", "",
         f"Generado {r['generado']} por `experimentos/barrido_e/fase4_replica.py`, escrito antes de simular el par a -e 1. "
         "Cada captura de A a -e 1 y a -e 2 contra su propia versión a -e 0,5; al lado, B.", "",
         "| comparación | SD 4–11 kHz (dB) | SD 12–16 kHz (dB) | muescas perdidas | corrimiento de la muesca, mediana [RIC] |",
         "|---|---|---|---|---|"]
    for e in COMPARADAS:
        for captura in ("A", "C"):
            x = r["A"][f"{captura}_{e}"]
            n = x["notch"]
            L.append(f"| A {captura}: -e {e} frente a -e 0,5 | {num(x['sd_bandas_db']['4-11']['todas'])} | "
                     f"{num(x['sd_bandas_db']['12-16']['todas'])} | {num(100 * n['fraccion_perdidas'], 0)} % | "
                     f"{num(n['mediana_hz'], 0)} Hz [{num(n['q1_hz'], 0)}, {num(n['q3_hz'], 0)}] |")
        s = r["B"][e]
        L.append(f"| **B: -e {e} frente a -e 0,5** | {num(s['sd_4_11_db'])} | {num(s['sd_12_16_db'])} | "
                 f"{num(100 * s['fraccion_perdidas'], 0)} % | {num(s['mediana_hz'], 0)} Hz [{num(s['q1_hz'], 0)}, {num(s['q3_hz'], 0)}] |")
    L += ["", "A: frecuencias comunes hasta "
          f"{num(r['A']['A_1']['hasta_hz'] / 1000, 1)} kHz (el par a -e 0,5 llega a 18,9 kHz). B: 75 frecuencias "
          "hasta 23,1 kHz; sus bandas de 4–11 y 12–16 kHz y la búsqueda de muescas no dependen de ese tope."]
    (SALIDA / "informe_replica.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    principal()
