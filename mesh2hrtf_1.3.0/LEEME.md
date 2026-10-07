# Mesh2HRTF 1.3.0 (solo el exportador de Blender)

Lo que usa `malla/exportacion.py` para exportar los proyectos de NumCalc, copiado sin
cambios de Mesh2HRTF 1.3.0 (https://github.com/Any2HRTF/Mesh2HRTF):

- `mesh2hrtf/Mesh2Input/mesh2input.py`: el complemento de Blender (operador
  `bpy.ops.mesh2input.inp`). No se instala en el Blender del usuario: el script de
  exportación lo registra desde aquí al arrancar Blender en segundo plano.
- `mesh2hrtf/Mesh2Input/EvaluationGrids/Data/`: mallas de evaluación (solo `Nodes.txt`
  y `Elements.txt`; los PDF y PNG de muestra se quedaron fuera).
- `mesh2hrtf/Mesh2Input/Materials/Data/`: materiales.
- `VERSION`: el exportador lo lee en `programPath/../VERSION`, por eso esta estructura.

`config.MESH2HRTF_PATH` apunta a `mesh2hrtf/` dentro de esta carpeta (se resuelve solo,
también en la app empaquetada).

Licencia: EUPL 1.2 (`LICENSE.txt`), que permite redistribuirlo conservando la licencia.
