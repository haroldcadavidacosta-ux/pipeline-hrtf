"""Repite las pruebas de la Sección VII-G de la tesis en los pares C3–C1 y E2–E1, y en A3–A1 como
comprobación. Criterios registrados antes de calcular en
metricas/predicciones_repetibilidad_C_E_2026-11-05.md.

Reutiliza sin cambios evaluacion_prototipo.py, metricas_binaurales.py y fase3_analisis.py, para que
los números salgan del mismo código que los de A.

Uso:  .venv\\Scripts\\python.exe experimentos\\repetibilidad\\evaluacion_repetibilidad.py [carpeta de las capturas]
Escribe en datos/salidas/evaluacion_repetibilidad/: resumen.json, figuras/*.png.
"""
import itertools
import json
import re
import sys
import warnings
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt   # noqa: E402
import numpy as np                # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402
import sofar as sf                # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RAIZ), str(RAIZ / "experimentos" / "barrido_e")]
import config                     # noqa: E402
import evaluacion_prototipo as ep  # noqa: E402
import fase3_analisis as F        # noqa: E402
import metricas_binaurales as mb  # noqa: E402
from malla.simulacion import fuente  # noqa: E402
from metricas import errores, espectral, ild  # noqa: E402

CAPTURAS = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ.parent / "PRUEBA REPETIBILIDAD"
SALIDA = RAIZ / "datos" / "salidas" / "evaluacion_repetibilidad"
PARES = [("A1", "A3"), ("C1", "C3"), ("E1", "E2")]            # (referencia, evaluada)
INTERVALOS_P1 = {("A1", "A3"): (0.0, 20.0), ("C1", "C3"): (-16.3, 3.7), ("E1", "E2"): (-8.9, 11.1)}
BANDAS_TABLA = [1000.0, 2000.0, 4000.0, 8000.0, 16000.0]
_SALIDAS_REALES = ep.SALIDAS
# Tamaño final en la tesis: 0,85\\linewidth de un texto de 516 pt (IEEEtran, una columna). Las figuras se
# guardan a ese tamaño, sin recortar, para que estos puntos sean los que se ven impresos.
ANCHO_FIGURA_IN = 0.85 * 516 / 72.27
ESTILO_TEXTO = {"font.size": 9, "axes.labelsize": 9, "axes.titlesize": 9.5, "xtick.labelsize": 8.5,
                "ytick.labelsize": 8.5, "legend.fontsize": 8.5, "savefig.dpi": 300}
FORMATO_COMA = FuncFormatter(lambda x, _: f"{x:g}".replace(".", ",").replace("-", "\u2212"))
ESTILO_PARES = {"A3-A1": {"color": "#d1495b", "ls": "-"}, "C3-C1": {"color": "#00798c", "ls": (0, (5, 2))},
                "E2-E1": {"color": "#4b2e83", "ls": (0, (1, 1.5))}}


def carpeta(c: str) -> Path:
    """A1 y A3 siguen en datos/salidas; las nuevas, en la carpeta de la prueba."""
    return CAPTURAS / c if (CAPTURAS / c).is_dir() else _SALIDAS_REALES / config.carpeta_captura(c)


def cargar_48(c: str, rejilla: str = "Default") -> dict:
    """metricas_binaurales.cargar busca en SALIDAS/<carpeta_captura>: se le indica dónde está cada una."""
    ruta = carpeta(c)
    mb.SALIDAS = ruta.parent
    config.CARPETAS_CAPTURAS[c] = ruta.name
    return mb.cargar(c, rejilla)


# ---------------------------------------------------------------- funcional

def verificar_sofa(c: str) -> dict:
    archivos = sorted((carpeta(c) / ep.CARPETA_SOFA).glob("*.sofa"))
    malos = []
    with warnings.catch_warnings(record=True) as avisos:
        warnings.simplefilter("always")
        for a in archivos:
            try:
                sf.read_sofa(str(a), verify=True)
            except Exception as e:
                malos.append(f"{a.name}: {e}")
    return {"archivos": len(archivos), "fallan": malos, "avisos": sorted({str(w.message)[:120] for w in avisos})}


def sesiones(proyecto: Path) -> list[dict]:
    out = []
    for f in sorted(proyecto.glob("manage_numcalc_*.txt")):
        t = f.read_text(encoding="utf-8", errors="replace")
        m = re.findall(r"([A-Z][a-z]{2} \d{2} \d{4}, \d{2}:\d{2}:\d{2})", t)
        if m:
            a, b = [datetime.strptime(x, "%b %d %Y, %H:%M:%S") for x in (m[0], m[-1])]
            out.append({"inicio": a.isoformat(), "fin": b.isoformat(), "horas": round((b - a).total_seconds() / 3600, 2),
                        "termino": "All NumCalc projects finished" in t})
    return out


