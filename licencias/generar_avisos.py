"""Licencias y código fuente que acompañan a la app empaquetada. Lo llama pipeline_hrtf.spec
al terminar de construir; también se puede correr solo:

    .venv\\Scripts\\python.exe licencias\\generar_avisos.py dist\\pipeline_hrtf

Deja junto a pipeline_hrtf.exe:
- LICENSE.txt: la GPL-3.0 del proyecto.
- AVISOS_DE_TERCEROS.md: qué lleva la app, con qué licencia y dónde está su código.
- licencias/: los textos completos (textos/ y nativas/ de esta carpeta) y, en python/, la
  licencia de cada paquete de Python que PyInstaller metió en la app (se detectan mirando
  _internal y el archivo PYZ del .exe, así que la lista sigue a lo que de verdad se empaquetó).
- codigo_fuente_pipeline_hrtf.zip: el código para construir la app (los archivos versionados
  en git, tal como están en la carpeta al construir, sin experimentos, documentación de
  trabajo ni pruebas), que la GPL-3 exige entregar con el binario.
"""
import importlib.metadata as md
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
PATRON_LICENCIA = re.compile(r"(LICEN[CS]E|COPYING|NOTICE|AUTHORS)", re.IGNORECASE)
FUERA_DEL_ZIP = ("experimentos/", "docs/", "pruebas/", "metricas/")
DOCUMENTOS_DE_TRABAJO = {"contexto.md", "guia_arranque_pipeline_hrtf.md"}


def modulos_en_exe(exe: Path) -> set[str]:
    """Módulos de primer nivel que PyInstaller comprimió dentro del .exe (archivo PYZ): ahí van
    los paquetes de Python puro, que no aparecen como carpeta en _internal."""
    from PyInstaller.archive.readers import CArchiveReader
    c = CArchiveReader(str(exe))
    pyz = c.open_embedded_archive(next(n for n in c.toc if n.endswith(".pyz")))
    return {m.split(".")[0] for m in pyz.toc}


def paquetes_empaquetados(dist: Path) -> list[md.Distribution]:
    """Distribuciones de Python instaladas cuyo módulo de primer nivel va en la app: como carpeta
    o extensión en _internal, o comprimido dentro del .exe."""
    presentes = {p.name.split(".")[0] for p in (dist / "_internal").iterdir()}
    presentes |= modulos_en_exe(dist / "pipeline_hrtf.exe")
    presentes = {p.lower() for p in presentes}
    por_modulo = md.packages_distributions()
    nombres = {d for mod, dists in por_modulo.items() if mod.lower() in presentes for d in dists}
    return sorted((md.distribution(n) for n in nombres), key=lambda d: d.metadata["Name"].lower())


def licencia_declarada(d: md.Distribution) -> str:
    m = d.metadata
    expr = m.get("License-Expression")
    if expr:
        return expr
    clasif = [c.split("::")[-1].strip() for c in m.get_all("Classifier") or [] if c.startswith("License")]
    if clasif:
        return ", ".join(clasif)
    lic = (m.get("License") or "").strip().splitlines()
    return lic[0][:80] if lic else "sin declarar (ver el texto)"


def copiar_licencias_python(dists, destino: Path) -> list[tuple[str, str, str, int]]:
    destino.mkdir(parents=True, exist_ok=True)
    filas = []
    for d in dists:
        nombre, version = d.metadata["Name"], d.version
        textos = [f for f in d.files or [] if PATRON_LICENCIA.search(f.name) and ".dist-info" in str(f)]
        cuerpo = [f"{nombre} {version}\nLicencia declarada: {licencia_declarada(d)}\n"]
        for f in textos:
            cuerpo.append(f"\n===== {f.name} =====\n{Path(d.locate_file(f)).read_text(encoding='utf-8', errors='replace')}")
        if not textos:                                   # algunos paquetes solo la traen en los metadatos
            cuerpo.append("\n" + (d.metadata.get("License") or "El paquete no incluye texto de licencia."))
        (destino / f"{nombre}-{version}.txt").write_text("".join(cuerpo), encoding="utf-8")
        filas.append((nombre, version, licencia_declarada(d), len(textos)))
    return filas


def zip_codigo_fuente(destino: Path) -> int:
    archivos = subprocess.run(["git", "ls-files", "-z"], cwd=RAIZ, capture_output=True, check=True,
                              text=True).stdout.split("\0")
    # la GPL-3 pide el código para construir el .exe; los experimentos, la documentación de
    # trabajo y las pruebas no hacen falta (y nombran a los participantes del estudio)
    archivos = [a for a in archivos if a and (RAIZ / a).is_file()
                and not a.startswith(FUERA_DEL_ZIP) and a not in DOCUMENTOS_DE_TRABAJO]
    # la licencia y esta carpeta van siempre, aunque todavía no estén en git
    propios = ["LICENSE", "AVISOS_DE_TERCEROS.md"]
    propios += [p.relative_to(RAIZ).as_posix() for p in AQUI.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    archivos += [p for p in propios if p not in archivos and (RAIZ / p).is_file()]
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for a in archivos:
            z.write(RAIZ / a, f"pipeline_hrtf/{a}")
    return len(archivos)


def generar(dist: Path) -> None:
    dist = Path(dist)
    shutil.copy(RAIZ / "LICENSE", dist / "LICENSE.txt")
    shutil.copy(RAIZ / "AVISOS_DE_TERCEROS.md", dist / "AVISOS_DE_TERCEROS.md")
    lic = dist / "licencias"
    if lic.exists():
        shutil.rmtree(lic)
    shutil.copytree(AQUI / "textos", lic / "textos")
    shutil.copytree(AQUI / "nativas", lic / "nativas")
    filas = copiar_licencias_python(paquetes_empaquetados(dist), lic / "python")
    tabla = ["# Paquetes de Python incluidos en esta compilación", "",
             "Generado por licencias/generar_avisos.py a partir de lo que hay en _internal y en el .exe.", "",
             "| Paquete | Versión | Licencia declarada | Archivo |", "|---|---|---|---|"]
    tabla += [f"| {n} | {v} | {l} | licencias/python/{n}-{v}.txt |" for n, v, l, _ in filas]
    (lic / "python" / "INDICE.md").write_text("\n".join(tabla) + "\n", encoding="utf-8")
    n = zip_codigo_fuente(dist / "codigo_fuente_pipeline_hrtf.zip")
    sin_texto = [f"{n_} {v}" for n_, v, _, k in filas if k == 0]
    print(f"Licencias: {len(filas)} paquetes de Python, código fuente con {n} archivos.")
    if sin_texto:
        print("  Sin archivo de licencia propio (se usó el texto de los metadatos):", ", ".join(sin_texto))


if __name__ == "__main__":
    generar(Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "dist" / "pipeline_hrtf")
