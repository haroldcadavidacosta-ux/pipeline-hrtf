"""Barrido de -e, fase 2: guion conductor de las simulaciones. Solo produce datos, manifiesto
y registros; el análisis (fase 3) es otro guion que lee lo que deja este.

  fase2.py sellar                        registra los SHA-256 de las mallas de la fase 1 (una vez)
  fase2.py seco  --numcalc <carpeta>     prueba en seco: 900 y 12000 Hz en las cuatro condiciones
  fase2.py real  --numcalc <carpeta> --tanda 1|2

Tanda 1: -e 1 y luego -e 0,5. Tanda 2: -e 3 y luego -e 2 (de la más barata a la más cara).
<carpeta> es NumCalc_WindowsExe (NumCalc.exe de 2022 y sus DLL), la misma en todas las tandas.

Cada condición corre en una copia de su proyecto de diagnóstico (fase2/e_<valor>/), con
manage_numcalc de Mesh2HRTF en un proceso aparte (para poder cortarlo) y este guion vigilando:

  progreso.json   estado autoritativo (qué frecuencia de qué condición está completa). Al
                  reanudar, lo que no figura ahí como completo se borra y se vuelve a simular:
                  el estado nunca se infiere solo de los archivos que haya en las carpetas.
  progreso.csv    una línea por frecuencia, según terminan (el archivo para leer en la mañana)
  muestras_ram.csv   RAM sumada de TODOS los NumCalc vivos, cada 10 s
  manifiesto.json    hashes, versiones, vector de frecuencias, verificaciones y estimado/real
  conductor.log      lo que se imprime en pantalla
  sofa/           HRTF_<rejilla>_e<valor>.sofa marcados DIAGNÓSTICO; las frecuencias que no
                  convergieron en alguna condición completa van en NaN en todas (GLOBAL_Comment)

La convergencia se lee siempre de NC*.out (malla/convergencia.py), nunca del código de salida.
Política ante fallo: una condición que falla se registra y se sigue con la siguiente, salvo un
fallo en los primeros 15 min de la primera condición (error de configuración): ahí se aborta.
"""
import argparse
import contextlib
import csv
import ctypes
import hashlib
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import psutil

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from malla.convergencia import leer_salida   # noqa: E402
from malla.gradado import sin_ventanas_de_error          # noqa: E402
import config                                            # noqa: E402

BARRIDO = RAIZ / "datos" / "experimentos" / "barrido_e"
REGISTRO_SHA = BARRIDO / "fase1" / "sha256.json"
# Fase 4 (participante A): sus capturas A1 y A3 a cada -e. El nombre de cada condición (y de su
# carpeta e_<condición>) sale de config.condicion_barrido
FASE4 = {c: {e: config.condicion_barrido(c, e) for e in ("2", "0.5", "1")} for c in ("A1", "A3")}
CAPTURA_FASE4 = {cond: c for c, por_e in FASE4.items() for cond in por_e.values()}
TANDAS = {"1": ["1", "0.5"], "2": ["3", "2"], "y5": ["1_y5"],
          "j2": [FASE4["A1"]["2"], FASE4["A3"]["2"]], "j05": [FASE4["A1"]["0.5"], FASE4["A3"]["0.5"]],  # fase 4: repetibilidad (A)
          "j1": [FASE4["A1"]["1"], FASE4["A3"]["1"]]}                                                    # fase 4: par y réplica a -e 1
# Condiciones sueltas: su propia carpeta de salida, para que sus NaN no toquen los SOFA de las cuatro
SALIDA_TANDA = {"y5": "fase2_y5", "j2": "fase4_e2", "j05": "fase4_e0.5", "j1": "fase4_e1"}
# Condiciones fuera del sellado de la fase 1: su SHA-256 quedó en preparacion.json al prepararlas
PREPARACION = {"1_y5": BARRIDO / "e_1_y5" / "preparacion.json"} | {
    c: BARRIDO / f"e_{c}" / "preparacion.json" for c in CAPTURA_FASE4}
ORDEN_SECO = ["1", "0.5", "3", "2"]
FRECUENCIAS_SECO = [900.0, 12000.0]
# Tope de frecuencia por condición (fase 4, registrado antes de simular en
# fase4_sujeto_A_2026-10-05.md): por encima, NumCalc pide más RAM de la que tiene el equipo
# (A1 -e 0,5: 11-15 GB desde 19,2 kHz; 11,8 GB disponibles). La regla usa 4-14 kHz.
TOPE_HZ = {FASE4["A1"]["0.5"]: 18900.0, FASE4["A3"]["0.5"]: 18900.0}

# Presupuesto estimado (h) con el piloto: ajuste potencial del tiempo por frecuencia y, para
# manage_numcalc, una emulación de su planificador con 11,7 GB libres y 12 núcleos.
ESTIMADO_H = {"3": {"en_serie": 3.3, "manage_numcalc": 0.6}, "2": {"en_serie": 3.5, "manage_numcalc": 0.7},
              "1": {"en_serie": 7.6, "manage_numcalc": 4.3}, "0.5": {"en_serie": 9.0, "manage_numcalc": 7.2},
              # -e 1 -y 5: interpolado por caras entre -e 1 (3,32 h) y -e 0,5 (6,05 h) reales de la fase 2
              "1_y5": {"en_serie": None, "manage_numcalc": 4.3}}
# fase 4 (A): las mismas de B para cada -e (las mallas tienen un tamaño parecido)
ESTIMADO_H |= {cond: ESTIMADO_H[e] for por_e in FASE4.values() for e, cond in por_e.items()}

MARGEN_RAM = 1.0             # factor de seguridad sobre la estimación de NumCalc. manage_numcalc
                             # usa 1.05, pero con todo cerrado este equipo deja 11,0-11,3 GB libres y
                             # 24 kHz con -e 0,5 pide 10,97 x 1.05 = 11,52 (pico real medido: 10,39 GB).
                             # Bajado a 1.0 el 2026-09-29 por decisión del autor; va al manifiesto.
ESPERA_MANAGE_S = 15         # wait_time de manage_numcalc (su valor por defecto); la RAM que una
                             # instancia aún no ha tomado se reserva aparte (ver manage)
MUESTREO_S = 2
MUESTRA_CSV_S = 10
VENTANA_ABORTO_S = 15 * 60
SIN_INSTANCIAS_MAX_S = 30 * 60
ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
GB = 2**30

CAMPOS_CSV = ["condicion", "indice", "frecuencia_hz", "inicio", "fin", "minutos", "iteraciones",
              "factor_reduccion_residuo", "convergio", "alcanzo_tope", "ilu_fallido",
              "ram_pico_proceso_gb", "ram_pico_suma_numcalc_gb", "estado"]
