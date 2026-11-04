"""App del pipeline HRTF (NiceGUI): marcar puntos, alinear, medir, limpiar, gradar, exportar y simular.

1. Malla y puntos. Se carga el escaneo y se marcan con DOBLE CLIC siete puntos: la
   entrada de los dos canales auditivos y la punta de la nariz (definen la alineación,
   ver malla/alineacion.py) y lo más alto y lo más bajo de cada oreja (su largo sirve
   para la escala). Opcionalmente, dos más: los tragos, para escalar con el ancho
   bitragial medido con pie de rey. Se guardan <nombre>_alineada.ply y <nombre>_landmarks.json junto
   a la malla.
2. Medidas de la persona (opcionales): ancho bitragial (pie de rey), largo de cada
   oreja y circunferencia de la cabeza. La limpieza corre limpiar_malla.py en un proceso aparte, con su salida en
   pantalla, así que da lo mismo que desde la terminal.
3. Resultado: veredicto del control de calidad, escala, y las mallas de cada paso en
   el mismo visor.
4. Gradado: gradar_malla.py en un proceso aparte, igual que la limpieza. Al arrancar,
   la app comprueba que el binario del gradado (grading/) existe y arranca.
5. Exportación a Mesh2HRTF: exportar_malla.py en un proceso aparte (usa Blender en
   segundo plano). Al arrancar, la app comprueba que encuentra Blender.
6. Simulación y HRTF: simular_malla.py en un proceso aparte (NumCalc viene con la app, en
   numcalc/). Tarda horas; trabaja sobre una carpeta de resultados que se puede elegir, así
   que una simulación cortada se retoma sin repetir los pasos anteriores.

Ejecutar:  .venv/Scripts/python.exe app.py   ->  http://localhost:8080
Empaquetada (pipeline_hrtf.spec), la app se relanza a sí misma para cada tarea:
  pipeline_hrtf.exe limpiar | gradar | exportar | simular | hesuvi ...   (mismos argumentos que
  limpiar_malla.py, gradar_malla.py, exportar_malla.py, simular_malla.py y exportar_hesuvi.py; p. ej.
  pipeline_hrtf.exe simular --diagnostico)
"""
import json
import multiprocessing
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import numpy as np
import trimesh
from nicegui import app, events, run, ui
from scipy.spatial import cKDTree

import config
from malla.alineacion import aplicar_transformacion, matriz_alineacion, residuo_alineacion
from malla.gradado import MALLA_MM
from malla.exportacion import comprobar_blender
from malla.gradado import SALIDAS as SALIDAS_GRADADO
from malla.gradado import comprobar_binario
from malla.oreja import PUNTOS_BITRAGO, PUNTOS_LARGO
from malla.simulacion import CARPETA_SOFA, comprobar_numcalc

RAIZ = Path(__file__).resolve().parent
# Tareas largas que corren en un proceso aparte: subcomando -> script
TAREAS = {"limpiar": "limpiar_malla.py", "gradar": "gradar_malla.py", "exportar": "exportar_malla.py",
          "simular": "simular_malla.py", "hesuvi": "exportar_hesuvi.py"}
# Lo que se comprueba al arrancar: (bien, mensaje)
ESTADO_BINARIO: tuple[bool, str] = (False, "sin comprobar")   # binario del gradado
ESTADO_BLENDER: tuple[bool, str] = (False, "sin comprobar")   # Blender, para exportar
ESTADO_NUMCALC: tuple[bool, str] = (False, "sin comprobar")   # NumCalc, para simular
RUTA_POR_DEFECTO = Path(config.RUTA_DATOS) / "entrada" / "3Dmesh_orig.stl"
EXTENSIONES = {".obj", ".ply", ".stl"}
RESIDUO_MAX = 1e-6
# Límites SOLO para detectar unidades equivocadas (0.063 en vez de 63): fuera de esto no
# puede ser una oreja o una cabeza en milímetros. No juzgan si la medida es buena.
RANGO_OREJA_MM = (20, 120)
RANGO_CIRCUNFERENCIA_MM = (300, 900)
RANGO_BITRAGO_MM = (90, 220)

# Los puntos, en el orden en que se marcan: (clave, texto, color del marcador).
# Los tres primeros definen la alineación; los de las orejas, su largo (malla/oreja.py).
# Los siete primeros son obligatorios; los dos tragos, opcionales (solo hacen falta para
# escalar con el ancho bitragial medido con pie de rey).
HELIX_IZQ, LOBULO_IZQ = PUNTOS_LARGO["izq"]
HELIX_DER, LOBULO_DER = PUNTOS_LARGO["der"]
TRAGO_IZQ, TRAGO_DER = PUNTOS_BITRAGO
LANDMARKS = [
    ("oreja_izquierda", "la entrada del canal auditivo IZQUIERDO", "#e53935"),
    ("oreja_derecha", "la entrada del canal auditivo DERECHO", "#43a047"),
    ("nariz", "la punta de la NARIZ", "#1e88e5"),
    (HELIX_IZQ, "el punto más ALTO de la oreja IZQUIERDA (borde del hélix)", "#fb8c00"),
    (LOBULO_IZQ, "el punto más BAJO de la oreja IZQUIERDA (lóbulo)", "#fb8c00"),
    (HELIX_DER, "el punto más ALTO de la oreja DERECHA (borde del hélix)", "#8e24aa"),
    (LOBULO_DER, "el punto más BAJO de la oreja DERECHA (lóbulo)", "#8e24aa"),
    (TRAGO_IZQ, "el TRAGO IZQUIERDO (la muesca justo encima del trago, donde se apoyó el pie de rey)",
     "#00897b"),
    (TRAGO_DER, "el TRAGO DERECHO (la muesca justo encima del trago, donde se apoyó el pie de rey)",
     "#00897b"),
]
N_ALINEACION = 3
N_OBLIGATORIOS = 7
# La cámara va sola a donde está el punto que toca marcar (clave: cuántos hay marcados).
# Antes de alinear es una suposición por los ejes del archivo; después, exacta.
VISTA_PARA_PUNTO = {0: "Izquierda", 1: "Derecha", 2: "Frente", 3: "Izquierda", 5: "Derecha",
                    7: "Izquierda", 8: "Derecha"}

# Vistas en el sistema anatómico: dirección desde la que se mira y "arriba" de la pantalla
VISTAS = {
    "Frente": ((1, 0, 0), (0, 0, 1)), "Atrás": ((-1, 0, 0), (0, 0, 1)),
    "Izquierda": ((0, 1, 0), (0, 0, 1)), "Derecha": ((0, -1, 0), (0, 0, 1)),
    "Arriba": ((0, 0, 1), (1, 0, 0)), "Abajo": ((0, 0, -1), (1, 0, 0)),
}
# Antes de alinear no hay ejes anatómicos. Los .obj de KIRI traen +Y arriba y la cara
# hacia +Z (convención de OBJ y glTF): esta rotación lleva los ejes anatómicos a esos.
# STL y PLY se suponen con +Z arriba.
R_ARCHIVO_Y_ARRIBA = np.array([[0, 1, 0], [0, 0, 1], [1, 0, 0]], dtype=float)

# Visor: una luz sale siempre de la cámara (la luz fija de NiceGUI deja la malla plana y
# no se distingue la oreja). Intensidades ajustadas mirando capturas de B.
COLOR_RELIEVE = "#9a9a9a"
LUZ_RELIEVE, LUZ_TEXTURA = 2.5, 1.5

# Mallas que deja la limpieza, en el orden en que se ofrecen en el visor
MALLAS_LIMPIEZA = [
    ("1_limpia_abierta.ply", "1 · limpia abierta"),
    ("2_cerrada_poisson.ply", "2 · cerrada (Poisson)"),
    ("3_suavizada.ply", "3 · suavizada"),
    (MALLA_MM, "Final en mm"),
    (SALIDAS_GRADADO["left"], "Graduada izquierda"),
    (SALIDAS_GRADADO["right"], "Graduada derecha"),
]
MALLAS_EN_MM = {MALLA_MM, *SALIDAS_GRADADO.values()}   # escaladas después de alinear

