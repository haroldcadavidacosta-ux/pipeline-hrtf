"""Cruce a FMM de un nivel medido con NumCalc -estimate_ram (no resuelve el sistema), por bisección.

Predicción (NC_Addresses.cpp:65-96, fuente de 2022): con dLamdBeL = (c/f) / D, si dLamdBeL > 1,0 NumCalc usa
FMM de un nivel; si no, multinivel salvo que la estimación de niveles dé 1 (no depende de la frecuencia:
NC_Addresses.cpp:803-843) o que en algún nivel la razón de pares de clusters cancelados supere 0,75
(NC_Addresses.cpp:262-283; deja en NC.out la tabla «canceled interacting cluster pairs»). Así, el cruce
debería caer en f* = c/D. Predicción diferencial: -e 0,5 (D = 0,416562 m) -> 823,4 Hz; -e 3
(D = 0,414059 m) -> 828,4 Hz.

Una frecuencia por corrida: NumCalc solo escribe el método si la configuración cambió respecto al paso
anterior (`if(ifdiff) NC_FrequencyInformations`, NC_Main.cpp:383).

Trabaja sobre copias en datos/experimentos/barrido_e/cruce_fmm/biseccion/ (no toca fase2 ni fase2_y5).
Uso:  .venv/Scripts/python.exe experimentos/barrido_e/cruce_fmm.py <carpeta de NumCalc.exe>
"""
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt   # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
BARRIDO = RAIZ / "datos" / "experimentos" / "barrido_e"
SALIDA = BARRIDO / "cruce_fmm" / "biseccion"
CONDICIONES = ["0.5", "3"]
INICIALES_HZ = [815, 820, 825, 830]
UMBRAL_FMM1 = 1.0
UMBRAL_CANCELADOS = 0.75
METODOS = {"Single level fast multipole BEM": "un nivel", "Direct multilevel fast multipole BEM": "multinivel",
           "Traditional BEM": "BEM tradicional"}


def preparar(e: str) -> Path:
    """Copia de la malla, las rejillas y el NC.inp del proyecto de la fase 2 (sin resultados)."""
    origen, destino = BARRIDO / "fase2" / f"e_{e}", SALIDA / f"e_{e}"
    if not (destino / "NumCalc" / "source_1" / "NC.inp").exists():
        for sub in ("ObjectMeshes", "EvaluationGrids"):
            shutil.copytree(origen / sub, destino / sub, dirs_exist_ok=True)
        (destino / "NumCalc" / "source_1").mkdir(parents=True, exist_ok=True)
        shutil.copy2(origen / "NumCalc" / "source_1" / "NC.inp", destino / "NumCalc" / "source_1" / "NC.inp.fase2")
        shutil.copy2(origen / "NumCalc" / "source_1" / "NC.inp", destino / "NumCalc" / "source_1" / "NC.inp")
    (destino / "salidas").mkdir(exist_ok=True)
    return destino


def una_frecuencia(nc_inp_fase2: Path, nc_inp: Path, f: float) -> None:
    """NC.inp con una sola frecuencia: Controlparameter II con 1 paso y una curva de dos filas."""
    lineas = nc_inp_fase2.read_text(encoding="utf-8").splitlines()
    i = next(k for k, l in enumerate(lineas) if "Controlparameter II" in l)
    t = lineas[i + 1].split()
    t[1] = "1"
    lineas[i + 1] = " ".join(t)
    j = next(k for k, l in enumerate(lineas) if "Load Frequency Curve" in l)
    filas = int(lineas[j + 1].split()[1])
    lineas[j + 1: j + 2 + filas] = ["0 2", lineas[j + 2], f"0.000001 {f:.6e} 0.0"]
    nc_inp.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def leer(texto: str) -> dict:
    paso = re.search(r"Step 1, Frequency = ([\d.eE+-]+) Hz", texto)
    metodo = re.search(r"\n(" + "|".join(METODOS) + r")\n", texto)
    tablas = []
    for m in re.finditer(r"canceled interacting cluster pairs:\n.*Cancel ratio \(%\)\n((?:\s+\d+\s+\d+\s+\d+\s+[\d.eE+-]+\n)+)", texto):
        tablas.append([{"nivel": int(a), "cancelados": int(b), "interactuando": int(c), "razon": float(d) / 100}
                       for a, b, c, d in (l.split() for l in m.group(1).strip().splitlines())])
    return {"frecuencia_nc": float(paso.group(1)) if paso else None,
            "metodo": METODOS[metodo.group(1)] if metodo else None,
            "diametro_m": float(re.search(r"Diameter of the BE-mesh \.+ = ([\d.eE+-]+)", texto).group(1)),
            "c_ms": float(re.search(r"Sound speed \.+ = ([\d.eE+-]+)", texto).group(1)),
            "tablas_cancelados": tablas}


