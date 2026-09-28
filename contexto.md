# Contexto del proyecto — pipeline HRTF

> Para ponerse al día: qué hay hecho, cómo montar el entorno en tu máquina, cómo están
> organizadas las carpetas y cómo trabajamos con Git. Si vas a tocar la limpieza de
> mallas, lee además [malla/LIMPIEZA.md](malla/LIMPIEZA.md).

---

## 1. Qué hemos hecho hasta ahora

El objetivo es sacar la HRTF de una persona a partir de un escaneo 3D de su cabeza hecho
con el celular (KIRI Engine). Las dos primeras etapas ya funcionan y están juntas en una
sola app, `app.py`:

1. **Marcar puntos y alinear.** Se carga el escaneo y se marcan con doble clic 7 puntos:
   la entrada de los dos canales auditivos, la punta de la nariz, y lo más alto (hélix) y
   lo más bajo (lóbulo) de cada oreja. Con los tres primeros la cabeza se lleva a un
   sistema fijo: **+x adelante, +y a la izquierda del sujeto, +z arriba, origen en el
   punto medio entre los dos canales**. La distancia entre canales se llama **AID**.
2. **Limpiar la malla.** Quita las piezas sueltas y la "cresta" que KIRI inventa en la
   coronilla, cierra la malla (reconstrucción Poisson), alisa el pelo sin tocar las orejas,
   repara túneles y autointersecciones, y pasa un **control de calidad** que dice si el
   escaneo sirve (APROBADA) o hay que repetirlo (RECHAZADA).
3. **Escalar a milímetros.** KIRI entrega cada escaneo con una **escala arbitraria**: no
   está en metros ni en milímetros, y cambia de un escaneo a otro. Para pasarlo a mm se
   usan medidas tomadas a la persona en casa, sin calibrador:
   - el **largo de cada oreja** con una regla (de lo alto del hélix a lo bajo del lóbulo);
   - la **circunferencia de la cabeza** con cinta métrica, con el mismo gorro del
     escaneo, por encima de cejas y orejas y paralela a la línea oreja–punta de la nariz.

   Con varias medidas se usa la mediana y la app muestra cuánto se aparta cada una.

### Decisiones que conviene conocer

- **La app es NiceGUI, no Streamlit.** La guía de arranque planeaba Streamlit + Plotly,
  pero la prueba de la Fase 5 falló: Plotly no deja seleccionar puntos en gráficos 3D.
  NiceGUI sí permite hacer clic sobre la malla. Los scripts de esas pruebas están en
  `pruebas/` y ya no se usan.
- **La matemática vive en `malla/`, sin interfaz**, para poder reutilizarla desde otros
  scripts o desde Blender. La interfaz está aparte, en `app.py`.
- **En la limpieza, las distancias van en fracciones del AID**, por lo de la escala
  arbitraria de KIRI.
- **Los túneles**: a veces Poisson deja "asas" de unos milímetros (genus > 0). Ahora se
  localizan y se reparan solos. Antes, volver a marcar los puntos 1–2 mm más a un lado
  podía convertir una malla aprobada en rechazada.

### Resultados con los escaneos que tenemos

| Sujeto | Resultado |
|---|---|
| C, B, D, E1 | aprobados |
| C2 | rechazado: tiene una cavidad grande en la nuca y tela doblada; hay que repetir el escaneo |

### Pendiente

- **Validar la escala con personas reales**: medir a varios sujetos (orejas y
  circunferencia), limpiar y comparar. De ahí sale qué medida es la más fiable y el umbral
  de discrepancia, que hoy está sin fijar.
- **Confirmar en qué unidades espera la malla Mesh2HRTF** antes de exportar.
- La concha de la oreja sale poco profunda en todos los escaneos: es una limitación de la
  fotogrametría con celular y se resuelve al capturar, no en el código.
