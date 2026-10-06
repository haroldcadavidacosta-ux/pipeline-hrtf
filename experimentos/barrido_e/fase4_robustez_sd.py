"""Fase 4, comprobación de robustez: ¿la elección de -e depende de cómo se define la SD?

Comprobación posterior a los datos (no forma parte de la regla registrada). Compara dos definiciones de la
distorsión espectral en 4-11 kHz, con D(f, Ω) = diferencia de magnitud en dB:

  usada (la de las tablas y la regla, fase3_analisis.sd_f):
      SD(f) = sqrt( Σ_Ω w_Ω D² / Σ_Ω w_Ω ), w = área de Voronoi;   SD_banda = media de SD(f) en la banda
  por dirección (la de la ecuación de la tesis y del mapa direccional):
      SD(Ω) = sqrt( media_f D² ) sobre las frecuencias de la banda;  SD_banda = media de SD(Ω) sobre
      direcciones, sin ponderar y ponderada por área

para el barrido de B (cada -e frente a -e 0,5) y para los pisos de ruido de A (A3 frente a A1,
cada -e simulado). Luego aplica la regla de la SD con cada definición.

Uso:  .venv/Scripts/python.exe experimentos/barrido_e/fase4_robustez_sd.py
Escribe datos/experimentos/barrido_e/fase4/robustez_sd.json e informe_robustez_sd.md.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import sofar as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fase3_analisis as F    # noqa: E402

B = F.BARRIDO
SALIDA = B / "fase4"
BANDA = (4000.0, 11000.0)
DEFINICIONES = ("usada", "por_direccion", "por_direccion_ponderada")
NOMBRES = {"usada": "usada (SD(f) ponderada, media en la banda)", "por_direccion": "por dirección, sin ponderar",
           "por_direccion_ponderada": "por dirección, ponderada por área"}


def leer(carpeta: Path):
    s = sf.read_sofa(str(carpeta / "Output2HRTF" / "HRTF_Default.sofa"), verify=False)
    H = (np.asarray(s.Data_Real) + 1j * np.asarray(s.Data_Imag))[:, 0, :]
    return np.asarray(s.N, float), np.asarray(s.SourcePosition, float), 20 * np.log10(np.abs(H))


def sd(ref, otra) -> dict:
    (f1, pos, d1), (f2, _, d2) = ref, otra
    f = np.intersect1d(f1, f2)
    f = f[(f >= BANDA[0]) & (f <= BANDA[1])]
    D = d2[:, np.searchsorted(f2, f)] - d1[:, np.searchsorted(f1, f)]
    w = F.pesos_voronoi(pos)
    por_dir = np.sqrt((D ** 2).mean(axis=1))
    return {"usada": float(F.sd_f(D, w).mean()), "por_direccion": float(por_dir.mean()),
            "por_direccion_ponderada": float((w * por_dir).sum()), "frecuencias": int(len(f))}


def principal() -> None:
    ref = leer(B / "fase2" / "e_0.5")
    barrido = {e: sd(ref, leer(B / "fase2" / f"e_{e}")) for e in ("1", "2", "3")}
    barrido["1_y5"] = sd(ref, leer(B / "fase2_y5" / "e_1_y5"))
    pisos = {}
    for e in ("2", "1", "0.5"):
        a, c = B / f"fase4_e{e}" / f"e_A1_{e}", B / f"fase4_e{e}" / f"e_A3_{e}"
        if (a / "Output2HRTF" / "HRTF_Default.sofa").exists() and (c / "Output2HRTF" / "HRTF_Default.sofa").exists():
            pisos[e] = sd(leer(a), leer(c))
    valor = lambda e: float(e.split("_")[0])

    def elegir(definicion: str, piso: float) -> str:
        return max([e for e in barrido if "_" not in e and barrido[e][definicion] <= piso], key=valor, default="0.5")

    eleccion = {e: {d: elegir(d, p[d]) for d in DEFINICIONES} for e, p in pisos.items()}
    r = {"generado": datetime.now().astimezone().isoformat(timespec="seconds"), "banda_hz": BANDA,
         "barrido_B": barrido, "pisos_A": pisos, "eleccion_por_sd": eleccion}
    SALIDA.mkdir(parents=True, exist_ok=True)
    (SALIDA / "robustez_sd.json").write_text(json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")

    num = F.num
    L = ["# Fase 4: ¿la elección depende de cómo se define la SD?", "",
         f"Generado {r['generado']} por `experimentos/barrido_e/fase4_robustez_sd.py`. Comprobación posterior a los "
         "datos; no forma parte de la regla registrada. Banda 4–11 kHz.", "",
         "- **Usada** (tablas y regla): SD(f) = raíz de la media de D² sobre direcciones, ponderada por área de "
         "Voronoi; luego la media de SD(f) sobre las frecuencias de la banda.",
         "- **Por dirección** (ecuación de la tesis, mapa direccional): SD(Ω) = raíz de la media de D² sobre las "
         "frecuencias de la banda; luego la media sobre direcciones, sin ponderar o ponderada por área.", "",
         "| comparación | " + " | ".join(NOMBRES[d] for d in DEFINICIONES) + " |", "|---|---|---|---|"]
    for e, x in barrido.items():
        L.append(f"| B: -e {e.replace('_y5', ' -y 5').replace('.', ',')} frente a -e 0,5 | "
                 + " | ".join(f"{num(x[d])} dB" for d in DEFINICIONES) + " |")
    for e, x in pisos.items():
        L.append(f"| **Piso: A3 frente a A1, -e {e.replace('.', ',')}** | "
                 + " | ".join(f"**{num(x[d])} dB**" for d in DEFINICIONES) + " |")
    L += ["", "Elección por el criterio de SD (el -e más grande del barrido por debajo del piso), con cada definición:", "",
          "| piso de A | " + " | ".join(NOMBRES[d] for d in DEFINICIONES) + " |", "|---|---|---|---|"]
    for e, x in eleccion.items():
        L.append(f"| -e {e.replace('.', ',')} | " + " | ".join(f"-e {x[d].replace('.', ',')}" for d in DEFINICIONES) + " |")
    iguales = all(len(set(x.values())) == 1 for x in eleccion.values())
    L += ["", "**La elección por SD " + ("no depende de la definición.**" if iguales else "cambia según la definición.**")
          + " El criterio de muescas no usa la SD y no cambia."]
    (SALIDA / "informe_robustez_sd.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    principal()
