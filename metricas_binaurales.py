"""ITD, ILD y sus errores entre dos HRTF del pipeline (nivel 3 de la evaluación).

Lee de cada captura (por su código; la carpeta sale de config.carpeta_captura), en
datos/salidas/<carpeta>/SOFA_myHRTF_project_merged/, la HRIR (para la
ITD) y la HRTF (para la ILD) SIN ecualizar, en la rejilla pedida, y calcula:

  ITD por dirección          metricas/itd.py  (correlación cruzada, paso bajo FC_ITD)
  ILD por dirección y banda  metricas/ild.py  (tercio de octava, ILD_BANDAS_HZ)
  e_ITD, e_ILD = sim − ref   metricas/errores.py: error absoluto medio, máximo, fracción
                             sobre el umbral (UMBRAL_ITD_S, UMBRAL_ILD_DB)

Con un solo sujeto (--ref sin --sim) solo calcula sus ITD e ILD, para desarrollar y revisar.

Uso:
  .venv/Scripts/python.exe metricas_binaurales.py --ref A1
  .venv/Scripts/python.exe metricas_binaurales.py --ref A1 --sim A3
Escribe en datos/salidas/metricas/<sim>_vs_<ref>_<rejilla>/ (o <ref>_<rejilla>/):
resumen.json, itd.csv, ild_<ref|sim>.csv, e_ild.csv, informe.md y figuras/*.png.
"""
import argparse
import csv
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
from metricas import errores, ild, itd   # noqa: E402

SALIDAS = RAIZ / "datos" / "salidas"
CARPETA = "SOFA_myHRTF_project_merged"
FS = 48000


def cargar(sujeto: str, rejilla: str) -> dict:
    base = SALIDAS / config.carpeta_captura(sujeto) / CARPETA
    s_ir = sf.read_sofa(str(base / f"HRIR_{rejilla}_{FS}.sofa"), verify=False)
    s_tf = sf.read_sofa(str(base / f"HRTF_{rejilla}_{FS}.sofa"), verify=False)
    pos = np.asarray(s_ir.SourcePosition, dtype=float)
    if not np.array_equal(pos, np.asarray(s_tf.SourcePosition, dtype=float)):
        raise ValueError(f"{sujeto}: la HRIR y la HRTF no tienen las mismas direcciones")
    rec = np.asarray(s_ir.ReceiverPosition, dtype=float).reshape(2, 3)
    if not rec[0, 1] > 0 > rec[1, 1]:
        raise ValueError(f"{sujeto}: el receptor 0 no es la oreja izquierda (+y)")
    return {"sujeto": sujeto, "pos": pos, "fs": float(np.squeeze(s_ir.Data_SamplingRate)),
            "ir": np.asarray(s_ir.Data_IR, dtype=float),
            "H": np.asarray(s_tf.Data_Real) + 1j * np.asarray(s_tf.Data_Imag),
            "f": np.asarray(s_tf.N, dtype=float),
            "aid_m": float(rec[0, 1] - rec[1, 1]),
            "comentario": str(s_ir.GLOBAL_Comment)}


def pistas(d: dict, bs: list[dict]) -> dict:
    return {"itd": itd.itd(d["ir"], d["fs"]), "ild": ild.ild_bandas(d["H"], d["f"], bs)}


def escribir_csv(ruta: Path, cabecera: list, filas) -> None:
    with open(ruta, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cabecera)
        w.writerows(filas)


