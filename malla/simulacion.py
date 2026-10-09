"""Simulación con NumCalc y armado de la HRTF, después de la exportación. Quinta pieza del pipeline.

Entrada: la carpeta del escaneo con myHRTF_project_L y myHRTF_project_R (exportación aprobada).
Salida, en la misma carpeta:

  myHRTF_project_*/NumCalc/source_1/   lo que deja NumCalc (be.out/, NC*.out, Memory.txt)
  myHRTF_project_*/Output2HRTF/        los SOFA de cada oreja (output2hrtf de Mesh2HRTF)
  SOFA_myHRTF_project_merged/          la HRTF de las dos orejas juntas:
                                         HRTF_<rejilla>_48000.sofa   presión compleja, 160 frecuencias
                                         HRIR_<rejilla>_48000.sofa   respuesta al impulso a 48 kHz
                                         HRIR_<rejilla>_44100.sofa   ídem, remuestreada a 44,1 kHz
                                         parameters.json y figuras de diagnóstico
  informe_simulacion.json

1. NumCalc, una frecuencia por proceso, con manage_numcalc de Mesh2HRTF (el mismo planificador
   del barrido de -e). NumCalc no toma su memoria al arrancar sino durante minutos, así que la
   RAM libre que ve manage_numcalc se corrige descontando lo que a cada NumCalc vivo le falta para
   llegar a su estimación (como en experimentos/barrido_e/fase2.py). Se puede cortar y volver a
   lanzar: manage_numcalc salta las frecuencias ya terminadas.
2. La convergencia de cada frecuencia se lee de NC*.out (malla/convergencia.py): NumCalc termina
   con código 0 aunque no converja. Si alguna frecuencia no convergió o no tiene resultado, se
   para aquí: no se arma una HRTF con frecuencias inválidas.
3. output2hrtf de cada oreja y unión de las dos como lo hace finalize_hrtf_simulation.py (v3.02)
   de mesh2hrtf-tools, el procedimiento con que se armó la corrida de HUTUBS: la izquierda se
   reconoce por su receptor en +y, se unen los SOFA del mismo nombre, se agregan las HRIR a las
   frecuencias de muestreo menores que admite el vector (con 150 Hz de paso, 44,1 kHz) y se
   copia parameters.json. No se exportan los VTK de Paraview. Al final, cada SOFA unido lleva en
   GLOBAL_Comment cómo se hizo (gradado, NumCalc, convergencia).

Todo lo que hace falta viene con la app: NumCalc en numcalc/ (config.NUMCALC_EXE) y el paquete
de Python de Mesh2HRTF.
"""
import contextlib
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import psutil

import config
from malla import convergencia
from malla.gradado import sin_ventanas_de_error

GB = 2**30
CARPETA_SOFA = "SOFA_myHRTF_project_merged"      # el nombre que le da finalize_hrtf_simulation.py
DLL_NUMCALC = ("libgcc_s_seh-1.dll", "libstdc++-6.dll", "libwinpthread-1.dll")
DLL_NO_ENCONTRADA = 0xC0000135
ESPERA_MANAGE_S = 15             # wait_time de manage_numcalc (su valor por defecto)
MUESTREO_S = 10                  # cada cuánto el vigilante mira qué frecuencias terminaron
AVISO_ESPERA_S = 5 * 60          # sin ningún NumCalc corriendo tanto rato: se avisa que espera RAM
DESPLAZAMIENTO_HRIR = 40         # muestras; el que usa finalize_hrtf_simulation.py en compute_hrirs
FRECUENCIAS_MUESTREO = [192000, 96000, 88200, 48000, 44100]   # las que prueba finalize_hrtf_simulation.py


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def ahora() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def fuente(proyecto: Path) -> Path:
    return proyecto / "NumCalc" / "source_1"


