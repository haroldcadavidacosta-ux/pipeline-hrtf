"""Gradado de la malla para Mesh2HRTF con hrtf_mesh_grading (Palm et al., DAGA 2021).

Entrada: la carpeta de salida de la limpieza, con malla_final_mm.ply (cerrada, en mm y en
el sistema anatómico: origen entre los canales, +y oreja izquierda, +x adelante, +z
arriba). Se copia como 3Dmesh_orig.stl, que es la entrada que espera Mesh2HRTF, y se
gradúa una vez por lado:

  3Dmesh_graded_left.ply    elementos finos en la oreja izquierda
  3Dmesh_graded_right.ply   elementos finos en la oreja derecha
  informe_gradado.json

El binario (grading/, con sus DLL) viene con la app; su ruta es config.GRADING_EXE.
Parámetros en config.py (GRADING_X_MM, GRADING_E_MM, GRADING_Y_MM).
"""
import ctypes
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import trimesh

import config

ENTRADA = "3Dmesh_orig.stl"
SALIDAS = {"left": "3Dmesh_graded_left.ply", "right": "3Dmesh_graded_right.ply"}
MALLA_MM = "malla_final_mm.ply"
TIEMPO_MAX_S = 600              # por lado; con una malla sana tarda segundos
REINTENTOS_MAX = 5              # si el programa se cae (ver gradar_lado)
DLL_NO_ENCONTRADA = 0xC0000135  # código de salida de Windows cuando falta una DLL


def sin_ventanas_de_error() -> None:
    """Si falta una DLL, Windows abre una ventana modal que deja el proceso colgado.
    Con este modo (que heredan los procesos hijos) el proceso termina con un código."""
    if sys.platform == "win32":
        ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x8000)  # SEM_FAILCRITICALERRORS | SEM_NOOPENFILEERRORBOX


def ejecutar(argumentos: list[str], cwd: Path, tiempo_max: float) -> subprocess.CompletedProcess:
    sin_ventanas_de_error()
    ocultar = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    # la ayuda del programa trae comillas tipográficas en UTF-8
    return subprocess.run([str(config.GRADING_EXE), *argumentos], cwd=cwd, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=tiempo_max,
                          creationflags=ocultar)


def comprobar_binario() -> tuple[bool, str]:
    """El binario existe y arranca: sin argumentos imprime la ayuda (y sale con 1)."""
    exe = Path(config.GRADING_EXE)
    if not exe.is_file():
        return False, f"no existe {exe}"
    try:
        # cwd neutro: Windows también busca DLL en la carpeta de trabajo y taparía una que falte
        r = ejecutar([], Path(config.CARPETA_APP).anchor, 30)
    except (OSError, subprocess.TimeoutExpired) as ex:
        return False, f"{exe} no arranca: {ex}"
    if r.returncode & 0xFFFFFFFF == DLL_NO_ENCONTRADA:
        return False, f"{exe} no arranca: falta una DLL (deben estar al lado del .exe)"
    if "Example usage" not in r.stdout + r.stderr:
        return False, f"{exe} arranca pero no imprime la ayuda (código {r.returncode})"
    return True, f"{exe} arranca e imprime la ayuda"


def leer_verbose(texto: str) -> dict:
    """Lo que informa el programa con -v: canales estimados (y en mm) y número de caras."""
    datos = {}
    for lado in ("left", "right"):
        m = re.search(rf"ear channel entrance {lado}:\s*([-\d.eE+]+)/", texto)
        if m:
            datos[f"canal_estimado_{lado}_y_mm"] = float(m.group(1))
    for clave, patron in (("caras_antes", r"Faces before remeshing:\s*(\d+)"),
                          ("caras_despues", r"Faces after remeshing:\s*(\d+)")):
        m = re.search(patron, texto)
        if m:
            datos[clave] = int(m.group(1))
    return datos


