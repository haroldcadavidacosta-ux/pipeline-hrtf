"""Exploratorio, POSTERIOR a los datos: ¿cuánto del error de ILD entre capturas se debe a la escala?

En una simulación de cuerpo rígido, una cabeza s veces mayor da la misma HRTF con el eje de frecuencias
dividido por s: H_s(f) = H(s·f). Es una aproximación: el corte del cuello y la fuente no escalan igual.
Por eso se simula un error de escala sin correr NumCalc: se deforma el eje de frecuencias de la captura
evaluada y se recalcula el error de ILD, con el mismo promedio de la Tabla de rasgos individuales.

Uso:  .venv\\Scripts\\python.exe experimentos\\repetibilidad\\ild_escala.py [carpeta de las capturas]
Escribe datos/salidas/evaluacion_repetibilidad/ild_escala.json.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluacion_repetibilidad as er  # noqa: E402
from metricas import espectral, ild  # noqa: E402

ep = er.ep
ESCALAS_PCT = [-4.7, -2.4, -1.0, 0.0, 1.0, 2.4, 4.7]


def deformar(d: dict, s: float) -> np.ndarray:
    """Magnitud de la HRTF de una cabeza s veces mayor, interpolada en dB: H_s(f) = H(s·f)."""
    db = espectral.magnitud_db(d["H"])
    f = d["f"]
    x = np.clip(s * f, f[0], f[-1])
    i = np.clip(np.searchsorted(f, x) - 1, 0, len(f) - 2)
    t = (x - f[i]) / (f[i + 1] - f[i])
    return 10 ** ((db[..., i] * (1 - t) + db[..., i + 1] * t) / 20)


def mae_ild(a: dict, b_ild: np.ndarray, bs: list[dict]) -> float:
    interp = np.array([bb["nominal"] >= er.config.ILD_INTERPRETAR_DESDE_HZ for bb in bs])
    e = np.abs(b_ild[:, interp] - a["ild"][:, interp])
    return float((a["pesos"][:, None] * e).sum() / (a["pesos"].sum() * e.shape[1]))


def sd_4_11(a: dict, b_mag: np.ndarray) -> float:
    sd = espectral.sd_direccion(a["db"], 20 * np.log10(b_mag), a["f"], (4000.0, 11000.0))
    return espectral.promedios(sd, a["pesos"])["media_ponderada"]


def principal() -> None:
    bs = ild.bandas()
    resumen = json.loads((er.SALIDA / "resumen.json").read_text(encoding="utf-8"))
    p5 = resumen["rasgos"]["inter"]["ild_mae_db"]["p5"]
    res = {"p5_ild_db": p5, "pares": {}}
    for ref, sim in er.PARES:
        a = ep.preparar(ep._desde_sofa(er.carpeta(ref) / ep.CARPETA_SOFA / "HRIR_Default_44100.sofa", ref), bs)
        b = ep.preparar(ep._desde_sofa(er.carpeta(sim) / ep.CARPETA_SOFA / "HRIR_Default_44100.sofa", sim), bs)
        filas = {}
        for pct in sorted(set(ESCALAS_PCT) | set(np.arange(-6.0, 6.01, 0.25).round(2))):
            m = deformar(b, 1 + pct / 100)
            b_ild = ild.ild_bandas(m, b["f"], bs)
            filas[float(pct)] = {"ild": mae_ild(a, b_ild, bs), "sd_4_11": sd_4_11(a, m)}
        mejor_ild = min(filas, key=lambda k: filas[k]["ild"])
        mejor_sd = min(filas, key=lambda k: filas[k]["sd_4_11"])
        res["pares"][f"{sim}-{ref}"] = {
            "original_ild": mae_ild(a, b["ild"], bs),
            "tabla": {str(k): filas[k] for k in ESCALAS_PCT},
            "mejor_ild": {"escala_pct": mejor_ild, **filas[mejor_ild]},
            "mejor_sd": {"escala_pct": mejor_sd, **filas[mejor_sd]}}
    (er.SALIDA / "ild_escala.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print("p5", round(p5, 3))
    for p, v in res["pares"].items():
        print(p, "original", round(v["original_ild"], 3), "| mejor ILD", {k: round(x, 3) for k, x in v["mejor_ild"].items()},
              "| mejor SD", {k: round(x, 3) for k, x in v["mejor_sd"].items()})
        print("   ", {k: (round(x["ild"], 2), round(x["sd_4_11"], 2)) for k, x in v["tabla"].items()})


if __name__ == "__main__":
    principal()
