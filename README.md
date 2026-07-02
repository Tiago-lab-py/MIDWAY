# MIDWAY - Tratamento IQS ADMS

Versao atual: `6.0.0`

Processo para extrair dados do IQS Oracle, gerar DuckDB bruto, aplicar regras de tratamento de sobreposicao ADMS e exportar arquivos CSV para carga no IQS.

Fluxo oficial atual:

```text
docs/14_fluxo_oficial_atual.md
```

## Fluxo

```text
Oracle IQS
  -> midway.extract.adms
  -> data/raw/iqs_adms_raw_<ANOMES>.duckdb
  -> midway.transform.tratamento
  -> data/processed/iqs_adms_processed_<ANOMES>.duckdb
  -> data/marts/ auditorias e conferencias
  -> data/export/ arquivos finais IQS
```

## Estrutura

```text
run.bat      ponto unico de execucao operacional
midway/      pacote Python principal
  extract/     extratores ADMS/IQS
  transform/   utilitarios e sincronizacao de transformacao
  auditoria/   auditorias e exportacoes auxiliares
  apuracao/    rotinas de apuracao ja modularizadas
  export/      exportacao IQS
  web/         painel Streamlit
scripts/
  legacy/    atalhos .bat antigos preservados por historico
notebooks/   verificacoes exploratorias
tools/       ferramentas auxiliares locais
tests/       testes automatizados dos dados tratados
data/
  amostra/     modelo de formato CSV
  control/     locks e arquivos .done.json
  export/      arquivos finais para envio ao IQS
  input/       aceites manuais de anomalias revisadas
  logs/        logs das execucoes
  marts/       auditorias, anomalias e pre-export bloqueado
  processed/   DuckDB processado
  raw/         DuckDB bruto extraido do Oracle
  temp/        temporarios do DuckDB
docs/
  00_especificacao.md
  01_controle.md
  02_auditoria.md
  13_organizacao_arquivos.md
```

Observacao: os comandos oficiais devem ser executados pelo `run.bat`. Os `.bat` antigos ficam em `scripts/legacy/` apenas como atalhos historicos para o proprio `run.bat`.

## Configuracao

Crie ou ajuste o arquivo `.env` na raiz do projeto.

```env
IQS_UID=usuario
IQS_PWD=senha
IQS_DB=dsn
IQS_CONFIG_DIR=C:\oracle\network\admin
ANOMES=202605
```

O `python-oracledb` usa modo thin por padrao. Use modo thick somente se necessario:

```env
IQS_ORACLE_THICK_MODE=1
IQS_ORACLE_CLIENT_LIB_DIR=C:\oracle\instantclient_21_13
```

## Execucao pelo CMD

Entre na pasta do projeto:

```bat
cd /d D:\MIDWAY
```

Consultar versao:

```bat
run.bat versao
```

Comandos principais:

```bat
run.bat extract       :: extrai Oracle para DuckDB bruto
run.bat tratamento    :: executa tratamento e exportacao
run.bat full          :: executa extract e depois tratamento
run.bat registrar     :: registra DuckDB bruto ja existente no controle
run.bat reprocessar   :: refaz somente o tratamento
run.bat reextrair     :: refaz somente a extracao
run.bat exportar      :: gera arquivos IQS sem refazer o tratamento
run.bat validar_dados :: executa testes e metricas de qualidade
run.bat painel        :: abre painel Streamlit de avaliacao
```

Para forcar extracao e tratamento completos:

```bat
set REEXTRAIR=1
set REPROCESSAR=1
run.bat full
```

Depois, limpe as variaveis se continuar usando a mesma janela:

```bat
set REEXTRAIR=
set REPROCESSAR=
```

## Controle de execucao

O processo usa `data/control` para evitar repeticao acidental de etapas pesadas.

Arquivos principais:

```text
extract_<ANOMES>.done.json
tratamento_<ANOMES>.done.json
extract_<ANOMES>.lock
tratamento_<ANOMES>.lock
```

Regras:

- `midway.extract.adms` nao reextrai se `extract_<ANOMES>.done.json` ja existir, exceto com `REEXTRAIR=1`.
- `midway.transform.tratamento` exige extracao finalizada.
- `midway.transform.tratamento` nao reprocessa se `tratamento_<ANOMES>.done.json` ja existir, exceto com `REPROCESSAR=1`.
- arquivos `.lock` impedem duas execucoes simultaneas da mesma etapa.

## Saidas

Arquivos finais para envio ao IQS ficam somente em:

```text
data/export/
```