def comprobar_numcalc() -> tuple[bool, str]:
    """¿Está NumCalc con sus DLL y arranca? Se corre en una carpeta vacía: sin NC.inp termina
    enseguida; lo que interesa es que no falte ninguna DLL."""
    exe = Path(config.NUMCALC_EXE)
    if not exe.is_file():
        return False, f"no está {exe}"
    faltan = [d for d in DLL_NUMCALC if not (exe.parent / d).is_file()]
    if faltan:
        return False, f"faltan junto a NumCalc.exe: {', '.join(faltan)}"
    sin_ventanas_de_error()
    with tempfile.TemporaryDirectory() as tmp:
        try:
            r = subprocess.run([str(exe)], cwd=tmp, capture_output=True, timeout=60)
        except subprocess.TimeoutExpired:
            return False, "NumCalc no terminó en 60 s en una carpeta vacía"
    if r.returncode & 0xFFFFFFFF == DLL_NO_ENCONTRADA:
        return False, "NumCalc no arranca: falta una DLL"
    if r.returncode & 0xFFFFFFFF >= 0xC0000000:
        return False, f"NumCalc se cayó al arrancar (código {r.returncode & 0xFFFFFFFF:#x})"
    return True, f"{exe} (versión 2022-08-26, la del barrido de -e)"


def estimar_ram(proyecto: Path) -> np.ndarray:
    """Memory.txt de NumCalc -estimate_ram (paso, frecuencia, GB); lo calcula si no está."""
    src = fuente(proyecto)
    if not (src / "Memory.txt").is_file():
        subprocess.run([str(config.NUMCALC_EXE), "-estimate_ram"], cwd=src, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=3600, check=True)
    return np.loadtxt(src / "Memory.txt", ndmin=2)


def terminado(src: Path, k: int) -> bool:
    """El mismo criterio de manage_numcalc: hay resultados y NC*.out llegó al final."""
    nc = src / f"NC{k}-{k}.out"
    return ((src / "be.out" / f"be.{k}" / "pEvalGrid").is_file() and nc.is_file()
            and "End time:" in nc.read_text(encoding="utf-8", errors="replace"))


def numcalc_del_proyecto(proyecto: Path) -> list[psutil.Process]:
    """Los NumCalc vivos que corren dentro de este proyecto (no los de otros)."""
    vivos = []
    for p in psutil.process_iter(["name"]):
        if (p.info["name"] or "").lower() == "numcalc.exe":
            with contextlib.suppress(psutil.Error):
                if Path(p.cwd()).resolve().is_relative_to(proyecto.resolve()):
                    vivos.append(p)
    return vivos


def tiempos_nc(ruta: Path) -> tuple[float | None, float | None]:
    """Inicio y fin (segundos de época) que escribe NumCalc en NC*.out."""
    texto = ruta.read_text(encoding="utf-8", errors="replace") if ruta.is_file() else ""
    res = []
    for etiqueta in ("Start time", "End time"):
        m = re.search(etiqueta + r": (\d+)/(\d+)/(\d+) (\d+):(\d+):(\d+)", texto)
        res.append(datetime(int(m[3]), int(m[2]), int(m[1]), int(m[4]), int(m[5]), int(m[6])).timestamp()
                   if m else None)
    return res[0], res[1]


