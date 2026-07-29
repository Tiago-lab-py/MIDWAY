@echo off
echo =========================================================================
echo REEXTRACAO COMPLETA E REPROCESSAMENTO DE TODAS AS BASES (RAW & PROCESSED)
echo =========================================================================

:: Garante que o script esta rodando na pasta raiz do projeto
cd /d "D:\MIDWAY"

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
    pause
    exit /b %errorlevel%
)

echo.
echo [2/3] Extraindo dados do banco GEO (Chaves RA)...
call run.bat geo
if %errorlevel% neq 0 (
    echo ERRO: Ocorreu uma falha na extracao do GEO.
    pause
    exit /b %errorlevel%
)

echo.
echo [3/3] Gerando Relatorio de Ressarcimento Preventivo com as novas bases...
"%PYTHON_EXE%" -m midway.analytics.ressarcimento_diario
if %errorlevel% neq 0 (
    echo ERRO: Ocorreu uma falha ao gerar o relatorio de ressarcimento.
    pause
    exit /b %errorlevel%
)

echo.
echo =========================================================================
echo ATUALIZACAO COMPLETA DAS BASES RAW E PROCESSED CONCLUIDA COM SUCESSO!
echo =========================================================================
:: pause
