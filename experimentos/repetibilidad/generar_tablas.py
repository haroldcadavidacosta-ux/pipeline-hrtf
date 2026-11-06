"""Tablas de LaTeX de la repetibilidad en tres pares, generadas de los resultados para no transcribir.

Lee datos/salidas/evaluacion_repetibilidad/ y escribe en <carpeta de las capturas>/resultados/:
tablas_repetibilidad.tex, las figuras y los JSON. Estima además el ancho de cada tabla, porque no siempre
hay LaTeX para compilar (con la fuente Times del documento, en \\small).

Uso:  .venv\\Scripts\\python.exe experimentos\\repetibilidad\\generar_tablas.py [carpeta de las capturas]
"""
import json
import re
import shutil
import sys
from pathlib import Path

from matplotlib.font_manager import FontProperties, findfont
from matplotlib.ft2font import FT2Font

RAIZ = Path(__file__).resolve().parents[2]
CAPTURAS = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ.parent / "PRUEBA REPETIBILIDAD"
ENTRADA = RAIZ / "datos" / "salidas" / "evaluacion_repetibilidad"
SALIDA = CAPTURAS / "resultados"
PARES = ["A3-A1", "C3-C1", "E2-E1"]
CAPS = ["A1", "A3", "C1", "C3", "E1", "E2"]
EQUIPO = {"A1": ("T", "T"), "A3": ("T", "T"), "C1": ("T", "T"), "C3": ("P", "P"), "E1": ("T", "T"), "E2": ("P", "T")}  # T: torre; P: portátil
# Lo registrado antes de calcular. A: metricas/predicciones_A1_A3_*.md (de ReceiverPosition). C y E:
# metricas/predicciones_repetibilidad_C_E_*.md (de los informes de limpieza); se comprueba abajo.
DELTA_AID_REGISTRADO = {"A3-A1": 2.3, "C3-C1": -1.45, "E2-E1": 0.26}
ANCHO_TEXTO_PT = 516.0   # IEEEtran, una columna
TAMANO_PT = 11.0         # \small en una clase de 12 pt
SEP_COLUMNA_PT = 6.0     # \tabcolsep

r = json.loads((ENTRADA / "resumen.json").read_text(encoding="utf-8"))
giro = json.loads((ENTRADA / "itd_giro_escala.json").read_text(encoding="utf-8"))
esc = json.loads((ENTRADA / "ild_escala.json").read_text(encoding="utf-8"))["pares"]
eq = json.loads((ENTRADA / "equipo" / "prueba_equipo.json").read_text(encoding="utf-8"))
costo = json.loads((SALIDA / "costo_piso_ruido.json").read_text(encoding="utf-8"))
_FUENTE = FT2Font(findfont(FontProperties(family="STIXGeneral")))
_FUENTE.set_size(TAMANO_PT, 72)
ANCHOS = {}


def n(x, d=2, signo=False):
    s = f"{x:+.{d}f}" if signo else f"{x:.{d}f}"
    s = s.replace(".", ",")
    return s.replace("-", "$-$") if s.startswith("-") else s


def percentil(x):
    return n(x, 1) if 0 < x < 1 else n(x, 0)


def par(p):
    return p.replace("-", "--")


def dos(a, b):
    """Cabecera en dos líneas."""
    return f"\\begin{{tabular}}{{@{{}}c@{{}}}}{a}\\\\{b}\\end{{tabular}}"


def _visible(c):
    c = re.sub(r"\\begin\{tabular\}\{[^}]*\}|\\end\{tabular\}", "", str(c))
    c = c.replace("\\mathrm", "").replace("\\textbf", "").replace("\\mu", "µ").replace("\\checkmark", "v").replace("\\times", "x")
    c = c.replace("\\Delta", "D").replace("\\,", " ").replace("\\%", "%").replace("~", " ").replace("--", "–")
    return re.sub(r"[${}_^]", "", c)


def _ancho(texto):
    medidas = []
    for t in texto.split("\\\\"):
        _FUENTE.set_text(t or " ")
        medidas.append(_FUENTE.get_width_height()[0] / 64)
    return max(medidas)


