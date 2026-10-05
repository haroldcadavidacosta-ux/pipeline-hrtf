"""Convergencia de NumCalc por frecuencia, leída de sus archivos NC*.out.

NumCalc devuelve código 0 aunque el solver no haya convergido (`return(0)` sin consultar el
estado, y no hay opción para que falle), y el estado no queda en ningún archivo de datos: solo
en el texto de NC*.out. Por eso el estado de cada frecuencia SIEMPRE se lee de ahí. Contrato
del pipeline: ninguna corrida se da por buena sin pasar por aquí.

Lo que hace el solver (fuente de NumCalc, commit 001351d7e1 de 2022-08-18, el más cercano al
binario del 2022-08-26; idéntico en la 1.3.0; ver docs/verificacion_numcalc.md, 1.4 a 1.5c y 3.3):

    double ErroIterSols = 1.0e-9;                      // NC_CommonFunctions.cpp:39
    for(j=0; j<=niter_max_; j++) { ...                 // :1126, niter_max_ = 250 (NC_Main.cpp:75)
        if(err_rel < ErroIterSols || j == niter_max_)  // :1162
    NCout << "\\nCGS solver: number of iterations = " << j << ", relative error = " << err_rel

El criterio es del solver y es binario. Las dos condiciones de salida se registran por separado
(`convergio` y `alcanzo_tope`) porque pueden cumplirse a la vez en la última iteración; ninguna
se deduce de la otra. La tolerancia (1e-9) y el tope (250) son constantes de NumCalc: no se leen
de NC.inp. El «0.000001» de NC.inp (Controlparameter II, tercer número) es el incremento de paso
de la curva de frecuencias, no una tolerancia. El tope solo se cambia con -nitermax, que el
pipeline nunca pasa.
"""
import re
from pathlib import Path

TOLERANCIA_NUMCALC = 1e-9     # ErroIterSols, fija en el código; no configurable
TOPE_ITERACIONES = 250        # niter_max_ por defecto; el pipeline no usa -nitermax

_PASO = re.compile(r"Step (\d+), Frequency = ([\d.eE+-]+) Hz")
_SOLVER = re.compile(r"CGS solver: number of iterations = (\d+), relative error = ([\d.eE+-]+|nan|inf)",
                     re.IGNORECASE)
_AVISO_TOPE = "Warning: Maximum number of iterations is reached!"
_ILU_FALLIDO = "ILU preconditioning failed, the row scanning method is used!"
_RESPALDO_DIRECTO = "Iteration method CGS failed, direct method is used!"


