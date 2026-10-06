"""Condición -e 1 -y 5: prepararla SIN simular, para preinscribir las predicciones antes de correr.

Pregunta: ¿la distorsión de 12-16 kHz de -e 1 viene de la discretización de la cabeza? -y 5 limita la
arista de la cabeza sin tocar la oreja (cuyas aristas ya son < 5 mm con -y 10), así que separa las dos
causas. Pasos:

  1. gradado: -x 0.5 -y 5 -e 1 -s left -v, desde el mismo 3Dmesh_orig.stl
  2. geometría: caras, F = 2V - 4, aristas por región, Hausdorff en la pina contra la original (como
     la fase 1) y contra la oreja de -e 1 -y 10 (¿la oreja quedó igual?)
  3. exportación del proyecto de diagnóstico con los mismos parámetros que las cuatro condiciones
  4. NumCalc -estimate_ram y comprobación de que NC.inp tiene el mismo vector y los mismos parámetros
     que -e 1 -y 10

Uso:  .venv/Scripts/python.exe experimentos/barrido_e/y5_preparar.py
Escribe e_1_y5/preparacion.json. No lanza ninguna simulación.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import trimesh

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config                                                    # noqa: E402
from malla import exportacion                                    # noqa: E402
from malla.discretizacion import predecir                        # noqa: E402
from malla.gradado import sin_ventanas_de_error                  # noqa: E402
from fase1_geometria import aristas, hausdorff, leer_verbose, malla_pymeshlab, RADIO_OREJA_MM   # noqa: E402
from fase2 import vector_nc, lineas_fisicas, sha256              # noqa: E402

BARRIDO = RAIZ / "datos" / "experimentos" / "barrido_e"
CARPETA = BARRIDO / "e_1_y5"
MALLA = "3Dmesh_graded_left_e1_y5.ply"
PROYECTO = "DIAGNOSTICO_proyecto_L_e1_y5"
ARGUMENTOS = ["-x", "0.5", "-y", "5", "-e", "1", "-s", "left", "-v", "-i", "../3Dmesh_orig.stl", "-o", MALLA]
NUMCALC = Path(r"C:\Users\Usuario\Documents\PROYECTO DE GRADO\Mesh2HRTF\mesh2hrtf-tools-code-investigacion\NumCalc_WindowsExe\NumCalc.exe")


def principal() -> None:
    sin_ventanas_de_error()
    CARPETA.mkdir(exist_ok=True)
    r = {"condicion": "-e 1 -y 5", "comando_gradado": "hrtf_mesh_grading " + " ".join(ARGUMENTOS)}

    # 1. gradado
    if not (CARPETA / MALLA).exists():
        g = subprocess.run([str(config.GRADING_EXE), *ARGUMENTOS], cwd=CARPETA, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=600)
        (CARPETA / "grading_verbose.txt").write_text(g.stdout + g.stderr, encoding="utf-8")
        (CARPETA / "comando_grading.txt").write_text(r["comando_gradado"] + "\n", encoding="utf-8")
        if g.returncode != 0 or not (CARPETA / MALLA).exists():
            sys.exit(f"el gradado falló (código {g.returncode}); ver grading_verbose.txt")
    r["verbose"] = leer_verbose((CARPETA / "grading_verbose.txt").read_text(encoding="utf-8", errors="replace"))

    # 2. geometría
    aid = json.loads((BARRIDO / "informe_limpieza.json").read_text(encoding="utf-8"))["escala"]["aid_mm"]
    canal = np.array([0.0, aid / 2, 0.0])
    original = BARRIDO / "3Dmesh_orig.stl"
    ref10 = BARRIDO / "e_1" / "3Dmesh_graded_left_e1.ply"
    geo = {}
    for nombre, ruta in (("e1_y5", CARPETA / MALLA), ("e1_y10", ref10)):
        m = trimesh.load(ruta, process=False)
        oreja = np.linalg.norm(m.triangles_center - canal, axis=1) < RADIO_OREJA_MM
        geo[nombre] = {"vertices": len(m.vertices), "caras": len(m.faces), "F_igual_2V_menos_4": len(m.faces) == 2 * len(m.vertices) - 4,
                       "cerrada": bool(m.is_watertight), "caras_oreja": int(oreja.sum()),
                       "aristas_toda": aristas(m), "aristas_oreja": aristas(m, oreja),
                       "hausdorff_oreja_original_a_graduada": hausdorff(malla_pymeshlab(original, canal), malla_pymeshlab(ruta)),
                       "hausdorff_oreja_graduada_a_original": hausdorff(malla_pymeshlab(ruta, canal), malla_pymeshlab(original)),
                       "frecuencia_util": predecir(np.asarray(m.vertices), np.asarray(m.faces), canal)}
    # ¿la oreja quedó igual? distancia entre las dos graduadas, dentro de la esfera, en ambos sentidos
    geo["oreja_y5_contra_y10"] = {
        "y5_a_y10": hausdorff(malla_pymeshlab(CARPETA / MALLA, canal), malla_pymeshlab(ref10)),
        "y10_a_y5": hausdorff(malla_pymeshlab(ref10, canal), malla_pymeshlab(CARPETA / MALLA))}
    r["geometria"] = geo
    r["sha256_malla"] = sha256(CARPETA / MALLA)

    # 3. exportación con los mismos parámetros que las cuatro condiciones
    proyecto = CARPETA / PROYECTO
    if not (proyecto / "NumCalc" / "source_1" / "NC.inp").exists():
        plantilla = json.loads((BARRIDO / "e_1" / "trabajo_exportacion.json").read_text(encoding="utf-8"))
        trabajo = {"programPath": plantilla["programPath"],
                   "parametros": plantilla["parametros"] | {"title": "DIAGNOSTICO barrido -e 1 -y 5 (NO es una HRTF valida)"},
                   "canales_mm": plantilla["canales_mm"],
                   "lados": {"left": {"malla": (CARPETA / MALLA).as_posix(), "proyecto": proyecto.as_posix()}}}
        ruta_trabajo = CARPETA / "trabajo_exportacion.json"
        ruta_trabajo.write_text(json.dumps(trabajo, indent=2), encoding="utf-8")
        blender = Path(config.BLENDER_EXE) if config.BLENDER_EXE else exportacion.buscar_blender()
        b = subprocess.run([str(blender), "--background", "--factory-startup", "--python-exit-code", "1",
                            "--python", str(exportacion.SCRIPT_BLENDER), "--", str(ruta_trabajo)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        (CARPETA / "exportacion_blender.log").write_text(b.stdout + b.stderr, encoding="utf-8")
        if b.returncode != 0:
            sys.exit(f"la exportación falló (código {b.returncode}); ver exportacion_blender.log")
    verif, errores, avisos = exportacion.verificar_proyecto(proyecto, CARPETA / MALLA, "left", canal)
    r["verificacion_proyecto"] = {"datos": verif, "errores": errores, "avisos": avisos}

    # 4. RAM estimada y comparabilidad del NC.inp
    fuente = proyecto / "NumCalc" / "source_1"
    if not (fuente / "Memory.txt").exists():
        subprocess.run([str(NUMCALC), "-estimate_ram"], cwd=fuente, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=1800, check=True)
    M = np.loadtxt(fuente / "Memory.txt", ndmin=2)
    M10 = np.loadtxt(BARRIDO / "e_1" / "DIAGNOSTICO_proyecto_L_e1" / "NumCalc" / "source_1" / "Memory.txt", ndmin=2)
    nc10 = BARRIDO / "e_1" / "DIAGNOSTICO_proyecto_L_e1" / "NumCalc" / "source_1" / "NC.inp"
    r["numcalc"] = {"ram_estimada_max_gb": float(M[:, 2].max()), "ram_estimada_24khz_gb": float(M[-1, 2]),
                    "ram_estimada_max_gb_e1_y10": float(M10[:, 2].max()),
                    "vector_igual_a_e1_y10": vector_nc(fuente / "NC.inp") == vector_nc(nc10),
                    "parametros_iguales_a_e1_y10": lineas_fisicas(fuente / "NC.inp") == lineas_fisicas(nc10)}
    (CARPETA / "preparacion.json").write_text(json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: r[k] for k in ("numcalc", "verificacion_proyecto")}, indent=1, ensure_ascii=False)[:2500])
    for n in ("e1_y5", "e1_y10"):
        x = geo[n]
        print(n, x["caras"], x["F_igual_2V_menos_4"], x["cerrada"], "oreja", x["caras_oreja"], x["aristas_oreja"],
              "HD", x["hausdorff_oreja_original_a_graduada"]["rms_mm"], x["hausdorff_oreja_original_a_graduada"]["max_mm"],
              {k: round(v["frecuencia_util_hz"]) for k, v in x["frecuencia_util"].items() if isinstance(v, dict)},
              {k: v["arista_mediana_mm"] for k, v in x["frecuencia_util"].items() if isinstance(v, dict)})
    print("oreja y5 vs y10", geo["oreja_y5_contra_y10"])


if __name__ == "__main__":
    principal()
