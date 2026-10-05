"""Distribución del factor de reducción del residuo final de NumCalc en todos los NC*.out del disco.

Pregunta: ¿el umbral de parada del binario de 2022 es 1e-9? El código dice `ErroIterSols = 1.0e-9`
(verificacion_numcalc.md, 1.4), pero es una constante: no deja cadena en el .exe. Si el umbral fuera 1e-9,
los pasos que convergen deben amontonarse justo debajo de 1e-9 (el bucle para en la primera iteración que lo
cruza) y no debe haber ninguno entre 1e-9 y 1e-6. Se separan las salidas del binario de 2022 de las que trae
Mesh2HRTF 1.3.0 en tests/resources (otro binario).

Uso:  .venv/Scripts/python.exe experimentos/histograma_factor_residuo.py <carpeta de salida> <raíz> [<raíz> ...]
"""
import json
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt   # noqa: E402
import numpy as np                # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from malla.convergencia import TOLERANCIA_NUMCALC, leer_fuente   # noqa: E402


def recoger(raices: list[str]) -> dict[str, list[dict]]:
    grupos = {"binario_2022": [], "tests_mesh2hrtf_1.3.0": []}
    vistas = set()
    for raiz in raices:
        for d, _, archivos in os.walk(raiz):
            if d in vistas or not any(a.startswith("NC") and a.endswith(".out") for a in archivos):
                continue
            vistas.add(d)
            grupo = "tests_mesh2hrtf_1.3.0" if "tests" in Path(d).parts and "resources" in Path(d).parts else "binario_2022"
            for paso, r in leer_fuente(Path(d)).items():
                if r["convergio"] is not None:
                    grupos[grupo].append({"fuente": d, "paso": paso, "iteraciones": r["iteraciones"],
                                          "factor": r["factor_reduccion_residuo"], "convergio": r["convergio"]})
    return grupos


def estadisticos(filas: list[dict]) -> dict:
    conv = np.array([r["factor"] for r in filas if r["convergio"]])
    lg = np.log10(conv)
    it = np.array([r["iteraciones"] for r in filas if r["convergio"]])
    return {"pasos_con_resultado": len(filas), "convergidos": int(len(conv)),
            "no_convergidos": [r["factor"] for r in filas if not r["convergio"]],
            "minimo": float(conv.min()), "maximo": float(conv.max()),
            "cuantiles_log10": {q: float(np.quantile(lg, q / 100)) for q in (1, 5, 25, 50, 75, 95, 99)},
            "en_[1e-10,1e-9)": int(((conv >= 1e-10) & (conv < 1e-9)).sum()),
            "en_[1e-11,1e-10)": int(((conv >= 1e-11) & (conv < 1e-10)).sum()),
            "por_debajo_de_1e-11": int((conv < 1e-11).sum()),
            "en_[1e-9,1e-6]": int(((conv >= 1e-9) & (conv <= 1e-6)).sum()),
            "iteraciones_convergidos": {"min": int(it.min()), "mediana": float(np.median(it)), "max": int(it.max())}}


def principal() -> None:
    salida = Path(sys.argv[1])
    salida.mkdir(parents=True, exist_ok=True)
    grupos = recoger(sys.argv[2:])
    res = {g: estadisticos(f) for g, f in grupos.items() if f}
    (salida / "factor_residuo.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")

    todos = [r for f in grupos.values() for r in f]
    lg_todos = np.log10([r["factor"] for r in todos])
    bordes = np.arange(np.floor(lg_todos.min() * 10) / 10, np.ceil(lg_todos.max() * 10) / 10 + 0.1, 0.1)
    fig, ax = plt.subplots(figsize=(9, 4.2), dpi=150)
    colores = {"binario_2022": "#2a78d6", "tests_mesh2hrtf_1.3.0": "#eb6834"}
    nombres = {"binario_2022": "binario 2022 (nuestras corridas)", "tests_mesh2hrtf_1.3.0": "tests de Mesh2HRTF 1.3.0"}
    ax.hist([np.log10([r["factor"] for r in grupos[g]]) for g in grupos if grupos[g]], bins=bordes, stacked=True,
            color=[colores[g] for g in grupos if grupos[g]],
            label=[f"{nombres[g]} (n = {len(grupos[g])})" for g in grupos if grupos[g]])
    ax.axvline(np.log10(TOLERANCIA_NUMCALC), color="#0b0b0b", lw=1)
    ax.text(np.log10(TOLERANCIA_NUMCALC) + 0.08, ax.get_ylim()[1] * 0.92, "1e-9 (ErroIterSols)", fontsize=8)
    ax.axvspan(-9, -6, color="#e1e0d9", alpha=0.6, zorder=0)
    ax.text(-7.5, ax.get_ylim()[1] * 0.5, "1e-9 a 1e-6:\nninguno", ha="center", fontsize=8, color="#52514e")
    ax.set_yscale("symlog", linthresh=1)
    ax.set_xlabel("log10 del factor de reducción del residuo final  (‖r_j‖/‖r_1‖, lo que NC.out llama «relative error»)")
    ax.set_ylabel("pasos (escala log)")
    ax.set_title("Factor final por paso, todos los NC*.out del disco (bins de 0,1 década)", fontsize=10, loc="left")
    ax.legend(fontsize=8, frameon=False, loc="upper right")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(salida / "factor_residuo.png")

    # Detalle: los convergidos del binario de 2022, en escala lineal, de 1e-11 a 1e-9
    conv = np.array([r["factor"] for r in grupos["binario_2022"] if r["convergio"]])
    fig, ax = plt.subplots(figsize=(9, 3.6), dpi=150)
    ax.hist(np.log10(conv), bins=np.arange(-11.5, -8.95, 0.05), color="#2a78d6")
    ax.axvline(-9, color="#0b0b0b", lw=1)
    ax.set_xlabel("log10 del factor final (convergidos, binario 2022)")
    ax.set_ylabel("pasos")
    ax.set_title(f"Convergidos del binario 2022 (n = {len(conv)}), bins de 0,05 década", fontsize=10, loc="left")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(salida / "factor_residuo_detalle.png")
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    principal()