Os arquivos finais possuem nomes de colunas fixos aceitos pelo IQS. Os valores sao gerados a partir do RAW original (`hiadms_raw`) com pequenas mudancas de grafia nos nomes das colunas.

Na pratica:

```text
CSV final = RAW original renomeado para o layout IQS + ajustes do tratamento
```

Somente os campos abaixo sao sobrescritos pelas regras de tratamento:

```text
ESTADO_INTRP
DTHR_INICIO_INTRP_UC
NUM_INTRP_INIC_MANOBRA_UCI
NUM_MOTIVO_TRAT_DIF_UCI
INDIC_SIT_PROCES_INDIC_UCI
```

O processo nao preenche campos com espaco em branco por padrao. Campos fora das regras de tratamento preservam o valor do RAW; se o RAW estiver nulo ou vazio, o CSV tambem fica vazio.

O processo gera em `data/marts` o arquivo:

```text
Mapeamento_Layout_IQS_<timestamp>.CSV
```

Use esse arquivo para conferir quais colunas do layout vieram do bruto, quais vieram do tratamento e quais ainda ficaram sem origem.

Formato:

```text
Interrupcoes_IQS_<YYYYMMDDHHMMSS>_<REGIONAL>.CSV
Exportacao_IQS_<YYYYMMDDHHMMSS>_RESUMO.TXT
```

Auditorias e conferencias ficam em:

```text
data/marts/
```

Incluem:

```text
Auditoria_Outliers_Bruto_IQS_<timestamp>.CSV
Auditoria_ESTADO_7_IQS_<timestamp>.CSV
Auditoria_UC_91_D_IQS_<timestamp>.CSV
Auditoria_Manobra_HCAI_IQS_<timestamp>.CSV
*_ANOMALIAS.CSV
*_RESUMO.TXT
PRE_EXPORT_Interrupcoes_IQS_<timestamp>_<REGIONAL>.CSV
```

Arquivos `PRE_EXPORT_...` sao apenas para conferencia quando existe anomalia bloqueante. Eles nao devem ser enviados ao IQS.

## Aceite de anomalias ESTADO 7

Quando a auditoria `ESTADO_INTRP = 7` encontrar anomalias, o processo bloqueia os arquivos oficiais em `data/export` e gera pendencias em:

```text
data/marts/Auditoria_ESTADO_7_IQS_<timestamp>_ANOMALIAS_PENDENTES.CSV
```

Para liberar anomalias revisadas, preencha:

```text
data/input/estado_7_aceitas.csv
```

Layout:

```text
NUM_SEQ_INTRP_REGISTRO_7|NUM_SEQ_INTRP_REGISTRO_MANTIDO|RESULTADO_AUDITORIA|MOTIVO_ACEITE|APROVADO_POR|DATA_APROVACAO
```

Depois rode:

```bat
run.bat reprocessar
```

Anomalias que nao estiverem em `estado_7_aceitas.csv` continuam bloqueando. O arquivo `data/input/estado_7_desconsideradas.csv` e documental e nao libera exportacao.

## Regras principais

1. Sobreposicao total por equipamento:
   - remove interrupcao duplicada como um todo;
   - classifica como `ESTADO_INTRP = 7`;
   - exige outro registro `ESTADO_INTRP = 4` cobrindo o periodo do equipamento.

2. Sobreposicao total por UC:
   - descarta somente a UC;
   - mantem a interrupcao em `ESTADO_INTRP = 4`;
   - preenche `NUM_MOTIVO_TRAT_DIF_UCI = 91`;
   - preenche `INDIC_SIT_PROCES_INDIC_UCI = D`.

3. Sobreposicao parcial por UC:
   - ajusta `DTHR_INICIO_INTRP_UC`;
   - preenche `NUM_INTRP_INIC_MANOBRA_UCI` quando aplicavel.

4. Manobras HCAI:
   - interrupcoes com `NUM_INTRP_INIC_MANOBRA_HCAI` nao sao classificadas automaticamente como `ESTADO_INTRP = 7`;
   - a referencia HCAI e usada como referencia da interrupcao pai.

## Auditorias

A auditoria de `ESTADO_INTRP = 7` e bloqueante. Se houver anomalias:

- os arquivos oficiais em `data/export` nao sao gerados;
- os arquivos de auditoria e `PRE_EXPORT_...` sao gerados em `data/marts`;
- o controle `tratamento_<ANOMES>.done.json` nao e gravado.

Consulte:

```text
docs/00_especificacao.md
docs/01_controle.md
docs/02_auditoria.md
```

## Problemas comuns

