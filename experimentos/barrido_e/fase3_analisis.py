"""Barrido de -e, fase 3: análisis. Solo lee lo que dejaron las fases 1 y 2 (no simula), así
que se puede reejecutar cuantas veces haga falta.

Referencia: -e 0,5. Para -e 1, 2 y 3, contra la referencia:

  SD(f)   distorsión espectral por frecuencia, promediada sobre direcciones; también por
          hemisferio (ipsilateral y > 0 / contralateral y < 0; el plano medio no entra en ninguno)
  SD(θ)   distorsión espectral por dirección, promediada sobre frecuencias
  notch   primer notch de la pina en la dirección ipsilateral (azimut 90°, elevación 0°):
          mínimo de |H| en dB en 5-11 kHz, con interpolación parabólica; corrimiento contra la
          referencia, comparado con los 1,4 kHz de Di Giusto et al. (2023)

Análisis principal: las cuatro condiciones sobre las frecuencias comunes (se excluyen las que no
convergieron en alguna condición, leídas de progreso.json). Análisis secundario, aparte: las 78
frecuencias entre -e 0,5, 2 y 3, que convergieron en todas, para ver si las frecuencias del tope
tienen algo raro de por sí. Sin ILD: con un solo oído habría que suponer simetría.

Rejilla principal: Default (1850 direcciones, esfera completa a 1,5 m). Los promedios sobre
direcciones se ponderan por el área de la celda de Voronoi esférica de cada dirección (la
rejilla es casi, no exactamente, equiareal); también se reporta el promedio sin ponderar. La
rejilla ARI (sin polo sur) se reporta sin ponderar, como comprobación.

Uso:  .venv/Scripts/python.exe experimentos/barrido_e/fase3_analisis.py
Escribe datos/experimentos/barrido_e/fase3/: metricas.json, tabla_decision.csv, sd_f.csv,
sd_theta.csv, informe.md y figuras/*.png.
"""
import csv
import json
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt   # noqa: E402
import matplotlib.ticker          # noqa: E402,F401
import numpy as np                # noqa: E402
import sofar as sf                # noqa: E402
from scipy.spatial import SphericalVoronoi   # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
import sys                        # noqa: E402
sys.path.insert(0, str(RAIZ))
BARRIDO = RAIZ / "datos" / "experimentos" / "barrido_e"
FASE2 = BARRIDO / "fase2"
CRUCE_FMM = BARRIDO / "cruce_fmm"     # NumCalc -estimate_ram en pasos de 150 Hz (corridas previas a la fase 2)
UMBRAL_FMM1 = 1.0                     # thresholFMM1 de NumCalc (NC_Addresses.cpp:70, fuente de 2022)
SALIDA = BARRIDO / "fase3"
REF = "0.5"
COMPARADAS = ["1", "2", "3"]
TODAS = [REF] + COMPARADAS
BANDA_SD = (4000.0, 16000.0)
BANDA_NOTCH = (5000.0, 11000.0)
BANDA_NOTCH_EXTENDIDA = (5000.0, 12000.0)   # solo si el mínimo cae en el borde; se reporta aparte
DI_GIUSTO_KHZ = 1.4        # corrimiento del primer notch por fotogrametría frente a láser
# Umbrales plausibles (PROVISIONALES: el real sale de la repetibilidad de KIRI, aún sin medir)
UMBRALES_SD_DB = [0.5, 1.0, 1.5, 2.0, 3.0]
LATERAL_MIN = 1e-6          # |y| por debajo: plano medio, fuera de ambos hemisferios
SD_PUNTOS_HZ = [4000.0, 6000.0, 8000.0, 12000.0, 16000.0]   # forma de SD(f), interpolada entre muestras
C_MS = 343.0
GRADING_Y_MM = 10.0
CERCA_TOPE_MM = 9.0         # "cerca del tope de -y": arista más larga de la cara >= 0,9·y
RADIO_OREJA_MM = 40.0       # la misma esfera del Hausdorff de la fase 1
# Notch sobre todas las direcciones (criterio declarado antes de mirar los corrimientos)
BANDA_BUSQUEDA = (4000.0, 14000.0)   # donde se buscan y miden los notches
PROFUNDIDAD_MIN_DB = 3.0             # prominencia mínima frente al máximo a cada lado
ANCHURA_MAX_HZ = 3000.0              # anchura máxima a media prominencia
EMPAREJAR_MAX_HZ = 2000.0            # distancia máxima entre el notch de la condición y el de la referencia
MARGINAL_DB = 4.0                    # un notch de la referencia con menos de esto está "justo por encima" de 3 dB
# Bandas de la SD: la de la pina conduce la decisión; la alta se reporta como límite de ancho de banda
BANDAS_SD = {"4-11": (4000.0, 11000.0), "12-16": (12000.0, 16000.0)}
BANDA_DECISION = "4-11"

# Paleta (guía dataviz): la referencia en tinta neutra; las comparadas en los tres primeros slots
# categóricos, validados en todos los pares y en ambos modos según la guía. El validador no se
# pudo correr aquí (no hay Node instalado).
COLOR = {"0.5": "#0b0b0b", "1": "#2a78d6", "2": "#eb6834", "3": "#1baf7a"}
TINTA, TINTA_2, TENUE = "#0b0b0b", "#52514e", "#898781"
REJILLA, EJE, FONDO = "#e1e0d9", "#c3c2b7", "#fcfcfb"
RAMPA_AZUL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]


def etiqueta(e: str) -> str:
    return f"-e {e.replace('.', ',')}" + (" (ref.)" if e == REF else "")


# ---------------------------------------------------------------- datos

def cargar(e: str, rejilla: str) -> dict:
    """SOFA de output2hrtf sin marcar (los NaN se aplican aquí, desde progreso.json)."""
    s = sf.read_sofa(str(FASE2 / f"e_{e}" / "Output2HRTF" / f"HRTF_{rejilla}.sofa"), verify=False)
    H = (np.asarray(s.Data_Real) + 1j * np.asarray(s.Data_Imag))[:, 0, :]
    return {"f": np.asarray(s.N, dtype=float), "pos": np.asarray(s.SourcePosition, dtype=float),
            "db": 20 * np.log10(np.abs(H))}


def pesos_voronoi(pos: np.ndarray) -> np.ndarray:
    az, el = np.radians(pos[:, 0]), np.radians(pos[:, 1])
    xyz = np.column_stack([np.cos(el) * np.cos(az), np.cos(el) * np.sin(az), np.sin(el)])
    v = SphericalVoronoi(xyz, radius=1.0)
    a = v.calculate_areas()
    return a / a.sum()


def lateral(pos: np.ndarray) -> np.ndarray:
    """Coordenada y (izquierda) de cada dirección en la esfera unidad."""
    az, el = np.radians(pos[:, 0]), np.radians(pos[:, 1])
    return np.cos(el) * np.sin(az)


def sd_f(D: np.ndarray, w: np.ndarray, sel: np.ndarray | None = None) -> np.ndarray:
    """SD(f) = sqrt(sum_θ w_θ D² / sum_θ w_θ) por frecuencia. D: (direcciones, frecuencias)."""
    if sel is not None:
        D, w = D[sel], w[sel]
    return np.sqrt((w[:, None] * D**2).sum(axis=0) / w.sum())


def notch(f: np.ndarray, db: np.ndarray, banda: tuple = BANDA_NOTCH) -> dict:
    """Mínimo de la magnitud en dB en la banda del notch, con interpolación parabólica. Si cae en
    el borde, se repite con la banda extendida (BANDA_NOTCH_EXTENDIDA) y se reporta aparte."""
    k = np.where((f >= banda[0]) & (f <= banda[1]))[0]
    i = k[np.argmin(db[k])]
    r = {"f_muestra_hz": float(f[i]), "db_muestra": float(db[i]), "interior": bool(k[0] < i < k[-1])}
    if r["interior"]:
        y0, y1, y2 = db[i - 1], db[i], db[i + 1]
        d = 0.5 * (y0 - y2) / (y0 - 2 * y1 + y2)
        paso = f[i + 1] - f[i]
        r |= {"f_notch_hz": float(f[i] + d * paso), "db_notch": float(y1 - 0.25 * (y0 - y2) * d)}
    else:
        r |= {"f_notch_hz": None, "db_notch": None,
              "nota": "el mínimo cae en el borde de la banda: no hay notch interior"}
    # todos los mínimos locales de la banda, con su profundidad respecto de los máximos vecinos
    locales = []
    for j in k[1:-1]:
        if db[j] < db[j - 1] and db[j] < db[j + 1]:
            izq, der = db[k[0]:j + 1].max(), db[j:k[-1] + 1].max()
            locales.append({"f_hz": float(f[j]), "db": float(db[j]), "profundidad_db": float(min(izq, der) - db[j])})
    r["minimos_locales"] = locales
    if r["interior"]:
        r["profundidad_db"] = next((m["profundidad_db"] for m in locales if m["f_hz"] == r["f_muestra_hz"]), None)
    elif banda == BANDA_NOTCH:
        r["banda_extendida"] = notch(f, db, BANDA_NOTCH_EXTENDIDA)
    return r


def aristas(e: str, canal: np.ndarray) -> dict:
    """Distribución de la arista más larga de cada cara, en toda la malla y fuera de la oreja
    (fuera de la esfera de RADIO_OREJA_MM alrededor del canal), y su fracción cerca del tope -y."""
    import trimesh
    m = trimesh.load(BARRIDO / f"e_{e}" / f"3Dmesh_graded_left_e{e}.ply", process=False)
    mx = m.edges_unique_length[m.faces_unique_edges].max(axis=1)
    area = m.area_faces
    oreja = np.linalg.norm(m.triangles_center - canal, axis=1) < RADIO_OREJA_MM

    def resumen(sel):
        a = area[sel]
        return {"caras": int(sel.sum()), "mediana_mm": float(np.median(mx[sel])),
                "p90_mm": float(np.percentile(mx[sel], 90)), "max_mm": float(mx[sel].max()),
                "fraccion_caras_cerca_del_tope": float((mx[sel] >= CERCA_TOPE_MM).mean()),
                "fraccion_area_cerca_del_tope": float(a[mx[sel] >= CERCA_TOPE_MM].sum() / a.sum())}
    return {"toda": resumen(np.ones(len(mx), bool)), "fuera_de_la_oreja": resumen(~oreja), "oreja": resumen(oreja),
            "fraccion_area_oreja": float(area[oreja].sum() / area.sum())}


