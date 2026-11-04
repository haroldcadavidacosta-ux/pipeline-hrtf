# Licencias de pipeline_hrtf y de lo que incluye

## El proyecto

pipeline_hrtf — Copyright (C) 2026 Jerónimo Cardona y Harold Cadavid.

Es software libre: se puede redistribuir y modificar bajo la **Licencia Pública General de
GNU, versión 3 o posterior** (GPL-3.0-or-later), publicada por la Free Software Foundation
(texto completo en [LICENSE](LICENSE)). Se distribuye con la esperanza de que sea útil, pero
**sin ninguna garantía**, ni siquiera la implícita de comercialización o de idoneidad para un
fin determinado.

**Por qué GPL-3.** La app empaquetada lleva [pymeshlab](https://github.com/cnr-isti-vclab/PyMeshLab)
(MeshLab), que es GPL-3, en el mismo ejecutable. Mesh2HRTF (EUPL-1.2) es compatible con la
GPL-3: la EUPL la incluye en su lista de licencias compatibles. La GPL-3 también cubre
`malla/blender_exportar.py`, que usa la API de Blender (GPL).

**Código fuente.** La app empaquetada trae el código del proyecto en
`codigo_fuente_pipeline_hrtf.zip`, junto a `pipeline_hrtf.exe`. El código de los
componentes de terceros con copyleft está en los enlaces de las tablas, en la versión indicada.

## Componentes incluidos en el repositorio y en la app

Se copiaron sin cambios.

| Componente | Versión | Licencia | Texto | Código fuente |
|---|---|---|---|---|
| Exportador de Mesh2HRTF (`mesh2hrtf_1.3.0/`) y paquete de Python `mesh2hrtf` | 1.3.0 | EUPL-1.2 | `mesh2hrtf_1.3.0/LICENSE.txt` | https://github.com/Any2HRTF/Mesh2HRTF/tree/v1.3.0 |
| NumCalc (`numcalc/NumCalc.exe`), solver BEM de Mesh2HRTF | binario del 2022-08-26 (mesh2hrtf-tools) | EUPL-1.2 (licencia del repositorio en esa fecha) y LGPL-3.0 (según el `COPYING` heredado y el readme del binario); se cumplen las dos | `licencias/textos/EUPL-1.2.txt`, `LGPL-3.0.txt`, `GPL-3.0.txt` | Último commit de `mesh2hrtf/NumCalc/src` antes de esa fecha: https://github.com/Any2HRTF/Mesh2HRTF/tree/001351d7e19b6940ad33b9cccd5c285947c48e55/mesh2hrtf/NumCalc/src. Binario: https://sourceforge.net/p/mesh2hrtf-tools/code/ci/master/tree/NumCalc_WindowsExe/ |
| hrtf_mesh_grading (`grading/`) | binario del 2022-04-17 (mesh2hrtf-tools) | MIT, © 2021 Computer Graphics TU Berlin | `grading/LICENSE_hrtf_mesh_grading.txt` | https://github.com/cg-tub/hrtf_mesh_grading |
| pmp-library (`grading/libpmp.dll`) | la del binario | MIT | `licencias/nativas/pmp-library.txt` | https://github.com/pmp-library/pmp-library |
| Runtime de GCC/MinGW-w64 (`libgcc_s_seh-1.dll`, `libstdc++-6.dll`) en `grading/` y `numcalc/` | MSYS2 de 2022 | GPL-3.0 con la excepción de runtime de GCC 3.1 | `licencias/textos/GPL-3.0.txt`, `GCC-excepcion-runtime-3.1.txt` | https://gcc.gnu.org/git/ |
| winpthreads de MinGW-w64 (`libwinpthread-1.dll`) | MSYS2 de 2022 | MIT y BSD | `licencias/textos/winpthreads.txt` | https://github.com/mingw-w64/mingw-w64 |

## Componentes que solo van en la app empaquetada

**Paquetes de Python.** La lista exacta de cada compilación, con la licencia de cada paquete,
la genera `licencias/generar_avisos.py` en `licencias/python/` (índice en `INDICE.md`). Los
principales:

| Componente | Versión | Licencia | Código fuente |
|---|---|---|---|
| pymeshlab (MeshLab, vcglib) | 2025.7.post1 | GPL-3.0 | https://github.com/cnr-isti-vclab/PyMeshLab |
| NiceGUI | 3.17.1 | MIT | https://github.com/zauberzeug/nicegui |
| trimesh | 5.1.0 | MIT | https://github.com/mikedh/trimesh |
| NumPy / SciPy | 2.4.6 / 1.18.1 | BSD-3-Clause (y licencias de sus librerías internas) | https://github.com/numpy/numpy, https://github.com/scipy/scipy |
| matplotlib | 3.11.2 | licencia de matplotlib (tipo PSF) | https://github.com/matplotlib/matplotlib |
| pyfar / sofar / spharpy | 0.8.1 / 1.3.0 / 1.0.1 | MIT | https://github.com/pyfar |
| soundfile + libsndfile | 0.14.0 | BSD-3-Clause; libsndfile LGPL-2.1 | https://github.com/libsndfile/libsndfile |
| psutil | 7.2.2 | BSD-3-Clause | https://github.com/giampaolo/psutil |

Otros paquetes con copyleft débil, incluidos sin modificar:
- certifi, orjson y bidict: MPL-2.0. Su código está en PyPI y en sus repositorios
  (https://github.com/certifi/python-certifi, https://github.com/ijl/orjson,
  https://github.com/jab/bidict).
- docutils: dominio público, BSD y algunas partes GPL; todas son compatibles con la GPL-3.

Todos los demás paquetes son permisivos (MIT, BSD, Apache-2.0, PSF o equivalentes).

**Librerías nativas que trae pymeshlab** (en `_internal/pymeshlab/`):

| Componente | Licencia | Texto | Código fuente |
|---|---|---|---|
| Qt 5.15.2 (`Qt5*.dll` y plugins) | LGPL-3.0 | `licencias/textos/LGPL-3.0.txt` | https://download.qt.io/archive/qt/5.15/5.15.2/single/ |
| GMP (`libgmp-10.dll`) y MPFR (`libmpfr-4.dll`) | LGPL-3.0 | `licencias/textos/LGPL-3.0.txt` | https://gmplib.org, https://www.mpfr.org |
| lib3ds (`external-lib3ds.dll`) | LGPL-2.1 | `licencias/textos/LGPL-2.1.txt` | https://github.com/cnr-isti-vclab/meshlab (src/external) |
| Embree (`embree4.dll`) | Apache-2.0 | `licencias/nativas/embree.txt` | https://github.com/RenderKit/embree |
| oneTBB (`tbb12.dll`) | Apache-2.0 | `licencias/nativas/onetbb.txt` | https://github.com/uxlfoundation/oneTBB |
| U3D/IFX (`IFX*.dll`) | Apache-2.0 | `licencias/textos/Apache-2.0.txt` | https://github.com/cnr-isti-vclab/meshlab (src/external) |
| lib3mf | BSD-2-Clause | `licencias/nativas/lib3mf.txt` | https://github.com/3MFConsortium/lib3mf |
| libE57Format | BSL-1.0 | `licencias/nativas/libE57Format.txt` | https://github.com/asmaloney/libE57Format |
| GLEW | BSD-3 / MIT | `licencias/nativas/glew.txt` | https://github.com/nigels-com/glew |
| muparser | BSD-2-Clause | `licencias/nativas/muparser.txt` | https://github.com/beltoforion/muparser |
| ANGLE (`libEGL.dll`, `libGLESv2.dll`) | BSD-3-Clause | `licencias/nativas/angle.txt` | https://github.com/google/angle |
| Mesa llvmpipe (`opengl32sw.dll`) | MIT | `licencias/nativas/mesa-llvmpipe.txt` | https://gitlab.freedesktop.org/mesa/mesa |

**Python y sus librerías** (de la instalación de conda con la que se construye):

| Componente | Licencia | Texto |
|---|---|---|
| Python 3.14.7 | PSF-2.0 | `licencias/nativas/python-3.14.txt` |
| OpenSSL 3.5.7 (`libcrypto-3-x64.dll`, `libssl-3-x64.dll`) | Apache-2.0 | `licencias/nativas/openssl-3.5.txt` |
| bzip2, expat, libffi, mpdecimal, zlib, SQLite, XZ (liblzma), zstd | bzip2, MIT, MIT, BSD-2, zlib, dominio público, 0BSD, BSD-3 | `licencias/nativas/` (un archivo por librería) |
| Runtime de Microsoft Visual C++ y UCRT | licencia de Microsoft, que permite redistribuirlos | `licencias/nativas/microsoft-*.txt` |

## Lo que no va incluido

- **Blender** (GPL) no va dentro de la app. Hay que tenerlo instalado; la app lo ejecuta como
  programa aparte.
- **KIRI Engine**, que hace los escaneos, tampoco va incluido; sus condiciones de uso son las
  del servicio.

## Citas

No son una obligación de licencia, pero los autores lo piden:

- Mesh2HRTF y NumCalc:
  - H. Ziegelwanger, W. Kreuzer y P. Majdak, «Mesh2HRTF: Open-source software package for
    the numerical calculation of head-related transfer functions», Proceedings of the 22nd
    ICSV, Florencia, 2015.
  - H. Ziegelwanger, P. Majdak y W. Kreuzer, «Numerical calculation of listener-specific
    head-related transfer functions and sound localization: Microphone model and mesh
    discretization», J. Acoust. Soc. Am. 138, 208-222, 2015.
- hrtf_mesh_grading: T. Palm, S. Koch, F. Brinkmann y M. Alexa, «Curvature-adaptive mesh
  grading for numerical approximation of head-related transfer functions», DAGA 2021, Viena,
  pp. 1111-1114.
