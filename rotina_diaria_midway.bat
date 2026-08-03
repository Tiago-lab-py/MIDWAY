@echo off
echo ========================================================
echo INICIANDO ROTINA AUTOMATIZADA - MIDWAY
echo ========================================================

:: Garante que o script esta rodando na pasta correta
cd /d "D:\MIDWAY"

:: Verifica onde esta o python (usando a mesma logica do run.bat)
set "PYTHON_EXE=C:\Program Files\Python311\python.exe"
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=python"
)

:: 1. Roda as fases 1 a 4 (Orquestrador Central ETL)
echo.
echo [1/3] Rodando ETL Oficial (Fases 1 a 4)...
call run.bat etl
if %errorlevel% neq 0 (
    echo ERRO: Ocorreu um problema durante a execucao do ETL.
    exit /b %errorlevel%
)

:: 2. Roda a extração do banco GEO
echo.
echo [2/3] Extraindo dados do banco GEO (Chaves RA)...
call run.bat geo
if %errorlevel% neq 0 (
    echo ERRO: Ocorreu um problema na extracao do GEO.
    exit /b %errorlevel%
)

:: 3. Roda o relatorio de ressarcimento
echo.
echo [3/3] Gerando Relatorio de Ressarcimento Preventivo...
"%PYTHON_EXE%" -m midway.analytics.ressarcimento_diario
if %errorlevel% neq 0 (
    echo ERRO: Ocorreu um problema ao gerar o relatorio de ressarcimento.
    exit /b %errorlevel%
)

echo.
echo ========================================================
echo ROTINA FINALIZADA COM SUCESSO!
echo ========================================================
:: Se for colocar no agendador de tarefas e quiser que a janela feche sozinha,
:: basta apagar ou colocar "::" na frente do comando pause abaixo:
:: pause
