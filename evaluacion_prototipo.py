"""Evaluación del prototipo con los datos ya obtenidos (formas 2, 3 y 4).

  validez          ¿La HRTF producida se comporta como una HRTF humana? Rasgos de A1 y
                   A3 frente a la dispersión de las HRTF simuladas de HUTUBS.
  repetibilidad    ¿Dos capturas de la misma persona dan la misma HRTF? SD por dirección entre
                   A1 y A3 con las HRTF de producción (las pistas binaurales las da
                   metricas_binaurales.py).
  personalizacion  ¿La diferencia entre dos capturas de la misma persona (intra) es menor que
                   la diferencia entre personas distintas (inter)? Intra: A1 frente a
                   A3. Inter: todos los pares de personas de HUTUBS (simuladas), cada uno
                   en su propia rejilla, de modo que ninguna comparación empareja direcciones
                   de rejillas distintas.

Todo con HRIR sin ecualizar a 44,1 kHz llevadas a líneas de 150 Hz (FFT de 294 muestras: las
HRIR de HUTUBS, de 256, se completan con ceros), y con los mismos estimadores para todos
(metricas/). Criterios registrados antes de calcular: metricas/predicciones_evaluacion_*.md.

Uso:  .venv/Scripts/python.exe evaluacion_prototipo.py [validez|repetibilidad|personalizacion|todo]
Escribe en datos/salidas/evaluacion/: <forma>.json, informe.md y figuras/*.png.
"""
import argparse
import itertools
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt   # noqa: E402
import numpy as np                # noqa: E402
import sofar as sf                # noqa: E402

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
import config                     # noqa: E402
from metricas import errores, espectral, ild, itd   # noqa: E402

SALIDAS = RAIZ / "datos" / "salidas"
HUTUBS = RAIZ / "datos" / "referencias" / "hutubs"
SALIDA = SALIDAS / "evaluacion"
CARPETA_SOFA = "SOFA_myHRTF_project_merged"
FS = 44100.0
N_FFT = 294                        # 44 100 / 150: líneas cada 150 Hz, como la simulación
SUJETOS_PROPIOS = ["A1", "A3"]       # códigos; la carpeta sale de config.carpeta_captura
# HUTUBS: pp1 y pp96 son el maniquí FABIAN; pp22 y pp88, la misma persona medida dos veces
HUTUBS_NO_HUMANOS = {1, 96}
HUTUBS_REPETIDO = (22, 88)
PERCENTILES_RANGO = (2.5, 97.5)    # rango «humano» para la validez
PERCENTIL_INTER = 5.0              # la intra debe quedar por debajo de este percentil de la inter
NIVEL_BF_HZ = (150.0, 450.0)       # nivel a baja frecuencia: debe rondar 0 dB
NIVEL_BF_MAX_DB = 1.0
BANDAS_ILD_REPORTE = [1000.0, 2000.0, 4000.0, 8000.0, 16000.0]


# ---------------------------------------------------------------- datos

def _desde_sofa(ruta: Path, nombre: str) -> dict:
    s = sf.read_sofa(str(ruta), verify=False)
    fs = float(np.squeeze(s.Data_SamplingRate))
    if fs != FS:
        raise ValueError(f"{nombre}: {fs} Hz, se esperaba {FS}")
    ir = np.asarray(s.Data_IR, dtype=float)
    if ir.shape[-1] > N_FFT:
        raise ValueError(f"{nombre}: {ir.shape[-1]} muestras, más que la FFT de {N_FFT}")
    H = np.fft.rfft(ir, n=N_FFT, axis=-1)
    return {"nombre": nombre, "pos": np.asarray(s.SourcePosition, dtype=float), "ir": ir, "fs": fs,
            "H": H, "f": np.fft.rfftfreq(N_FFT, 1.0 / FS)}


def cargar_propio(sujeto: str) -> dict:
    return _desde_sofa(SALIDAS / config.carpeta_captura(sujeto) / CARPETA_SOFA / "HRIR_Default_44100.sofa", sujeto)


def cargar_hutubs(i: int, tipo: str = "simulated") -> dict:
    return _desde_sofa(HUTUBS / f"pp{i}_HRIRs_{tipo}.sofa", f"pp{i}")