def preparar_entrada(carpeta: Path) -> dict:
    """malla_final_mm.ply -> 3Dmesh_orig.stl, comprobando que sirve para el gradado."""
    ruta_informe = carpeta / "informe_limpieza.json"
    informe = json.loads(ruta_informe.read_text(encoding="utf-8")) if ruta_informe.exists() else {}
    if not (carpeta / MALLA_MM).exists():
        raise ValueError(f"no hay {MALLA_MM} en {carpeta}: la limpieza tiene que haberse hecho "
                         "con alguna medida de la persona (el gradado necesita la malla en mm)")
    if not informe.get("control_calidad", {}).get("aprobado"):
        raise ValueError("la limpieza de esta malla no está aprobada")
    malla = trimesh.load(carpeta / MALLA_MM, process=False)
    if not malla.is_watertight:
        raise ValueError(f"{MALLA_MM} no es cerrada")
    malla.export(carpeta / ENTRADA, file_type="stl")
    return {"caras": len(malla.faces), "caja_mm": np.round(malla.bounds, 1).tolist(),
            "aid_mm": informe.get("escala", {}).get("aid_mm")}


def salio_bien(r: subprocess.CompletedProcess, carpeta: Path, archivo: str) -> bool:
    """El intento cuenta solo si el programa terminó bien Y gradó de verdad. Con A1 (-e 0.5) un
    reintento devolvió código 0 sin remallar ("Faces after remeshing" = "before"): la salida era la
    malla de entrada, sin soldar."""
    v = leer_verbose(r.stdout + r.stderr)
    gradó = "caras_antes" not in v or v.get("caras_despues", v["caras_antes"]) < v["caras_antes"]
    return r.returncode == 0 and (carpeta / archivo).exists() and gradó


def reordenada(malla: trimesh.Trimesh, semilla: int) -> trimesh.Trimesh:
    """La misma malla con los vértices y las caras en otro orden (y cada cara empezando en otro
    vértice, misma orientación). La geometría no cambia en nada: ni un punto se mueve."""
    rng = np.random.default_rng(semilla)
    pv = rng.permutation(len(malla.vertices))
    nuevo = np.empty_like(pv)
    nuevo[pv] = np.arange(len(pv))
    F = nuevo[np.asarray(malla.faces)][rng.permutation(len(malla.faces))]
    return trimesh.Trimesh(np.asarray(malla.vertices)[pv], np.roll(F, int(rng.integers(3)), axis=1), process=False)


def gradar_lado(carpeta: Path, lado: str, archivo: str, registrar) -> tuple[subprocess.CompletedProcess, int]:
    """Gradúa un lado. El binario (versión de 2022) a veces se cae (0xC0000005) con mallas
    sanas, de forma caótica: depende de detalles internos, no de la geometría. A1 (-e 0.5)
    se caía cortada a -115 mm y no a -110, ni sin cortar. Si se cae (o termina sin remallar),
    se reintenta con la MISMA malla escrita en otro orden (reordenada): con A1 funcionó en
    4 de los órdenes 1 a 5 (el 2 también se cae; repetido el 2026-10-07). Antes se movía la malla
    0.0001 mm, pero con A1 eso dejaba al programa sin remallar en 15 de 15 intentos. El
    resultado depende un poco del orden (52 590 a 52 878 caras en esos 4), así que el reintento
    queda anotado en el informe.
    Devuelve el último resultado y cuántos reintentos hicieron falta."""
    def correr(entrada: str) -> subprocess.CompletedProcess:
        # nombres relativos a la carpeta: el programa no abre rutas con tildes (p. ej. "Begoña")
        return ejecutar(["-x", str(config.GRADING_X_MM), "-e", str(config.GRADING_E_MM), "-y", str(config.GRADING_Y_MM),
                         "-s", lado, "-v", "-i", entrada, "-o", archivo], carpeta, TIEMPO_MAX_S)

    r = correr(ENTRADA)
    if salio_bien(r, carpeta, archivo):
        return r, 0
    malla = trimesh.load(carpeta / MALLA_MM, process=False)
    temporal = f"3Dmesh_reintento_{lado}.stl"
    try:
        for intento in range(1, REINTENTOS_MAX + 1):
            registrar(f"  el programa se cayó o no gradó (código {r.returncode}); reintento {intento} de {REINTENTOS_MAX}")
            reordenada(malla, intento).export(carpeta / temporal, file_type="stl")
            (carpeta / archivo).unlink(missing_ok=True)
            r = correr(temporal)
            if salio_bien(r, carpeta, archivo):
                return r, intento
    finally:
        (carpeta / temporal).unlink(missing_ok=True)
    return r, REINTENTOS_MAX