def comprobaciones(d: dict, p: dict) -> dict:
    """Plausibilidad de un sujeto: simetría, signo y orden de magnitud de la ITD."""
    az, el = d["pos"][:, 0], d["pos"][:, 1]
    horiz = np.abs(el) < 1e-6
    i90 = np.flatnonzero(horiz & (np.abs(az - 90) < 1e-6))
    i270 = np.flatnonzero(horiz & (np.abs(az - 270) < 1e-6))
    i0 = np.flatnonzero(horiz & (np.abs(az) < 1e-6))
    t = p["itd"]
    return {"aid_mm": d["aid_m"] * 1e3,
            "itd_kuhn_max_us": itd.itd_max_kuhn(d["aid_m"]) * 1e6,
            "itd_max_us": float(t.max() * 1e6), "itd_min_us": float(t.min() * 1e6),
            "itd_az90_us": float(t[i90[0]] * 1e6) if i90.size else None,
            "itd_az270_us": float(t[i270[0]] * 1e6) if i270.size else None,
            "itd_frente_us": float(t[i0[0]] * 1e6) if i0.size else None}


def figura_horizontal(datos: list, ps: list, carpeta: Path) -> str:
    fig, ax = plt.subplots(figsize=(7, 3.6))
    for d, p in zip(datos, ps):
        h = np.abs(d["pos"][:, 1]) < 1e-6
        orden = np.argsort(d["pos"][h, 0])
        ax.plot(d["pos"][h, 0][orden], p["itd"][h][orden] * 1e6, label=d["sujeto"], lw=1.4)
    ax.axhline(0, color="#898781", lw=0.6)
    ax.set_xlabel("Azimut (°)  —  90° izquierda, 270° derecha")
    ax.set_ylabel("ITD (µs)")
    ax.set_xticks(range(0, 361, 45))
    ax.set_title("ITD en el plano horizontal")
    ax.legend(frameon=False)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    ruta = carpeta / "itd_horizontal.png"
    fig.savefig(ruta, dpi=150)
    plt.close(fig)
    return ruta.name


def figura_mapa_eitd(pos: np.ndarray, e_us: np.ndarray, carpeta: Path) -> str:
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    lim = max(config.UMBRAL_ITD_S * 1e6 * 2, np.nanmax(np.abs(e_us)))
    sc = ax.scatter(pos[:, 0], pos[:, 1], c=e_us, cmap="RdBu_r", vmin=-lim, vmax=lim, s=9)
    fig.colorbar(sc, ax=ax, label="e_ITD (µs)")
    ax.set_xlabel("Azimut (°)")
    ax.set_ylabel("Elevación (°)")
    ax.set_xticks(range(0, 361, 45))
    ax.set_title("Error de ITD por dirección (sim − ref)")
    fig.tight_layout()
    ruta = carpeta / "e_itd_mapa.png"
    fig.savefig(ruta, dpi=150)
    plt.close(fig)
    return ruta.name


def figura_eild(bs: list, e_ild: np.ndarray, carpeta: Path) -> str:
    noms = [b["nominal"] for b in bs]
    a = np.abs(e_ild)
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    x = np.arange(len(bs))
    ax.plot(x, np.nanmean(a, axis=0), "o-", label="media |e_ILD|")
    ax.plot(x, np.nanpercentile(a, 95, axis=0), "s--", label="percentil 95")
    ax.plot(x, np.nanmax(a, axis=0), "^:", label="máximo")
    ax.axhline(config.UMBRAL_ILD_DB, color="#eb6834", lw=1, label="umbral 1 dB")
    k = next(i for i, n in enumerate(noms) if n >= config.ILD_INTERPRETAR_DESDE_HZ)
    ax.axvspan(-0.5, k - 0.5, color="#e1e0d9", alpha=0.6, lw=0)
    ax.set_xticks(x, [f"{n/1000:g}" for n in noms], rotation=45)
    ax.set_xlabel("Banda de tercio de octava, centro (kHz)")
    ax.set_ylabel("|e_ILD| (dB)")
    ax.set_yscale("log")
    ax.set_title("Error de ILD por banda (sombreado: no se interpreta)")
    ax.legend(frameon=False, fontsize=8)
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    ruta = carpeta / "e_ild_bandas.png"
    fig.savefig(ruta, dpi=150)
    plt.close(fig)
    return ruta.name