def sujetos_hutubs(tipo: str = "simulated") -> list[int]:
    return sorted(int(p.name[2:].split("_")[0]) for p in HUTUBS.glob(f"pp*_HRIRs_{tipo}.sofa"))


def preparar(d: dict, bs: list[dict]) -> dict:
    """Magnitud en dB, ITD por dirección, ILD por banda y pesos de la rejilla."""
    d["db"] = espectral.magnitud_db(d["H"])
    d["itd_us"] = itd.itd(d["ir"], d["fs"]) * 1e6
    d["ild"] = ild.ild_bandas(d["H"], d["f"], bs)
    d["pesos"] = errores.pesos_voronoi(d["pos"])
    return d


def mas_cercana(pos: np.ndarray, az: float, el: float) -> tuple[int, float]:
    """Índice de la dirección más cercana a (az, el) y su error angular en grados."""
    u = errores.unitarios(pos)
    v = errores.unitarios(np.array([[az, el, 1.0]]))[0]
    c = np.clip(u @ v, -1, 1)
    i = int(np.argmax(c))
    return i, float(np.degrees(np.arccos(c[i])))


# ---------------------------------------------------------------- forma 2: validez

def rasgos(d: dict, bs: list[dict]) -> dict:
    sel = (d["f"] >= NIVEL_BF_HZ[0]) & (d["f"] <= NIVEL_BF_HZ[1])
    i90, e90 = mas_cercana(d["pos"], 90, 0)
    i270, e270 = mas_cercana(d["pos"], 270, 0)
    i0, e0 = mas_cercana(d["pos"], 0, 0)
    noms = [b["nominal"] for b in bs]
    return {"nivel_bf_db": float(d["db"][..., sel].mean()),
            "itd_90_us": float(d["itd_us"][i90]), "itd_270_us": float(d["itd_us"][i270]),
            "itd_frente_us": float(d["itd_us"][i0]), "itd_max_us": float(np.abs(d["itd_us"]).max()),
            "asimetria_itd_us": float(abs(d["itd_us"][i90] + d["itd_us"][i270])),
            **{f"ild_90_{int(n)}_db": float(d["ild"][i90, noms.index(n)]) for n in BANDAS_ILD_REPORTE},
            "error_angular_max": max(e90, e270, e0)}


def validez(propios: dict, hutubs: dict, bs: list[dict]) -> dict:
    humanos = [i for i in hutubs if i not in HUTUBS_NO_HUMANOS and i != HUTUBS_REPETIDO[1]]
    ref = {i: rasgos(hutubs[i], bs) for i in humanos}
    claves = [k for k in next(iter(ref.values())) if k != "error_angular_max"]
    rango = {k: [float(np.percentile([r[k] for r in ref.values()], p)) for p in PERCENTILES_RANGO]
             for k in claves}
    out = {"n_hutubs": len(humanos), "rango_hutubs": rango, "sujetos": {}}
    for s, d in propios.items():
        r = rasgos(d, bs)
        dentro = {k: (rango[k][0] <= r[k] <= rango[k][1]) for k in claves
                  if k not in ("nivel_bf_db", "asimetria_itd_us", "itd_frente_us")}
        dentro["nivel_bf_db"] = abs(r["nivel_bf_db"]) <= NIVEL_BF_MAX_DB
        out["sujetos"][s] = {"rasgos": r, "dentro": dentro}
    return out


# ---------------------------------------------------------------- comparación de dos HRTF

def comparar(a: dict, b: dict) -> dict:
    """Diferencia entre dos HRTF de la MISMA rejilla (b frente a a)."""
    if not np.array_equal(a["pos"], b["pos"]):
        raise ValueError(f"{a['nombre']} y {b['nombre']} no comparten rejilla")
    out = {}
    for nombre, banda in espectral.BANDAS_SD_HZ.items():
        sd = espectral.sd_direccion(a["db"], b["db"], a["f"], banda)
        out[f"sd_{nombre}"] = espectral.promedios(sd, a["pesos"])["media_ponderada"]
    e_itd = np.abs(b["itd_us"] - a["itd_us"])
    out["itd_mae_us"] = float((a["pesos"] * e_itd).sum() / a["pesos"].sum())
    interp = np.array([bb["nominal"] >= config.ILD_INTERPRETAR_DESDE_HZ for bb in BANDAS])
    e_ild = np.abs(b["ild"][:, interp] - a["ild"][:, interp])
    out["ild_mae_db"] = float((a["pesos"][:, None] * e_ild).sum() / (a["pesos"].sum() * e_ild.shape[1]))
    return out


