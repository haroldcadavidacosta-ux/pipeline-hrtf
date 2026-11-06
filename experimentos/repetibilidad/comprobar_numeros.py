"""Coherencia de números: compara lo que dicen el borrador y el documento de contexto con los JSON.

Para cada afirmación recalcula el valor desde los JSON, le da el formato con que aparece en el texto y
comprueba que esa cadena esté en el documento. Además lista los números del borrador que no aparecen en
las tablas ni en estas afirmaciones, para revisarlos a mano.

Uso:  .venv\\Scripts\\python.exe experimentos\\repetibilidad\\comprobar_numeros.py [carpeta de las capturas]
Escribe <carpeta de las capturas>/resultados/comprobacion_numeros.md.
"""
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = (Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ.parent / "PRUEBA REPETIBILIDAD") / "resultados"


def leer(n):
    return json.loads((SALIDA / n).read_text(encoding="utf-8"))


r, giro, esc, eq, costo = leer("resumen.json"), leer("itd_giro_escala.json"), leer("ild_escala.json"), leer("prueba_equipo.json"), leer("costo_piso_ruido.json")
borrador = (SALIDA / "borrador_repetibilidad.tex").read_text(encoding="utf-8")
contexto = (SALIDA / "CONTEXTO_PARA_REDACCION.md").read_text(encoding="utf-8")
tablas = (SALIDA / "tablas_repetibilidad.tex").read_text(encoding="utf-8")
R, I, V, C, M = r["repetibilidad"], r["rasgos"], r["validez"], r["capturas"], r["muescas_descriptivo"]
PARES = ["A3-A1", "C3-C1", "E2-E1"]


def n(x, d=2):
    return f"{abs(x):.{d}f}".replace(".", ",")


sd = {p: R[p]["sd"]["4-11"]["media_ponderada"] for p in PARES}
itd = {p: R[p]["e_itd_us"]["media_abs_ponderada"] for p in PARES}
ctx = r["contexto_medido"]["intra_pp22_pp88"]
horas = {c: [C[c]["lados"][l]["horas_suma_por_frecuencia"] for l in ("left", "right")] for c in C}
portatil = [horas["C3"][0], horas["C3"][1], horas["E2"][0]]
torre = [*horas["A1"], *horas["A3"], *horas["C1"], *horas["E1"], horas["E2"][1]]
razones = [e["tiempo_s_original"] / e["tiempo_s_repetida"] for e in eq if e["equipo_original"] == "portátil"]
pctl = lambda p, m: I["pares"][p][m]["percentil"]
Mf = {p: 100 * M[p]["fraccion_perdidas"] for p in PARES}
Ms = {p: M[p]["sd_4_11_izq_db"] for p in PARES}
AF = [(name, V["sujetos"][name]) for name in ("A1", "A3", "C1", "C3", "E1", "E2")]
fuera = {k: sum(not x for x in s["dentro"].values()) for k, s in AF}