def captura_resumen(c: str) -> dict:
    d = carpeta(c)
    inf = json.loads((d / "informe_limpieza.json").read_text(encoding="utf-8"))
    sim = json.loads((d / "informe_simulacion.json").read_text(encoding="utf-8"))
    esc = inf["escala"]
    # la columna de la tabla es la circunferencia de la malla escalada, no la cinta
    if abs(esc["circunferencia_modelo"] * esc["factor"] - esc["circunferencia_mm"]) > 0.1:
        raise ValueError(f"{c}: circunferencia_mm no es la de la malla escalada")
    lados = {}
    for lado, nombre in config.PROYECTOS_MESH2HRTF.items():
        v = sim["lados"][lado]
        s = sesiones(d / nombre)
        ram = np.loadtxt(fuente(d / nombre) / "Memory.txt", ndmin=2)
        c_ = v["convergencia"]
        lados[lado] = {"convergieron": c_["convergieron"], "pasos": c_["pasos"], "iter_max": v.get("iteraciones_max"),
                       "horas_suma_por_frecuencia": v.get("horas_suma_por_frecuencia"),
                       "horas_pared_sesiones": round(sum(x["horas"] for x in s), 2), "sesiones": len(s),
                       "ram_max_gb": float(ram[:, 2].max())}
    return {"escala": esc["fuente"], "factor": esc["factor"], "aid_mm": esc["aid_mm"],
            "circunferencia_mm": esc["circunferencia_mm"],
            "cinta_mm": round(esc["factores"]["circunferencia"] * esc["circunferencia_modelo"], 1), "orejas_mm": esc["largo_oreja_mm"],
            "bitrago_mm": esc.get("bitrago_mm"), "corte_mm": inf["corte_cuello"]["z_mm"],
            "aprobada": inf["control_calidad"]["aprobado"], "sim_aprobada": sim.get("aprobado"),
            "fallas_sim": sim.get("fallas"), "avisos_sim": sim.get("avisos"), "lados": lados, "sofa": verificar_sofa(c)}


# ---------------------------------------------------------------- repetibilidad (48 kHz)

def repetibilidad_par(ref: str, sim: str, bs: list[dict]) -> dict:
    a, b = cargar_48(ref), cargar_48(sim)
    if not np.array_equal(a["pos"], b["pos"]) or not np.array_equal(a["f"], b["f"]):
        raise ValueError(f"{sim} y {ref} no comparten rejilla o frecuencias")
    w = errores.pesos_voronoi(a["pos"])
    db_a, db_b = espectral.magnitud_db(a["H"]), espectral.magnitud_db(b["H"])
    sd_out, mapas = {}, {}
    for nombre, banda in espectral.BANDAS_SD_HZ.items():
        sd = espectral.sd_direccion(db_a, db_b, a["f"], banda)
        sd_out[nombre] = {**espectral.promedios(sd, w), "p95": float(np.percentile(sd, 95)), "max": float(sd.max()),
                          "izq_ponderada": float((w * sd[:, 0]).sum() / w.sum()),
                          "der_ponderada": float((w * sd[:, 1]).sum() / w.sum())}
        mapas[nombre] = sd.mean(axis=1)
    figura_mapa_sd(a["pos"], mapas, SALIDA / f"{sim}_vs_{ref}" / "figuras" / "eval_repetibilidad_sd.png")

    pa, pb = mb.pistas(a, bs), mb.pistas(b, bs)
    ca, cb = mb.comprobaciones(a, pa), mb.comprobaciones(b, pb)
    e_itd = (pb["itd"] - pa["itd"]) * 1e6
    r_itd = errores.resumen(e_itd, config.UMBRAL_ITD_S * 1e6, w)
    r_itd["direccion_max"] = a["pos"][r_itd.pop("indice_max"), :2].tolist()
    r_itd["frac_sobre_umbral_ponderada"] = float((w * (np.abs(e_itd) > config.UMBRAL_ITD_S * 1e6)).sum())
    lateral = {"90": abs(cb["itd_az90_us"]) - abs(ca["itd_az90_us"]), "270": abs(cb["itd_az270_us"]) - abs(ca["itd_az270_us"])}
    lo, hi = INTERVALOS_P1[(ref, sim)]
    e_ild = pb["ild"] - pa["ild"]
    lineas = ild.lineas_por_banda(a["f"], bs)
    bandas = []
    for j, bb in enumerate(bs):
        if lineas[j]:
            r = errores.resumen(e_ild[:, j], config.UMBRAL_ILD_DB, w)
            r["direccion_max"] = a["pos"][r.pop("indice_max"), :2].tolist()
            bandas.append({"nominal": bb["nominal"], "lineas": int(lineas[j]), **r})
    return {"referencia": ref, "evaluada": sim, "aid_mm": {ref: ca["aid_mm"], sim: cb["aid_mm"]},
            "itd": {ref: ca, sim: cb}, "sd": sd_out, "e_itd_us": r_itd,
            "p1_lateral_us": lateral, "p1_intervalo": [lo, hi],
            "p1_cumple": all(lo <= v <= hi for v in lateral.values()), "e_ild_bandas": bandas}


