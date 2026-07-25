@echo off
setlocal EnableExtensions
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

set "DESTINO=%~1"
if "%DESTINO%" == "" (
    if not "%RESSARCIMENTO_DIARIO_DESTINO%" == "" (
        set "DESTINO=%RESSARCIMENTO_DIARIO_DESTINO%"
    ) else (
        set "DESTINO=data\marts\ressarcimento_diario"
    )
)

echo Destino: %DESTINO%
echo Python : %PYTHON_EXE%
echo.

"%PYTHON_EXE%" -m midway.analytics.ressarcimento_diario "%DESTINO%"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%" == "0" (
    echo Processo finalizado com erro. Codigo: %EXIT_CODE%
    exit /b %EXIT_CODE%
)

echo Processo finalizado com sucesso.
exit /b 0
