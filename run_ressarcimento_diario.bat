@echo off
setlocal
chcp 65001 >nul

cd /d "%~dp0"

IF EXIST ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) ELSE (
    set "PYTHON_EXE=python"
)

echo ==============================================================
echo [ MIDWAY ] Iniciando Rotina Diaria de Ressarcimento Preventivo
echo ==============================================================

if "%~1" == "" (
    "%PYTHON_EXE%" -m midway.analytics.ressarcimento_diario
) else (
    "%PYTHON_EXE%" -m midway.analytics.ressarcimento_diario "%~1"
)

echo.
echo Processo finalizado!
pause
