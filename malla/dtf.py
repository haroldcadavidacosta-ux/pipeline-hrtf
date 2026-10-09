"""HRIR ecualizada al campo difuso (DTF): la HRTF para escuchar con timbre neutro.

Las HRIR de Mesh2HRTF están referidas al campo libre en el centro de la cabeza, así que llevan
la resonancia de la oreja y del canal (hasta unos +20 dB entre 3 y 6 kHz) y suenan brillantes.
La DTF divide cada HRTF por la respuesta de campo difuso (el promedio energético sobre todas las
direcciones y las dos orejas), como sofa_dtfs_equalization.py de mesh2hrtf-tools, con
mesh2hrtf.compute_dtfs:

  - sobre la rejilla Default, que cubre la esfera completa (ARI no tiene la parte de abajo);
  - promedio ponderado por área (Voronoi), porque la rejilla no es uniforme (la herramienta
    usa pesos iguales por omisión);
  - filtro inverso de fase mínima, sin suavizado (los valores por omisión de la herramienta).

El filtro es el mismo para las dos orejas: la ILD no cambia y la ITD prácticamente tampoco. Sí
cambia el espectro absoluto, así que las métricas (SD) se calculan sobre la HRTF sin ecualizar.

Salida, junto a los SOFA: HRIR_Default_<fs>_DTF.sofa (48 y 44,1 kHz).
"""
from pathlib import Path

FRECUENCIAS_MUESTREO = (48000, 44100)


def nombre_dtf(fs: int) -> str:
    return f"HRIR_Default_{fs}_DTF.sofa"


def escribir(carpeta_sofa: Path, registrar=print) -> list[Path]:
    """Escribe HRIR_Default_<fs>_DTF.sofa por cada HRIR_Default_<fs>.sofa que haya. Devuelve las rutas."""
    import mesh2hrtf as m2h
    import sofar as sf
    carpeta_sofa = Path(carpeta_sofa)
    escritos = []
    for fs in FRECUENCIAS_MUESTREO:
        origen = carpeta_sofa / f"HRIR_Default_{fs}.sofa"
        if not origen.is_file():
            continue
        sofa = sf.read_sofa(str(origen), verify=False)
        dtf, _ = m2h.compute_dtfs(sofa, smooth_fractions=None, phase="minimum", weights="voronoi")
        dtf.GLOBAL_Comment = (
            (sofa.GLOBAL_Comment + " " if sofa.GLOBAL_Comment else "")
            + "ECUALIZADA AL CAMPO DIFUSO (DTF) para escuchar: mesh2hrtf.compute_dtfs sobre la rejilla Default, "
            "ponderacion por area (Voronoi), filtro inverso de fase minima, sin suavizado. No usar para metricas "
            "espectrales: la HRTF sin ecualizar es " + origen.name + ".")
        destino = carpeta_sofa / nombre_dtf(fs)
        sf.write_sofa(str(destino), dtf)
        escritos.append(destino)
    if escritos:
        registrar(f"  DTF: {', '.join(p.name for p in escritos)}")
    return escritos