- Las siguientes etapas del pipeline: corte del cuello, gradado de la malla, Mesh2HRTF y
  las métricas (ITD, ILD, distorsión espectral).

---

## 2. Montar el entorno en tu máquina

### 2.1 Herramientas (una sola vez)

1. **VS Code** (`code.visualstudio.com`) con la extensión **Python** de Microsoft.
2. **Git** (`git-scm.com`), instalación por defecto. Comprueba en una terminal:
   ```
   git --version
   ```
3. **Python 3.12 o superior** (`python.org`; nosotros usamos 3.14). Al instalar, marca
   *"Add python.exe to PATH"*. Comprueba:
   ```
   python --version
   ```
4. Cuenta de **GitHub** y la invitación al repositorio aceptada (llega por correo). El
   repositorio es privado: https://github.com/Jeronimo-Cardona/pipeline-hrtf

### 2.2 Clonar el repositorio (crea la carpeta del proyecto)

No crees la carpeta a mano: `git clone` la crea con todo dentro. Desde la carpeta donde
guardas el proyecto de grado:

```
cd "C:\Users\TU_USUARIO\Documents\PROYECTO DE GRADO"
git clone https://github.com/Jeronimo-Cardona/pipeline-hrtf.git pipeline_hrtf
```

La primera vez, Git abre una ventana para iniciar sesión en GitHub. Después abre la
carpeta `pipeline_hrtf` en VS Code (*Archivo → Abrir carpeta*; la carpeta, no un archivo
suelto).

### 2.3 Entorno virtual y paquetes

En la terminal de VS Code (`Ctrl+ñ`), dentro de `pipeline_hrtf`:

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Tarda unos minutos. **Usa siempre la ruta explícita `.venv\Scripts\python.exe`**, así da
igual si la terminal tiene el entorno activado o no. La carpeta `.venv` no se sube al
repositorio: cada uno crea la suya.

Comprueba que todo quedó bien:

```
.venv\Scripts\python.exe pruebas\comprobar_entorno.py
```

Tiene que salir `OK` en cada paquete y `Entorno .venv: SI`.

Si alguien añade un paquete nuevo a `requirements.txt`, después del `git pull` vuelve a
correr el `pip install -r requirements.txt`.

### 2.4 Tu `config_local.py`

`config.py` tiene rutas de ejemplo y se comparte. Tus rutas reales van en un archivo
**`config_local.py`** que creas tú en la raíz del proyecto. **No se sube al repositorio**:
el `.gitignore` lo excluye y cada máquina tiene el suyo. Es opcional: los datos van por
defecto a `datos\` dentro del proyecto, y el programa del gradado viene con el
repositorio (`grading\`), así que no hay que configurarlo. Ejemplo:

```python
BLENDER_EXE = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
MESH2HRTF_PATH = r"C:\Users\TU_USUARIO\Documents\PROYECTO DE GRADO\Mesh2HRTF\Mesh2HRTF-1.3.0\mesh2hrtf"
```

Para comprobar que el gradado funciona en tu máquina:
`.venv\Scripts\python.exe gradar_malla.py --diagnostico` (la app también lo comprueba al
arrancar y lo muestra en el paso 4).

**No pongas tus rutas en `config.py`**: si las subes, le cambias las rutas al otro en su
próximo `pull`.

### 2.5 Carpetas de datos

Crea a mano, dentro de `pipeline_hrtf`:

```
datos\entrada\
datos\salidas\
```

`datos/` no se sube al repositorio. Las mallas pesan decenas de MB y GitHub rechaza
archivos de más de 100 MB.

### 2.6 Arrancar la app

```
.venv\Scripts\python.exe app.py
```

Se abre `http://localhost:8080` en el navegador. Para pararla, `Ctrl+C` en la terminal.

Flujo dentro de la app:
1. Pega la ruta del `.obj` de KIRI y pulsa **Cargar**. Si esa malla ya tiene puntos
   guardados, aparece **"Usar los puntos guardados"**.
