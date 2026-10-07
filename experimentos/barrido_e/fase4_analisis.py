"""Fase 4: piso de ruido de la captura (A1 frente a A3) y la elección de -e. Escrito ANTES de
tener los datos del par (fase4_sujeto_A_2026-10-05.md fija el sujeto, el par y la regla).

A1 es la referencia de A3, los dos graduados con el mismo -e y simulados con el mismo protocolo.
Se miden los dos pisos de ruido con el código de la fase 3, sin cambiar nada:

  - SD media en 4-11 kHz (rejilla Default, ponderada por área de Voronoi) entre las dos capturas
  - fracción de muescas perdidas: de las direcciones con primer notch válido en A1, cuántas no tienen
    notch emparejado en A3 (mismo criterio de muesca)

Regla (metodología, fase 4): con cada piso como umbral, se elige el mayor -e cuya diferencia contra la
referencia -e 0,5 de B no lo supera (intervalos de fase3/metricas.json, más la quinta candidata
-e 1 -y 5 de fase3/y5/metricas_y5.json); la elección final es la menor de las dos. Con el par a -e 2 la
elección es orientativa; la definitiva sale del par a -e 0,5, en el mismo pie que la tabla.

Se excluyen las frecuencias que no convergieron en alguna de las dos capturas y las excluidas del
análisis principal del barrido (23,4-24 kHz); ninguna toca la banda de 4-11 kHz.

Solo descriptivo (no entra en la regla): SD por hemisferio, SD en 12-16 kHz y en 0,9-4 kHz. Esta última
es donde más pesaría el trozo de hombro que entra en la malla de A con el corte a -115 mm.

Uso:  .venv/Scripts/python.exe experimentos/barrido_e/fase4_analisis.py <e>      (e = 2 o 0.5)
Escribe datos/experimentos/barrido_e/fase4/analisis_e<e>.json e informe_e<e>.md.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import sofar as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fase3_analisis as F    # noqa: E402

BARRIDO = F.BARRIDO
SALIDA = BARRIDO / "fase4"
BANDAS = {"4-11": (4000.0, 11000.0), "12-16": (12000.0, 16000.0), "0.9-4": (900.0, 4000.0)}


def cargar(e: str, captura: str) -> dict:
    clave = f"A{captura}_{e}"
    carpeta = BARRIDO / f"fase4_e{e}"
    s = sf.read_sofa(str(carpeta / f"e_{clave}" / "Output2HRTF" / "HRTF_Default.sofa"), verify=False)
    H = (np.asarray(s.Data_Real) + 1j * np.asarray(s.Data_Imag))[:, 0, :]
    prog = json.loads((carpeta / "progreso.json").read_text(encoding="utf-8"))["condiciones"][clave]
    return {"f": np.asarray(s.N, dtype=float), "pos": np.asarray(s.SourcePosition, dtype=float),
            "db": 20 * np.log10(np.abs(H)), "estado": prog["estado"],
            "divergidas": sorted(r["frecuencia_hz"] for r in prog["pasos"].values() if r["estado"] != "convergió")}


def candidatas() -> dict:
    """Diferencia de cada -e contra la referencia de B: SD 4-11 kHz y fracción de muescas perdidas."""
    m = json.loads((BARRIDO / "fase3" / "metricas.json").read_text(encoding="utf-8"))
    c = {e: {"sd_4_11_db": x["sd_bandas_db"]["4-11"]["todas"],
             "muescas_perdidas": x["notch_distribucion"]["todas"]["fraccion_perdidas"]}
         for e, x in m["condiciones"].items() if e != F.REF}
    y5 = BARRIDO / "fase3" / "y5" / "metricas_y5.json"
    if y5.exists():
        s = json.loads(y5.read_text(encoding="utf-8"))["secundaria_y5_contra_ref"]
        c["1_y5"] = {"sd_4_11_db": s["sd_bandas_db"]["4-11"]["todas"],
                     "muescas_perdidas": s["notch"]["todas"]["fraccion_perdidas"]}
    return c, m["frecuencias_excluidas_hz"]


def elegir(cand: dict, umbral_sd: float, umbral_muescas: float) -> dict:
    """El mayor -e por debajo de cada umbral; la final es la menor de las dos. -e 1 -y 5 se reporta aparte."""
    valor = lambda e: float(e.split("_")[0])
    por_sd = max([e for e in cand if "_" not in e and cand[e]["sd_4_11_db"] <= umbral_sd], key=valor, default=F.REF)
    por_muescas = max([e for e in cand if "_" not in e and cand[e]["muescas_perdidas"] <= umbral_muescas],
                      key=valor, default=F.REF)
    y5 = cand.get("1_y5")
    return {"por_sd": por_sd, "por_muescas": por_muescas, "final": min(por_sd, por_muescas, key=valor),
            "y5_pasa_los_dos": None if y5 is None else bool(y5["sd_4_11_db"] <= umbral_sd
                                                             and y5["muescas_perdidas"] <= umbral_muescas)}


def principal() -> None:
    e = sys.argv[1]
    SALIDA.mkdir(parents=True, exist_ok=True)
    a, c = cargar(e, "A"), cargar(e, "C")
    if not np.allclose(a["pos"], c["pos"]) or not np.array_equal(a["f"], c["f"]):
        sys.exit("las dos capturas no tienen la misma rejilla o el mismo vector de frecuencias")
    cand, excl_barrido = candidatas()
    excl = sorted(set(a["divergidas"]) | set(c["divergidas"]) | set(excl_barrido))
    k = ~np.isin(a["f"], excl)
    f = a["f"][k]
    w = F.pesos_voronoi(a["pos"])
    y = F.lateral(a["pos"])
    ipsi, contra = y > F.LATERAL_MIN, y < -F.LATERAL_MIN
    D = (c["db"] - a["db"])[:, k]
    sd = {"todas": F.sd_f(D, w), "ipsilateral": F.sd_f(D, w, ipsi), "contralateral": F.sd_f(D, w, contra)}
    bandas = {b: {h: float(v[(f >= lo) & (f <= hi)].mean()) for h, v in sd.items()} for b, (lo, hi) in BANDAS.items()}
    notch = F.notch_distribucion(a["f"], a["db"], c["db"], np.ones(len(w), bool))
    piso_sd, piso_muescas = bandas["4-11"]["todas"], notch["fraccion_perdidas"]
    eleccion = elegir(cand, piso_sd, piso_muescas)
    r = {"generado": datetime.now().astimezone().isoformat(timespec="seconds"), "e": e,
         "referencia": "A1", "comparada": "A3", "estado": {"A": a["estado"], "C": c["estado"]},
         "frecuencias_excluidas_hz": excl, "frecuencias_comunes": int(k.sum()),
         "piso_sd_4_11_db": piso_sd, "piso_muescas_perdidas": piso_muescas,
         "sd_bandas_db": bandas, "notch": {x: notch[x] for x in notch if x != "corrimientos_hz"},
         "candidatas_contra_ref_B": cand, "eleccion": eleccion,
         "caracter": f"orientativa (par a -e {e.replace('.', ',')})" if e != "0.5" else "definitiva (par a -e 0,5)"}
    (SALIDA / f"analisis_e{e}.json").write_text(json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")
    escribir_informe(r)
    print(json.dumps({x: r[x] for x in ("piso_sd_4_11_db", "piso_muescas_perdidas", "eleccion", "caracter")},
                     indent=1, ensure_ascii=False))


def escribir_informe(r: dict) -> None:
    num, b = F.num, r["sd_bandas_db"]
    L = [f"# Fase 4: piso de ruido de la captura con -e {r['e'].replace('.', ',')}", "",
         f"Generado {r['generado']} por `experimentos/barrido_e/fase4_analisis.py`, escrito antes de tener los datos. "
         "A1 es la referencia de A3; los dos con el mismo -e y el mismo protocolo que el barrido.", "",
         "## Los dos pisos de ruido", "",
         f"- **SD media en 4–11 kHz entre las dos capturas: {num(r['piso_sd_4_11_db'])} dB**",
         f"- **Muescas perdidas entre las dos capturas: {num(100 * r['piso_muescas_perdidas'], 0)} %** "
         f"({r['notch']['sin_notch_emparejado']} de {r['notch']['validas'] + r['notch']['sin_notch_emparejado']} direcciones)",
         "", f"Frecuencias excluidas: {', '.join(num(x / 1000, 1) for x in r['frecuencias_excluidas_hz']) or 'ninguna'} kHz "
         f"({r['frecuencias_comunes']} comunes). Estado de las simulaciones: A {r['estado']['A']}, C {r['estado']['C']}.", "",
         "## Elección de -e: " + r["caracter"], "",
         "| -e | SD 4–11 kHz frente a la ref. (dB) | Muescas perdidas frente a la ref. | ¿Bajo el piso de SD? | ¿Bajo el piso de muescas? |",
         "|---|---|---|---|---|"]
    for e, x in sorted(r["candidatas_contra_ref_B"].items(), key=lambda kv: float(kv[0].split("_")[0])):
        L.append(f"| {e.replace('_y5', ' -y 5').replace('.', ',')} | {num(x['sd_4_11_db'])} | {num(100 * x['muescas_perdidas'], 0)} % "
                 f"| {'sí' if x['sd_4_11_db'] <= r['piso_sd_4_11_db'] else 'no'} "
                 f"| {'sí' if x['muescas_perdidas'] <= r['piso_muescas_perdidas'] else 'no'} |")
    el = r["eleccion"]
    L += ["", f"Por SD: -e {el['por_sd'].replace('.', ',')}. Por muescas: -e {el['por_muescas'].replace('.', ',')}. "
          f"**Elección: -e {el['final'].replace('.', ',')}** (la menor de las dos).",
          "" if el["y5_pasa_los_dos"] is None else
          f"-e 1 -y 5 {'pasa' if el['y5_pasa_los_dos'] else 'no pasa'} los dos pisos.", "",
          "## Descriptivo (no entra en la regla)", "",
          "| banda | todas (dB) | ipsilateral (dB) | contralateral (dB) |", "|---|---|---|---|"]
    for banda in ("0.9-4", "4-11", "12-16"):
        L.append(f"| {banda.replace('.', ',')} kHz | {num(b[banda]['todas'])} | {num(b[banda]['ipsilateral'])} | {num(b[banda]['contralateral'])} |")
    L += ["", "En 0,9–4 kHz es donde más pesaría el trozo de hombro que entra en la malla de A con el corte a "
          "−115 mm (limitación declarada en fase4_sujeto_A_2026-10-05.md).",
          "", f"Muesca: corrimiento mediano {num(r['notch']['mediana_hz'], 0)} Hz "
          f"[{num(r['notch']['q1_hz'], 0)}, {num(r['notch']['q3_hz'], 0)}]."]
    (SALIDA / f"informe_e{r['e']}.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    principal()
