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
- Licencias: NumCalc es parte de Mesh2HRTF (LGPL v3 o posterior); las DLL de MSYS2, BSD de
  3 cláusulas (ver `readme_NumCalc_WindowsExe.txt`).
