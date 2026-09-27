"""App del pipeline HRTF (NiceGUI): marcar puntos, alinear, medir y limpiar.

1. Malla y puntos. Se carga el escaneo y se marcan con DOBLE CLIC siete puntos: la
   entrada de los dos canales auditivos y la punta de la nariz (definen la alineación,
   ver malla/alineacion.py) y lo más alto y lo más bajo de cada oreja (su largo sirve
   para la escala). Se guardan <nombre>_alineada.ply y <nombre>_landmarks.json junto
   a la malla.
2. Medidas de la persona (opcionales): largo de cada oreja y circunferencia de la
   cabeza. La limpieza corre limpiar_malla.py en un proceso aparte, con su salida en
   pantalla, así que da lo mismo que desde la terminal.
3. Resultado: veredicto del control de calidad, escala, y las mallas de cada paso en
   el mismo visor.

Ejecutar:  .venv/Scripts/python.exe app.py   ->  http://localhost:8080
"""
import json
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
from malla.oreja import PUNTOS_LARGO

RAIZ = Path(__file__).resolve().parent
LIMPIAR_MALLA = RAIZ / "limpiar_malla.py"
RUTA_POR_DEFECTO = Path(config.RUTA_DATOS) / "entrada" / "3Dmesh_orig.stl"
EXTENSIONES = {".obj", ".ply", ".stl"}
RESIDUO_MAX = 1e-6
# Límites SOLO para detectar unidades equivocadas (0.063 en vez de 63): fuera de esto no
# puede ser una oreja o una cabeza en milímetros. No juzgan si la medida es buena.
RANGO_OREJA_MM = (20, 120)
RANGO_CIRCUNFERENCIA_MM = (300, 900)

# Los siete puntos, en el orden en que se marcan: (clave, texto, color del marcador).
# Los tres primeros definen la alineación; los de las orejas, su largo (malla/oreja.py).
HELIX_IZQ, LOBULO_IZQ = PUNTOS_LARGO["izq"]
HELIX_DER, LOBULO_DER = PUNTOS_LARGO["der"]
LANDMARKS = [
    ("oreja_izquierda", "la entrada del canal auditivo IZQUIERDO", "#e53935"),
    ("oreja_derecha", "la entrada del canal auditivo DERECHO", "#43a047"),
    ("nariz", "la punta de la NARIZ", "#1e88e5"),
    (HELIX_IZQ, "el punto más ALTO de la oreja IZQUIERDA (borde del hélix)", "#fb8c00"),
    (LOBULO_IZQ, "el punto más BAJO de la oreja IZQUIERDA (lóbulo)", "#fb8c00"),
    (HELIX_DER, "el punto más ALTO de la oreja DERECHA (borde del hélix)", "#8e24aa"),
    (LOBULO_DER, "el punto más BAJO de la oreja DERECHA (lóbulo)", "#8e24aa"),
]
N_ALINEACION = 3
# La cámara va sola a donde está el punto que toca marcar (clave: cuántos hay marcados).
# Antes de alinear es una suposición por los ejes del archivo; después, exacta.
VISTA_PARA_PUNTO = {0: "Izquierda", 1: "Derecha", 2: "Frente", 3: "Izquierda", 5: "Derecha"}

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
    ("malla_final_mm.ply", "Final en mm"),
]

INSTRUCCIONES_MEDIDAS = """
**Todas son opcionales.** Sin ninguna, la malla queda sin escala real (en las unidades
arbitrarias de KIRI). Con varias, se usa la mediana y se muestra cuánto se aparta cada una.

**Largo de cada oreja.** Con una regla, en línea recta desde el punto más alto del borde
de la oreja (hélix) hasta el punto más bajo del lóbulo, sin aplastarla. Son los mismos dos
puntos que se marcan en la malla. Mejor si lo mide otra persona.

**Circunferencia de la cabeza.** Con cinta métrica y **el mismo gorro del escaneo puesto**.
La cinta pasa justo por encima de las cejas y de las orejas, y rodea la cabeza paralela a la
línea que va de la oreja a la punta de la nariz (vista de perfil, la cinta y esa línea no se
acercan ni se alejan). Ajustada, sin apretar: cada milímetro de holgura cambia la escala ~1 %.

*Protocolo provisional: falta validarlo con medidas reales (ver malla/LIMPIEZA.md).*
"""

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


