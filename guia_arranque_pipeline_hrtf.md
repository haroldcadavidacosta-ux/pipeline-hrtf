# Guía de arranque — pipeline HRTF

> Paso a paso completo, desde cero, para dos personas trabajando juntas.
> Al terminar tendrán: un repositorio compartido, el entorno funcionando en las dos
> máquinas, y la primera pieza del pipeline —marcar tres puntos sobre la malla y
> alinearla— probada sobre la cabeza de C.
>
> Tiempo estimado: una tarde entre los dos.

---

## El mapa

```
Fase 0   Repartir el trabajo y acordar la estructura        los dos juntos, 10 min
Fase 1   Instalar las herramientas                          cada uno, 20 min
Fase 2   Crear el repositorio y clonarlo                    uno crea, el otro clona
Fase 3   Entorno de Python y paquetes                       cada uno, 10 min
Fase 4   Comprobar que Streamlit funciona                   cada uno, 5 min
Fase 5   EL SPIKE: ¿llegan los clics 3D?                    cada uno, 5 min  ← crítico
Fase 6   La app de alineación                               uno de los dos
Fase 7   Probarla con la malla de C                    quien la escribió
Fase 8   La rutina de trabajo diaria                        los dos
```

**No se salten la Fase 5.** Ahí se decide si este camino sirve. Si falla, todo lo
que venga después hay que rehacerlo con otra herramienta, y es mejor descubrirlo
en cinco minutos.

---

## Fase 0 — Repartir el trabajo y acordar la estructura

**Diez minutos hablando, antes de tocar nada.**

### El reparto

Las piezas del pipeline son casi independientes, así que se pueden repartir sin
pisarse:

| | Se encarga de |
|---|---|
| **Persona A** | Malla y Blender: limpieza con PyMeshLab, alineación, corte del cuello, gradado, exportación headless |
| **Persona B** | Métricas y app: ITD, ILD, distorsión espectral, la interfaz de Streamlit |

Lo único que comparten es `config.py`, que conviene acordar entre los dos al
principio y después tocar poco.

### La estructura de carpetas

Acuerden esta y respétenla los dos, porque las rutas dependen de ella:

```
pipeline_hrtf/                 ← esto es el repositorio
├── .gitignore
├── requirements.txt
├── config.py                  ← va al repositorio, con rutas de ejemplo
├── config_local.py            ← NO va al repositorio, rutas reales de cada máquina
├── app_alineacion.py
├── metricas/
├── malla/
├── pruebas/
│   ├── hola.py
│   └── spike.py
└── datos/                     ← NO va al repositorio
    ├── entrada/               ← aquí las mallas
    └── salidas/               ← aquí lo que produce el pipeline
```

**Regla que no se rompe: al repositorio va código, nunca datos.** Las mallas pesan
decenas de megas y los SOFA cientos. GitHub rechaza archivos de más de 100 MB, y
aunque los aceptara, el repositorio sería inmanejable en una semana.

---

## Fase 1 — Instalar las herramientas

**Cada uno en su máquina.**

1. **VS Code** desde `code.visualstudio.com`.
2. Dentro de VS Code, la extensión **Python** de Microsoft. Icono de los cuadraditos
   en la barra izquierda, buscar "Python", instalar.
3. **Git** desde `git-scm.com`. Instalación por defecto, siguiente-siguiente.
   VS Code lo detecta solo al reiniciarse.
4. Cuenta en **github.com** si no la tienen.

Para comprobar que Git quedó bien, abran cualquier terminal y escriban:

```
git --version
```

Debe responder con un número de versión.

---

## Fase 2 — El repositorio

### Lo hace la persona A

**2.1 — Crear el repositorio en GitHub.** En github.com, botón *New*. Nombre:
`pipeline-hrtf`. **Privado** por ahora; lo pasan a público cuando entreguen.
No marquen ninguna casilla de inicializar con README.

**2.2 — Añadir al otro.** En el repositorio: *Settings → Collaborators → Add people*.

**2.3 — Crear la carpeta del proyecto** en su computador, por ejemplo:

```
C:\Users\Usuario\Documents\PROYECTO DE GRADO\pipeline_hrtf
```

**2.4 — Abrirla en VS Code.** *Archivo → Abrir carpeta*. Importante: abrir la
carpeta, no un archivo suelto.

**2.5 — Crear el `.gitignore` ANTES QUE NADA.** Este orden importa: si hacen
`git add` antes de tener el `.gitignore`, suben miles de archivos del entorno
virtual y luego cuesta sacarlos.

Nuevo archivo llamado exactamente `.gitignore` (con el punto delante):

