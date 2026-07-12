@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PYTHON_EXE=C:/Program Files/Python311/python.exe"

if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=python"
)

if "%~1"=="" goto uso

if /I "%~1"=="versao" (
    type "%SCRIPT_DIR%VERSION"
    goto fim
)

if /I "%~1"=="painel" (
    echo Abrindo painel Streamlit...
    "%PYTHON_EXE%" -m streamlit run "%SCRIPT_DIR%midway\web\home.py"
    if errorlevel 1 goto erro
    goto fim
)

if /I "%~1"=="api" (
    echo Abrindo MIDWAY API FastAPI...
    if "%MIDWAY_API_PORT%"=="" set "MIDWAY_API_PORT=8001"
    "%PYTHON_EXE%" -m uvicorn midway.api.main:app --host 127.0.0.1 --port %MIDWAY_API_PORT% --reload
    if errorlevel 1 goto erro
    goto fim
)

if /I "%~1"=="frontend" (
    echo Abrindo frontend React...
    pushd "%SCRIPT_DIR%frontend"
    npm run dev
    if errorlevel 1 (
        popd
        goto erro
    )
    popd
    goto fim
)

if /I "%~1"=="extract" (
    echo Executando extracao...
    "%PYTHON_EXE%" -m midway.extract.adms
    goto fim
)

if /I "%~1"=="registrar" (
    echo Registrando DuckDB bruto existente...
    set "REGISTRAR_RAW=1"
    "%PYTHON_EXE%" -m midway.extract.adms
    goto fim
)

if /I "%~1"=="tratamento" (
    echo Executando tratamento...
    "%PYTHON_EXE%" -m midway.transform.tratamento
    goto fim
)

if /I "%~1"=="reprocessar" (
    echo Executando tratamento com REPROCESSAR=1...
    set "REPROCESSAR=1"
    "%PYTHON_EXE%" -m midway.transform.tratamento
    goto fim
)

if /I "%~1"=="reextrair" (
    echo Executando extracao com REEXTRAIR=1...
    set "REEXTRAIR=1"
    "%PYTHON_EXE%" -m midway.extract.adms
    goto fim
)

if /I "%~1"=="amostra_raw" (
    echo Exportando amostra do RAW...
    "%PYTHON_EXE%" "%SCRIPT_DIR%tools\exportar_amostra_raw.py"
    goto fim
)

if /I "%~1"=="exportar" (
    echo Exportando CSVs finais sem reprocessar...
    "%PYTHON_EXE%" -m midway.export.csv_iqs
    goto fim
)

if /I "%~1"=="exportar_motivo" (
    echo Exportando teste com NUM_MOTIVO_TRAT_DIF_UCI preenchido...
    "%PYTHON_EXE%" -m midway.auditoria.motivo
    goto fim
)

if /I "%~1"=="exportacao_sobreposicao" (
    echo Processamento separado da sobreposicao total por UC e parcial por UC...
    "%PYTHON_EXE%" -m midway.auditoria.sobreposicoes
    goto fim
)

if /I "%~1"=="interrupcao_sem_uc" (
    echo Exportando interrupcoes sem UC para ESTADO 7...
    "%PYTHON_EXE%" -m midway.auditoria.interrupcao_sem_uc
    goto fim
)

if /I "%~1"=="auditar_ajuste_inicio_manobra" (
    echo Gerando auditoria de ajuste de inicio de manobra...
    "%PYTHON_EXE%" -m midway.auditoria.ajuste_inicio_manobra
    goto fim
)

if /I "%~1"=="exportacoes_auxiliares" (
    echo Gerando exportacoes separadas de sobreposicao...
    "%PYTHON_EXE%" -m midway.auditoria.sobreposicoes
    if errorlevel 1 goto erro

    ping -n 2 127.0.0.1 >nul

    echo Gerando exportacao de interrupcoes sem UC...
    "%PYTHON_EXE%" -m midway.auditoria.interrupcao_sem_uc
    if errorlevel 1 goto erro

    echo Normalizando datas das exportacoes auxiliares...
    "%PYTHON_EXE%" -m midway.export.normalizar_datas_iqs
    if errorlevel 1 goto erro

    goto fim
)