def notches_validos(f: np.ndarray, db: np.ndarray) -> list[dict]:
    """Todos los notches bien definidos de una curva en BANDA_BUSQUEDA: mínimo local interior con
    prominencia >= PROFUNDIDAD_MIN_DB (contra el máximo a cada lado dentro de la banda) y anchura a
    media prominencia <= ANCHURA_MAX_HZ. Frecuencia por interpolación parabólica en dB."""
    k = np.where((f >= BANDA_BUSQUEDA[0]) & (f <= BANDA_BUSQUEDA[1]))[0]
    i0, i1 = k[0], k[-1]
    res = []
    for j in k[1:-1]:
        if not (db[j] < db[j - 1] and db[j] <= db[j + 1]):
            continue
        prof = min(db[i0:j + 1].max(), db[j:i1 + 1].max()) - db[j]
        if prof < PROFUNDIDAD_MIN_DB:
            continue
        mitad = db[j] + prof / 2
        a = j
        while db[a] < mitad:
            a -= 1
        b = j
        while db[b] < mitad:
            b += 1
        fl = f[a] + (mitad - db[a]) * (f[a + 1] - f[a]) / (db[a + 1] - db[a])
        fr = f[b - 1] + (mitad - db[b - 1]) * (f[b] - f[b - 1]) / (db[b] - db[b - 1])
        if fr - fl > ANCHURA_MAX_HZ:
            continue
        y0, y1, y2 = db[j - 1], db[j], db[j + 1]
        d = 0.5 * (y0 - y2) / (y0 - 2 * y1 + y2) if (y0 - 2 * y1 + y2) != 0 else 0.0
        res.append({"f_hz": float(f[j] + d * (f[j + 1] - f[j])), "profundidad_db": float(prof), "anchura_hz": float(fr - fl)})
    return res


def notch_distribucion(f: np.ndarray, db_ref: np.ndarray, db_e: np.ndarray, sel: np.ndarray) -> dict:
    """Corrimiento del primer notch por dirección. En la referencia: el notch válido de menor
    frecuencia dentro de BANDA_NOTCH. En la condición: el notch válido más cercano a ese, a no más
    de EMPAREJAR_MAX_HZ (puede salir de 5-11 kHz: por eso se busca en BANDA_BUSQUEDA)."""
    corr, sin_ref = [], 0
    prof_sobreviven, prof_perdidas = [], []      # profundidad en la REFERENCIA de cada notch
    cambio_prof = []                             # profundidad en la condición menos en la referencia
    for d in np.where(sel)[0]:
        r = [n for n in notches_validos(f, db_ref[d]) if BANDA_NOTCH[0] <= n["f_hz"] <= BANDA_NOTCH[1]]
        if not r:
            sin_ref += 1
            continue
        fr = r[0]["f_hz"]
        c = [n for n in notches_validos(f, db_e[d]) if abs(n["f_hz"] - fr) <= EMPAREJAR_MAX_HZ]
        if not c:
            prof_perdidas.append(r[0]["profundidad_db"])
            continue
        prof_sobreviven.append(r[0]["profundidad_db"])
        par = min(c, key=lambda n: abs(n["f_hz"] - fr))
        corr.append(par["f_hz"] - fr)
        cambio_prof.append(par["profundidad_db"] - r[0]["profundidad_db"])
    corr = np.array(corr)
    cp = np.array(cambio_prof)
    qp = np.percentile(cp, [10, 25, 50, 75, 90]) if len(cp) else [None] * 5
    q = np.percentile(corr, [10, 25, 50, 75, 90]) if len(corr) else [None] * 5

    def profundidades(v):
        v = np.array(v)
        if not len(v):
            return {"n": 0}
        p = np.percentile(v, [25, 50, 75])
        return {"n": int(len(v)), "q1_db": float(p[0]), "mediana_db": float(p[1]), "q3_db": float(p[2]),
                "fraccion_marginal": float((v < MARGINAL_DB).mean())}
    con_ref = len(corr) + len(prof_perdidas)
    return {"direcciones": int(sel.sum()), "validas": int(len(corr)), "sin_notch_en_la_referencia": sin_ref,
            "sin_notch_emparejado": len(prof_perdidas),
            "fraccion_perdidas": len(prof_perdidas) / con_ref if con_ref else None,
            "mediana_hz": q[2], "q1_hz": q[1], "q3_hz": q[3], "p10_hz": q[0], "p90_hz": q[4],
            "mediana_abs_hz": float(np.median(np.abs(corr))) if len(corr) else None,
            "cambio_profundidad_db": {"mediana": qp[2], "q1": qp[1], "q3": qp[3], "p10": qp[0], "p90": qp[4],
                                      "fraccion_pierde_mas_de_3db": float((cp < -3).mean()) if len(cp) else None,
                                      "mediana_relativa": float(np.median(cp / np.array(prof_sobreviven))) if len(cp) else None},
            "profundidad_referencia_sobreviven": profundidades(prof_sobreviven),
            "profundidad_referencia_perdidas": profundidades(prof_perdidas),
            "corrimientos_hz": [float(x) for x in corr]}


def malla_graduada(e: str) -> Path:
    return BARRIDO / f"e_{e}" / f"3Dmesh_graded_left_e{e}.ply"


def codo(f: np.ndarray, s: np.ndarray, ventana: tuple) -> dict:
    """Codo de SD(f): recta con un quiebre (bisagra) ajustada por mínimos cuadrados en la ventana."""
    k = (f >= ventana[0]) & (f <= ventana[1])
    x, y = f[k], s[k]
    mejor = None
    for fb in x[2:-2]:
        X = np.column_stack([np.ones_like(x), x, np.maximum(0, x - fb)])
        c = np.linalg.lstsq(X, y, rcond=None)[0]
        sse = float(((X @ c - y) ** 2).sum())
        if mejor is None or sse < mejor[0]:
            mejor = (sse, fb, c[1], c[1] + c[2])
    return {"ventana_hz": list(ventana), "codo_hz": float(mejor[1]),
            "pendiente_antes_db_por_khz": float(mejor[2] * 1000), "pendiente_despues_db_por_khz": float(mejor[3] * 1000)}


def cruce_fmm(e: str) -> dict:
    """Frecuencia por debajo de la cual NumCalc pasa forzosamente a FMM de un nivel.

    NC_Addresses.cpp:65-96 (2022): con dLamdBeL = waveLength_/diameterBE_, si dLamdBeL > 1,0 usa FMM
    de un nivel; si no, estima el número de niveles (y si sale 1, también un nivel). diameterBE_ es la
    diagonal de la caja envolvente de los nodos de la malla de contorno, sin la rejilla de evaluación
    (NC_Input.cpp:667-701), y NumCalc la imprime en NC.out. Por tanto f* = c / D: por debajo de f*
    el cambio es forzoso; por encima el multinivel es posible, no seguro.
    Se contrasta con lo observado: el método que NC.out declara en cada paso y el salto de la RAM
    estimada (Memory.txt de -estimate_ram)."""
    import re
    src = FASE2 / f"e_{e}" / "NumCalc" / "source_1"
    texto = (src / "NC1-1.out").read_text(encoding="utf-8", errors="replace")
    d = float(re.search(r"Diameter of the BE-mesh \.+ = ([\d.eE+-]+)", texto).group(1))
    c = float(re.search(r"Sound speed \.+ = ([\d.eE+-]+)", texto).group(1))
    metodos = {}
    for ruta in src.glob("NC*.out"):
        for m in re.finditer(r"Step \d+, Frequency = ([\d.eE+-]+) Hz\s*\n\s*\n(Single|Direct|Traditional) ",
                             ruta.read_text(encoding="utf-8", errors="replace")):
            metodos[float(m.group(1))] = {"Single": "un nivel", "Direct": "multinivel", "Traditional": "BEM tradicional"}[m.group(2)]
    r = {"diametro_m": d, "c_ms": c, "f_cruce_hz": c / (d * UMBRAL_FMM1),
         "metodo_en_la_fase2": sorted(set(metodos.values())), "pasos_con_metodo": len(metodos),
         "primera_frecuencia_fase2_hz": min(metodos)}
    nodos = np.loadtxt(FASE2 / f"e_{e}" / "ObjectMeshes" / "Reference" / "Nodes.txt", skiprows=1, usecols=(1, 2, 3))
    r["y_min_mm"], r["y_max_mm"] = float(nodos[:, 1].min() * 1000), float(nodos[:, 1].max() * 1000)
    mem = CRUCE_FMM / f"e_{e}" / "Memory.txt"
    if mem.exists():
        filas = [(float(a), float(b)) for _, a, b in (l.split() for l in mem.read_text().splitlines() if l.strip())]
        for (f0, g0), (f1, g1) in zip(filas, filas[1:]):
            if g1 != g0:
                r["salto_ram"] = {"ultima_frecuencia_antes_hz": f0, "ram_antes_gb": g0,
                                  "primera_frecuencia_despues_hz": f1, "ram_despues_gb": g1}
                break
    return r


