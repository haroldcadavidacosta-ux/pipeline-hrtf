# Métricas de evaluación (persona B)

Esta carpeta es tuya: aquí va el cálculo de la **ITD**, la **ILD** y sus errores (el nivel 3 de la
evaluación del marco teórico). El pipeline ya produce HRTF completas en SOFA; tu parte las lee y
las compara contra una referencia. No hace falta correr la app ni tocar `malla/` para trabajar.

## Qué hay que calcular

Lo que dice el marco teórico (subsección «Evaluación»):

- **Error de ITD** por dirección Ω: `e_ITD(Ω) = ITD_sim(Ω) − ITD_ref(Ω)`.
- **Error de ILD** por dirección y por banda de tercio de octava f_c:
  `e_ILD(f_c, Ω) = ΔL_1/3^sim(f_c, Ω) − ΔL_1/3^ref(f_c, Ω)`.
- Se reportan el **error absoluto medio** y el **máximo**, y se comparan con los umbrales del
  marco (del orden de 16 µs para la ITD y 1 dB para la ILD).
- **El mismo estimador, con los mismos parámetros**, para la simulación y para la referencia: la
  ITD depende del método con que se estime. El estimador lo define la subsección del marco sobre
  la estimación de la ITD; `config.py` ya tiene `FC_ITD = 1500.0` (Hz) como parámetro compartido.

Los métodos (estimador, parámetros, bandas, cómo se resume el error) se **registran en git antes
de calcular sobre las referencias**, como se hizo en todo el barrido de -e: así nadie puede decir
que se eligieron después de ver los resultados.

## Los datos de entrada

**No están en git** (`datos/` y `*.sofa` están en el `.gitignore`): pídele a Jeronimo la carpeta
`SOFA_myHRTF_project_merged` de cada sujeto y ponla en
`datos\salidas\<sujeto>\SOFA_myHRTF_project_merged\`. Hoy está la de **A1** (58 MB).

| Archivo | Qué es | ¿Para métricas? |
|---|---|---|
| `HRTF_Default_48000.sofa` | HRTF compleja, 1850 direcciones, 160 frecuencias (150–24 000 Hz cada 150 Hz) | **Sí** |
| `HRIR_Default_48000.sofa` | Respuesta al impulso a 48 kHz, 320 muestras | **Sí** (para la ITD) |
| `HRTF_ARI_48000.sofa`, `HRIR_ARI_48000.sofa` | Lo mismo en la rejilla ARI (1550 direcciones) | Sí, si la referencia está en ARI |
| `HRIR_*_44100.sofa` | La HRIR remuestreada a 44,1 kHz (294 muestras) | Solo si la referencia está a 44,1 kHz |
| `HRIR_Default_*_DTF.sofa` | Ecualizada al campo difuso, **para escuchar** | **No** (ver abajo) |
| `HeSuVi_*.wav`, `*.pdf`, `*.jpeg` | Para escuchar y figuras de diagnóstico | No |

**Convenciones de los SOFA** (comprobadas en los archivos de A1):

- `SourcePosition`: esféricas, `[azimut °, elevación °, radio m]`. **Azimut 0° al frente, 90° a la
  izquierda, 270° a la derecha**; elevación de −90° (abajo) a +90° (arriba). Radio 1,5 m (Default)
  o 1,2 m (ARI).
- Segundo eje de los datos = oreja: **0 izquierda, 1 derecha**. Los receptores están en
  y = ±AID/2 (A1: +0,0710 y −0,0708 m); el origen es el punto medio entre las entradas de los
  canales (+x adelante, +y izquierda, +z arriba).
- HRTF: `Data_Real + 1j·Data_Imag`, forma `(direcciones, 2, frecuencias)`; frecuencias en `N`.
  Está **referida al campo libre en el centro de la cabeza**: a frecuencia baja vale ≈ 0 dB.
- HRIR: `Data_IR`, forma `(direcciones, 2, muestras)`, `Data_SamplingRate`, `Data_Delay = 0`.
  Desplazada 40 muestras para ser causal (la llegada cae entre las muestras 30 y 75).

Para leerlos (sofar y numpy ya están en `requirements.txt`):

```python
import numpy as np
import sofar as sf

