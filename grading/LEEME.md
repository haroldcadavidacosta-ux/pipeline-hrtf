# hrtf_mesh_grading (binario para Windows)

Programa que gradúa la malla de la cabeza para Mesh2HRTF: elementos finos en la oreja
del lado indicado y cada vez más grandes lejos de ella. Lo usa `malla/gradado.py`; la
app y `gradar_malla.py` lo encuentran solos en esta carpeta (no hay que configurar rutas).

- `hrtf_mesh_grading.exe` + las 4 DLL de MSYS2 que necesita. Funciona sin nada más
  instalado. Comprobar que arranca: `.venv\Scripts\python.exe gradar_malla.py --diagnostico`
- Origen: el binario compilado para Windows de *mesh2hrtf-tools*
  (https://sourceforge.net/p/mesh2hrtf-tools/code/ci/master/tree/hrtf_mesh_grading_WindowsExe/),
  versión 2022-04-17; ver `readme_mesh2hrtf-tools.txt`.
- Código fuente: https://github.com/cg-tub/hrtf_mesh_grading. Tiene cambios de 2024
  (gradado por distancia, `-l`/`-r` para dar la posición de los canales) que este
  binario no incluye. Oficialmente solo se soporta en Linux; para actualizar, compilar
  una vez y reemplazar el `.exe` (los parámetros son los mismos).
- **Error conocido**: con algunas mallas sanas se cae (código 0xC0000005) de forma
  caótica: depende de detalles internos, no de la geometría. A1 con -e 0.5 se caía
  cortada a −115 mm, pero no cortada a −110 mm ni sin cortar; no hay una zona "mala" que
  limpiar. `malla/gradado.py` reintenta hasta 5 veces con **la misma malla escrita en otro
  orden** (vértices y caras permutados: ningún punto se mueve), y lo deja como aviso en
  `informe_gradado.json`. Con A1 a -e 0.5 funcionó en 4 de los órdenes 1 a 5: el orden 2
  también se cae (repetido el 2026-10-07). El resultado depende un poco del orden (52 590 a
  52 878 caras en esos 4; el orden 1, el que usó la fase 4, da siempre 52 590). Antes se reintentaba con la
  malla movida ~0.0001 mm: con A1 eso dejaba al programa terminando sin remallar
  (código 0 y "Faces after" = "before"), así que ahora un intento solo cuenta si de verdad
  bajó el número de caras. Quizá la versión de 2024 no tenga este error.
- Licencias: el programa, MIT (`LICENSE_hrtf_mesh_grading.txt`); las DLL de MSYS2,
  BSD de 3 cláusulas.
- Si se usa, citar: T. Palm, S. Koch, F. Brinkmann y M. Alexa, "Curvature-adaptive mesh
  grading for numerical approximation of head-related transfer functions", DAGA 2021,
  Viena, pp. 1111-1114.