METRICAS_F4 = ["sd_4-11", "sd_12-16", "itd_mae_us", "ild_mae_db"]


def personalizacion(propios: dict, hutubs: dict) -> dict:
    humanos = [i for i in hutubs if i not in HUTUBS_NO_HUMANOS and i != HUTUBS_REPETIDO[1]]
    intra = comparar(propios["A1"], propios["A3"])
    inter = {m: [] for m in METRICAS_F4}
    for i, j in itertools.combinations(humanos, 2):
        c = comparar(hutubs[i], hutubs[j])
        for m in METRICAS_F4:
            inter[m].append(c[m])
    out = {"n_personas": len(humanos), "n_pares": len(inter[METRICAS_F4[0]]), "intra": intra, "inter": {}}
    for m in METRICAS_F4:
        v = np.array(inter[m])
        out["inter"][m] = {"min": float(v.min()), f"p{PERCENTIL_INTER:g}": float(np.percentile(v, PERCENTIL_INTER)),
                           "mediana": float(np.median(v)), "max": float(v.max()),
                           "percentil_de_intra": float((v < intra[m]).mean() * 100),
                           "cumple": bool(intra[m] < np.percentile(v, PERCENTIL_INTER))}
    out["_inter_valores"] = {m: [float(x) for x in inter[m]] for m in METRICAS_F4}
    return out


def contexto_medido(bs: list[dict]) -> dict | None:
    """Referencia de la propia base: la persona medida dos veces (pp22, pp88) frente a los
    pares de personas distintas, todo con HRTF medidas (rejilla de 440 direcciones)."""
    ids = [i for i in sujetos_hutubs("measured") if i not in HUTUBS_NO_HUMANOS]
    if HUTUBS_REPETIDO[0] not in ids or HUTUBS_REPETIDO[1] not in ids:
        return None
    med = {i: preparar(cargar_hutubs(i, "measured"), bs) for i in ids}
    intra = comparar(med[HUTUBS_REPETIDO[0]], med[HUTUBS_REPETIDO[1]])
    humanos = [i for i in ids if i != HUTUBS_REPETIDO[1]]
    inter = {m: [comparar(med[i], med[j])[m] for i, j in itertools.combinations(humanos, 2)]
             for m in METRICAS_F4}
    return {"intra_pp22_pp88": intra,
            "inter_mediana": {m: float(np.median(v)) for m, v in inter.items()},
            "percentil_de_intra": {m: float((np.array(v) < intra[m]).mean() * 100) for m, v in inter.items()}}


# ---------------------------------------------------------------- forma 3: repetibilidad (SD)

def repetibilidad() -> dict:
    """SD por dirección entre A1 y A3 con las HRTF de producción a 48 kHz."""
    out, mapas = {}, {}
    hs = {}
    for s in SUJETOS_PROPIOS:
        x = sf.read_sofa(str(SALIDAS / config.carpeta_captura(s) / CARPETA_SOFA / "HRTF_Default_48000.sofa"), verify=False)
        hs[s] = {"pos": np.asarray(x.SourcePosition, dtype=float), "f": np.asarray(x.N, dtype=float),
                 "db": espectral.magnitud_db(np.asarray(x.Data_Real) + 1j * np.asarray(x.Data_Imag))}
    a, c = hs["A1"], hs["A3"]
    w = errores.pesos_voronoi(a["pos"])
    for nombre, banda in espectral.BANDAS_SD_HZ.items():
        sd = espectral.sd_direccion(a["db"], c["db"], a["f"], banda)
        p = espectral.promedios(sd, w)
        out[nombre] = {**p, "p95": float(np.percentile(sd, 95)), "max": float(sd.max()),
                       "izq_ponderada": float((w * sd[:, 0]).sum() / w.sum()),
                       "der_ponderada": float((w * sd[:, 1]).sum() / w.sum())}
        mapas[nombre] = sd.mean(axis=1)
    figura_mapa_sd(a["pos"], mapas)
    return out


