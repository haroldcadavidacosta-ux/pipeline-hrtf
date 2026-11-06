# Repetibilidad en los participantes C y E: criterios registrados antes de calcular

Registrado el 2026-11-05. Hasta este momento no se ha calculado ninguna comparación entre las
HRTF de C1 y C3 ni entre las de E1 y E2, ni sus rasgos frente a HUTUBS. Lo único conocido son los
informes de limpieza y de simulación de cada captura (escala, AID, convergencia).

Pares: **C3 frente a C1** y **E2 frente a E1**, con la captura más antigua como referencia, igual
que A1 en el par A3–A1. Se recalcula también A3–A1 con el mismo código, como comprobación contra
las tablas de la tesis (XXVIII, XXIX y XXXII) y como referencia.

## Qué se repite y qué no

Se repiten sin cambios las pruebas de la Sección VII-G de la tesis (validez física, repetibilidad
y rasgos individuales), con los mismos estimadores, bandas, umbrales y criterios
(`metricas/predicciones_evaluacion_2026-10-24.md` y `metricas/predicciones_A1_A3_2026-10-13.md`).

No se repite el piso de ruido de la Sección VII-E: exige simular cada captura con el protocolo del
barrido (vector de diagnóstico, oreja izquierda, -y 10, tres valores de -e). De manera descriptiva
se calcula la SD 4–11 kHz de la oreja izquierda y la fracción de muescas perdidas con las HRTF de
producción de los tres pares. **No es un piso de ruido** y no cambia la regla ni su resultado.

## Diferencias de protocolo frente al par A, declaradas de antemano

- **Sesión.** A1 y A3 son de la misma sesión. Las capturas de C y de E son de fechas distintas:
  según la fecha de sus archivos, unas 8 semanas entre C1 y C3 y unas 5 entre E1 y E2. Estos pares
  miden también lo que cambia de un día a otro, como la colocación del gorro.
- **Escala.** A1 y A3 se escalaron con la mediana y sus medidas caseras. C y E se escalaron con el
  ancho bitragial, con una sola medida por persona usada en las dos capturas (145 y 150 mm). Por
  eso sus pares no incluyen el error de medir de nuevo.
- **Cuello.** C1 termina por encima del corte estándar y se cortó en −113,2 mm; las demás, en
  −115 mm.
- **Equipos.** C1, E1 y la oreja derecha de E2 se simularon en la torre (i5-10400F). C3 y la oreja
  izquierda de E2 se simularon en el portátil (i5-12450H). Mismo NumCalc (mismo SHA-256).

## Predicciones

**Validez (V1).** Cada rasgo de C1, C3, E1 y E2 queda dentro del rango de HUTUBS (percentiles 2,5
a 97,5), y el nivel entre 150 y 450 Hz, a menos de 1 dB de 0 dB. Cada rasgo fuera se reporta; el
rango no se ajusta. Con el bitragial, las AID de estas capturas (124–131 mm) son menores que las
de A (142–144 mm), así que puede haber ITD por debajo del rango; se reporta igual.

**Repetibilidad, nivel espectral.** Descriptiva, sin umbral de aceptación. Se espera una SD de 2 a
3 dB en 4–11 kHz, como en A. Un valor mayor se reporta como tal.

**Repetibilidad, ITD (P1).** Con la misma sensibilidad y el mismo margen de ±10 µs de la predicción
de A (Kuhn, 3/2c ≈ 4,37 µs/mm), a azimut 90° y 270°, elevación 0°. La refuta un valor fuera del
intervalo en cualquiera de los dos:

| Par | ΔAID (informes de limpieza) | Esperado | Intervalo de \|ITD\| evaluada − \|ITD\| referencia |
|---|---|---|---|
| C3 − C1 | 123,54 − 124,99 = −1,45 mm | −6,3 µs | −16,3 a +3,7 µs |
| E2 − E1 | 131,29 − 131,03 = +0,26 mm | +1,1 µs | −8,9 a +11,1 µs |

**Repetibilidad, ILD.** Sin predicción numérica; se reporta igual que en A.

**Rasgos individuales.** Para cada par, por separado, los criterios ya registrados:
- **P1 (decisivo).** SD intra en 4–11 kHz menor que el percentil 5 de la inter.
- **P2.** |e_ITD| intra menor que el percentil 5 de la inter.
- **P3.** |e_ILD| intra menor que el percentil 5 de la inter (bandas desde 1 kHz).
- SD en 12–16 kHz: descriptiva.

Cada par se reporta por separado. No se promedia para decidir un criterio.

## ¿Influye el equipo en el resultado, además de en el tiempo?

Se simulan de nuevo en la torre tres frecuencias que se simularon en el portátil (oreja izquierda
de E2, pasos 27, 54 y 80: 4,05, 8,1 y 12 kHz), y como control, una de la torre (oreja derecha de
E2, paso 54), sobre copias de los proyectos.

- **PC1.** En el portátil frente a la torre, la presión en la rejilla de evaluación difiere menos
  de 0,01 dB en todas las direcciones. Si no se cumple, las dos orejas de E2 y las capturas de cada
  par no son directamente comparables entre equipos y se reporta la diferencia.
- El control indica si NumCalc da el mismo resultado al repetirlo en el mismo equipo.

Solo se prueban tres frecuencias de un proyecto: es una comprobación puntual, no una demostración
para todas.
