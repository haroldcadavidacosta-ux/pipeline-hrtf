# Limpieza de mallas de KIRI Engine — decisiones de diseño

Qué hace `malla/limpieza.py`, por qué, y qué se probó y se descartó. Leer antes de
cambiar parámetros: casi todos salieron de probar contra escaneos reales.

## Uso

Lo normal es hacerlo todo desde la app (marcar los 7 puntos, meter las medidas, limpiar
y ver el resultado):

```
.venv/Scripts/python.exe app.py
```

La app corre `limpiar_malla.py` por debajo, así que también se puede usar a mano:

```
.venv/Scripts/python.exe limpiar_malla.py RUTA/3DModel.obj --oreja-izq-mm 63 --oreja-der-mm 62 --circunferencia-mm 572
.venv/Scripts/python.exe vista_previa.py comparacion.png RUTA/3DModel_alineada.ply datos/salidas/<sujeto>/3_suavizada.ply
```

Salida en `datos/salidas/<carpeta de la malla>/`:

| Archivo | Qué es |
|---|---|
| `1_limpia_abierta.ply` | sin piezas flotantes ni cresta; abierta arriba y en el cuello |
| `2_cerrada_poisson.ply` | cerrada (Poisson), sin alisar |
| `3_suavizada.ply` | cerrada, con el casco y la cara alisados — **la que sigue en el pipeline** |
| `malla_final_mm.ply` | `3_suavizada` escalada a milímetros y cortada en el cuello (solo si se dio una medida) |
| `informe_limpieza.json` | métricas de cada paso + `control_calidad` (`aprobado`, `fallas`, `avisos`) |

Código de salida 0 = aprobada, 1 = hay que repetir el escaneo.

Todo trabaja en el sistema alineado (+x adelante, +y izquierda, +z arriba, origen
interaural) y **todas las distancias están en fracciones del AID**, porque KIRI entrega
cada escaneo con una escala arbitraria (la misma persona dio AID 0.442 y 0.602: `C1` y `C2`).

## Pasos y por qué

1. **Piezas flotantes → quedarse con la componente conexa más grande.** `Remove isolated
   pieces wrt diameter` con el 10 % por defecto NO sirve: en C1 la pieza suelta más
   grande medía el 25 % del diámetro de la malla.
2. **La "cresta" no es una aleta delgada: es una carpa** que KIRI inventa sobre la
   coronilla que el celular no vio (la textura ahí es del fondo). Se ajusta un elipsoide
   al cráneo con la banda lateral (0.25–0.85 AID de altura, sin la cara) y en el casquete
   se quita lo que no coincide con él en posición o normal. También se quitan los
   pliegues (normal hacia adentro) de la mitad superior.
   - El elipsoide lleva la restricción **radio vertical = radio lateral**: las paredes
     laterales casi verticales no informan la curvatura de arriba y sin la restricción el
     ajuste da un cilindro.
3. **Poisson** con: datos reales + puntos del elipsoide solo en el casquete (desplazados
   con un promedio gaussiano para empalmar sin escalón) + una tapa plana en el cuello.
   - La tapa usa el contorno real de la sección (regla par-impar). Con el casco convexo
     la tapa se salía del cuerpo y Poisson hacía túneles.
   - Si sale con túneles (genus > 0) se repite con tolerancias más estrictas
     (`TOLERANCIAS`).
   - **Altura de la tapa del cuello.** La regla es el punto más alto del borde abierto por
     debajo de las orejas, más `MARGEN_CUELLO`. Supone que ese borde es un anillo más o
     menos horizontal alrededor del cuello. En A1 no lo era: KIRI captó hombros y
     torso, pero por detrás la espalda quedó cortada alta (−74 mm, 19 cm detrás de los
     canales), y la tapa subió a −71 mm y se llevó el cuello entero. Ahora se busca además
     el plano más bajo (hasta `CUELLO_MAS_BAJO`, cada `PASO_CUELLO`) en que el trozo de la
     cabeza por encima no toca el borde abierto (`plano_cuello_mas_bajo`): ahí el cuello es
     un anillo completo. Si queda al menos `BAJADA_CUELLO_MIN` por debajo de la regla del
     borde, la tapa va en ese plano y a Poisson solo entra el trozo de la cabeza
     (`cabeza_sobre_plano`); los trozos sueltos, como esa espalda, quedan fuera. Si no, se
     usa la regla del borde tal cual. En los escaneos aprobados antes (C1, B,
     D, E1) la búsqueda cae a menos de 0,02 AID de la regla del borde, así
     que siguen exactamente igual. Queda en `informe["tapa_cuello"]` (`regla`, `z_AID`).
   - **Lo que no arregla:** si la espalda sigue unida al cuello por encima del corte (A
     B: hasta −105 mm), no hay anillo limpio más abajo y la malla termina por encima del
     corte en mm, y la malla se rechaza (paso 8).
