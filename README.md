# pipeline_hrtf

HRTF personalizadas a partir de un escaneo de la cabeza hecho con el celular (KIRI Engine): la
malla se limpia y se escala, se gradúa, se simula con Mesh2HRTF/NumCalc y sale la HRTF de las dos
orejas en SOFA. Todo corre desde una app (`app.py`); el usuario solo necesita la app y Blender.

## Por dónde empezar

| Si vas a... | Lee |
|---|---|
| Entender el proyecto y montar el entorno | [contexto.md](contexto.md) |
| Trabajar en las métricas (ITD, ILD) | [metricas/LEEME.md](metricas/LEEME.md) |
| Tocar la limpieza de mallas | [malla/LIMPIEZA.md](malla/LIMPIEZA.md) (antes de modificar `malla/limpieza.py`) |
| Entender qué hace NumCalc y cómo se verifica | [docs/verificacion_numcalc.md](docs/verificacion_numcalc.md) |
| Ver el experimento que fijó el gradado (-e 1 -y 5) | [experimentos/barrido_e/](experimentos/barrido_e/) |

## Las etapas

| Etapa | Script (la app usa el mismo) | Código |
|---|---|---|
| 1. Puntos y alineación | `app.py` | `malla/alineacion.py` |
| 2–3. Limpieza, escala y corte del cuello | `limpiar_malla.py` | `malla/limpieza.py` |
| 4. Gradado | `gradar_malla.py` | `malla/gradado.py` + `grading/` |
| 5. Exportación a Mesh2HRTF | `exportar_malla.py` | `malla/exportacion.py` + `mesh2hrtf_1.3.0/` (necesita Blender) |
| 6–7. Simulación y HRTF en SOFA | `simular_malla.py` o `simular.bat` | `malla/simulacion.py` + `numcalc/` |
| Para escuchar (DTF, HeSuVi) | `exportar_hesuvi.py` | `malla/dtf.py`, `malla/hesuvi.py` |
| Evaluación (SD, ITD, ILD) | `evaluacion_prototipo.py` | `metricas/` |

## Reglas

- Todo en español: código, comentarios y textos de la interfaz.
- La matemática de cada etapa va en su carpeta (`malla/`, `metricas/`) sin interfaz.
- Los parámetros compartidos van en `config.py`; las rutas de cada máquina, en `config_local.py`
  (no se sube).
- Al repositorio va código, nunca datos: `datos/` está en el `.gitignore`.
- Intérprete: `.venv\Scripts\python.exe` (Windows).

## Licencia

GPL-3.0 o posterior ([LICENSE](LICENSE)). La app empaquetada incluye pymeshlab (GPL-3), así
que el proyecto entero tiene que distribuirse bajo GPL-3 y con su código fuente.

La licencia, la versión y el código fuente de cada componente de terceros (Mesh2HRTF, NumCalc,
hrtf_mesh_grading, Qt, Python, etc.) están en [AVISOS_DE_TERCEROS.md](AVISOS_DE_TERCEROS.md),
junto con las citas que piden sus autores. Los textos completos están en [licencias/](licencias/).

Al empaquetar, `pipeline_hrtf.spec` llama a `licencias/generar_avisos.py`, que deja junto al
`.exe` la licencia, los avisos, los textos y `codigo_fuente_pipeline_hrtf.zip`. Para repartir la
app, se reparte la carpeta `dist\pipeline_hrtf\` entera, con esos archivos.

Los datos de los participantes (mallas, fotografías y HRTF) no se publican.
