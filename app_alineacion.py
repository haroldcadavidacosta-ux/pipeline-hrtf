"""App de alineación por tres puntos (NiceGUI). Primera pieza del pipeline HRTF.

Se marca con DOBLE CLIC sobre la malla: la entrada del canal auditivo izquierdo,
la del derecho y la punta de la nariz, en ese orden. Con los tres puntos se
calcula la matriz de alineación (ver malla/alineacion.py) y se guarda la malla
alineada junto con un JSON de landmarks.

Ejecutar:  .venv/Scripts/python.exe app_alineacion.py   ->  http://localhost:8080
"""
import json
import shutil
import tempfile
import uuid
from pathlib import Path

import numpy as np
import trimesh
from nicegui import app, events, run, ui
from scipy.spatial import cKDTree

import config
from malla.alineacion import matriz_alineacion, residuo_alineacion

RUTA_POR_DEFECTO = Path(config.RUTA_DATOS) / "entrada" / "3Dmesh_orig.stl"
EXTENSIONES = {".obj", ".ply", ".stl"}
RESIDUO_MAX = 1e-6

# Los tres puntos, en el orden en que se marcan: (clave, texto, color del marcador)
LANDMARKS = [
    ("oreja_izquierda", "entrada del canal auditivo IZQUIERDO", "#e53935"),
    ("oreja_derecha", "entrada del canal auditivo DERECHO", "#43a047"),
    ("nariz", "punta de la NARIZ", "#1e88e5"),
]
EJES_VISTA = ("+x", "-x", "+y", "-y", "+z", "-z")

# El visor carga la malla desde una URL, así que se sirve una carpeta temporal
# con una copia en STL (three.js no lee .obj ni .ply directamente).
DIR_VISOR = Path(tempfile.mkdtemp(prefix="alineacion_"))
app.add_static_files("/visor", DIR_VISOR)


# --- Carga (funciones sin interfaz, se ejecutan en un hilo aparte) ----------
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


