"""¿Cambia el resultado de NumCalc según el equipo? Criterio registrado en
metricas/predicciones_repetibilidad_C_E_2026-11-05.md.

Repite en este equipo (la torre) unas frecuencias sobre COPIAS de los proyectos y compara la presión
en la rejilla de evaluación con el resultado original. No toca los originales.

Uso:  .venv\\Scripts\\python.exe experimentos\\repetibilidad\\prueba_equipo.py [carpeta de las capturas]
Escribe en datos/salidas/evaluacion_repetibilidad/equipo/: prueba_equipo.json y las copias.
"""
import json
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
import config  # noqa: E402

CAPTURAS = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ.parent / "PRUEBA REPETIBILIDAD"
SALIDA = RAIZ / "datos" / "salidas" / "evaluacion_repetibilidad" / "equipo"
# (proyecto, paso, equipo donde se simuló el original)
CASOS = [("myHRTF_project_L", 27, "portátil"), ("myHRTF_project_L", 54, "portátil"),
         ("myHRTF_project_L", 80, "portátil"), ("myHRTF_project_R", 54, "torre")]
UMBRAL_DB = 0.01


def copiar_proyecto(origen: Path, destino: Path) -> None:
    """Copia el proyecto sin los resultados de NumCalc."""
    if destino.exists():
        shutil.rmtree(destino)
    ignorar = shutil.ignore_patterns("be.out", "NC*-*.out", "NC.out", "Output2HRTF", "manage_numcalc_*", "*.blend")
    shutil.copytree(origen, destino, ignore=ignorar)


def leer_presion(ruta: Path) -> tuple[np.ndarray, bytes]:
    crudo = ruta.read_bytes()
    filas = [fila.split() for fila in crudo.decode().splitlines()[3:] if fila.strip()]
    v = np.array(filas, dtype=float)
    return v[:, 1] + 1j * v[:, 2], crudo


def tiempo_s(ruta: Path) -> float | None:
    """Duración según las marcas Start time y End time de NC*.out."""
    texto = ruta.read_text(encoding="utf-8", errors="replace")
    t = re.findall(r"(?:Start|End) time: \d+/\d+/\d+ (\d+):(\d+):(\d+)", texto)
    if len(t) < 2:
        return None
    a, b = [int(h) * 3600 + int(mi) * 60 + int(s) for h, mi, s in t[:2]]
    return float((b - a) % 86400)


def iteraciones(ruta: Path) -> int | None:
    v = re.findall(r"number of iterations = (\d+)", ruta.read_text(encoding="utf-8", errors="replace"))
    return int(v[-1]) if v else None


def correr(caso: tuple) -> dict:
    proyecto, paso, equipo = caso
    origen = CAPTURAS / "E2" / proyecto
    destino = SALIDA / f"{proyecto}_{paso}"
    copiar_proyecto(origen, destino)
    src = destino / "NumCalc" / "source_1"
    t0 = time.time()
    r = subprocess.run([str(config.NUMCALC_EXE), "-istart", str(paso), "-iend", str(paso)], cwd=src,
                       capture_output=True)
    pared = time.time() - t0
    a, crudo_a = leer_presion(origen / "NumCalc" / "source_1" / "be.out" / f"be.{paso}" / "pEvalGrid")
    b, crudo_b = leer_presion(src / "be.out" / f"be.{paso}" / "pEvalGrid")
    if a.shape != b.shape:
        raise ValueError(f"{proyecto} paso {paso}: {a.shape} frente a {b.shape}")
    db = 20 * np.log10(np.abs(b) / np.abs(a))
    fase = np.degrees(np.abs(np.angle(b / a)))
    nc_o = origen / "NumCalc" / "source_1" / f"NC{paso}-{paso}.out"
    nc_n = src / f"NC{paso}-{paso}.out"
    return {"proyecto": proyecto, "paso": paso, "frecuencia_hz": paso * 150.0, "equipo_original": equipo,
            "codigo": r.returncode, "puntos": int(a.size), "identico_al_byte": crudo_a == crudo_b,
            "max_abs_db": float(np.abs(db).max()), "media_abs_db": float(np.abs(db).mean()),
            "max_fase_grados": float(fase.max()),
            "cumple_umbral": bool(np.abs(db).max() < UMBRAL_DB),
            "iteraciones_original": iteraciones(nc_o), "iteraciones_repetida": iteraciones(nc_n),
            "tiempo_s_original": tiempo_s(nc_o), "tiempo_s_repetida": tiempo_s(nc_n), "pared_s": round(pared, 1)}


def principal() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    print("NumCalc:", config.NUMCALC_EXE)
    with ThreadPoolExecutor(len(CASOS)) as ex:
        res = list(ex.map(correr, CASOS))
    (SALIDA / "prueba_equipo.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    for r in res:
        print(r)


if __name__ == "__main__":
    principal()
