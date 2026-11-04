# Contexto del proyecto — pipeline HRTF

> Para ponerse al día: qué hay hecho, cómo montar el entorno en tu máquina, cómo están
> organizadas las carpetas y cómo trabajamos con Git. Si vas a tocar la limpieza de
> mallas, lee además [malla/LIMPIEZA.md](malla/LIMPIEZA.md).

---

## 1. Qué hemos hecho hasta ahora

El objetivo es sacar la HRTF de una persona a partir de un escaneo 3D de su cabeza hecho
con el celular (KIRI Engine). Todas las etapas, del escaneo a la HRTF en SOFA, funcionan y
están juntas en una sola app, `app.py`:

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
4. **Cortar el cuello.** Ya en mm, la malla se corta con un plano horizontal a −115 mm
   del eje de los canales y se tapa. Si la malla no llega a ese plano, se rechaza.
5. **Gradar.** `hrtf_mesh_grading` simplifica la malla una vez por oreja: triángulos finos
   en la oreja que se simula y más grandes lejos de ella. Los parámetros (`-x 0.5 -e 1
   -y 5`) salieron del barrido de -e (`experimentos/barrido_e/`).
6. **Exportar a Mesh2HRTF.** Blender, en segundo plano, arma `myHRTF_project_L` y
   `myHRTF_project_R`, listos para NumCalc.
7. **Simular y armar la HRTF.** NumCalc simula las dos orejas (tarda horas), se verifica que
   cada frecuencia convergió y se unen las dos orejas en SOFA (HRTF y HRIR), como lo hace
   `finalize_hrtf_simulation.py` de mesh2hrtf-tools.

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
| C1, B, D, E1 | aprobados |
| C2 | rechazado: tiene una cavidad grande en la nuca y tela doblada; hay que repetir el escaneo |
| A1, A3 | aprobados y cortados a −115 mm; el corte incluye un trozo del hombro izquierdo |
| A2 | rechazado: la espalda sigue unida al cuello y la malla no llega al corte de −115 mm |

### Pendiente

- **Validar la escala con personas reales**: medir a varios sujetos (orejas y
  circunferencia), limpiar y comparar. De ahí sale qué medida es la más fiable y el umbral
  de discrepancia, que hoy está sin fijar.
- La concha de la oreja sale poco profunda en todos los escaneos: es una limitación de la
  fotogrametría con celular y se resuelve al capturar, no en el código.
- **La primera HRTF completa** (A1, las dos orejas, 150 Hz a 24 kHz): la simulación
  ya está en la app, falta correrla. Su tiempo todavía no está medido.
