# MIDWAY - Tratamento IQS ADMS

Versao atual: `6.2.0`

O MIDWAY e uma ferramenta local de ETL e pre-apuracao para tratar registros de interrupcao do ADMS antes da carga no IQS.

O objetivo e criar uma camada intermediaria mais consistente para:

- extrair dados do IQS/ADMS;
- organizar bases RAW, SILVER e GOLD em DuckDB;
- tratar sobreposicoes temporais por UC;
- gerar previa de DEC/FEC, DIC/FIC, DMIC, DICRI e DISE;
- calcular previa de compensacoes/ressarcimentos;
- gerar CSVs de retorno no layout aceito pelo IQS;
- apoiar auditoria da pos-operacao com metricas, amostras e painel Streamlit.

> Dados operacionais ficam em `data/` e nao devem ser versionados no Git, exceto `data/input`, que guarda dicionarios e listas auxiliares pequenas usadas pelo codigo.

## Fluxo Oficial

```text
Oracle IQS / ADMS
  -> data/raw/iqs_adms_raw_<ANOMES>.duckdb
  -> data/raw/iqs_raw_<ANOMES>.duckdb
  -> data/processed/iqs_adms_processed_<ANOMES>.duckdb
  -> data/marts/ auditorias, metricas e conferencias
  -> data/export/ arquivos CSV para carga no IQS
```

Fluxo detalhado:

```text
docs/14_fluxo_oficial_atual.md
```

## Estrutura do Projeto

```text
run.bat          ponto unico de execucao operacional
midway/          pacote Python principal
  extract/       extracoes ADMS/IQS
  transform/     tratamento, sincronizacao e normalizacao
  apuracao/      apuracao previa e camadas gold
  auditoria/     auditorias e exportacoes auxiliares
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

Fluxo local mais usado quando o RAW ja existe:

```bat
set ANOMES=202606
set REPROCESSAR=1
run.bat reprocessar
run.bat apuracao_parcial
run.bat validar_dados
```

Abrir painel de conferencia:

```bat
run.bat painel
```

## Comandos Principais

| Comando | Uso |
| --- | --- |
| `run.bat extract` | Extrai Oracle para DuckDB bruto |
| `run.bat registrar` | Registra DuckDB bruto local ja existente |
| `run.bat tratamento` | Executa tratamento e exportacao principal |
| `run.bat reprocessar` | Reexecuta o tratamento com `REPROCESSAR=1` |
| `run.bat apuracao_parcial` | Gera camadas gold, BDO e previa de ressarcimento |
| `run.bat validar_dados` | Executa testes automatizados e metricas |
| `run.bat painel` | Abre painel Streamlit |
| `run.bat exportar` | Regenera CSVs finais sem refazer tratamento |
| `run.bat exportacoes_auxiliares` | Gera exportacoes separadas de sobreposicao e sem UC |
| `run.bat sincronizar_iqs_raw` | Sincroniza `data/raw/iqs_raw_<ANOMES>.duckdb` para o processed |
| `run.bat extrair_dbguo_reclamacoes` | Extrai reclamacoes DBGUO para `data/raw` |
| `run.bat dbguo_reclamacoes` | Materializa silver/gold de reclamacoes DBGUO |
| `run.bat extrair_adms_servicos` | Extrai servicos ADMS de backup para `data/raw` |
| `run.bat vrc` | Extrai VRC IQS sob demanda |
| `run.bat metas_uc` | Extrai metas UC IQS sob demanda |

Para ver todos os comandos:

```bat
run.bat
```

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

Detalhamento:

```text
docs/10_prodist_modulo8.md
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

Detalhamento:

```text
docs/12_painel_streamlit.md
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

Exportacoes auxiliares:

```bat
run.bat exportacoes_auxiliares
```

Pastas geradas:

```text
data/export/sobreposicao_total_uc
data/export/sobreposicao_UC_parcial
data/export/interrupcao_sem_uc
```

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

Documentos principais:

```text
docs/00_especificacao.md
docs/01_controle.md
docs/02_auditoria.md
docs/09_proposta_melhoria.md
docs/10_prodist_modulo8.md
docs/11_testes_automatizados_estatisticos.md
docs/12_painel_streamlit.md
docs/13_organizacao_arquivos.md
docs/14_fluxo_oficial_atual.md
```

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

## Destaques da 6.2.0

- Exportacoes IQS em layout padrao: `|`, UNIX/LF e ISO-8859-1 transliterado.
- Exportador separado para sobreposicao total por UC, parcial por UC e interrupcao sem UC.
- Reclamacoes DBGUO com janela do mes de apuracao `+-2 dias`.
- Analise de reclamacoes com causa provavel, aderencia IQS e ranking por ocorrencia.
- Extrator RAW de servicos ADMS para apoiar causa/componente e improcedencia.
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
cd /d D:\MIDWAY_novo

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
run.bat exportacoes_auxiliares
run.bat validar_dados

## Processo de restração para ao longo do mes
cd /d D:\MIDWAY_novo

set ANOMES=202606
set REEXTRAIR=1
set REPROCESSAR=1

run.bat extract
run.bat tratamento
run.bat apuracao_parcial
run.bat exportacoes_auxiliares
run.bat validar_dados
