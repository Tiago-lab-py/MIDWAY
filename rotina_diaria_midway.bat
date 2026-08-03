@echo off
title MIDWAY ROTINA DIARIA
echo ========================================================
echo INICIANDO ROTINA AUTOMATIZADA - MIDWAY
echo ========================================================

:: Garante que o script esta rodando na pasta correta
cd /d "D:\MIDWAY"

:: 0. Garante a liberação das bases DuckDB fechando conexões ativas
echo.
echo [0/3] Liberando arquivos DuckDB (fechando processos python ativos)...
taskkill /f /fi "WINDOWTITLE eq MIDWAY API FastAPI*" >nul 2>&1
taskkill /f /fi "WINDOWTITLE eq MIDWAY Frontend React*" >nul 2>&1
taskkill /f /im python.exe >nul 2>&1
timeout /t 3 /nobreak >nul

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
    goto reiniciar_stack_erro
)

:: 2. Roda a extração do banco GEO
echo.
echo [2/3] Extraindo dados do banco GEO (Chaves RA)...
call run.bat geo
if %errorlevel% neq 0 (
    echo ERRO: Ocorreu um problema na extracao do GEO.
    goto reiniciar_stack_erro
)

:: 3. Roda o relatorio de ressarcimento
echo.
echo [3/3] Gerando Relatorio de Ressarcimento Preventivo...
"%PYTHON_EXE%" -m midway.analytics.ressarcimento_diario
if %errorlevel% neq 0 (
    echo ERRO: Ocorreu um problema ao gerar o relatorio de ressarcimento.
    goto reiniciar_stack_erro
)

echo.
echo ========================================================
echo ROTINA FINALIZADA COM SUCESSO!
echo ========================================================

:reiniciar_stack
echo.
echo Inicializando API FastAPI novamente...
start "MIDWAY API FastAPI" /D "D:\MIDWAY" cmd /k "call run.bat api"
timeout /t 3 /nobreak >nul
echo Inicializando Frontend React novamente...
start "MIDWAY Frontend React" /D "D:\MIDWAY" cmd /k "call run.bat frontend"
goto fim

:reiniciar_stack_erro
echo.
echo Reiniciando a stack do sistema em segundo plano por seguranca...
start "MIDWAY API FastAPI" /D "D:\MIDWAY" cmd /k "call run.bat api"
timeout /t 3 /nobreak >nul
start "MIDWAY Frontend React" /D "D:\MIDWAY" cmd /k "call run.bat frontend"
exit /b 1

:fim
:: Se for colocar no agendador de tarefas e quiser que a janela feche sozinha,
:: basta apagar ou colocar "::" na frente do comando pause abaixo:
:: pause