def gradar(carpeta: Path, registrar=print) -> dict:
    """Gradúa los dos lados. Devuelve (y guarda) el informe; "aprobado" dice si salió bien."""
    carpeta = Path(carpeta)
    informe = {"binario": str(config.GRADING_EXE),
               "parametros": {"x_mm": config.GRADING_X_MM, "e_mm": config.GRADING_E_MM, "y_mm": config.GRADING_Y_MM},
               "lados": {}, "avisos": [], "fallas": []}
    ok, mensaje = comprobar_binario()
    registrar(mensaje)
    if not ok:
        informe["fallas"].append(mensaje)
        return guardar_informe(carpeta, informe)
    try:
        informe["entrada"] = preparar_entrada(carpeta)
    except ValueError as ex:
        informe["fallas"].append(str(ex))
        return guardar_informe(carpeta, informe)
    registrar(f"{ENTRADA}: {informe['entrada']['caras']:,} caras")
    aid_mm = informe["entrada"]["aid_mm"]

    for lado, archivo in SALIDAS.items():
        (carpeta / archivo).unlink(missing_ok=True)
        registrar(f"Gradando lado {lado}...")
        t = time.time()
        try:
            r, reintentos = gradar_lado(carpeta, lado, archivo, registrar)
        except subprocess.TimeoutExpired:
            informe["fallas"].append(f"{lado}: no terminó en {TIEMPO_MAX_S} s")
            continue
        res = {"archivo": archivo, "segundos": round(time.time() - t, 1), "codigo": r.returncode,
               "reintentos": reintentos}
        res |= leer_verbose(r.stdout + r.stderr)
        if r.returncode != 0 or not (carpeta / archivo).exists():
            informe["fallas"].append(f"{lado}: el programa falló (código {r.returncode}) "
                                     f"también tras {reintentos} reintentos")
            informe["lados"][lado] = res | {"salida_programa": (r.stdout + r.stderr)[-2000:]}
            continue
        if reintentos:
            informe["avisos"].append(f"{lado}: el programa se cayó y salió al reintento {reintentos} "
                                     "(la misma malla escrita en otro orden)")
        g = trimesh.load(carpeta / archivo, process=False)
        res |= {"caras": len(g.faces), "cerrada": bool(g.is_watertight),
                "piezas": len(g.split(only_watertight=False))}
        if not res["cerrada"] or res["piezas"] != 1:
            informe["fallas"].append(f"{lado}: la malla graduada no es una sola pieza cerrada")
        # el programa estima dónde está el canal del lado fino; debe quedar algo por dentro del real
        est = res.get(f"canal_estimado_{lado}_y_mm")
        if aid_mm and est is not None and abs(est) > aid_mm / 2:
            signo = 1 if lado == "left" else -1
            informe["avisos"].append(
                f"{lado}: canal estimado por el programa en y = {est:.1f} mm, por fuera del marcado "
                f"({signo * aid_mm / 2:.1f} mm); revisar los elementos cerca del canal")
        informe["lados"][lado] = res
        registrar(f"  {archivo}: {res['caras']:,} caras en {res['segundos']} s")
    return guardar_informe(carpeta, informe)


def guardar_informe(carpeta: Path, informe: dict) -> dict:
    informe["aprobado"] = not informe["fallas"] and len(informe["lados"]) == len(SALIDAS)
    (carpeta / "informe_gradado.json").write_text(json.dumps(informe, indent=2, ensure_ascii=False),
                                                  encoding="utf-8")
    return informe