4. **Alisado del casco** (`suavizar_casco`): la superficie se trata como un relieve sobre
   el elipsoide; se difunde la distancia al elipsoide y se mueve cada vértice sobre la
   normal del elipsoide. Quita pelo, pozos y pliegues **sin encoger** la cabeza (un
   Laplaciano sí la encoge). Cubre desde las cejas hacia arriba y la nuca detrás de las
   orejas (nudos y pliegues del gorro). **Nunca toca las orejas** (radio 0.30 AID).
4b. **Alisado de la cara** (`alisar_cara`, `PASOS_HC_CARA = 10`): el casco no cubre la
   cara, y su ruido fino (cejas, pestañas, reflejos de los ojos, barba, poros) llegaba
   intacto al gradado, que lo toma por curvatura y lo llena de elementos. 10 pasadas de
   HC Laplaciano en toda la cabeza con la misma protección de las orejas (0 dentro de
   0.30 AID, entrada gradual hasta 0.45).
   - C1, gradado izquierdo (`-x 0.5 -y 10`): 47 378 → 39 104 caras; solo la cara
     14 688 → 9 365. Mueve < 1 mm el 99 % de la cara (máx. ~3 mm, en los pelos de las
     cejas), la punta de la nariz 0.6 mm, volumen −0.17 %. Métricas de oreja idénticas.
   - **Probado y descartado**: Taubin (×10–×100) se queda corto (−5 %); el de dos pasos
     de MeshLab empeora (+6 %) porque conserva los bordes finos, que son justo el ruido.
     HC ×20/×40 ahorran poco más (−21 %/−24 %) y ya mueven la nariz 1–1.8 mm.
   - Aun así, más de la mitad de las caras graduadas son de la oreja, que no se alisa.
5. **Autointersecciones**: se borran las caras que se cruzan con un margen, se cierra el
   hueco y se alisa solo el parche (alisar sin borrar las empeoraba).
5b. **Túneles** (`reparar_tuneles`): si Poisson deja asas (genus > 0), se localiza cada
   una y se repara igual que las autointersecciones: borrar su caja + `MARGEN_TUNEL`,
   cerrar el agujero, alisar el parche. Solo actúa si hay túneles, así que las mallas que
   ya salían con genus 0 quedan idénticas.
   - **Por qué hacía falta**: B aprobaba con unos landmarks y daba genus 2 con otros
     marcados a 1–3 mm (1.25° de giro), dentro de la precisión de un clic. Los dos túneles
     eran de ~3 mm: uno en la coronilla (unión relleno–datos) y otro en la nuca detrás de
     la oreja izquierda (pliegues del gorro). Los reintentos con `TOLERANCIAS` no lo
     arreglaban: solo actúan en el casquete.
   - **Cómo se localiza**: el genus de un trozo de malla sale de Euler con bordes,
     χ = V − E + F = 2·piezas − 2·genus − bordes (`genus_region`). Un túnel solo cuenta
     si el trozo lo contiene entero. Se barre un plano por cada lado de cada eje
     (búsqueda binaria, `PASO_BARRIDO`): el genus salta donde el plano deja de cortar el
     túnel, y eso da su caja (`localizar_tunel`).
   - **Salvaguardas**: no se toca un túnel de más de `TUNEL_MAX` (0.10 AID, ~15 mm: es un
     defecto del escaneo) ni uno a menos de `RADIO_OREJA` de un canal (cambiaría la
     acústica del pabellón); en esos casos la malla sigue rechazada. Si el parche no baja
     el genus se reintenta con el doble de margen y, si tampoco, se deja como estaba.
   - Queda en `informe["tuneles"]`: cuántos, sus cajas en AID y las caras borradas.
6. **Control de calidad**: una pieza, cerrada, manifold, genus 0, sin autointersecciones,
   proporciones del cráneo plausibles y, si hay escala, AID dentro de
   `config.AID_MIN_MM`–`AID_MAX_MM`. Avisa (sin bloquear) si una concha salió poco
   profunda o si no hay escala.