def estimar_ancho(cabeceras, filas):
    cols = {}
    for f in [*cabeceras, *filas]:
        i = 0
        for c in f:
            m = re.match(r"\\multicolumn\{(\d+)\}", str(c))
            if m:
                i += int(m.group(1))
                continue
            cols[i] = max(cols.get(i, 0), _ancho(_visible(c)))
            i += 1
    return sum(cols.values()) + 2 * SEP_COLUMNA_PT * len(cols)


def tabla(titulo, etiqueta, columnas, cabecera, filas, nota=None, cabecera2=None):
    L = ["\\begin{table}[!htbp]", "\\centering", "\\small", f"\\caption{{{titulo}}}", f"\\label{{{etiqueta}}}",
         f"\\begin{{tabular}}{{{columnas}}}", "\\hline", " & ".join(cabecera) + " \\\\"]
    if cabecera2:
        L += [" & ".join(cabecera2) + " \\\\"]
    L += ["\\hline"]
    L += [" & ".join(str(c) for c in f) + " \\\\" for f in filas]
    L += ["\\hline", "\\end{tabular}"]
    if nota:
        L += [f"\\par\\smallskip\\footnotesize {nota}"]
    L += ["\\end{table}", ""]
    ANCHOS[etiqueta] = estimar_ancho([cabecera] + ([cabecera2] if cabecera2 else []), filas)
    return L


T = ["% Generado por experimentos/repetibilidad/generar_tablas.py: no editar los números a mano.",
     "% Colocación [!htbp], como el resto de la tesis. Requiere amssymb (\\checkmark).",
     "% %REVISAR: subsubsec:res_marcado y demás etiquetas salen de la tesis; compilar para comprobarlas.", ""]

c = r["capturas"]
T += tabla("Capturas de los tres pares de repetibilidad", "tab:rep_capturas", "llccccll",
           ["Captura", "Escala", "AID (mm)", dos("Cinta", "(mm)"), dos("Circ. de la", "malla (mm)"), dos("Corte", "(mm)"),
            dos("Equipo", "(izq. / der.)"), dos("Horas de cálculo", "(izq. / der.)")],
           [[k, "Mediana" if c[k]["escala"].startswith("mediana") else "Bitragial", n(c[k]["aid_mm"], 1), n(c[k]["cinta_mm"], 0),
             n(c[k]["circunferencia_mm"], 1), n(c[k]["corte_mm"], 1), f"{EQUIPO[k][0]} / {EQUIPO[k][1]}",
             f"{n(c[k]['lados']['left']['horas_suma_por_frecuencia'], 1)} / {n(c[k]['lados']['right']['horas_suma_por_frecuencia'], 1)}"]
            for k in CAPS],
           "Equipo: T, torre; P, portátil. Cinta: medida en la persona. Circ. de la malla: perímetro de la malla ya escalada. Horas de cálculo: suma de la duración de cada frecuencia, no el tiempo de pared.")

v = r["validez"]
RASGOS = [("itd_90_us", "ITD a 90° ($\\mu$s)", 0), ("itd_270_us", "ITD a 270° ($\\mu$s)", 0), ("itd_max_us", "ITD máxima ($\\mu$s)", 0),
          ("ild_90_1000_db", "ILD a 90°, 1~kHz (dB)", 1), ("ild_90_2000_db", "ILD a 90°, 2~kHz (dB)", 1),
          ("ild_90_4000_db", "ILD a 90°, 4~kHz (dB)", 1), ("ild_90_8000_db", "ILD a 90°, 8~kHz (dB)", 1),
          ("ild_90_16000_db", "ILD a 90°, 16~kHz (dB)", 1), ("nivel_bf_db", "Nivel de 150 a 450~Hz (dB)", 2)]
filas = []
for clave, nombre, d in RASGOS:
    lo, hi = v["rango_hutubs"][clave]
    fila = [nombre, f"{n(lo, d)} a {n(hi, d)}"]
    for k in CAPS:
        s = v["sujetos"][k]
        t = n(s["rasgos"][clave], d)
        fila.append(t if s["dentro"][clave] else f"\\textbf{{{t}}}")
    filas.append(fila)
fuera = {k: sum(not x for x in v["sujetos"][k]["dentro"].values()) for k in CAPS}
filas.append(["Rasgos fuera", "", *[fuera[k] for k in CAPS]])
T += tabla("Rasgos de las seis HRTF frente al rango de HUTUBS (percentiles 2,5 a 97,5). En negrita, los valores fuera del rango",
           "tab:rep_validez", "llcccccc", ["Rasgo", "HUTUBS", *CAPS], filas)