INSTRUCCIONES_MEDIDAS = """
**Todas son opcionales.** Sin ninguna, la malla queda sin escala real (en las unidades
arbitrarias de KIRI). Con varias, se usa la mediana y se muestra cuánto se aparta cada una;
si se da el ancho bitragial, manda él y las demás quedan de control.

**Ancho bitragial (pie de rey).** De tragion a tragion: la pequeña muesca justo encima de
cada trago (la pestaña de cartílago delante del canal), por delante de la cara, sin apretar
la piel. Tres veces y la del medio; mejor si mide otra persona, el mismo día del escaneo.
Hay que marcar en la malla los dos tragos (puntos 8 y 9) **en el mismo sitio** donde se
apoyó el pie de rey.

**Largo de cada oreja.** Con una regla, en línea recta desde el punto más alto del borde
de la oreja (hélix) hasta el punto más bajo del lóbulo, sin aplastarla. Son los mismos dos
puntos que se marcan en la malla. Mejor si lo mide otra persona.

**Circunferencia de la cabeza.** Con cinta métrica y **el mismo gorro del escaneo puesto**.
La cinta pasa justo por encima de las cejas y de las orejas, y rodea la cabeza paralela a la
línea que va de la oreja a la punta de la nariz (vista de perfil, la cinta y esa línea no se
acercan ni se alejan). Ajustada, sin apretar: cada milímetro de holgura cambia la escala ~1 %.

*Protocolo provisional: falta validarlo con medidas reales (ver malla/LIMPIEZA.md).*
"""

# Aspecto: modo oscuro con la paleta de Quasar ajustada y unas pocas clases propias
COLORES = dict(primary="#5b8cff", secondary="#8b6cff", accent="#2ec4a6", positive="#34c37a",
               negative="#f0605d", warning="#f5a524", info="#5b8cff", dark="#161a22")
CSS = """
body { background: #0f1218; }
.encabezado { background: #161a22 !important; border-bottom: 1px solid #262c38; }
.tarjeta { background: #161a22 !important; border: 1px solid #262c38; border-radius: 14px; box-shadow: none; }
.q-stepper--vertical .q-stepper__tab { padding-top: 14px; padding-bottom: 14px; }
.tenue { color: #8b94a8; }
.instruccion { color: #9cb8ff; }
.registro { background: #0b0e13 !important; color: #c9d1d9; font-family: Consolas, monospace;
            font-size: 12px; border-radius: 8px; border: 1px solid #222833; }
.visor-vacio { width: 640px; height: 480px; border-radius: 10px; background: #1b2029;
               display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; }
.dato { background: #1b2029; border-radius: 8px; padding: 6px 10px; }
.punto { width: 10px; height: 10px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
"""
FONDO_VISOR = "#1b2029"
ANCHO_VISOR, ALTO_VISOR = 640, 480


def ruta_corta(ruta) -> str:
    """La ruta desde la carpeta que contiene datos/ (p. ej. datos/salidas/C3), o solo el nombre."""
    ruta = Path(ruta)
    try:
        return ruta.resolve().relative_to(Path(config.RUTA_DATOS).resolve().parent).as_posix()
    except ValueError:
        return ruta.name


def veredicto(texto: str, bien: bool) -> None:
    with ui.row().classes("items-center gap-2 mt-2"):
        ui.icon("check_circle" if bien else "cancel", color="positive" if bien else "negative") \
            .classes("text-3xl")
        ui.label(texto).classes("text-xl font-semibold " + ("text-positive" if bien else "text-negative"))


def fallas_y_avisos(fallas: list[str], avisos: list[str]) -> None:
    for falla in fallas:
        ui.label(f"✖ {falla}").classes("text-negative text-sm")
    for aviso in avisos:
        ui.label(f"⚠ {aviso}").classes("text-warning text-sm")


def dato(texto: str) -> None:
    ui.label(texto).classes("dato text-sm")


# El visor carga las mallas desde una URL, así que se sirve una carpeta temporal con
# copias en STL (three.js no lee .obj ni .ply directamente).
DIR_VISOR = Path(tempfile.mkdtemp(prefix="pipeline_hrtf_"))
app.add_static_files("/visor", DIR_VISOR)


# --- Funciones sin interfaz (se ejecutan en un hilo aparte) --------------------
def cargar_malla(ruta: Path) -> trimesh.Trimesh:
    m = trimesh.load(ruta, process=False)
    if isinstance(m, trimesh.Scene):        # .obj con varios objetos
        m = m.to_geometry()
    return m


def exportar_para_visor(ruta: Path, malla: trimesh.Trimesh) -> Path:
    destino = DIR_VISOR / f"{uuid.uuid4().hex}.stl"   # nombre único: evita caché
    if ruta.suffix.lower() == ".stl":
        shutil.copy(ruta, destino)
    else:
        malla.export(destino, file_type="stl")
    return destino


def exportar_textura(malla: trimesh.Trimesh) -> Path | None:
    """Copia en GLB con la textura del escaneo (KIRI la trae), o None si no tiene."""
    material = getattr(malla.visual, "material", None)
    imagen = getattr(material, "image", None) or getattr(material, "baseColorTexture", None)
    if getattr(malla.visual, "uv", None) is None or imagen is None:
        return None
    con_textura = malla.copy()
    pbr = material.to_pbr() if hasattr(material, "to_pbr") else material.copy()
    # mate y no metálico: el metálico por defecto se ve negro sin reflejos del entorno
    pbr.metallicFactor, pbr.roughnessFactor = 0.0, 1.0
    con_textura.visual.material = pbr
    destino = DIR_VISOR / f"{uuid.uuid4().hex}.glb"
    destino.write_bytes(con_textura.export(file_type="glb", include_normals=True))
    return destino


def rotar(q, v) -> np.ndarray:
    """Rota el vector v con el cuaternión q = (x, y, z, w)."""
    u, w = np.asarray(q[:3], dtype=float), float(q[3])
    t = 2 * np.cross(u, v)
    return np.asarray(v, dtype=float) + w * t + np.cross(u, t)


def preparar_resultado(ruta: Path) -> tuple[Path, np.ndarray, np.ndarray]:
    """Copia en STL de una malla de salida de la limpieza, y su caja envolvente."""
    malla = cargar_malla(ruta)
    return exportar_para_visor(ruta, malla), malla.vertices.min(0), malla.vertices.max(0)


def carpeta_salida(ruta_malla: Path) -> Path:
    """La misma carpeta que usa limpiar_malla.py por defecto."""
    return Path(config.RUTA_DATOS) / "salidas" / ruta_malla.resolve().parent.name


# Diálogos nativos de Windows para elegir la malla o la carpeta de resultados. Se abren con
# PowerShell (Windows Forms) porque la app empaquetada no lleva tkinter; salen en el PC donde
# corre la app, que es el mismo del navegador. La ruta inicial va por variable de entorno para
# no tener que escapar comillas ni tildes, y la respuesta vuelve en UTF-8.
_DIALOGO = """
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName System.Windows.Forms
$dueno = New-Object System.Windows.Forms.Form -Property @{{TopMost = $true; ShowInTaskbar = $false}}
{cuerpo}
if ($d.ShowDialog($dueno) -eq [System.Windows.Forms.DialogResult]::OK) {{ {resultado} }}
"""
_ELEGIR_ARCHIVO = _DIALOGO.format(cuerpo="""$d = New-Object System.Windows.Forms.OpenFileDialog -Property @{
    Title = 'Elegir la malla del escaneo'; InitialDirectory = $env:DIALOGO_INICIAL
    Filter = 'Mallas 3D (*.obj;*.ply;*.stl)|*.obj;*.ply;*.stl|Todos los archivos (*.*)|*.*'}""",
                                  resultado="$d.FileName")
_ELEGIR_CARPETA = _DIALOGO.format(cuerpo="""$d = New-Object System.Windows.Forms.FolderBrowserDialog -Property @{
    Description = 'Elegir la carpeta de resultados (con myHRTF_project_L y myHRTF_project_R)'
    SelectedPath = $env:DIALOGO_INICIAL; ShowNewFolderButton = $false}""",
                                  resultado="$d.SelectedPath")


def elegir_con_dialogo(carpeta: bool, inicial: Path) -> Path | None:
    """Abre el diálogo y devuelve lo elegido, o None si se cancela (o no hay PowerShell)."""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-STA", "-Command",
                            _ELEGIR_CARPETA if carpeta else _ELEGIR_ARCHIVO],
                           capture_output=True, env=os.environ | {"DIALOGO_INICIAL": str(inicial)},
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except OSError:
        return None
    texto = r.stdout.decode("utf-8", errors="replace").strip()
    return Path(texto) if texto else None


