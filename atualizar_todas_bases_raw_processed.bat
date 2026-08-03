@echo off
echo =========================================================================
echo REEXTRACAO COMPLETA E REPROCESSAMENTO DE TODAS AS BASES (RAW E PROCESSED)
echo =========================================================================

:: Garante que o script esta rodando na pasta raiz do projeto
cd /d "D:\MIDWAY"

:: 0. Garante a liberação das bases DuckDB fechando conexões ativas
echo.
echo [0/3] Liberando arquivos DuckDB (fechando processos python ativos)...
taskkill /f /fi "WINDOWTITLE eq MIDWAY API FastAPI*" >nul 2>&1
taskkill /f /fi "WINDOWTITLE eq MIDWAY Frontend React*" >nul 2>&1
taskkill /f /im python.exe >nul 2>&1
timeout /t 3 /nobreak >nul

:: Verifica onde esta o executavel do python
set "PYTHON_EXE=C:\Program Files\Python311\python.exe"
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=python"
)

:: Habilita as variaveis de ambiente para FORCAR a reextracao completa de TODAS as fontes RAW:
:: - ADMS Ocorrencias (iqs_adms_raw)
:: - ADMS Servicos (adms_servicos_raw)
:: - DBGUO Reclamacoes (dbguo_raw)
:: - Tratamento e Normalizacao (iqs_adms_processed)
set "REEXTRAIR=1"
set "REPROCESSAR=1"
set "REEXTRAIR_DBGUO=1"
set "REEXTRAIR_ADMS_SERVICOS=1"

echo.
echo [1/3] Executando Pipeline ETL com Reextracao Total (RAW + Processed + Gold)...
call run.bat etl
if %errorlevel% neq 0 (
    echo ERRO: Ocorreu uma falha no reprocessamento geral do ETL.
    goto reiniciar_stack_erro
)

echo.
echo [2/3] Extraindo dados do banco GEO (Chaves RA)...
call run.bat geo
if %errorlevel% neq 0 (
    echo ERRO: Ocorreu uma falha na extracao do GEO.
    goto reiniciar_stack_erro
)

echo.
echo [3/3] Gerando Relatorio de Ressarcimento Preventivo com as novas bases...
"%PYTHON_EXE%" -m midway.analytics.ressarcimento_diario
if %errorlevel% neq 0 (
    echo ERRO: Ocorreu uma falha ao gerar o relatorio de ressarcimento.
    goto reiniciar_stack_erro
)

echo.
echo =========================================================================
echo ATUALIZACAO COMPLETA DAS BASES RAW E PROCESSED CONCLUIDA COM SUCESSO!
echo =========================================================================

:reiniciar_stack
echo.
echo Inicializando API FastAPI novamente...
start "MIDWAY API FastAPI" /D "D:\MIDWAY" cmd /k "call run.bat api"
timeout /t 3 /nobreak >nul
echo Inicializando Frontend React novamente...
start "MIDWAY Frontend React" /D "D:\MIDWAY" cmd /k "call run.bat frontend"
goto fim

reiniciar_stack_erro:
echo.
echo Reiniciando a stack do sistema em segundo plano por seguranca...
start "MIDWAY API FastAPI" /D "D:\MIDWAY" cmd /k "call run.bat api"
timeout /t 3 /nobreak >nul
start "MIDWAY Frontend React" /D "D:\MIDWAY" cmd /k "call run.bat frontend"
exit /b 1

:fim
:: pause