if /I "%~1"=="apuracao_parcial" (
    echo Gerando camada gold e BDO de apuracao previa...
    "%PYTHON_EXE%" -m midway.apuracao.previa
    if errorlevel 1 goto erro

    echo Gerando gold_outlier_uc...
    "%PYTHON_EXE%" -m midway.analytics.outlier_uc
    if errorlevel 1 goto erro

    goto fim
)

if /I "%~1"=="extrair_dbguo_reclamacoes" (
    echo Extraindo reclamacoes DBGUO...
    "%PYTHON_EXE%" -m midway.extract.reclamacoes_dbguo
    if errorlevel 1 goto erro
    goto fim
)

if /I "%~1"=="dbguo_reclamacoes" (
    echo Materializando silver e gold de reclamacoes DBGUO...
    "%PYTHON_EXE%" -m midway.transform.dbguo_reclamacoes_silver
    if errorlevel 1 goto erro
    goto fim
)

if /I "%~1"=="extrair_adms_servicos" (
    echo Extraindo servicos ADMS para RAW...
    "%PYTHON_EXE%" -m midway.extract.adms_servicos
    if errorlevel 1 goto erro
    goto fim
)

if /I "%~1"=="correcao_9282" (
    echo Gerando tratativa em massa RA 92/82...
    "%PYTHON_EXE%" -m midway.auditoria.correcao_9282
    if errorlevel 1 goto erro
    goto fim
)

if /I "%~1"=="analise_tecnica_cache" (
    echo Materializando cache da Analise Tecnica...
    if "%~2"=="" (
        "%PYTHON_EXE%" -m midway.qualidade.analise_tecnica_cache
    ) else (
        "%PYTHON_EXE%" -m midway.qualidade.analise_tecnica_cache %~2
    )
    if errorlevel 1 goto erro
    goto fim
)

if /I "%~1"=="testar_dados" (
    echo Executando testes automatizados dos dados tratados...
    "%PYTHON_EXE%" -m unittest discover -s "%SCRIPT_DIR%tests" -p "test_*.py"
    if errorlevel 1 goto erro
    goto fim
)

if /I "%~1"=="validar_dados" (
    echo Executando testes automatizados dos dados tratados...
    "%PYTHON_EXE%" -m unittest discover -s "%SCRIPT_DIR%tests" -p "test_*.py"
    if errorlevel 1 goto erro

    echo Gerando metricas de qualidade dos dados tratados...
    "%PYTHON_EXE%" "%SCRIPT_DIR%tools\gerar_metricas_qualidade.py"
    if errorlevel 1 goto erro

    goto fim
)

if /I "%~1"=="metricas_qualidade" (
    echo Gerando metricas de qualidade dos dados tratados...
    "%PYTHON_EXE%" "%SCRIPT_DIR%tools\gerar_metricas_qualidade.py"
    if errorlevel 1 goto erro
    goto fim
)

if /I "%~1"=="amostras_auditoria" (
    echo Exportando amostras de auditoria orientadas por risco...
    "%PYTHON_EXE%" "%SCRIPT_DIR%tools\exportar_amostras_auditoria.py"
    if errorlevel 1 goto erro
    goto fim
)

if /I "%~1"=="consumidores" (
    echo Extraindo consumidores IQS...
    "%PYTHON_EXE%" -m midway.extract.consumidores
    goto fim
)

if /I "%~1"=="uc_fatura" (
    echo Extraindo UCs consideradas na apuracao...
    "%PYTHON_EXE%" -m midway.extract.uc_fatura
    goto fim
)

