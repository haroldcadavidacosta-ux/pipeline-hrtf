@echo off
:: Fase 0.7: simulaciones de diagnostico con el NumCalc de 2022, de la mas barata a la mas cara.
::   1) -e 1 en 20.1 / 21 / 21.9 / 23.1 kHz (perfil de la divergencia)
::   2) -e 0.98 y -e 1.02 a 24 kHz (sensibilidad)
::   3) -e 0.5 a 24 kHz (lo pendiente del piloto; necesita ~11.5 GB libres)
:: Cerrar ANTES VS Code y todo lo demas. Tarda unas 2-3 horas. No cerrar esta ventana.
:: Resultados: datos\experimentos\barrido_e\diagnostico\diagnostico.json y piloto\piloto.json
cd /d "%~dp0\..\.."
set NUMCALC=C:\Users\Usuario\Documents\PROYECTO DE GRADO\Mesh2HRTF\mesh2hrtf-tools-code-investigacion\NumCalc_WindowsExe\NumCalc.exe
echo Inicio: %date% %time%
.venv\Scripts\python.exe -c "import psutil; print('RAM libre al empezar: %%.1f GB' %% (psutil.virtual_memory().available/2**30))"
.venv\Scripts\python.exe experimentos\barrido_e\diagnostico_convergencia.py datos\experimentos\barrido_e "%NUMCALC%"
.venv\Scripts\python.exe experimentos\barrido_e\piloto.py datos\experimentos\barrido_e "%NUMCALC%"
echo.
echo Fin: %date% %time%
echo Terminado. Ya puedes abrir VS Code.
pause