2. Marca los 7 puntos con **doble clic**. La cámara se mueve sola a lo que toca marcar, y
   el botón **Ver relieve / Ver textura** ayuda a ver bien la oreja.
3. **Guardar alineación y puntos.**
4. Escribe las medidas **en milímetros** (hay un desplegable "Cómo medir") y pulsa
   **Limpiar malla**. Tarda alrededor de un minuto.
5. Revisa el veredicto y las mallas de cada paso con los botones del visor.
6. **Gradar malla**: con la limpieza aprobada y alguna medida dada, gradúa los dos lados
   en unos segundos y deja las mallas listas para Mesh2HRTF.

---

## 3. Organización de carpetas

```
PROYECTO DE GRADO\
├── ESCANEOS KIRI ENGINE\            ← escaneos originales, FUERA del repositorio
│   └── B\
│       ├── 3DModel.obj / .mtl / .jpg          (lo que entrega KIRI)
│       ├── 3DModel_alineada.ply               (lo guarda la app al marcar)
│       └── 3DModel_landmarks.json             (los 7 puntos, el AID y la matriz)
│
└── pipeline_hrtf\                   ← el repositorio
    ├── .gitignore
    ├── requirements.txt             paquetes de Python
    ├── config.py                    parámetros compartidos, rutas de ejemplo
    ├── config_local.py              TUS rutas (no se sube)
    ├── contexto.md                  este archivo
    ├── guia_arranque_pipeline_hrtf.md   guía original de arranque
    ├── app.py                       la app: puntos, medidas, limpieza, gradado, visor
    ├── limpiar_malla.py             la limpieza desde la terminal (la app la usa por debajo)
    ├── gradar_malla.py              el gradado desde la terminal (ídem); --diagnostico
    ├── vista_previa.py              renders de una malla desde 6 ángulos (PNG)
    ├── pipeline_hrtf.spec           empaquetado con PyInstaller (ver sección 3b)
    ├── requirements-empaquetado.txt solo para empaquetar
    ├── grading\                     hrtf_mesh_grading.exe + sus DLL (sí se sube; ver LEEME.md)
    ├── malla\                       matemática de la malla, sin interfaz (persona A)
    │   ├── alineacion.py            matriz de alineación por 3 puntos
    │   ├── limpieza.py              la limpieza completa y la escala
    │   ├── gradado.py               el gradado (llama a grading\hrtf_mesh_grading.exe)
    │   ├── oreja.py                 métricas de la oreja y largo hélix–lóbulo
    │   └── LIMPIEZA.md              por qué cada paso es como es (LEER antes de tocar)
    ├── metricas\                    ITD, ILD, distorsión espectral (persona B, por empezar)
    ├── pruebas\                     scripts de prueba del entorno y los spikes
    └── datos\                       NO se sube
        ├── entrada\
        └── salidas\<carpeta del escaneo>\    lo que produce la limpieza
```

### Qué produce la limpieza

