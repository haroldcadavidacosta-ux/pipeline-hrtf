"""Fase 4, prueba de repetibilidad: preparar una captura de A a un -e dado, SIN simular.

El mismo proceso que siguió B en el barrido, paso por paso:

  1. entrada: malla_final_mm.ply de la limpieza (aprobada y cortada a config.CORTE_CUELLO_MM) ->
     A<X>_3Dmesh_orig.stl, como hace malla/gradado.preparar_entrada
  2. gradado: -x 0.5 -y 10 -e <e> -s left -v, con los reintentos de malla/gradado.gradar_lado si el
     binario de 2022 se cae
  3. geometría: caras, F = 2V - 4, aristas, Hausdorff en la pina contra su propia malla de entrada
  4. exportación con la plantilla del barrido (900-24000 Hz cada 300 Hz, Default y ARI, ML-FMM BEM); los
     canales se ubican con el AID de esta captura
  5. NumCalc -estimate_ram y comprobación de que NC.inp tiene el mismo vector y los mismos parámetros
     que el barrido

La condición se llama A<X>_<e> y vive en datos/experimentos/barrido_e/e_A<X>_<e>/, para que el
conductor de la fase 2 la simule igual que las demás (tanda en fase2.py).

Uso:  .venv/Scripts/python.exe experimentos/barrido_e/fase4_preparar.py <A|C> <e>
Escribe e_A<X>_<e>/preparacion.json. No lanza ninguna simulación.
"""
import json
import shutil
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
from malla.gradado import RUIDO_REINTENTO_MM, REINTENTOS_MAX, salio_bien, sin_ventanas_de_error   # noqa: E402
from fase1_geometria import aristas, hausdorff, leer_verbose, malla_pymeshlab, RADIO_OREJA_MM   # noqa: E402
from fase2 import vector_nc, lineas_fisicas, sha256              # noqa: E402

BARRIDO = RAIZ / "datos" / "experimentos" / "barrido_e"
SALIDAS = RAIZ / "datos" / "salidas"
NUMCALC = Path(r"C:\Users\Usuario\Documents\PROYECTO DE GRADO\Mesh2HRTF\mesh2hrtf-tools-code-investigacion\NumCalc_WindowsExe\NumCalc.exe")
REFERENCIA_NC = BARRIDO / "e_1" / "DIAGNOSTICO_proyecto_L_e1" / "NumCalc" / "source_1" / "NC.inp"


def gradar(carpeta: Path, entrada: Path, malla: str, e: str) -> tuple[subprocess.CompletedProcess, int, list]:
    """Gradado con los reintentos de malla/gradado.gradar_lado (misma semilla por intento)."""
    def correr(archivo: str) -> subprocess.CompletedProcess:
        args = ["-x", "0.5", "-y", "10", "-e", e, "-s", "left", "-v", "-i", archivo, "-o", malla]
        return subprocess.run([str(config.GRADING_EXE), *args], cwd=carpeta, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=900), args

    r, args = correr("../" + entrada.name)
    if salio_bien(r, carpeta, malla):
        return r, 0, args
    base = trimesh.load(entrada, process=False)
    temporal = carpeta / "3Dmesh_reintento_left.stl"
    try:
        for intento in range(1, REINTENTOS_MAX + 1):
            ruido = np.random.default_rng(intento).normal(0, RUIDO_REINTENTO_MM, base.vertices.shape)
            trimesh.Trimesh(base.vertices + ruido, base.faces, process=False).export(temporal, file_type="stl")
            (carpeta / malla).unlink(missing_ok=True)
            r, args = correr(temporal.name)
            if salio_bien(r, carpeta, malla):
                return r, intento, args
    finally:
        temporal.unlink(missing_ok=True)
    return r, REINTENTOS_MAX, args