def leer_json(ruta: Path):
    return json.loads(ruta.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- figuras

def estilo(ax, xlog: bool = False) -> None:
    ax.set_facecolor(FONDO)
    ax.grid(True, color=REJILLA, linewidth=0.6)
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(EJE)
    ax.tick_params(colors=TINTA_2, labelsize=8.5)
    ax.xaxis.label.set_color(TINTA_2)
    ax.yaxis.label.set_color(TINTA_2)
    if xlog:
        ax.set_xscale("log")
        ticks = [1000, 2000, 4000, 8000, 16000]
        ax.set_xticks(ticks)
        ax.set_xticklabels([f"{t // 1000}" for t in ticks])
        ax.minorticks_off()
        ax.set_xlabel("frecuencia (kHz)")


def figura(ancho: float, alto: float, n: int = 1, **kw):
    fig, ejes = plt.subplots(1, n, figsize=(ancho, alto), facecolor=FONDO, **kw)
    return fig, (np.atleast_1d(ejes) if n > 1 else ejes)


def titular(fig, titulo: str, subtitulo: str) -> None:
    fig.text(0.01, 0.985, titulo, ha="left", va="top", fontsize=11.5, color=TINTA, weight="bold")
    fig.text(0.01, 0.935, subtitulo, ha="left", va="top", fontsize=8.5, color=TINTA_2)


def rotular_final(ax, x, y, e: str, dy: float = 0.0) -> None:
    """Etiqueta directa al final de la curva, en tinta de texto con un trazo del color de la serie."""
    ok = ~np.isnan(y)
    ax.annotate(etiqueta(e), (x[ok][-1], y[ok][-1] + dy), xytext=(6, 0), textcoords="offset points",
                va="center", fontsize=8, color=TINTA_2)


def guardar(fig, nombre: str) -> str:
    ruta = SALIDA / "figuras" / nombre
    fig.savefig(ruta, dpi=300, facecolor=FONDO)
    plt.close(fig)
    return f"figuras/{nombre}"


def lineas_umbral(ax, x_texto: float) -> None:
    for u in (1.0, 2.0, 3.0):
        ax.axhline(u, color=TENUE, linewidth=0.8, linestyle=(0, (4, 3)), zorder=1)
        ax.text(x_texto, u, f" {u:g} dB", va="bottom", ha="left", fontsize=7.5, color=TENUE)


# ---------------------------------------------------------------- principal

def principal() -> None:
    (SALIDA / "figuras").mkdir(parents=True, exist_ok=True)
    progreso = leer_json(FASE2 / "progreso.json")["condiciones"]
    geometria = leer_json(BARRIDO / "fase1" / "geometria.json")["e"]

    # frecuencias excluidas: las que no convergieron en alguna condición
    divergidas = {e: sorted(r["frecuencia_hz"] for r in progreso[e]["pasos"].values() if r["estado"] == "no convergió")
                  for e in TODAS}
    sin_resultado = {e: [k for k, r in progreso[e]["pasos"].items() if r["estado"] == "sin resultado"] for e in TODAS}
    if any(sin_resultado.values()) or any(progreso[e]["estado"] != "completa" for e in TODAS):
        raise SystemExit(f"hay condiciones incompletas: {sin_resultado}")
    excluidas = sorted(set().union(*divergidas.values()))

    datos = {g: {e: cargar(e, g) for e in TODAS} for g in ("Default", "ARI")}
    for g, d in datos.items():
        for e in TODAS:
            if not (np.array_equal(d[e]["f"], d[REF]["f"]) and np.allclose(d[e]["pos"], d[REF]["pos"])):
                raise SystemExit(f"{g}: -e {e} no tiene las mismas frecuencias o direcciones que la referencia")
    # coherencia con los SOFA de diagnóstico marcados en la fase 2
    marcado = sf.read_sofa(str(FASE2 / "sofa" / "HRTF_Default_e1.sofa"), verify=False)
    nan_marcado = sorted(float(x) for x in np.asarray(marcado.N)[np.isnan(np.asarray(marcado.Data_Real)).all(axis=(0, 1))])
    if nan_marcado != excluidas:
        raise SystemExit(f"los SOFA marcados tienen NaN en {nan_marcado} y progreso.json dice {excluidas}")

    D0 = datos["Default"]
    f = D0[REF]["f"]
    comunes = ~np.isin(f, excluidas)
    fc = f[comunes]
    pos = D0[REF]["pos"]
    w = pesos_voronoi(pos)
    uno = np.ones(len(pos))
    y = lateral(pos)
    ipsi, contra = y > LATERAL_MIN, y < -LATERAL_MIN
    i_ipsi = int(np.argmin(np.abs(pos[:, 0] - 90) + np.abs(pos[:, 1])))
    banda = (fc >= BANDA_SD[0]) & (fc <= BANDA_SD[1])

    metricas = {"generado": datetime.now().astimezone().isoformat(timespec="seconds"),
                "referencia": REF, "rejilla_principal": "Default", "direcciones": int(len(pos)),
                "direcciones_ipsilaterales": int(ipsi.sum()), "direcciones_contralaterales": int(contra.sum()),
                "direcciones_plano_medio": int((~ipsi & ~contra).sum()),
                "frecuencias_total": int(len(f)), "frecuencias_excluidas_hz": excluidas,
                "frecuencias_comunes": int(comunes.sum()), "divergidas_por_condicion_hz": divergidas,
                "banda_sd_hz": BANDA_SD, "banda_notch_hz": BANDA_NOTCH,
                "direccion_ipsilateral": {"indice": i_ipsi, "azimut": float(pos[i_ipsi, 0]), "elevacion": float(pos[i_ipsi, 1])},
                "condiciones": {},
                "cruce_fmm": {e: cruce_fmm(e) for e in TODAS},
                "cruce_fmm_biseccion": leer_json(CRUCE_FMM / "biseccion" / "resumen.json")
                if (CRUCE_FMM / "biseccion" / "resumen.json").exists() else None}

    sdf = {}
    for e in COMPARADAS:
        D = (D0[e]["db"] - D0[REF]["db"])[:, comunes]
        s_all, s_ipsi, s_contra = sd_f(D, w), sd_f(D, w, ipsi), sd_f(D, w, contra)
        s_sin_peso = sd_f(D, uno)
        s_theta = np.sqrt((D**2).mean(axis=1))
        A = datos["ARI"]
        s_ari = sd_f((A[e]["db"] - A[REF]["db"])[:, comunes], np.ones(len(A[REF]["pos"])))
        sdf[e] = {"todas": s_all, "ipsi": s_ipsi, "contra": s_contra, "theta": s_theta}
        metricas["condiciones"][e] = {
            "sd_media_4_16khz_db": float(s_all[banda].mean()),
            "sd_media_4_16khz_ipsilateral_db": float(s_ipsi[banda].mean()),
            "sd_media_4_16khz_contralateral_db": float(s_contra[banda].mean()),
            "sd_media_4_16khz_sin_ponderar_db": float(s_sin_peso[banda].mean()),
            "sd_media_4_16khz_rejilla_ari_sin_ponderar_db": float(s_ari[banda].mean()),
            "sd_media_todas_las_comunes_db": float(s_all.mean()),
            "sd_bandas_db": {b: {h: float(s[(fc >= lo) & (fc <= hi)].mean())
                                 for h, s in (("todas", s_all), ("ipsilateral", s_ipsi), ("contralateral", s_contra))}
                             for b, (lo, hi) in BANDAS_SD.items()},
            "sd_f_maxima_db": float(s_all.max()), "f_de_sd_maxima_hz": float(fc[np.argmax(s_all)]),
            "sd_theta": {"mediana_db": float(np.median(s_theta)), "p95_db": float(np.percentile(s_theta, 95)),
                         "maxima_db": float(s_theta.max()),
                         "direccion_maxima": {"azimut": float(pos[np.argmax(s_theta), 0]), "elevacion": float(pos[np.argmax(s_theta), 1])},
                         "ipsilateral_90_0_db": float(s_theta[i_ipsi])},
        }

    notches = {e: notch(f, D0[e]["db"][i_ipsi]) for e in TODAS}
    for e in TODAS:
        metricas["condiciones"].setdefault(e, {})["notch"] = notches[e]
    f_ref = notches[REF]["f_notch_hz"]
    for e in COMPARADAS:
        fe = notches[e]["f_notch_hz"]
        corr = None if (fe is None or f_ref is None) else fe - f_ref
        metricas["condiciones"][e]["corrimiento_notch_hz"] = corr
        metricas["condiciones"][e]["corrimiento_notch_fraccion_di_giusto"] = None if corr is None else abs(corr) / (DI_GIUSTO_KHZ * 1000)
        ext = notches[e].get("banda_extendida", {})
        if ext.get("f_notch_hz") is not None and f_ref is not None:
            metricas["condiciones"][e]["corrimiento_notch_banda_extendida_hz"] = ext["f_notch_hz"] - f_ref

    # forma de SD(f): valores en puntos fijos y si sube con la frecuencia
    for e in COMPARADAS:
        s = sdf[e]["todas"]
        k = (fc >= BANDA_SD[0]) & (fc <= BANDA_SD[1])
        dif = np.diff(s[k])
        metricas["condiciones"][e]["forma_sd"] = {
            "sd_en_puntos_db": {f"{p:.0f}": float(np.interp(p, fc, s)) for p in SD_PUNTOS_HZ},
            "fraccion_de_pasos_que_suben_4_16khz": float((dif > 0).mean()),
            "correlacion_rangos_con_f_4_16khz": float(np.corrcoef(np.argsort(np.argsort(fc[k])), np.argsort(np.argsort(s[k])))[0, 1]),
        }

    # aristas de las mallas graduadas y elementos por longitud de onda
    canal = np.array(leer_json(BARRIDO / "fase1" / "geometria.json")["canal_izq_mm"])
    from malla.discretizacion import predecir_archivo, frecuencia_util_hz
    for e in TODAS:
        a = aristas(e, canal)
        a["prediccion_frecuencia_util"] = predecir_archivo(malla_graduada(e), canal)
        a["elementos_por_longitud_de_onda"] = {
            f"{p:.0f}": {"oreja": float(C_MS / p * 1000 / a["oreja"]["mediana_mm"]),
                         "fuera_de_la_oreja": float(C_MS / p * 1000 / a["fuera_de_la_oreja"]["mediana_mm"]),
                         "arista_tope_y": float(C_MS / p * 1000 / GRADING_Y_MM)} for p in SD_PUNTOS_HZ}
        metricas["condiciones"][e]["aristas"] = a

    # f_util = c / (6 · arista mediana fuera de la oreja) frente a la subida medida de SD(f).
    # El detector de codo es exploratorio: se reportan dos ventanas porque el resultado depende de ella.
    pred = {e: metricas["condiciones"][e]["aristas"]["prediccion_frecuencia_util"]["resto_de_la_cabeza"]["frecuencia_util_hz"] for e in TODAS}
    orden_pred = sorted(COMPARADAS, key=lambda e: pred[e])
    umbral_subida = {e: next((float(x) for x, v in zip(fc, sdf[e]["todas"]) if v >= 1.0), None) for e in COMPARADAS}
    metricas["frecuencia_util"] = {
        "formula": "f = c / (6 · mediana de la arista más larga de cada cara, fuera de la esfera de 40 mm de la oreja)",
        "prediccion_hz": pred,
        "codos_medidos": {e: [codo(fc, sdf[e]["todas"], (4000.0, 20000.0)), codo(fc, sdf[e]["todas"], (4000.0, 16000.0))] for e in COMPARADAS},
        "primera_frecuencia_con_sd_1db_hz": umbral_subida,
        "orden_predicho": orden_pred,
        "orden_de_la_subida_a_1db": sorted(COMPARADAS, key=lambda e: umbral_subida[e] or 1e9),
    }

    # notch sobre todas las direcciones
    metricas["notch_criterio"] = {"banda_del_primer_notch_hz": BANDA_NOTCH, "banda_de_busqueda_hz": BANDA_BUSQUEDA,
                                  "profundidad_min_db": PROFUNDIDAD_MIN_DB, "anchura_max_hz": ANCHURA_MAX_HZ,
                                  "emparejamiento_max_hz": EMPAREJAR_MAX_HZ}
    for e in COMPARADAS:
        metricas["condiciones"][e]["notch_distribucion"] = {
            "todas": notch_distribucion(f, D0[REF]["db"], D0[e]["db"], np.ones(len(pos), bool)),
            "ipsilateral": notch_distribucion(f, D0[REF]["db"], D0[e]["db"], ipsi)}

    # costo y geometría (medidos en las fases 1 y 2)
    for e in TODAS:
        pasos = progreso[e]["pasos"].values()
        corridas = progreso[e]["corridas"]
        g = geometria[e]
        metricas["condiciones"][e] |= {
            "caras": g["caras"], "vertices": g["vertices"],
            "arista_oreja_media_mm": g["aristas_oreja"]["media_mm"], "arista_oreja_mediana_mm": g["aristas_oreja"]["mediana_mm"],
            "hausdorff_pina_rms_mm": max(g["hausdorff_oreja_original_a_graduada"]["rms_mm"], g["hausdorff_oreja_graduada_a_original"]["rms_mm"]),
            "hausdorff_pina_max_mm": max(g["hausdorff_oreja_original_a_graduada"]["max_mm"], g["hausdorff_oreja_graduada_a_original"]["max_mm"]),
            "frecuencias_divergidas": len(divergidas[e]),
            "ram_pico_proceso_gb": max(r["ram_pico_proceso_gb"] for r in pasos if r.get("ram_pico_proceso_gb") is not None),
            "ram_pico_suma_numcalc_gb": max(c.get("ram_pico_suma_numcalc_gb", 0) for c in corridas),
            "tiempo_pared_h": sum(c.get("horas_reales", 0) for c in corridas),
            "tiempo_suma_frecuencias_h": sum(r["minutos"] for r in pasos) / 60,
            "iteraciones_medianas": float(np.median([r["iteraciones"] for r in pasos])),
        }

    # análisis secundario: 78 frecuencias, solo condiciones que convergieron en todas
    completas = [e for e in TODAS if not divergidas[e]]
    tope = np.isin(f, excluidas)
    vecinas = (f >= 20000) & (f < min(excluidas)) if excluidas else np.zeros_like(f, bool)
    secundario = {"condiciones": completas, "frecuencias_tope_hz": excluidas, "vecinas_hz": [float(x) for x in f[vecinas]], "por_condicion": {}}
    sd78 = {}
    for e in [c for c in completas if c != REF]:
        s = sd_f(D0[e]["db"] - D0[REF]["db"], w)
        sd78[e] = s
        # la SD crece con la frecuencia: el tope se compara con la recta ajustada a las vecinas,
        # y el residuo se mide en desviaciones típicas de los residuos de esas vecinas
        a, b = np.polyfit(f[vecinas], s[vecinas], 1)
        dev = (s[vecinas] - (a * f[vecinas] + b)).std(ddof=2)
        previsto = a * f[tope] + b
        secundario["por_condicion"][e] = {
            "sd_tope_db": {f"{x:.0f}": float(v) for x, v in zip(f[tope], s[tope])},
            "sd_tope_prevista_por_tendencia_db": {f"{x:.0f}": float(p) for x, p in zip(f[tope], previsto)},
            "pendiente_vecinas_db_por_khz": float(a * 1000), "desv_residuos_vecinas_db": float(dev),
            "z_tope": {f"{x:.0f}": float((v - p) / dev) for x, v, p in zip(f[tope], s[tope], previsto)},
        }
    for e in completas:
        it = {int(k): r["iteraciones"] for k, r in progreso[e]["pasos"].items()}
        secundario["por_condicion"].setdefault(e, {})["iteraciones_tope"] = {f"{f[k - 1]:.0f}": it[k] for k in range(1, len(f) + 1) if tope[k - 1]}
        secundario["por_condicion"][e]["iteraciones_vecinas"] = [it[k] for k in range(1, len(f) + 1) if vecinas[k - 1]]
    metricas["secundario_78_frecuencias"] = secundario

    # decisión (PROVISIONAL)
    # El umbral sale de simular dos capturas del mismo sujeto (mismo -e) y medir la SD entre ellas:
    # está en dB, como la tabla. La elección se da por intervalos del umbral.
    sd = {e: metricas["condiciones"][e]["sd_bandas_db"][BANDA_DECISION]["todas"] for e in COMPARADAS}
    cortes = sorted(sd.items(), key=lambda kv: kv[1])
    intervalos, previo, abajo = [], 0.0, REF
    for e, v in cortes:
        intervalos.append({"desde_db": previo, "hasta_db": v, "eleccion": abajo})
        previo = v
        abajo = max([x for x in COMPARADAS if sd[x] <= v], key=float)
    intervalos.append({"desde_db": previo, "hasta_db": None, "eleccion": abajo})
    decision = {"nota": "umbral pendiente: SD en 4-11 kHz entre dos capturas KIRI del mismo sujeto, graduadas con el mismo -e y simuladas",
                "banda_hz": BANDAS_SD[BANDA_DECISION],
                "intervalos_sd": intervalos,
                "por_umbral_sd": [{"umbral_db": u, "eleccion": max([e for e in COMPARADAS if sd[e] < u], key=float, default=REF)}
                                  for u in UMBRALES_SD_DB]}
    perdidas = {e: metricas["condiciones"][e]["notch_distribucion"]["todas"]["fraccion_perdidas"] for e in COMPARADAS}
    im, previo, abajo = [], 0.0, REF
    for e, v in sorted(perdidas.items(), key=lambda kv: kv[1]):
        im.append({"desde": previo, "hasta": v, "eleccion": abajo})
        previo, abajo = v, max([x for x in COMPARADAS if perdidas[x] <= v], key=float)
    im.append({"desde": previo, "hasta": None, "eleccion": abajo})
    decision["intervalos_muescas"] = im
    decision["regla"] = "el -e más grande por debajo del umbral en ambos criterios (SD 4-11 kHz y muescas perdidas)"
    decision["umbrales_sd_que_eligen_e1"] =[d["umbral_db"] for d in decision["por_umbral_sd"] if d["eleccion"] == "1"]
    decision["intervalo_que_elige_e1"] = next(([i["desde_db"], i["hasta_db"]] for i in intervalos if i["eleccion"] == "1"), None)
    metricas["decision_provisional"] = decision

    # ---------------------------------------------------------------- tablas
    with open(SALIDA / "tabla_decision.csv", "w", newline="", encoding="utf-8-sig") as fh:
        wr = csv.writer(fh)
        wr.writerow(["e", "caras", "arista_oreja_media_mm", "arista_fuera_oreja_mediana_mm", "area_cerca_tope_y",
                     "hausdorff_pina_rms_mm", "hausdorff_pina_max_mm", "sd_media_4_16khz_db", "sd_ipsilateral_db",
                     "sd_contralateral_db", "notch_corrimiento_mediana_hz", "notch_q1_hz", "notch_q3_hz",
                     "notch_direcciones_validas", "frecuencias_divergidas", "ram_pico_proceso_gb",
                     "ram_pico_suma_numcalc_gb", "tiempo_pared_h", "tiempo_suma_frecuencias_h"])
        for e in TODAS:
            c = metricas["condiciones"][e]
            nd = c.get("notch_distribucion", {}).get("todas", {})
            wr.writerow([e, c["caras"], c["arista_oreja_media_mm"], round(c["aristas"]["fuera_de_la_oreja"]["mediana_mm"], 3),
                         round(c["aristas"]["toda"]["fraccion_area_cerca_del_tope"], 4),
                         c["hausdorff_pina_rms_mm"], c["hausdorff_pina_max_mm"],
                         c.get("sd_media_4_16khz_db", 0.0), c.get("sd_media_4_16khz_ipsilateral_db", 0.0),
                         c.get("sd_media_4_16khz_contralateral_db", 0.0), nd.get("mediana_hz", 0.0), nd.get("q1_hz", 0.0),
                         nd.get("q3_hz", 0.0), nd.get("validas", ""), c["frecuencias_divergidas"], c["ram_pico_proceso_gb"],
                         c["ram_pico_suma_numcalc_gb"], round(c["tiempo_pared_h"], 3), round(c["tiempo_suma_frecuencias_h"], 3)])
    with open(SALIDA / "sd_f.csv", "w", newline="", encoding="utf-8-sig") as fh:
        wr = csv.writer(fh)
        wr.writerow(["frecuencia_hz"] + [f"sd_{h}_e{e}_db" for e in COMPARADAS for h in ("todas", "ipsi", "contra")])
        for k, x in enumerate(fc):
            wr.writerow([x] + [round(float(sdf[e][h][k]), 4) for e in COMPARADAS for h in ("todas", "ipsi", "contra")])
    with open(SALIDA / "sd_theta.csv", "w", newline="", encoding="utf-8-sig") as fh:
        wr = csv.writer(fh)
        wr.writerow(["azimut", "elevacion", "peso_voronoi"] + [f"sd_theta_e{e}_db" for e in COMPARADAS])
        for k in range(len(pos)):
            wr.writerow([pos[k, 0], pos[k, 1], float(w[k])] + [round(float(sdf[e]["theta"][k]), 4) for e in COMPARADAS])

    # ---------------------------------------------------------------- figuras
    plt.rcParams.update({"font.family": ["Segoe UI", "DejaVu Sans"], "font.size": 9})
    figs = {}
    sub = f"Referencia -e 0,5 · rejilla Default ({len(pos)} direcciones, ponderadas por área) · {comunes.sum()} frecuencias comunes"

    # 1. SD(f)
    fig, ax = figura(7.2, 4.2)
    estilo(ax, xlog=True)
    for b, (lo, hi) in BANDAS_SD.items():
        ax.axvspan(lo, hi, color=REJILLA, alpha=0.55 if b == BANDA_DECISION else 0.25, linewidth=0, zorder=0)
        ax.text(np.sqrt(lo * hi), 0.02, "4–11 kHz: decide" if b == BANDA_DECISION else "12–16 kHz",
                transform=ax.get_xaxis_transform(), ha="center", va="bottom", fontsize=7.5, color=TENUE)
    for e in COMPARADAS:
        ax.plot(fc, sdf[e]["todas"], color=COLOR[e], linewidth=1.5, label=etiqueta(e))
        rotular_final(ax, fc, sdf[e]["todas"], e)
    lineas_umbral(ax, 900)
    ax.set_xlim(850, 30000)
    ax.set_ylim(bottom=0)
    ax.set_ylabel("SD(f) (dB)")
    ax.legend(frameon=False, fontsize=8, loc="upper left", labelcolor=TINTA_2)
    titular(fig, "Distorsión espectral contra la referencia, por frecuencia",
            sub + "\nLíneas punteadas: umbrales plausibles, PROVISIONALES (el real sale de la repetibilidad de KIRI)")
    fig.subplots_adjust(top=0.80, left=0.08, right=0.97, bottom=0.12)
    figs["sd_f"] = guardar(fig, "1_sd_f.png")

    # 2. SD(f) por hemisferio
    fig, ejes = figura(9.2, 4.0, 2, sharey=True)
    for ax, h, nombre in zip(ejes, ("ipsi", "contra"), (f"Ipsilateral (y > 0, {ipsi.sum()} dir.)", f"Contralateral (y < 0, {contra.sum()} dir.)")):
        estilo(ax, xlog=True)
        for e in COMPARADAS:
            ax.plot(fc, sdf[e][h], color=COLOR[e], linewidth=1.5, label=etiqueta(e))
            rotular_final(ax, fc, sdf[e][h], e)
        ax.set_xlim(850, 32000)
        ax.set_ylim(bottom=0)
        ax.set_title(nombre, fontsize=9.5, color=TINTA, loc="left")
    ejes[0].set_ylabel("SD(f) (dB)")
    ejes[0].legend(frameon=False, fontsize=8, loc="upper left", labelcolor=TINTA_2)
    titular(fig, "Distorsión espectral por hemisferio", sub + " · el plano medio no entra en ninguno")
    fig.subplots_adjust(top=0.80, left=0.07, right=0.97, bottom=0.13, wspace=0.12)
    figs["sd_f_hemisferios"] = guardar(fig, "2_sd_f_hemisferios.png")

    # 3. Magnitud ipsilateral + zoom del notch
    fig, ejes = figura(9.6, 4.2, 2, gridspec_kw={"width_ratios": [1.5, 1]})
    for ax, zoom in zip(ejes, (False, True)):
        estilo(ax, xlog=not zoom)
        for e in TODAS:
            mag = D0[e]["db"][i_ipsi].copy()
            mag[~comunes] = np.nan
            if zoom:
                ax.plot(f / 1000, mag, color=COLOR[e], linewidth=1.5, marker="o", markersize=3, label=etiqueta(e))
            else:
                ax.plot(f, mag, color=COLOR[e], linewidth=1.5, label=etiqueta(e))
        if zoom:
            ax.set_xlim(BANDA_NOTCH[0] / 1000, BANDA_NOTCH[1] / 1000)
            k = (f >= BANDA_NOTCH[0]) & (f <= BANDA_NOTCH[1])
            lo = min(D0[e]["db"][i_ipsi][k].min() for e in TODAS)
            hi = max(D0[e]["db"][i_ipsi][k].max() for e in TODAS)
            ax.set_ylim(lo - 2, hi + 2)
            for e in TODAS:
                n = notches[e]
                if n["f_notch_hz"] is not None:
                    ax.plot(n["f_notch_hz"] / 1000, n["db_notch"], marker="v", markersize=8, color=COLOR[e],
                            markeredgecolor=FONDO, markeredgewidth=1.5, zorder=5)
            ax.set_xlabel("frecuencia (kHz)")
            ax.set_title("Zoom 5–11 kHz · ▼ notch interpolado", fontsize=9.5, color=TINTA, loc="left")
        else:
            ax.set_xlim(850, 25000)
            ax.axvspan(*BANDA_NOTCH, color=REJILLA, alpha=0.35, linewidth=0, zorder=0)
            ax.set_ylabel("|H| (dB)")
            ax.set_title("900 Hz – 23,1 kHz", fontsize=9.5, color=TINTA, loc="left")
            ax.legend(frameon=False, fontsize=8, loc="lower left", labelcolor=TINTA_2)
    titular(fig, "Magnitud en la dirección ipsilateral (azimut 90°, elevación 0°)",
            "Oreja izquierda · HRTF referenciada al centro de la cabeza · frecuencias excluidas sin trazar")
    fig.subplots_adjust(top=0.80, left=0.07, right=0.98, bottom=0.13, wspace=0.18)
    figs["magnitud_ipsilateral"] = guardar(fig, "3_magnitud_ipsilateral.png")

    # 4. SD(θ) en mapa azimut-elevación
    from matplotlib.colors import LinearSegmentedColormap
    mapa = LinearSegmentedColormap.from_list("azul", RAMPA_AZUL)
    vmax = max(float(np.percentile(sdf[e]["theta"], 99)) for e in COMPARADAS)
    azs = np.where(pos[:, 0] > 180, pos[:, 0] - 360, pos[:, 0])
    fig, ejes = figura(11, 3.9, 3, sharey=True)
    for ax, e in zip(ejes, COMPARADAS):
        estilo(ax)
        sc = ax.scatter(azs, pos[:, 1], c=sdf[e]["theta"], cmap=mapa, vmin=0, vmax=vmax, s=9, linewidths=0)
        ax.set_xlim(-182, 182)
        ax.set_xticks([-90, 0, 90])
        ax.set_xlabel("azimut (°) · 90 = izquierda (ipsi.)")
        c = metricas["condiciones"][e]["sd_theta"]
        ax.set_title(f"{etiqueta(e)} · mediana {num(c['mediana_db'])} dB", fontsize=9.5, color=TINTA, loc="left")
    ejes[0].set_ylabel("elevación (°)")
    barra = fig.colorbar(sc, cax=fig.add_axes([0.925, 0.14, 0.012, 0.66]), extend="max")
    barra.set_label("SD(θ) (dB)", color=TINTA_2)
    barra.outline.set_visible(False)
    titular(fig, "Distorsión espectral por dirección", f"Referencia -e 0,5 · promedio sobre las {comunes.sum()} frecuencias comunes · escala común (tope en el percentil 99)")
    fig.subplots_adjust(top=0.80, left=0.05, right=0.9, bottom=0.14, wspace=0.08)
    figs["sd_theta"] = guardar(fig, "4_sd_theta.png")

    # 5. Costo
    xs = [float(e) for e in TODAS]
    fig, ejes = figura(10, 3.6, 3)
    paneles = [("caras", "caras de la malla", False), ("ram_pico_proceso_gb", "RAM pico de una instancia (GB)", False),
               ("tiempo_pared_h", "tiempo de pared (h)", False)]
    for ax, (clave, nombre, ylog) in zip(ejes, paneles):
        estilo(ax)
        ys = [metricas["condiciones"][e][clave] for e in TODAS]
        ax.plot(xs, ys, color=TENUE, linewidth=1, zorder=1)
        for x, yv, e in zip(xs, ys, TODAS):
            ax.plot(x, yv, marker="o", markersize=8, color=COLOR[e], markeredgecolor=FONDO, markeredgewidth=1.5, zorder=3)
            ax.annotate(f"{yv:,.0f}".replace(",", ".") if clave == "caras" else f"{yv:.2f}".replace(".", ","),
                        (x, yv), xytext=(0, 8), textcoords="offset points", ha="center", fontsize=7.5, color=TINTA_2)
        if ylog:
            ax.set_yscale("log")
        else:
            ax.set_ylim(0, max(ys) * 1.2)
        if clave == "caras":
            ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v / 1000:.0f} mil"))
        ax.set_xticks(xs)
        ax.set_xticklabels([x.replace(".", ",") for x in TODAS])
        ax.set_xlabel("-e (mm)")
        ax.set_title(nombre, fontsize=9.5, color=TINTA, loc="left")
    titular(fig, "Costo de cada condición", "Medido: caras (fase 1); RAM y tiempo en la corrida de la fase 2 con manage_numcalc (78 frecuencias, 12 núcleos)")
    fig.subplots_adjust(top=0.76, left=0.06, right=0.98, bottom=0.16, wspace=0.28)
    figs["costo"] = guardar(fig, "5_costo.png")

    # 6. Hausdorff en la pina
    fig, ax = figura(6.2, 3.8)
    estilo(ax)
    for clave, nombre, marca in (("hausdorff_pina_max_mm", "máximo", "s"), ("hausdorff_pina_rms_mm", "RMS", "o")):
        ys = [metricas["condiciones"][e][clave] for e in TODAS]
        ax.plot(xs, ys, color=TINTA_2 if clave.endswith("max_mm") else TENUE, linewidth=1.2, zorder=1)
        for x, yv, e in zip(xs, ys, TODAS):
            ax.plot(x, yv, marker=marca, markersize=7, color=COLOR[e], markeredgecolor=FONDO, markeredgewidth=1.5, zorder=3)
        ax.annotate(nombre, (xs[-1], ys[-1]), xytext=(8, 0), textcoords="offset points", va="center", fontsize=8, color=TINTA_2)
    ax.set_yscale("log")
    ax.set_yticks([0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10])
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}".replace(".", ",")))
    ax.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.set_xticks(xs)
    ax.set_xticklabels([x.replace(".", ",") for x in TODAS])
    ax.set_xlim(0.3, 3.5)
    ax.set_xlabel("-e (mm)")
    ax.set_ylabel("Hausdorff en la pina (mm)")
    titular(fig, "Error geométrico en la pina", "Esfera de 40 mm alrededor del canal izquierdo · el mayor de los dos sentidos · fase 1")
    fig.subplots_adjust(top=0.82, left=0.12, right=0.9, bottom=0.14)
    figs["hausdorff"] = guardar(fig, "6_hausdorff_pina.png")

    # 7. Secundario: 78 frecuencias
    fig, ejes = figura(10, 4.0, 2, gridspec_kw={"width_ratios": [1.5, 1]})
    for ax, zoom in zip(ejes, (False, True)):
        estilo(ax, xlog=not zoom)
        if excluidas:
            ax.axvspan((min(excluidas) - 150) / (1000 if zoom else 1), (max(excluidas) + 150) / (1000 if zoom else 1),
                       color=REJILLA, alpha=0.6, linewidth=0, zorder=0)
        for e, s in sd78.items():
            x = f / 1000 if zoom else f
            ax.plot(x, s, color=COLOR[e], linewidth=1.5, label=etiqueta(e), marker="o" if zoom else None, markersize=3)
            if not zoom:
                rotular_final(ax, f, s, e)
            else:
                v = vecinas
                a_, b_ = np.polyfit(f[v], s[v], 1)
                xt = np.array([f[v][0], f[tope][-1]])
                ax.plot(xt / 1000, a_ * xt + b_, color=COLOR[e], linewidth=0.8, linestyle=(0, (4, 3)))
                ax.plot(f[tope] / 1000, s[tope], linestyle="none", marker="o", markersize=7, color=COLOR[e],
                        markeredgecolor=FONDO, markeredgewidth=1.5, zorder=4)
        if zoom:
            ax.set_xlim(19.8, 24.2)
            ax.set_xlabel("frecuencia (kHz)")
            ax.set_title("Zoom 20–24 kHz · punteada: tendencia de 20,1–23,1 kHz", fontsize=9.5, color=TINTA, loc="left")
            ax.text(np.mean(excluidas) / 1000, 0.02, "tope", transform=ax.get_xaxis_transform(),
                    ha="center", va="bottom", fontsize=7.5, color=TENUE)
        else:
            ax.set_xlim(850, 34000)
            ax.set_ylim(bottom=0)
            ax.set_ylabel("SD(f) (dB)")
            ax.set_title("900 Hz – 24 kHz", fontsize=9.5, color=TINTA, loc="left")
            ax.legend(frameon=False, fontsize=8, loc="upper left", labelcolor=TINTA_2)
    titular(fig, "Análisis secundario: las 78 frecuencias, sin -e 1",
            "Solo las condiciones que convergieron en todas · referencia -e 0,5 · banda gris: 23,4–24 kHz (excluida del principal)")
    fig.subplots_adjust(top=0.80, left=0.07, right=0.97, bottom=0.13, wspace=0.18)
    figs["secundario_78"] = guardar(fig, "7_secundario_78_frecuencias.png")

    # 8. Corrimiento del notch sobre todas las direcciones: mediana, RIC y p10-p90 por condición
    fig, ax = figura(7.6, 3.4)
    estilo(ax)
    ax.axvline(0, color=EJE, linewidth=1, zorder=1)
    ax.axvline(DI_GIUSTO_KHZ * 1000, color=TENUE, linewidth=0.8, linestyle=(0, (4, 3)), zorder=1)
    ax.text(DI_GIUSTO_KHZ * 1000, len(COMPARADAS) - 0.35, " 1,4 kHz: fotogrametría\n frente a láser (Di Giusto 2023)",
            fontsize=7.5, color=TENUE, va="top", ha="left")
    for i, e in enumerate(reversed(COMPARADAS)):
        n = metricas["condiciones"][e]["notch_distribucion"]["todas"]
        ax.plot([n["p10_hz"], n["p90_hz"]], [i, i], color=COLOR[e], linewidth=1.2, zorder=2)
        ax.plot([n["q1_hz"], n["q3_hz"]], [i, i], color=COLOR[e], linewidth=6, solid_capstyle="round", zorder=3, alpha=0.9)
        ax.plot(n["mediana_hz"], i, marker="o", markersize=8, color=FONDO, markeredgecolor=COLOR[e], markeredgewidth=2, zorder=4)
        ax.annotate(f"mediana {num(n['mediana_hz'], 0)} Hz · {n['validas']} de {n['direcciones']} dir.",
                    (n["p90_hz"], i), xytext=(8, 0), textcoords="offset points", va="center", fontsize=8, color=TINTA_2)
    ax.set_yticks(range(len(COMPARADAS)))
    ax.set_yticklabels([etiqueta(e) for e in reversed(COMPARADAS)])
    ax.set_ylim(-0.6, len(COMPARADAS) - 0.2)
    ax.set_xlim(-600, 3300)
    ax.set_xlabel("corrimiento del primer notch frente a -e 0,5 (Hz)")
    titular(fig, "Corrimiento del primer notch, sobre todas las direcciones",
            f"Punto: mediana · barra gruesa: rango intercuartílico · línea: percentiles 10–90 · notch válido: ≥ {num(PROFUNDIDAD_MIN_DB, 0)} dB "
            f"de profundidad y ≤ {num(ANCHURA_MAX_HZ / 1000, 0)} kHz de ancho")
    fig.subplots_adjust(top=0.78, left=0.12, right=0.97, bottom=0.16)
    figs["notch_distribucion"] = guardar(fig, "8_notch_distribucion.png")

    metricas["figuras"] = figs
    (SALIDA / "metricas.json").write_text(json.dumps(metricas, indent=2, ensure_ascii=False), encoding="utf-8")
    escribir_informe(metricas)
    print(f"Listo: {SALIDA}")


