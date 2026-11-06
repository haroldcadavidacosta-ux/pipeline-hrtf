"""Exploratorio, POSTERIOR a los datos: ¿de dónde sale el error de ITD entre capturas?

La ITD crece con la coordenada lateral y de la dirección, ITD ≈ -k·y. Un cambio de escala multiplica
k; un giro de la cabeza alrededor del eje vertical (yaw) o del eje frontal (roll) mezcla y con x o z.
Por eso se ajusta, ponderando por área:

    e_ITD ≈ -k·(s·y + yaw·x + roll·z) + c

y se mira qué parte del error absoluto medio queda tras quitar ese ajuste. No demuestra la causa: un
giro de la malla y una diferencia de geometría equivalente no se distinguen con este ajuste.

Uso:  .venv\\Scripts\\python.exe experimentos\\repetibilidad\\itd_giro_escala.py [carpeta de las capturas]
Escribe datos/salidas/evaluacion_repetibilidad/itd_giro_escala.json.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluacion_repetibilidad as er  # noqa: E402
from metricas import errores, ild  # noqa: E402


def analizar(ref: str, sim: str, bs: list[dict]) -> dict:
    a, b = er.cargar_48(ref), er.cargar_48(sim)
    pa, pb = er.mb.pistas(a, bs), er.mb.pistas(b, bs)
    ita, itb = pa["itd"] * 1e6, pb["itd"] * 1e6
    w = errores.pesos_voronoi(a["pos"])
    x, y, z = errores.unitarios(a["pos"]).T
    raiz = np.sqrt(w)
    k = -float(np.linalg.lstsq((raiz * y)[:, None], raiz * ita, rcond=None)[0][0])
    e = itb - ita
    A = np.column_stack([-k * y, -k * x, -k * z, np.ones_like(y)])
    c = np.linalg.lstsq(A * raiz[:, None], e * raiz, rcond=None)[0]
    resto = e - A @ c
    mae = lambda v: float((w * np.abs(v)).sum() / w.sum())
    r2 = 1 - float((w * resto**2).sum() / (w * (e - (w * e).sum() / w.sum())**2).sum())
    sin_giro = e - A[:, 1:3] @ c[1:3]
    sin_escala = e - A[:, 0] * c[0]
    return {"k_us": k, "escala_pct": float(c[0] * 100), "yaw_grados": float(np.degrees(c[1])),
            "roll_grados": float(np.degrees(c[2])), "constante_us": float(c[3]), "r2": r2,
            "mae_us": mae(e), "mae_sin_giro_us": mae(sin_giro), "mae_sin_escala_us": mae(sin_escala),
            "mae_sin_ajuste_us": mae(resto), "frac_16us_sin_ajuste": float((w * (np.abs(resto) > 16)).sum())}


def principal() -> None:
    bs = ild.bandas()
    res = {f"{s}-{r}": analizar(r, s, bs) for r, s in er.PARES}
    (er.SALIDA / "itd_giro_escala.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    for p, v in res.items():
        print(p, {k: round(x, 3) for k, x in v.items()})


if __name__ == "__main__":
    principal()