s = sf.read_sofa(r"datos\salidas\A1\SOFA_myHRTF_project_merged\HRIR_Default_48000.sofa")
ir = np.asarray(s.Data_IR)              # (1850, 2, 320): dirección, oreja (0 izq, 1 der), muestra
fs = float(s.Data_SamplingRate)         # 48000
pos = np.asarray(s.SourcePosition)      # (1850, 3): azimut °, elevación °, radio m
```

## Contra qué se compara (las referencias)

| Referencia | Qué mide | Estado |
|---|---|---|
| **A3** (otra captura de la misma persona) | Repetibilidad de la captura con celular | Hay que simularla (Jeronimo, unas 11 h) |
| **HUTUBS**: HRTF medida del mismo sujeto cuya malla se simula | Error de la simulación frente a una medición | Faltan las HRTF medidas y simular en sus direcciones |
| **KU100** (dataset de KU Leuven, `DatasetRDR`): fotogrametría frente a láser | Referencia de la literatura | En el disco de Jeronimo; simulado por elementos finitos (no medido), 44 kHz, 5042 direcciones |

Mientras llegan, A1 sirve para **desarrollar y probar** los estimadores. Para comparar dos
conjuntos tienen que coincidir la frecuencia de muestreo (remuestrear si no) y las direcciones
(la misma rejilla, o la dirección más cercana con su error angular declarado).

## Lo que hay que saber antes de interpretar

- **No uses las DTF.** La ecualización divide las dos orejas por el mismo filtro: la ILD y la fase
  de cada frecuencia no cambian, pero en A1 la ILD de banda ancha cambia hasta 3,9 dB y la ITD
  por correlación cruzada hasta 15 µs, porque cambia el peso de cada frecuencia.
- **El hombro de A.** Su malla incluye un trozo del hombro izquierdo y no del derecho (con el
  corte estándar a −115 mm; no se puede quitar sin quitar el cuello). En la HRTF de A1 ya se ve
  una asimetría entre orejas para fuentes de atrás y abajo, entre 4 y 16 kHz. Está declarado como
  limitación; tu análisis es el que la cuantifica.
- **Cada oreja sale de una malla graduada distinta** (fina en su oreja, gruesa en la otra), como es
  normal en Mesh2HRTF. Las dos salen de la misma malla limpia, y cada una se aparta de ella del
  orden de 1 mm como mucho (el gradado usa `-e 1`).
- **La concha sale poco profunda** en los escaneos con celular: las muescas de la oreja son menos
  profundas que en HUTUBS (5,4 frente a 7,4 dB de mediana en A1).
- **La corrida manual de HUTUBS** que hay en el disco de Jeronimo tiene los receptores asimétricos
  (+75,9 y −86,8 mm): su origen no está entre los canales. Sirve para probar código, no como
  referencia.

## Reglas del repositorio

- Todo en español: código, comentarios, nombres.
- La matemática va en `metricas/`, **sin interfaz** (funciones que reciben arreglos y devuelven
  números), para poder usarla desde scripts o desde la app.
- Los parámetros compartidos van en `config.py` (`FC_ITD` ya está ahí); nada de números mágicos
  repartidos por el código.
- Los resultados van a `datos/` (no se suben). Al repositorio va código, nunca datos.
- Trabaja en tu propia rama (`git switch -c metricas`) y pide el merge cuando esté listo.
- Intérprete: `.venv\Scripts\python.exe` (cómo montar el entorno: `contexto.md`, sección 2). El
  paquete `mesh2hrtf` no hace falta para las métricas: `sofar`, `pyfar` y `numpy` bastan.

## Dónde está el resto

- `contexto.md`: qué hace cada etapa, cómo montar el entorno y la estructura de carpetas.
- Documento de metodología (pídele el enlace a Jeronimo): el plan de evaluación completo, el caso de
  A1 paso a paso y las decisiones tomadas.
- `experimentos/barrido_e/fase3_analisis.py`: código reutilizable de la distorsión espectral, los
  pesos de Voronoi por dirección (`pesos_voronoi`) y el detector de muescas (`notches_validos`).