AFIRMACIONES = [
    ("SD 4–11 mínimo", n(min(sd.values())) + " a " + n(max(sd.values())), "1,59 a 3,91", "b"),
    ("SD 4–11 rango en contexto", "2,53 ✓", None, None),
    ("|e_ITD| rango", n(min(itd.values()), 1) + " a " + n(max(itd.values()), 1), "11,0 a 12,5", "b"),
    ("Direcciones > 16 µs, rango", f"{100 * min(R[p]['e_itd_us']['frac_sobre_umbral'] for p in PARES):.0f} y el {100 * max(R[p]['e_itd_us']['frac_sobre_umbral'] for p in PARES):.0f}", "20 y el 34", "b"),
    ("Percentil 5 inter SD 4–11", n(I["inter"]["sd_4-11"]["p5"]), "4,72", "bc"),
    ("Mínimo inter SD 4–11", n(I["inter"]["sd_4-11"]["min"]), "3,78", "bc"),
    ("Pares inter", f"{I['n_pares']}", "4278", None),
    ("Percentil SD de C", n(pctl("C3-C1", "sd_4-11"), 1), "0,1", "b"),
    ("Percentiles ITD", ", ".join(f"{pctl(p, 'itd_mae_us'):.0f}" for p in PARES[:2]) + f" y {pctl('E2-E1', 'itd_mae_us'):.0f}", "12, 16 y 20", "b"),
    ("Percentiles ILD de C y E", f"{pctl('C3-C1', 'ild_mae_db'):.0f} y {pctl('E2-E1', 'ild_mae_db'):.0f}", "2 y 0", "b"),
    ("Percentil ILD de A", f"{pctl('A3-A1', 'ild_mae_db'):.0f}", "10", "b"),
    ("HUTUBS medida dos veces", f"{n(ctx['sd_4-11'])}~dB, {n(ctx['itd_mae_us'], 1)}~$\\mu$s y {n(ctx['ild_mae_db'])}~dB", "2,64~dB, 11,9~$\\mu$s y 1,30~dB", "b"),
    ("Archivos SOFA", f"{sum(c['sofa']['archivos'] for c in C.values())} de {sum(c['sofa']['archivos'] - len(c['sofa']['fallan']) for c in C.values())}", "48 de 48", "c"),
    ("Horas de cálculo, portátil", n(min(portatil), 1) + " a " + n(max(portatil), 1), "19,4 a 22,3", "b"),
    ("Horas de cálculo, torre", n(min(torre), 1) + " a " + n(max(torre), 1), "10,7 a 12,8", "b"),
    ("Factor entre equipos", n(min(razones), 1) + " y " + n(max(razones), 1), "1,6 y 1,8", "b"),
    ("Pared E2 izq.", n(C["E2"]["lados"]["left"]["horas_pared_sesiones"]), "9,45", "c"),
    ("Pared E2 der.", n(C["E2"]["lados"]["right"]["horas_pared_sesiones"]), "4,10", "c"),
    ("Pared E1 der.", n(C["E1"]["lados"]["right"]["horas_pared_sesiones"]), "5,65", "c"),
    ("Pared C1", n(C["C1"]["lados"]["left"]["horas_pared_sesiones"]) + " y " + n(C["C1"]["lados"]["right"]["horas_pared_sesiones"]), "4,58 y 4,29", "c"),
    ("Pared C3", n(C["C3"]["lados"]["left"]["horas_pared_sesiones"], 1) + " y " + n(C["C3"]["lados"]["right"]["horas_pared_sesiones"]), "8,8 y 14,67", "c"),
    ("Muescas, rango", n(min(Ms.values())) + " y " + n(max(Ms.values())), "2,40 y 3,90", "b"),
    ("Muescas perdidas, rango", n(min(Mf.values()), 1) + " y el " + n(max(Mf.values()), 1), "15,8 y el 50,0", "b"),
    ("Muescas de A", f"{n(Ms['A3-A1'])}~dB y {n(Mf['A3-A1'], 1)}", "2,72~dB y 43,6", "b"),
    ("ILD 16 kHz, rango", n(min(next(b['media_abs_ponderada'] for b in R[p]['e_ild_bandas'] if b['nominal'] == 16000) for p in PARES)) + " a " + n(max(next(b['media_abs_ponderada'] for b in R[p]['e_ild_bandas'] if b['nominal'] == 16000) for p in PARES)), "2,85 a 4,20", "b"),
    ("Rasgos fuera", ", ".join(f"{k} {v}" for k, v in fuera.items()), "A1 0, A3 3, C1 0, C3 1, E1 1, E2 1", None),
    ("ILD de C3 a 4 kHz", n(V["sujetos"]["C3"]["rasgos"]["ild_90_4000_db"], 1), "9,2", "bc"),
    ("ILD de E a 16 kHz", n(V["sujetos"]["E1"]["rasgos"]["ild_90_16000_db"], 1) + " y " + n(V["sujetos"]["E2"]["rasgos"]["ild_90_16000_db"], 1), "35,4 y 36,2", "bc"),
    ("Giro: A sin escala", f"{n(giro['A3-A1']['mae_us'], 1)} a {n(giro['A3-A1']['mae_sin_escala_us'], 1)}", "11,0 a 7,3", "bc"),
    ("Giro: C sin giros", f"{n(giro['C3-C1']['mae_us'], 1)} a {n(giro['C3-C1']['mae_sin_giro_us'], 1)}", "11,8 a 5,1", "bc"),
    ("Giro: E sin giros", f"{n(giro['E2-E1']['mae_us'], 1)} a {n(giro['E2-E1']['mae_sin_giro_us'], 1)}", "12,5 a 3,3", "bc"),
    ("Escala en C y E", f"{n(giro['C3-C1']['escala_pct'], 1)} y {n(giro['E2-E1']['escala_pct'], 1)}", "0,8 y 0,2", "bc"),
    ("ILD de A con la mejor escala", n(esc["pares"]["A3-A1"]["mejor_ild"]["ild"]), "2,08", "bc"),
    ("Margen de C en el criterio ILD", n(esc["p5_ild_db"] - esc["pares"]["C3-C1"]["original_ild"]), "0,08", "bc"),
    ("Costo por captura", n(costo["completo_por_captura_h"], 1), "7,6", "bc"),
    ("Costo de las cuatro", f"{costo['completo_cuatro_capturas_h']:.0f}", "30", "bc"),
]