R = r["repetibilidad"]
filas = []
for p in PARES:
    x = R[p]
    s1, s2, e = x["sd"]["4-11"], x["sd"]["12-16"], x["e_itd_us"]
    filas.append([par(p), n(s1["media_ponderada"]), n(s1["p95"]), n(s1["izq_ponderada"]), n(s1["der_ponderada"]),
                  n(s2["media_ponderada"]), n(s2["p95"]), n(e["media_abs_ponderada"], 1), n(e["max_abs"], 1), n(100 * e["frac_sobre_umbral"], 0)])
T += tabla("Repetibilidad entre capturas de la misma persona, HRTF de producción a 48~kHz, rejilla Default", "tab:rep_espectral",
           "lcccccccccc".replace("cccccccccc", "ccccccccc"),
           ["Par", "\\multicolumn{4}{c}{SD 4--11~kHz (dB)}", "\\multicolumn{2}{c}{SD 12--16~kHz (dB)}", "\\multicolumn{3}{c}{$|e_{\\mathrm{ITD}}|$ ($\\mu$s)}"],
           filas, "SD: media ponderada por área, de las dos orejas o de cada una; p95: percentil 95. $|e_{\\mathrm{ITD}}|$: media ponderada por área, máximo y porcentaje de direcciones por encima de 16~$\\mu$s.",
           cabecera2=["", "Media", "p95", "Izq.", "Der.", "Media", "p95", "Media", "Máx.", "$>16$ (\\%)"])

filas = []
for nominal in [1000, 2000, 4000, 5000, 8000, 16000]:
    fila = [n(nominal / 1000, 0)]
    for p in PARES:
        b = next(y for y in R[p]["e_ild_bandas"] if y["nominal"] == nominal)
        fila += [n(b["media_abs_ponderada"]), n(b["max_abs"]), n(100 * b["frac_sobre_umbral"], 1)]
    filas.append(fila)
T += tabla("Error de ILD por banda de tercio de octava en los tres pares", "tab:rep_ild", "l" + "ccc" * 3,
           ["kHz", *[f"\\multicolumn{{3}}{{c}}{{{par(p)}}}" for p in PARES]], filas,
           "Media y máximo de $|e|$ en dB, media ponderada por área; $>1$: porcentaje de direcciones por encima de 1~dB.",
           cabecera2=["", *["Media", "Máx.", "$>1$ (\\%)"] * 3])

filas = []
for p in PARES:
    x = R[p]
    sim, ref = p.split("-")
    if p != "A3-A1":
        de_informes = c[sim]["aid_mm"] - c[ref]["aid_mm"]
        if abs(de_informes - DELTA_AID_REGISTRADO[p]) > 0.005:
            raise ValueError(f"{p}: el registro no coincide con los informes ({de_informes})")
    lo, hi = x["p1_intervalo"]
    filas.append([par(p), n(DELTA_AID_REGISTRADO[p], 1 if p == "A3-A1" else 2, True), n(x["aid_mm"][sim] - x["aid_mm"][ref], 2, True),
                  n(x["p1_lateral_us"]["90"], 1, True), n(x["p1_lateral_us"]["270"], 1, True), f"{n(lo, 1)} a {n(hi, 1)}", "Sí" if x["p1_cumple"] else "No"])
T += tabla("Predicción registrada de la ITD lateral: $|$ITD$|$ de la captura evaluada menos la de la referencia ($\\mu$s)",
           "tab:rep_prediccion", "lcccccc",
           ["Par", dos("$\\Delta$AID", "registrado (mm)"), dos("$\\Delta$AID", "SOFA (mm)"), dos("Azimut", "90°"), dos("Azimut", "270°"),
            dos("Intervalo", "registrado"), "Se cumple"], filas,
           "$\\Delta$AID registrado: el que fijó cada intervalo antes de calcular, de ReceiverPosition de los SOFA en A3--A1 y de los informes de limpieza (distancia entre los canales marcados, escalada) en C3--C1 y E2--E1. "
           "$\\Delta$AID SOFA: de ReceiverPosition, que usa la cara de la malla graduada donde se ubica la fuente. Los intervalos no cambian.")