7. **Escala**: con medidas que cualquiera puede tomar en casa (no hace falta calibrador):
   - `--oreja-izq-mm`, `--oreja-der-mm`: largo de la oreja con regla, de lo alto del
     hélix a lo bajo del lóbulo; se compara con la distancia entre esos dos puntos
     marcados en la malla (el JSON de landmarks los trae si se marcaron en `app.py`).
   - `--circunferencia-mm`: con cinta, contra el perímetro horizontal máximo sobre las
     orejas (ver "Circunferencia" abajo para el protocolo).
   - Con varias se usa la **mediana** de sus factores: con tres, una medida mala no
     arrastra la escala, y en `escala.discrepancias` se ve cuál se aparta. Es
     provisional: falta validar cuál de las medidas es más fiable. El umbral de
     discrepancia (`DISCREPANCIA_OREJAS_MAX`) está en `None` (solo se informa) hasta
     tener medidas reales.
   - `--bitrago-mm` (opcional, con pie de rey): ancho bitragial, de tragion a tragion (la
     muesca justo encima de cada trago). Se compara con la distancia entre los dos tragos
     marcados en `app.py` (puntos 8 y 9, opcionales; `informe["bitrago_modelo"]`). Si se
     da, **manda él** y las medidas caseras quedan de control: su `escala.discrepancias`
     frente al bitragial es directamente el error del método casero. Se eligió el
     bitragial porque es la medida de instrumento más cercana al AID, que gobierna la ITD
     (en A1 frente a A3, 2,3 mm de AID fueron ~20–26 µs de ITD lateral). Con los
     tragos marcados, el informe da `escala.bitrago_mm` aunque no se use para escalar.
   - `--aid-mm` sigue disponible (factor directo; si se da, manda él y la circunferencia
     es control al 2 %), pero mide entre ENTRADAS de canal, no trago a trago.
   - Después de escalar, el control de calidad exige el AID dentro de
     `config.AID_MIN_MM`–`AID_MAX_MM`: atrapa errores gruesos de cualquier medida.
8. **Corte del cuello** (`cortar_cuello`): sobre `malla_final_mm.ply`, plano horizontal
   en `config.CORTE_CUELLO_MM` (mm respecto del eje de los canales; −115, el del barrido de -e) y
   tapa plana. Va en mm, así que solo se hace si hay escala. Quita superficie que el
   gradado igual llenaría de elementos: en B, 67 296 → 63 256 caras graduadas a
   −150 mm y 56 200 a −100 mm (`-x 0.5 -y 10`).
   - **Corte exacto** (`cortar_por_plano`): las caras que cruzan el plano se parten justo
     en él; el punto de corte se crea una vez por arista, así el borde queda sin grietas.
     Los puntos casi coincidentes que deja un plano que roza un vértice se fusionan,
     **solo los que están sobre el plano**: con `meshing_merge_close_vertices` de MeshLab
     sobre toda la malla, en E1 se fusionaron dos vértices muy juntos de la
     punta de la nariz y abrió un agujero allí.
   - **Solo queda la pieza mayor**: el plano puede dejar sueltos trozos de hombro que
     suben por encima del corte (E1 a −150 mm: una isla de 17 × 12 mm), y
     **el programa de gradado se cae** (segfault) con piezas extra. Se cuentan en
     `piezas_sueltas_quitadas`.
   - **Tapa** (`tapar_lazo`): rejilla interior (3 aristas de paso, sin pegarse al borde)
     + Delaunay, quedándose con los triángulos de dentro, mirando hacia abajo.
   - **Probado y descartado**: `meshing_close_holes` de MeshLab para la tapa deja ~80 %
     de los triángulos volteados (tapa plegada sobre sí misma; el detector de
     autointersecciones no lo ve porque son coplanares). Recorte de orejas (*ear
     clipping*): tapa válida pero con triángulos larguísimos, y **el programa de gradado
     se cuelga** con ellos. Remallar la tapa con MeshLab: deja 2–3 triángulos volteados.
     Desplazar el plano hasta que no roce ningún vértice: imposible con ~600 000
     vértices (lo corría 2.4 mm).
   - **Solo se guarda si el resultado es sano**: una pieza, cerrada, orientación coherente, genus 0,
     normales hacia fuera y área de la tapa = área de la sección (sin solapes ni
     huecos). Si no, o si la malla ya termina por encima del plano, **se rechaza**: sin el
     corte estándar no es comparable con las demás. Queda en
     `informe["corte_cuello"]`.