# ---------------------------------------------------------------- informe

def num(x, d=2) -> str:
    return "—" if x is None else f"{x:.{d}f}".replace(".", ",")


def seccion_cruce_fmm(cr: dict, bis: dict | None) -> list[str]:
    fs = {e: x["f_cruce_hz"] for e, x in cr.items()}
    L = ["## Límite inferior del vector: el cruce a FMM de un nivel",
         "",
         "El vector de diagnóstico empieza en 900 Hz, y esa frontera queda fijada por una cadena de tres pasos:",
         "",
         "1. **El criterio, leído en el fuente** (`NC_Addresses.cpp:65-96`, fuente de 2022; "
         "`docs/verificacion_numcalc.md`, 3.2 y 3.2b). Si la longitud de onda dividida por el diámetro de la malla de "
         "contorno supera 1,0, NumCalc usa FMM de un nivel en vez de multinivel. Ese diámetro es la diagonal de la caja "
         "envolvente de los nodos de la malla, sin la rejilla de evaluación, y NumCalc lo imprime en NC.out. El cruce "
         "debería caer entonces en f* = c/D.",
         "2. **La predicción, calculada desde la geometría de cada malla** (D recalculado desde `Nodes.txt`, igual al de "
         "NC.out a 6 cifras; c = 343 m/s del NC.inp, sin planos de simetría):",
         "",
         "| -e | D (m) | f* = c/D (Hz) |",
         "|---|---|---|"]
    for e, x in cr.items():
        L.append(f"| {e.replace('.', ',')} | {num(x['diametro_m'], 6)} | {num(x['f_cruce_hz'], 1)} |")
    L.append("")
    if bis:
        b05, b3 = bis["condiciones"]["0.5"], bis["condiciones"]["3"]
        s05 = {k: v for k, v in b05["corridas"].items()}
        a, b = b05["biseccion"]["ultimo_un_nivel_hz"], b05["biseccion"]["primero_multinivel_hz"]
        ra, rb = s05[f"{a:g}"]["ram_estimada_gb"], s05[f"{b:g}"]["ram_estimada_gb"]
        a3, b3_ = b3["biseccion"]["ultimo_un_nivel_hz"], b3["biseccion"]["primero_multinivel_hz"]
        L += [f"3. **La observación, a 1 Hz** (`NumCalc -estimate_ram`, que no resuelve el sistema; una frecuencia por "
              "corrida, sobre copias de los proyectos; `cruce_fmm/biseccion/`). Con -e 0,5, el último paso en un nivel es "
              f"{a:.0f} Hz y el primero en multinivel {b:.0f} Hz (predicho {num(b05['f_predicha_hz'], 1)}). Con -e 3, "
              f"{a3:.0f} y {b3_:.0f} Hz (predicho {num(b3['f_predicha_hz'], 1)}). La predicción es diferencial: los dos "
              f"cruces se separan {bis['diferencial']['observado_hz']:.0f} Hz frente a "
              f"{num(bis['diferencial']['predicho_hz'], 2)} Hz predichos, en el sentido correcto (la malla de menor D cruza "
              f"más arriba). En el mismo hertz salta la memoria: la RAM estimada de -e 0,5 cae de {num(ra)} GB a {a:.0f} Hz "
              f"a {num(rb)} GB a {b:.0f} Hz, {num(ra / rb, 1)} veces menos. Ese salto es el mecanismo de la pared de "
              "memoria que originó este experimento.",
              ""]
    L += ["En todos los puntos de la bisección decidió λ/D > 1. Ningún NC.out trae la tabla de pares de clusters "
          "cancelados, así que la regla del 75 % (`NC_Addresses.cpp:262-283`) no intervino. La estimación del número de "
          "niveles (`NC_Addresses.cpp:803-843`) usa solo el número de elementos y su área media, no la frecuencia, así "
          "que en estas mallas no puede mandar cerca del borde. Queda una precisión: por debajo de f* el nivel único es "
          "forzoso, y por encima el multinivel es posible pero no está garantizado en general; en estas mallas, los otros "
          "dos criterios no lo impiden en la zona del cruce. **Alcance:** verificado para las mallas de este trabajo con "
          "el binario de 2022, no demostrado en general.",
          "",
          f"f* se mueve de {num(min(fs.values()), 1)} a {num(max(fs.values()), 1)} Hz entre condiciones, y no de forma "
          "monótona en -e. El cambio de D está casi entero en la extensión lateral (y): "
          + "; ".join(f"-e {e.replace('.', ',')}: de {num(x['y_min_mm'], 1)} a {num(x['y_max_mm'], 1)} mm"
                      for e, x in cr.items())
          + ". Con -e 3, el punto más lateral del lado de la oreja simulada retrocede y el del lado opuesto avanza. "
          "El corte en 900 Hz queda por encima del cruce en las cuatro condiciones, de modo que el vector entero se "
          "resuelve con el mismo método: NC.out declara multinivel en los 78 pasos de las cuatro condiciones.",
          "",
          "**Detalle operativo:** NumCalc solo escribe el método de un paso si cambió respecto al paso anterior "
          "(`if(ifdiff) NC_FrequencyInformations`, `NC_Main.cpp:383`; `NC_DeclareArrays` devuelve 0, sin imprimir, solo "
          "cuando el método y el número de niveles son los mismos, `NC_Addresses.cpp:125-134`). En una corrida de varias "
          "frecuencias, un paso sin la línea hereda el método del último paso que la tiene. Un análisis que lea el método "
          "paso por paso sin conocer esa regla deja pasos sin método, sin aviso. Por eso la bisección corre una "
          "frecuencia por vez, y en la fase 2 cada frecuencia es un proceso aparte de NumCalc.",
          ""]
    return L


