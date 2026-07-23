# MIDWAY - Anomalias OMS/ADMS para IQS

Versao atual: `7.1.0`

O MIDWAY e uma plataforma local de ETL, apuracao, auditoria e decisao governada para tratar anomalias dos dados OMS/ADMS antes da carga no IQS.

O objetivo principal e criar uma camada intermediaria confiavel para:

- extrair dados do IQS/ADMS;
- organizar bases RAW, SILVER e GOLD em DuckDB;
- detectar anomalias em ocorrencias, interrupcoes, UCs, equipamentos, alimentadores e conjuntos;
- reunir evidencias tecnicas a partir de OMS/ADMS, servicos, reclamacoes, referencia IQS e apuracao;
- gerar previa de DEC/FEC, DIC/FIC, DMIC, DICRI e DISE;
- calcular previa de compensacoes/ressarcimentos;
- apoiar decisao humana auditavel;
- gerar CSVs de retorno no layout aceito pelo IQS para qualquer modulo aprovado;
- apoiar auditoria da pos-operacao com metricas, amostras e paineis.

> Importante: a regra `92/82` e um modulo especializado ja implementado, nao o objetivo central do MIDWAY. O norte atual esta em `docs/33_reorientacao_anomalias_oms_iqs.md`.

> Dados operacionais ficam em `data/` e nao devem ser versionados no Git, exceto `data/input`, que guarda dicionarios e listas auxiliares pequenas usadas pelo codigo.

## Fluxo Oficial

```text
Oracle IQS / ADMS
  -> data/raw/iqs_adms_raw_<ANOMES>.duckdb
  -> data/raw/iqs_raw_<ANOMES>.duckdb
  -> data/processed/iqs_adms_processed_<ANOMES>.duckdb
  -> motor de anomalias e evidencias
  -> governanca e decisao humana
  -> data/marts/ auditorias, metricas e conferencias
  -> data/export/ arquivos CSV aprovados para carga no IQS
```

Fluxo detalhado:

```text
docs/14_fluxo_oficial_atual.md
docs/35_contrato_exportacao_iqs.md
docs/36_regras_prodist_copel.md
docs/37_visao_produto_governanca_midway.md
```

## Estrutura do Projeto

```text
run.bat          ponto unico de execucao operacional
midway/          pacote Python principal
  extract/       extracoes ADMS/IQS
  transform/     tratamento, sincronizacao e normalizacao
  apuracao/      apuracao previa e camadas gold
  auditoria/     auditorias e exportacoes auxiliares
  v7/            nucleo de anomalias e evidencias governadas
  export/        exportacao CSV IQS
  web/           painel Streamlit multipage
    home.py      orquestrador do painel
    pages/       paginas Streamlit
    library/     funcoes, consultas e componentes reutilizaveis
tools/           utilitarios locais
tests/           testes automatizados dos dados tratados
docs/            documentacao tecnica e historico de decisoes
SQL/             consultas Oracle de apoio
scripts/legacy/  atalhos antigos preservados por historico
notebooks/       verificacoes exploratorias
data/            dados locais; somente data/input e versionado
```

## Requisitos

- Windows com CMD ou PowerShell;
- Python 3.11+;
- dependencias em `requirements.txt`;
- acesso Oracle apenas para etapas de extracao;
- DuckDB local para processamento e consultas.

Instale as dependencias:

```bat
cd /d D:\MIDWAY
pip install -r requirements.txt
```

## Configuracao

Crie um arquivo `.env` na raiz do projeto. Use `.env.example` como referencia.

Exemplo minimo:

```env
IQS_UID=usuario
IQS_PWD=senha
IQS_DB=dsn
IQS_CONFIG_DIR=C:\oracle\network\admin
ANOMES=202606
```

O `python-oracledb` usa modo thin por padrao. Se precisar do modo thick:

```env
IQS_ORACLE_THICK_MODE=1
IQS_ORACLE_CLIENT_LIB_DIR=C:\oracle\instantclient_21_13
```

## Execucao Rapida

Entre na pasta:

```bat
cd /d D:\MIDWAY
```

Consultar versao:

```bat
run.bat versao
```

Abrir toda a stack do sistema (PostgreSQL local, API FastAPI e painel React `MIDWAY 7.1.0`):

```bat
inicio.bat
```

