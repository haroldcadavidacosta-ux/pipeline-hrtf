# Licencias

Textos completos de las licencias de lo que incluye el proyecto. El resumen está en
[../AVISOS_DE_TERCEROS.md](../AVISOS_DE_TERCEROS.md): qué componente usa cada licencia y dónde
está su código fuente.

| Carpeta o archivo | Contenido |
|---|---|
| `textos/` | Licencias genéricas: GPL-3.0, LGPL-3.0, LGPL-2.1, EUPL-1.2, Apache-2.0, MPL-2.0, excepción de runtime de GCC 3.1 y winpthreads. Bajadas de las fuentes oficiales el 2026-11-03 |
| `nativas/` | Licencias de las librerías nativas que van en la app empaquetada: Python y sus librerías (copiadas de los paquetes de conda con que se construye) y las que trae pymeshlab (copiadas de sus repositorios) |
| `generar_avisos.py` | Lo llama `pipeline_hrtf.spec` al empaquetar. Deja junto al `.exe` la licencia, los avisos, estos textos, la licencia de cada paquete de Python empaquetado y el código fuente |

Si se cambia la versión de Python, de conda o de pymeshlab con que se construye, hay que revisar
`nativas/` y las versiones de `AVISOS_DE_TERCEROS.md`.