### `run.bat` nao reconhecido

Execute a partir da pasta do projeto:

```bat
cd /d D:\MIDWAY
run.bat tratamento
```

Ou use o caminho completo:

```bat
D:\MIDWAY\run.bat tratamento
```

### DuckDB em uso pelo DBeaver

Feche a conexao do banco no DBeaver antes de reprocessar:

```text
data/processed/iqs_adms_processed_<ANOMES>.duckdb
```

### Forcar nova extracao

```bat
set REEXTRAIR=1
run.bat extract
```

### Forcar novo tratamento

```bat
set REPROCESSAR=1
run.bat tratamento
```

### Gerar somente arquivos finais

Use quando o tratamento ja foi executado e voce quer apenas regenerar os CSVs em `data/export`.

```bat
run.bat exportar
```

Esse comando usa `data/processed/iqs_adms_processed_<ANOMES>.duckdb` e `data/raw/iqs_adms_raw_<ANOMES>.duckdb`. Ele nao refaz a extracao Oracle nem as regras de tratamento.
## Atualizacao operacional

### Fluxo para o mes configurado no `.env`

O mes de processamento e controlado por `ANOMES` no arquivo `.env`.

Os SQLs Oracle ficam centralizados na pasta `SQL/`:

```text
SQL/IQS_consumidor.sql
SQL/IQS_uc_fatura.sql
SQL/IQS_vrc.sql
SQL/IQS_METAS UC 2026.sql
```

O VRC e as metas UC sao extraidos sob demanda, pois podem retornar muitos registros e nao fazem parte do fluxo automatico principal.
As extracoes auxiliares do IQS ficam agora em:

```text
data/raw/iqs_raw_<ANOMES>.duckdb
```

Tabelas raw:

```text
raw_iqs_consumidores
raw_iqs_uc_fatura
raw_iqs_vrc
raw_iqs_metas_uc
```

Na apuracao, essas tabelas sao sincronizadas para o DuckDB processado como `silver_iqs_consumidores`, `silver_iqs_uc_fatura`, `silver_iqs_vrc` e `silver_iqs_metas_uc`. As tabelas `gold_consumidores`, `gold_uc_fatura`, `gold_vrc` e `gold_metas_uc` continuam sendo criadas por compatibilidade com as camadas analiticas atuais.

Comandos:

```bat
run.bat vrc
run.bat reextrair_vrc
run.bat metas_uc
run.bat reextrair_metas_uc
```

Saida materializada no processado:

```text
silver_iqs_consumidores
silver_iqs_uc_fatura
silver_iqs_vrc
silver_iqs_metas_uc
gold_consumidores
gold_uc_fatura
gold_vrc
gold_metas_uc
```

### Continuidade por UC

A apuracao parcial cria a tabela:

```text
gold_continuidade_uc
```

Ela consolida `DIC`, `FIC`, `DMIC`, `DIC_DICRI`, `FIC_DICRI`, `DIC_ISE`, `FIC_ISE`, metas individuais e percentuais de ultrapassagem por UC.

Antes de rodar a apuracao parcial com continuidade individual, garanta que as metas UC foram extraidas:

```bat
run.bat vrc
run.bat metas_uc
run.bat apuracao_parcial
```

Com `silver_iqs_vrc`/`gold_vrc` e `silver_iqs_metas_uc`/`gold_metas_uc`, a tabela tambem calcula `KEI`, `COMP_DIC`, `COMP_FIC`, `COMP_DMIC`, `COMP_DICRI`, `COMP_DISE` e `COMP_GERAL`.

Para executar o fluxo completo, incluindo nova extracao, tratamento, consumidores, UCs faturadas, apuracao previa e exportacoes auxiliares:

```bat
set REEXTRAIR=1
set REPROCESSAR=1
run.bat full_mais_apuracao
```

Para reprocessar somente tratamento e apuracao usando o RAW ja extraido:

```bat
set REEXTRAIR=
set REPROCESSAR=1
run.bat tratamento
run.bat apuracao_parcial
```

### Regras de tratamento ativas

A avaliacao de sobreposicao total por equipamento foi removida do fluxo principal. O processo nao marca mais interrupcoes como `ESTADO_INTRP = 7` por criterio de equipamento e nao gera `91/R` por essa regra.

As regras ativas sao:

1. Sobreposicao total por UC:
   - aplicada diretamente sobre os registros validos de UC;
   - compara somente registros do mesmo `COD_TIPO_INTRP`;
   - nao restringe artificialmente a lista de tipos;
   - mantem a interrupcao em `ESTADO_INTRP = 4`;
   - marca a UC contida com `NUM_MOTIVO_TRAT_DIF_UCI = 91` e `INDIC_SIT_PROCES_INDIC_UCI = D`.

