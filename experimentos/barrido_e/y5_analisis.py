"""Análisis de la condición -e 1 -y 5, escrito ANTES de tener sus datos (las predicciones están en
predicciones_e1_y5_2026-09-29.md, commit 5aa8207). Solo lee: fase2/ (las cuatro condiciones) y fase2_y5/.

  Comparación PRINCIPAL:  -e 1 -y 5 contra -e 1 -y 10 (cambia solo la cabeza; es la única limpia)
  Comparación secundaria: -e 1 -y 5 contra -e 0,5 (confundida en 12-16 kHz: la referencia tiene la
                          cabeza más gruesa que -y 5)

Mismo método que la fase 3: rejilla Default ponderada por área de Voronoi, SD media por banda, notch
sobre todas las direcciones con el mismo criterio. En cada comparación se excluyen las frecuencias que
no convergieron en cualquiera de las dos condiciones.

Uso:  .venv/Scripts/python.exe experimentos/barrido_e/y5_analisis.py
Escribe datos/experimentos/barrido_e/fase3/y5/: metricas_y5.json e informe_y5.md.
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
SALIDA = BARRIDO / "fase3" / "y5"
CONDICIONES = {  # nombre: (carpeta de la fase 2, clave en su progreso.json, malla graduada)
    "y5": (BARRIDO / "fase2_y5", "1_y5", BARRIDO / "e_1_y5" / "3Dmesh_graded_left_e1_y5.ply"),
    "y10": (BARRIDO / "fase2", "1", BARRIDO / "e_1" / "3Dmesh_graded_left_e1.ply"),
    "ref": (BARRIDO / "fase2", "0.5", BARRIDO / "e_0.5" / "3Dmesh_graded_left_e0.5.ply"),
}
NOMBRE = {"y5": "-e 1 -y 5", "y10": "-e 1 -y 10", "ref": "-e 0,5 -y 10 (ref.)"}
# Predicciones preinscritas (valores exactos del archivo del commit 5aa8207)
PRED = {
    "B_4_11_max": 0.5, "B_4_11_refuta": 0.8, "B_12_16_min": 1.5, "B_12_16_factor": 2.0, "B_ipsi_4_11_max": 0.3,
    "A_4_11": (0.85, 1.15), "A_12_16_max": 2.5,
}


def cargar(nombre: str) -> dict:
    carpeta, clave, _ = CONDICIONES[nombre]
    s = sf.read_sofa(str(carpeta / f"e_{clave}" / "Output2HRTF" / "HRTF_Default.sofa"), verify=False)
    H = (np.asarray(s.Data_Real) + 1j * np.asarray(s.Data_Imag))[:, 0, :]
    prog = json.loads((carpeta / "progreso.json").read_text(encoding="utf-8"))["condiciones"][clave]
    return {"f": np.asarray(s.N, dtype=float), "pos": np.asarray(s.SourcePosition, dtype=float),
            "db": 20 * np.log10(np.abs(H)), "progreso": prog,
            "divergidas": sorted(r["frecuencia_hz"] for r in prog["pasos"].values() if r["estado"] == "no convergió")}


def comparar(a: dict, b: dict, w: np.ndarray, ipsi: np.ndarray, contra: np.ndarray) -> dict:
    excl = sorted(set(a["divergidas"]) | set(b["divergidas"]))
    k = ~np.isin(a["f"], excl)
    fc = a["f"][k]
    D = (a["db"] - b["db"])[:, k]
    s = {"todas": F.sd_f(D, w), "ipsilateral": F.sd_f(D, w, ipsi), "contralateral": F.sd_f(D, w, contra)}
    bandas = {bn: {h: float(v[(fc >= lo) & (fc <= hi)].mean()) for h, v in s.items()} for bn, (lo, hi) in F.BANDAS_SD.items()}
    return {"frecuencias_excluidas_hz": excl, "frecuencias_comunes": int(k.sum()), "sd_bandas_db": bandas,
            "sd_f_db": {f"{x:.0f}": float(v) for x, v in zip(fc, s["todas"])},
            "notch": {"todas": F.notch_distribucion(a["f"], b["db"], a["db"], np.ones(len(w), bool)),
                      "ipsilateral": F.notch_distribucion(a["f"], b["db"], a["db"], ipsi)}}


def costo(nombre: str, d: dict) -> dict:
    pasos = d["progreso"]["pasos"].values()
    corr = d["progreso"]["corridas"]
    return {"ram_pico_proceso_gb": max(r["ram_pico_proceso_gb"] for r in pasos if r.get("ram_pico_proceso_gb") is not None),
            "tiempo_pared_h": sum(c.get("horas_reales", 0) for c in corr),
            "tiempo_suma_frecuencias_h": sum(r["minutos"] for r in pasos) / 60,
            "frecuencias_divergidas": d["divergidas"]}


def principal() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    d = {n: cargar(n) for n in CONDICIONES}
    for n in d:
        if not (np.array_equal(d[n]["f"], d["ref"]["f"]) and np.allclose(d[n]["pos"], d["ref"]["pos"])):
            raise SystemExit(f"{n}: frecuencias o direcciones distintas de la referencia")
    pos = d["ref"]["pos"]
    w = F.pesos_voronoi(pos)
    y = F.lateral(pos)
    ipsi, contra = y > F.LATERAL_MIN, y < -F.LATERAL_MIN
    canal = np.array(F.leer_json(BARRIDO / "fase1" / "geometria.json")["canal_izq_mm"])
    from malla.discretizacion import predecir_archivo
    import trimesh

    m = {"generado": datetime.now().astimezone().isoformat(timespec="seconds"), "predicciones_commit": "5aa8207",
         "principal_y5_contra_y10": comparar(d["y5"], d["y10"], w, ipsi, contra),
         "secundaria_y5_contra_ref": comparar(d["y5"], d["ref"], w, ipsi, contra),
         "y10_contra_ref": comparar(d["y10"], d["ref"], w, ipsi, contra),
         "condiciones": {}}
    for n, (_, _, malla) in CONDICIONES.items():
        g = trimesh.load(malla, process=False)
        mx = g.edges_unique_length[g.faces_unique_edges].max(axis=1)
        fuera = np.linalg.norm(g.triangles_center - canal, axis=1) >= F.RADIO_OREJA_MM
        a, x = g.area_faces[fuera], mx[fuera]
        o = np.argsort(x)
        cw = np.cumsum(a[o]) / a.sum()
        m["condiciones"][n] = costo(n, d[n]) | {
            "caras": int(len(g.faces)),
            "cabeza_arista_mediana_por_area_mm": float(x[o][np.searchsorted(cw, 0.5)]),
            "cabeza_arista_p90_por_caras_mm": float(np.percentile(x, 90)),
            "frecuencia_util": predecir_archivo(malla, canal)}

    # evaluación de las predicciones preinscritas
    B, A = m["principal_y5_contra_y10"]["sd_bandas_db"], m["secundaria_y5_contra_ref"]["sd_bandas_db"]
    ev = [
        ("B: 4–11 kHz, SD(-y 5 frente a -y 10) ≤ 0,5 dB", B["4-11"]["todas"] <= PRED["B_4_11_max"], B["4-11"]["todas"],
         "refutada si > 0,8 dB" + (" → REFUTADA" if B["4-11"]["todas"] > PRED["B_4_11_refuta"] else "")),
        ("B: 12–16 kHz, SD ≥ 1,5 dB y ≥ 2 veces la de 4–11 kHz",
         B["12-16"]["todas"] >= PRED["B_12_16_min"] and B["12-16"]["todas"] >= PRED["B_12_16_factor"] * B["4-11"]["todas"],
         B["12-16"]["todas"], f"cociente 12–16 / 4–11 = {B['12-16']['todas'] / B['4-11']['todas']:.2f}"),
        ("B: 4–11 kHz ipsilateral ≤ 0,3 dB y contralateral mayor", B["4-11"]["ipsilateral"] <= PRED["B_ipsi_4_11_max"]
         and B["4-11"]["contralateral"] > B["4-11"]["ipsilateral"], B["4-11"]["ipsilateral"],
         f"contralateral {B['4-11']['contralateral']:.2f} dB"),
        ("A (secundaria): 4–11 kHz frente a la ref. entre 0,85 y 1,15 dB",
         PRED["A_4_11"][0] <= A["4-11"]["todas"] <= PRED["A_4_11"][1], A["4-11"]["todas"],
         "refutada por abajo (< 0,85) = la cabeza pesa en la banda de la pina" if A["4-11"]["todas"] < PRED["A_4_11"][0] else ""),
        ("A (secundaria): 12–16 kHz frente a la ref. ≤ 2,5 dB", A["12-16"]["todas"] <= PRED["A_12_16_max"], A["12-16"]["todas"],
         "confundida: la referencia tiene la cabeza más gruesa"),
    ]
    m["evaluacion"] = [{"prediccion": p, "cumplida": bool(ok), "valor_db": float(v), "nota": nota} for p, ok, v, nota in ev]
    cabeza_ok = B["12-16"]["todas"] >= PRED["B_12_16_min"] and B["12-16"]["todas"] >= PRED["B_12_16_factor"] * B["4-11"]["todas"]
    m["formula"] = {"sd_12_16_baja_contra_y10": bool(cabeza_ok),
                    "veredicto": ("falsada la mediana por caras; gana la estadística de cola (p90 por caras)" if cabeza_ok
                                  else "la bajada preinscrita no se da: la mediana por caras no queda falsada por esta corrida")}
    c = m["condiciones"]
    m["candidata_produccion"] = {
        "cabeza_mas_fina_que_ref": c["y5"]["cabeza_arista_mediana_por_area_mm"] < c["ref"]["cabeza_arista_mediana_por_area_mm"],
        "menos_tiempo_que_ref": c["y5"]["tiempo_pared_h"] < c["ref"]["tiempo_pared_h"],
        "menos_ram_que_ref": c["y5"]["ram_pico_proceso_gb"] < c["ref"]["ram_pico_proceso_gb"]}
    m["candidata_produccion"]["quinta_candidata"] = all(m["candidata_produccion"].values())
    (SALIDA / "metricas_y5.json").write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
    escribir_informe(m)
    print(f"Listo: {SALIDA}")


def escribir_informe(m: dict) -> None:
    num, c = F.num, m["condiciones"]
    P, S, R = m["principal_y5_contra_y10"], m["secundaria_y5_contra_ref"], m["y10_contra_ref"]
    L = ["# -e 1 -y 5: resultado frente a las predicciones preinscritas", "",
         f"Generado {m['generado']} por `experimentos/barrido_e/y5_analisis.py`, escrito antes de tener los datos. "
         f"Predicciones: `experimentos/barrido_e/predicciones_e1_y5_2026-09-29.md` (commit {m['predicciones_commit']}).", "",
         "## Predicciones preinscritas", "", "| predicción | valor medido (dB) | ¿cumplida? | nota |", "|---|---|---|---|"]
    for e in m["evaluacion"]:
        L.append(f"| {e['prediccion']} | {num(e['valor_db'])} | {'sí' if e['cumplida'] else 'no'} | {e['nota']} |")
    L += ["", "## Comparación principal: -e 1 -y 5 frente a -e 1 -y 10", "",
          "Cambia solo la cabeza (la oreja difiere 0,027 mm RMS entre las dos mallas). Es la única comparación limpia.", "",
          "| banda | todas (dB) | ipsilateral (dB) | contralateral (dB) |", "|---|---|---|---|"]
    for b in ("4-11", "12-16"):
        x = P["sd_bandas_db"][b]
        L.append(f"| {b.replace('-', '–')} kHz | {num(x['todas'])} | {num(x['ipsilateral'])} | {num(x['contralateral'])} |")
    L += ["", f"Frecuencias excluidas (no convergieron en alguna de las dos): "
          f"{', '.join(num(x / 1000, 1) for x in P['frecuencias_excluidas_hz']) or 'ninguna'} kHz.",
          "", "## Comparación secundaria: -e 1 -y 5 frente a -e 0,5 (confundida en 12–16 kHz)", "",
          f"**Advertencia:** la referencia tiene la cabeza más gruesa ({num(c['ref']['cabeza_arista_mediana_por_area_mm'], 1)} mm "
          f"de arista mediana por área fuera de la oreja) que -e 1 -y 5 ({num(c['y5']['cabeza_arista_mediana_por_area_mm'], 1)} mm): "
          "en 12–16 kHz esta SD mide también el error de discretización de la propia referencia.", "",
          "| banda | -e 1 -y 5 frente a la ref. (dB) | -e 1 -y 10 frente a la ref. (dB) |", "|---|---|---|"]
    for b in ("4-11", "12-16"):
        L.append(f"| {b.replace('-', '–')} kHz | {num(S['sd_bandas_db'][b]['todas'])} | {num(R['sd_bandas_db'][b]['todas'])} |")
    ns, nr = S["notch"]["todas"], R["notch"]["todas"]
    L += ["", f"Muescas frente a la referencia: -e 1 -y 5 pierde {num(100 * ns['fraccion_perdidas'], 0)} % "
          f"(corrimiento mediano {num(ns['mediana_hz'], 0)} Hz, cambio de profundidad mediano "
          f"{num(ns['cambio_profundidad_db']['mediana'], 2)} dB); -e 1 -y 10 pierde {num(100 * nr['fraccion_perdidas'], 0)} %.",
          "", "## Frente a la referencia en las cuatro dimensiones", "",
          "| | caras | arista mediana por área, cabeza (mm) | RAM pico (GB) | tiempo de pared (h) | SD 4–11 kHz frente a la ref. (dB) | SD 12–16 kHz frente a la ref. (dB) | frecuencias divergidas |",
          "|---|---|---|---|---|---|---|---|"]
    sd_ref = {"y5": S, "y10": R}
    for n in ("ref", "y10", "y5"):
        x = c[n]
        s = sd_ref.get(n)
        L.append(f"| {NOMBRE[n]} | {x['caras']:,}".replace(",", ".") + f" | {num(x['cabeza_arista_mediana_por_area_mm'], 1)}"
                 f" | {num(x['ram_pico_proceso_gb'])} | {num(x['tiempo_pared_h'])}"
                 f" | {'—' if s is None else num(s['sd_bandas_db']['4-11']['todas'])} | {'—' if s is None else num(s['sd_bandas_db']['12-16']['todas'])}"
                 f" | {len(x['frecuencias_divergidas'])} |")
    q = m["candidata_produccion"]
    L += ["", "## Interpretación", "",
          f"**La fórmula de frecuencia útil:** {m['formula']['veredicto']}."]
    if m["formula"]["sd_12_16_baja_contra_y10"]:
        L.append("Se corrige `malla/discretizacion.py` para usar el percentil 90 por caras. **Causa alternativa no "
                 "descartada:** la bajada también podría deberse a mejor condicionamiento del sistema o a un "
                 "comportamiento distinto del FMM con otra distribución de tamaños de elemento; con una sola corrida no "
                 "se puede separar de la discretización.")
    L += ["", "**Candidata para producción:** "
          + ("-e 1 -y 5 es mejor que -e 0,5 en cabeza, tiempo y memoria a la vez: **es una quinta candidata para "
             "producción**, a evaluar con los mismos dos umbrales de la fase 4." if q["quinta_candidata"] else
             "-e 1 -y 5 no es mejor que -e 0,5 en las tres cosas a la vez (cabeza "
             f"{'sí' if q['cabeza_mas_fina_que_ref'] else 'no'}, tiempo {'sí' if q['menos_tiempo_que_ref'] else 'no'}, "
             f"memoria {'sí' if q['menos_ram_que_ref'] else 'no'}).")]
    (SALIDA / "informe_y5.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    principal()