I = r["rasgos"]
NOMBRES = {"sd_4-11": ("SD 4--11~kHz (dB)", 2), "sd_12-16": ("SD 12--16~kHz (dB)", 2),
           "itd_mae_us": ("$|e_{\\mathrm{ITD}}|$ medio ($\\mu$s)", 2), "ild_mae_db": ("$|e_{\\mathrm{ILD}}|$ medio (dB)", 2)}
filas = []
for m, (nombre, d) in NOMBRES.items():
    i = I["inter"][m]
    fila = [nombre, f"{n(i['min'], d)} / {n(i['p5'], d)} / {n(i['mediana'], d)}"]
    for p in PARES:
        y = I["pares"][p][m]
        fila.append(f"{n(y['intra'], d)} ({percentil(y['percentil'])})" + ("" if m == "sd_12-16" else (" \\checkmark" if y["cumple"] else " $\\times$")))
    filas.append(fila)
ctx = r["contexto_medido"]["intra_pp22_pp88"]
T += tabla(f"Diferencia intra-sujeto en los tres pares frente a la diferencia entre personas ({I['n_pares']:,} pares de HUTUBS)".replace(",", "\\,"),
           "tab:rep_rasgos", "llccc", ["Métrica", "Inter: mín. / p5 / mediana", *[par(p) for p in PARES]], filas,
           "Entre paréntesis, percentil de la intra en la inter; \\checkmark\\ cumple el criterio (por debajo del percentil 5), $\\times$ no lo cumple. "
           f"La SD 12--16~kHz es descriptiva. Referencia medida (persona de HUTUBS medida dos veces): SD 4--11~kHz {n(ctx['sd_4-11'])}~dB, "
           f"$|e_{{\\mathrm{{ITD}}}}|$ {n(ctx['itd_mae_us'], 1)}~$\\mu$s, $|e_{{\\mathrm{{ILD}}}}|$ {n(ctx['ild_mae_db'])}~dB.")

M = r["muescas_descriptivo"]
filas = [[par(p), n(M[p]["sd_4_11_izq_db"]), f"{M[p]['perdidas']} de {M[p]['con_referencia']:,}".replace(",", "\\,") + f" ({n(100 * M[p]['fraccion_perdidas'], 1)}~\\%)",
          f"{n(M[p]['corrimiento_mediana_hz'], 0)} [{n(M[p]['corrimiento_q1_hz'], 0)}, {n(M[p]['corrimiento_q3_hz'], 0)}]"] for p in PARES]
T += tabla("Criterios del barrido con las HRTF de producción, oreja izquierda (descriptivo; no es un piso de ruido)", "tab:rep_muescas", "lccc",
           ["Par", "SD 4--11~kHz (dB)", "Muescas perdidas", "Corrimiento mediano [RIC] (Hz)"], filas,
           "SD($f$) de la Ecuación~\\eqref{eq:sdf}. Daños del barrido en la Tabla~\\ref{tab:res_dano}: $-e$~1, 1,006~dB y 10,1~\\%; $-e$~2, 1,440~dB y 16,2~\\%.")

filas = [[par(p), n(giro[p]["escala_pct"], 2, True), n(giro[p]["yaw_grados"], 2, True), n(giro[p]["roll_grados"], 2, True),
          n(giro[p]["mae_us"], 1), n(giro[p]["mae_sin_escala_us"], 1), n(giro[p]["mae_sin_giro_us"], 1), n(giro[p]["mae_sin_ajuste_us"], 1)]
         for p in PARES]
T += tabla("Exploratorio, posterior a los datos: parte del error de ITD compatible con un cambio de escala y con un giro de la malla", "tab:rep_giro", "lccccccc",
           ["Par", dos("Escala", "(\\%)"), dos("Giro", "vertical (°)"), dos("Giro", "frontal (°)"), "$|e_{\\mathrm{ITD}}|$", dos("Sin", "escala"), dos("Sin", "giros"), dos("Sin", "ambos")], filas,
           "$|e_{\\mathrm{ITD}}|$ en $\\mu$s, ponderado por área.")