> **Aviso de Migração (v7.1.0):** A execução encadeada manual via `.env` (onde era preciso rodar `reprocessar`, `apuracao_parcial`, `validar_dados` etc separadamente) caiu em desuso. Todo o fluxo local agora é 100% governado e executado diretamente pela interface gráfica no menu **Administração > Processamentos**, utilizando o novo orquestrador central `etl`.

Preparar o núcleo de anomalias no PostgreSQL local pela primeira vez:

```bat
run.bat anomalias_setup
```

Abrir painel Streamlit legado de conferencia técnica:

```bat
run.bat painel
```

## Fechamento e Abertura de Novo Mês (Virada de Ciclo)

O MIDWAY agora possui uma interface de Governança para realizar a virada de mês (fechar um ciclo e abrir outro) sem a necessidade de editar o `.env` manualmente.

Para iniciar um novo mês:
1. Abra a interface React em seu navegador.
2. Navegue até o menu **Administração**.
3. Acesse a guia **Ciclo de Apuração**.
4. Clique no botão **"Fechar Mês Definitivamente"**. Isso bloqueará o mês atual contra alterações e atualizará automaticamente a variável `ANOMES` do seu arquivo `.env` para o mês seguinte. A tela sofrerá um "reload" e o sistema já acordará no novo mês.
5. Acesse a guia **Processamentos**.
6. Selecione no dropdown a opção **`run.bat etl — Pipeline ETL Central`** e clique em **Executar no backend**.
Isso vai realizar automaticamente a extração limpa (ADMS/IQS), o tratamento DuckDB e as apurações prévias daquele novo mês de maneira encadeada.

Em caso de necessidade de roll-back, administradores podem utilizar a opção "Reabrir Mês", que reverterá as ações do `.env` e abrirá a base mediante registro de justificativa na auditoria.

## Módulos de Anomalia e Orquestração

O MIDWAY evoluiu para uma arquitetura escalável e orientada a objetos focada no motor de propostas. Todos os agentes analíticos agora herdam da classe `BaseModulo` e são executados centralizadamente pelo **Orquestrador Central**. 

O orquestrador é responsável por invocar os módulos, compilar a lista unificada de `Propostas de Tratamento` e persisti-las em bloco (`bulk insert`) no PostgreSQL local (tabela `ddcq.midway_propostas_tratamento`), garantindo enorme performance e zero vazamento de memória.

Módulos regulatórios (Apurados via SQL/DuckDB puro na etapa de Apuração):

| Módulo | Escopo | Objetivo |
| --- | --- | --- |
| DIC/FIC PRODIST | UC/indicador individual | Calcular DIC, FIC, DMIC, DICRI e DISE conforme PRODIST Módulo 8 e filtros COPEL |
| DEC/FEC PRODIST | conjunto/regional/empresa | Calcular DEC e FEC com denominador COPEL de consumidores faturados |
| Ressarcimento PRODIST | UC/compensação | Calcular compensação financeira por continuidade conforme metas, VRC e filtros COPEL |

Módulos de anomalia migrados para a nova arquitetura (Orquestrador `BaseModulo`):

| Módulo | Escopo | Objetivo |
| --- | --- | --- |
| Durações Negativas | Interrupção | Sanitiza ocorrências onde FIM < INÍCIO para evitar crash nos módulos temporais |
| Sobreposição UC (Total/Parcial) | UC/interrupção | Corrige conflito temporal (Total: anula, Parcial: trunca) preservando a base apurável |
| Interrupção sem UC | Interrupção/ocorrência | Identifica eventos totalmente esvaziados (Estado 7) após a sobreposição 91/D |
| Ajuste Início Manobra | Interrupção | Reposiciona a chave `NUM_INTRP_INIC_MANOBRA_UCI` para pai válido |
| Duplicidade Tipo Intrp | Interrupção | Oculta registros clones idênticos (dupla persistência ADMS/OMS) |
| Agente de Causa/Componente | Ocorrência/interrupção | Sugere par Componente/Causa cruzando serviços e reclamações reais |
| Suspeita Falha Religador (RA) | Equipamento/alimentador | Detecta operações sucessivas de RA com FIC alto e sem reclamações |
| Correção 92/82 | Especialização Causa/Comp | Usa Heurística e NLP para reclassificar o lixo genérico de religadores |

## Comandos Principais (Atualizados v7.1.0)