- **Las métricas** (ITD, ILD, distorsión espectral) y la evaluación final.

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
.venv\Scripts\python.exe -m pip install "C:\Users\TU_USUARIO\Documents\PROYECTO DE GRADO\Mesh2HRTF\Mesh2HRTF-1.3.0"
```

La última línea instala el paquete de Python de Mesh2HRTF (lo que convierte la salida de
NumCalc en SOFA). La versión 1.3.0 **no está en PyPI**, así que se instala desde tu
carpeta de Mesh2HRTF (la que tiene `pyproject.toml`); cambia la ruta por la tuya.

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
el `.gitignore` lo excluye y cada máquina tiene el suyo. **Normalmente no hace falta**:
- los datos van por defecto a `datos\` dentro del proyecto;
- el programa del gradado (`grading\`) y el exportador de Mesh2HRTF (`mesh2hrtf_1.3.0\`)
  vienen con el repositorio;
- Blender se busca solo en `C:\Program Files\Blender Foundation\` (la versión más alta).

Solo si Blender está en otro sitio:

```python
BLENDER_EXE = r"D:\Programas\Blender\blender.exe"
```

**Blender sí hay que instalarlo** (gratis, blender.org): el exportador de Mesh2HRTF es un
complemento de Blender. No hace falta instalar el complemento: la app lo carga sola.

Para comprobar que todo funciona en tu máquina (la app también lo comprueba al arrancar
y lo muestra en los pasos 4, 5 y 6):
```
.venv\Scripts\python.exe gradar_malla.py --diagnostico
.venv\Scripts\python.exe exportar_malla.py --diagnostico
.venv\Scripts\python.exe simular_malla.py --diagnostico
```

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
7. **Exportar proyectos**: con el gradado aprobado, Blender (en segundo plano) exporta
   `myHRTF_project_L` y `myHRTF_project_R`, listos para NumCalc.
8. **Simular y armar la HRTF**: con la exportación aprobada (la carpeta se llena sola, o se
   escribe la de una sesión anterior), NumCalc simula las dos orejas. Tarda horas; se puede
   cortar y volver a lanzar, y lo ya simulado se conserva. Al terminar, la HRTF queda en
   `SOFA_myHRTF_project_merged\`. Desde la terminal: `simular_malla.py "<carpeta>"`.

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
    ├── app.py                       la app: puntos, medidas, limpieza, gradado, exportación, simulación, visor
    ├── limpiar_malla.py             la limpieza desde la terminal (la app la usa por debajo)
    ├── gradar_malla.py              el gradado desde la terminal (ídem); --diagnostico
    ├── exportar_malla.py            la exportación a Mesh2HRTF desde la terminal (ídem); --diagnostico
    ├── simular_malla.py             la simulación con NumCalc y la HRTF desde la terminal (ídem); --diagnostico
    ├── exportar_hesuvi.py           los WAV de HeSuVi de una carpeta ya simulada (la simulación ya los deja)
    ├── simular.bat                  simular con doble clic, sin VS Code ni navegador
    ├── vista_previa.py              renders de una malla desde 6 ángulos (PNG)
    ├── pipeline_hrtf.spec           empaquetado con PyInstaller (ver sección 3b)
    ├── requirements-empaquetado.txt solo para empaquetar
    ├── grading\                     hrtf_mesh_grading.exe + sus DLL (sí se sube; ver LEEME.md)
    ├── mesh2hrtf_1.3.0\             el exportador de Mesh2HRTF para Blender (sí se sube; ver LEEME.md)
    ├── numcalc\                     NumCalc.exe de 2022 + sus DLL, el del barrido (sí se sube; ver LEEME.md)
    ├── malla\                       matemática de la malla, sin interfaz (persona A)
    │   ├── alineacion.py            matriz de alineación por 3 puntos
    │   ├── limpieza.py              la limpieza completa y la escala
    │   ├── gradado.py               el gradado (llama a grading\hrtf_mesh_grading.exe)
    │   ├── exportacion.py           la exportación (lanza Blender y revisa los proyectos)
    │   ├── blender_exportar.py      lo que corre DENTRO de Blender: materiales, fuente, exportar
    │   ├── simulacion.py            NumCalc, convergencia, output2hrtf y unión de las dos orejas
    │   ├── convergencia.py          lee de NC*.out si cada frecuencia convergió
    │   ├── dtf.py                   la HRIR ecualizada al campo difuso (DTF), para escuchar
    │   ├── hesuvi.py                la HRTF en WAV de 14 canales para HeSuVi (7.1 virtual con audífonos)
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
| `myHRTF_project_L\` | proyecto de Mesh2HRTF con la fuente en la oreja izquierda, listo para NumCalc |
| `myHRTF_project_R\` | ídem, oreja derecha |
| `informe_exportacion.json` | nodos y elementos de cada proyecto, cara de la fuente y su distancia al canal marcado, veredicto |
| `myHRTF_project_*\Output2HRTF\` | los SOFA de cada oreja (output2hrtf de Mesh2HRTF) |
| `SOFA_myHRTF_project_merged\` | **la HRTF de las dos orejas**: `HRTF_<rejilla>_48000.sofa`, `HRIR_<rejilla>_48000.sofa` y `HRIR_<rejilla>_44100.sofa` (rejillas Default y ARI), `parameters.json` y figuras de diagnóstico |
| `SOFA_myHRTF_project_merged\HRIR_Default_*_DTF.sofa` | la HRIR **ecualizada al campo difuso** (DTF), para escuchar con programas que cargan SOFA: timbre neutro. **No para métricas**: la ILD y la fase por frecuencia no cambian, pero sí el espectro absoluto y los resúmenes (ILD de banda ancha, ITD por correlación) |
| `SOFA_myHRTF_project_merged\HeSuVi_*.wav` | para **escuchar** la HRTF en Windows con HeSuVi: `HeSuVi_DTF_48000.wav` (ecualizada al campo difuso, la recomendada) y `HeSuVi_48000.wav` (tal cual), también a 44,1 kHz |
| `informe_simulacion.json` | convergencia de cada frecuencia, tiempos, RAM, huellas de los SOFA, veredicto |

Cada limpieza o gradado **sobrescribe** lo anterior de esa carpeta. La exportación
también reemplaza los proyectos, **salvo que alguno ya tenga resultados de NumCalc**: en
ese caso no toca ninguno (hay que moverlo o renombrarlo a mano). Los parámetros están en
`config.py`: gradado (`GRADING_X_MM`, `GRADING_E_MM`, `GRADING_Y_MM`) y exportación
(`EXPORTACION_MESH2HRTF`: frecuencias, mallas de evaluación, método, etc.).

La fuente de cada proyecto es **una sola cara**: la más cercana a la entrada del canal
marcado con la app, (0, ±AID/2, 0) mm. El sistema de coordenadas del pipeline es el de
Mesh2HRTF (nariz +x, oreja izquierda +y, arriba +z, origen entre los canales) y las
mallas van en mm (`unit='mm'`).

### 3b. App empaquetada (sin Python)

```
.venv\Scripts\python.exe -m pip install -r requirements-empaquetado.txt
.venv\Scripts\python.exe -m PyInstaller pipeline_hrtf.spec --noconfirm
```

Deja `dist\pipeline_hrtf\` (~470 MB): se reparte la carpeta entera y se abre
`pipeline_hrtf.exe`. Lleva dentro el programa del gradado, el exportador de Mesh2HRTF y
NumCalc;
**Blender no va dentro** (hay que tenerlo instalado). Los datos van a `datos\` al lado
del `.exe`. `dist\` y `build\` no se suben.

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
