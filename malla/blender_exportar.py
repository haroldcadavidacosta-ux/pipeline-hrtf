"""Exporta los proyectos de Mesh2HRTF. Se ejecuta DENTRO de Blender, no con el Python
del entorno: lo lanza malla/exportacion.py así

  blender --background --factory-startup --python-exit-code 1
          --python malla/blender_exportar.py -- <trabajo.json>

El JSON trae las rutas y los parámetros (se arma en malla/exportacion.py desde config.py)
y aquí se escribe el resultado ("resultado" en el mismo JSON). Por cada lado:

  1. escena vacía; se importa la malla graduada tal cual (sin girar ni escalar: el
     exportador escribe los vértices sin aplicar la transformación del objeto, así que
     llegan con los ejes del pipeline, que son los de Mesh2HRTF);
  2. se llama "Reference" (el nombre que exige el exportador);
  3. materiales "Skin" (todo), "Left ear" y "Right ear": una cara cada uno, la más
     cercana a la entrada del canal marcado, (0, ±AID/2, 0) mm. El exportador pide las
     dos ranuras aunque la fuente sea una sola oreja;
  4. bpy.ops.mesh2input.inp con la fuente en la oreja de ese lado.

El complemento mesh2input no se instala en el Blender del usuario: se registra desde la
copia de Mesh2HRTF que trae la app (--factory-startup deja fuera sus preferencias).
"""
import json
import sys
from pathlib import Path

import bpy
import numpy as np

MATERIALES = ("Skin", "Left ear", "Right ear")      # índices 0, 1, 2
# Solo para ver el .blend que guarda el exportador (Mesh2HRTF usa los nombres, no los
# colores): los mismos de su script AssignMaterials.py
COLORES = {"Skin": (0, 1, 0, 1), "Left ear": (0, 0, 1, 1), "Right ear": (1, 0, 0, 1)}
FUENTE = {"left": "Left ear", "right": "Right ear"}


def decir(texto: str) -> None:
    print(f"[exportar] {texto}", flush=True)


def vaciar_escena() -> None:
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def importar(ruta: str):
    antes = set(bpy.data.objects)
    bpy.ops.wm.ply_import(filepath=ruta, forward_axis="Y", up_axis="Z", global_scale=1.0,
                          use_scene_unit=False, merge_verts=False)
    nuevos = [o for o in bpy.data.objects if o not in antes]
    if len(nuevos) != 1:
        raise RuntimeError(f"al importar {ruta} aparecieron {len(nuevos)} objetos")
    return nuevos[0]


def caras_de_los_canales(obj, canales: dict) -> dict:
    """Para cada canal, la cara cuyo centro está más cerca, con su distancia (mm), área
    (mm²) y la componente de su normal hacia fuera por ese lado."""
    caras = obj.data.polygons
    n = len(caras)
    centros, normales, areas = np.empty(3 * n), np.empty(3 * n), np.empty(n)
    caras.foreach_get("center", centros)
    caras.foreach_get("normal", normales)
    caras.foreach_get("area", areas)
    centros, normales = centros.reshape(-1, 3), normales.reshape(-1, 3)
    res = {}
    for lado, canal in canales.items():
        d = np.linalg.norm(centros - np.asarray(canal), axis=1)
        i = int(np.argmin(d))
        signo = 1 if lado == "left" else -1
        res[lado] = {"cara": i, "centro_mm": [round(float(c), 4) for c in centros[i]],
                     "distancia_mm": round(float(d[i]), 4), "area_mm2": round(float(areas[i]), 5),
                     "normal_hacia_fuera": round(float(signo * normales[i, 1]), 3)}
    return res


def asignar_materiales(obj, caras: dict) -> None:
    obj.data.materials.clear()
    for nombre in MATERIALES:
        material = bpy.data.materials.get(nombre) or bpy.data.materials.new(nombre)
        material.diffuse_color = COLORES[nombre]
        obj.data.materials.append(material)
    indices = np.zeros(len(obj.data.polygons), dtype=np.int32)
    indices[caras["left"]["cara"]] = MATERIALES.index("Left ear")
    indices[caras["right"]["cara"]] = MATERIALES.index("Right ear")
    obj.data.polygons.foreach_set("material_index", indices)
    obj.data.update()


def escena_en_mm() -> None:
    """Las mallas están en mm: que Blender rotule mm y no m (solo visual; el exportador
    no mira las unidades de la escena, usa unit='mm')."""
    unidades = bpy.context.scene.unit_settings
    unidades.system, unidades.scale_length, unidades.length_unit = "METRIC", 0.001, "MILLIMETERS"
    for pantalla in bpy.data.screens:                  # colores de los materiales en la vista sólida
        for area in pantalla.areas:
            for espacio in area.spaces:
                if espacio.type == "VIEW_3D":
                    espacio.shading.color_type = "MATERIAL"
                    espacio.clip_end = 100000.0        # la cabeza mide ~250 unidades


def principal() -> None:
    ruta_trabajo = Path(sys.argv[sys.argv.index("--") + 1])
    trabajo = json.loads(ruta_trabajo.read_text(encoding="utf-8"))

    sys.path.insert(0, str(Path(trabajo["programPath"]) / "Mesh2Input"))
    import mesh2input
    mesh2input.register()
    decir(f"Blender {bpy.app.version_string}, exportador mesh2input cargado")
    escena_en_mm()

    resultado = {}
    for lado, datos in trabajo["lados"].items():
        vaciar_escena()
        obj = importar(datos["malla"])
        obj.name = obj.data.name = "Reference"
        caras = caras_de_los_canales(obj, trabajo["canales_mm"])
        asignar_materiales(obj, caras)
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        decir(f"{lado}: {len(obj.data.vertices):,} vértices, {len(obj.data.polygons):,} caras; "
              f"fuente en la cara {caras[lado]['cara']}, a {caras[lado]['distancia_mm']:.2f} mm del canal")
        estado = bpy.ops.mesh2input.inp(filepath=datos["proyecto"], programPath=trabajo["programPath"],
                                        sourceType=FUENTE[lado], **trabajo["parametros"])
        if "FINISHED" not in estado:
            raise RuntimeError(f"{lado}: el exportador terminó con {estado}")
        decir(f"{lado}: proyecto exportado en {datos['proyecto']}")
        resultado[lado] = {"vertices": len(obj.data.vertices), "caras": len(obj.data.polygons),
                           "caras_canales": caras}

    trabajo["resultado"] = resultado
    ruta_trabajo.write_text(json.dumps(trabajo, indent=2, ensure_ascii=False), encoding="utf-8")


principal()
