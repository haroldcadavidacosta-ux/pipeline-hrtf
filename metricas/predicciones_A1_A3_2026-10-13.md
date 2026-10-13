# Predicciones: ITD e ILD de A3 frente a A1 (registradas antes de calcular)

Método: `metricas/` y `metricas_binaurales.py` tal como quedan en este commit, con los
parámetros de `config.py` (FC_ITD = 1500 Hz, Butterworth de orden 4 ida y vuelta, ILD por
tercio de octava de 500 Hz a 16 kHz, interpretada desde 1 kHz, umbrales 16 µs y 1 dB).
Rejilla Default, HRIR y HRTF sin ecualizar a 48 kHz. A1 es la referencia.

Hasta este commit solo se calcularon las pistas de A1 por separado (para desarrollar y
revisar el código). La comparación con A3 no se ha calculado.

## Predicción

- La AID de A3 (144,1 mm, de su ReceiverPosition) es 2,3 mm mayor que la de A1
  (141,8 mm). Con la sensibilidad de Kuhn (3/2c ≈ 4,37 µs/mm), se espera que |ITD| lateral de
  A3 supere a la de A1 en unos 10 µs.
- **P1.** En el plano horizontal, a azimut 90° y 270°: |ITD_C| − |ITD_A| entre 0 y 20 µs.
  La refuta un valor negativo o mayor que 20 µs en cualquiera de los dos.

Sin predicción numérica para la ILD: es la primera vez que se mide su repetibilidad.