def muescas_par(ref: str, sim: str) -> dict:
    """Descriptivo, oreja izquierda: los dos criterios del barrido con las HRTF de producción. NO es
    un piso de ruido (ese usa otro gradado y otro vector de frecuencias)."""
    a, b = cargar_48(ref), cargar_48(sim)
    izq_a, izq_b = espectral.magnitud_db(a["H"])[:, 0, :], espectral.magnitud_db(b["H"])[:, 0, :]
    w = errores.pesos_voronoi(a["pos"])
    s = F.sd_f(izq_b - izq_a, w)
    sel = (a["f"] >= 4000) & (a["f"] <= 11000)
    n = F.notch_distribucion(a["f"], izq_a, izq_b, np.ones(len(w), bool))
    return {"sd_4_11_izq_db": float(s[sel].mean()), "perdidas": n["sin_notch_emparejado"],
            "con_referencia": n["validas"] + n["sin_notch_emparejado"], "fraccion_perdidas": n["fraccion_perdidas"],
            "corrimiento_mediana_hz": n["mediana_hz"], "corrimiento_q1_hz": n["q1_hz"], "corrimiento_q3_hz": n["q3_hz"]}


# ---------------------------------------------------------------- rasgos individuales

def inter_hutubs(hutubs: dict) -> dict:
    humanos = [i for i in hutubs if i not in ep.HUTUBS_NO_HUMANOS and i != ep.HUTUBS_REPETIDO[1]]
    inter = {m: [] for m in ep.METRICAS_F4}
    for i, j in itertools.combinations(humanos, 2):
        c = ep.comparar(hutubs[i], hutubs[j])
        for m in ep.METRICAS_F4:
            inter[m].append(c[m])
    return {"n_personas": len(humanos), "valores": {m: np.array(v) for m, v in inter.items()}}


def rasgos_individuales(propios: dict, inter: dict) -> dict:
    v = inter["valores"]
    out = {"n_personas": inter["n_personas"], "n_pares": len(next(iter(v.values()))),
           "inter": {m: {"min": float(x.min()), "p5": float(np.percentile(x, ep.PERCENTIL_INTER)),
                         "mediana": float(np.median(x)), "max": float(x.max())} for m, x in v.items()},
           "pares": {}}
    for ref, sim in PARES:
        intra = ep.comparar(propios[ref], propios[sim])
        out["pares"][f"{sim}-{ref}"] = {
            m: {"intra": intra[m], "percentil": float((v[m] < intra[m]).mean() * 100),
                "cumple": bool(intra[m] < np.percentile(v[m], ep.PERCENTIL_INTER))} for m in ep.METRICAS_F4}
    return out