def ejecutar_limpieza(argumentos: list[str], lineas: list[str]) -> int:
    """Corre limpiar_malla.py y va dejando su salida en `lineas`. Devuelve el código."""
    entorno = os.environ | {"PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
    with subprocess.Popen([sys.executable, str(LIMPIAR_MALLA), *argumentos], cwd=RAIZ, env=entorno,
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
        self.salida: Path | None = None
        self.informe: dict | None = None
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
        ui.label("Pipeline HRTF: alineación, medidas y limpieza").classes("text-2xl")

        ui.label("1. Malla y puntos").classes("text-xl mt-4")
        with ui.row().classes("w-full items-end"):
            self.entrada_ruta = ui.input("Ruta de la malla (.obj, .ply o .stl)",
                                         value=str(RUTA_POR_DEFECTO)).classes("flex-grow")
            self.boton_cargar = ui.button("Cargar", on_click=self.cargar)
        self.boton_puntos_guardados = ui.button("Usar los puntos guardados",
                                                on_click=self.usar_puntos_guardados)
        self.boton_puntos_guardados.set_visibility(False)

        self.info_malla = ui.label("Ninguna malla cargada.")
        self.instruccion = ui.label("").classes("text-lg font-bold")

        with ui.row().classes("items-center"):
            ui.label("Vista:")
            for nombre in VISTAS:
                ui.button(nombre, on_click=lambda nombre=nombre: self.mover_camara(nombre))
            self.nota_ejes = ui.label("")
        with ui.row().classes("items-center"):
            ui.label("Mostrar:")
            self.selector_mallas = ui.row()
            self.boton_textura = ui.button("Ver relieve", on_click=self.alternar_textura)
            self.boton_textura.set_visibility(False)
            self.etiqueta_vista = ui.label("")
        ui.label("Arrastra para girar, rueda para acercar, DOBLE CLIC para marcar.")

        self.contenedor_escena = ui.column()

        with ui.row():
            self.boton_deshacer = ui.button("Deshacer", on_click=self.deshacer)
            self.boton_reiniciar = ui.button("Empezar de nuevo", on_click=self.reiniciar)
        self.lista_puntos = ui.column()
        self.resultados_alineacion = ui.column()
        self.boton_guardar = ui.button("Guardar alineación y puntos", on_click=self.guardar)

        ui.label("2. Medidas de la persona (opcionales) y limpieza").classes("text-xl mt-4")
        with ui.expansion("Cómo medir").classes("w-full"):
            ui.markdown(INSTRUCCIONES_MEDIDAS)
        def en_mm(rango):
            lo, hi = rango
            return {f"En milímetros (entre {lo} y {hi})": lambda v: v is None or lo <= v <= hi}
        with ui.row():
            self.campo_oreja_izq = ui.number("Largo oreja izquierda", placeholder="p. ej. 63", suffix="mm",
                                             validation=en_mm(RANGO_OREJA_MM))
            self.campo_oreja_der = ui.number("Largo oreja derecha", placeholder="p. ej. 63", suffix="mm",
                                             validation=en_mm(RANGO_OREJA_MM))
            self.campo_circ = ui.number("Circunferencia de la cabeza", placeholder="p. ej. 570", suffix="mm",
                                        validation=en_mm(RANGO_CIRCUNFERENCIA_MM))
        with ui.row().classes("items-center"):
            self.boton_limpiar = ui.button("Limpiar malla", on_click=self.limpiar)
            self.spinner = ui.spinner(size="lg")
            self.spinner.set_visibility(False)
            self.estado_limpieza = ui.label("")
        self.registro = ui.log(max_lines=300).classes("w-full h-40")

        ui.label("3. Resultado").classes("text-xl mt-4")
        self.resultado = ui.column()
        ui.timer(0.25, self.seguir_camara)
        self.refrescar()

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
            with ui.scene(width=1000, height=650, grid=False, camera=camara,
                          on_click=self.al_doble_clic, click_events=["dblclick"]) as escena:
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
        if archivo == "malla_final_mm.ply":      # escalada después de alinear
            M = np.diag([*[self.informe["escala"]["factor"]] * 3, 1.0]) @ M
        self.vista.update(original=False, M=M)
        self.etiqueta_vista.set_text(f"Mostrando: {etiqueta}")
        self.boton_textura.set_visibility(False)   # las mallas limpias no tienen textura
        stl, vmin, vmax = self.cache_visor[ruta]
        self.construir_escena([stl], vmin, vmax, "Izquierda")

    def refrescar_selector(self) -> None:
        self.selector_mallas.clear()
        with self.selector_mallas:
            ui.button("Original", on_click=self.mostrar_original)
            if self.salida is not None:
                for archivo, etiqueta in MALLAS_LIMPIEZA:
                    if (self.salida / archivo).exists():
                        ui.button(etiqueta, on_click=lambda a=archivo, e=etiqueta: self.mostrar_salida(a, e))

    def refrescar(self) -> None:
        """Actualiza instrucción, lista de puntos, alineación y botones según el estado."""
        n = len(self.puntos)
        if self.malla is None:
            self.instruccion.set_text("")
        elif n < len(LANDMARKS):
            self.instruccion.set_text(
                f"Punto {n + 1} de {len(LANDMARKS)}: doble clic sobre {LANDMARKS[n][1]}.")
        else:
            self.instruccion.set_text("Siete puntos marcados. Revisa los resultados y guarda.")

        self.lista_puntos.clear()
        with self.lista_puntos:
            for p in self.puntos:
                texto = next(t for k, t, _ in LANDMARKS if k == p["clave"])
                ui.label(f"- {texto}: vértice {p['indice']} en {np.round(p['xyz'], 3)}")

        self.resultados_alineacion.clear()
        self.T = None
        if n >= N_ALINEACION:
            xyz = [p["xyz"] for p in self.puntos[:N_ALINEACION]]
            self.T, self.aid = matriz_alineacion(*xyz)
            self.residuo = residuo_alineacion(self.T, *xyz, self.aid)
            vmin, vmax = self.caja_original
            d = vmax - vmin
            with self.resultados_alineacion:
                ui.label(f"AID (distancia interaural): {self.aid:.4f}").classes("text-lg")
                ui.label(f"Caja envolvente original: {d[0]:.3f} x {d[1]:.3f} x {d[2]:.3f} "
                         "(si mide ~200 está en mm; si ~0,2, en metros; KIRI da escala arbitraria)")
                ui.label(f"Residuo del alineado: {self.residuo:.2e}")
                puntos = {p["clave"]: p["xyz"] for p in self.puntos}
                for lado, (arriba, abajo) in PUNTOS_LARGO.items():
                    if arriba in puntos and abajo in puntos:
                        largo = float(np.linalg.norm(puntos[arriba] - puntos[abajo]))
                        ui.label(f"Largo de la oreja {lado} en la malla: {largo:.4f} "
                                 f"({largo / self.aid:.3f} AID)")
                        z_arriba, z_abajo = aplicar_transformacion(self.T, [puntos[arriba], puntos[abajo]])[:, 2]
                        if z_arriba <= z_abajo:
                            ui.label(f"AVISO: en la oreja {lado} el punto ALTO quedó por debajo del BAJO. "
                                     "¿Se marcaron al revés o lejos de los extremos? Deshacer y volver "
                                     "a marcar.").classes("text-orange-700")
                if self.residuo > RESIDUO_MAX:
                    ui.label(f"ERROR: residuo mayor que {RESIDUO_MAX:.0e}, hay un fallo en la "
                             "matriz. No se puede guardar.").classes("text-red-700 font-bold")

        self.nota_ejes.set_text("(ejes anatómicos)" if self.T is not None else
                                "(ejes supuestos del archivo hasta marcar los 3 primeros puntos)")
        completo = n == len(LANDMARKS) and self.residuo <= RESIDUO_MAX
        self.boton_guardar.set_enabled(completo and not self.limpiando)
        self.boton_limpiar.set_enabled(self.guardado and not self.limpiando)
        self.boton_cargar.set_enabled(not self.limpiando)

    def invalidar(self) -> None:
        """Los puntos cambiaron: lo guardado y la limpieza ya no les corresponden."""
        self.guardado = False
        self.salida, self.informe = None, None
        self.resultado.clear()
        for stl, _, _ in self.cache_visor.values():
            stl.unlink(missing_ok=True)
        self.cache_visor.clear()
        self.refrescar_selector()

    def puede_editar(self) -> bool:
        if self.limpiando:
            ui.notify("Espera a que termine la limpieza.", type="warning")
        return not self.limpiando

    # --- manejadores: puntos --------------------------------------------------
    def al_doble_clic(self, e: events.SceneClickEventArguments) -> None:
        if self.malla is None or not self.puede_editar():
            return
        if not self.vista["original"]:
            ui.notify("Para marcar puntos, muestra el escaneo original.", type="warning")
            return
        if len(self.puntos) >= len(LANDMARKS):
            ui.notify("Ya están los siete puntos. Usa Deshacer o Empezar de nuevo.", type="warning")
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
        self.guardado = len(self.puntos) == len(LANDMARKS)   # el JSON ya es el de estos puntos
        self.refrescar()
        self.mostrar_original()
        ui.notify(f"{len(self.puntos)} puntos recuperados.")

    # --- manejadores: carga y guardado -------------------------------------------
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

    # --- manejadores: limpieza -------------------------------------------------
    async def limpiar(self) -> None:
        salida = carpeta_salida(self.ruta)
        argumentos = [str(self.ruta), "--landmarks", str(self.ruta_json), "--salida", str(salida)]
        for opcion, campo, (lo, hi) in (("--oreja-izq-mm", self.campo_oreja_izq, RANGO_OREJA_MM),
                                        ("--oreja-der-mm", self.campo_oreja_der, RANGO_OREJA_MM),
                                        ("--circunferencia-mm", self.campo_circ, RANGO_CIRCUNFERENCIA_MM)):
            if campo.value:
                if not lo <= campo.value <= hi:
                    ui.notify(f"{campo.props['label']}: {campo.value} no puede estar en milímetros. "
                              "¿Está en metros o en cm? Escribe mm (63, no 0.063).", type="negative")
                    return
                argumentos += [opcion, str(campo.value)]

        self.limpiando = True
        self.invalidar()
        self.guardado = True                    # invalidar() lo apaga, pero los puntos no cambiaron
        self.refrescar()
        self.spinner.set_visibility(True)
        self.estado_limpieza.set_text("Limpiando (tarda unos minutos)...")
        self.registro.clear()
        lineas: list[str] = []
        enviadas = 0

        def volcar() -> None:
            nonlocal enviadas
            for linea in lineas[enviadas:]:
                self.registro.push(linea)
            enviadas = len(lineas)

        temporizador = ui.timer(0.3, volcar)
        codigo = await run.io_bound(ejecutar_limpieza, argumentos, lineas)
        volcar()
        temporizador.cancel()
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
        self.estado_limpieza.set_text(f"Terminada. Archivos en {salida}")
        self.salida, self.informe = salida, informe
        self.mostrar_resultado()
        self.refrescar_selector()
        self.refrescar()
        await self.mostrar_salida("3_suavizada.ply", "3 · suavizada")

    def mostrar_resultado(self) -> None:
        inf, cc = self.informe, self.informe["control_calidad"]
        self.resultado.clear()
        with self.resultado:
            if cc["aprobado"]:
                ui.label("APROBADA").classes("text-3xl font-bold text-green-700")
            else:
                ui.label("RECHAZADA: hay que repetir el escaneo").classes("text-3xl font-bold text-red-700")
            for falla in cc["fallas"]:
                ui.label(f"✖ {falla}").classes("text-red-700")
            for aviso in cc["avisos"]:
                ui.label(f"⚠ {aviso}").classes("text-orange-700")

            esc = inf["escala"]
            ui.label("Escala").classes("text-lg font-bold mt-2")
            if esc["factor"]:
                ui.label(f"Fuente: {esc['fuente']}  ·  factor {esc['factor']:.3f} mm por unidad")
                partes = [f"AID {esc['aid_mm']} mm", f"circunferencia en la malla {esc['circunferencia_mm']} mm"]
                partes += [f"oreja {lado} {mm} mm" for lado, mm in esc.get("largo_oreja_mm", {}).items()]
                ui.label("Con esa escala: " + "  ·  ".join(partes))
                for fuente, dif in esc.get("discrepancias", {}).items():
                    ui.label(f"{fuente}: se aparta un {100 * dif:.1f} % de la escala usada")
                if esc.get("discrepancias"):
                    ui.label("(Umbral de discrepancia aún sin fijar: falta validar con medidas "
                             "reales.)").classes("text-gray-600")
            else:
                ui.label("Sin escala real: no se dio ninguna medida.")

            final = inf.get("suavizada") or inf["cerrada_poisson"]
            ui.label("Malla final").classes("text-lg font-bold mt-2")
            ui.label(f"{final['faces_number']:,} caras  ·  {final['connected_components_number']} pieza(s)  ·  "
                     f"genus {final['genus']}  ·  {final['boundary_edges']} aristas de borde  ·  "
                     f"{final['caras_autointersecadas']} caras autointersecadas")
            for lado, o in inf.get("oreja", {}).items():
                ui.label(f"Oreja {lado}: concha de {o['profundidad_concha_AID']} AID de profundidad, "
                         f"facetado {o['facetado_grados']}°")


def principal() -> None:
    """Función raíz: NiceGUI la llama una vez por cada página que se abre."""
    AppPipeline()


if __name__ == "__main__":
    ui.run(root=principal, title="Pipeline HRTF", port=8080, reload=False,
           show=True, show_welcome_message=False)