CAMPOS_CONVERGENCIA = ["iteraciones", "factor_reduccion_residuo", "convergio", "alcanzo_tope", "ilu_fallido"]


# ---------------------------------------------------------------- utilidades

def ahora() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def iso(t: float) -> str:
    return datetime.fromtimestamp(t).astimezone().isoformat(timespec="seconds")


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def guardar_json(ruta: Path, datos) -> None:
    tmp = ruta.with_suffix(".tmp")
    tmp.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, ruta)      # atómico: una interrupción nunca deja el archivo a medias


class Registro:
    def __init__(self, carpeta: Path):
        self.ruta = carpeta / "conductor.log"

    def __call__(self, mensaje: str) -> None:
        linea = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {mensaje}"
        print(linea, flush=True)
        with open(self.ruta, "a", encoding="utf-8") as f:
            f.write(linea + "\n")


def origen(e: str) -> Path:
    return BARRIDO / f"e_{e}" / f"DIAGNOSTICO_proyecto_L_e{e}"


def malla_graduada(e: str) -> Path:
    return BARRIDO / f"e_{e}" / f"3Dmesh_graded_left_e{e}.ply"


def comando_gradado(e: str) -> str:
    """Parámetros del gradado de la condición (-x -y -e), leídos de su comando_grading.txt."""
    texto = (BARRIDO / f"e_{e}" / "comando_grading.txt").read_text(encoding="utf-8")
    return " ".join(re.findall(r"-[xye] [\d.]+", texto))


def fuente(proyecto: Path) -> Path:
    return proyecto / "NumCalc" / "source_1"


def vector_nc(nc_inp: Path) -> list[float]:
    """Frecuencias de la curva de carga de NC.inp (sin la fila de 0 Hz), comprobando que su
    número coincide con el de Controlparameter II."""
    lineas = nc_inp.read_text(encoding="utf-8").splitlines()
    i = next(k for k, l in enumerate(lineas) if "Controlparameter II" in l)
    n = int(lineas[i + 1].split()[1])
    j = next(k for k, l in enumerate(lineas) if "Load Frequency Curve" in l)
    filas = int(lineas[j + 1].split()[1])
    f = [float(lineas[j + 2 + q].split()[1]) for q in range(1, filas)]
    if len(f) != n:
        raise ValueError(f"{nc_inp}: Controlparameter II dice {n} frecuencias y la curva trae {len(f)}")
    return f


def lineas_fisicas(nc_inp: Path) -> dict:
    """Líneas de NC.inp que deben ser iguales entre condiciones (todo menos malla y fuente)."""
    lineas = nc_inp.read_text(encoding="utf-8").splitlines()
    return {t: lineas[next(k for k, l in enumerate(lineas) if t in l) + 1].strip()
            for t in ("Controlparameter I", "Controlparameter II", "Main Parameters II",
                      "Main Parameters III", "Main Parameters IV")}


def memoria(proyecto: Path) -> np.ndarray:
    """Memory.txt de NumCalc -estimate_ram: paso, frecuencia, GB (sin cabecera)."""
    return np.loadtxt(fuente(proyecto) / "Memory.txt", ndmin=2)


def cabecera_ply(ruta: Path) -> dict:
    with open(ruta, "rb") as f:
        texto = b"".join(iter(f.readline, b"end_header\n")).decode("ascii", "replace")
    return {k: int(n) for k, n in re.findall(r"element (vertex|face) (\d+)", texto)}


def numcalc_vivos() -> list[psutil.Process]:
    vivos = []
    for p in psutil.process_iter(["name"]):
        if (p.info["name"] or "").lower() == "numcalc.exe":
            vivos.append(p)
    return vivos


def matar(proc: psutil.Process | None) -> None:
    """Corta el proceso de manage_numcalc, sus hijos y cualquier NumCalc que quede vivo."""
    objetivos = []
    if proc is not None:
        with contextlib.suppress(psutil.Error):
            objetivos = proc.children(recursive=True) + [proc]
    objetivos += numcalc_vivos()
    for p in objetivos:
        with contextlib.suppress(psutil.Error):
            p.kill()
    psutil.wait_procs(objetivos, timeout=30)


# ---------------------------------------------------------------- sellado de la fase 1

