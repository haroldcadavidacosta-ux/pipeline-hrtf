"""Exportación de los proyectos de Mesh2HRTF (listos para NumCalc), después del gradado.

Entrada: la carpeta de salida de la limpieza y el gradado, con 3Dmesh_graded_left.ply y
3Dmesh_graded_right.ply (en mm y en el sistema anatómico, que es el mismo de Mesh2HRTF:
+x nariz, +y oreja izquierda, +z arriba, origen entre los canales). Salida, en la misma
carpeta:

  myHRTF_project_L/   proyecto con la fuente en la oreja izquierda (graduada izquierda)
  myHRTF_project_R/   ídem, oreja derecha
  informe_exportacion.json

El exportador de Mesh2HRTF es un complemento de Blender, así que se corre Blender en
segundo plano con malla/blender_exportar.py. Blender es lo único que hay que tener
instalado: se busca solo (config.BLENDER_EXE para otro sitio) y el complemento viene
con la app (mesh2hrtf_1.3.0/, config.MESH2HRTF_PATH). Parámetros en config.py
(EXPORTACION_MESH2HRTF, PROYECTOS_MESH2HRTF).

La fuente de cada proyecto es UNA cara: la más cercana a la entrada del canal marcado,
(0, ±AID/2, 0) mm. Después de exportar se comprueba en los archivos del proyecto que
NC.inp use esa cara.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import numpy as np
import trimesh

import config
from malla.gradado import SALIDAS as GRADUADAS

SCRIPT_BLENDER = Path(config.CARPETA_RECURSOS) / "malla" / "blender_exportar.py"
FUENTE = {"left": "Left ear", "right": "Right ear"}
TIEMPO_MAX_S = 1800
OCULTAR = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


# --- Blender ------------------------------------------------------------------
def version_carpeta(exe: Path) -> tuple:
    """(5, 2) para ...\\Blender 5.2\\blender.exe; sirve para quedarse con la más nueva."""
    return tuple(int(n) for n in re.findall(r"\d+", exe.parent.name)) or (0,)


def buscar_blender() -> Path | None:
    if config.BLENDER_EXE:
        return Path(config.BLENDER_EXE)
    bases = {os.environ.get(v) for v in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)")} - {None}
    candidatos = [exe for base in bases for exe in Path(base, "Blender Foundation").glob("*/blender.exe")]
    if candidatos:
        return max(candidatos, key=version_carpeta)
    en_path = shutil.which("blender")
    return Path(en_path) if en_path else None


def comprobar_blender(completo: bool = False) -> tuple[bool, str]:
    """Blender existe y responde. Con completo, además carga el exportador de Mesh2HRTF
    (tarda unos segundos más)."""
    exe = buscar_blender()
    if exe is None:
        return False, ("no se encontró Blender: instalarlo desde blender.org (o poner BLENDER_EXE "
                       "en config_local.py si está en otro sitio)")
    if not exe.is_file():
        return False, f"no existe {exe} (BLENDER_EXE en config_local.py)"
    if not completo:
        argumentos = ["--version"]
    else:
        argumentos = ["--background", "--factory-startup", "--python-exit-code", "1", "--python-expr",
                      "import sys, bpy\n"
                      f"sys.path.insert(0, {str(Path(config.MESH2HRTF_PATH) / 'Mesh2Input')!r})\n"
                      "import mesh2input; mesh2input.register()\n"
                      "print('EXPORTADOR_OK', hasattr(bpy.ops.mesh2input, 'inp'))"]
    try:
        r = subprocess.run([str(exe), *argumentos], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=120, creationflags=OCULTAR)
    except (OSError, subprocess.TimeoutExpired) as ex:
        return False, f"{exe} no arranca: {ex}"
    version = next((l.strip() for l in r.stdout.splitlines() if l.startswith("Blender ")), "")
    if completo and "EXPORTADOR_OK True" not in r.stdout:
        return False, f"{exe} arranca pero no carga el exportador de Mesh2HRTF: {r.stdout[-500:]}"
    if not completo and not version:
        return False, f"{exe} no responde como Blender (código {r.returncode})"
    return True, f"{exe} ({version or 'Blender'})" + (", exportador de Mesh2HRTF cargado" if completo else "")


# --- Comprobaciones de un proyecto exportado -------------------------------------
def leer_tabla(ruta: Path) -> tuple[int, np.ndarray]:
    """Nodes.txt / Elements.txt de Mesh2HRTF: número de filas en la primera línea, luego
    filas con el índice en la primera columna."""
    lineas = ruta.read_text(encoding="utf-8").split("\n")
    cabecera = int(lineas[0].split()[0])
    return cabecera, np.loadtxt(lineas[1:], ndmin=2)


def tiene_resultados(proyecto: Path) -> bool:
    """Si NumCalc ya corrió (o se procesó la salida), el proyecto no se toca: son horas."""
    if (proyecto / "Output2HRTF").exists():
        return True
    return any(p.name != "NC.inp" for p in proyecto.glob("NumCalc/source_*/*"))


def verificar_proyecto(proyecto: Path, graduada: Path, lado: str, canal_mm: np.ndarray) -> tuple[dict, list, list]:
    """Revisa lo que dejó el exportador. Devuelve (datos, fallas, avisos)."""
    fallas, avisos, res = [], [], {"proyecto": proyecto.name}
    malla = trimesh.load(graduada, process=False)
    nodos, elementos = proyecto / "ObjectMeshes" / "Reference" / "Nodes.txt", proyecto / "ObjectMeshes" / "Reference" / "Elements.txt"
    nc = proyecto / "NumCalc" / "source_1" / "NC.inp"
    for ruta in (nodos, elementos, nc, proyecto / "parameters.json"):
        if not ruta.is_file():
            fallas.append(f"{lado}: falta {ruta.relative_to(proyecto)}")
    if fallas:
        return res, fallas, avisos

    n_nodos, N = leer_tabla(nodos)
    n_elem, E = leer_tabla(elementos)
    res |= {"nodos": n_nodos, "elementos": n_elem}
    for nombre, cabecera, filas, esperado in (("Nodes.txt", n_nodos, len(N), len(malla.vertices)),
                                              ("Elements.txt", n_elem, len(E), len(malla.faces))):
        if not cabecera == filas == esperado:
            fallas.append(f"{lado}: {nombre} dice {cabecera} en la cabecera y tiene {filas} filas; "
                          f"la malla graduada tiene {esperado}")

    m = re.search(r"#\s*(Left|Right) ear velocity source\s*\nELEM (\d+) TO (\d+) VELO", nc.read_text(encoding="utf-8"))
    if not m:
        fallas.append(f"{lado}: NC.inp no tiene la fuente en una oreja (ELEM ... VELO)")
        return res, fallas, avisos
    oreja, a, b = m.group(1) + " ear", int(m.group(2)), int(m.group(3))
    res |= {"fuente_nc": f"{oreja}: ELEM {a} TO {b}"}
    if oreja != FUENTE[lado]:
        fallas.append(f"{lado}: la fuente de NC.inp es '{oreja}', debería ser '{FUENTE[lado]}'")
    if a != b:
        fallas.append(f"{lado}: la fuente son {b - a + 1} elementos; debe ser una sola cara")
    # la cara de la fuente, desde los archivos del proyecto (Nodes.txt en metros)
    fila = E[E[:, 0] == a]
    if len(fila) == 1:
        idx = {int(i): k for k, i in enumerate(N[:, 0])}
        v = N[[idx[int(n)] for n in fila[0, 1:4]], 1:4] * 1000
        d = float(np.linalg.norm(v.mean(axis=0) - canal_mm))
        area = float(0.5 * np.linalg.norm(np.cross(v[1] - v[0], v[2] - v[0])))
        res |= {"fuente_distancia_canal_mm": round(d, 3), "fuente_area_mm2": round(area, 4)}
        if d > config.DISTANCIA_CANAL_MAX_MM:
            fallas.append(f"{lado}: la cara de la fuente está a {d:.2f} mm del canal marcado "
                          f"(máximo {config.DISTANCIA_CANAL_MAX_MM} mm)")
    else:
        fallas.append(f"{lado}: el elemento {a} de NC.inp no está en Elements.txt")

    p = json.loads((proyecto / "parameters.json").read_text(encoding="utf-8"))
    res |= {"sourceType": p.get("sourceType"), "unidad": p.get("3D_SceneUnit"),
            "frecuencias": p.get("numFrequencies"), "mallas_evaluacion": p.get("evaluationGrids")}
    if p.get("sourceType") != FUENTE[lado]:
        fallas.append(f"{lado}: parameters.json dice sourceType '{p.get('sourceType')}'")
    if p.get("3D_SceneUnit") != "mm":
        fallas.append(f"{lado}: parameters.json dice unidad '{p.get('3D_SceneUnit')}', no mm")
    return res, fallas, avisos


# --- La etapa ---------------------------------------------------------------------
def exportar(carpeta: Path, registrar=print) -> dict:
    """Exporta los dos proyectos. Devuelve (y guarda) el informe; "aprobado" dice si salió bien."""
    carpeta = Path(carpeta).resolve()    # Blender corre con otra carpeta de trabajo: rutas absolutas
    informe = {"proyectos": dict(config.PROYECTOS_MESH2HRTF), "parametros": config.EXPORTACION_MESH2HRTF,
               "mesh2hrtf": config.MESH2HRTF_PATH, "lados": {}, "avisos": [], "fallas": []}

    ok, mensaje = comprobar_blender()
    registrar(mensaje)
    informe["blender"] = mensaje
    if not ok:
        informe["fallas"].append(mensaje)
        return guardar_informe(carpeta, informe)

    # entrada: las dos graduadas (gradado aprobado) y el AID en mm para ubicar los canales
    try:
        gradado = json.loads((carpeta / "informe_gradado.json").read_text(encoding="utf-8"))
        aid_mm = json.loads((carpeta / "informe_limpieza.json").read_text(encoding="utf-8"))["escala"]["aid_mm"]
    except (FileNotFoundError, KeyError):
        gradado, aid_mm = {}, None
    if not gradado.get("aprobado") or not aid_mm:
        informe["fallas"].append("primero hay que gradar la malla (gradado aprobado y con escala en mm)")
        return guardar_informe(carpeta, informe)
    faltan = [a for a in GRADUADAS.values() if not (carpeta / a).exists()]
    if faltan:
        informe["fallas"].append(f"faltan {', '.join(faltan)}")
        return guardar_informe(carpeta, informe)
    canales = {"left": np.array([0, aid_mm / 2, 0]), "right": np.array([0, -aid_mm / 2, 0])}
    informe["canales_mm"] = {lado: c.tolist() for lado, c in canales.items()}

    # proyectos anteriores: se reemplazan, salvo que alguno ya tenga resultados de NumCalc
    # (entonces no se toca ninguno: primero se revisan los dos y después se borra)
    anteriores = [carpeta / n for n in config.PROYECTOS_MESH2HRTF.values() if (carpeta / n).exists()]
    for proyecto in anteriores:
        if tiene_resultados(proyecto):
            informe["fallas"].append(
                f"{proyecto.name} ya tiene resultados de NumCalc: no se sobrescribe. Moverlo o "
                "renombrarlo a mano para volver a exportar")
    if informe["fallas"]:
        return guardar_informe(carpeta, informe)
    for proyecto in anteriores:
        shutil.rmtree(proyecto)

    trabajo = carpeta / "exportacion_trabajo.json"
    trabajo.write_text(json.dumps({
        "programPath": str(config.MESH2HRTF_PATH),
        "parametros": config.EXPORTACION_MESH2HRTF,
        "canales_mm": informe["canales_mm"],
        "lados": {lado: {"malla": str(carpeta / GRADUADAS[lado]),
                         "proyecto": str(carpeta / config.PROYECTOS_MESH2HRTF[lado])} for lado in FUENTE},
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    exe = buscar_blender()
    registrar("Exportando con Blender en segundo plano...")
    salida_blender = []
    proceso = subprocess.Popen([str(exe), "--background", "--factory-startup", "--python-exit-code", "1",
                                "--python", str(SCRIPT_BLENDER), "--", str(trabajo)],
                               cwd=carpeta, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                               encoding="utf-8", errors="replace", creationflags=OCULTAR)
    # si Blender se cuelga, se corta a los TIEMPO_MAX_S (cerrar su salida termina el bucle)
    cortado = threading.Event()

    def cortar() -> None:
        cortado.set()
        proceso.kill()
    vigilante = threading.Timer(TIEMPO_MAX_S, cortar)
    vigilante.start()
    try:
        for linea in proceso.stdout:
            salida_blender.append(linea.rstrip())
            if linea.startswith("[exportar]"):
                registrar("  " + linea[len("[exportar]"):].strip())
        proceso.wait()
        resultado = json.loads(trabajo.read_text(encoding="utf-8")).get("resultado")
    finally:
        vigilante.cancel()
        trabajo.unlink(missing_ok=True)
    if proceso.returncode != 0 or not resultado:
        informe["fallas"].append(f"Blender falló (código {proceso.returncode})"
                                 + (f": no terminó en {TIEMPO_MAX_S} s" if cortado.is_set() else ""))
        informe["salida_blender"] = "\n".join(salida_blender[-40:])
        return guardar_informe(carpeta, informe)

    for lado, nombre in config.PROYECTOS_MESH2HRTF.items():
        res, fallas, avisos = verificar_proyecto(carpeta / nombre, carpeta / GRADUADAS[lado], lado, canales[lado])
        cara = resultado[lado]["caras_canales"][lado]
        res["fuente_normal_hacia_fuera"] = cara["normal_hacia_fuera"]
        if cara["normal_hacia_fuera"] <= 0:
            avisos.append(f"{lado}: la cara de la fuente no mira hacia fuera de la cabeza "
                          f"(componente {cara['normal_hacia_fuera']}); revisar el canal")
        informe["lados"][lado] = res
        informe["fallas"] += fallas
        informe["avisos"] += avisos
        if "fuente_distancia_canal_mm" in res:
            registrar(f"  {nombre}: {res['nodos']:,} nodos, {res['elementos']:,} elementos, "
                      f"fuente a {res['fuente_distancia_canal_mm']} mm del canal")
    return guardar_informe(carpeta, informe)


def guardar_informe(carpeta: Path, informe: dict) -> dict:
    informe["aprobado"] = not informe["fallas"] and len(informe["lados"]) == len(FUENTE)
    (carpeta / "informe_exportacion.json").write_text(json.dumps(informe, indent=2, ensure_ascii=False),
                                                      encoding="utf-8")
    return informe