| Comando | Uso |
| --- | --- |
| `inicio.bat` | Inicia PostgreSQL local, API FastAPI e frontend React |
| `run.bat etl` | **(NOVO)** Roda o orquestrador principal completo (Extração, Tratamento e Apuração) |
| `run.bat orquestrador` | Roda a inteligência dos módulos de anomalia e salva propostas no Postgres |
| `run.bat extract` | Extrai Oracle para DuckDB bruto (Modo granular) |
| `run.bat registrar` | Registra DuckDB bruto local ja existente (Modo granular) |
| `run.bat validar_dados` | Executa testes automatizados e metricas |
| `run.bat painel` | Abre painel Streamlit legado |
| `run.bat exportar` | Regenera CSVs finais a partir dos dados já processados |
| `run.bat extrair_dbguo_reclamacoes` | Extrai reclamacoes DBGUO para `data/raw` |
| `run.bat extrair_adms_servicos` | Extrai servicos ADMS de backup para `data/raw` |
| `run.bat anomalias_setup` | Aplica núcleo de anomalias e prepara o banco PostgreSQL |
| `run.bat vrc` | Extrai VRC IQS sob demanda |
| `run.bat metas_uc` | Extrai metas UC IQS sob demanda |

Para ver todos os comandos:

```bat
run.bat
```

## Migração COPEL / DBGUO-DDCQ

O desenvolvimento local usa PostgreSQL local para governança, mas o destino corporativo planejado é DBGUO/PostgreSQL no schema `ddcq`.

Documentos ativos:

- `docs/migracao_copel_dbguo_ddcq.md`: guia de provisão, `.env`, DBeaver, scripts e validação.
- `docs/pedencia_para_rodar_copel.md`: checklist do que falta para rodar dentro da rede COPEL.
- `SQL/postgres/ddcq/`: scripts versionados do schema operacional.

## Dados Locais

Estrutura esperada:

```text
data/
  raw/         DuckDBs brutos
  processed/   DuckDB processado
  marts/       auditorias, metricas e conferencias
  export/      CSVs finais e auxiliares
  control/     locks e arquivos .done.json
  input/       dicionarios versionados e aceites manuais
  logs/        logs de execucao
  temp/        temporarios DuckDB
```

Arquivos importantes:

```text
data/raw/iqs_adms_raw_<ANOMES>.duckdb
data/raw/iqs_raw_<ANOMES>.duckdb
data/raw/adms_servicos_raw_<ANOMES>.duckdb
data/processed/iqs_adms_processed_<ANOMES>.duckdb
```

## Controle de Execucao

O processo usa `data/control` para evitar repeticao acidental de etapas pesadas.

Arquivos de controle:

```text
extract_<ANOMES>.done.json
tratamento_<ANOMES>.done.json
extract_<ANOMES>.lock
tratamento_<ANOMES>.lock
```

Regras:

- `extract` nao reextrai se `extract_<ANOMES>.done.json` existir, exceto com `REEXTRAIR=1`;
- `tratamento` exige extracao finalizada ou registro do RAW existente;
- `tratamento` nao reprocessa se `tratamento_<ANOMES>.done.json` existir, exceto com `REPROCESSAR=1`;
- arquivos `.lock` impedem execucoes simultaneas da mesma etapa.

Se houver lock antigo e nenhum processo rodando, remova manualmente o `.lock` correspondente em `data/control`.

## Camadas Geradas

Principais tabelas no DuckDB processado:

```text
silver_iqs_consumidores
silver_iqs_uc_fatura
silver_iqs_vrc
silver_iqs_metas_uc
gold_interrupcao_tratada
gold_apuracao_uc
gold_continuidade_uc
gold_ressarcimento_prodist
gold_interrupcao_sem_uc
gold_ocorrencia_sem_uc
```

As tabelas `gold_consumidores`, `gold_uc_fatura`, `gold_vrc` e `gold_metas_uc` tambem podem ser materializadas por compatibilidade com as analises atuais.

## Regras Principais de Tratamento

### Sobreposicao Total por UC

Quando uma UC esta totalmente contida por outra interrupcao da mesma UC, mesmo `COD_TIPO_INTRP` e mesmo `TIPO_PROTOC_JUSTIF_UCI`, o registro contido recebe:

