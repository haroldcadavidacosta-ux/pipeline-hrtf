# Fase 4: cambio de sujeto para la prueba de repetibilidad

Escrito el 2026-10-05, **antes de escanear** al sujeto nuevo. Ninguna captura de A existe todavía. Este archivo va
al repositorio para que la fecha del commit lo certifique.

## El cambio

La prueba de repetibilidad se hará con **A**, no con B. No es posible contactar a B ni a C para
repetir capturas. Los escaneos de E no sirven: quedaron mal hechos.

El protocolo no cambia. Ya decía «escanear dos veces seguidas al mismo sujeto», sin nombrar a B: lo que se mide
es el error del proceso de captura (celular, KIRI, limpieza, puntos de referencia), y para eso basta con que las dos
capturas sean de la misma persona.

## Supuesto que entra

**El ruido de captura con A es representativo del de B.** Las SD del barrido se midieron en B y el
umbral saldrá de A. Es razonable, porque el ruido es del método, pero no está demostrado. Podría no cumplirse si
A difiere mucho en algo que afecte la captura (pelo sobre las orejas, una oreja con más pliegues). Se declara como
limitación.

## Protocolo (sin cambios respecto de la metodología)

1. Escanear a A dos veces seguidas con KIRI, en la misma sesión y de la misma forma. Medir orejas (regla) y
   circunferencia (cinta).
2. Pasar las dos capturas por el mismo pipeline: puntos, limpieza, escala, el mismo -e en el gradado, oreja izquierda.
   Una captura rechazada en la limpieza se repite; no se sustituye por otra de otro día.
3. Simular las dos con el protocolo del barrido: vector de diagnóstico (900 Hz a 24 kHz cada 300 Hz), oreja
   izquierda, el mismo NumCalc de 2022, convergencia leída de NC*.out.
4. Tomar una captura como referencia de la otra (la primera, A, como referencia de la segunda, B) y medir dos pisos
   de ruido con el mismo código de la fase 3: la SD media en 4–11 kHz y la fracción de muescas que sobreviven, con
   el mismo criterio de muesca.

Dos pasadas: primero el par a -e 2 (unas 0,7 h por simulación), después el par a -e 0,5 (unas 6 h por simulación, el
número definitivo, en el mismo pie que la tabla, cuya referencia es -e 0,5).

## Regla de decisión (la de la metodología)

Se elige el mayor -e cuya diferencia contra la referencia quede por debajo del piso de ruido **en los dos criterios**.
Valores del barrido en B, frente a -e 0,5:

| -e | SD 4–11 kHz (dB) | Muescas perdidas |
|---|---|---|
| 1 | 1,01 | 10 % |
| 1 -y 5 | 1,02 | 10 % |
| 2 | 1,44 | 16 % |
| 3 | 4,86 | 38 % |

## Réplica opcional

Si hay tiempo, simular también la captura A de A con -e 1 y compararla con su -e 0,5. Si la SD de 4–11 kHz se
parece a la de B (1,01 dB), el barrido se generaliza a una segunda cabeza y el supuesto de arriba pierde peso.
No cambia la regla de decisión; solo se reporta.

## Elección del par (2026-10-05, antes de simular)

Se hicieron tres capturas seguidas de A (A, B, C). El criterio para elegir el par es solo que la malla sea válida
con la misma regla del barrido; no depende de ningún resultado acústico:

| Captura | Limpieza | Corte del cuello a −115 mm (el de B) |
|---|---|---|
| A1 | aprobada | aplicado, un anillo |
| A2 | aprobada | **no aplicado**: la espalda sigue unida al cuello hasta −105 mm y la malla termina en −102 mm |
| A3 | aprobada | aplicado, un anillo |

**El par es A1 + A3, con A1 como referencia.** A2 queda fuera.

A1 solo llega al corte gracias a la corrección de la tapa del cuello en la limpieza (commit 6631606): con la
regla anterior perdía el cuello entero (terminaba en −71 mm). Las mallas aprobadas antes, incluida B, no
cambian con esa corrección.

**El corte sigue en −115 mm, la regla del barrido.** A tiene el hombro izquierdo a −92/−100 mm, a la altura del
fin de la barbilla, así que a −115 mm su malla incluye un trozo de hombro que B no tenía. No se analiza con
otra altura de corte: cambiaría la regla justo en la medición que define el umbral (decisión del autor). Queda como
limitación: el trozo de hombro puede variar entre capturas y sumarse al piso de ruido, sobre todo por debajo de unos
3–4 kHz.

## Primera pasada (-e 2) y preparación de la definitiva (-e 0,5)

**Resultado del par a -e 2 (orientativo):** piso de 2,54 dB en 4–11 kHz y 35 % de muescas perdidas; elige -e 2
(`datos/experimentos/barrido_e/fase4/informe_e2.md`). Ese piso incluye el error de gradar las dos capturas con -e 2;
la medición definitiva es el par a -e 0,5.

**Gradado de A1 a -e 0,5.** El gradador de 2022 se caía con la malla tal cual (fallo conocido, caótico: no se
cae con la misma malla cortada a −110 mm ni sin cortar). Se gradó al primer reintento con la misma malla escrita en
otro orden, sin mover ningún punto (commit 461a08a). El resultado depende un poco del orden (52 656 a 53 018 caras
en cinco órdenes; la usada tiene 52 590): queda como limitación. Ninguna malla anterior del barrido ni de A
necesitó reintento.

## Tope de frecuencia del par a -e 0,5 (2026-10-05, antes de simular)

**El par a -e 0,5 se simula de 900 Hz a 18,9 kHz (61 de las 78 frecuencias), igual para las dos capturas.**

- **Motivo:** la memoria del equipo. Por encima de 18,9 kHz, NumCalc estima entre 11 y 15,4 GB por frecuencia
  para A1 (13,0 GB como máximo para A3), y el equipo dispone de 11,8 GB con todo cerrado. En el barrido, el
  pico real fue el 95 % de lo estimado (B -e 0,5: 10,39 de 10,97 GB). Con el tope, lo más caro pide 10,46 GB.
  Gráfica: `datos/experimentos/barrido_e/fase4/ram_por_frecuencia.png`.
- **No cambia la regla:** usa la SD en 4–11 kHz y las muescas entre 4 y 14 kHz. Las bandas descriptivas (0,9–4 y
  12–16 kHz) también quedan enteras.
- **Mismo tipo de decisión que el límite inferior del vector** (900 Hz, también impuesto por la memoria) y que la
  exclusión de 23,4–24 kHz del análisis principal.
- **Lo que se pierde:** la descripción del par por encima de 19 kHz. Si hiciera falta, esas frecuencias se pueden
  simular después en un equipo con más memoria: cada frecuencia de NumCalc es independiente.
- Implementado en el conductor (`TOPE_HZ` en `fase2.py`), que comprueba antes de simular que las copias tienen
  exactamente el vector del barrido hasta 18,9 kHz.