def leer_salida(ruta: Path) -> dict[int, dict]:
    """Estado por paso de un NC*.out: {paso: registro}. Campos del registro:

    frecuencia_hz
    iteraciones               el índice j del bucle de CGS al salir (0..250).
    factor_reduccion_residuo  lo que NumCalc imprime como «relative error». Es ‖r_j‖ / ‖r_1‖:
                              la norma 2 del residuo en la iteración j dividida por la del residuo
                              tras la PRIMERA iteración (j = 0), no por la del residuo inicial.
                              El residuo es el de la recurrencia de CGS (no un b − A·x recalculado)
                              y es el del sistema reescalado por filas (A y b multiplicados por los
                              factores del precondicionador) y precondicionado por la derecha.
                              NO es ‖b − A·x‖ / ‖b‖: no mide la calidad absoluta de la solución y
                              no permite reconstruir ese residuo. Vale 1.0 si el bucle termina en
                              j = 0 (valor inicial de err_rel en el código).
    convergio                 factor_reduccion_residuo < 1e-9 (criterio del solver).
    alcanzo_tope              iteraciones == 250.
    aviso_tope                NumCalc escribió «Maximum number of iterations is reached!». Lo
                              escribe exactamente cuando j == niter_max_, así que debe coincidir con
                              alcanzo_tope; se guarda aparte para detectar un binario o un -nitermax
                              distinto de lo supuesto.
    ilu_fallido               NumCalc avisó «ILU preconditioning failed, the row scanning method is
                              used!»: con FMM, si el ILU parecía casi singular, la frecuencia se
                              resolvió con el precondicionador de escalado por filas, no el ILU
                              declarado en NC.inp.
    respaldo_directo          NumCalc avisó «Iteration method CGS failed, direct method is used!»:
                              solo en BEM tradicional (sin FMM), la solución salió de eliminación
                              gaussiana. Puede no haber línea del solver (si el ILU falló antes de
                              iterar), y entonces iteraciones, factor y convergio quedan en None.

    Los pasos sin línea del solver (estimación de RAM, corrida cortada) salen con convergio=None:
    no hay resultado iterativo.

    El factor se compara tal como está impreso (6 cifras significativas, formato por defecto de
    C++). Un valor entre 0.9999995e-9 y 1e-9 se imprime «1e-09» y aquí saldría no convergido
    aunque el solver lo diera por convergido; alcanzo_tope lo delata (el solver habría parado antes).
    """
    texto = Path(ruta).read_text(encoding="utf-8", errors="replace")
    marcas = list(_PASO.finditer(texto))
    pasos = {}
    for k, m in enumerate(marcas):
        bloque = texto[m.end(): marcas[k + 1].start() if k + 1 < len(marcas) else len(texto)]
        s = _SOLVER.search(bloque)
        r = {"frecuencia_hz": float(m.group(2)), "iteraciones": None, "factor_reduccion_residuo": None,
             "convergio": None, "alcanzo_tope": None, "aviso_tope": _AVISO_TOPE in bloque,
             "ilu_fallido": _ILU_FALLIDO in bloque, "respaldo_directo": _RESPALDO_DIRECTO in bloque}
        if s:
            iteraciones, factor = int(s.group(1)), float(s.group(2))
            r |= {"iteraciones": iteraciones, "factor_reduccion_residuo": factor,
                  "convergio": factor < TOLERANCIA_NUMCALC, "alcanzo_tope": iteraciones == TOPE_ITERACIONES}
        pasos[int(m.group(1))] = r
    return pasos


def leer_fuente(carpeta_fuente: Path) -> dict[int, dict]:
    """Estado por frecuencia de una carpeta NumCalc/source_N: junta todos sus NC*.out (si un
    paso aparece en varios, manda el archivo más reciente que tenga resultado del solver)."""
    pasos = {}
    for ruta in sorted(Path(carpeta_fuente).glob("NC*.out"), key=lambda p: p.stat().st_mtime):
        for paso, r in leer_salida(ruta).items():
            if r["convergio"] is not None or paso not in pasos:
                pasos[paso] = r | {"archivo": ruta.name}
    return pasos


def resumen(pasos: dict[int, dict]) -> dict:
    """Conteos y listas por bandera. Las banderas son independientes: un paso puede estar en
    varias listas (p. ej. convergió y alcanzó el tope en la misma iteración)."""
    def lista(cond):
        return [{"paso": p, "frecuencia_hz": r["frecuencia_hz"], "iteraciones": r["iteraciones"],
                 "factor_reduccion_residuo": r["factor_reduccion_residuo"]}
                for p, r in sorted(pasos.items()) if cond(r)]
    return {"pasos": len(pasos),
            "convergieron": sum(r["convergio"] is True for r in pasos.values()),
            "no_convergieron": lista(lambda r: r["convergio"] is False),
            "alcanzaron_tope": lista(lambda r: r["alcanzo_tope"] is True),
            "convergieron_en_el_tope": lista(lambda r: r["convergio"] is True and r["alcanzo_tope"] is True),
            "ilu_fallido": lista(lambda r: r["ilu_fallido"]),
            "respaldo_directo": lista(lambda r: r["respaldo_directo"]),
            "aviso_tope_incoherente": lista(lambda r: r["alcanzo_tope"] is not None
                                            and r["aviso_tope"] != r["alcanzo_tope"]),
            "sin_resultado": [{"paso": p, "frecuencia_hz": r["frecuencia_hz"]}
                              for p, r in sorted(pasos.items()) if r["convergio"] is None]}