## Circunferencia: qué mide la malla y cómo medir con cinta

`circunferencia()` busca el perímetro máximo en planos **horizontales del sistema
alineado** (paralelos al plano que pasa por los dos canales y la punta de la nariz),
entre 0.35 y 0.80 AID sobre el eje interaural. Probado en los 5 sujetos:

- **Es robusto en altura**: por encima de las orejas hay una meseta; en B da
  4.22 / 4.21 / 4.21 / 4.18 AID entre 0.30 y 0.45 AID (±1 %). Más abajo corta las orejas.
- **Es sensible a la inclinación**: inclinar el plano de 0° a +15° (frente más alta)
  cambia el perímetro entre 1 % y 3.5 % según el sujeto.
- **"El perímetro máximo" con planos inclinados NO sirve**: el máximo cae siempre en
  planos de −25°/−30° que pasan por la punta de la nariz y suben a la coronilla (un
  corte diagonal por la cara), 7–13 % por encima del horizontal. Por eso no se buscó el
  máximo en planos inclinados.

Protocolo de la cinta, para que mida lo mismo que la malla (provisional, sin validar):
**con el mismo gorro del escaneo puesto** (la malla mide el gorro; cada mm de holgura o
de pelo aplastado es ~1.1 % de escala), justo por encima de las cejas y de las orejas, y
**paralela a la línea oreja–punta de la nariz**, ajustada sin apretar.

## Probado y descartado

- **Rellenar con el elipsoide la franja de pliegues quitados** (debajo del casquete):
  en la nuca los datos se separan 1–2 cm del elipsoide, el relleno queda paralelo a
  ellos y Poisson crea 6–10 túneles. Tampoco sirvió desplazarlo por k-vecinos (saltos).
- **Alisar solo "donde no hay datos"**: los pozos de la nuca sí tienen datos (malos).
- **Segundo Poisson** sobre la malla alisada: no mejora y triplica el tamaño.
- **Alisar la oreja** (HC Laplaciano): baja el facetado pero también la profundidad de
  la concha (−9 % con 3 pasadas), que ya viene demasiado baja. El facetado de KIRI es
  *mayor* que el de la salida de Poisson.

## Resultados con los escaneos disponibles

| Sujeto | Resultado |
|---|---|
| C1, D, E1, B | aprobadas |
| C2 | rechazada (genus 8): el escaneo tiene una cavidad grande en la nuca y tela doblada |
| A1, A3 | aprobadas y cortadas a −115 mm (A1 gracias a la tapa del cuello del paso 3). A tiene el hombro izquierdo a −92/−100 mm, a la altura del fin de la barbilla: el corte a −115 incluye un trozo de hombro |
| A2 | rechazada: termina en −102 mm: la espalda sigue unida al cuello hasta −105 y el corte a −115 no se aplica |

## Pendiente / abierto

- **Validar la escala con personas reales**: medir a varios sujetos las dos orejas y la
  circunferencia (con el gorro), limpiar, y mirar `escala.factores` y
  `escala.discrepancias`. De ahí sale cuál de las medidas debe mandar (hoy: mediana) y el
  umbral `DISCREPANCIA_OREJAS_MAX` (hoy: sin fijar). La escala se decidió con medidas
  caseras (regla y cinta) porque la gente no tiene calibrador; `--aid-mm` queda solo
  para laboratorio.
- **Circunferencia/AID** sale entre 4.2 y 4.7 según el sujeto (y 6 % distinta entre los
  dos escaneos de C). No se sabe si esa variación viene de la circunferencia o de
  dónde se marcaron los canales (el AID); con orejas + circunferencia la escala ya no
  depende de los clics en los canales, solo la alineación.
- La precisión de la escala importa: un 3 % de error de tamaño corre un 3 % las muescas
  del pabellón en frecuencia (una muesca de 8 kHz, ~240 Hz).
- **Concha poco profunda en todos** (0–9 mm contra ~10–15 mm reales): limitación de la
  fotogrametría con celular. Se resuelve en la captura, no aquí. El umbral del aviso
  (`PROFUNDIDAD_CONCHA_MIN`) es provisional.
- ~~Confirmar las unidades que espera Mesh2HRTF antes de exportar.~~ Resuelto: la exportación
  declara `unit: mm` y `malla/exportacion.py` rechaza el proyecto si su `parameters.json` no
  dice mm.
- Los rangos del control de calidad salieron de solo 4 sujetos buenos.
