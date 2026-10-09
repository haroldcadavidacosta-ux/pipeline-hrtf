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
| Evaluación (ITD, ILD) | — | `metricas/` (por hacer) |

## Reglas

- Todo en español: código, comentarios y textos de la interfaz.
- La matemática de cada etapa va en su carpeta (`malla/`, `metricas/`) sin interfaz.
- Los parámetros compartidos van en `config.py`; las rutas de cada máquina, en `config_local.py`
  (no se sube).
- Al repositorio va código, nunca datos: `datos/` está en el `.gitignore`.
- Intérprete: `.venv\Scripts\python.exe` (Windows).