def figura_mapa_sd(pos: np.ndarray, mapas: dict, ruta: Path) -> None:
    """El mapa de ep.figura_mapa_sd, con coma decimal y al tamaño final."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with plt.rc_context(ESTILO_TEXTO):
        fig, ejes = plt.subplots(1, len(mapas), figsize=(ANCHO_FIGURA_IN, 2.75), sharey=True, layout="constrained")
        for ax, letra, (nombre, v) in zip(ejes, "ab", mapas.items()):
            sc = ax.scatter(pos[:, 0], pos[:, 1], c=v, cmap="viridis", s=4, vmin=0, vmax=10)
            ax.set_title(f"({letra}) {nombre.replace('-', '\u2013')} kHz", loc="left")
            ax.set_xlabel("Azimut (°)")
            ax.set_xticks(range(0, 361, 90))
            ax.set_xlim(-5, 360)
            ax.xaxis.set_major_formatter(FORMATO_COMA)
            ax.yaxis.set_major_formatter(FORMATO_COMA)
        ejes[0].set_ylabel("Elevación (°)")
        cb = fig.colorbar(sc, ax=ejes, label="SD (dB), media de las dos orejas", extend="max")
        cb.ax.yaxis.set_major_formatter(FORMATO_COMA)
        fig.savefig(ruta)
        plt.close(fig)


def figura_rasgos(res: dict, inter: dict) -> None:
    rot = {"sd_4-11": "SD 4\u201311 kHz (dB)", "sd_12-16": "SD 12\u201316 kHz (dB)",
           "itd_mae_us": r"$|e_{\mathrm{ITD}}|$ medio ($\mu$s)",
           "ild_mae_db": r"$|e_{\mathrm{ILD}}|$ medio, desde 1 kHz (dB)"}
    with plt.rc_context(ESTILO_TEXTO):
        fig, ejes = plt.subplots(2, 2, figsize=(ANCHO_FIGURA_IN, 4.9), layout="constrained")
        ejes = ejes.ravel()
        for ax, letra, m in zip(ejes, "abcd", ep.METRICAS_F4):
            v = inter["valores"][m]
            ax.hist(v, bins=40, color="#c9dcf2", label="Entre personas (pares de HUTUBS)")
            ax.axvline(np.percentile(v, ep.PERCENTIL_INTER), color="#52514e", lw=1, ls=(0, (3, 3)),
                       label=f"Percentil {ep.PERCENTIL_INTER:g} entre personas")
            for par, estilo in ESTILO_PARES.items():
                ax.axvline(res["pares"][par][m]["intra"], lw=1.8, **estilo, label=f"Misma persona ({par.replace('-', chr(0x2013))})")
            ax.set_xlabel(rot[m])
            ax.set_title(f"({letra})", loc="left")
            ax.xaxis.set_major_formatter(FORMATO_COMA)
            ax.yaxis.set_major_formatter(FORMATO_COMA)
        for ax in ejes[::2]:
            ax.set_ylabel("Número de pares")
        # panel (c): las tres líneas casi coinciden; se rotulan aparte, con su valor, sin moverlas
        ax = ejes[2]
        for i, par in enumerate(ESTILO_PARES):
            x = res["pares"][par]["itd_mae_us"]["intra"]
            texto = f"{par.replace('-', chr(0x2013))}: {x:.2f}".replace(".", ",") + " \u00b5s"
            ax.annotate(texto, xy=(x, 0.97 - 0.09 * i), xycoords=("data", "axes fraction"), xytext=(0.48, 0.92 - 0.11 * i),
                        textcoords="axes fraction", fontsize=8, color=ESTILO_PARES[par]["color"], va="center",
                        arrowprops=dict(arrowstyle="-", lw=0.6, color=ESTILO_PARES[par]["color"], shrinkB=0))
        fig.legend(*ejes[0].get_legend_handles_labels(), loc="outside lower center", ncol=2, frameon=False)
        fig.savefig(SALIDA / "figuras" / "eval_rasgos_tres_pares.png")
        plt.close(fig)


# ---------------------------------------------------------------- principal

def principal() -> None:
    (SALIDA / "figuras").mkdir(parents=True, exist_ok=True)
    capturas = [c for par in PARES for c in par]
    bs = ild.bandas()
    res = {"generado": datetime.now().astimezone().isoformat(timespec="seconds"),
           "capturas": {c: captura_resumen(c) for c in capturas}}
    print("Funcional listo", flush=True)
    res["repetibilidad"] = {f"{s}-{r}": repetibilidad_par(r, s, bs) for r, s in PARES}
    res["muescas_descriptivo"] = {f"{s}-{r}": muescas_par(r, s) for r, s in PARES}
    print("Repetibilidad lista", flush=True)
    propios = {c: ep.preparar(ep._desde_sofa(carpeta(c) / ep.CARPETA_SOFA / "HRIR_Default_44100.sofa", c), bs)
               for c in capturas}
    hutubs = {i: ep.preparar(ep.cargar_hutubs(i), bs) for i in ep.sujetos_hutubs()}
    print(f"HUTUBS simuladas: {len(hutubs)}", flush=True)
    ep.BANDAS = bs
    res["validez"] = ep.validez(propios, hutubs, bs)
    inter = inter_hutubs(hutubs)
    res["rasgos"] = rasgos_individuales(propios, inter)
    figura_rasgos(res["rasgos"], inter)
    res["contexto_medido"] = ep.contexto_medido(bs)
    (SALIDA / "resumen.json").write_text(json.dumps(res, indent=2, ensure_ascii=False, default=float), encoding="utf-8")
    print("Resultados en", SALIDA)


if __name__ == "__main__":
    principal()