def correr_numcalc(proyecto: Path, memoria: np.ndarray, registrar) -> dict:
    """manage_numcalc sobre un proyecto, con la RAM corregida y un vigilante que avisa cada
    frecuencia que termina. Devuelve lo medido (tiempo de pared, RAM pico sumada)."""
    import mesh2hrtf as m2h
    from mesh2hrtf.NumCalc import manage_numcalc as modulo_manage
    src = fuente(proyecto)
    estimada = {int(p): g * GB for p, g in zip(memoria[:, 0], memoria[:, 2])}
    frecuencias = {int(p): f for p, f in zip(memoria[:, 0], memoria[:, 1])}

    def ram_con_reservas(total_ram, max_ram_load):
        libre = psutil.virtual_memory().available
        pendiente = 0
        for p in numcalc_del_proyecto(proyecto):
            with contextlib.suppress(psutil.Error, ValueError, IndexError):
                args = p.cmdline()
                paso = int(args[args.index("-istart") + 1])
                pendiente += max(0.0, estimada.get(paso, 0) * config.SIMULACION_MARGEN_RAM - p.memory_info().rss)
        usada = total_ram - libre / GB
        return max(0.0, max_ram_load - usada - pendiente / GB), usada

    hechos = {k for k in frecuencias if terminado(src, k)}
    medido = {"pico_ram_suma_gb": 0.0}
    parar = threading.Event()

    def anunciar_terminados() -> None:
        for k in sorted(set(frecuencias) - hechos):
            if terminado(src, k):
                hechos.add(k)
                r = convergencia.leer_salida(src / f"NC{k}-{k}.out").get(k, {})
                estado = {True: "convergió", False: "NO CONVERGIÓ", None: "sin resultado"}[r.get("convergio")]
                registrar(f"  {proyecto.name}: {len(hechos)}/{len(frecuencias)} · {frecuencias[k]:.0f} Hz "
                          f"{estado} ({r.get('iteraciones')} iteraciones)")

    def vigilar() -> None:
        sin_nada_desde = None
        while not parar.wait(MUESTREO_S):
            vivos = numcalc_del_proyecto(proyecto)
            suma = 0
            for p in vivos:
                with contextlib.suppress(psutil.Error):
                    suma += p.memory_info().rss
            medido["pico_ram_suma_gb"] = max(medido["pico_ram_suma_gb"], suma / GB)
            anunciar_terminados()
            # ningún NumCalc corriendo y quedan frecuencias: manage_numcalc espera RAM libre
            if vivos or len(hechos) == len(frecuencias):
                sin_nada_desde = None
            elif sin_nada_desde is None:
                sin_nada_desde = time.time()
            elif time.time() - sin_nada_desde > AVISO_ESPERA_S:
                sin_nada_desde = time.time()
                faltan = [k for k in frecuencias if k not in hechos]
                registrar(f"  {proyecto.name}: esperando memoria libre ({psutil.virtual_memory().available / GB:.1f} GB "
                          f"libres; la siguiente pide hasta {max(estimada[k] for k in faltan) / GB:.1f} GB). "
                          "Cerrar otros programas")

    def solo_al_log(mensaje, _color, log_file):
        """manage_numcalc escribe cada paso en pantalla y en su log; aquí solo en su log (el
        vigilante informa en pantalla, una línea por frecuencia terminada)."""
        with open(log_file, "a", encoding="utf8", newline="\n") as f:
            f.write(mensaje + "\n")

    hilo = threading.Thread(target=vigilar, daemon=True)
    t0 = time.time()
    modulo_manage._get_current_ram = ram_con_reservas
    modulo_manage._print_message = solo_al_log
    sin_ventanas_de_error()          # lo heredan los NumCalc: si falta una DLL, terminan con un código
    hilo.start()
    try:
        m2h.manage_numcalc(project_path=str(proyecto), numcalc_path=str(Path(config.NUMCALC_EXE).parent),
                           ram_safety_factor=config.SIMULACION_MARGEN_RAM, wait_time=ESPERA_MANAGE_S,
                           starting_order="alternate", confirm_errors=False)
    except BaseException:
        # cortado (o manage_numcalc falló): no dejar NumCalc huérfanos de este proyecto. Lo que
        # quedó a medias se vuelve a simular la próxima vez (no tiene "End time").
        for p in numcalc_del_proyecto(proyecto):
            with contextlib.suppress(psutil.Error):
                p.kill()
        raise
    finally:
        parar.set()
        hilo.join()
    anunciar_terminados()            # los que terminaron después del último muestreo
    return {"horas_pared": round((time.time() - t0) / 3600, 3),
            "pico_ram_suma_numcalc_gb": round(medido["pico_ram_suma_gb"], 2)}