if /I "%~1"=="vrc" (
    echo Extraindo VRC IQS sob demanda...
    "%PYTHON_EXE%" -m midway.extract.vrc
    goto fim
)

if /I "%~1"=="reextrair_vrc" (
    echo Reextraindo VRC IQS sob demanda...
    set "REEXTRAIR_VRC=1"
    "%PYTHON_EXE%" -m midway.extract.vrc
    goto fim
)

if /I "%~1"=="metas_uc" (
    echo Extraindo metas UC IQS sob demanda...
    "%PYTHON_EXE%" -m midway.extract.metas_uc
    goto fim
)

if /I "%~1"=="referencia_iqs" (
    echo Extraindo referencia componente/causa IQS...
    "%PYTHON_EXE%" -m midway.extract.referencia_componente_causa
    if errorlevel 1 goto erro
    goto fim
)

if /I "%~1"=="reextrair_referencia_iqs" (
    echo Reextraindo referencia componente/causa IQS...
    set "REEXTRAIR_REFERENCIA_IQS=1"
    "%PYTHON_EXE%" -m midway.extract.referencia_componente_causa
    if errorlevel 1 goto erro
    goto fim
)

if /I "%~1"=="sincronizar_iqs_raw" (
    echo Sincronizando IQS raw para DuckDB processado...
    "%PYTHON_EXE%" "%SCRIPT_DIR%tools\sincronizar_iqs_raw.py"
    goto fim
)

if /I "%~1"=="postgres_validar" (
    echo Validando PostgreSQL operacional MIDWAY...
    "%PYTHON_EXE%" -m midway.db.postgres
    if errorlevel 1 goto erro
    goto fim
)

if /I "%~1"=="postgres_status" (
    echo Verificando PostgreSQL local...
    if not exist "C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe" (
        echo pg_ctl nao encontrado em "C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe".
        goto erro
    )
    "C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe" status -D "C:\Program Files\PostgreSQL\18\data"
    goto fim
)

if /I "%~1"=="postgres_start" (
    echo Iniciando PostgreSQL local...
    if not exist "C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe" (
        echo pg_ctl nao encontrado em "C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe".
        goto erro
    )
    "C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe" start -D "C:\Program Files\PostgreSQL\18\data" -l "C:\Program Files\PostgreSQL\18\data\server.log"
    if errorlevel 1 goto erro
    goto fim
)

if /I "%~1"=="postgres_governanca" (
    echo Aplicando SQL de governanca MIDWAY...
    "%PYTHON_EXE%" -m midway.db.apply_sql 006_governanca.sql
    if errorlevel 1 goto erro
    goto fim
)

if /I "%~1"=="anomalias_setup" (
    echo Preparando nucleo funcional de anomalias MIDWAY...
    "%PYTHON_EXE%" -m midway.db.apply_sql 008_nucleo_anomalias_v7.sql
    if errorlevel 1 goto erro

    echo Carregando anomalias a partir de RAW, SILVER e GOLD...
    "%PYTHON_EXE%" -m midway.v7.generate_real_anomalies
    if errorlevel 1 goto erro

    echo Validando PostgreSQL operacional MIDWAY...
    "%PYTHON_EXE%" -m midway.db.postgres
    if errorlevel 1 goto erro
    goto fim
)

if /I "%~1"=="v7_setup" (
    call "%SCRIPT_DIR%run.bat" anomalias_setup
    goto fim
)

if /I "%~1"=="anomalias_validar" (
    echo Validando nucleo de anomalias MIDWAY...
    "%PYTHON_EXE%" -m unittest tests.test_v7_real_anomalies
    if errorlevel 1 goto erro
    goto fim
)

if /I "%~1"=="v7_validar" (
    call "%SCRIPT_DIR%run.bat" anomalias_validar
    goto fim
)

if /I "%~1"=="admin_bootstrap" (
    echo Criando usuario ADM inicial, se ainda nao existir...
    "%PYTHON_EXE%" -m midway.db.bootstrap_admin
    if errorlevel 1 goto erro
    goto fim
)

