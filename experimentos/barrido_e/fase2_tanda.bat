@echo off
:: Fase 2 del barrido de -e. Doble clic (pregunta la tanda) o desde una terminal:
::     experimentos\barrido_e\fase2_tanda.bat 1       tanda 1: -e 1 y luego -e 0.5
::     experimentos\barrido_e\fase2_tanda.bat 2       tanda 2: -e 3 y luego -e 2
::     experimentos\barrido_e\fase2_tanda.bat seco    prueba en seco (900 y 12000 Hz, ~20 min)
::     experimentosbarrido_ease2_tanda.bat y5      -e 1 -y 5 (prueba de control)
::     experimentosbarrido_ease2_tanda.bat j2      fase 4: A1 y A3 con -e 2 (repetibilidad)
::     experimentosbarrido_ease2_tanda.bat j05     fase 4: A1 y A3 con -e 0.5
::
:: ANTES DE LANZAR (el conductor lo comprueba y no arranca si algo falta):
::  1. Cerrar VS Code y todo lo demas. Abrir una terminal nueva (cmd) y lanzar desde ahi.
::  2. Windows Update: si tiene un reinicio pendiente, reiniciar ANTES (eso si bloquea). Pausar
::     las actualizaciones es recomendable pero ya no obligatorio (solo se avisa).
::     (Las horas activas de este equipo son 8-17: sin pausa puede reiniciar de noche.)
::  3. Suspension e hibernacion en "Nunca" con corriente (este .bat lo fija abajo; ademas el
::     conductor le pide a Windows que no se duerma mientras corre). Equipo enchufado.
::  4. Carpeta de NumCalc excluida del antivirus (excluir_antivirus.bat, como administrador).
::  5. No cerrar esta ventana: cerrarla corta NumCalc. Si se corta, volver a lanzar la misma
::     tanda: reanuda donde iba (lo completo esta en datos\experimentos\barrido_e\fase2\progreso.json).
::
:: En la manana: datos\experimentos\barrido_e\fase2\progreso.csv (una linea por frecuencia).
cd /d "%~dp0\..\.."
set NUMCALC=C:\Users\Usuario\Documents\PROYECTO DE GRADO\Mesh2HRTF\mesh2hrtf-tools-code-investigacion\NumCalc_WindowsExe
set TANDA=%~1
if "%TANDA%"=="" (
    echo Tanda 1: -e 1 y luego -e 0.5    Tanda 2: -e 3 y luego -e 2    y5: -e 1 -y 5    seco: prueba en seco
    echo j2: A1 y C con -e 2    j05: A1 y C con -e 0.5   (fase 4, repetibilidad)
    set /p TANDA=Que tanda quieres correr? [1 / 2 / y5 / j2 / j05 / seco]:
)
if /i not "%TANDA%"=="1" if /i not "%TANDA%"=="2" if /i not "%TANDA%"=="y5" if /i not "%TANDA%"=="j2" if /i not "%TANDA%"=="j05" if /i not "%TANDA%"=="seco" (
    echo Tanda no valida: "%TANDA%". Debe ser 1, 2, y5, j2, j05 o seco.
    pause
    exit /b 1
)
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
if /i "%TANDA%"=="seco" (
    .venv\Scripts\python.exe experimentos\barrido_e\fase2.py seco --numcalc "%NUMCALC%"
) else (
    .venv\Scripts\python.exe experimentos\barrido_e\fase2.py real --tanda %TANDA% --numcalc "%NUMCALC%"
)
echo.
echo Codigo de salida: %errorlevel%  (0 = todo bien, 1 = alguna condicion fallo, 2 = no arranco, 3 = abortado)
pause