def correr(proyecto: Path, numcalc: Path, f: float, registro: dict) -> dict:
    clave = f"{f:g}"
    if clave in registro:
        return registro[clave]
    src = proyecto / "NumCalc" / "source_1"
    for viejo in ("NC.out", "Memory.txt"):
        (src / viejo).unlink(missing_ok=True)
    una_frecuencia(src / "NC.inp.fase2", src / "NC.inp", f)
    t0 = time.time()
    p = subprocess.run([str(numcalc / "NumCalc.exe"), "-estimate_ram"], cwd=src, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=1800)
    nc_out = next((src / n for n in ("NC.out", "NC1-1.out") if (src / n).exists()), None)
    if nc_out is None:
        raise RuntimeError(f"{proyecto.name} {f} Hz: NumCalc no escribió NC.out (código {p.returncode})")
    texto = nc_out.read_text(encoding="utf-8", errors="replace")
    shutil.copy2(nc_out, proyecto / "salidas" / f"NC_{clave}Hz.out")
    r = leer(texto) | {"frecuencia_hz": f, "codigo_salida": p.returncode, "segundos": round(time.time() - t0, 1)}
    if (src / "Memory.txt").exists():
        shutil.copy2(src / "Memory.txt", proyecto / "salidas" / f"Memory_{clave}Hz.txt")
        campos = (src / "Memory.txt").read_text().split()
        r["ram_estimada_gb"] = float(campos[2]) if len(campos) >= 3 else None
    r["lambda_sobre_d"] = r["c_ms"] / f / r["diametro_m"]
    r["criterio"] = criterio(r)
    registro[clave] = r
    return r


def criterio(r: dict) -> str:
    """Cuál regla del código explica el método observado."""
    multinivel_cancelado = any(len(t) > 1 and max(x["razon"] for x in t) > UMBRAL_CANCELADOS
                               for t in r["tablas_cancelados"])
    if r["metodo"] == "multinivel":
        return "ninguno (multinivel)"
    if r["metodo"] == "un nivel":
        if r["lambda_sobre_d"] > UMBRAL_FMM1:
            return "λ/D > 1"
        if multinivel_cancelado:
            return "pares cancelados > 75 %"
        return "estimación de niveles = 1 (o no identificado)"
    return f"otro: {r['metodo']}"


def biseccion(proyecto: Path, numcalc: Path, registro: dict, log) -> dict:
    for f in INICIALES_HZ:
        r = correr(proyecto, numcalc, float(f), registro)
        log(f"  {f} Hz: {r['metodo']} (λ/D = {r['lambda_sobre_d']:.5f}, {r['criterio']}, {r['segundos']} s)")
    puntos = sorted((float(k), v["metodo"]) for k, v in registro.items())
    bajos = [f for f, m in puntos if m == "un nivel"]
    altos = [f for f, m in puntos if m == "multinivel"]
    if not bajos or not altos or max(bajos) > min(altos):
        return {"resuelto": False, "motivo": "los puntos iniciales no encierran un único cruce", "puntos": puntos}
    a, b = max(bajos), min(altos)
    while b - a > 1:
        m = float(round((a + b) / 2))
        r = correr(proyecto, numcalc, m, registro)
        log(f"  {m:g} Hz: {r['metodo']} (λ/D = {r['lambda_sobre_d']:.5f}, {r['criterio']})")
        a, b = (m, b) if r["metodo"] == "un nivel" else (a, m)
    # Monotonía cerca del borde: dos frecuencias enteras a cada lado del intervalo final
    for f in (a - 2, a - 1, b + 1, b + 2):
        correr(proyecto, numcalc, f, registro)
    puntos = sorted((float(k), v["metodo"]) for k, v in registro.items())
    monotono = all(m == "un nivel" for f, m in puntos if f <= a) and all(m == "multinivel" for f, m in puntos if f >= b)
    return {"resuelto": True, "ultimo_un_nivel_hz": a, "primero_multinivel_hz": b, "monotono": monotono}