```
# Entorno de Python
.venv/
__pycache__/
*.pyc

# Configuración local de cada máquina
config_local.py

# Datos: NO van al repositorio
datos/
*.obj
*.ply
*.stl
*.blend
*.blend1
*.sofa
*.inp

# Sistema
.DS_Store
Thumbs.db
```

**2.6 — Crear `config.py`** con rutas de ejemplo:

```python
"""Parámetros del pipeline. Única fuente de verdad.

Las rutas de este archivo son de ejemplo. Cada uno pone las suyas en
config_local.py, que no se sube al repositorio y sobreescribe lo de aquí.
"""

# --- Rutas (sobreescribir en config_local.py) -----------------------------
RUTA_DATOS = r"C:\ruta\de\ejemplo\datos"
BLENDER_EXE = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
MESH2HRTF_PATH = r"C:\ruta\de\ejemplo\Mesh2HRTF-1.3.0\mesh2hrtf"
GRADING_EXE = r"C:\ruta\de\ejemplo\bin\hrtf_mesh_grading.exe"

# --- Geometría ------------------------------------------------------------
CORTE_CUELLO_MM = -150.0          # respecto del eje interaural
AID_MIN_MM, AID_MAX_MM = 120.0, 200.0

# --- Estimadores ----------------------------------------------------------
FC_ITD = 1500.0                   # Hz

# --- Sobreescritura local -------------------------------------------------
try:
    from config_local import *    # noqa: F401,F403
except ImportError:
    pass
```

**2.7 — Crear `requirements.txt`**, para que los dos tengan los mismos paquetes:

```
streamlit>=1.35
plotly
trimesh
scipy
numpy
```

**2.8 — Subirlo todo.** En la terminal de VS Code (`Ctrl+ñ`):

```
git init
git add .
git commit -m "Estructura inicial del proyecto"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/pipeline-hrtf.git
git push -u origin main
```

La primera vez pedirá autenticarse con GitHub; se abre el navegador y se autoriza.

*Cómo saber que salió bien:* recarga la página del repositorio en GitHub y ahí
están los archivos.

### Lo hace la persona B

En la terminal, dentro de la carpeta donde quiera tener el proyecto:

```
git clone https://github.com/USUARIO_DE_A/pipeline-hrtf.git
```

Y abre esa carpeta en VS Code.

---

## Fase 3 — Entorno de Python

**Cada uno en su máquina, dentro de la carpeta del proyecto ya abierta en VS Code.**

**3.1 — Crear el entorno virtual.** `Ctrl+Shift+P`, escribir
`Python: Create Environment`, Enter.

- Tipo → **Venv**
- Intérprete → cualquier Python 3.10 o superior

*Qué deberías ver:* aparece una carpeta `.venv` en el Explorador, y abajo a la
derecha VS Code muestra el intérprete seleccionado.

**3.2 — Instalar los paquetes.** Abre la terminal con `Ctrl+ñ`.

*Comprueba antes:* al principio de la línea debe aparecer `(.venv)`. Si no,
cierra esa terminal con el icono de la papelera y abre otra.

```
pip install -r requirements.txt
```

Tarda uno o dos minutos.

**3.3 — Crear tu `config_local.py`** con tus rutas reales. No se sube al
repositorio, así que cada uno pone las suyas:

```python
RUTA_DATOS = r"C:\Users\TuUsuario\Documents\PROYECTO DE GRADO\pipeline_hrtf\datos"
BLENDER_EXE = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
MESH2HRTF_PATH = r"C:\Users\TuUsuario\Documents\PROYECTO DE GRADO\Mesh2HRTF\Mesh2HRTF-1.3.0\mesh2hrtf"
GRADING_EXE = r"C:\Users\TuUsuario\Documents\PROYECTO DE GRADO\Mesh2HRTF\mesh2hrtf-tools-C\bin\hrtf_mesh_grading.exe"
```

**3.4 — Crear las carpetas de datos** y copiar ahí `3Dmesh_orig.stl`:

```
datos\entrada\
datos\salidas\
```

---

## Fase 4 — Comprobar que Streamlit funciona

**Cada uno, cinco minutos.**

Crea `pruebas\hola.py`:

```python
import streamlit as st

st.title("Hola")
nombre = st.text_input("¿Cómo te llamas?")
if nombre:
    st.write(f"Mucho gusto, {nombre}")
```

En la terminal:

```
streamlit run pruebas/hola.py
```

*Qué deberías ver:* la terminal imprime `http://localhost:8501` y se abre el
navegador con la página. Escribe tu nombre y aparece el saludo.

La primera vez puede pedir un correo; pulsa Enter para saltarlo.