def principal() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ref", required=True, help="captura de referencia (código, p. ej. A1)")
    ap.add_argument("--sim", help="captura evaluada; sin ella solo se calculan las pistas de --ref")
    ap.add_argument("--rejilla", default="Default", choices=["Default", "ARI"])
    a = ap.parse_args()

    bs = ild.bandas()
    ref = cargar(a.ref, a.rejilla)
    datos = [ref]
    if a.sim:
        sim = cargar(a.sim, a.rejilla)
        if not np.array_equal(ref["pos"], sim["pos"]):
            raise ValueError("Las dos HRTF no tienen las mismas direcciones: hace falta emparejar")
        if ref["fs"] != sim["fs"] or not np.array_equal(ref["f"], sim["f"]):
            raise ValueError("Distinta frecuencia de muestreo o vector de frecuencias")
        datos.append(sim)
    ps = [pistas(d, bs) for d in datos]

    nombre = (f"{a.sim}_vs_{a.ref}" if a.sim else a.ref).replace(" ", "_") + f"_{a.rejilla}"
    carpeta = SALIDAS / "metricas" / nombre
    (carpeta / "figuras").mkdir(parents=True, exist_ok=True)

    lineas = ild.lineas_por_banda(ref["f"], bs)
    m = {"rejilla": a.rejilla, "fs": ref["fs"], "n_direcciones": int(len(ref["pos"])),
         "parametros": {"FC_ITD": config.FC_ITD, "ITD_ORDEN_FILTRO": config.ITD_ORDEN_FILTRO,
                        "ILD_BANDAS_HZ": list(config.ILD_BANDAS_HZ),
                        "ILD_INTERPRETAR_DESDE_HZ": config.ILD_INTERPRETAR_DESDE_HZ,
                        "UMBRAL_ITD_S": config.UMBRAL_ITD_S, "UMBRAL_ILD_DB": config.UMBRAL_ILD_DB},
         "bandas": [{"nominal": b["nominal"], "lineas": int(n)} for b, n in zip(bs, lineas)],
         "sujetos": {d["sujeto"]: comprobaciones(d, p) for d, p in zip(datos, ps)}}

    pos = ref["pos"]
    for d, p in zip(datos, ps):
        escribir_csv(carpeta / f"ild_{d['sujeto'].replace(' ', '_')}.csv",
                     ["azimut", "elevacion"] + [f"{b['nominal']:g}" for b in bs],
                     [[*pos[i, :2], *np.round(p["ild"][i], 4)] for i in range(len(pos))])
    figs = [figura_horizontal(datos, ps, carpeta / "figuras")]

    if a.sim:
        w = errores.pesos_voronoi(pos)
        e_itd = ps[1]["itd"] - ps[0]["itd"]
        e_ild = ps[1]["ild"] - ps[0]["ild"]
        interp = np.array([b["nominal"] >= config.ILD_INTERPRETAR_DESDE_HZ for b in bs])
        r_itd = errores.resumen(e_itd * 1e6, config.UMBRAL_ITD_S * 1e6, w)
        r_itd["direccion_max"] = pos[r_itd.pop("indice_max"), :2].tolist()
        por_banda = []
        for j, b in enumerate(bs):
            r = errores.resumen(e_ild[:, j], config.UMBRAL_ILD_DB, w) if lineas[j] else None
            if r:
                r["direccion_max"] = pos[r.pop("indice_max"), :2].tolist()
            por_banda.append({"nominal": b["nominal"], "lineas": int(lineas[j]),
                              "interpretada": bool(interp[j]), "resumen": r})
        e_int = e_ild[:, interp]
        a_int = np.abs(e_int)
        m["e_itd_us"] = r_itd
        m["e_ild_db"] = {"por_banda": por_banda,
                         "global_interpretadas": {
                             "media_abs": float(np.nanmean(a_int)),
                             "max_abs": float(np.nanmax(a_int)),
                             "frac_sobre_umbral": float(np.nanmean(a_int > config.UMBRAL_ILD_DB))}}
        escribir_csv(carpeta / "itd.csv", ["azimut", "elevacion", "itd_ref_us", "itd_sim_us",
                                           "e_itd_us", "peso_voronoi"],
                     [[*pos[i, :2], round(ps[0]["itd"][i] * 1e6, 3), round(ps[1]["itd"][i] * 1e6, 3),
                       round(e_itd[i] * 1e6, 3), w[i]] for i in range(len(pos))])
        escribir_csv(carpeta / "e_ild.csv", ["azimut", "elevacion"] + [f"{b['nominal']:g}" for b in bs],
                     [[*pos[i, :2], *np.round(e_ild[i], 4)] for i in range(len(pos))])
        figs += [figura_mapa_eitd(pos, e_itd * 1e6, carpeta / "figuras"),
                 figura_eild(bs, e_ild, carpeta / "figuras")]
    else:
        escribir_csv(carpeta / "itd.csv", ["azimut", "elevacion", "itd_us"],
                     [[*pos[i, :2], round(ps[0]["itd"][i] * 1e6, 3)] for i in range(len(pos))])

    m["figuras"] = figs
    (carpeta / "resumen.json").write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
    escribir_informe(carpeta, m, a)
    print(f"Resultados en {carpeta}")
    print((carpeta / "informe.md").read_text(encoding="utf-8"))