def estado_lado(proyecto: Path, memoria: np.ndarray) -> dict:
    """Convergencia y tiempos de todas las frecuencias de un proyecto, leídos de NC*.out."""
    src = fuente(proyecto)
    # solo los pasos del vector actual: el NC.out de -estimate_ram (o de una exportación anterior)
    # puede nombrar pasos que este proyecto ya no tiene
    validos = {int(p) for p in memoria[:, 0]}
    pasos = {k: r for k, r in convergencia.leer_fuente(src).items() if k in validos}
    for k in sorted(validos):                                   # pasos que nunca arrancaron
        pasos.setdefault(k, {"frecuencia_hz": float(memoria[k - 1, 1]), "convergio": None,
                             "iteraciones": None, "factor_reduccion_residuo": None,
                             "alcanzo_tope": None, "aviso_tope": False, "ilu_fallido": False,
                             "respaldo_directo": False})
    minutos = []
    for k, r in pasos.items():
        ini, fin = tiempos_nc(src / f"NC{k}-{k}.out")
        r["minutos"] = round((fin - ini) / 60, 2) if ini and fin else None
        if r["minutos"] is not None:
            minutos.append(r["minutos"])
    res = convergencia.resumen(pasos)
    convergidos = [r for r in pasos.values() if r["convergio"]]
    return {"frecuencias": len(memoria), "de_hz": float(memoria[0, 1]), "a_hz": float(memoria[-1, 1]),
            "ram_estimada_max_gb": round(float(memoria[:, 2].max()), 2),
            "convergencia": res,
            "iteraciones_max": max((r["iteraciones"] for r in convergidos), default=None),
            "factor_max": max((r["factor_reduccion_residuo"] for r in convergidos), default=None),
            "horas_suma_por_frecuencia": round(sum(minutos) / 60, 2),
            "pasos": {str(k): r for k, r in sorted(pasos.items())}}


# --- unión de las dos orejas (finalize_hrtf_simulation.py v3.02 de mesh2hrtf-tools) -----------
def unir_sofa(izq, der, carpeta: Path, nombre: str, tipo: str):
    """merge_write_sofa de finalize_hrtf_simulation.py: un SOFA con las dos orejas."""
    import sofar as sf
    sofa = sf.Sofa("SimpleFreeFieldHRTF" if tipo == "HRTF" else "SimpleFreeFieldHRIR")
    sofa.GLOBAL_ApplicationName = izq.GLOBAL_ApplicationName
    sofa.GLOBAL_ApplicationVersion = izq.GLOBAL_ApplicationVersion
    sofa.GLOBAL_History = izq.GLOBAL_History
    sofa.GLOBAL_Title = izq.GLOBAL_Title or f"untitled {tipo} SOFA data"
    sofa.GLOBAL_Origin = izq.GLOBAL_Origin or "Mesh2HRTF_simulation"
    sofa.SourcePosition = izq.SourcePosition
    sofa.SourcePosition_Units = izq.SourcePosition_Units
    sofa.SourcePosition_Type = izq.SourcePosition_Type
    sofa.ReceiverPosition = [izq.ReceiverPosition.reshape(3, 1), der.ReceiverPosition.reshape(3, 1)]
    sofa.ReceiverPosition_Units = izq.ReceiverPosition_Units
    sofa.ReceiverPosition_Type = izq.ReceiverPosition_Type
    if tipo == "HRTF":
        sofa.Data_Real = np.concatenate((izq.Data_Real, der.Data_Real), axis=1)
        sofa.Data_Imag = np.concatenate((izq.Data_Imag, der.Data_Imag), axis=1)
        sofa.N = izq.N
        fs = int(2 * sofa.N[-1])
    else:
        sofa.Data_IR = np.concatenate((izq.Data_IR, der.Data_IR), axis=1)
        sofa.Data_SamplingRate = izq.Data_SamplingRate
        sofa.Data_Delay = np.ones((1, 2)) * izq.Data_Delay
        fs = int(sofa.Data_SamplingRate)
    sofa.verify()
    ruta = carpeta / f"{Path(nombre).stem}_{fs}.sofa"
    ruta.unlink(missing_ok=True)
    sf.write_sofa(str(ruta), sofa)
    return ruta, sofa