En `datos\salidas\<nombre de la carpeta del escaneo>\`:

| Archivo | Qué es |
|---|---|
| `1_limpia_abierta.ply` | sin piezas sueltas ni cresta, todavía abierta |
| `2_cerrada_poisson.ply` | cerrada |
| `3_suavizada.ply` | cerrada y alisada: la que sigue en el pipeline (unidades de KIRI) |
| `malla_final_mm.ply` | la misma, en milímetros y cortada en el cuello a `CORTE_CUELLO_MM` (solo si se dieron medidas) |
| `informe_limpieza.json` | todas las métricas, la escala y el veredicto |
| `3Dmesh_orig.stl` | `malla_final_mm.ply` en STL: la entrada del gradado (y de Mesh2HRTF) |
| `3Dmesh_graded_left.ply` | graduada: elementos finos en la oreja izquierda |
| `3Dmesh_graded_right.ply` | graduada: elementos finos en la oreja derecha |
| `informe_gradado.json` | caras de cada lado, canales estimados por el programa, veredicto |

Cada limpieza o gradado **sobrescribe** lo anterior de esa carpeta. Los parámetros del
gradado están en `config.py` (`GRADING_X_MM`, `GRADING_Y_MM`).

### 3b. App empaquetada (sin Python)

```
.venv\Scripts\python.exe -m pip install -r requirements-empaquetado.txt
.venv\Scripts\python.exe -m PyInstaller pipeline_hrtf.spec --noconfirm
```

Deja `dist\pipeline_hrtf\` (~470 MB): se reparte la carpeta entera y se abre
`pipeline_hrtf.exe`. Lleva dentro el programa del gradado; los datos van a `datos\` al
lado del `.exe`. `dist\` y `build\` no se suben.

**Ojo con las unidades en otros programas**: `malla_final_mm.ply` está en mm, pero
**Blender supone metros** y mostrará "240 m" para una cabeza de 240 mm. En Blender, pon
*Scene Properties → Units*: Unit Scale **0.001** y Length **Millimeters**. MeshLab no
tiene unidades: los números que muestra son mm.

---

## 4. Cómo trabajamos con Git

La idea: el repositorio en GitHub es la versión compartida, y cada uno tiene una copia en
su máquina. `pull` trae lo del otro, `commit` guarda tus cambios en tu copia y `push` los
sube.

### Todos los días

**Al empezar, antes de tocar nada:**

```
git pull
```

**Cuando termines algo que funciona:**

```
git status                       ← mira qué cambió antes de subir
git add .
git commit -m "Qué hiciste, en una frase"
git push
```

- **`git status` antes del `add`**: comprueba que no aparezca nada de `datos/`, `.venv/`
  ni `config_local.py`. Si aparece, algo falla en el `.gitignore`: avisa antes de subir.
- **El mensaje del commit tiene que decir algo**: "Corrige el signo del eje z en la
  alineación" sirve dentro de un mes; "arreglos" no.
- **Haz commits pequeños y a menudo**, de cosas que funcionan.

En VS Code todo esto también está en el icono de las ramitas de la barra izquierda: ves
los archivos cambiados, escribes el mensaje y pulsas *Commit* y *Sync*.

### Si los dos tocamos lo mismo

Si hiciste commits y el otro subió cambios antes, el `push` se rechaza. Haz `git pull`
(Git junta los cambios) y vuelve a hacer `git push`. Si los dos cambiaron las mismas
líneas de un archivo, Git marca el **conflicto** en ese archivo: VS Code muestra las dos
versiones para elegir. Se resuelve, se guarda, y luego `git add .`, `git commit` y
`git push`. Es tedioso pero no grave. Para evitarlo:

- `pull` siempre antes de empezar y `push` al acabar;
- cada uno en sus carpetas (persona A en `malla/`, persona B en `metricas/`);
- `config.py` es compartido: avisa antes de cambiarlo.

### Cambios grandes: una rama

Para algo que va a tardar varios días o que puede romper lo que ya funciona, trabaja en
una **rama** para que `main` siga funcionando:

```
git checkout -b nombre-de-la-rama      ← crea la rama y te cambia a ella
... commits normales ...
git push -u origin nombre-de-la-rama   ← la primera vez; después basta con git push
```

Cuando esté probado, se fusiona en `main`:

```
git checkout main
git pull
git merge nombre-de-la-rama
git push
```

Así se hizo la app integrada (rama `app-integrada`).

### Si instalas un paquete nuevo

Añádelo a mano a `requirements.txt`, haz commit y push, y avisa al otro para que corra
`pip install -r requirements.txt` después de su `pull`.

### Lo que nunca va al repositorio

Mallas, escaneos, resultados (`datos/`, `*.obj`, `*.ply`, `*.stl`, …), el entorno
(`.venv/`) y `config_local.py`. **Al repositorio va código, nunca datos.**
