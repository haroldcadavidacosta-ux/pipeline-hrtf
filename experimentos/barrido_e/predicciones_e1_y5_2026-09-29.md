# Predicciones preinscritas: -e 1 -y 5

Escritas el 2026-09-29, **antes de simular** la condición. El gradado, la exportación y la estimación de RAM ya
están hechos (`experimentos/barrido_e/y5_preparar.py` → `datos/experimentos/barrido_e/e_1_y5/preparacion.json`);
ninguna frecuencia se ha simulado. Este archivo va al repositorio para que la fecha del commit lo certifique.

## La pregunta

La SD de -e 1 frente a -e 0,5 es 1,01 dB en 4–11 kHz y 3,11 dB en 12–16 kHz. Interpretación a poner a prueba:
**en 4–11 kHz manda la geometría de la pina; en 12–16 kHz manda la discretización de la cabeza.** -y 5 limita la
arista de la cabeza sin tocar la oreja, así que separa las dos causas.

## Hechos medidos antes de simular

| | -e 1 -y 10 (ya simulada) | -e 1 -y 5 |
|---|---|---|
| Caras | 21 360 | 31 738 |
| F = 2V − 4, cerrada | sí | sí |
| Caras en la oreja (esfera de 40 mm) | 6 666 | 6 660 |
| Arista media en la oreja (mm) | 1,67 | 1,67 |
| Hausdorff pina contra la original, RMS / máx (mm) | 0,081 / 1,12 | 0,081 / 1,10 |
| Arista más larga por cara, fuera de la oreja: mediana por caras (mm) | 4,39 | 4,62 |
| Ídem, mediana por área (mm) | 8,69 | 4,86 |
| Ídem, percentil 90 por caras (mm) | 9,39 | 5,45 |
| RAM estimada por NumCalc, paso más caro (GB) | 6,79 | 6,12 |
| Vector de frecuencias y parámetros de NC.inp | — | idénticos a -e 1 -y 10 |

**La oreja no queda exactamente igual.** El gradado rehace toda la malla. Entre las dos graduadas, dentro de la
esfera de 40 mm, la distancia es RMS 0,027 mm y máx 0,64 mm: un tercio del RMS que -e 1 ya tiene frente a la
original. Es la mejor separación posible con este gradador.

**La referencia (-e 0,5 -y 10) tampoco tiene la cabeza fina:** su arista mediana por área fuera de la oreja es
6,87 mm. Con -y 5 la cabeza de -e 1 queda más fina que la de la referencia.

## Predicciones de la frecuencia útil (malla/discretizacion.py, f = c / (6·h))

| | -e 1 -y 10 | -e 1 -y 5 |
|---|---|---|
| Oreja (h = mediana por caras) | 32,7 kHz | 32,5 kHz |
| Cabeza, con la estadística registrada (mediana por caras) | 13,0 kHz | 12,4 kHz |
| Cabeza, con una estadística de cola (percentil 90 por caras) | 6,1 kHz | 10,5 kHz |

La fórmula tal como quedó registrada (mediana por caras) **predice que -y 5 no mejora la cabeza**: -y solo recorta
la cola de aristas largas y la mediana no la ve. Si la SD de 12–16 kHz baja con -y 5, la idea de λ/6 puede
seguir en pie, pero la estadística correcta para la fórmula es la de cola, no la mediana: el módulo se corrige.

## Predicciones de la distorsión espectral

Todas son SD media sobre direcciones (Default, ponderada por área) en la banda indicada, con el mismo análisis de
la fase 3 (`fase3_analisis.py`), sobre las frecuencias comunes.

### A. Contra la referencia -e 0,5 (las que pidió el autor)

| Banda | -e 1 -y 10 (medido) | Predicción para -e 1 -y 5 | Qué la refuta |
|---|---|---|---|
| 4–11 kHz | 1,01 dB | **0,85 a 1,15 dB** (cambia poco: la oreja es la misma) | < 0,85 dB: la cabeza sí afecta la banda de la pina y la interpretación está mal |
| 12–16 kHz | 3,11 dB | **≤ 2,5 dB** (baja al menos un 20 %) | > 2,5 dB |

La de 4–11 kHz es la importante. La de 12–16 kHz es débil a propósito: como la referencia también tiene la cabeza
gruesa, la SD contra ella no puede bajar al nivel de la oreja sola, así que que baje poco no refutaría del todo la
hipótesis. Por eso la prueba decisiva es la B.

### B. Contra -e 1 -y 10 (misma oreja, distinta cabeza): la prueba decisiva

| Banda | Predicción para SD(-y 5 frente a -y 10) | Qué la refuta |
|---|---|---|
| 4–11 kHz | **≤ 0,5 dB** | > 0,8 dB: la cabeza pesa en la banda de la pina |
| 12–16 kHz | **≥ 1,5 dB y al menos el doble que en 4–11 kHz** | < 1,5 dB o menos del doble: la cabeza no explica la banda alta |

### Por hemisferio

Si la cabeza pesa en algún sitio de 4–11 kHz, será en el contralateral (la zona de sombra, lejos de la malla fina):
ahí -e 1 tiene 1,30 dB frente a 0,60 dB en el ipsilateral. Predicción: en la comparación B, en 4–11 kHz, la SD
contralateral es mayor que la ipsilateral, y la ipsilateral es ≤ 0,3 dB.

## Lo que no se predice

- **Convergencia en 23,4–24 kHz.** La divergencia de -e 1 -y 10 depende de la malla exacta (-e 0,98 y -e 1,02
  convergen), así que no se puede anticipar. Si -e 1 -y 5 diverge, esas frecuencias quedan excluidas igual que en
  la fase 2.
- **Tiempo.** Solo una estimación: unas 4,3 h de pared (interpolando entre -e 1 y -e 0,5 por número de caras).

## Cómo se corre

El mismo conductor de la fase 2, con el mismo NumCalc de 2022 y el mismo margen de RAM, en una carpeta aparte; el
análisis se añade a la fase 3 como condición secundaria, sin tocar la tabla principal hasta verla.
