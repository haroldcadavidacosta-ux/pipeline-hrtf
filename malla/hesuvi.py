"""Exportación de la HRTF a HeSuVi: sonido envolvente 7.1 virtual con audífonos en Windows.

HeSuVi (sobre Equalizer APO) virtualiza 7 parlantes con un WAV de 14 canales: la respuesta al
impulso de cada parlante a cada oreja. Aquí se arma ese WAV desde la HRIR de la carpeta
SOFA_myHRTF_project_merged, igual que sofa_to_hesuvi_ir_extractor.py (v1.03) de mesh2hrtf-tools:
mismas direcciones, mismo orden de canales y misma normalización. Se reescribió porque el
original usa atributos internos de pyfar 0.5 que ya no existen (falla con pyfar 0.8) y pide
confirmaciones por teclado.

Salen dos versiones por frecuencia de muestreo (48 y 44,1 kHz):
  HeSuVi_<fs>.wav       la HRIR tal cual sale de Mesh2HRTF (referida al campo libre en el centro
                        de la cabeza): conserva la resonancia de la oreja, suena brillante
  HeSuVi_DTF_<fs>.wav   desde HRIR_Default_<fs>_DTF.sofa, ecualizada al campo difuso
                        (malla/dtf.py): suena más neutra; es la recomendada para escuchar

Es una salida para escuchar, no para medir: las métricas se calculan sobre los SOFA.
"""
from pathlib import Path

import numpy as np

# Parlantes 7.1 de HeSuVi: L, Ls, Lb, C, R, Rs, Rb (sin LFE), en el plano horizontal.
# Azimut como en SOFA: 0° al frente, 90° a la izquierda.
PARLANTES = [("L", 30), ("Ls", 90), ("Lb", 135), ("C", 0), ("R", 330), ("Rs", 270), ("Rb", 225)]
# Canal del WAV para cada (parlante, oreja), en el orden de PARLANTES y oreja izquierda/derecha:
# 0 L-Le, 1 L-Re, 2 Ls-Le, 3 Ls-Re, 4 Lb-Le, 5 Lb-Re, 6 C-Le, 7 R-Re, 8 R-Le, 9 Rs-Re, 10 Rs-Le,
# 11 Rb-Re, 12 Rb-Le, 13 C-Re (https://sourceforge.net/p/hesuvi/discussion/general/thread/34f3be74b9/)
MAPA_CANALES = [0, 1, 2, 3, 4, 5, 6, 13, 8, 7, 10, 9, 12, 11]
PICO = 0.985                     # normalización del original: el máximo de los 14 canales a 0,985
ANGULO_MAX_GRADOS = 1.0          # la dirección elegida no puede quedar más lejos que esto de la pedida


def direccion_mas_cercana(pos: np.ndarray, az: float, el: float = 0.0) -> tuple[int, float]:
    """Índice de la dirección de la rejilla más cercana (ángulo sobre la esfera) y su distancia en grados."""
    def unitario(a, e):
        a, e = np.radians(a), np.radians(e)
        return np.stack([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)], axis=-1)
    cos = np.clip(unitario(pos[:, 0], pos[:, 1]) @ unitario(az, el), -1, 1)
    i = int(np.argmax(cos))
    return i, float(np.degrees(np.arccos(cos[i])))


def catorce_canales(ir: np.ndarray, pos: np.ndarray) -> tuple[np.ndarray, dict]:
    """(14, muestras) en el orden de HeSuVi, sin normalizar, y la dirección usada por parlante."""
    salida = np.zeros((14, ir.shape[2]))
    usadas, k = {}, 0
    for nombre, az in PARLANTES:
        i, error = direccion_mas_cercana(pos, az)
        if error > ANGULO_MAX_GRADOS:
            raise ValueError(f"la rejilla no tiene una dirección a menos de {ANGULO_MAX_GRADOS}° de "
                             f"{nombre} (azimut {az}°): la más cercana está a {error:.1f}°")
        usadas[nombre] = {"azimut": float(pos[i, 0]), "elevacion": float(pos[i, 1]), "error_grados": round(error, 3)}
        for oreja in (0, 1):
            salida[MAPA_CANALES[k]] = ir[i, oreja]
            k += 1
    return salida, usadas


def escribir(ruta: Path, canales: np.ndarray, fs: int) -> float:
    """WAV de 32 bits en coma flotante, normalizado como el original. Devuelve la ganancia aplicada."""
    import soundfile
    ganancia = PICO / np.abs(canales).max()
    soundfile.write(str(ruta), (canales * ganancia).T.astype(np.float32), fs, subtype="FLOAT")
    return float(ganancia)


def exportar(carpeta_sofa: Path, registrar=print) -> dict:
    """Escribe los WAV de HeSuVi junto a los SOFA. Devuelve lo hecho (archivos y direcciones).
    La versión DTF sale de HRIR_Default_<fs>_DTF.sofa (malla/dtf.py), que se escribe si falta."""
    import sofar as sf
    from malla import dtf as modulo_dtf
    carpeta_sofa = Path(carpeta_sofa)
    hecho = {"archivos": {}, "direcciones": None}
    for fs in modulo_dtf.FRECUENCIAS_MUESTREO:
        origen = carpeta_sofa / f"HRIR_Default_{fs}.sofa"
        if not origen.is_file():
            continue
        if not (carpeta_sofa / modulo_dtf.nombre_dtf(fs)).is_file():
            modulo_dtf.escribir(carpeta_sofa, registrar)
        sofa = sf.read_sofa(str(origen), verify=False)
        dtf = sf.read_sofa(str(carpeta_sofa / modulo_dtf.nombre_dtf(fs)), verify=False)
        for s in (sofa, dtf):
            if int(s.Data_SamplingRate) != fs or np.asarray(s.Data_IR).shape[1] != 2:
                raise ValueError(f"se esperaba HRIR de dos orejas a {fs} Hz en {carpeta_sofa}")
        pos = np.asarray(sofa.SourcePosition, float)
        for etiqueta, datos in (("", sofa), ("DTF_", dtf)):
            canales, usadas = catorce_canales(np.asarray(datos.Data_IR), pos)
            ruta = carpeta_sofa / f"HeSuVi_{etiqueta}{fs}.wav"
            ganancia = escribir(ruta, canales, fs)
            hecho["archivos"][ruta.name] = {"ganancia": round(ganancia, 4), "muestras": canales.shape[1]}
            hecho["direcciones"] = usadas
    if not hecho["archivos"]:
        raise ValueError(f"no hay HRIR_Default_48000.sofa ni HRIR_Default_44100.sofa en {carpeta_sofa} "
                         "(HeSuVi trabaja a 48 o 44,1 kHz)")
    registrar(f"  HeSuVi: {', '.join(hecho['archivos'])}")
    return hecho