def escribir_informe(carpeta: Path, m: dict, a) -> None:
    L = [f"# Pistas binaurales — {a.sim + ' frente a ' + a.ref if a.sim else a.ref} ({a.rejilla})", "",
         "## Comprobaciones por sujeto", "",
         "| Sujeto | AID (mm) | ITD Kuhn máx (µs) | ITD az 90° (µs) | ITD az 270° (µs) | ITD frente (µs) |",
         "|---|---|---|---|---|---|"]
    for s, c in m["sujetos"].items():
        L.append(f"| {s} | {c['aid_mm']:.1f} | {c['itd_kuhn_max_us']:.0f} | {c['itd_az90_us']:.1f} | "
                 f"{c['itd_az270_us']:.1f} | {c['itd_frente_us']:.1f} |")
    if "e_itd_us" in m:
        r = m["e_itd_us"]
        L += ["", "## Error de ITD", "",
              f"- Error absoluto medio: **{r['media_abs']:.1f} µs** (ponderado por área: "
              f"{r['media_abs_ponderada']:.1f} µs); sesgo medio {r['sesgo']:+.1f} µs",
              f"- Máximo: **{r['max_abs']:.1f} µs** en azimut {r['direccion_max'][0]:g}°, "
              f"elevación {r['direccion_max'][1]:g}°; percentil 95: {r['p95_abs']:.1f} µs",
              f"- Direcciones sobre el umbral de {config.UMBRAL_ITD_S*1e6:g} µs: "
              f"{100*r['frac_sobre_umbral']:.1f} %",
              "", "## Error de ILD por tercio de octava", "",
              "| Banda (Hz) | Líneas | Media \\|e\\| (dB) | Máx \\|e\\| (dB) | % > 1 dB |", "|---|---|---|---|---|"]
        for b in m["e_ild_db"]["por_banda"]:
            r = b["resumen"]
            nota = "" if b["interpretada"] else " *"
            if r:
                L.append(f"| {b['nominal']:g}{nota} | {b['lineas']} | {r['media_abs']:.2f} | "
                         f"{r['max_abs']:.2f} | {100*r['frac_sobre_umbral']:.1f} |")
        g = m["e_ild_db"]["global_interpretadas"]
        L += ["", f"\\* No se interpreta (menos de {config.ILD_INTERPRETAR_DESDE_HZ:g} Hz).", "",
              f"Bandas interpretadas en conjunto: media {g['media_abs']:.2f} dB, máximo "
              f"{g['max_abs']:.2f} dB, {100*g['frac_sobre_umbral']:.1f} % de los valores sobre 1 dB."]
    L += ["", "Figuras: " + ", ".join(f"figuras/{f}" for f in m["figuras"])]
    (carpeta / "informe.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    principal()
