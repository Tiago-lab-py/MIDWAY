@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PYTHON_EXE=C:/Program Files/Python311/python.exe"

if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=python"
)

echo Materializando silver de reclamacoes DBGUO...
"%PYTHON_EXE%" -m midway.transform.dbguo_reclamacoes_silver

if errorlevel 1 (
    echo.
    echo Processo interrompido por erro.
    exit /b 1
)

echo.
echo Silver de reclamacoes DBGUO finalizada.
endlocal
