# Cambios de Harold Cadavid (coautor), 13 de octubre de 2026

Hay dos ramas nuevas en el repo para revisar antes de unirlas a `main`. Son independientes y
`main` no cambió.

## 1. Rama `metricas`: ITD, ILD y sus errores (nivel 3 de la evaluación)

### Archivos nuevos

- `metricas/itd.py`: ITD por correlación cruzada de las HRIR, como en el marco teórico.
  - Paso bajo Butterworth de orden 4 a `FC_ITD` = 1500 Hz, aplicado ida y vuelta (fase cero).
  - Refinado sub-muestra con parábola.
  - ITD > 0 para fuentes a la derecha.
- `metricas/ild.py`: ILD por tercio de octava (valor eficaz por banda), de 500 Hz a 16 kHz. Se
  interpreta desde 1 kHz.
- `metricas/errores.py`: e_ITD y e_ILD con error absoluto medio, máximo, percentil 95 y % sobre
  el umbral. Como complemento, el promedio ponderado por Voronoi.
- `metricas_binaurales.py`: script que compara dos sujetos y deja informe, CSV y figuras en
  `datos/salidas/metricas/`. Uso:

  ```
  .venv\Scripts\python.exe metricas_binaurales.py --ref "A1" --sim "A3"
  ```

- `metricas/predicciones_A1_A3_2026-10-13.md`: la predicción, registrada antes de
  calcular, como en el barrido.

### Cambio en un archivo compartido

- `config.py`: se añadieron `ITD_ORDEN_FILTRO`, `ILD_BANDAS_HZ`, `ILD_INTERPRETAR_DESDE_HZ`,
  `UMBRAL_ITD_S` (16 µs) y `UMBRAL_ILD_DB` (1 dB). No se tocó nada de lo que ya había.

### Verificación y primer resultado

- Con señales sintéticas de ITD e ILD conocidas, el error fue menor de 0,05 µs.
- A3 frente a A1 (repetibilidad):
  - e_ITD medio de 10,8 µs y máximo de 37,9 µs.
  - La ILD es repetible hasta unos 1,6 kHz. Desde 2 kHz la diferencia media supera 1 dB, y
    llega a 2–4 dB entre 3 y 16 kHz.
  - La predicción de ITD (diferencia lateral entre 0 y 20 µs por la AID 2,3 mm mayor de
    A3) quedó refutada por poco: salieron 20,1 y 25,9 µs.

## 2. Rama `escala-bitragial`: escala con pie de rey (toca la limpieza y la app)

### Qué hace

- Permite escalar la cabeza con el ancho bitragial medido con pie de rey (de tragion a
  tragion).
- Es opcional: sin pie de rey todo funciona exactamente como antes.

### Cambios por archivo

- `app.py`:
  - Dos puntos opcionales después de los 7 de siempre: trago izquierdo (8) y trago derecho
    (9). Se puede guardar con 7 o con 9 puntos, no con 8.
  - Campo nuevo «Ancho bitragial (pie de rey)», con su protocolo en «Cómo medir».
  - El resultado de la limpieza muestra el bitragial escalado.
- `malla/oreja.py`: `PUNTOS_BITRAGO` y `bitrago()`, la distancia entre los tragos en la malla.
- `malla/limpieza.py`:
  - `escalar()` y `limpiar_auto()` reciben `bitrago_mm`.
  - Si se da, manda el bitragial. Las orejas y la circunferencia quedan de control, y su
    `escala.discrepancias` es directamente el error del método casero frente al pie de rey.
  - `--aid-mm` sigue teniendo prioridad si se usa.
- `limpiar_malla.py`: opción `--bitrago-mm`.
- `malla/LIMPIEZA.md`: documentado en el paso 7 (Escala).

### Lo que falta probar

Marcar los 9 puntos y limpiar un escaneo real con una medida de pie de rey. Solo se probó con
una malla sintética y viendo el campo en la app.

## Cómo traer las ramas

```
git fetch
git switch metricas
git switch escala-bitragial
```

Para volver: `git switch main`. Cuando estés de acuerdo, se unen a `main` con merge o con un
pull request en GitHub.

## Otros dos puntos

- `comprobar_numcalc()` en `malla/simulacion.py` no captura `OSError`. En el PC de Harold,
  Windows bloqueaba `NumCalc.exe` (Control inteligente de aplicaciones) y la app se caía al
  arrancar, en vez de mostrar el aviso.
- En el paper se actualizaron el marco y la metodología para incluir la escala con pie de rey
  (con la cita de la ISO 7250-1) y se arreglaron las citas rotas.