```text
NUM_MOTIVO_TRAT_DIF_UCI = 91
INDIC_SIT_PROCES_INDIC_UCI = D
```

### Sobreposicao Parcial por UC

Quando ha sobreposicao parcial para a mesma UC, mesmo `COD_TIPO_INTRP` e mesmo `TIPO_PROTOC_JUSTIF_UCI`, o inicio do segundo trecho e ajustado:

```text
DTHR_INICIO_INTRP_UC = DATA_HORA_FIM_INTRP anterior
```

Quando aplicavel, `NUM_INTRP_INIC_MANOBRA_UCI` recebe a referencia da interrupcao anterior.

### Interrupcao sem UC Apuravel

A apuracao identifica interrupcoes que permanecem em `ESTADO_INTRP = 4`, mas ficaram sem UC apuravel apos o tratamento. Esses casos sao materializados em:

```text
gold_interrupcao_sem_uc
gold_ocorrencia_sem_uc
```

Essas camadas apoiam analise de ocorrencias candidatas a descarte integral por criterio de ocorrencia completa.

## Codigos de Referencia

| Campo | Codigo | Uso |
| --- | --- | --- |
| `COD_TIPO_INTRP` | `1` | Acidental |
| `COD_TIPO_INTRP` | `2` | Programado |
| `COD_TIPO_INTRP` | `3` | Voluntario |
| `TIPO_PROTOC_JUSTIF_UCI` | `0` | Base liquida para `DIC`, `FIC` e `DMIC` |
| `TIPO_PROTOC_JUSTIF_UCI` | `1` | Dia critico, base para `DICRI` |
| `TIPO_PROTOC_JUSTIF_UCI` | `5`/`6` | ISE, base para `DISE` |

`NUM_MOTIVO_TRAT_DIF_UCI` deve estar nulo para a UC entrar nos calculos liquidos de continuidade.

## Apuracao e Ressarcimento

A etapa `apuracao_parcial` cria:

- `gold_apuracao_uc`;
- `gold_continuidade_uc`;
- `gold_ressarcimento_prodist`;
- BDO de apuracao previa;
- arquivos de conferencia em `data/marts`.

Exemplo:

```bat
run.bat apuracao_parcial
```

O calculo de compensacao considera bases financeiras separadas dos indicadores realizados:

```text
DIC_BASE_COMPENSACAO
FIC_BASE_COMPENSACAO
DMIC_BASE_COMPENSACAO
```

Eventos com `COD_COMP_INTRP = 52` ou `COD_CAUSA_INTRP = 71` nao compoem `DIC`, `FIC`, `DMIC` nem a base financeira de compensacao.

Eventos de posto particular (`INDIC_PROPR_POSTO_INTRP = P`), chave particular e UC acessante permanecem como filtros da base financeira de compensacao, sem remover a rastreabilidade operacional.

Detalhamento ativo:

```text
docs/14_fluxo_oficial_atual.md
docs/modulos/ressarcimento_atipico.md
```

## Painel Streamlit

O painel facilita a conferencia sem leitura manual de CSVs grandes:

```bat
run.bat painel
```

Paginas disponiveis:

- `01 Conferencia ETL`;
- `02 Analytics Pos-Operacao`;
- `03 Dia Critico`;
- `04 Simulacao ISE`;
- `05 Validacao Pos-Operacao`;
- `06 Executivo`;
- `07 SQL`.

Recursos:

- metricas de qualidade;
- conferencia de sobreposicoes;
- indicadores DIC/FIC;
- ressarcimento PRODIST;
- arquivos gerados;
- consulta SQL com catalogo de tabelas;
- ranking estatistico de ocorrencias para verificacao.

Detalhamento ativo:

```text
docs/14_fluxo_oficial_atual.md
docs/modulos/README.md
```

## Testes e Qualidade

Executar testes dos dados tratados:

```bat
run.bat testar_dados
```

Executar testes e gerar metricas:

```bat
run.bat validar_dados
```

As metricas sao exportadas para:

```text
data/marts/
```

## Exportacoes

Arquivos finais para envio ao IQS:

```text
data/export/
```

Formato geral:

```text
Interrupcoes_IQS_<YYYYMMDDHHMMSS>_<REGIONAL>.CSV
Exportacao_IQS_<YYYYMMDDHHMMSS>_RESUMO.TXT
```

Exportacoes auxiliares (Legado inativado):