def carpeta_existente(ruta: Path) -> Path:
    """La carpeta existente más cercana a una ruta (para abrir el diálogo ahí)."""
    for p in (ruta, *ruta.parents):
        if p.is_dir():
            return p
    return Path(config.RUTA_DATOS)


def comando_tarea(tarea: str) -> list[str]:
    """Cómo lanzar una tarea: en desarrollo, su script con el mismo Python; empaquetada,
    el propio .exe con el subcomando (no hay intérprete ni .py sueltos)."""
    if getattr(sys, "frozen", False):
        return [sys.executable, tarea]
    return [sys.executable, str(RAIZ / TAREAS[tarea])]


def ejecutar_tarea(tarea: str, argumentos: list[str], lineas: list[str]) -> int:
    """Corre la tarea y va dejando su salida en `lineas`. Devuelve el código."""
    entorno = os.environ | {"PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
    with subprocess.Popen([*comando_tarea(tarea), *argumentos], cwd=RAIZ, env=entorno,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, encoding="utf-8", errors="replace") as proceso:
        for linea in proceso.stdout:
            lineas.append(linea.rstrip())
    return proceso.returncode


# --- La app: estado + interfaz + manejadores ------------------------------------
class AppPipeline:
    """Una instancia por página abierta. NiceGUI no reejecuta el código en cada
    interacción, así que el estado vive en atributos normales."""

    def __init__(self) -> None:
        self.ruta: Path | None = None
        self.malla: trimesh.Trimesh | None = None
        self.vert: np.ndarray | None = None
        self.arbol: cKDTree | None = None
        self.stl_original: Path | None = None
        self.glb_original: Path | None = None   # con textura, si el escaneo la trae
        self.con_textura = True                 # qué versión del original se ve
        self.caja_original: tuple[np.ndarray, np.ndarray] | None = None
        self.puntos: list[dict] = []            # {"clave", "indice", "xyz"}
        self.T: np.ndarray | None = None        # alineación (con 3 puntos o más)
        self.aid: float = 0.0
        self.residuo: float = 0.0
        self.ruta_json: Path | None = None
        self.guardado = False                   # el JSON en disco corresponde a los puntos actuales
        self.limpiando = False
        self.gradando = False
        self.exportando = False
        self.simulando = False
        self.salida: Path | None = None
        self.informe: dict | None = None
        self.informe_gradado: dict | None = None
        self.cache_visor: dict[Path, tuple[Path, np.ndarray, np.ndarray]] = {}
        # lo que muestra el visor: M lleva coordenadas del escaneo original a las mostradas
        self.vista = {"original": True, "centro": np.zeros(3), "diag": 1.0, "M": np.eye(4)}
        self.escena: ui.scene | None = None
        # capas de la escena: (objeto, su luz, es_textura); solo una visible a la vez
        self.capas: list[tuple] = []
        self.ids_malla: set[str] = set()        # para ignorar impactos sobre los marcadores
        self.pose_camara: tuple | None = None   # última pose vista, para mover la luz solo si cambia
        self.marcadores: list = []
        self.construir_interfaz()

    # --- interfaz -----------------------------------------------------------
    def construir_interfaz(self) -> None:
        self.construir_encabezado()
        with ui.row().classes("w-full items-start gap-5 p-5"):
            self.construir_visor()
            with ui.column().classes("flex-1 gap-4").style("min-width: 420px"):
                self.construir_pasos()
        # Aviso legal que la GPL-3 pide en las interfaces interactivas (sección 5.d)
        ui.label("pipeline_hrtf © 2026 Jerónimo Cardona y Harold Cadavid. Software libre bajo la "
                 "GPL-3.0 o posterior, SIN NINGUNA GARANTÍA. Incluye MeshLab, Mesh2HRTF, NumCalc y otros "
                 "componentes con sus propias licencias: ver LICENSE.txt y AVISOS_DE_TERCEROS.md junto a "
                 "la app. El código fuente va en codigo_fuente_pipeline_hrtf.zip."
                 ).classes("text-xs tenue px-5 pb-5")
        ui.timer(0.25, self.seguir_camara)
        self.refrescar()

    def construir_encabezado(self) -> None:
        with ui.header().classes("items-center justify-between px-6 py-3 encabezado"):
            with ui.row().classes("items-center gap-3"):
                ui.icon("hearing", color="primary").classes("text-3xl")
                with ui.column().classes("gap-0"):
                    ui.label("Pipeline HRTF").classes("text-lg font-semibold")
                    ui.label("Del escaneo de la cabeza a la HRTF individual en SOFA").classes("text-xs tenue")
            with ui.row().classes("items-center gap-2"):
                for nombre, (bien, mensaje) in (("Gradado", ESTADO_BINARIO), ("Blender", ESTADO_BLENDER),
                                                ("NumCalc", ESTADO_NUMCALC)):
                    with ui.chip(nombre, icon="check_circle" if bien else "error",
                                 color="positive" if bien else "negative").props("outline dense"):
                        ui.tooltip(mensaje)

    def construir_visor(self) -> None:
        with ui.card().classes("tarjeta p-5 gap-3").style(f"width: {ANCHO_VISOR + 42}px"):
            self.instruccion = ui.label("Carga una malla para empezar.").classes("text-base font-medium instruccion")
            with ui.row().classes("items-center gap-2"):
                ui.label("Vista").classes("tenue text-sm w-16")
                with ui.button_group().props("flat"):
                    for nombre in VISTAS:
                        ui.button(nombre, on_click=lambda nombre=nombre: self.mover_camara(nombre)) \
                            .props("flat dense no-caps")
                self.nota_ejes = ui.label("").classes("tenue text-xs")
            with ui.row().classes("items-center gap-2"):
                ui.label("Mostrar").classes("tenue text-sm w-16")
                self.selector_mallas = ui.row().classes("gap-1")
                self.boton_textura = ui.button("Ver relieve", icon="texture", on_click=self.alternar_textura) \
                    .props("flat dense no-caps color=accent")
                self.boton_textura.set_visibility(False)
                self.etiqueta_vista = ui.label("").classes("tenue text-xs")
            self.contenedor_escena = ui.column()
            with self.contenedor_escena:
                with ui.element("div").classes("visor-vacio"):
                    ui.icon("view_in_ar").classes("text-6xl tenue")
                    ui.label("Aquí aparece la malla").classes("tenue")
            ui.label("Arrastra para girar  ·  rueda para acercar  ·  doble clic para marcar") \
                .classes("tenue text-xs")

    def construir_pasos(self) -> None:
        self.stepper = ui.stepper().props("vertical header-nav animated flat").classes("w-full tarjeta")
        with self.stepper:
            with ui.step("puntos", title="1 · Malla y puntos", icon="ads_click") as self.paso_puntos:
                with ui.row().classes("w-full items-end no-wrap gap-2"):
                    self.entrada_ruta = ui.input("Ruta de la malla (.obj, .ply o .stl)",
                                                 value=str(RUTA_POR_DEFECTO)) \
                        .props("dense outlined").classes("flex-grow")
                    ui.button("Elegir archivo…", icon="folder_open", on_click=self.elegir_malla) \
                        .props("outline no-caps")
                    self.boton_cargar = ui.button("Cargar", icon="upload_file", on_click=self.cargar) \
                        .props("unelevated no-caps")
                self.boton_puntos_guardados = ui.button("Usar los puntos guardados", icon="history",
                                                        on_click=self.usar_puntos_guardados) \
                    .props("flat no-caps")
                self.boton_puntos_guardados.set_visibility(False)
                self.info_malla = ui.label("Ninguna malla cargada.").classes("tenue text-sm")
                self.lista_puntos = ui.column().classes("w-full gap-1")
                self.resultados_alineacion = ui.column().classes("w-full gap-1")
                with ui.row().classes("gap-2 mt-2"):
                    self.boton_deshacer = ui.button("Deshacer", icon="undo", on_click=self.deshacer) \
                        .props("flat no-caps")
                    self.boton_reiniciar = ui.button("Empezar de nuevo", icon="restart_alt",
                                                     on_click=self.reiniciar).props("flat no-caps")
                    self.boton_guardar = ui.button("Guardar puntos", icon="save", on_click=self.guardar) \
                        .props("unelevated no-caps")

            with ui.step("limpieza", title="2–3 · Medidas, limpieza, escala y corte",
                         icon="cleaning_services") as self.paso_limpieza:
                with ui.expansion("Cómo medir", icon="help_outline").classes("w-full ayuda"):
                    ui.markdown(INSTRUCCIONES_MEDIDAS).classes("text-sm")

                def en_mm(rango):
                    lo, hi = rango
                    return {f"En milímetros (entre {lo} y {hi})": lambda v: v is None or lo <= v <= hi}
                with ui.grid(columns=2).classes("w-full gap-3"):
                    self.campo_oreja_izq = ui.number("Largo oreja izquierda", placeholder="p. ej. 63", suffix="mm",
                                                     validation=en_mm(RANGO_OREJA_MM)).props("dense outlined")
                    self.campo_oreja_der = ui.number("Largo oreja derecha", placeholder="p. ej. 63", suffix="mm",
                                                     validation=en_mm(RANGO_OREJA_MM)).props("dense outlined")
                    self.campo_circ = ui.number("Circunferencia de la cabeza", placeholder="p. ej. 570",
                                                suffix="mm", validation=en_mm(RANGO_CIRCUNFERENCIA_MM)) \
                        .props("dense outlined")
                    self.campo_bitrago = ui.number("Ancho bitragial (opcional)", placeholder="p. ej. 148",
                                                   suffix="mm", validation=en_mm(RANGO_BITRAGO_MM)) \
                        .props("dense outlined")
                with ui.row().classes("items-center gap-3"):
                    self.boton_limpiar = ui.button("Limpiar malla", icon="auto_fix_high", on_click=self.limpiar) \
                        .props("unelevated no-caps")
                    self.spinner = ui.spinner(size="md", color="primary")
                    self.spinner.set_visibility(False)
                    self.estado_limpieza = ui.label("").classes("tenue text-sm")
                with ui.expansion("Registro", icon="terminal").classes("w-full"):
                    self.registro = ui.log(max_lines=300).classes("w-full h-40 registro")
                self.resultado = ui.column().classes("w-full gap-1")

            with ui.step("gradado", title="4 · Gradado", icon="grid_on") as self.paso_gradado:
                self.aviso_herramienta(ESTADO_BINARIO, "el programa de gradado")
                ui.label("Una malla por oreja, fina en la oreja que se simula y gruesa lejos de ella. "
                         "Necesita la limpieza aprobada y en milímetros.").classes("tenue text-sm")
                with ui.row().classes("items-center gap-3"):
                    self.boton_gradar = ui.button("Gradar las dos orejas", icon="grid_on", on_click=self.gradar) \
                        .props("unelevated no-caps")
                    self.spinner_gradado = ui.spinner(size="md", color="primary")
                    self.spinner_gradado.set_visibility(False)
                    self.estado_gradado = ui.label("").classes("tenue text-sm")
                with ui.expansion("Registro", icon="terminal").classes("w-full"):
                    self.registro_gradado = ui.log(max_lines=100).classes("w-full h-32 registro")
                self.resultado_gradado = ui.column().classes("w-full gap-1")

            with ui.step("exportacion", title="5 · Exportación a Mesh2HRTF", icon="output") as self.paso_exportacion:
                self.aviso_herramienta(ESTADO_BLENDER, "Blender")
                ui.label("Un proyecto de Mesh2HRTF por oreja, listo para NumCalc. Un proyecto que ya tenga "
                         "resultados no se sobrescribe.").classes("tenue text-sm")
                with ui.row().classes("items-center gap-3"):
                    self.boton_exportar = ui.button("Exportar los dos proyectos", icon="output",
                                                    on_click=self.exportar).props("unelevated no-caps")
                    self.spinner_exportacion = ui.spinner(size="md", color="primary")
                    self.spinner_exportacion.set_visibility(False)
                    self.estado_exportacion = ui.label("").classes("tenue text-sm")
                with ui.expansion("Registro", icon="terminal").classes("w-full"):
                    self.registro_exportacion = ui.log(max_lines=100).classes("w-full h-32 registro")
                self.resultado_exportacion = ui.column().classes("w-full gap-1")

            with ui.step("simulacion", title="6–7 · Simulación y HRTF", icon="graphic_eq") as self.paso_simulacion:
                self.aviso_herramienta(ESTADO_NUMCALC, "NumCalc")
                ui.label("Simula las dos orejas (tarda horas), verifica que cada frecuencia convergió y "
                         f"deja la HRTF en {CARPETA_SOFA}. Si se corta, al relanzarla se conserva lo "
                         "ya simulado. Para retomar otra carpeta, elígela o escribe su ruta.").classes("tenue text-sm")
                with ui.row().classes("w-full items-end no-wrap gap-2"):
                    self.entrada_simulacion = ui.input("Carpeta de resultados (con los proyectos exportados)",
                                                       on_change=lambda _: self.refrescar()) \
                        .props("dense outlined").classes("flex-grow")
                    ui.button("Elegir carpeta…", icon="folder_open", on_click=self.elegir_carpeta_simulacion) \
                        .props("outline no-caps")
                with ui.row().classes("items-center gap-3"):
                    self.boton_simular = ui.button("Simular y armar la HRTF", icon="play_arrow",
                                                   on_click=self.simular).props("unelevated no-caps")
                    self.spinner_simulacion = ui.spinner(size="md", color="primary")
                    self.spinner_simulacion.set_visibility(False)
                    self.estado_simulacion = ui.label("").classes("tenue text-sm")
                with ui.expansion("Registro", icon="terminal").classes("w-full"):
                    self.registro_simulacion = ui.log(max_lines=500).classes("w-full h-48 registro")
                self.resultado_simulacion = ui.column().classes("w-full gap-1")

    def aviso_herramienta(self, estado: tuple[bool, str], nombre: str) -> None:
        bien, mensaje = estado
        if not bien:
            ui.label(f"No se encontró {nombre}: {mensaje}").classes("text-negative text-sm font-medium")

    def continuar(self, paso: str, texto: str) -> None:
        ui.button(texto, icon="arrow_downward", on_click=lambda: self.stepper.set_value(paso)) \
            .props("flat no-caps color=primary")

    def R_vista(self) -> np.ndarray:
        """Rotación de ejes anatómicos a ejes del visor. En el escaneo original sin
        alinear todavía no hay ejes anatómicos: se suponen los del archivo."""
        if not self.vista["original"]:
            return np.eye(3)                     # las salidas de la limpieza ya están alineadas
        if self.T is not None:
            return self.T[:3, :3].T
        return R_ARCHIVO_Y_ARRIBA if self.ruta.suffix.lower() == ".obj" else np.eye(3)

    def apuntar_luces(self, pos, adelante, arriba) -> None:
        """Pone la luz de cada capa en la cámara, mirando hacia donde mira ella."""
        d = np.asarray(adelante, dtype=float) / np.linalg.norm(adelante)
        y = np.asarray(arriba, dtype=float) - (np.dot(arriba, d)) * d
        if np.linalg.norm(y) < 1e-9:             # "arriba" paralelo a la mirada
            y = np.cross(d, [1.0, 0, 0]) if abs(d[0]) < 0.9 else np.cross(d, [0, 1.0, 0])
        y /= np.linalg.norm(y)
        R = np.c_[d, y, np.cross(d, y)].tolist()  # el foco de NiceGUI alumbra hacia su +x
        for _, luz, _ in self.capas:
            luz.move(*pos).rotate_R(R)

    async def seguir_camara(self) -> None:
        """Mueve la luz con la cámara cuando se gira o acerca a mano."""
        if self.escena is None or not self.capas:
            return
        try:
            cam = await self.escena.get_camera()
        except Exception:  # noqa: BLE001  (escena todavía sin montar en el navegador)
            return
        comp = lambda v, claves: [float(v[k] if k in v else v["_" + k]) for k in claves]
        pos = comp(cam["position"], "xyz")
        q = cam["quaternion"]
        q = comp(q, ("x", "y", "z", "w")) if isinstance(q, dict) else [float(c) for c in q]
        pose = tuple(np.round(pos + q, 9))
        if pose == self.pose_camara:
            return
        self.pose_camara = pose
        self.apuntar_luces(pos, rotar(q, [0, 0, -1.0]), rotar(q, [0, 1.0, 0]))

    def escala_vista(self) -> float:
        """Cuánto agranda el visor las coordenadas del escaneo (1, o el factor a mm)."""
        return float(np.cbrt(abs(np.linalg.det(self.vista["M"][:3, :3]))))

    def mover_camara(self, nombre: str, duracion: float = 0.5, de_cerca: bool = False) -> None:
        """Coloca la cámara mirando desde la vista indicada. Sin alinear, encuadra la
        malla entera; alineada, la cabeza, y con de_cerca (vistas laterales) la oreja."""
        if self.escena is None:
            return
        R = self.R_vista()
        direccion, arriba = (R @ np.array(v, dtype=float) for v in VISTAS[nombre])
        if self.T is None:
            centro, distancia = self.vista["centro"], 1.5 * self.vista["diag"]
        else:
            # de ejes anatómicos a coordenadas del visor: deshacer T y aplicar M
            a_vista = self.vista["M"] @ np.linalg.inv(self.T)
            if de_cerca and nombre in ("Izquierda", "Derecha"):
                lado = 1 if nombre == "Izquierda" else -1
                objetivo, distancia = [0, lado * self.aid / 2, 0], 1.0 * self.aid
            else:
                objetivo, distancia = [0, 0, 0.2 * self.aid], 2.5 * self.aid
            centro = aplicar_transformacion(a_vista, objetivo)
            distancia *= self.escala_vista()
        pos = centro + distancia * direccion
        self.escena.move_camera(
            x=pos[0], y=pos[1], z=pos[2],
            look_at_x=centro[0], look_at_y=centro[1], look_at_z=centro[2],
            up_x=arriba[0], up_y=arriba[1], up_z=arriba[2], duration=duracion)
        self.apuntar_luces(pos, centro - pos, arriba)

    def construir_escena(self, archivos: list[Path], vmin, vmax, vista_inicial: str) -> None:
        """Escena con una capa por archivo (la misma malla: .glb con textura o .stl en
        relieve), cada una con su luz; se ve la que toque según self.con_textura."""
        self.vista["centro"] = (np.asarray(vmin) + np.asarray(vmax)) / 2
        self.vista["diag"] = diag = float(np.linalg.norm(np.asarray(vmax) - np.asarray(vmin)))
        self.contenedor_escena.clear()
        camara = ui.scene.perspective_camera(fov=60, near=diag / 1000, far=diag * 50)
        with self.contenedor_escena:
            with ui.scene(width=ANCHO_VISOR, height=ALTO_VISOR, grid=False, camera=camara,
                          on_click=self.al_doble_clic, click_events=["dblclick"],
                          background_color=FONDO_VISOR).classes("rounded-lg") as escena:
                self.capas = []
                for archivo in archivos:
                    es_textura = archivo.suffix == ".glb"
                    url = f"/visor/{archivo.name}"
                    objeto = escena.gltf(url) if es_textura else escena.stl(url).material(COLOR_RELIEVE)
                    luz = escena.spot_light(intensity=LUZ_TEXTURA if es_textura else LUZ_RELIEVE,
                                            angle=1.2, decay=0)
                    self.capas.append((objeto, luz, es_textura))
        self.escena = escena
        self.ids_malla = {objeto.id for objeto, _, _ in self.capas}
        self.pose_camara = None
        self.aplicar_capa()
        self.marcadores = []
        for punto in self.puntos:
            self.dibujar_marcador(punto)
        self.mover_camara(vista_inicial, duracion=0, de_cerca=self.vista["original"])

    def aplicar_capa(self) -> None:
        """Deja visible (con su luz) solo la capa elegida; si hay una sola, esa."""
        hay_textura = any(t for _, _, t in self.capas) and len(self.capas) > 1
        for objeto, luz, es_textura in self.capas:
            visible = not hay_textura or es_textura == self.con_textura
            objeto.visible(visible)
            luz.visible(visible)

    def alternar_textura(self) -> None:
        self.con_textura = not self.con_textura
        self.boton_textura.set_text("Ver relieve" if self.con_textura else "Ver textura")
        self.aplicar_capa()

    def dibujar_marcador(self, punto: dict) -> None:
        color = next(c for k, _, c in LANDMARKS if k == punto["clave"])
        xyz = aplicar_transformacion(self.vista["M"], punto["xyz"])
        with self.escena:
            # ~2 mm: que no tape la entrada del canal al mirar de cerca
            radio = (0.012 * self.aid * self.escala_vista() if self.T is not None
                     else self.vista["diag"] / 400)
            esfera = self.escena.sphere(radius=radio).material(color).move(*xyz)
        self.marcadores.append(esfera)

    def mostrar_original(self) -> None:
        if self.stl_original is None:
            return
        self.vista.update(original=True, M=np.eye(4))
        self.etiqueta_vista.set_text("Mostrando: escaneo original")
        self.boton_textura.set_visibility(self.glb_original is not None)
        archivos = [a for a in (self.glb_original, self.stl_original) if a is not None]
        inicial = VISTA_PARA_PUNTO.get(len(self.puntos), "Frente")
        self.construir_escena(archivos, *self.caja_original, inicial)

    async def mostrar_salida(self, archivo: str, etiqueta: str) -> None:
        ruta = self.salida / archivo
        if ruta not in self.cache_visor:
            self.etiqueta_vista.set_text(f"Cargando {etiqueta}...")
            self.cache_visor[ruta] = await run.io_bound(preparar_resultado, ruta)
        M = self.T.copy()
        if archivo in MALLAS_EN_MM:
            M = np.diag([*[self.informe["escala"]["factor"]] * 3, 1.0]) @ M
        self.vista.update(original=False, M=M)
        self.etiqueta_vista.set_text(f"Mostrando: {etiqueta}")
        self.boton_textura.set_visibility(False)   # las mallas limpias no tienen textura
        stl, vmin, vmax = self.cache_visor[ruta]
        self.construir_escena([stl], vmin, vmax, "Izquierda")

    def refrescar_selector(self) -> None:
        self.selector_mallas.clear()
        with self.selector_mallas:
            ui.button("Original", on_click=self.mostrar_original).props("flat dense no-caps")
            if self.salida is not None:
                for archivo, etiqueta in MALLAS_LIMPIEZA:
                    if (self.salida / archivo).exists():
                        ui.button(etiqueta, on_click=lambda a=archivo, e=etiqueta: self.mostrar_salida(a, e)) \
                            .props("flat dense no-caps")

    def refrescar(self) -> None:
        """Actualiza instrucción, lista de puntos, alineación y botones según el estado."""
        n = len(self.puntos)
        if self.malla is None:
            self.instruccion.set_text("Carga una malla para empezar.")
        elif n < N_OBLIGATORIOS:
            self.instruccion.set_text(
                f"Punto {n + 1} de {N_OBLIGATORIOS}: doble clic sobre {LANDMARKS[n][1]}.")
        elif n < len(LANDMARKS):
            self.instruccion.set_text(
                ("Siete puntos marcados: ya se puede guardar. " if n == N_OBLIGATORIOS else "")
                + f"Opcional, solo si se midió con pie de rey: punto {n + 1} de {len(LANDMARKS)}, "
                f"doble clic sobre {LANDMARKS[n][1]}.")
        else:
            self.instruccion.set_text("Todos los puntos marcados. Revisa los resultados y guarda.")

        self.lista_puntos.clear()
        with self.lista_puntos:
            for i, p in enumerate(self.puntos, 1):
                texto, color = next((t, c) for k, t, c in LANDMARKS if k == p["clave"])
                with ui.row().classes("items-center gap-2 no-wrap"):
                    ui.element("span").classes("punto").style(f"background: {color}")
                    ui.label(f"{i}. {texto[0].upper()}{texto[1:]}").classes("text-sm")
                    ui.label(f"vértice {p['indice']}").classes("tenue text-xs")

        self.resultados_alineacion.clear()
        self.T = None
        if n >= N_ALINEACION:
            xyz = [p["xyz"] for p in self.puntos[:N_ALINEACION]]
            self.T, self.aid = matriz_alineacion(*xyz)
            self.residuo = residuo_alineacion(self.T, *xyz, self.aid)
            vmin, vmax = self.caja_original
            d = vmax - vmin
            with self.resultados_alineacion:
                ui.label("Medidas en la malla (unidades de KIRI)").classes("tenue text-xs mt-2")
                puntos = {p["clave"]: p["xyz"] for p in self.puntos}
                avisos = []
                with ui.row().classes("gap-2"):
                    dato(f"AID {self.aid:.4f}")
                    dato(f"Caja {d[0]:.3f} × {d[1]:.3f} × {d[2]:.3f}")
                    dato(f"Residuo {self.residuo:.1e}")
                    for lado, (arriba, abajo) in PUNTOS_LARGO.items():
                        if arriba in puntos and abajo in puntos:
                            largo = float(np.linalg.norm(puntos[arriba] - puntos[abajo]))
                            dato(f"Oreja {lado} {largo:.4f} ({largo / self.aid:.3f} AID)")
                            z_arriba, z_abajo = aplicar_transformacion(self.T, [puntos[arriba], puntos[abajo]])[:, 2]
                            if z_arriba <= z_abajo:
                                avisos.append(f"En la oreja {lado} el punto ALTO quedó por debajo del BAJO. "
                                              "¿Se marcaron al revés o lejos de los extremos? Deshacer y "
                                              "volver a marcar.")
                    if TRAGO_IZQ in puntos and TRAGO_DER in puntos:
                        ancho = float(np.linalg.norm(puntos[TRAGO_IZQ] - puntos[TRAGO_DER]))
                        dato(f"Bitragial {ancho:.4f} ({ancho / self.aid:.3f} AID)")
                for aviso in avisos:
                    ui.label(f"⚠ {aviso}").classes("text-warning text-sm")
                if self.residuo > RESIDUO_MAX:
                    ui.label(f"✖ Residuo mayor que {RESIDUO_MAX:.0e}: hay un fallo en la matriz. "
                             "No se puede guardar.").classes("text-negative text-sm font-medium")

        self.nota_ejes.set_text("(ejes anatómicos)" if self.T is not None else
                                "(ejes supuestos del archivo hasta marcar los 3 primeros puntos)")
        # los tragos van juntos: o ninguno o los dos
        completo = n in (N_OBLIGATORIOS, len(LANDMARKS)) and self.residuo <= RESIDUO_MAX
        ocupado = self.tarea_en_curso() is not None
        self.boton_guardar.set_enabled(completo and not ocupado)
        self.boton_limpiar.set_enabled(self.guardado and not ocupado)
        self.boton_cargar.set_enabled(not ocupado)
        se_puede_gradar = (self.salida is not None and (self.salida / MALLA_MM).exists()
                           and self.informe["control_calidad"]["aprobado"] and ESTADO_BINARIO[0])
        self.boton_gradar.set_enabled(se_puede_gradar and not ocupado)
        se_puede_exportar = (self.informe_gradado is not None and self.informe_gradado["aprobado"]
                             and ESTADO_BLENDER[0])
        self.boton_exportar.set_enabled(se_puede_exportar and not ocupado)
        self.boton_simular.set_enabled(ESTADO_NUMCALC[0] and self.exportacion_aprobada() and not ocupado)
        self.entrada_simulacion.set_enabled(not ocupado)
        # pasos completados en el stepper
        for paso, hecho in ((self.paso_puntos, self.guardado),
                            (self.paso_limpieza, bool(self.informe and self.informe["control_calidad"]["aprobado"])),
                            (self.paso_gradado, bool(self.informe_gradado and self.informe_gradado["aprobado"])),
                            (self.paso_exportacion, self.exportacion_aprobada())):
            if hecho:
                paso.props("done")
            else:
                paso.props(remove="done")

    def carpeta_simulacion(self) -> Path | None:
        texto = (self.entrada_simulacion.value or "").strip().strip('"')
        return Path(texto) if texto else None

    def exportacion_aprobada(self) -> bool:
        """Se mira en disco: la carpeta puede ser de una sesión anterior."""
        carpeta = self.carpeta_simulacion()
        if carpeta is None or not (carpeta / "informe_exportacion.json").is_file():
            return False
        try:
            informe = json.loads((carpeta / "informe_exportacion.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        return bool(informe.get("aprobado"))

    def invalidar(self) -> None:
        """Los puntos cambiaron: lo guardado y la limpieza ya no les corresponden."""
        self.guardado = False
        self.salida, self.informe, self.informe_gradado = None, None, None
        self.resultado.clear()
        self.limpiar_exportacion()
        self.resultado_gradado.clear()
        self.registro_gradado.clear()
        self.estado_gradado.set_text("")
        for stl, _, _ in self.cache_visor.values():
            stl.unlink(missing_ok=True)
        self.cache_visor.clear()
        self.refrescar_selector()

    def limpiar_exportacion(self) -> None:
        """La exportación que se ve ya no corresponde (otros puntos, otra limpieza u otro gradado)."""
        self.resultado_exportacion.clear()
        self.registro_exportacion.clear()
        self.estado_exportacion.set_text("")

    def tarea_en_curso(self) -> str | None:
        for en_curso, nombre in ((self.limpiando, "la limpieza"), (self.gradando, "el gradado"),
                                 (self.exportando, "la exportación"), (self.simulando, "la simulación")):
            if en_curso:
                return nombre
        return None

    def puede_editar(self) -> bool:
        tarea = self.tarea_en_curso()
        if tarea:
            ui.notify(f"Espera a que termine {tarea}.", type="warning")
        return tarea is None

    # --- manejadores: puntos --------------------------------------------------
    def al_doble_clic(self, e: events.SceneClickEventArguments) -> None:
        if self.malla is None or not self.puede_editar():
            return
        if not self.vista["original"]:
            ui.notify("Para marcar puntos, muestra el escaneo original.", type="warning")
            return
        if len(self.puntos) >= len(LANDMARKS):
            ui.notify("Ya están todos los puntos. Usa Deshacer o Empezar de nuevo.", type="warning")
            return
        impactos = [h for h in e.hits if h.object_id in self.ids_malla]
        if not impactos:
            ui.notify("Doble clic fuera de la malla.", type="warning")
            return
        h = impactos[0]                                 # el más cercano a la cámara
        _, indice = self.arbol.query([h.x, h.y, h.z])   # vértice más cercano de la malla completa
        punto = {"clave": LANDMARKS[len(self.puntos)][0],
                 "indice": int(indice), "xyz": self.vert[indice].copy()}
        self.puntos.append(punto)
        self.dibujar_marcador(punto)
        self.invalidar()
        self.refrescar()
        if len(self.puntos) in VISTA_PARA_PUNTO:
            self.mover_camara(VISTA_PARA_PUNTO[len(self.puntos)], de_cerca=True)

    def deshacer(self) -> None:
        if not self.puede_editar():
            return
        if self.puntos:
            self.puntos.pop()
            if self.vista["original"] and self.marcadores:
                self.marcadores.pop().delete()
        self.invalidar()
        self.refrescar()

    def reiniciar(self) -> None:
        if not self.puede_editar():
            return
        self.puntos.clear()
        for m in self.marcadores:
            m.delete()
        self.marcadores.clear()
        self.invalidar()
        self.refrescar()

    def usar_puntos_guardados(self) -> None:
        """Retoma los puntos del JSON de landmarks, en el orden de LANDMARKS, hasta el
        primero que falte (los JSON antiguos solo traen los tres de la alineación)."""
        if not self.puede_editar():
            return
        guardados = json.loads(self.ruta_json.read_text(encoding="utf-8"))["puntos"]
        self.reiniciar()
        for clave, _, _ in LANDMARKS:
            if clave not in guardados:
                break
            _, indice = self.arbol.query(guardados[clave]["xyz"])
            self.puntos.append({"clave": clave, "indice": int(indice), "xyz": self.vert[indice].copy()})
        # el JSON ya es el de estos puntos (con o sin los tragos opcionales)
        self.guardado = len(self.puntos) == len(guardados) and len(self.puntos) in (N_OBLIGATORIOS, len(LANDMARKS))
        self.refrescar()
        self.mostrar_original()
        ui.notify(f"{len(self.puntos)} puntos recuperados.")

    # --- manejadores: carga y guardado -------------------------------------------
    async def elegir_malla(self) -> None:
        """Diálogo de Windows para la malla; al elegirla se carga."""
        if not self.puede_editar():
            return
        actual = Path(self.entrada_ruta.value.strip().strip('"') or config.RUTA_DATOS)
        inicial = carpeta_existente(actual if actual.suffix == "" else actual.parent)
        ruta = await run.io_bound(elegir_con_dialogo, False, inicial)
        if ruta is not None:
            self.entrada_ruta.value = str(ruta)
            await self.cargar()

    async def elegir_carpeta_simulacion(self) -> None:
        """Diálogo de Windows para la carpeta de resultados que se va a simular."""
        actual = self.carpeta_simulacion() or Path(config.RUTA_DATOS) / "salidas"
        ruta = await run.io_bound(elegir_con_dialogo, True, carpeta_existente(actual))
        if ruta is not None:
            self.entrada_simulacion.value = str(ruta)          # dispara refrescar()

    async def cargar(self) -> None:
        if not self.puede_editar():
            return
        ruta = Path(self.entrada_ruta.value.strip().strip('"'))
        if not ruta.is_file():
            ui.notify(f"No existe el archivo: {ruta}", type="negative")
            return
        if ruta.suffix.lower() not in EXTENSIONES:
            ui.notify("La extensión debe ser .obj, .ply o .stl", type="negative")
            return
        self.boton_cargar.disable()
        self.info_malla.set_text("Cargando malla...")
        try:
            malla = await run.io_bound(cargar_malla, ruta)
            stl = await run.io_bound(exportar_para_visor, ruta, malla)
            glb = await run.io_bound(exportar_textura, malla)
        except Exception as ex:  # noqa: BLE001
            self.info_malla.set_text(f"No se pudo cargar: {ex}")
            self.boton_cargar.enable()
            return
        for anterior in (self.stl_original, self.glb_original):
            if anterior is not None:
                anterior.unlink(missing_ok=True)

        self.ruta, self.malla, self.stl_original, self.glb_original = ruta, malla, stl, glb
        self.con_textura = glb is not None
        self.boton_textura.set_text("Ver relieve")
        self.vert = np.asarray(malla.vertices, dtype=float)
        self.arbol = cKDTree(self.vert)
        self.caja_original = (self.vert.min(0), self.vert.max(0))
        self.puntos, self.marcadores = [], []
        self.ruta_json = ruta.with_name(f"{ruta.stem}_landmarks.json")
        self.invalidar()
        self.registro.clear()
        self.estado_limpieza.set_text("")

        d = self.caja_original[1] - self.caja_original[0]
        self.info_malla.set_text(f"{ruta.name}: {len(self.vert):,} vértices, "
                                 f"{len(malla.faces):,} caras, caja envolvente "
                                 f"{d[0]:.3f} x {d[1]:.3f} x {d[2]:.3f}")
        if self.ruta_json.exists():
            n = len(json.loads(self.ruta_json.read_text(encoding="utf-8"))["puntos"])
            self.boton_puntos_guardados.set_text(f"Usar los puntos guardados ({n})")
        self.boton_puntos_guardados.set_visibility(self.ruta_json.exists())
        self.refrescar()
        self.mostrar_original()

    async def guardar(self) -> None:
        ruta = self.ruta
        salida_malla = ruta.with_name(f"{ruta.stem}_alineada.ply")
        T = self.T

        def exportar() -> None:
            alineada = self.malla.copy()
            alineada.apply_transform(T)
            alineada.export(salida_malla)

        self.boton_guardar.disable()
        try:
            await run.io_bound(exportar)
            datos = {
                "malla_original": str(ruta),
                "malla_alineada": str(salida_malla),
                "puntos": {p["clave"]: {"indice": p["indice"], "xyz": p["xyz"].tolist()}
                           for p in self.puntos},
                "aid": self.aid,
                "residuo": self.residuo,
                "matriz": T.tolist(),
                "sistema": "+x adelante, +y izquierda del sujeto, +z arriba, "
                           "origen en el punto medio interaural",
            }
            self.ruta_json.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as ex:  # noqa: BLE001
            ui.notify(f"Error al guardar: {ex}", type="negative")
            self.refrescar()
            return
        self.guardado = True
        self.boton_puntos_guardados.set_text(f"Usar los puntos guardados ({len(self.puntos)})")
        self.boton_puntos_guardados.set_visibility(True)
        ui.notify(f"Guardado: {salida_malla.name} y {self.ruta_json.name}", type="positive")
        self.refrescar()
        self.stepper.set_value("limpieza")

    # --- manejadores: limpieza y gradado ----------------------------------------
    async def correr_tarea(self, tarea: str, argumentos: list[str], registro: ui.log) -> int:
        """Corre la tarea en un proceso aparte mostrando su salida en `registro`."""
        registro.clear()
        lineas: list[str] = []
        enviadas = 0

        def volcar() -> None:
            nonlocal enviadas
            for linea in lineas[enviadas:]:
                registro.push(linea)
            enviadas = len(lineas)

        temporizador = ui.timer(0.3, volcar)
        codigo = await run.io_bound(ejecutar_tarea, tarea, argumentos, lineas)
        volcar()
        temporizador.cancel()
        return codigo

    async def limpiar(self) -> None:
        salida = carpeta_salida(self.ruta)
        argumentos = [str(self.ruta), "--landmarks", str(self.ruta_json), "--salida", str(salida)]
        for opcion, campo, (lo, hi) in (("--oreja-izq-mm", self.campo_oreja_izq, RANGO_OREJA_MM),
                                        ("--oreja-der-mm", self.campo_oreja_der, RANGO_OREJA_MM),
                                        ("--circunferencia-mm", self.campo_circ, RANGO_CIRCUNFERENCIA_MM),
                                        ("--bitrago-mm", self.campo_bitrago, RANGO_BITRAGO_MM)):
            if campo.value:
                if not lo <= campo.value <= hi:
                    ui.notify(f"{campo.props['label']}: {campo.value} no puede estar en milímetros. "
                              "¿Está en metros o en cm? Escribe mm (63, no 0.063).", type="negative")
                    return
                argumentos += [opcion, str(campo.value)]
        if self.campo_bitrago.value and len(self.puntos) < len(LANDMARKS):
            ui.notify("Para usar el ancho bitragial hay que marcar los dos tragos (puntos 8 y 9) y "
                      "guardar los puntos.", type="negative")
            return

        self.limpiando = True
        self.invalidar()
        self.guardado = True                    # invalidar() lo apaga, pero los puntos no cambiaron
        self.refrescar()
        self.spinner.set_visibility(True)
        self.estado_limpieza.set_text("Limpiando (tarda unos minutos)...")
        codigo = await self.correr_tarea("limpiar", argumentos, self.registro)
        self.limpiando = False
        self.spinner.set_visibility(False)

        # El código 1 significa "rechazada" pero también "excepción"; solo el informe con
        # control de calidad (lo último que escribe la limpieza) dice que terminó bien.
        ruta_informe = salida / "informe_limpieza.json"
        informe = json.loads(ruta_informe.read_text(encoding="utf-8")) if ruta_informe.exists() else {}
        if codigo not in (0, 1) or "control_calidad" not in informe:
            self.estado_limpieza.set_text("La limpieza falló: ver el registro.")
            self.refrescar()
            return
        self.estado_limpieza.set_text(f"Terminada. Archivos en {ruta_corta(salida)}")
        self.salida, self.informe = salida, informe
        self.mostrar_resultado()
        self.refrescar_selector()
        self.refrescar()
        await self.mostrar_salida("3_suavizada.ply", "3 · suavizada")

    async def gradar(self) -> None:
        self.gradando = True
        self.informe_gradado = None
        self.resultado_gradado.clear()
        self.limpiar_exportacion()
        self.refrescar()
        self.spinner_gradado.set_visibility(True)
        self.estado_gradado.set_text("Gradando los dos lados...")
        codigo = await self.correr_tarea("gradar", [str(self.salida)], self.registro_gradado)
        self.gradando = False
        self.spinner_gradado.set_visibility(False)
        ruta_informe = self.salida / "informe_gradado.json"
        informe = json.loads(ruta_informe.read_text(encoding="utf-8")) if ruta_informe.exists() else {}
        if codigo not in (0, 1) or "aprobado" not in informe:
            self.estado_gradado.set_text("El gradado falló: ver el registro.")
            self.refrescar()
            return
        self.informe_gradado = informe
        self.estado_gradado.set_text(f"Terminado. Archivos en {ruta_corta(self.salida)}")
        with self.resultado_gradado:
            veredicto("Gradado aprobado" if informe["aprobado"] else "Gradado fallido", informe["aprobado"])
            fallas_y_avisos(informe["fallas"], informe["avisos"])
            with ui.row().classes("gap-2"):
                for lado, r in informe["lados"].items():
                    if "caras" in r:
                        dato(f"{'Izquierda' if lado == 'left' else 'Derecha'}: {r['caras']:,} caras, {r['segundos']} s")
            if informe["aprobado"]:
                self.continuar("exportacion", "Continuar con la exportación")
        for archivo in SALIDAS_GRADADO.values():   # el visor puede tener una versión anterior
            anterior = self.cache_visor.pop(self.salida / archivo, None)
            if anterior is not None:
                anterior[0].unlink(missing_ok=True)
        self.refrescar_selector()
        self.refrescar()
        if informe["aprobado"]:
            await self.mostrar_salida(SALIDAS_GRADADO["left"], "Graduada izquierda")

    async def exportar(self) -> None:
        self.exportando = True
        self.limpiar_exportacion()
        self.refrescar()
        self.spinner_exportacion.set_visibility(True)
        self.estado_exportacion.set_text("Exportando con Blender...")
        codigo = await self.correr_tarea("exportar", [str(self.salida)], self.registro_exportacion)
        self.exportando = False
        self.spinner_exportacion.set_visibility(False)
        ruta_informe = self.salida / "informe_exportacion.json"
        informe = json.loads(ruta_informe.read_text(encoding="utf-8")) if ruta_informe.exists() else {}
        if codigo not in (0, 1) or "aprobado" not in informe:
            self.estado_exportacion.set_text("La exportación falló: ver el registro.")
            self.refrescar()
            return
        self.estado_exportacion.set_text(f"Terminada. Proyectos en {ruta_corta(self.salida)}")
        if informe["aprobado"]:
            self.entrada_simulacion.set_value(str(self.salida))
        with self.resultado_exportacion:
            veredicto("Exportación aprobada" if informe["aprobado"] else "Exportación fallida", informe["aprobado"])
            fallas_y_avisos(informe["fallas"], informe["avisos"])
            for r in informe["lados"].values():
                if "fuente_distancia_canal_mm" in r:
                    dato(f"{r['proyecto']}: {r['nodos']:,} nodos, {r['elementos']:,} elementos, fuente a "
                         f"{r['fuente_distancia_canal_mm']} mm del canal marcado, {r['frecuencias']} frecuencias")
            if informe["aprobado"]:
                self.continuar("simulacion", "Continuar con la simulación")
        self.refrescar()

    async def simular(self) -> None:
        carpeta = self.carpeta_simulacion()
        self.simulando = True
        self.resultado_simulacion.clear()
        self.refrescar()
        self.spinner_simulacion.set_visibility(True)
        self.estado_simulacion.set_text("Simulando con NumCalc (tarda horas)...")
        codigo = await self.correr_tarea("simular", [str(carpeta)], self.registro_simulacion)
        self.simulando = False
        self.spinner_simulacion.set_visibility(False)
        ruta_informe = carpeta / "informe_simulacion.json"
        informe = json.loads(ruta_informe.read_text(encoding="utf-8")) if ruta_informe.exists() else {}
        if codigo not in (0, 1) or "aprobado" not in informe:
            self.estado_simulacion.set_text("La simulación falló o se cortó: ver el registro. "
                                            "Se puede volver a lanzar.")
            self.refrescar()
            return
        self.estado_simulacion.set_text(f"Terminada. Resultados en {ruta_corta(carpeta)}")
        with self.resultado_simulacion:
            if informe["aprobado"]:
                veredicto("HRTF lista", True)
                ui.label(f"Archivos en {ruta_corta(carpeta / informe['sofa']['carpeta'])}: "
                         + ", ".join(informe["sofa"]["sha256"])).classes("text-sm")
                if informe.get("dtf"):
                    ui.label("Para escuchar con programas que cargan SOFA (timbre neutro): "
                             + ", ".join(informe["dtf"]) + ". Para métricas, usar los SOFA sin ecualizar")
                if informe.get("hesuvi", {}).get("archivos"):
                    ui.label("Para escuchar en Windows con HeSuVi (7.1 virtual con audífonos): "
                             + ", ".join(informe["hesuvi"]["archivos"])
                             + ". Recomendado: HeSuVi_DTF_48000.wav")
            else:
                veredicto("Simulación fallida", False)
            fallas_y_avisos(informe["fallas"], informe["avisos"])
            for r in informe["lados"].values():
                c = r["convergencia"]
                dato(f"{r['proyecto']}: {c['convergieron']}/{c['pasos']} frecuencias convergieron "
                         f"({r['de_hz']:.0f}–{r['a_hz']:.0f} Hz), {r['horas_suma_por_frecuencia']} h de cálculo"
                         + (f", RAM pico {r['pico_ram_suma_numcalc_gb']} GB" if "pico_ram_suma_numcalc_gb" in r else ""))
        self.refrescar()

    def mostrar_resultado(self) -> None:
        inf, cc = self.informe, self.informe["control_calidad"]
        self.resultado.clear()
        with self.resultado:
            veredicto("Malla aprobada" if cc["aprobado"] else "Malla rechazada: hay que repetir el escaneo",
                      cc["aprobado"])
            fallas_y_avisos(cc["fallas"], cc["avisos"])

            esc = inf["escala"]
            ui.label("Escala").classes("text-base font-semibold mt-3")
            if esc["factor"]:
                ui.label(f"Fuente: {esc['fuente']}  ·  factor {esc['factor']:.3f} mm por unidad").classes("text-sm")
                with ui.row().classes("gap-2"):
                    dato(f"AID {esc['aid_mm']} mm")
                    dato(f"Circunferencia {esc['circunferencia_mm']} mm")
                    for lado, mm in esc.get("largo_oreja_mm", {}).items():
                        dato(f"Oreja {lado} {mm} mm")
                    if "bitrago_mm" in esc:
                        dato(f"Bitragial {esc['bitrago_mm']} mm")
                for fuente, dif in esc.get("discrepancias", {}).items():
                    ui.label(f"{fuente.replace('_', ' ').capitalize()}: se aparta un {100 * dif:.1f} % "
                             "de la escala usada").classes("tenue text-sm")
            else:
                ui.label("Sin escala real: no se dio ninguna medida.").classes("text-sm")

            final = inf.get("suavizada") or inf["cerrada_poisson"]
            ui.label("Malla final").classes("text-base font-semibold mt-3")
            with ui.row().classes("gap-2"):
                dato(f"{final['faces_number']:,} caras")
                dato(f"{final['connected_components_number']} pieza(s)")
                dato(f"genus {final['genus']}")
                dato(f"{final['boundary_edges']} aristas de borde")
                dato(f"{final['caras_autointersecadas']} autointersecciones")
            if cc["aprobado"]:
                self.continuar("gradado", "Continuar con el gradado")


def principal() -> None:
    """Función raíz: NiceGUI la llama una vez por cada página que se abre."""
    ui.dark_mode(True)
    ui.colors(**COLORES)
    ui.add_css(CSS)
    AppPipeline()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    if len(sys.argv) > 1 and sys.argv[1] in TAREAS:
        # la app empaquetada se relanza a sí misma para cada tarea (ver comando_tarea)
        import exportar_malla
        import gradar_malla
        import limpiar_malla
        import exportar_hesuvi
        import simular_malla
        {"limpiar": limpiar_malla.principal, "gradar": gradar_malla.principal,
         "exportar": exportar_malla.principal, "simular": simular_malla.principal,
         "hesuvi": exportar_hesuvi.principal}[sys.argv[1]](sys.argv[2:])
    else:
        # las carpetas de datos existen desde el primer arranque (en un PC nuevo no hay nada)
        for sub in ("entrada", "salidas"):
            (Path(config.RUTA_DATOS) / sub).mkdir(parents=True, exist_ok=True)
        ESTADO_BINARIO = comprobar_binario()
        print(("Gradado: " if ESTADO_BINARIO[0] else "AVISO, el gradado no va a funcionar: ")
              + ESTADO_BINARIO[1])
        ESTADO_BLENDER = comprobar_blender()
        print(("Exportación: " if ESTADO_BLENDER[0] else "AVISO, la exportación no va a funcionar: ")
              + ESTADO_BLENDER[1])
        ESTADO_NUMCALC = comprobar_numcalc()
        print(("Simulación: " if ESTADO_NUMCALC[0] else "AVISO, la simulación no va a funcionar: ")
              + ESTADO_NUMCALC[1])
        ui.run(root=principal, title="Pipeline HRTF", port=8080, reload=False,
               show=True, show_welcome_message=False)