if /I "%~1"=="reextrair_metas_uc" (
    echo Reextraindo metas UC IQS sob demanda...
    set "REEXTRAIR_METAS_UC=1"
    "%PYTHON_EXE%" -m midway.extract.metas_uc
    goto fim
)

if /I "%~1"=="extract_uc_fatura" (
    echo Extraindo UCs consideradas na apuracao...
    "%PYTHON_EXE%" -m midway.extract.uc_fatura
    goto fim
)

if /I "%~1"=="auditoria_duplicidade_tipo" (
    echo Auditando duplicidade de interrupcao por COD_TIPO_INTRP 1, 2 e 3...
    "%PYTHON_EXE%" -m midway.auditoria.duplicidade_tipo_intrp
    goto fim
)

if /I "%~1"=="full" (
    echo Executando extracao...
    "%PYTHON_EXE%" -m midway.extract.adms
    if errorlevel 1 goto erro

    echo Executando tratamento...
    "%PYTHON_EXE%" -m midway.transform.tratamento
    if errorlevel 1 goto erro

    goto fim
)

if /I "%~1"=="full_mais_apuracao" (
    echo Executando extracao...
    "%PYTHON_EXE%" -m midway.extract.adms
    if errorlevel 1 goto erro

    echo Executando tratamento...
    "%PYTHON_EXE%" -m midway.transform.tratamento
    if errorlevel 1 goto erro

    echo Extraindo consumidores IQS...
    "%PYTHON_EXE%" -m midway.extract.consumidores
    if errorlevel 1 goto erro

    echo Extraindo UCs consideradas na apuracao...
    "%PYTHON_EXE%" -m midway.extract.uc_fatura
    if errorlevel 1 goto erro

    echo Gerando camada gold e BDO de apuracao previa...
    "%PYTHON_EXE%" -m midway.apuracao.previa
    if errorlevel 1 goto erro

    echo Gerando gold_outlier_uc...
    "%PYTHON_EXE%" -m midway.analytics.outlier_uc
    if errorlevel 1 goto erro

    echo Gerando exportacoes separadas de sobreposicao...
    "%PYTHON_EXE%" -m midway.auditoria.sobreposicoes
    if errorlevel 1 goto erro

    ping -n 2 127.0.0.1 >nul

    echo Gerando exportacao de interrupcoes sem UC...
    "%PYTHON_EXE%" -m midway.auditoria.interrupcao_sem_uc
    if errorlevel 1 goto erro

    echo Normalizando datas das exportacoes auxiliares...
    "%PYTHON_EXE%" -m midway.export.normalizar_datas_iqs
    if errorlevel 1 goto erro

    goto fim
)

echo Opcao invalida: %~1
echo.
goto uso