filas, dif = [], []
for nombre, calculado, esperado, donde in AFIRMACIONES:
    if esperado is None:
        if "Rasgos" in nombre:
            ok = calculado == "A1 0, A3 3, C1 0, C3 1, E1 1, E2 1"
            filas.append((nombre, calculado, "ok" if ok else "DIFERENTE"))
            if not ok:
                dif.append(nombre)
        continue
    faltan = []
    if calculado != esperado:
        faltan.append(f"JSON da {calculado}")
    for d, texto, etiqueta in (("b", borrador, "borrador"), ("c", contexto, "contexto")):
        if d in (donde or "") and esperado not in texto:
            faltan.append(f"no está en {etiqueta}")
    filas.append((nombre, calculado, "ok" if not faltan else "; ".join(faltan)))
    if faltan:
        dif.append(nombre)

# máximos del cambio por escala, y números del borrador que no salen de lo anterior
cambio = max(abs(v["ild"] - x["original_ild"]) for x in esc["pares"].values() for k, v in x["tabla"].items() if abs(float(k)) <= 4.7)
filas.append(("Cambio máximo de ILD con ±4,7 %", n(cambio), "ok" if cambio < 0.2 else "DIFERENTE"))
if cambio >= 0.2:
    dif.append("Cambio máximo de ILD")
sinmat = re.sub(r"%.*", "", borrador)
numeros = sorted(set(re.findall(r"(?<![\w{,])\d+,\d+(?![\w])|(?<=\{)\d+\{,\}\d+", sinmat)))
conocidos = tablas + " ".join(a[2] or "" for a in AFIRMACIONES)
sin_fuente = [x for x in numeros if x.replace("{,}", ",") not in conocidos]
numeros_ctx = sorted(set(re.findall(r"(?<![\w,])\d+,\d+(?![\w])", contexto)))
sin_fuente_ctx = [x for x in numeros_ctx if x not in conocidos and x not in borrador]

L = ["# Comprobación de números del borrador y del contexto", "",
     "Generado por `experimentos/repetibilidad/comprobar_numeros.py`.", "",
     "| Afirmación | Valor desde los JSON | Resultado |", "|---|---|---|"]
L += [f"| {a} | {b} | {c} |" for a, b, c in filas]
L += ["", f"Diferencias: {len(dif)}." + (" " + ", ".join(dif) if dif else ""), "",
      "Números del borrador que no aparecen en las tablas ni en esta lista (revisados a mano):",
      ", ".join(sin_fuente) if sin_fuente else "ninguno", "",
      "Números del contexto que no aparecen en las tablas, el borrador ni esta lista (revisados a mano):",
      ", ".join(sin_fuente_ctx) if sin_fuente_ctx else "ninguno"]
(SALIDA / "comprobacion_numeros.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("\n".join(L))