def unir_orejas(izq: Path, der: Path, destino: Path, registrar) -> tuple[list[Path], list[str]]:
    """Une los SOFA de Output2HRTF de las dos orejas. Devuelve (archivos, fallas)."""
    import mesh2hrtf as m2h
    import sofar as sf
    a, b = izq / "Output2HRTF", der / "Output2HRTF"
    nombres = sorted((p.name for p in a.glob("*.sofa")), key=lambda x: x.split("_")[0])
    if not nombres or nombres != sorted((p.name for p in b.glob("*.sofa")), key=lambda x: x.split("_")[0]):
        return [], [f"los SOFA de {a} y {b} no coinciden: {nombres} / {[p.name for p in b.glob('*.sofa')]}"]
    primero = sf.read_sofa(str(a / nombres[0]))
    if primero.ReceiverPosition[0, 1] <= 0:
        return [], [f"{izq.name} no es la oreja izquierda: su receptor está en y = {primero.ReceiverPosition[0, 1]}"]
    # HRIR a frecuencias de muestreo menores, si el paso del vector lo permite (150 o 75 Hz)
    paso = np.round(primero.Data_SamplingRate / primero.Data_IR.shape[2])
    otras = [fs for fs in FRECUENCIAS_MUESTREO if paso in (150, 75) and primero.Data_IR.shape[2] > fs / paso]
    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir()
    archivos, fallas = [], []
    for nombre in nombres:
        L, R = sf.read_sofa(str(a / nombre)), sf.read_sofa(str(b / nombre))
        tipo = "HRIR" if L.GLOBAL_DataType == "FIR" else "HRTF"
        if tipo == "HRIR" and (L.Data_SamplingRate != R.Data_SamplingRate or L.Data_IR.shape != R.Data_IR.shape):
            fallas.append(f"{nombre}: las dos orejas no tienen la misma frecuencia de muestreo o el mismo largo")
            continue
        if tipo == "HRTF" and (L.N.size != R.N.size or np.any(np.abs(L.N - R.N) > 1e-6)):
            fallas.append(f"{nombre}: las dos orejas no tienen las mismas frecuencias")
            continue
        ruta, unido = unir_sofa(L, R, destino, nombre, tipo)
        archivos.append(ruta)
        if tipo == "HRTF":
            for fs in otras:
                hrir = m2h.compute_hrirs(unido, DESPLAZAMIENTO_HRIR, int(fs))
                ruta = destino / f"{Path(nombre.replace('HRTF', 'HRIR')).stem}_{fs}.sofa"
                sf.write_sofa(str(ruta), hrir)
                archivos.append(ruta)
    if (izq / "parameters.json").is_file():
        shutil.copy2(izq / "parameters.json", destino / "parameters.json")
    registrar(f"  SOFA unidos en {destino.name}: {', '.join(p.name for p in archivos)}")
    return archivos, fallas


