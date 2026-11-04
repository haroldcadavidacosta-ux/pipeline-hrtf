# NumCalc (binario para Windows)

El solver BEM de Mesh2HRTF. Lo usa `malla/simulacion.py`; `simular_malla.py` lo encuentra
solo en esta carpeta (`config.NUMCALC_EXE`), no hay que configurar rutas.

- `NumCalc.exe` + las 3 DLL de MSYS2 que necesita. Funciona sin nada más instalado.
  Comprobar que arranca: `.venv\Scripts\python.exe simular_malla.py --diagnostico`
- Origen: el binario compilado para Windows de *mesh2hrtf-tools*
  (https://sourceforge.net/p/mesh2hrtf-tools/code/ci/master/tree/NumCalc_WindowsExe/),
  versión 2022-08-26; ver `readme_NumCalc_WindowsExe.txt`.
- **Es exactamente el binario de todo el barrido de -e**: los SHA-256 de los cuatro archivos
  coinciden con los del manifiesto de la fase 2 (`datos/experimentos/barrido_e/fase2/manifiesto.json`).
  Lo que se sabe de él (tolerancia 1e-9 fija, tope de 250 iteraciones, código de salida 0
  aunque no converja, cruce a FMM de un nivel en c/D) está en `docs/verificacion_numcalc.md`.
- No trae `-adapt_fmmlength` (llegó después). Con -e 1 -y 10, B no convergía en
  23,4–24 kHz; con -e 1 -y 5, el gradado de producción, converge en todas.
- Licencias: NumCalc es parte de Mesh2HRTF. En la fecha del binario, el repositorio estaba bajo
  EUPL-1.2 (`LICENSE.txt`), aunque su `COPYING` heredado y el readme del binario dicen LGPL-3;
  se cumplen las dos. Las DLL no son de MSYS2 en sí, sino el runtime de GCC (`libgcc_s_seh-1`,
  `libstdc++-6`: GPL-3 con la excepción de runtime de GCC) y winpthreads (`libwinpthread-1`:
  MIT/BSD). Textos en `licencias/`; resumen en `AVISOS_DE_TERCEROS.md`.
- Código fuente: el binario se compiló de la rama `develop` de Mesh2HRTF. El último commit que
  tocó `mesh2hrtf/NumCalc/src` antes del 2022-08-26 es `001351d7` (2022-08-18):
  https://github.com/Any2HRTF/Mesh2HRTF/tree/001351d7e19b6940ad33b9cccd5c285947c48e55/mesh2hrtf/NumCalc/src