def sellar() -> None:
    """La fase 1 no registró SHA-256. Se sellan ahora, solo si hay evidencia de que las mallas
    no cambiaron desde que la fase 1 las midió: son anteriores a geometria.json y tienen los
    vértices y caras que registró."""
    if REGISTRO_SHA.exists():
        sys.exit(f"Ya existe {REGISTRO_SHA}; no se sobrescribe.")
    geometria = BARRIDO / "fase1" / "geometria.json"
    g = json.loads(geometria.read_text(encoding="utf-8"))
    t_fase1 = geometria.stat().st_mtime
    registro = {"sellado": ahora(),
                "nota": ("La fase 1 no registró SHA-256. Se sellaron después, comprobando que cada archivo es "
                         "anterior a fase1/geometria.json y que cada malla graduada tiene los vértices y caras "
                         "que registró la fase 1."),
                "geometria_json_modificado": iso(t_fase1), "archivos": {}}
    entrada = BARRIDO / "3Dmesh_orig.stl"
    rutas = {"3Dmesh_orig.stl": entrada} | {f"e_{e}": malla_graduada(e) for e in ORDEN_SECO}
    for clave, ruta in rutas.items():
        t = ruta.stat().st_mtime
        if t > t_fase1:
            sys.exit(f"{ruta} se modificó ({iso(t)}) después de la fase 1 ({iso(t_fase1)}): no se sella.")
        r = {"ruta": str(ruta.relative_to(RAIZ)), "sha256": sha256(ruta), "modificado": iso(t)}
        if clave.startswith("e_"):
            cab, esperado = cabecera_ply(ruta), g["e"][clave[2:]]
            if (cab["vertex"], cab["face"]) != (esperado["vertices"], esperado["caras"]):
                sys.exit(f"{ruta}: {cab} no coincide con la fase 1 ({esperado['vertices']} v, {esperado['caras']} c)")
            r |= {"vertices": cab["vertex"], "caras": cab["face"]}
        registro["archivos"][clave] = r
    guardar_json(REGISTRO_SHA, registro)
    print(json.dumps(registro, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------- verificaciones previas

def defender_excluye(carpeta: Path) -> tuple[bool, str]:
    """Sin permisos de administrador Get-MpPreference no enseña las exclusiones, pero el registro
    de eventos de Defender sí: el evento 5007 trae el valor anterior (2.ª línea) y el nuevo
    (3.ª). Vale el último evento que menciona la carpeta."""
    ps = ("Get-WinEvent -LogName 'Microsoft-Windows-Windows Defender/Operational' "
          "-FilterXPath '*[System[EventID=5007]]' -ErrorAction Stop | "
          "ForEach-Object { $_.TimeCreated.ToString('o') + \"`t\" + ($_.Message -replace \"`r?`n\", '|') }")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120)
    except (OSError, subprocess.TimeoutExpired) as ex:
        return False, f"no se pudo leer el registro de Defender ({ex})"
    clave = ("Exclusions\\Paths\\" + str(carpeta)).lower()
    for linea in r.stdout.splitlines():            # del más reciente al más antiguo
        cuando, _, mensaje = linea.partition("\t")
        partes = [p.strip().lower() for p in mensaje.split("|") if p.strip()]
        for k, p in enumerate(partes):
            if p.endswith(clave + " = 0x0") or clave + " = " in p:
                if k == len(partes) - 1:
                    return True, f"exclusión añadida el {cuando[:19]} (evento 5007 de Defender)"
                return False, f"la exclusión se quitó el {cuando[:19]}"
    return False, "Defender no registra la exclusión de la carpeta de NumCalc (ejecutar excluir_antivirus.bat como administrador)"


def valor_powercfg(guid: str) -> int | None:
    r = subprocess.run(["powercfg", "/query", "SCHEME_CURRENT", "SUB_SLEEP", guid],
                       capture_output=True, text=True, errors="replace")
    valores = re.findall(r"0x([0-9a-fA-F]{8})", r.stdout)
    return int(valores[-2], 16) if len(valores) >= 2 else None    # [..., CA, CC]


def reinicio_pendiente() -> bool:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired"):
            return True
    except OSError:
        return False


def windows_update(horas: float) -> tuple[bool, str]:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\WindowsUpdate\UX\Settings") as k:
            expira = winreg.QueryValueEx(k, "PauseUpdatesExpiryTime")[0]
        hasta = datetime.fromisoformat(expira.replace("Z", "+00:00"))
    except (OSError, ValueError):
        return False, "las actualizaciones no están pausadas (Configuración > Windows Update > Pausar 7 días)"
    if hasta < datetime.now(timezone.utc) + timedelta(hours=horas):
        return False, f"la pausa de actualizaciones vence el {hasta.astimezone():%Y-%m-%d %H:%M}, antes de terminar"
    return True, f"actualizaciones pausadas hasta {hasta.astimezone():%Y-%m-%d %H:%M}"


def verificar(condiciones: list[str], salida: Path, numcalc: Path, seco: bool, horas: float) -> list[dict]:
    """Todas se evalúan (para verlas todas de una vez); si alguna falla no se arranca."""
    v = []

    def anotar(nombre, ok, detalle, bloquea=True):
        v.append({"verificacion": nombre, "ok": bool(ok), "bloquea": bloquea, "detalle": detalle})

    # 1. vectores de frecuencia idénticos: se comparan, no se suponen (todas las condiciones)
    vectores = {e: vector_nc(fuente(origen(e)) / "NC.inp") for e in ORDEN_SECO}
    param = {e: json.loads((origen(e) / "parameters.json").read_text(encoding="utf-8"))["frequencies"]
             for e in ORDEN_SECO}
    ref = vectores["1"]
    iguales = all(vectores[e] == ref and param[e] == ref for e in ORDEN_SECO)
    anotar("vector de frecuencias idéntico en los cuatro NC.inp (y en parameters.json)", iguales,
           f"{len(ref)} frecuencias, {ref[0]:.0f}–{ref[-1]:.0f} Hz" if iguales else
           {e: [len(vectores[e]), vectores[e][:2], vectores[e][-2:]] for e in ORDEN_SECO})
    copias = {e: vector_nc(fuente(salida / f"e_{e}") / "NC.inp") for e in condiciones}
    primera = next(iter(copias.values()))
    tope = min(TOPE_HZ.get(e, float("inf")) for e in condiciones)
    esperado = [f for f in ref if f <= tope]
    anotar("vector de frecuencias idéntico en las copias que se van a simular",
           all(c == primera for c in copias.values()) and (seco or primera == esperado),
           f"{len(primera)} frecuencias: {primera[:3]}…{primera[-2:]}" + ("" if seco else
           ", iguales a las de la fase 2" + (f" hasta {tope:.0f} Hz (TOPE_HZ)" if tope < float("inf") else "")))
    fisica = {e: lineas_fisicas(fuente(origen(e)) / "NC.inp") for e in ORDEN_SECO}
    anotar("parámetros de NC.inp idénticos (control, solver, c, rho)",
           all(fisica[e] == fisica["1"] for e in ORDEN_SECO), fisica["1"])

    # 2. SHA-256 de las mallas contra el registro de la fase 1
    if not REGISTRO_SHA.exists():
        anotar("SHA-256 de las mallas iguales a la fase 1", False, f"no existe {REGISTRO_SHA} (correr 'fase2.py sellar')")
    else:
        reg = json.loads(REGISTRO_SHA.read_text(encoding="utf-8"))["archivos"]
        def sha_registrado(e):
            if e in PREPARACION:
                return json.loads(PREPARACION[e].read_text(encoding="utf-8"))["sha256_malla"]
            return reg[f"e_{e}"]["sha256"]
        malas = [e for e in condiciones if sha256(malla_graduada(e)) != sha_registrado(e)]
        if sha256(BARRIDO / "3Dmesh_orig.stl") != reg["3Dmesh_orig.stl"]["sha256"]:
            malas.append("3Dmesh_orig.stl")
        anotar("SHA-256 de las mallas iguales a la fase 1", not malas,
               "coinciden" if not malas else f"distintos: {malas}")
        # la copia que se simula viene de esa malla: mismos vértices y caras
        malos = []
        for e in condiciones:
            cab = cabecera_ply(malla_graduada(e))
            ref_dir = salida / f"e_{e}" / "ObjectMeshes" / "Reference"
            n = [int(open(ref_dir / a).readline()) for a in ("Nodes.txt", "Elements.txt")]
            if n != [cab["vertex"], cab["face"]]:
                malos.append(f"e_{e}: proyecto {n}, malla {[cab['vertex'], cab['face']]}")
        anotar("proyectos con los vértices y caras de su malla graduada", not malos, malos or "coinciden")

    # 3. disco: be.out por frecuencia medido en el piloto, con margen x3
    necesario = 0
    for e in condiciones:
        be = BARRIDO / "piloto" / f"e_{e}" / "NumCalc" / "source_1" / "be.out" / "be.38"
        por_paso = sum(a.stat().st_size for a in be.rglob("*") if a.is_file()) if be.exists() else 10 * 2**20
        necesario += por_paso * len(copias[e])
    libre_disco = shutil.disk_usage(salida).free
    anotar("espacio en disco", libre_disco > 3 * necesario + GB,
           f"libres {libre_disco / GB:.1f} GB; se esperan {necesario / GB:.2f} GB de resultados")

    # 4. RAM libre, registrada; sin la del paso más caro, manage_numcalc esperaría para siempre
    libre = psutil.virtual_memory().available / GB
    mayor = max(float(memoria(salida / f"e_{e}")[:, 2].max()) for e in condiciones)
    anotar("RAM libre al arrancar", libre >= mayor * MARGEN_RAM,
           f"libres {libre:.2f} GB de {psutil.virtual_memory().total / GB:.1f}; el paso más caro pide "
           f"{mayor:.2f} x {MARGEN_RAM} = {mayor * MARGEN_RAM:.2f} GB")

    # 5. antivirus
    ok, detalle = defender_excluye(numcalc)
    anotar("carpeta de NumCalc excluida del antivirus", ok, detalle)

    # 6. nada de NumCalc corriendo (la RAM libre y la suma de RAM pico serían falsas)
    otros = numcalc_vivos()
    anotar("ningún NumCalc corriendo", not otros, f"{len(otros)} procesos NumCalc.exe" if otros else "ninguno")

    # 7. que la máquina no se duerma (además el conductor lo pide con SetThreadExecutionState)
    suspender, hibernar = valor_powercfg("29f6c1db-86da-48c5-9fdb-f2b67b1f44da"), valor_powercfg("9d7815a6-7ee4-497e-8888-515a05f02364")
    anotar("suspensión e hibernación desactivadas (corriente alterna)", suspender == 0 and hibernar == 0,
           f"suspender tras {suspender} s, hibernar tras {hibernar} s (0 = nunca)")
    bateria = psutil.sensors_battery()
    anotar("conectado a la corriente", bateria is None or bateria.power_plugged,
           "equipo sin batería" if bateria is None else f"batería {bateria.percent} %, enchufado: {bateria.power_plugged}")

    # 8. que Windows Update no reinicie durante la ventana. Un reinicio ya pendiente bloquea; la
    # pausa de actualizaciones solo se avisa (decisión del 2026-09-29: el límite de pausas estaba
    # agotado y este equipo nunca se ha reiniciado solo)
    pendiente = reinicio_pendiente()
    anotar("sin reinicio pendiente de Windows Update", not pendiente,
           "hay un reinicio pendiente: reiniciar ANTES de lanzar" if pendiente else "ninguno")
    ok, detalle = windows_update(horas)
    anotar("actualizaciones de Windows pausadas", ok, detalle, bloquea=False)
    return v


# ---------------------------------------------------------------- preparación

def recortar(proyecto: Path, frecuencias: list[float]) -> None:
    """Prueba en seco: deja en NC.inp y parameters.json solo las frecuencias dadas."""
    nc = fuente(proyecto) / "NC.inp"
    lineas = nc.read_text(encoding="utf-8").splitlines()
    todas = vector_nc(nc)
    i = next(k for k, l in enumerate(lineas) if "Controlparameter II" in l)
    t = lineas[i + 1].split()
    t[1] = str(len(frecuencias))
    lineas[i + 1] = " ".join(t)
    j = next(k for k, l in enumerate(lineas) if "Load Frequency Curve" in l)
    filas = int(lineas[j + 1].split()[1])
    curva = lineas[j + 2: j + 2 + filas]
    nuevas = [curva[0]]
    for q, f in enumerate(frecuencias, start=1):
        _, valor, resto = curva[todas.index(f) + 1].split(maxsplit=2)
        nuevas.append(f"{q * 1e-6:.6f} {valor} {resto}")
    lineas[j + 1: j + 2 + filas] = [f"0 {len(nuevas)}"] + nuevas
    nc.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    ruta = proyecto / "parameters.json"
    p = json.loads(ruta.read_text(encoding="utf-8"))
    p["frequencies"], p["numFrequencies"] = frecuencias, len(frecuencias)
    ruta.write_text(json.dumps(p, indent=4), encoding="utf-8")
    if vector_nc(nc) != frecuencias:
        raise RuntimeError(f"el recorte de {nc} no dio {frecuencias}")


def preparar(e: str, salida: Path, numcalc: Path, seco: bool, log: Registro) -> None:
    proyecto = salida / f"e_{e}"
    if proyecto.exists():
        return                                          # se está reanudando
    shutil.copytree(origen(e), proyecto, ignore=shutil.ignore_patterns(
        "*.out", "be.out", "*.blend", "Memory.txt", "Output2HRTF", "NC*_log.txt", "manage_numcalc_*"))
    if seco:
        recortar(proyecto, FRECUENCIAS_SECO)
    elif e in TOPE_HZ:
        recortar(proyecto, [f for f in vector_nc(fuente(proyecto) / "NC.inp") if f <= TOPE_HZ[e]])
        log(f"e_{e}: vector recortado hasta {TOPE_HZ[e]:.0f} Hz (TOPE_HZ)")
    log(f"e_{e}: proyecto copiado; estimando RAM (NumCalc -estimate_ram)...")
    r = subprocess.run([str(numcalc / "NumCalc.exe"), "-estimate_ram"], cwd=fuente(proyecto),
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1800)
    if r.returncode != 0 or not (fuente(proyecto) / "Memory.txt").exists():
        shutil.rmtree(proyecto)
        raise RuntimeError(f"e_{e}: NumCalc -estimate_ram falló (código {r.returncode})")


# ---------------------------------------------------------------- ejecución de una condición

class Progreso:
    def __init__(self, salida: Path, modo: str):
        self.ruta, self.csv = salida / "progreso.json", salida / "progreso.csv"
        self.datos = json.loads(self.ruta.read_text(encoding="utf-8")) if self.ruta.exists() else \
            {"modo": modo, "creado": ahora(), "condiciones": {}}
        if self.csv.exists() and self.csv.read_text(encoding="utf-8-sig").splitlines()[:1] != [",".join(CAMPOS_CSV)]:
            self.migrar(salida)
        if not self.csv.exists():
            self.escribir_cabecera()

    def escribir_cabecera(self) -> None:
        with open(self.csv, "w", newline="", encoding="utf-8-sig") as f:    # BOM: Excel lee las tildes
            csv.writer(f).writerow(CAMPOS_CSV)

    def migrar(self, salida: Path) -> None:
        """Progreso escrito con el criterio anterior (campo error_relativo, tolerancia 1e-6 leída por
        error de NC.inp): vuelve a leer la convergencia de cada paso de su NC*.out con el criterio
        actual (malla/convergencia.py) y reescribe el CSV. El CSV viejo queda como progreso_v1.csv.
        Si el NC*.out de un paso ya no está, solo se renombra el campo y se conserva su estado."""
        viejo = self.csv.with_name("progreso_v1.csv")
        if not viejo.exists():
            self.csv.rename(viejo)
        self.cambios_migracion = []
        for e, cond in self.datos["condiciones"].items():
            for k, r in cond["pasos"].items():
                if "error_relativo" in r:
                    r["factor_reduccion_residuo"] = r.pop("error_relativo")
                if not (fuente(salida / f"e_{e}") / f"NC{k}-{k}.out").exists():
                    continue
                nuevo = resultado_paso(salida / f"e_{e}", int(k), r["frecuencia_hz"])
                if nuevo["estado"] != r["estado"]:
                    self.cambios_migracion.append(f"e_{e} paso {k}: {r['estado']} -> {nuevo['estado']}")
                r |= {c: nuevo[c] for c in CAMPOS_CONVERGENCIA + ["estado"]}
        self.guardar()
        self.escribir_cabecera()
        with open(self.csv, "a", newline="", encoding="utf-8") as f:
            for e, cond in self.datos["condiciones"].items():
                for k, r in sorted(cond["pasos"].items(), key=lambda x: int(x[0])):
                    csv.writer(f).writerow([e] + [r.get(c) for c in CAMPOS_CSV[1:]])

    def condicion(self, e: str) -> dict:
        return self.datos["condiciones"].setdefault(e, {"estado": "pendiente", "pasos": {}, "corridas": []})

    def completos(self, e: str) -> set[int]:
        return {int(k) for k, r in self.condicion(e)["pasos"].items() if r["estado"] in ("convergió", "no convergió")}

    def paso(self, e: str, r: dict) -> None:
        self.condicion(e)["pasos"][str(r["indice"])] = r
        self.guardar()
        with open(self.csv, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([e] + [r.get(c) for c in CAMPOS_CSV[1:]])

    def guardar(self) -> None:
        guardar_json(self.ruta, self.datos)


def resultado_paso(proyecto: Path, k: int, f: float) -> dict:
    src = fuente(proyecto)
    salida_nc = src / f"NC{k}-{k}.out"
    c = leer_salida(salida_nc).get(k, {}) if salida_nc.exists() else {}
    hay_datos = (src / "be.out" / f"be.{k}" / "pEvalGrid").exists()
    if c.get("convergio") is None or not hay_datos:
        estado = "sin resultado"
    else:
        estado = "convergió" if c["convergio"] else "no convergió"
    return {"indice": k, "frecuencia_hz": f, "estado": estado} | {x: c.get(x) for x in CAMPOS_CONVERGENCIA}


def tiempos_nc(ruta: Path) -> tuple[str | None, str | None]:
    """Inicio y fin que escribe NumCalc en NC*.out (solo para pasos que el vigilante no vio)."""
    texto = ruta.read_text(encoding="utf-8", errors="replace") if ruta.exists() else ""
    res = []
    for etiqueta in ("Start time", "End time"):
        m = re.search(etiqueta + r": (\d+)/(\d+)/(\d+) (\d+):(\d+):(\d+)", texto)
        res.append(iso(datetime(int(m[3]), int(m[2]), int(m[1]), int(m[4]), int(m[5]), int(m[6])).timestamp())
                   if m else None)
    return res[0], res[1]


def correr_condicion(e: str, salida: Path, numcalc: Path, prog: Progreso, log: Registro,
                     primera: bool) -> str:
    """Devuelve 'ok', 'falló' o 'abortar'."""
    proyecto = salida / f"e_{e}"
    cond = prog.condicion(e)
    frecuencias = vector_nc(fuente(proyecto) / "NC.inp")
    completos = prog.completos(e)
    pendientes = [k for k in range(1, len(frecuencias) + 1) if k not in completos]
    if not pendientes:
        log(f"e_{e}: todas las frecuencias ya estaban completas en progreso.json")
        return "ok"
    # lo que no está completo en progreso.json se vuelve a simular desde cero
    src = fuente(proyecto)
    shutil.rmtree(proyecto / "Output2HRTF", ignore_errors=True)     # SOFA de datos que van a cambiar
    for k in pendientes:
        shutil.rmtree(src / "be.out" / f"be.{k}", ignore_errors=True)
        (src / f"NC{k}-{k}.out").unlink(missing_ok=True)

    libre = psutil.virtual_memory().available / GB
    swap0 = psutil.swap_memory().used / GB
    M = memoria(proyecto)
    corrida = {"inicio": ahora(), "pasos_pendientes": len(pendientes), "ram_libre_al_empezar_gb": round(libre, 2),
               "ram_estimada_max_gb": round(float(M[:, 2].max()), 3)}
    log(f"e_{e}: {len(pendientes)}/{len(frecuencias)} frecuencias por simular; RAM libre {libre:.2f} GB; "
        f"el paso más caro pide {M[:, 2].max():.2f} GB")
    for previa in cond["corridas"]:
        if "fin" not in previa:
            previa["estado"] = "interrumpida (el conductor se cortó; lo no registrado se volvió a simular)"
    cond["estado"] = "en curso"
    cond["corridas"].append(corrida)
    prog.guardar()

    with open(salida / f"e_{e}_manage_numcalc.log", "a", encoding="utf-8") as salida_manage:
        hijo = subprocess.Popen([sys.executable, "-u", str(Path(__file__).resolve()), "_manage", str(proyecto), str(numcalc)],
                                stdout=salida_manage, stderr=subprocess.STDOUT)
        t0 = time.time()
        vivos, pico_suma, pico_proceso, swap_max, ultimo_csv, sin_instancias = {}, 0.0, 0.0, swap0, 0.0, None
        motivo = None
        with open(salida / "muestras_ram.csv", "a", newline="", encoding="utf-8") as fm:
            muestras = csv.writer(fm)
            if fm.tell() == 0:
                muestras.writerow(["hora", "condicion", "instancias", "ram_suma_numcalc_gb", "ram_libre_gb",
                                   "swap_usado_gb", "cpu_pct"])
            while True:
                terminado = hijo.poll() is not None
                actuales = {p.pid: p for p in numcalc_vivos()}
                for pid, p in actuales.items():
                    if pid not in vivos:
                        try:
                            args = p.cmdline()
                            k = int(args[args.index("-istart") + 1])
                            vivos[pid] = {"proc": p, "paso": k, "inicio": p.create_time(), "pico_proceso": 0, "pico_suma": 0}
                        except (psutil.Error, ValueError, IndexError):
                            continue                 # -estimate_ram u otro: no es un paso
                suma = 0
                for pid, v in vivos.items():
                    with contextlib.suppress(psutil.Error):
                        mi = v["proc"].memory_info()
                        suma += mi.rss                                # working set actual
                        v["pico_proceso"] = max(v["pico_proceso"], mi.peak_wset)
                for v in vivos.values():
                    v["pico_suma"] = max(v["pico_suma"], suma)
                pico_suma = max(pico_suma, suma)
                swap_max = max(swap_max, psutil.swap_memory().used / GB)
                if time.time() - ultimo_csv >= MUESTRA_CSV_S:
                    ultimo_csv = time.time()
                    muestras.writerow([ahora(), e, len(vivos), round(suma / GB, 3),
                                       round(psutil.virtual_memory().available / GB, 3), round(swap_max, 3),
                                       psutil.cpu_percent(interval=None)])
                    fm.flush()
                # pasos que terminaron
                for pid in [p for p in vivos if p not in actuales]:
                    v = vivos.pop(pid)
                    r = resultado_paso(proyecto, v["paso"], frecuencias[v["paso"] - 1])
                    fin = time.time()
                    r |= {"inicio": iso(v["inicio"]), "fin": iso(fin), "minutos": round((fin - v["inicio"]) / 60, 2),
                          "ram_pico_proceso_gb": round(v["pico_proceso"] / GB, 3),
                          "ram_pico_suma_numcalc_gb": round(v["pico_suma"] / GB, 3), "observado": True}
                    pico_proceso = max(pico_proceso, v["pico_proceso"])
                    prog.paso(e, r)
                    log(f"e_{e} paso {r['indice']} ({r['frecuencia_hz']:.0f} Hz): {r['estado']}, "
                        f"{r['iteraciones']} it, {r['minutos']:.1f} min, RAM {r['ram_pico_proceso_gb']:.2f} GB "
                        f"(suma NumCalc {r['ram_pico_suma_numcalc_gb']:.2f} GB)")
                    if r["estado"] == "sin resultado" and primera and time.time() - t0 < VENTANA_ABORTO_S:
                        motivo = "abortar"
                if motivo == "abortar":
                    matar(psutil.Process(hijo.pid) if hijo.poll() is None else None)
                    break
                if terminado and not vivos:
                    break
                # manage_numcalc vivo sin lanzar nada durante mucho rato: no hay RAM para el paso siguiente
                if not terminado and not actuales:
                    sin_instancias = sin_instancias or time.time()
                    if time.time() - sin_instancias > SIN_INSTANCIAS_MAX_S and time.time() - t0 > SIN_INSTANCIAS_MAX_S:
                        motivo = "sin instancias"
                        matar(psutil.Process(hijo.pid))
                        break
                else:
                    sin_instancias = None
                time.sleep(MUESTREO_S)
    codigo = hijo.wait()

    # pasos que terminaron entre dos muestreos (o que ninguna muestra alcanzó a ver)
    registrados = {int(k) for k in cond["pasos"]}
    for k in pendientes:
        if k in registrados and (cond["pasos"][str(k)].get("inicio") or "") >= corrida["inicio"]:
            continue
        r = resultado_paso(proyecto, k, frecuencias[k - 1])
        if r["estado"] != "sin resultado" or (src / f"NC{k}-{k}.out").exists():
            ini, fin = tiempos_nc(src / f"NC{k}-{k}.out")
            prog.paso(e, r | {"inicio": ini, "fin": fin, "observado": False,
                              "nota": "no lo vio el vigilante; tiempos de NC*.out, sin RAM medida"})

    fin = time.time()
    pasos = [cond["pasos"].get(str(k)) for k in range(1, len(frecuencias) + 1)]
    sin = [k for k, r in enumerate(pasos, 1) if r is None or r["estado"] == "sin resultado"]
    no = [r["frecuencia_hz"] for r in pasos if r and r["estado"] == "no convergió"]
    corrida |= {"fin": ahora(), "horas_reales": round((fin - t0) / 3600, 3), "codigo_manage_numcalc": codigo,
                "ram_pico_proceso_max_gb": round(pico_proceso / GB, 3), "ram_pico_suma_numcalc_gb": round(pico_suma / GB, 3),
                "swap_usado_al_empezar_gb": round(swap0, 3), "swap_usado_max_gb": round(swap_max, 3),
                "frecuencias_sin_resultado": [frecuencias[k - 1] for k in sin], "frecuencias_no_convergidas": no}
    if motivo == "abortar":
        cond["estado"] = "falló en los primeros minutos (error de configuración): abortado"
    elif motivo == "sin instancias":
        cond["estado"] = f"falló: manage_numcalc estuvo {SIN_INSTANCIAS_MAX_S // 60} min sin lanzar instancias (¿RAM libre insuficiente?)"
    elif sin:
        cond["estado"] = f"incompleta: {len(sin)} frecuencias sin resultado (código de manage_numcalc {codigo})"
    else:
        cond["estado"] = "completa"
    corrida["estado"] = cond["estado"]
    prog.guardar()
    log(f"e_{e}: {cond['estado']}; {corrida['horas_reales']:.2f} h; RAM pico: proceso {corrida['ram_pico_proceso_max_gb']:.2f} GB, "
        f"suma NumCalc {corrida['ram_pico_suma_numcalc_gb']:.2f} GB; swap {swap0:.2f} → {swap_max:.2f} GB; "
        f"no convergieron: {no or 'ninguna'}")
    if motivo == "abortar" or (primera and codigo != 0 and fin - t0 < VENTANA_ABORTO_S):
        return "abortar"
    return "ok" if cond["estado"] == "completa" else "falló"


def manage(proyecto: str, numcalc: str) -> None:
    """Proceso hijo: manage_numcalc de Mesh2HRTF sobre un proyecto, con una corrección.

    manage_numcalc lanza otra instancia si la RAM libre EN ESE MOMENTO alcanza para ella, pero
    NumCalc no toma su memoria al arrancar: en la prueba en seco, la de 900 Hz con -e 0,5 iba
    en 0,3 GB a los 45 s y llegó a 3 GB minutos después. Así se puede sobrecomprometer la RAM
    y paginar a disco. Se reemplaza su lectura de RAM por una que descuenta, de cada NumCalc
    vivo, lo que aún le falta para llegar a su estimación x MARGEN_RAM. El resto de su lógica
    (orden, esperas, pasos completos, registro) queda igual."""
    sin_ventanas_de_error()     # lo heredan los NumCalc: si falta una DLL, terminan con un código
    import mesh2hrtf as m2h
    M = memoria(Path(proyecto))
    estimada = {int(p): g * GB for p, g in zip(M[:, 0], M[:, 2])}

    def ram_con_reservas(total_ram, max_ram_load):
        libre = psutil.virtual_memory().available
        pendiente = 0
        for p in numcalc_vivos():
            with contextlib.suppress(psutil.Error, ValueError, IndexError):
                args = p.cmdline()
                paso = int(args[args.index("-istart") + 1])
                pendiente += max(0.0, estimada.get(paso, 0) * MARGEN_RAM - p.memory_info().rss)
        usada = total_ram - libre / GB
        return max(0.0, max_ram_load - usada - pendiente / GB), usada

    m2h.manage_numcalc.__globals__["_get_current_ram"] = ram_con_reservas
    m2h.manage_numcalc(project_path=proyecto, numcalc_path=numcalc, ram_safety_factor=MARGEN_RAM,
                       wait_time=ESPERA_MANAGE_S, starting_order="alternate", confirm_errors=False)


# ---------------------------------------------------------------- SOFA

def escribir_sofas(salida: Path, prog: Progreso, log: Registro) -> dict:
    """output2hrtf por cada condición completa (una vez) y, desde esos SOFA sin tocar, copias
    DIAGNÓSTICO en sofa/ con NaN en toda frecuencia que no convergió en alguna condición completa."""
    import mesh2hrtf as m2h
    import sofar as sf
    completas = [e for e, c in prog.datos["condiciones"].items() if c["estado"] == "completa"]
    control = salida.name != "fase2"        # tanda de control (p. ej. -e 1 -y 5): fuera de las cuatro del barrido
    for e in completas:
        proyecto = salida / f"e_{e}"
        if sorted((proyecto / "Output2HRTF").glob("HRTF_*.sofa")):
            continue
        log(f"e_{e}: output2hrtf...")
        with open(salida / f"e_{e}_output2hrtf.log", "w", encoding="utf-8") as f, \
                contextlib.redirect_stdout(f), contextlib.redirect_stderr(f):
            m2h.output2hrtf(str(proyecto))
    nan = {}                                            # frecuencia -> condiciones donde divergió
    for e in completas:
        for r in prog.datos["condiciones"][e]["pasos"].values():
            if r["estado"] == "no convergió":
                nan.setdefault(r["frecuencia_hz"], []).append(e)
    carpeta = salida / "sofa"
    carpeta.mkdir(exist_ok=True)
    escritos = {}
    for e in completas:
        for original in sorted((salida / f"e_{e}" / "Output2HRTF").glob("HRTF_*.sofa")):
            sofa = sf.read_sofa(str(original), verify=False)
            f = np.asarray(sofa.N, dtype=float)
            idx = [i for i, x in enumerate(f) if x in nan]
            if idx:
                sofa.Data_Real[..., idx] = np.nan
                sofa.Data_Imag[..., idx] = np.nan
            detalle = "; ".join(f"{x:.0f} Hz (no convergio en -e {', '.join(nan[x])})" for x in sorted(nan)) or "ninguna"
            sofa.GLOBAL_Title = f"DIAGNOSTICO barrido -e {e} (NO es una HRTF valida)"
            sujeto = (f"prueba de repetibilidad (fase 4), sujeto A, captura {CAPTURA_FASE4[e]}, gradado {comando_gradado(e)}, "
                      "oreja izquierda" if e in CAPTURA_FASE4 else
                      f"condicion de control {comando_gradado(e)}, oreja izquierda (B)")
            sofa.GLOBAL_Comment = (
                f"DIAGNOSTICO, no es una HRTF valida. Barrido de -e, {sujeto}, fuera de las cuatro condiciones "
                f"del barrido. Vector de diagnostico "
                f"{f[0]:.0f}-{f[-1]:.0f} Hz ({len(f)} frecuencias), sin HRIR. NumCalc de 2022 (sin -adapt_fmmlength), "
                f"convergencia leida de NC*.out. Frecuencias en NaN (no convergieron en esta condicion): {detalle}. "
                f"El analisis excluye en cada comparacion las frecuencias que no convergieron en cualquiera de las "
                f"dos condiciones comparadas." if control else
                f"DIAGNOSTICO, no es una HRTF valida. Barrido de -e, fase 2, condicion -e {e}, oreja izquierda "
                f"(B), gradado {comando_gradado(e)}. Vector de diagnostico {f[0]:.0f}-{f[-1]:.0f} Hz ({len(f)} "
                f"frecuencias), sin HRIR. NumCalc de 2022 (sin -adapt_fmmlength), convergencia leida de NC*.out. "
                f"Frecuencias en NaN en todas las condiciones: {detalle}. Union calculada sobre las condiciones "
                f"completas al {ahora()}: -e {', '.join(sorted(completas, key=lambda x: float(x.split("_")[0])))}"
                + ("" if len(completas) == 4 else " (PROVISIONAL: faltan condiciones)") + ". "
                + (f"Esas frecuencias quedan EXCLUIDAS del analisis principal, que compara las cuatro condiciones "
                   f"sobre las {len(f) - len(nan)} frecuencias comunes (decision del autor, 2026-09-29); no se "
                   f"interpolan ni se sustituyen." if nan else ""))
            destino = carpeta / f"{original.stem}_e{e}.sofa"
            sf.write_sofa(str(destino), sofa, compression=4)
            escritos[destino.name] = {"frecuencias_nan": sorted(nan), "sha256": sha256(destino)}
    if escritos:
        log(f"SOFA de diagnóstico escritos: {', '.join(escritos)}; frecuencias en NaN: {sorted(nan) or 'ninguna'}")
    return escritos


# ---------------------------------------------------------------- manifiesto

def manifiesto(salida: Path, condiciones: list[str], numcalc: Path, verificaciones: list[dict], modo: str,
               prog: Progreso, sofas: dict, dry_piloto: dict | None) -> None:
    import mesh2hrtf as m2h
    import sofar as sf
    ruta = salida / "manifiesto.json"
    man = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {
        "experimento": "Barrido de -e de hrtf_mesh_grading, fase 2 (simulaciones de diagnóstico, oreja izquierda)",
        "modo": modo, "invocaciones": [], "condiciones": {}}
    blender = (BARRIDO / "e_1" / "exportacion_blender.log").read_text(encoding="utf-8", errors="replace")
    m = re.search(r"Blender [\d.]+( LTS)?", blender)
    man["entorno"] = {
        "equipo": socket.gethostname(), "sistema": platform.platform(), "python": sys.version.split()[0],
        "nucleos_logicos": psutil.cpu_count(), "ram_total_gb": round(psutil.virtual_memory().total / GB, 2),
        "versiones": {"mesh2hrtf_python": m2h.__version__,
                      "mesh2hrtf_exportador": (RAIZ / "mesh2hrtf_1.3.0" / "VERSION").read_text().strip(),
                      "blender": m.group(0) if m else None, "sofar": sf.__version__, "numpy": np.__version__,
                      "psutil": psutil.__version__,
                      "numcalc": {"carpeta": str(numcalc), "compilacion": "2022-08-26 (readme), sin -adapt_fmmlength",
                                  "sha256": {a.name: sha256(a) for a in sorted(numcalc.iterdir())
                                             if a.suffix.lower() in (".exe", ".dll")}}},
        "manage_numcalc": {"ram_safety_factor": MARGEN_RAM, "wait_time_s": ESPERA_MANAGE_S,
                           "starting_order": "alternate", "max_instances": "núcleos lógicos", "max_cpu_load": 90,
                           "correccion": ("la RAM disponible descuenta, de cada NumCalc vivo, lo que le falta para "
                                          "llegar a su estimación x ram_safety_factor (NumCalc toma su memoria "
                                          "durante minutos, no al arrancar)")}}
    frec = vector_nc(fuente(salida / f"e_{condiciones[0]}") / "NC.inp")
    man["vector_frecuencias_hz"] = frec
    man["entrada"] = {"ruta": str((BARRIDO / "3Dmesh_orig.stl").relative_to(RAIZ)),
                      "sha256": sha256(BARRIDO / "3Dmesh_orig.stl")}
    man["invocaciones"].append({"fecha": ahora(), "condiciones": condiciones, "verificaciones": verificaciones})
    for e in condiciones:
        proyecto = salida / f"e_{e}"
        ref = proyecto / "ObjectMeshes" / "Reference"
        nc = (fuente(proyecto) / "NC.inp").read_text(encoding="utf-8")
        elem = re.search(r"ELEM (\d+) TO \d+ VELO", nc)
        M, M0 = memoria(proyecto), memoria(origen(e))
        c = prog.datos["condiciones"].get(e, {})
        estimado = ESTIMADO_H[e] if modo == "real" else dry_piloto.get(e)
        man["condiciones"][e] = {
            "malla_graduada": {"ruta": str(malla_graduada(e).relative_to(RAIZ)), "sha256": sha256(malla_graduada(e)),
                               **{k: v for k, v in cabecera_ply(malla_graduada(e)).items()}},
            "comando_gradado": (BARRIDO / f"e_{e}" / "comando_grading.txt").read_text(encoding="utf-8").strip(),
            "proyecto": str(proyecto.relative_to(RAIZ)),
            "sha256_proyecto": {n: sha256(p) for n, p in (("Nodes.txt", ref / "Nodes.txt"),
                                                         ("Elements.txt", ref / "Elements.txt"),
                                                         ("NC.inp", fuente(proyecto) / "NC.inp"))},
            "elemento_fuente": int(elem.group(1)) if elem else None,
            "ram_estimada_max_gb": round(float(M[:, 2].max()), 3),
            "estimacion_ram_igual_a_la_de_fase1": bool(M.shape == M0.shape and np.allclose(M, M0)) if modo == "real" else None,
            "estado": c.get("estado"), "corridas": c.get("corridas", []),
            "estimado": estimado,
            "real_h": round(sum(r.get("horas_reales", 0) for r in c.get("corridas", [])), 3),
        }
    man["sofa"] = sofas or man.get("sofa", {})
    guardar_json(ruta, man)


# ---------------------------------------------------------------- principal

def piloto_12k() -> dict:
    p = json.loads((BARRIDO / "piloto" / "piloto.json").read_text(encoding="utf-8"))["corridas"]
    return {e: {"piloto_12000Hz_min": round(p[f"e{e}_12000Hz"]["segundos"] / 60, 2),
                "piloto_12000Hz_iteraciones": p[f"e{e}_12000Hz"]["iteraciones"]} for e in ORDEN_SECO}


def correr(modo: str, tanda: str | None, numcalc: Path) -> int:
    seco = modo == "seco"
    salida = BARRIDO / ("fase2_seco" if seco else SALIDA_TANDA.get(tanda, "fase2"))
    salida.mkdir(exist_ok=True)
    log = Registro(salida)
    condiciones = ORDEN_SECO if seco else TANDAS[tanda]
    sin_ventanas_de_error()
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)   # que no se duerma
    log(f"=== fase 2 {'PRUEBA EN SECO' if seco else f'tanda {tanda}'}: -e {', '.join(condiciones)} ===")
    if not (numcalc / "NumCalc.exe").is_file():
        log(f"no existe {numcalc / 'NumCalc.exe'}")
        return 2
    try:
        for e in condiciones:
            preparar(e, salida, numcalc, seco, log)
    except (RuntimeError, subprocess.TimeoutExpired) as ex:
        log(f"NO SE ARRANCA: {ex}")
        return 2
    horas = 1 if seco else sum(ESTIMADO_H[e]["en_serie"] or ESTIMADO_H[e]["manage_numcalc"] for e in condiciones) * 1.5
    v = verificar(condiciones, salida, numcalc, seco, horas)
    for x in v:
        marca = "OK   " if x["ok"] else ("FALLA" if x["bloquea"] else "AVISO")
        log(f"  [{marca}] {x['verificacion']}: {x['detalle']}")
    prog = Progreso(salida, modo)
    dry = piloto_12k() if seco else None
    if any(not x["ok"] and x["bloquea"] for x in v):
        log("NO SE ARRANCA: falló alguna verificación previa.")
        manifiesto(salida, condiciones, numcalc, v, modo, prog, {}, dry)
        return 2
    manifiesto(salida, condiciones, numcalc, v, modo, prog, {}, dry)

    codigo = 0
    for n, e in enumerate(condiciones):
        r = correr_condicion(e, salida, numcalc, prog, log, primera=(n == 0))
        manifiesto(salida, condiciones, numcalc, [], modo, prog, {}, dry)
        if r == "abortar":
            log("ABORTADO: la primera condición falló en sus primeros minutos; revisar la configuración.")
            return 3
        if r == "falló":
            codigo = 1
            log(f"e_{e} falló; se sigue con la siguiente condición.")
    try:
        sofas = escribir_sofas(salida, prog, log)
    except Exception as ex:                              # los datos de NumCalc ya están a salvo
        log(f"FALLÓ la escritura de SOFA: {ex!r}")
        sofas, codigo = {}, 1
    manifiesto(salida, condiciones, numcalc, [], modo, prog, sofas, dry)
    log(f"=== terminado ({'sin fallos' if codigo == 0 else 'con fallos: ver progreso.json'}) ===")
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
    return codigo


def principal() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "_manage":
        manage(sys.argv[2], sys.argv[3])
        return
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("modo", choices=["sellar", "seco", "real", "sofa"])
    a.add_argument("--numcalc", type=Path, help="carpeta NumCalc_WindowsExe")
    a.add_argument("--tanda", choices=list(TANDAS))
    x = a.parse_args()
    if x.modo == "sellar":
        sellar()
        return
    if x.modo == "sofa":            # reescribe los SOFA de diagnóstico desde los de output2hrtf, sin simular
        salida = BARRIDO / SALIDA_TANDA.get(x.tanda, "fase2")
        escribir_sofas(salida, Progreso(salida, "real"), Registro(salida))
        return
    if x.numcalc is None or (x.modo == "real" and x.tanda is None):
        a.error("seco y real piden --numcalc; real pide además --tanda")
    sys.exit(correr(x.modo, x.tanda, x.numcalc.resolve()))


if __name__ == "__main__":
    principal()