def figura(resumen: dict) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 3.4), dpi=150)
    colores = {"0.5": "#0b0b0b", "3": "#1baf7a"}
    for k, (e, x) in enumerate(resumen["condiciones"].items()):
        y = 1 - k
        for clave, r in x["corridas"].items():
            f = float(clave)
            ax.plot(f, y, marker="o" if r["metodo"] == "multinivel" else "x", color=colores[e], ms=6,
                    mfc="none" if r["metodo"] == "un nivel" else colores[e])
        ax.axvline(x["f_predicha_hz"], ymin=(y + 0.5 - 0.35) / 2, ymax=(y + 0.5 + 0.35) / 2, color=colores[e], lw=1, ls="--")
        b = x["biseccion"]
        if b.get("resuelto"):
            ax.axvspan(b["ultimo_un_nivel_hz"], b["primero_multinivel_hz"], ymin=(y + 0.5 - 0.3) / 2,
                       ymax=(y + 0.5 + 0.3) / 2, color=colores[e], alpha=0.15)
        ax.text(812.2, y + 0.18, f"-e {e.replace('.', ',')}: D = {x['diametro_m']:.6f} m, c/D = {x['f_predicha_hz']:.1f} Hz".replace(".", ","),
                fontsize=8, color=colores[e])
    ax.set_yticks([1, 0], [f"-e {e.replace('.', ',')}" for e in resumen["condiciones"]])
    ax.set_ylim(-0.6, 1.6)
    ax.set_xlim(812, 833)
    ax.set_xlabel("frecuencia (Hz)   ×: un nivel   ●: multinivel   - - -: c/D predicho   franja: cruce observado")
    ax.set_title("Cruce a FMM de un nivel: NumCalc -estimate_ram, una frecuencia por corrida", fontsize=10, loc="left")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(SALIDA / "cruce_fmm.png")


def principal() -> None:
    numcalc = Path(sys.argv[1])
    SALIDA.mkdir(parents=True, exist_ok=True)
    ruta = SALIDA / "resumen.json"
    resumen = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {"condiciones": {}}

    def log(s: str) -> None:
        print(s, flush=True)

    for e in CONDICIONES:
        proyecto = preparar(e)
        x = resumen["condiciones"].setdefault(e, {"corridas": {}})
        log(f"-e {e}:")
        if not x["corridas"]:
            r = correr(proyecto, numcalc, float(INICIALES_HZ[0]), x["corridas"])
            if r["metodo"] is None:
                ruta.write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
                sys.exit(f"El NC.out de -estimate_ram no declara el método (ver {proyecto / 'salidas'}): "
                         "el experimento no se puede hacer así.")
            log(f"  primera corrida: NC.out declara «{r['metodo']}»")
        x["biseccion"] = biseccion(proyecto, numcalc, x["corridas"], log)
        primera = next(iter(x["corridas"].values()))
        x["diametro_m"], x["c_ms"] = primera["diametro_m"], primera["c_ms"]
        x["f_predicha_hz"] = x["c_ms"] / (x["diametro_m"] * UMBRAL_FMM1)
        x["corridas"] = dict(sorted(x["corridas"].items(), key=lambda kv: float(kv[0])))
        ruta.write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
        log(f"  -> {x['biseccion']} ; predicho {x['f_predicha_hz']:.2f} Hz")
    a, b = (resumen["condiciones"][e] for e in CONDICIONES)
    if a["biseccion"].get("resuelto") and b["biseccion"].get("resuelto"):
        resumen["diferencial"] = {
            "predicho_hz": b["f_predicha_hz"] - a["f_predicha_hz"],
            "observado_hz": b["biseccion"]["primero_multinivel_hz"] - a["biseccion"]["primero_multinivel_hz"]}
    ruta.write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
    figura(resumen)
    log(json.dumps(resumen.get("diferencial"), ensure_ascii=False))


if __name__ == "__main__":
    principal()