2. Sobreposicao parcial por UC:
   - compara somente registros da mesma UC, mesmo protocolo e mesmo `COD_TIPO_INTRP`;
   - ajusta `DTHR_INICIO_INTRP_UC` para o fim da interrupcao pai/anterior;
   - preenche `NUM_INTRP_INIC_MANOBRA_UCI` com o `NUM_INTRP_UCI` da interrupcao pai/anterior.

Codigos principais:

| Campo | Codigo | Uso |
| --- | --- | --- |
| `COD_TIPO_INTRP` | `1` | Acidental |
| `COD_TIPO_INTRP` | `2` | Programado |
| `COD_TIPO_INTRP` | `3` | Voluntario |
| `TIPO_PROTOC_JUSTIF_UCI` | `0` | Base liquida para `DIC`, `FIC` e `DMIC` |
| `TIPO_PROTOC_JUSTIF_UCI` | `1` | Dia Critico, base para `DICRI` |
| `TIPO_PROTOC_JUSTIF_UCI` | `5`/`6` | ISE, base para `DISE` |

### Auditoria de interrupcao sem UC

Na apuracao previa, o processo materializa a tabela:

```text
gold_interrupcao_sem_uc
```

Essa camada identifica interrupcoes que permaneceram em `ESTADO_INTRP = 4`, mas ficaram sem nenhuma UC apuravel porque todas as UCs foram classificadas como `91/D` pela sobreposicao total por UC.

Arquivos gerados em `data/marts`:

```text
Auditoria_Interrupcao_Sem_UC_<ANOMES>_<timestamp>.CSV
Auditoria_Interrupcao_Sem_UC_<ANOMES>_<timestamp>_RESUMO.TXT
```

### Exportacoes separadas de sobreposicao

Para popular as pastas de exportacao separadas por tipo de tratamento:

```bat
run.bat exportacao_sobreposicao
```

Esse comando gera arquivos nas pastas:

```text
data/export/sobreposicao_total_uc
data/export/sobreposicao_UC_parcial
```

Uso recomendado depois do tratamento:

```bat
set REPROCESSAR=1
run.bat tratamento
run.bat exportacoes_auxiliares
```

Observacao: a regra de equipamento foi removida do tratamento principal. Portanto, a pasta `sobreposicao_total_uc` representa somente a sobreposicao total por UC. A pasta `sobreposicao_UC_parcial` representa somente a sobreposicao parcial por UC.

### Exportacao de interrupcao sem UC

Apos a analise de sobreposicao total por UC, pode existir interrupcao em `ESTADO_INTRP = 4` em que todas as UCs ficaram marcadas como `91/D`. Para auditar e exportar essas interrupcoes como descarte integral em arquivo separado:

```bat
run.bat interrupcao_sem_uc
```

O comando:

- popula a tabela `Auditoria_ESTADO_7` no DuckDB processado;
- gera auditoria em `data/marts`;
- cria arquivos no layout de entrada do IQS em:

```text
data/export/interrupcao_sem_uc
```

Ordem de gravacao dos arquivos auxiliares:

1. `data/export/sobreposicao_total_uc`
2. `data/export/sobreposicao_UC_parcial`
3. `data/export/interrupcao_sem_uc`

O processo aplica intervalo de 1 segundo entre as etapas para manter os nomes dos arquivos em sequencia temporal.

Regra de exportacao:

- `ESTADO_INTRP = 7`;
- `NUM_MOTIVO_TRAT_DIF_UCI = 91`;
- `INDIC_SIT_PROCES_INDIC_UCI = R`;
- interrupcoes com `NUM_INTRP_INIC_MANOBRA_UCI` preenchido ficam somente na auditoria e nao sao exportadas automaticamente;
- interrupcoes sem UC que sejam origem em `NUM_INTRP_INIC_MANOBRA_UCI` de outra interrupcao valida tambem ficam somente na auditoria.

Detalhamento tecnico: `docs/07_interrupcao_sem_UC.md`.

Para gerar todas as exportacoes auxiliares na ordem correta:

```bat
run.bat exportacoes_auxiliares
```

Esse comando grava, com intervalo de 1 segundo entre as etapas:

1. `data/export/sobreposicao_total_uc`
2. `data/export/sobreposicao_UC_parcial`
3. `data/export/interrupcao_sem_uc`
"# MIDWAY" 