# ---------------------------------------------------------------- figuras

def figura_mapa_sd(pos: np.ndarray, mapas: dict) -> None:
    fig, ejes = plt.subplots(1, len(mapas), figsize=(11, 3.6), sharey=True)
    for ax, letra, (nombre, v) in zip(ejes, "ab", mapas.items()):
        sc = ax.scatter(pos[:, 0], pos[:, 1], c=v, cmap="viridis", s=8, vmin=0, vmax=10)
        ax.set_title(f"({letra}) {nombre.replace('-', '–')} kHz", loc="left")
        ax.set_xlabel("Azimut (°)")
        ax.set_xticks(range(0, 361, 45))
        ax.set_xlim(-5, 360)
    ejes[0].set_ylabel("Elevación (°)")
    fig.colorbar(sc, ax=ejes, label="SD (dB), media de las dos orejas", extend="max")
    fig.savefig(SALIDA / "figuras" / "eval_repetibilidad_sd.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def figura_personalizacion(res: dict) -> None:
    rot = {"sd_4-11": "SD 4–11 kHz (dB)", "sd_12-16": "SD 12–16 kHz (dB)",
           "itd_mae_us": r"$|e_{\mathrm{ITD}}|$ medio ($\mu$s)",
           "ild_mae_db": r"$|e_{\mathrm{ILD}}|$ medio, desde 1 kHz (dB)"}
    fig, ejes = plt.subplots(2, 2, figsize=(7.5, 5.6))
    ejes = ejes.ravel()
    for ax, letra, m in zip(ejes, "abcd", METRICAS_F4):
        v = np.array(res["_inter_valores"][m])
        ax.hist(v, bins=40, color="#9ec5f4", label="Entre personas (pares de HUTUBS)")
        ax.axvline(np.percentile(v, PERCENTIL_INTER), color="#52514e", lw=1, ls="--",
                   label=f"Percentil {PERCENTIL_INTER:g} entre personas")
        ax.axvline(res["intra"][m], color="#eb6834", lw=2.2, label="Misma persona (A1–A3)")
        ax.set_xlabel(rot[m])
        ax.set_title(f"({letra})", loc="left")
    for ax in ejes[::2]:
        ax.set_ylabel("Número de pares")
    fig.legend(*ejes[0].get_legend_handles_labels(), loc="lower center", ncol=2, frameon=False)
    fig.tight_layout(rect=(0, 0.09, 1, 1))
    fig.savefig(SALIDA / "figuras" / "eval_personalizacion.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------- principal

BANDAS = ild.bandas()


def principal() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("forma", choices=["validez", "repetibilidad", "personalizacion", "todo"])
    a = ap.parse_args()
    (SALIDA / "figuras").mkdir(parents=True, exist_ok=True)
    formas = ["validez", "repetibilidad", "personalizacion"] if a.forma == "todo" else [a.forma]

    propios = hutubs = None
    if {"validez", "personalizacion"} & set(formas):
        propios = {s: preparar(cargar_propio(s), BANDAS) for s in SUJETOS_PROPIOS}
        hutubs = {i: preparar(cargar_hutubs(i), BANDAS) for i in sujetos_hutubs()}
        print(f"HUTUBS simuladas cargadas: {len(hutubs)}")

    for forma in formas:
        if forma == "validez":
            res = validez(propios, hutubs, BANDAS)
        elif forma == "repetibilidad":
            res = repetibilidad()
        else:
            res = personalizacion(propios, hutubs)
            figura_personalizacion(res)
            res["contexto_medido"] = contexto_medido(BANDAS)
        guardar = {k: v for k, v in res.items() if not k.startswith("_")}
        (SALIDA / f"{forma}.json").write_text(json.dumps(guardar, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n=== {forma} ===")
        print(json.dumps(guardar, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    principal()
