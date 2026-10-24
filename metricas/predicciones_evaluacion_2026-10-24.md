# Evaluación del prototipo con datos ya obtenidos: criterios registrados antes de calcular

Método: `evaluacion_prototipo.py` y `metricas/` tal como quedan en este commit. Sin pruebas
externas: solo las HRTF de producción de A1 y A3 y la base pública HUTUBS
(Brinkmann et al., 2019; descargada de sofacoustics.org el 24-10-2026). Hasta este commit no se
ha calculado ninguna comparación contra HUTUBS ni la SD entre A1 y A3. Lo único ya
conocido es la ITD/ILD entre A1 y A3 (`metricas/predicciones_A1_A3_2026-10-13.md`).

## Datos y tratamiento común

- HRIR sin ecualizar a 44,1 kHz: `HRIR_Default_44100` del prototipo (294 muestras, 1850
  direcciones) y `ppN_HRIRs_simulated` de HUTUBS (256 muestras, 1730 direcciones). FFT de 294
  muestras para todas (las de HUTUBS se completan con ceros), de modo que todas quedan en líneas
  de 150 Hz, como la simulación del prototipo.
- Personas de HUTUBS: todas las disponibles salvo pp1 y pp96 (maniquí FABIAN) y pp88 (misma
  persona que pp22). pp22 y pp88 solo se usan como referencia de repetición medida.
- Mismos estimadores para todos: ITD por correlación cruzada (FC_ITD = 1500 Hz) e ILD por tercio
  de octava, interpretada desde 1 kHz; SD por dirección del marco en 4–11 y 12–16 kHz.
- Promedios sobre direcciones ponderados por el área de Voronoi de cada rejilla, para que el
  promedio represente la esfera y sea comparable entre rejillas distintas.

## Forma 2: validez física

Rasgos de A1 y A3 frente al rango de las personas de HUTUBS (percentiles 2,5 a 97,5):
ITD a 90° y a 270° (elevación 0°), ITD máxima en valor absoluto y ILD a 90° en las bandas de 1,
2, 4, 8 y 16 kHz. Además, el nivel medio entre 150 y 450 Hz debe estar a menos de 1 dB de 0 dB.

- **V1.** Todos esos rasgos de A1 y de A3 quedan dentro del rango. Cada rasgo fuera se
  reporta como tal; no se ajusta el rango después de ver los datos.

## Forma 3: repetibilidad

SD por dirección entre A3 y A1 con las HRTF de producción (48 kHz, rejilla Default), en
4–11 y 12–16 kHz, con mapa direccional. Descriptiva: sin umbral de aceptación. Se espera que,
como en el piso de ruido del barrido (2,5 a 2,7 dB en 4–11 kHz, oreja izquierda), quede en
torno a 2 a 3 dB en 4–11 kHz.

## Forma 4: personalización (intra frente a inter)

Intra: A1 frente a A3 (misma rejilla). Inter: todos los pares de personas de HUTUBS
simuladas (misma rejilla entre sí). Ninguna comparación empareja direcciones de rejillas
distintas. Métricas: SD 4–11 kHz, SD 12–16 kHz, |e_ITD| medio y |e_ILD| medio (bandas ≥ 1 kHz).

- **P1 (decisiva).** SD intra en 4–11 kHz menor que el percentil 5 de la SD inter.
- **P2.** |e_ITD| intra menor que el percentil 5 de la inter.
- **P3.** |e_ILD| intra menor que el percentil 5 de la inter.
- SD en 12–16 kHz: descriptiva.

Si P1 se cumple, el ruido de la captura con celular es menor que la diferencia típica entre
personas, y el prototipo conserva rasgos individuales. Si no, la captura no distingue a una
persona de otra en las pistas espectrales.

Limitación declarada de antemano: intra e inter vienen de geometrías obtenidas de forma distinta
(fotogrametría con celular en A; las mallas de HUTUBS en la base) y de simulaciones
distintas. La comparación responde si el ruido de captura es menor que la diferencia entre
personas, no si la HRTF de A es exacta.

Como contexto (sin criterio), lo mismo con las HRTF medidas de HUTUBS: pp22 frente a pp88 (una
persona medida dos veces) dentro de la distribución de pares de personas distintas.
