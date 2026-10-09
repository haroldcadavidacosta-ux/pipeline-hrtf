@echo off
:: Corre solo las simulaciones pendientes del piloto (las que no cupieron en RAM).
:: Cerrar antes VS Code y todo lo demas: 24 kHz con -e 0.5 necesita ~11.5 GB libres.
:: Los resultados quedan en datos\experimentos\barrido_e\piloto\piloto.json
cd /d "%~dp0\..\.."
echo Corriendo lo pendiente del piloto. No cierres esta ventana.
.venv\Scripts\python.exe experimentos\barrido_e\piloto.py datos\experimentos\barrido_e "C:\Users\Usuario\Documents\PROYECTO DE GRADO\Mesh2HRTF\mesh2hrtf-tools-code-investigacion\NumCalc_WindowsExe\NumCalc.exe"
echo.
echo Terminado. Ya puedes abrir VS Code.
pause