filas = [[f"{'Izquierda' if e['proyecto'].endswith('L') else 'Derecha'}, {n(e['frecuencia_hz'] / 1000, 2)}~kHz", e["equipo_original"],
          f"{e['tiempo_s_original']:.0f}", f"{e['tiempo_s_repetida']:.0f}", f"{e['iteraciones_original']} / {e['iteraciones_repetida']}",
          "Sí" if e["identico_al_byte"] else "No"] for e in eq]
T += tabla("Frecuencias de E2 repetidas en la torre", "tab:rep_equipo", "lccccc",
           ["Oreja y frecuencia", dos("Equipo", "original"), dos("Original", "(s)"), dos("Torre", "(s)"), "Iteraciones", dos("pEvalGrid", "idéntico")], filas,
           f"{eq[0]['puntos']:,} puntos de la rejilla de evaluación por frecuencia.".replace(",", "\\,"))

filas = [[par(p), n(esc[p]["original_ild"]), f"{n(esc[p]['mejor_ild']['ild'])} ({n(esc[p]['mejor_ild']['escala_pct'], 2, True)}~\\%)",
          *[n(esc[p]["tabla"][k]["ild"]) for k in ("-4.7", "-2.4", "2.4", "4.7")]] for p in PARES]
T += tabla("Exploratorio, posterior a los datos: error medio de ILD (dB) al simular un error de escala en la captura evaluada", "tab:rep_ild_escala", "lcccccc",
           ["Par", "Original", "Mejor escala", "$-$4,7~\\%", "$-$2,4~\\%", "+2,4~\\%", "+4,7~\\%"], filas,
           "La escala se simula desplazando el eje de frecuencias, $H_s(f)=H(sf)$. Es una aproximación: el corte del cuello y la fuente no escalan igual que la cabeza. Criterio: menos de 2,00~dB.")

pa = costo["pasadas"]
filas = [[f"$-e$~{e.replace('.', ',')}", n(pa[e]["A1"]["horas_de_primera_a_ultima"]), n(pa[e]["A3"]["horas_de_primera_a_ultima"]),
          n(pa[e]["horas_por_captura_media"]), n(4 * pa[e]["horas_por_captura_media"], 1)] for e in ("2", "1", "0.5")]
filas.append(["Total", "", "", n(costo["completo_por_captura_h"], 1), n(costo["completo_cuatro_capturas_h"], 1)])
T += tabla("Costo de repetir el piso de ruido en C1, C3, E1 y E2, según los tiempos medidos en A1 y A3 (horas de torre)", "tab:rep_costo_piso", "lcccc",
           ["Pasada", "A1", "A3", dos("Media por", "captura"), dos("Cuatro", "capturas")], filas,
           "Oreja izquierda, vector de diagnóstico, $-x$~0,5 e $-y$~10; tiempo de pared entre la primera y la última frecuencia. Sin contar gradado, exportación ni análisis. Es una estimación: el tamaño de cada malla puede cambiarla.")

SALIDA.mkdir(parents=True, exist_ok=True)
(SALIDA / "tablas_repetibilidad.tex").write_text("\n".join(T), encoding="utf-8")
(SALIDA / "figuras").mkdir(exist_ok=True)
shutil.copy(ENTRADA / "figuras" / "eval_rasgos_tres_pares.png", SALIDA / "figuras")
for p in PARES:
    s, ref = p.split("-")
    shutil.copy(ENTRADA / f"{s}_vs_{ref}" / "figuras" / "eval_repetibilidad_sd.png", SALIDA / "figuras" / f"eval_sd_{s}_{ref}.png")
for j in ("resumen.json", "itd_giro_escala.json", "ild_escala.json", "equipo/prueba_equipo.json"):
    shutil.copy(ENTRADA / j, SALIDA / Path(j).name)
shutil.copy(RAIZ / "metricas" / "predicciones_repetibilidad_C_E_2026-11-05.md", SALIDA)
print(f"Ancho del texto: {ANCHO_TEXTO_PT:.0f} pt. Ancho estimado de cada tabla:")
for etiqueta, a in ANCHOS.items():
    print(f"  {etiqueta:22s} {a:5.0f} pt  {100 * a / ANCHO_TEXTO_PT:3.0f} %{'  NO CABE' if a > ANCHO_TEXTO_PT else ''}")
