"""Auditoría: convergencia de NumCalc en TODOS los NC*.out que haya en disco.

Uso:  .venv/Scripts/python.exe experimentos/auditar_convergencia.py <salida.json> <raíz> [<raíz> ...]
Agrupa por carpeta de fuente (la que tiene los NC*.out) e indica el proyecto (la carpeta con
parameters.json más cercana hacia arriba, si la hay).
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from malla.convergencia import leer_fuente, resumen   # noqa: E402


def proyecto_de(carpeta: Path) -> Path | None:
    for p in [carpeta, *carpeta.parents]:
        if (p / "parameters.json").exists():
            return p
    return None


def principal() -> None:
    salida, raices = Path(sys.argv[1]), [Path(r) for r in sys.argv[2:]]
    fuentes = set()
    for raiz in raices:
        for dirpath, _, archivos in os.walk(raiz):
            if any(a.startswith("NC") and a.endswith(".out") for a in archivos):
                fuentes.add(Path(dirpath))
    informe = []
    for fuente in sorted(fuentes):
        pasos = leer_fuente(fuente)
        if not pasos:
            continue
        proyecto = proyecto_de(fuente)
        par = json.loads((proyecto / "parameters.json").read_text(encoding="utf-8")) if proyecto else {}
        mtimes = [p.stat().st_mtime for p in fuente.glob("NC*.out")]
        informe.append({"fuente": str(fuente), "proyecto": str(proyecto) if proyecto else None,
                        "frecuencias_del_proyecto": par.get("numFrequencies"),
                        "titulo": par.get("projectTitle"), "fecha_ultima_salida": max(mtimes)}
                       | resumen(pasos))
    salida.write_text(json.dumps(informe, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(informe)} carpetas de fuente con salida de NumCalc -> {salida}")


if __name__ == "__main__":
    principal()