**Para pararlo:** `Ctrl+C` en la terminal.

### Lo único raro de Streamlit, y conviene entenderlo ya

Cada vez que el usuario toca algo, **Streamlit vuelve a ejecutar el script entero,
de arriba abajo**. No actualiza solo el trozo que cambió.

Compruébalo con esto:

```python
import streamlit as st, random
st.write("Número aleatorio:", random.random())
st.button("Pulsa aquí")
```

El número cambia en cada pulsación, aunque el botón no haga nada. De ahí salen las
dos únicas cosas que hay que saber: `st.session_state` para recordar cosas entre
ejecuciones, y `@st.cache_data` para no recargar la malla cada vez.

---

## Fase 5 — El spike (crítico)

**Cinco minutos, y de esto depende el resto.**

Crea `pruebas\spike.py`:

```python
import streamlit as st
import plotly.graph_objects as go

st.title("Prueba de clic en 3D")
st.write("Gira la escena arrastrando, y luego haz clic sobre una de las bolas.")

fig = go.Figure(go.Scatter3d(
    x=[0, 1, 2], y=[0, 1, 0], z=[0, 0, 1],
    mode="markers", marker=dict(size=14)))
fig.update_layout(height=500, margin=dict(l=0, r=0, t=0, b=0))

evento = st.plotly_chart(fig, on_select="rerun", key="spike")

st.write("Evento recibido:")
st.json(evento)
```

```
streamlit run pruebas/spike.py
```

**Haz clic sobre una bola.** Prueba varias veces y con distintas bolas: en 3D hay
que acertar bastante encima.

- **Si aparece un JSON con coordenadas** (`"points": [{"x": 1, "y": 1, "z": 0 ...`)
  → el camino está despejado, sigue a la Fase 6.
- **Si el JSON sale siempre vacío** → párate aquí. Hay que cambiar a NiceGUI, que
  resuelve el picking 3D de otra forma. No habrán perdido más de veinte minutos.

Suban el resultado al repositorio antes de seguir:

```
git add .
git commit -m "Entorno y pruebas básicas de Streamlit"
git push
```

---

## Fase 6 — La app de alineación

**La escribe uno de los dos.**

Prompt:

```
Crea una app de Streamlit en app_alineacion.py para marcar tres puntos sobre una
malla 3D y alinearla. Es la primera pieza de un pipeline de HRTF. No escribas
nada más del pipeline: solo esta app.

ENTORNO
- El entorno virtual .venv ya existe con streamlit, plotly, trimesh, scipy y numpy.
- Ya comprobé que los clics sobre un Scatter3d de Plotly llegan a Streamlit con
  st.plotly_chart(fig, on_select="rerun").
- Hay un config.py con rutas; úsalo para la ruta por defecto de la malla.

QUÉ DEBE HACER LA APP
1. Una caja de texto donde pego la ruta de un archivo de malla (.obj, .ply o .stl).
2. Cargar la malla con trimesh y mostrarla como nube de puntos con
   plotly.graph_objects.Scatter3d, para que se pueda girar y acercar.
   IMPORTANTE: la malla puede tener cientos de miles de vértices. Muestra solo una
   submuestra de unos 50.000 puntos para que el navegador vaya fluido, pero cuando
   el usuario haga clic, engancha el punto al vértice más cercano de la malla
   COMPLETA usando un KD-tree de scipy.
3. Pedir tres puntos, en este orden, uno a uno, indicando cuál toca en cada momento:
     1) entrada del canal auditivo IZQUIERDO
     2) entrada del canal auditivo DERECHO
     3) punta de la NARIZ
   Los puntos ya marcados se dibujan en otro color y con marcadores más grandes.
   Botones de "Deshacer" y "Empezar de nuevo".
4. Cuando haya tres puntos, calcular la matriz de alineación y mostrar el resultado.

LA MATEMÁTICA DE LA ALINEACIÓN (respétala exactamente)
Sistema de destino: +x adelante, +y hacia la izquierda del sujeto, +z arriba,
origen en el punto medio entre las dos entradas del canal auditivo.

    origen = (p_izq + p_der) / 2
    v_y    = p_izq - p_der
    aid    = norma(v_y)
    y      = v_y / aid
    v      = p_nariz - origen
    x      = v - (v·y) y        # quitar la componente sobre el eje interaural
    x      = x / norma(x)
    z      = cruz(x, y)         # sistema derecho
    R      = filas [x, y, z]
    T      = matriz 4x4 con R arriba a la izquierda y traslación -R·origen

QUÉ MOSTRAR AL FINAL
- El AID
- La caja envolvente de la malla original (sirve para saber si el archivo viene en
  milímetros o en metros)
- El residuo del alineado: tras aplicar T, la oreja izquierda debe quedar en
  (0, +aid/2, 0) y la derecha en (0, -aid/2, 0), y la nariz con y = 0.
  Muestra el máximo de esas desviaciones. Debe ser prácticamente cero.
- Aviso si el AID queda fuera del rango AID_MIN_MM–AID_MAX_MM de config.py
- Error si el residuo supera 1e-6

BOTÓN FINAL "Alinear y guardar"
- Guarda la malla transformada como <nombre>_alineada.ply junto al original
- Guarda un landmarks.json con los tres puntos, el AID y la matriz, para poder
  reejecutar después sin volver a marcar

REQUISITOS DE CÓDIGO
- La carga y la submuestra de la malla con @st.cache_data, porque Streamlit
  reejecuta el script entero en cada interacción y la malla es grande.
- La lista de puntos en st.session_state.
- Los comentarios y los textos de la interfaz en español.
- Mantén la matemática (matriz_alineacion) en funciones puras, sin nada de
  Streamlit dentro, para poder reutilizarlas después fuera de la app.

Cuando esté escrito, córrela tú con streamlit y dime si arranca sin errores. No
la pruebes con una malla real, eso lo hago yo.
```

