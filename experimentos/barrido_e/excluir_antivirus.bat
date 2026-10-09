@echo off
:: Excluye la carpeta de NumCalc del analisis de Microsoft Defender, para que el antivirus no
:: bloquee sus DLL a mitad de una corrida larga (episodio del 2026-09-29: libstdc++-6.dll).
:: EJECUTAR COMO ADMINISTRADOR: clic derecho -> "Ejecutar como administrador".
net session >nul 2>&1
if errorlevel 1 (
    echo Hay que ejecutarlo como administrador: clic derecho -^> "Ejecutar como administrador".
    pause
    exit /b 1
)
set CARPETA=C:\Users\Usuario\Documents\PROYECTO DE GRADO\Mesh2HRTF\mesh2hrtf-tools-code-investigacion\NumCalc_WindowsExe
powershell -NoProfile -Command "Add-MpPreference -ExclusionPath '%CARPETA%'; Add-MpPreference -ExclusionProcess '%CARPETA%\NumCalc.exe'; 'Exclusiones actuales de carpetas:'; (Get-MpPreference).ExclusionPath; 'Exclusiones actuales de procesos:'; (Get-MpPreference).ExclusionProcess"
echo.
echo Listo. Para quitarla mas adelante: Remove-MpPreference -ExclusionPath "%CARPETA%" (como administrador).
pause
