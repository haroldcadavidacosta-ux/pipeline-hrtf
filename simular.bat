@echo off
rem Simula una carpeta de resultados con NumCalc y arma la HRTF, sin VS Code ni navegador.
rem Uso: doble clic y pegar la ruta de la carpeta, o arrastrar la carpeta encima de este archivo.
rem Si la carpeta todavia no tiene los proyectos de Mesh2HRTF, los exporta primero (Blender).
chcp 65001 >nul
setlocal
set "RAIZ=%~dp0"
set "PYTHONIOENCODING=utf-8"
set "CARPETA=%~1"
if "%CARPETA%"=="" set /p "CARPETA=Ruta de la carpeta de resultados (p. ej. datos\salidas\A1): "
set "CARPETA=%CARPETA:"=%"

echo.
echo Cerrar VS Code, el navegador y otros programas: NumCalc necesita la memoria.
echo No hacer clic dentro de esta ventana: Windows pausa el programa (si pasa, pulsar Esc).
echo Se puede cerrar y volver a lanzar: lo ya simulado se conserva.
echo.

if not exist "%CARPETA%\informe_exportacion.json" (
    echo La carpeta no tiene proyectos exportados: exportando primero con Blender...
    "%RAIZ%.venv\Scripts\python.exe" "%RAIZ%exportar_malla.py" "%CARPETA%" || goto fin
)
"%RAIZ%.venv\Scripts\python.exe" "%RAIZ%simular_malla.py" "%CARPETA%"

:fin
echo.
pause