def principal() -> None:
    sin_ventanas_de_error()
    captura, e = sys.argv[1].upper(), sys.argv[2]
    nombre = f"A{captura}_{e}"
    carpeta = BARRIDO / f"e_{nombre}"
    carpeta.mkdir(exist_ok=True)
    malla = f"3Dmesh_graded_left_e{nombre}.ply"
    r = {"condicion": nombre, "sujeto": "A", "captura": captura, "e": e}

    # 1. entrada
    limpieza = SALIDAS / f"A {captura}"
    inf = json.loads((limpieza / "informe_limpieza.json").read_text(encoding="utf-8"))
    corte = inf.get("corte_cuello", {})
    if not inf["control_calidad"]["aprobado"] or not corte.get("aplicado") or corte.get("z_mm") != config.CORTE_CUELLO_MM:
        sys.exit(f"A {captura}: la limpieza no está aprobada o no está cortada a {config.CORTE_CUELLO_MM} mm")
    entrada = BARRIDO / f"A{captura}_3Dmesh_orig.stl"
    if not entrada.exists():
        m = trimesh.load(limpieza / "malla_final_mm.ply", process=False)
        if not m.is_watertight:
            sys.exit("malla_final_mm.ply no es cerrada")
        m.export(entrada, file_type="stl")
    aid = inf["escala"]["aid_mm"]
    canal = np.array([0.0, aid / 2, 0.0])
    r["entrada"] = {"limpieza": str(limpieza), "aid_mm": aid, "escala": inf["escala"]["factor"],
                    "corte_cuello_mm": corte["z_mm"], "tapa_cuello": inf.get("tapa_cuello"),
                    "sha256_entrada": sha256(entrada)}

    # 2. gradado
    if not (carpeta / malla).exists():
        g, reintentos, args = gradar(carpeta, entrada, malla, e)
        (carpeta / "grading_verbose.txt").write_text(g.stdout + g.stderr, encoding="utf-8")
        (carpeta / "comando_grading.txt").write_text("hrtf_mesh_grading " + " ".join(args) + "\n", encoding="utf-8")
        r["reintentos_gradado"] = reintentos
        if not salio_bien(g, carpeta, malla):
            sys.exit(f"el gradado falló (código {g.returncode}) tras {reintentos} reintentos; ver grading_verbose.txt")
    r["comando_gradado"] = (carpeta / "comando_grading.txt").read_text(encoding="utf-8").strip()
    r["verbose"] = leer_verbose((carpeta / "grading_verbose.txt").read_text(encoding="utf-8", errors="replace"))

    # 3. geometría
    m = trimesh.load(carpeta / malla, process=False)
    oreja = np.linalg.norm(m.triangles_center - canal, axis=1) < RADIO_OREJA_MM
    r["geometria"] = {
        "vertices": len(m.vertices), "caras": len(m.faces), "F_igual_2V_menos_4": len(m.faces) == 2 * len(m.vertices) - 4,
        "cerrada": bool(m.is_watertight), "caras_oreja": int(oreja.sum()),
        "aristas_toda": aristas(m), "aristas_oreja": aristas(m, oreja),
        "hausdorff_oreja_original_a_graduada": hausdorff(malla_pymeshlab(entrada, canal), malla_pymeshlab(carpeta / malla)),
        "hausdorff_oreja_graduada_a_original": hausdorff(malla_pymeshlab(carpeta / malla, canal), malla_pymeshlab(entrada)),
        "frecuencia_util": predecir(np.asarray(m.vertices), np.asarray(m.faces), canal)}
    r["sha256_malla"] = sha256(carpeta / malla)

    # 4. exportación con la plantilla del barrido; canales de esta captura
    proyecto = carpeta / f"DIAGNOSTICO_proyecto_L_e{nombre}"
    if not (proyecto / "NumCalc" / "source_1" / "NC.inp").exists():
        if proyecto.exists():
            shutil.rmtree(proyecto)
        plantilla = json.loads((BARRIDO / "e_1" / "trabajo_exportacion.json").read_text(encoding="utf-8"))
        trabajo = {"programPath": plantilla["programPath"],
                   "parametros": plantilla["parametros"] | {
                       "title": f"DIAGNOSTICO repetibilidad A {captura} -e {e} (NO es una HRTF valida)"},
                   "canales_mm": {"left": canal.tolist(), "right": (-canal).tolist()},
                   "lados": {"left": {"malla": (carpeta / malla).as_posix(), "proyecto": proyecto.as_posix()}}}
        ruta_trabajo = carpeta / "trabajo_exportacion.json"
        ruta_trabajo.write_text(json.dumps(trabajo, indent=2), encoding="utf-8")
        blender = Path(config.BLENDER_EXE) if config.BLENDER_EXE else exportacion.buscar_blender()
        b = subprocess.run([str(blender), "--background", "--factory-startup", "--python-exit-code", "1",
                            "--python", str(exportacion.SCRIPT_BLENDER), "--", str(ruta_trabajo)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        (carpeta / "exportacion_blender.log").write_text(b.stdout + b.stderr, encoding="utf-8")
        if b.returncode != 0:
            sys.exit(f"la exportación falló (código {b.returncode}); ver exportacion_blender.log")
    verif, errores, avisos = exportacion.verificar_proyecto(proyecto, carpeta / malla, "left", canal)
    r["verificacion_proyecto"] = {"datos": verif, "errores": errores, "avisos": avisos}

    # 5. RAM estimada y comparabilidad del NC.inp con el barrido
    fuente = proyecto / "NumCalc" / "source_1"
    if not (fuente / "Memory.txt").exists():
        subprocess.run([str(NUMCALC), "-estimate_ram"], cwd=fuente, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=1800, check=True)
    M = np.loadtxt(fuente / "Memory.txt", ndmin=2)
    r["numcalc"] = {"ram_estimada_max_gb": float(M[:, 2].max()), "ram_estimada_24khz_gb": float(M[-1, 2]),
                    "vector_igual_al_barrido": vector_nc(fuente / "NC.inp") == vector_nc(REFERENCIA_NC),
                    "parametros_iguales_al_barrido": lineas_fisicas(fuente / "NC.inp") == lineas_fisicas(REFERENCIA_NC)}
    (carpeta / "preparacion.json").write_text(json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")

    g = r["geometria"]
    print(f"{nombre}: {g['caras']} caras (F=2V-4: {g['F_igual_2V_menos_4']}, cerrada: {g['cerrada']}), "
          f"oreja {g['caras_oreja']} caras; Hausdorff pina RMS/máx "
          f"{g['hausdorff_oreja_original_a_graduada']['rms_mm']}/{g['hausdorff_oreja_original_a_graduada']['max_mm']} mm; "
          f"reintentos {r.get('reintentos_gradado', '-')}")
    print(f"   proyecto: errores {errores or 'ninguno'}; avisos {avisos or 'ninguno'}")
    print(f"   NumCalc: {r['numcalc']}")


if __name__ == "__main__":
    principal()