def escribir_informe(m: dict) -> None:
    c = m["condiciones"]
    exc = ", ".join(num(x / 1000, 1) for x in m["frecuencias_excluidas_hz"]) or "ninguna"
    crit = m["notch_criterio"]
    d = m["decision_provisional"]
    L = ["# Barrido de -e — fase 3: análisis",
         "",
         f"Generado {m['generado']} por `experimentos/barrido_e/fase3_analisis.py` (solo lee las fases 1 y 2).",
         "",
         "## Qué es medido y qué es provisional",
         "",
         "- **Medido:** todas las métricas de las tablas (geometría en la fase 1 y en las mallas graduadas; simulación, "
         "RAM y tiempos en la fase 2).",
         "- **Provisional:** la elección de -e, porque falta el umbral (ver «Fase 4»).",
         "- **Limitación de todo el estudio:** la referencia -e 0,5 no representa la verdad, sino la configuración más "
         "fina que esta máquina puede calcular, y en la cabeza no es la más fina del conjunto (su arista mediana por "
         "área fuera de la oreja es 6,9 mm; con -e 1 -y 5 es 4,9 mm). Todas las SD de este informe son diferencias "
         "contra esa referencia, no errores absolutos; lo que la referencia tenga en común con una condición (por "
         "ejemplo, las caras en el tope de -y) no aparece en ninguna SD.",
         "- **Supuestos del método (declarados):** promedio sobre direcciones ponderado por el área de Voronoi de cada "
         "dirección (se reporta también sin ponderar); la «media sobre 4–16 kHz» es la media aritmética de SD(f) en esa "
         "banda; el criterio del notch se describe en su sección.",
         "",
         "## Frecuencias excluidas",
         "",
         f"-e 1 no convergió en {exc} kHz (250 iteraciones, el máximo). Por decisión del autor (2026-09-29) esas "
         f"frecuencias van a NaN en las cuatro condiciones: el análisis principal compara sobre las "
         f"{m['frecuencias_comunes']} frecuencias comunes. No se interpolan ni se sustituyen. Está declarado también en "
         "el GLOBAL_Comment de los SOFA de diagnóstico (`fase2/sofa/`).",
         "",
         *seccion_cruce_fmm(m["cruce_fmm"], m["cruce_fmm_biseccion"]),
         "## Tabla de decisión",
         "",
         "Criterio principal: **SD media en 4–11 kHz** (la banda de la pina). La de 12–16 kHz se reporta como límite "
         "de ancho de banda útil, no decide.",
         "",
         "| -e | caras | Hausdorff pina RMS (mm) | Hausdorff pina máx (mm) | **SD 4–11 kHz (dB)** | SD 4–11 ipsi / contra (dB) | "
         "SD 12–16 kHz (dB) | corrimiento del notch, mediana [RIC] (Hz) | muescas perdidas | f útil predicha, cabeza (kHz) | "
         "frecuencias divergidas | RAM pico (GB) | tiempo de pared (h) |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for e in TODAS:
        x = c[e]
        ref = e == REF
        nd = x.get("notch_distribucion", {}).get("todas")
        notch_txt = "—" if ref else f"{num(nd['mediana_hz'], 0)} [{num(nd['q1_hz'], 0)}, {num(nd['q3_hz'], 0)}]"
        caras = f"{x['caras']:,}".replace(",", ".")
        b = x.get("sd_bandas_db", {})
        fu = x["aristas"]["prediccion_frecuencia_util"]["resto_de_la_cabeza"]["frecuencia_util_hz"]
        L.append(
            f"| {e.replace('.', ',')}{' (ref.)' if ref else ''} | {caras} | {num(x['hausdorff_pina_rms_mm'], 3)}"
            f" | {num(x['hausdorff_pina_max_mm'])} | {'—' if ref else '**' + num(b['4-11']['todas']) + '**'}"
            f" | {'—' if ref else num(b['4-11']['ipsilateral']) + ' / ' + num(b['4-11']['contralateral'])}"
            f" | {'—' if ref else num(b['12-16']['todas'])}"
            f" | {notch_txt} | {'—' if ref else num(100 * nd['fraccion_perdidas'], 0) + ' %'} | {num(fu / 1000, 1)}"
            f" | {x['frecuencias_divergidas']} | {num(x['ram_pico_proceso_gb'])} | {num(x['tiempo_pared_h'])} |")
    L += ["",
          "RAM pico: una instancia de NumCalc (la suma de las instancias simultáneas está en `metricas.json`). Tiempo de "
          "pared: corrida con manage_numcalc en paralelo; la suma de los tiempos por frecuencia (equivalente en serie) está en "
          "`tabla_decision.csv`.",
          "",
          "**Hausdorff máximo contra el -e nominal.** -e acota el error geométrico máximo, no el RMS. En la pina, el máximo "
          "medido es " + "; ".join(f"{num(c[e]['hausdorff_pina_max_mm'])} mm con -e {e.replace('.', ',')} "
                                   f"({num(c[e]['hausdorff_pina_max_mm'] / float(e), 1)} veces el nominal)" for e in TODAS)
          + ". Solo -e 0,5 queda por debajo de su nominal. El Hausdorff de la fase 1 se mide contra la malla de entrada, "
          "muestreada en ambos sentidos, y no tiene por qué coincidir con la métrica interna del gradado.",
          "",
          "## Fase 4: protocolo del umbral y regla de decisión",
          "",
          "La tabla decide en decibelios y la repetibilidad geométrica de KIRI da milímetros; no son convertibles porque "
          "miden fuentes de error distintas. El umbral se mide igual que la tabla: **dos capturas KIRI del mismo sujeto, "
          "graduadas ambas con el mismo -e, simuladas ambas con este mismo protocolo** (vector de diagnóstico, oreja "
          "izquierda, mismo NumCalc), y entre ellas se miden **dos pisos de ruido**:",
          "",
          "1. la SD media en 4–11 kHz;",
          "2. la fracción de muescas que sobreviven (con el criterio de muesca de este informe, tomando una captura "
          "como referencia de la otra).",
          "",
          "**Regla:** se acepta el -e más grande que quede por debajo del umbral en **ambos** criterios: SD en 4–11 kHz "
          "menor que el piso de SD, y fracción de muescas perdidas menor que la que se pierde entre las dos capturas. "
          "La SD sola ignoraría degradaciones como el 16 % de muescas perdidas de -e 2, que en su mayoría es pérdida real.",
          "",
          "**Dos pasadas:**",
          "",
          "1. El par de capturas a -e 2 (unas 0,67 h de simulación cada una): dice el mismo día de qué lado de la ventana "
          "cae el umbral.",
          "2. El par a -e 0,5: el número definitivo, en el mismo pie que la tabla (la referencia es -e 0,5).",
          "",
          "Elección según dónde caiga cada umbral (PROVISIONAL); la final es la menor de las dos:",
          "",
          "| umbral de SD media 4–11 kHz | elección por SD |", "|---|---|"]
    for i in d["intervalos_sd"]:
        hasta = "en adelante" if i["hasta_db"] is None else f"a {num(i['hasta_db'])} dB"
        L.append(f"| de {num(i['desde_db'])} {hasta} | -e {i['eleccion'].replace('.', ',')} |")
    L += ["", "| umbral de muescas perdidas | elección por muescas |", "|---|---|"]
    for i in d["intervalos_muescas"]:
        hasta = "en adelante" if i["hasta"] is None else f"a {num(100 * i['hasta'], 0)} %"
        L.append(f"| de {num(100 * i['desde'], 0)} % {hasta} | -e {i['eleccion'].replace('.', ',')} |")

    # SD por bandas y hemisferio
    L += ["", "## SD por bandas y por hemisferio", "",
          "Media de SD(f) en cada banda (dB). 4–11 kHz: la pina; 12–16 kHz: límite de ancho de banda útil.", "",
          "| -e | 4–11 kHz: todas | 4–11: ipsi | 4–11: contra | 12–16 kHz: todas | 12–16: ipsi | 12–16: contra |",
          "|---|---|---|---|---|---|---|"]
    for e in COMPARADAS:
        b = c[e]["sd_bandas_db"]
        L.append(f"| {e.replace('.', ',')} | " + " | ".join(num(b[k][h]) for k in ("4-11", "12-16")
                                                         for h in ("todas", "ipsilateral", "contralateral")) + " |")

    # muescas perdidas: ¿marginales en la referencia?
    L += ["", "## Muescas perdidas: ¿eran marginales en la referencia?", "",
          f"Profundidad, en la referencia, de los notches que sobreviven (tienen pareja válida en la condición) y de los "
          f"que se pierden. «Marginal»: menos de {num(MARGINAL_DB, 0)} dB, justo por encima del criterio de "
          f"{num(PROFUNDIDAD_MIN_DB, 0)} dB. Si las perdidas fueran marginales, sería ruido de detección; si eran "
          "profundas, destrucción real.", "",
          "| -e | direcciones | perdidas | profundidad de las que sobreviven: mediana [RIC] (dB) | marginales | "
          "profundidad de las perdidas: mediana [RIC] (dB) | marginales |", "|---|---|---|---|---|---|---|"]
    for e in COMPARADAS:
        for sub, nombre in (("todas", "todas"), ("ipsilateral", "ipsilaterales")):
            n = c[e]["notch_distribucion"][sub]
            s_, p_ = n["profundidad_referencia_sobreviven"], n["profundidad_referencia_perdidas"]
            L.append(f"| {e.replace('.', ',')} | {nombre} | {n['sin_notch_emparejado']} de {n['validas'] + n['sin_notch_emparejado']} "
                     f"({num(100 * n['fraccion_perdidas'], 0)} %) | {num(s_['mediana_db'], 1)} [{num(s_['q1_db'], 1)}, {num(s_['q3_db'], 1)}]"
                     f" | {num(100 * s_['fraccion_marginal'], 0)} % | {num(p_['mediana_db'], 1)} [{num(p_['q1_db'], 1)}, {num(p_['q3_db'], 1)}]"
                     f" | {num(100 * p_['fraccion_marginal'], 0)} % |")
    L += ["", "Sin una segunda simulación de la misma malla no se puede medir cuántas pérdidas produce el detector por sí "
          "solo; la fracción marginal es la cota razonable de ese ruido."]

    # frecuencia útil predicha
    fu = m["frecuencia_util"]
    L += ["", "## Frecuencia útil predicha desde las aristas", "",
          "Comprobación previa reutilizable (`malla/discretizacion.py`), sin simular: con h = mediana, sobre las caras fuera "
          "de la esfera de 40 mm de la oreja, de la arista más larga de cada cara,", "",
          "```latex", "f_{\\mathrm{útil}} = \\frac{c}{6\\,h}", "```", "",
          "| -e | h fuera de la oreja (mm) | f útil, cabeza (kHz) | h en la oreja (mm) | f útil, oreja (kHz) | primera f con SD ≥ 1 dB (kHz) | codo de SD(f), ventana 4–20 / 4–16 kHz |",
          "|---|---|---|---|---|---|---|"]
    for e in TODAS:
        p = c[e]["aristas"]["prediccion_frecuencia_util"]
        med = "—" if e == REF else num(fu["primera_frecuencia_con_sd_1db_hz"][e] / 1000, 1)
        cod = "—" if e == REF else " / ".join(num(k["codo_hz"] / 1000, 1) for k in fu["codos_medidos"][e])
        L.append(f"| {e.replace('.', ',')} | {num(p['resto_de_la_cabeza']['arista_mediana_mm'])} | {num(p['resto_de_la_cabeza']['frecuencia_util_hz'] / 1000, 1)}"
                 f" | {num(p['oreja']['arista_mediana_mm'])} | {num(p['oreja']['frecuencia_util_hz'] / 1000, 1)} | {med} | {cod} |")
    L += ["", f"**Verificación: solo el orden.** La fórmula ordena las condiciones igual que la subida medida de la "
          f"distorsión (-e {', '.join(x.replace('.', ',') for x in fu['orden_predicho'])} de menor a mayor frecuencia útil). "
          "Los valores no coinciden: el codo medido depende de la ventana del ajuste y la frecuencia en que SD llega a 1 dB "
          "cae muy por debajo de la predicha. Ningún detector se fijó antes de mirar los datos, así que ninguno cuenta como "
          "validación. Queda escrita como regla práctica (λ/6); la prueba que puede validarla es -e 1 -y 5, que cambia la "
          "arista de la cabeza sin cambiar la de la oreja."]

    # forma de SD(f)
    L += ["", "## Forma de SD(f)", "",
          "SD(f) interpolada linealmente entre las muestras de 300 Hz:", "",
          "| -e | " + " | ".join(f"{num(p / 1000, 0)} kHz" for p in SD_PUNTOS_HZ) + " | pasos que suben en 4–16 kHz |",
          "|---|" + "---|" * (len(SD_PUNTOS_HZ) + 1)]
    for e in COMPARADAS:
        fs = c[e]["forma_sd"]
        L.append(f"| {e.replace('.', ',')} | " + " | ".join(num(fs["sd_en_puntos_db"][f"{p:.0f}"]) for p in SD_PUNTOS_HZ)
                 + f" | {num(100 * fs['fraccion_de_pasos_que_suben_4_16khz'], 0)} % |")
    L += ["", "Elementos por longitud de onda (λ / arista mediana; la regla habitual pide al menos 6):", "",
          "| -e | región | arista mediana (mm) | " + " | ".join(f"{num(p / 1000, 0)} kHz" for p in SD_PUNTOS_HZ) + " |",
          "|---|---|---|" + "---|" * len(SD_PUNTOS_HZ)]
    for e in TODAS:
        a = c[e]["aristas"]
        for region, nombre in (("oreja", "oreja (esfera de 40 mm)"), ("fuera_de_la_oreja", "resto de la cabeza")):
            L.append(f"| {e.replace('.', ',')} | {nombre} | {num(a[region]['mediana_mm'])} | "
                     + " | ".join(num(a["elementos_por_longitud_de_onda"][f"{p:.0f}"][region], 1) for p in SD_PUNTOS_HZ) + " |")
    L.append(f"| — | arista en el tope -y ({num(GRADING_Y_MM, 0)} mm) | {num(GRADING_Y_MM, 0)} | "
             + " | ".join(num(C_MS / p * 1000 / GRADING_Y_MM, 1) for p in SD_PUNTOS_HZ) + " |")

    # aristas y -y
    L += ["", "## Aristas y el tope de -y", "",
          f"Una cara está «cerca del tope» si su arista más larga mide al menos {num(CERCA_TOPE_MM, 0)} mm (0,9 · -y). "
          "Fracción de caras y de área en esa situación:", "",
          "| -e | caras | cerca del tope: caras | cerca del tope: área | fuera de la oreja: arista mediana (mm) | fuera de la oreja, cerca del tope: caras |",
          "|---|---|---|---|---|---|"]
    for e in TODAS:
        a = c[e]["aristas"]
        caras = f"{a['toda']['caras']:,}".replace(",", ".")
        L.append(f"| {e.replace('.', ',')} | {caras}"
                 + f" | {num(100 * a['toda']['fraccion_caras_cerca_del_tope'], 1)} % | {num(100 * a['toda']['fraccion_area_cerca_del_tope'], 1)} %"
                 f" | {num(a['fuera_de_la_oreja']['mediana_mm'])} | {num(100 * a['fuera_de_la_oreja']['fraccion_caras_cerca_del_tope'], 1)} % |")
    L += ["", "-e no actúa solo en la oreja: también engrosa el resto de la cabeza, donde la arista mediana pasa de "
          + " a ".join(num(c[e]["aristas"]["fuera_de_la_oreja"]["mediana_mm"], 1) for e in TODAS)
          + " mm. Así que la SD de cada condición mezcla el cambio en la oreja con el del resto de la cabeza. Lo que sea "
          "común a las cuatro mallas (por ejemplo, las caras que están en el tope de -y en todas) se cancela en la "
          "comparación contra -e 0,5 y este experimento no lo ve."]

    # notch sobre todas las direcciones
    L += ["", "## Primer notch de la pina, sobre todas las direcciones", "",
          f"**Criterio (declarado antes de mirar los corrimientos).** En cada una de las {m['direcciones']} direcciones se "
          f"buscan notches en {num(crit['banda_de_busqueda_hz'][0] / 1000, 0)}–{num(crit['banda_de_busqueda_hz'][1] / 1000, 0)} kHz. "
          f"Un notch es válido si es un mínimo local con profundidad de al menos {num(crit['profundidad_min_db'], 0)} dB "
          f"(frente al máximo a cada lado dentro de la banda) y anchura a media profundidad de a lo sumo "
          f"{num(crit['anchura_max_hz'] / 1000, 0)} kHz; su frecuencia sale de interpolación parabólica en dB. El primer "
          f"notch de la referencia es el válido de menor frecuencia en {num(BANDA_NOTCH[0] / 1000, 0)}–"
          f"{num(BANDA_NOTCH[1] / 1000, 0)} kHz. En la condición se toma el válido más cercano a ese, a no más de "
          f"{num(crit['emparejamiento_max_hz'] / 1000, 0)} kHz. Una dirección cuenta solo si ambos existen.", "",
          "| -e | direcciones | válidas | sin notch en la referencia | sin notch emparejado | mediana (Hz) | RIC (Hz) | p10–p90 (Hz) | mediana de \\|corrimiento\\| (Hz) |",
          "|---|---|---|---|---|---|---|---|---|"]
    for e in COMPARADAS:
        for sub, nombre in (("todas", "todas"), ("ipsilateral", "ipsilaterales")):
            n = c[e]["notch_distribucion"][sub]
            L.append(f"| {e.replace('.', ',')} | {nombre} ({n['direcciones']}) | {n['validas']} | {n['sin_notch_en_la_referencia']}"
                     f" | {n['sin_notch_emparejado']} | {num(n['mediana_hz'], 0)} | {num(n['q1_hz'], 0)} a {num(n['q3_hz'], 0)}"
                     f" | {num(n['p10_hz'], 0)} a {num(n['p90_hz'], 0)} | {num(n['mediana_abs_hz'], 0)} |")
    L += ["", f"Referencia publicada: Di Giusto et al. (2023) atribuyen {num(DI_GIUSTO_KHZ, 1)} kHz de corrimiento del "
          "primer notch a la fotogrametría frente al escaneo láser. «Sin notch emparejado» también es un resultado: el "
          "notch de la referencia no tiene equivalente válido a menos de 2 kHz en la condición (desapareció o se fue lejos).",
          "",
          "### Cambio de profundidad de la muesca",
          "",
          "Misma maquinaria: en cada dirección válida, profundidad del notch emparejado en la condición menos profundidad "
          "en la referencia (dB; negativo = la muesca se aplana). Solo cuenta las muescas que sobreviven: las perdidas "
          "están en la tabla anterior.", "",
          "| -e | direcciones | mediana (dB) | RIC (dB) | p10–p90 (dB) | pierden más de 3 dB | cambio relativo mediano |",
          "|---|---|---|---|---|---|---|"]
    for e in COMPARADAS:
        for sub, nombre in (("todas", "todas"), ("ipsilateral", "ipsilaterales")):
            n = c[e]["notch_distribucion"][sub]
            p = n["cambio_profundidad_db"]
            L.append(f"| {e.replace('.', ',')} | {nombre} ({n['validas']}) | {num(p['mediana'], 2)} | {num(p['q1'], 2)} a {num(p['q3'], 2)}"
                     f" | {num(p['p10'], 1)} a {num(p['p90'], 1)} | {num(100 * p['fraccion_pierde_mas_de_3db'], 0)} % | "
                     f"{num(100 * p['mediana_relativa'], 0)} % |")
    L += ["",
          "La medición anterior en una sola dirección (azimut 90°, elevación 0°) queda reemplazada: ahí el notch es un "
          "valle ancho de unos 2 dB, y su corrimiento (+365 Hz con -e 1) resultó ser un caso atípico frente a la "
          "distribución. Se conserva en `metricas.json` (condiciones → notch) y en la figura 3."]

    # hemisferios
    L += ["", "## Distorsión por hemisferio", "",
          f"Ipsilateral: {m['direcciones_ipsilaterales']} direcciones con y > 0; contralateral: {m['direcciones_contralaterales']} "
          f"con y < 0; {m['direcciones_plano_medio']} en el plano medio, fuera de ambos. Media de SD(f) en 4–16 kHz:", ""]
    for e in COMPARADAS:
        x = c[e]
        L.append(f"- {etiqueta(e)}: ipsilateral {num(x['sd_media_4_16khz_ipsilateral_db'])} dB, contralateral "
                 f"{num(x['sd_media_4_16khz_contralateral_db'])} dB.")
    L += ["", "Comprobaciones del promedio sobre direcciones (misma banda):", ""]
    for e in COMPARADAS:
        x = c[e]
        L.append(f"- {etiqueta(e)}: ponderado {num(x['sd_media_4_16khz_db'])} dB; sin ponderar {num(x['sd_media_4_16khz_sin_ponderar_db'])} dB; "
                 f"rejilla ARI sin ponderar {num(x['sd_media_4_16khz_rejilla_ari_sin_ponderar_db'])} dB.")

    # secundario
    s = m["secundario_78_frecuencias"]
    L += ["", "## Análisis secundario: 78 frecuencias (aparte del principal)", "",
          f"Solo -e {', '.join(x.replace('.', ',') for x in s['condiciones'])}, que convergieron en todas. Pregunta: ¿las "
          f"frecuencias del tope ({exc} kHz) tienen algo raro de por sí, o el problema es exclusivo de la malla de -e 1? Se "
          f"compara la SD de esas frecuencias con la tendencia lineal de sus vecinas de 20,0 kHz hacia arriba ({len(s['vecinas_hz'])} frecuencias).", ""]
    for e, x in s["por_condicion"].items():
        if "sd_tope_db" in x:
            tope = "; ".join(f"{num(float(k) / 1000, 1)} kHz: {num(v)} dB, tendencia {num(x['sd_tope_prevista_por_tendencia_db'][k])} dB "
                             f"(z = {num(x['z_tope'][k], 1)})" for k, v in x["sd_tope_db"].items())
            L.append(f"- {etiqueta(e)} contra la referencia: las vecinas suben {num(x['pendiente_vecinas_db_por_khz'])} dB/kHz "
                     f"(residuos ± {num(x['desv_residuos_vecinas_db'])} dB); tope: {tope}.")
    for e, x in s["por_condicion"].items():
        it = ", ".join(f"{num(float(k) / 1000, 1)} kHz: {v}" for k, v in x["iteraciones_tope"].items())
        L.append(f"- Iteraciones del solver con {etiqueta(e)} en el tope: {it} (vecinas: {min(x['iteraciones_vecinas'])}–{max(x['iteraciones_vecinas'])}).")

    # conclusión
    L += ["", "## Conclusión (provisional mientras falte el umbral)", ""]
    L.append("Según dónde caiga el umbral de SD en 4–11 kHz: " + "; ".join(
        f"de {num(i['desde_db'])} {'en adelante' if i['hasta_db'] is None else 'a ' + num(i['hasta_db']) + ' dB'}, -e {i['eleccion'].replace('.', ',')}"
        for i in d["intervalos_sd"]) + ".")
    L.append("")
    L.append("Según el umbral de muescas perdidas: " + "; ".join(
        f"de {num(100 * i['desde'], 0)} % {'en adelante' if i['hasta'] is None else 'a ' + num(100 * i['hasta'], 0) + ' %'}, "
        f"-e {i['eleccion'].replace('.', ',')}" for i in d["intervalos_muescas"])
        + ". La elección final es la menor de las dos.")
    if d["intervalo_que_elige_e1"]:
        a, b = d["intervalo_que_elige_e1"]
        L += ["", f"**Si el umbral de SD cae entre {num(a)} y {num(b)} dB (y el de muescas permite -e 1), gana -e 1, y -e 1 es la única condición que necesita "
              f"arreglar el solver** (divergió en {exc} kHz con el NumCalc de 2022). En ese caso, compilar NumCalc 1.3.0 y "
              "validar -adapt_fmmlength deja de ser opcional y pasa a ser **prerrequisito de producción**: sin eso, -e 1 no "
              "entrega el vector completo."]
    L += ["", "## Figuras", ""]
    for v in m["figuras"].values():
        L.append(f"- `{v}`")
    L.append("- Renders de la oreja (fase 1): `../fase1/orejas_alambre.png`")
    L += ["", "Colores fijos por condición en todas las figuras; la paleta sigue la guía de visualización (tres primeros "
          "slots categóricos, validados según la guía; el validador no se pudo ejecutar aquí porque no hay Node instalado)."]
    (SALIDA / "informe.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    principal()