# --- La app: estado + interfaz + manejadores ------------------------------------
class AppAlineacion:
    """Una instancia por página abierta. NiceGUI no reejecuta el código en cada
    interacción, así que el estado vive en atributos normales."""

    def __init__(self) -> None:
        self.ruta: Path | None = None
        self.malla: trimesh.Trimesh | None = None
        self.vert: np.ndarray | None = None
        self.arbol: cKDTree | None = None
        self.centro: np.ndarray | None = None
        self.dim: np.ndarray | None = None
        self.diag: float = 1.0
        self.puntos: list[dict] = []            # {"clave", "indice", "xyz"}
        self.escena: ui.scene | None = None
        self.id_malla: str | None = None        # para ignorar impactos sobre los marcadores
        self.marcadores: list = []
        self.archivo_visor: Path | None = None
        self.T: np.ndarray | None = None
        self.aid: float = 0.0
        self.residuo: float = 0.0
        self.construir_interfaz()

    # --- interfaz -----------------------------------------------------------
    def construir_interfaz(self) -> None:
        ui.label("Alineación de la malla por tres puntos").classes("text-2xl")

        with ui.row().classes("w-full items-end"):
            self.entrada_ruta = ui.input("Ruta de la malla (.obj, .ply o .stl)",
                                         value=str(RUTA_POR_DEFECTO)).classes("flex-grow")
            self.boton_cargar = ui.button("Cargar", on_click=self.cargar)

        self.info_malla = ui.label("Ninguna malla cargada.")
        self.instruccion = ui.label("").classes("text-lg font-bold")

        with ui.row().classes("items-center"):
            ui.label("Vista:")
            for eje in EJES_VISTA:
                ui.button(eje, on_click=lambda eje=eje: self.mover_camara(eje))
            ui.label("Arrastra para girar, rueda para acercar, DOBLE CLIC para marcar.")

        self.contenedor_escena = ui.column()

        with ui.row():
            ui.button("Deshacer", on_click=self.deshacer)
            ui.button("Empezar de nuevo", on_click=self.reiniciar)

        self.lista_puntos = ui.column()
        self.resultados = ui.column()
        self.boton_guardar = ui.button("Alinear y guardar", on_click=self.guardar)
        self.refrescar()

    def mover_camara(self, eje: str, duracion: float = 0.5) -> None:
        """Coloca la cámara mirando al centro de la malla desde el eje indicado."""
        if self.escena is None:
            return
        signo = 1 if eje[0] == "+" else -1
        i = "xyz".index(eje[1])
        pos = self.centro.copy()
        pos[i] += signo * 1.5 * self.diag
        arriba = (1, 0, 0) if i == 2 else (0, 0, 1)   # mirando por z, "arriba" es +x
        self.escena.move_camera(
            x=pos[0], y=pos[1], z=pos[2],
            look_at_x=self.centro[0], look_at_y=self.centro[1], look_at_z=self.centro[2],
            up_x=arriba[0], up_y=arriba[1], up_z=arriba[2], duration=duracion)

    def construir_escena(self) -> None:
        self.contenedor_escena.clear()
        camara = ui.scene.perspective_camera(fov=60, near=self.diag / 1000,
                                             far=self.diag * 50)
        with self.contenedor_escena:
            with ui.scene(width=1000, height=650, grid=False, camera=camara,
                          on_click=self.al_doble_clic, click_events=["dblclick"]) as escena:
                objeto = escena.stl(f"/visor/{self.archivo_visor.name}").material("#c8c8c8")
        self.escena = escena
        self.id_malla = objeto.id
        self.marcadores = []
        self.mover_camara("-y", duracion=0)

    def dibujar_marcador(self, punto: dict) -> None:
        color = next(c for k, _, c in LANDMARKS if k == punto["clave"])
        with self.escena:
            esfera = (self.escena.sphere(radius=self.diag / 120)
                      .material(color).move(*punto["xyz"]))
        self.marcadores.append(esfera)

    def refrescar(self) -> None:
        """Actualiza instrucción, lista de puntos y resultados según el estado."""
        n = len(self.puntos)
        if self.malla is None:
            self.instruccion.set_text("")
        elif n < 3:
            self.instruccion.set_text(
                f"Punto {n + 1} de 3: doble clic sobre la {LANDMARKS[n][1]}.")
        else:
            self.instruccion.set_text("Tres puntos marcados. Revisa los resultados y guarda.")

        self.lista_puntos.clear()
        with self.lista_puntos:
            for p in self.puntos:
                texto = next(t for k, t, _ in LANDMARKS if k == p["clave"])
                ui.label(f"- {texto}: vértice {p['indice']} en {np.round(p['xyz'], 3)}")

        self.resultados.clear()
        self.boton_guardar.disable()
        if n < 3:
            return

        xyz = [p["xyz"] for p in self.puntos]
        T, aid = matriz_alineacion(*xyz)
        residuo = residuo_alineacion(T, *xyz, aid)
        self.T, self.aid, self.residuo = T, aid, residuo
        d = self.dim
        with self.resultados:
            ui.label(f"AID (distancia interaural): {aid:.3f}").classes("text-lg")
            ui.label(f"Caja envolvente original: {d[0]:.2f} x {d[1]:.2f} x {d[2]:.2f} "
                     "(si mide ~200 está en mm; si ~0,2, en metros)")
            ui.label(f"Residuo del alineado: {residuo:.2e}")
            if not config.AID_MIN_MM <= aid <= config.AID_MAX_MM:
                ui.label(f"AVISO: AID fuera del rango esperado "
                         f"[{config.AID_MIN_MM}, {config.AID_MAX_MM}] mm. "
                         "¿Unidades incorrectas o puntos mal marcados?").classes("text-orange-700")
            if residuo > RESIDUO_MAX:
                ui.label(f"ERROR: residuo mayor que {RESIDUO_MAX:.0e}, hay un fallo en la "
                         "matriz. No se puede guardar.").classes("text-red-700 font-bold")
            else:
                self.boton_guardar.enable()

    # --- manejadores --------------------------------------------------------
    def al_doble_clic(self, e: events.SceneClickEventArguments) -> None:
        if self.malla is None:
            return
        if len(self.puntos) >= 3:
            ui.notify("Ya hay tres puntos. Usa Deshacer o Empezar de nuevo.", type="warning")
            return
        impactos = [h for h in e.hits if h.object_id == self.id_malla]
        if not impactos:
            ui.notify("Doble clic fuera de la malla.", type="warning")
            return
        h = impactos[0]                                 # el más cercano a la cámara
        _, indice = self.arbol.query([h.x, h.y, h.z])   # vértice más cercano de la malla completa
        punto = {"clave": LANDMARKS[len(self.puntos)][0],
                 "indice": int(indice), "xyz": self.vert[indice].copy()}
        self.puntos.append(punto)
        self.dibujar_marcador(punto)
        self.refrescar()

    def deshacer(self) -> None:
        if self.puntos:
            self.puntos.pop()
            self.marcadores.pop().delete()
        self.refrescar()

    def reiniciar(self) -> None:
        self.puntos.clear()
        for m in self.marcadores:
            m.delete()
        self.marcadores.clear()
        self.refrescar()

    async def cargar(self) -> None:
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
            if self.archivo_visor and self.archivo_visor.exists():
                self.archivo_visor.unlink()
            archivo_visor = await run.io_bound(exportar_para_visor, ruta, malla)
        except Exception as ex:  # noqa: BLE001
            self.info_malla.set_text(f"No se pudo cargar: {ex}")
            self.boton_cargar.enable()
            return

        self.ruta, self.malla, self.archivo_visor = ruta, malla, archivo_visor
        self.vert = np.asarray(malla.vertices, dtype=float)
        self.arbol = cKDTree(self.vert)
        vmin, vmax = self.vert.min(0), self.vert.max(0)
        self.centro, self.dim = (vmin + vmax) / 2, vmax - vmin
        self.diag = float(np.linalg.norm(self.dim))
        self.puntos = []

        d = self.dim
        self.info_malla.set_text(f"{ruta.name}: {len(self.vert):,} vértices, "
                                 f"{len(malla.faces):,} caras, caja envolvente "
                                 f"{d[0]:.1f} x {d[1]:.1f} x {d[2]:.1f}")
        self.construir_escena()
        self.refrescar()
        self.boton_cargar.enable()

    async def guardar(self) -> None:
        ruta = self.ruta
        salida_malla = ruta.with_name(f"{ruta.stem}_alineada.ply")
        salida_json = ruta.with_name(f"{ruta.stem}_landmarks.json")

        def exportar() -> None:
            alineada = self.malla.copy()
            alineada.apply_transform(self.T)
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
                "matriz": self.T.tolist(),
                "sistema": "+x adelante, +y izquierda del sujeto, +z arriba, "
                           "origen en el punto medio interaural",
            }
            salida_json.write_text(json.dumps(datos, indent=2, ensure_ascii=False),
                                   encoding="utf-8")
        except Exception as ex:  # noqa: BLE001
            ui.notify(f"Error al guardar: {ex}", type="negative")
            self.boton_guardar.enable()
            return
        with self.resultados:
            ui.label(f"Guardado: {salida_malla.name} y {salida_json.name} "
                     f"en {ruta.parent}").classes("text-green-700 font-bold")
        self.boton_guardar.enable()


def principal() -> None:
    """Función raíz: NiceGUI la llama una vez por cada página que se abre."""
    AppAlineacion()


if __name__ == "__main__":
    ui.run(root=principal, title="Alineación HRTF", port=8080, reload=False,
           show=True, show_welcome_message=False)
