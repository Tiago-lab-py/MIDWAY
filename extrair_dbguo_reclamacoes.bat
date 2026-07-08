@echo off
setlocal

cd /d "%~dp0"
echo Extraindo reclamacoes DBGUO...
python -m midway.extract.reclamacoes_dbguo

if errorlevel 1 (
    echo.
    echo Processo interrompido por erro.
    exit /b 1
)

endlocal
