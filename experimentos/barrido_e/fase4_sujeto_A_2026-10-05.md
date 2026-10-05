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