def figuras(destino: Path, registrar) -> list[str]:
    """Las figuras de diagnóstico de finalize_hrtf_simulation.py (inspect_sofa_files, 2D y 3D)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import mesh2hrtf as m2h
    avisos = []
    for tipo in ("2D", "3D"):
        try:
            with contextlib.redirect_stdout(None):
                m2h.inspect_sofa_files(str(destino), plot=tipo, plane="horizontal", atol=0.1)
        except Exception as error:                      # las figuras son una ayuda, no un resultado
            avisos.append(f"no se pudieron hacer las figuras {tipo}: {error}")
        plt.close("all")
    if not avisos:
        registrar("  figuras de diagnóstico guardadas junto a los SOFA")
    return avisos


def version_pipeline() -> str:
    """Commit del repositorio (y si hay cambios sin commit); en la app empaquetada no hay git."""
    try:
        h = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=config.CARPETA_RECURSOS,
                           capture_output=True, text=True, timeout=10)
        s = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=config.CARPETA_RECURSOS,
                           capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return "sin git"
    if h.returncode != 0:
        return "sin git"
    return h.stdout.strip() + (" con cambios sin commit" if s.stdout.strip() else "")


def comentario(informe: dict, gradado: dict) -> str:
    """GLOBAL_Comment de los SOFA unidos: cómo se hizo esta HRTF."""
    p = gradado.get("parametros", {})
    lados = informe["lados"]
    n = lados["left"]["frecuencias"]
    it = max(l["iteraciones_max"] or 0 for l in lados.values())
    return (f"pipeline_hrtf ({informe['version_pipeline']}): escaneo de celular (KIRI Engine) limpiado y "
            f"escalado, cuello cortado a {config.CORTE_CUELLO_MM:g} mm del eje interaural, gradado con "
            f"hrtf_mesh_grading -x {p.get('x_mm')} -e {p.get('e_mm')} -y {p.get('y_mm')} (una malla por oreja), "
            f"exportado con Mesh2HRTF 1.3.0 (ML-FMM BEM, c = {config.EXPORTACION_MESH2HRTF['speedOfSound']} m/s). "
            f"NumCalc 2022-08-26 (sin -adapt_fmmlength). {n} frecuencias por oreja de "
            f"{lados['left']['de_hz']:.0f} a {lados['left']['a_hz']:.0f} Hz; convergencia leida de NC*.out: "
            f"convergieron todas (factor de reduccion del residuo < 1e-9, maximo {it} de 250 iteraciones). "
            f"Union de las dos orejas como finalize_hrtf_simulation.py v3.02. Simulado {informe['fin']}.")


def anotar(archivos: list[Path], texto: str) -> dict:
    import sofar as sf
    huellas = {}
    for ruta in archivos:
        sofa = sf.read_sofa(str(ruta))
        sofa.GLOBAL_Comment = texto
        sf.write_sofa(str(ruta), sofa)
        huellas[ruta.name] = sha256(ruta)
    return huellas


# --- la etapa completa --------------------------------------------------------------------------
def simular(carpeta: Path, registrar=print) -> dict:
    """Simula las dos orejas, verifica la convergencia y arma la HRTF. Devuelve (y guarda) el
    informe; "aprobado" dice si hay HRTF válida."""
    import mesh2hrtf as m2h
    carpeta = Path(carpeta).resolve()
    informe = {"inicio": ahora(), "version_pipeline": version_pipeline(),
               "numcalc": {"ruta": str(config.NUMCALC_EXE)}, "margen_ram": config.SIMULACION_MARGEN_RAM,
               "lados": {}, "avisos": [], "fallas": []}

    ok, mensaje = comprobar_numcalc()
    registrar(("NumCalc: " if ok else "ERROR: ") + mensaje)
    if not ok:
        informe["fallas"].append(mensaje)
        return guardar_informe(carpeta, informe)
    informe["numcalc"]["sha256"] = sha256(Path(config.NUMCALC_EXE))
    try:
        exportacion = json.loads((carpeta / "informe_exportacion.json").read_text(encoding="utf-8"))
        gradado = json.loads((carpeta / "informe_gradado.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        exportacion, gradado = {}, {}
    if not exportacion.get("aprobado"):
        informe["fallas"].append("primero hay que exportar los proyectos (exportación aprobada)")
        return guardar_informe(carpeta, informe)
    proyectos = {lado: carpeta / nombre for lado, nombre in config.PROYECTOS_MESH2HRTF.items()}
    informe["entrada"] = {"gradado": gradado.get("parametros"), "exportacion": exportacion.get("parametros"),
                          "sha256_nc_inp": {lado: sha256(fuente(p) / "NC.inp") for lado, p in proyectos.items()}}

    # 1. NumCalc, oreja por oreja
    for lado, proyecto in proyectos.items():
        M = estimar_ram(proyecto)
        src = fuente(proyecto)
        pendientes = [int(k) for k in M[:, 0] if not terminado(src, int(k))]
        registrar(f"{proyecto.name}: {len(M)} frecuencias ({M[0, 1]:.0f}–{M[-1, 1]:.0f} Hz), "
                  f"{len(pendientes)} por simular; el paso más caro pide {M[:, 2].max():.2f} GB")
        medido = {}
        if pendientes:
            # Imposible: más que toda la RAM del equipo. Si solo falta RAM libre ahora,
            # manage_numcalc empieza por las que caben y espera a que se libere para las demás.
            necesaria = float(M[[k - 1 for k in pendientes], 2].max()) * config.SIMULACION_MARGEN_RAM
            total = psutil.virtual_memory().total / GB
            libre = psutil.virtual_memory().available / GB
            if necesaria > total:
                informe["fallas"].append(
                    f"{proyecto.name}: la frecuencia más cara pide {necesaria:.1f} GB y el equipo tiene "
                    f"{total:.1f} GB en total: no se puede simular en este equipo")
                return guardar_informe(carpeta, informe)
            if necesaria > libre:
                aviso = (f"{proyecto.name}: hay {libre:.1f} GB libres y las frecuencias más caras piden hasta "
                         f"{necesaria:.1f} GB; esas esperan a que se libere memoria. Cerrar el navegador y "
                         "otros programas")
                registrar("AVISO: " + aviso)
                informe["avisos"].append(aviso)
            shutil.rmtree(proyecto / "Output2HRTF", ignore_errors=True)   # va a cambiar
            registrar(f"{proyecto.name}: simulando (tarda horas; se puede cortar y volver a lanzar)...")
            try:
                medido = correr_numcalc(proyecto, M, registrar)
            except Exception as error:
                informe["fallas"].append(f"{proyecto.name}: manage_numcalc falló: {error}")
        informe["lados"][lado] = {"proyecto": proyecto.name, **estado_lado(proyecto, M), **medido}
        c = informe["lados"][lado]["convergencia"]
        if c["sin_resultado"]:
            informe["fallas"].append(f"{proyecto.name}: {len(c['sin_resultado'])} frecuencias sin resultado "
                                     f"({', '.join(f'{x['frecuencia_hz']:.0f}' for x in c['sin_resultado'][:10])} Hz...). "
                                     "Volver a lanzar: se simulan solo esas")
        if c["no_convergieron"]:
            informe["fallas"].append(f"{proyecto.name}: no convergieron "
                                     f"{', '.join(f'{x['frecuencia_hz']:.0f}' for x in c['no_convergieron'])} Hz "
                                     "(NumCalc llegó a 250 iteraciones sin bajar de 1e-9)")
        for clave, texto in (("ilu_fallido", "el ILU falló y se usó el escalado por filas"),
                             ("respaldo_directo", "CGS falló y se resolvió por eliminación gaussiana"),
                             ("aviso_tope_incoherente", "el aviso de tope no coincide con las iteraciones")):
            if c[clave]:
                informe["avisos"].append(f"{proyecto.name}: {texto} en "
                                         f"{', '.join(f'{x['frecuencia_hz']:.0f}' for x in c[clave])} Hz")
        registrar(f"{proyecto.name}: {c['convergieron']}/{c['pasos']} frecuencias convergieron")
    if informe["fallas"]:
        return guardar_informe(carpeta, informe)

    # 2. output2hrtf de cada oreja y unión
    for lado, proyecto in proyectos.items():
        if not (proyecto / "Output2HRTF" / "HRTF_Default.sofa").is_file():
            registrar(f"{proyecto.name}: output2hrtf...")
            with open(proyecto / "output2hrtf.log", "w", encoding="utf-8") as log, \
                    contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                m2h.output2hrtf(str(proyecto))
    destino = carpeta / CARPETA_SOFA
    archivos, fallas = unir_orejas(proyectos["left"], proyectos["right"], destino, registrar)
    informe["fallas"] += fallas
    if informe["fallas"] or not archivos:
        return guardar_informe(carpeta, informe)
    informe["fin"] = ahora()
    informe["sofa"] = {"carpeta": destino.name, "sha256": anotar(archivos, comentario(informe, gradado))}
    informe["avisos"] += figuras(destino, registrar)
    # para escuchar (no para métricas): la HRIR ecualizada al campo difuso y los WAV de HeSuVi
    try:
        from malla import dtf
        informe["dtf"] = {p.name: sha256(p) for p in dtf.escribir(destino, registrar)}
    except Exception as error:
        informe["avisos"].append(f"no se pudo escribir la HRIR ecualizada (DTF): {error}")
    try:
        from malla import hesuvi
        informe["hesuvi"] = hesuvi.exportar(destino, registrar)
    except Exception as error:
        informe["avisos"].append(f"no se pudieron exportar los WAV de HeSuVi: {error}")
    return guardar_informe(carpeta, informe)


def guardar_informe(carpeta: Path, informe: dict) -> dict:
    informe.setdefault("fin", ahora())
    informe["aprobado"] = not informe["fallas"] and bool(informe.get("sofa"))
    (carpeta / "informe_simulacion.json").write_text(json.dumps(informe, indent=2, ensure_ascii=False),
                                                     encoding="utf-8")
    return informe