---

## Fase 7 — Probarla

```
streamlit run app_alineacion.py
```

**Usa `3Dmesh_orig.stl`**, el archivo que se le da al gradado. No uses una malla
gradada: esas tienen alta resolución en una oreja y baja en la otra, así que marcar
la oreja gruesa sería impreciso.

Las cinco comprobaciones:

1. **La caja envolvente.** Si la cabeza mide unos 200, el archivo está en
   milímetros. Si mide 0,2, está en metros. Es el primer dato real sobre la escala.
2. **Que se pueda girar y acercar a la oreja.** Rueda del ratón para zoom,
   arrastrar para girar.
3. **El AID de C.** Es un número que todavía no tienen.
4. **El residuo.** Debe salir del orden de 1e-15. Si sale grande, hay un error en
   la matriz.
5. **Abrir el `_alineada.ply` en MeshLab** y comprobar a ojo que la cabeza está
   derecha y mirando hacia +x.

Si las cinco salen bien, la pieza está terminada. Súbanla:

```
git add .
git commit -m "App de alineación por tres puntos"
git push
```

---

## Fase 8 — La rutina de trabajo

### Todos los días

**Al empezar:**
```
git pull
```

**Cuando termines algo que funciona:**
```
git add .
git commit -m "Descripción de lo que hiciste"
git push
```

En VS Code todo eso está en el icono de las ramitas de la barra izquierda: ves los
archivos cambiados, escribes el mensaje, pulsas los botones. No hace falta
memorizar comandos.

**La regla de oro:** `pull` antes de empezar, `push` al acabar. Si los dos editan
el mismo archivo sin hacerlo, Git pide resolver el conflicto a mano, que es tedioso
pero no grave.

### Si instalas un paquete nuevo

Añádelo a `requirements.txt` y súbelo, para que el otro lo tenga:

```
pip install lo_que_sea
```
y luego edita `requirements.txt` a mano añadiendo la línea.

### Para programar juntos en tiempo real

Extensión **Live Share** de Microsoft en VS Code. Uno inicia la sesión, comparte el
enlace, y el otro entra: mismo código, mismos cursores, terminal compartida.

Es muy útil para depurar juntos. Para el trabajo normal es mejor Git, porque queda
historia.

### Mensajes de commit

No hace falta nada elaborado, pero que digan algo. `"Arreglos"` no sirve dentro de
un mes; `"Corrige el signo del eje z en la alineación"` sí.

---

## Qué viene después

Con la Fase 7 superada, la siguiente pieza es la limpieza de malla. Para eso hace
falta un trabajo previo de diez minutos que solo pueden hacer ustedes:

**Transcribir las llamadas de PyMeshLab.** En MeshLab, cada diálogo de filtro trae
un botón **"Copy PyMeshLab call to clipboard"**. Hay que pulsarlo para los ocho
filtros de la receta y pegar el resultado en un archivo de texto:

1. Remove duplicate faces
2. Remove duplicate vertices
3. Remove isolated folded faces by edge flip
4. Remove unreferenced vertices
5. Remove zero area faces
6. Repair non-manifold edges
7. Repair non-manifold vertices by splitting
8. Surface reconstruction: Screened Poisson

Eso convierte la etapa de limpieza de "a ver si el código acierta los nombres" a
una transcripción directa, y es la diferencia entre que funcione a la primera o
pasar una tarde peleando con nombres de parámetros.
