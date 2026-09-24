# Limpieza de mallas de KIRI Engine — decisiones de diseño

Qué hace `malla/limpieza.py`, por qué, y qué se probó y se descartó. Leer antes de
cambiar parámetros: casi todos salieron de probar contra escaneos reales.

## Uso

```
.venv/Scripts/python.exe app_alineacion.py                       # 1. marcar oreja izq, oreja der, nariz
.venv/Scripts/python.exe limpiar_malla.py RUTA/3DModel.obj --aid-mm 131
.venv/Scripts/python.exe vista_previa.py comparacion.png RUTA/3DModel_alineada.ply datos/salidas/<sujeto>/3_suavizada.ply
```

Salida en `datos/salidas/<carpeta de la malla>/`:

| Archivo | Qué es |
|---|---|
| `1_limpia_abierta.ply` | sin piezas flotantes ni cresta; abierta arriba y en el cuello |
| `2_cerrada_poisson.ply` | cerrada (Poisson), sin alisar |
| `3_suavizada.ply` | cerrada y con el casco alisado — **la que sigue en el pipeline** |
| `malla_final_mm.ply` | `3_suavizada` escalada a milímetros (solo si se dio una medida) |
| `informe_limpieza.json` | métricas de cada paso + `control_calidad` (`aprobado`, `fallas`, `avisos`) |

Código de salida 0 = aprobada, 1 = hay que repetir el escaneo.

Todo trabaja en el sistema alineado (+x adelante, +y izquierda, +z arriba, origen
interaural) y **todas las distancias están en fracciones del AID**, porque KIRI entrega
cada escaneo con una escala arbitraria (la misma persona dio AID 0.438 y 0.602).

## Pasos y por qué

1. **Piezas flotantes → quedarse con la componente conexa más grande.** `Remove isolated
   pieces wrt diameter` con el 10 % por defecto NO sirve: en C la pieza suelta más
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
4. **Alisado del casco** (`suavizar_casco`): la superficie se trata como un relieve sobre
   el elipsoide; se difunde la distancia al elipsoide y se mueve cada vértice sobre la
   normal del elipsoide. Quita pelo, pozos y pliegues **sin encoger** la cabeza (un
   Laplaciano sí la encoge). Cubre desde las cejas hacia arriba y la nuca detrás de las
   orejas (nudos y pliegues del gorro). **Nunca toca las orejas** (radio 0.30 AID).
5. **Autointersecciones**: se borran las caras que se cruzan con un margen, se cierra el
   hueco y se alisa solo el parche (alisar sin borrar las empeoraba).
6. **Control de calidad**: una pieza, cerrada, manifold, genus 0, sin autointersecciones,
   proporciones del cráneo plausibles y, si hay escala, AID dentro de
   `config.AID_MIN_MM`–`AID_MAX_MM`. Avisa (sin bloquear) si una concha salió poco
   profunda o si no hay escala.
7. **Escala**: `--aid-mm` (factor directo) o `--circunferencia-mm` (contra el perímetro
   horizontal máximo sobre las orejas). Con las dos se usa el AID y se exige que
   coincidan al 2 %.

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
| C, D, E1, B | aprobadas |
| C2 | rechazada (genus 8): el escaneo tiene una cavidad grande en la nuca y tela doblada |

## Pendiente / abierto

- **Qué mide `--aid-mm`**: los landmarks marcan la **entrada del canal**; un calibrador
  mide **trago a trago**, que es más ancho. Hay que definir un solo protocolo (o marcar
  los tragos en la app, o usar la circunferencia) y validarlo midiendo personas reales.
- **Circunferencia/AID** sale entre 4.2 y 4.7 según el sujeto (y 6 % distinta entre los
  dos escaneos de C). Validar contra cinta métrica antes de confiar en ella.
- **Concha poco profunda en todos** (0–9 mm contra ~10–15 mm reales): limitación de la
  fotogrametría con celular. Se resuelve en la captura, no aquí. El umbral del aviso
  (`PROFUNDIDAD_CONCHA_MIN`) es provisional.
- Confirmar las unidades que espera Mesh2HRTF antes de exportar.
- Los rangos del control de calidad salieron de solo 4 sujetos buenos.