:uso
echo Uso:
echo   run.bat versao                       Mostra a versao atual do MIDWAY
echo   run.bat painel                       Abre painel Streamlit para avaliar resultados
echo   run.bat api                          Abre MIDWAY API FastAPI em http://127.0.0.1:8000
echo   run.bat frontend                     Abre frontend React em http://localhost:5173
echo   run.bat extract                      Executa apenas a extracao Oracle para DuckDB bruto
echo   run.bat registrar                    Valida DuckDB bruto existente e cria controle de extracao
echo   run.bat tratamento                   Executa apenas o tratamento e exportacao IQS principal
echo   run.bat reprocessar                  Refaz somente o tratamento com REPROCESSAR=1
echo   run.bat reextrair                    Refaz somente a extracao com REEXTRAIR=1
echo   run.bat amostra_raw                  Exporta 100 linhas do hiadms_raw para data\marts
echo   run.bat exportar                     Exporta novamente os CSVs finais sem reprocessar
echo   run.bat exportar_motivo              Exporta teste com NUM_MOTIVO_TRAT_DIF_UCI preenchido
echo   run.bat exportacao_sobreposicao      Processamento separado da sobreposicao total por UC e parcial por UC
echo   run.bat interrupcao_sem_uc           Exporta interrupcoes sem UC para ESTADO 7
echo   run.bat auditar_ajuste_inicio_manobra Gera auditoria de ajuste de inicio de manobra
echo   run.bat exportacoes_auxiliares       Exporta total UC, parcial UC e interrupcao sem UC na ordem correta
echo   run.bat consumidores                 Extrai consumidores IQS para gold_consumidores
echo   run.bat uc_fatura                    Extrai UCs faturadas para gold_uc_fatura
echo   run.bat vrc                          Extrai VRC IQS sob demanda para gold_vrc
echo   run.bat reextrair_vrc                Reextrai VRC IQS com REEXTRAIR_VRC=1
echo   run.bat metas_uc                     Extrai metas UC IQS sob demanda para gold_metas_uc
echo   run.bat reextrair_metas_uc           Reextrai metas UC IQS com REEXTRAIR_METAS_UC=1
echo   run.bat referencia_iqs               Extrai referencia grupo/componente/causa para Envio IQS
echo   run.bat reextrair_referencia_iqs     Reextrai referencia IQS com REEXTRAIR_REFERENCIA_IQS=1
echo   run.bat sincronizar_iqs_raw          Sincroniza data\raw\iqs_raw_^<ANOMES^>.duckdb para o processed
echo   run.bat postgres_validar             Valida conexao PostgreSQL e schema ddcq do MIDWAY 7.0.0
echo   run.bat postgres_status              Verifica se o PostgreSQL local esta rodando
echo   run.bat postgres_start               Inicia PostgreSQL local na instalacao PostgreSQL 18
echo   run.bat postgres_governanca          Aplica tabelas/views de governanca e login
echo   run.bat anomalias_setup              Aplica nucleo e carrega anomalias RAW/SILVER/GOLD
echo   run.bat anomalias_validar            Valida testes unitarios do nucleo de anomalias
echo   run.bat admin_bootstrap              Cria usuario ADM inicial sem senha padrao fixa
echo   run.bat apuracao_parcial             Gera camada gold e BDO de apuracao previa
echo   run.bat extrair_dbguo_reclamacoes    Extrai reclamacoes DBGUO para data\raw
echo   run.bat dbguo_reclamacoes            Materializa silver e gold de reclamacoes DBGUO
echo   run.bat extrair_adms_servicos        Extrai servicos ADMS de backup para data\raw
echo   run.bat correcao_9282                Gera arquivo de tratativa RA 92/82 em data\export\correcao_9282
echo   run.bat analise_tecnica_cache [ANOMES] Materializa cache rapido da Analise Tecnica
echo   run.bat testar_dados                 Executa testes automatizados dos dados tratados
echo   run.bat validar_dados                Executa testes e metricas de qualidade
echo   run.bat metricas_qualidade           Gera metricas estatisticas de qualidade
echo   run.bat amostras_auditoria           Exporta amostras para verificacao manual
echo   run.bat auditoria_duplicidade_tipo   Verifica duplicidade por COD_TIPO_INTRP 1, 2 e 3
echo   run.bat full                         Executa extracao e depois tratamento
echo   run.bat full_mais_apuracao           Executa extracao, tratamento, consumidores, UC fatura, apuracao e exportacoes auxiliares
echo.
echo Exemplos:
echo   set REEXTRAIR=1
echo   set REPROCESSAR=1
echo   run.bat full_mais_apuracao
echo.
echo   set REEXTRAIR=
echo   set REPROCESSAR=1
echo   run.bat tratamento
echo   run.bat exportacoes_auxiliares
echo   run.bat apuracao_parcial
echo   run.bat dbguo_reclamacoes
echo   run.bat referencia_iqs
goto fim

:erro
echo.
echo Processo interrompido por erro.
exit /b 1

:fim
endlocal