A rotina de anomalias (Sobreposições e Sem UC) foi migrada para o motor de Propostas de Tratamento (`run.bat orquestrador`). As planilhas manuais geradas anteriormente foram descontinuadas em favor da interface Web e persistência estruturada no Postgres.

## Problemas Comuns

### `run.bat` nao reconhecido

Execute a partir da pasta do projeto:

```bat
cd /d D:\MIDWAY
run.bat tratamento
```

### DuckDB em uso

Feche conexoes abertas no DBeaver, Streamlit ou outro processo antes de reprocessar:

```text
data/processed/iqs_adms_processed_<ANOMES>.duckdb
```

### Reprocessar sem reextrair

```bat
set REEXTRAIR=
set REPROCESSAR=1
run.bat tratamento
run.bat apuracao_parcial
```

### Registrar RAW local ja existente

Use quando o DuckDB bruto ja existe em `data/raw`, mas o controle `.done.json` ainda nao existe:

```bat
run.bat registrar
```

### Gerar CSVs sem refazer tratamento

```bat
run.bat exportar
```

## Documentacao

Documentos principais ativos:

```text
docs/README.md
docs/00_especificacao.md
docs/13_organizacao_arquivos.md
docs/14_fluxo_oficial_atual.md
docs/33_reorientacao_anomalias_oms_iqs.md
docs/34_governanca_exportacao_iqs.md
docs/modulos/README.md
```

Documentos antigos ficam em `docs/historico/` apenas como memoria tecnica, nao como especificacao vigente.

## Versionamento

A versao atual fica em:

```text
VERSION
midway/__init__.py
CHANGELOG.md
```

Consultar:

```bat
run.bat versao
```

## Destaques da 7.1.0

- **Nova Arquitetura `BaseModulo` e Orquestrador Central**: Backend de auditoria refatorado para um pipeline massivamente escalável de propostas de tratamento.
- **Persistência de Alto Desempenho**: Substituição de gravações individuais por Bulk Insert (execute_values) no PostgreSQL.
- Exportacoes IQS em layout padrao: `|`, UNIX/LF e ISO-8859-1 transliterado.
- Datas de pacote IQS normalizadas para `dd/mm/aaaa hh:mm:ss` e inteiros sem decimal pelo helper oficial.
- Exportador separado para sobreposicao total por UC, parcial por UC e interrupcao sem UC.
- Reclamacoes DBGUO com janela do mes de apuracao `+-2 dias`.
- Analise de reclamacoes com causa provavel, aderencia IQS e ranking por ocorrencia.
- Extrator RAW de servicos ADMS para apoiar causa/componente e improcedencia.
- Página `09 Qualidade de Interrupções` no Streamlit para cruzar interrupções, reclamações e serviços.
- Página `10 Ajuste Manual IQS` para registrar decisões e gerar CSV corrigido no layout IQS.
- Ajuste Manual IQS aceita data/hora da ocorrência e mostra evidências coloridas para o analista.
- DIC/FIC da qualidade de interrupções calculado pela `gold_apuracao_uc`.
- `data/input` versionado para distribuir `causa.csv`, `componente.csv` e listas auxiliares.
- Comandos DBGUO consolidados no `run.bat`.

## Observacao de Seguranca

Nao versionar:

- `data/`, exceto `data/input`;
- `.env`;
- bases `.duckdb`;
- logs e caches locais.

Essas regras estao em `.gitignore`.

## Processo de restração para inicio de mes
cd /d D:\MIDWAY

set ANOMES=202606
set REEXTRAIR=1
set REPROCESSAR=1
set REEXTRAIR_VRC=1
set REEXTRAIR_METAS_UC=1

run.bat extract
run.bat tratamento
run.bat consumidores
run.bat uc_fatura
run.bat vrc
run.bat metas_uc
run.bat apuracao_parcial
run.bat orquestrador
run.bat validar_dados

## Processo de restração para ao longo do mes
cd /d D:\MIDWAY

set ANOMES=202606
set REEXTRAIR=1
set REPROCESSAR=1

run.bat extract
run.bat tratamento
run.bat apuracao_parcial
run.bat orquestrador
run.bat validar_dados

## Rodar dados do react

run.bat anomalias_setup
run.bat dbguo_reclamacoes
run.bat analise_tecnica_cache
run.bat orquestrador