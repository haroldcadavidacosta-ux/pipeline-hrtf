"""Medidas de C1: qué informes usan la cinta de 571 mm o la oreja derecha de 63 mm, qué usó la prueba
nueva y cómo queda la escala por mediana del procesado anterior con las medidas correctas.

Solo lee. En la salida las carpetas con nombre propio se escriben con su código.
Uso:  .venv\\Scripts\\python.exe experimentos\\repetibilidad\\comprobar_medidas_c1.py
Escribe <carpeta de las capturas>/resultados/medidas_c1.json.
"""
import json
import re
import statistics
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
import config  # noqa: E402

PG = RAIZ.parent
PRUEBA = PG / "PRUEBA REPETIBILIDAD"
CORRECTAS = {"circunferencia": 597.0, "oreja_izq": 63.0, "oreja_der": 62.0}
_NOMBRES = sorted(((v, k) for k, v in config.CARPETAS_CAPTURAS.items() if v != k), key=lambda x: -len(x[0]))


def anonima(ruta: Path | str) -> str:
    s = str(ruta).replace("\\", "/").replace(str(PG).replace("\\", "/") + "/", "")
    for nombre, codigo in _NOMBRES:
        s = s.replace(f"/{nombre}/", f"/[{codigo}]/")
    for nombre, codigo in _NOMBRES:                        # también dentro de otros nombres de carpeta
        if len(nombre.split()[0]) > 2:
            s = re.sub(re.escape(nombre.split()[0]), f"[{codigo[0]}]", s, flags=re.IGNORECASE)
    return s


def medidas(inf: dict) -> dict:
    e, f = inf["escala"], inf["escala"]["factores"]
    out = {"circunferencia": f["circunferencia"] * e["circunferencia_modelo"],
           "oreja_izq": f["oreja_izq"] * inf["largo_oreja_modelo"]["izq"],
           "oreja_der": f["oreja_der"] * inf["largo_oreja_modelo"]["der"]}
    if "bitrago" in f:
        out["bitrago"] = f["bitrago"] * inf["bitrago_modelo"]
    return {k: round(v, 2) for k, v in out.items()}


def es_c1(inf: dict) -> bool:
    entrada = Path(inf.get("entrada", "")).parent.name
    return entrada in (config.carpeta_captura("C1"), "C1")


def principal() -> None:
    informes = []
    for raiz in (RAIZ, PRUEBA):
        for p in raiz.rglob("informe_limpieza.json"):
            if ".venv" in p.parts or "build" in p.parts:
                continue
            try:
                inf = json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if es_c1(inf) and (inf.get("escala") or {}).get("factores"):
                e = inf["escala"]
                informes.append({"ruta": anonima(p), "medidas_a_mano": medidas(inf), "escala": e["fuente"],
                                 "factor": round(e["factor"], 4), "aid_mm": e["aid_mm"],
                                 "usa_571": abs(medidas(inf)["circunferencia"] - 571) < 0.5,
                                 "usa_der_63": abs(medidas(inf)["oreja_der"] - 63) < 0.5})
    # 1c: el procesado anterior, con las medidas correctas
    inf = json.loads((RAIZ / "datos" / "salidas" / config.carpeta_captura("C1") / "informe_limpieza.json").read_text(encoding="utf-8"))
    e = inf["escala"]
    modelo = {"circunferencia": e["circunferencia_modelo"], "oreja_izq": inf["largo_oreja_modelo"]["izq"],
              "oreja_der": inf["largo_oreja_modelo"]["der"]}
    factores = {k: CORRECTAS[k] / modelo[k] for k in CORRECTAS}
    mediana = statistics.median(factores.values())
    res = {"informes_de_C1": informes,
           "recalculo_C1_anterior": {
               "antes": {"medidas": medidas(inf), "factores": {k: round(v, 3) for k, v in e["factores"].items()},
                         "factor": round(e["factor"], 3), "aid_mm": e["aid_mm"], "circunferencia_malla_mm": e["circunferencia_mm"],
                         "largo_oreja_mm": e["largo_oreja_mm"], "desviacion_max_pct": round(100 * max(e["discrepancias"].values()), 2)},
               "despues": {"medidas": CORRECTAS, "factores": {k: round(v, 3) for k, v in factores.items()},
                           "factor": round(mediana, 3), "aid_mm": round(inf["aid"] * mediana, 2),
                           "circunferencia_malla_mm": round(modelo["circunferencia"] * mediana, 1),
                           "circ_frente_a_cinta_pct": round(100 * (modelo["circunferencia"] * mediana / CORRECTAS["circunferencia"] - 1), 1),
                           "largo_oreja_mm": {"izq": round(modelo["oreja_izq"] * mediana, 1), "der": round(modelo["oreja_der"] * mediana, 1)},
                           "desviacion_max_pct": round(100 * max(abs(v - mediana) / mediana for v in factores.values()), 2)}}}
    salida = PRUEBA / "resultados" / "medidas_c1.json"
    salida.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    principal()
