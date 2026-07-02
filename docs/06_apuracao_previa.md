# 06 - Apuracao previa

## Objetivo

Criar uma camada `gold` com a versao tratada e valida das interrupcoes para permitir calculos previos de:

- `CI`;
- `CHI`;
- `DEC`;
- `FEC`.

Tambem gera o arquivo:

`data/export/BDO_interupcao_<yyyymmdd>.csv`

## Dicionario de codigos de apuracao

### `COD_TIPO_INTRP`

Classifica a natureza da interrupcao:

| Codigo | Significado |
| --- | --- |
| `1` | Acidental |
| `2` | Programado |
| `3` | Voluntario |

A regra de sobreposicao temporal por UC deve comparar apenas eventos da mesma UC e do mesmo `COD_TIPO_INTRP`, sem restringir artificialmente a lista de tipos.

### `TIPO_PROTOC_JUSTIF_UCI`

Classifica o tipo de protocolo/indicador aplicavel no nivel da UC:

| Codigo | Uso na apuracao |
| --- | --- |
| `0` | Base liquida para calculo de `DIC`, `FIC` e `DMIC` |
| `1` | Dia Critico, base para calculo de `DICRI` |
| `5` | ISE, base para calculo de `DISE` |
| `6` | ISE, base para calculo de `DISE` |

Esses codigos nao substituem `NUM_MOTIVO_TRAT_DIF_UCI`. Para entrar em qualquer base apuravel, a regra principal continua sendo `NUM_MOTIVO_TRAT_DIF_UCI` nulo.

## Entrada

A apuracao usa o DuckDB processado:

`data/processed/iqs_adms_processed_<ANOMES>.duckdb`

Tabelas esperadas:

- `raw_db.hiadms_raw`, no DuckDB bruto `data/raw/iqs_adms_raw_<ANOMES>.duckdb`;
- `adms_iqs_alterados`, no DuckDB processado.
- `gold_uc_fatura`, no DuckDB processado.

A apuracao nao usa apenas o arquivo de correcao IQS. Ela parte do RAW completo do mes e aplica os ajustes calculados pelo tratamento.

## UCs consideradas na apuracao

Antes da apuracao, deve ser criada a tabela:

`gold_uc_fatura`

Ela vem do SQL:

`IQS_uc_fatura.sql`

Execucao:

```bat
run.bat uc_fatura
```

Regra de origem:

```sql
TO_CHAR(DATA_INTRP_HCAI, 'yyyymm') = :anomes
AND INDIC_UC_ACESS_HCAI = 'N'
```

A tabela possui:

| Campo | Descricao |
| --- | --- |
| `UC` | unidade consumidora considerada na apuracao |
| `FATURADO` | indicador `INDIC_FAT_HCAI` |
| `REGIONAL` | regional da UC |

A `gold_apuracao_uc` considera somente registros cuja `NUM_UC_UCI` exista em `gold_uc_fatura` com:

```sql
FATURADO = 'S'
```

Ou seja, CI/CHI bruto e liquido consideram somente UC faturada.

## Tabela gold

Tabela criada:

`gold_interrupcao_tratada`

Regra:

```sql
ESTADO_INTRP = '4'
```

Essa tabela e a camada gold completa da interrupcao tratada. Ela nasce de `hiadms_raw`, preservando todos os registros validos do mes, e sobrepoe apenas os campos alterados em `adms_iqs_alterados`.

Campos sobrepostos pelo tratamento:

- `ESTADO_INTRP`;
- `NUM_MOTIVO_TRAT_DIF_UCI`;
- `INDIC_SIT_PROCES_INDIC_UCI`;
- `DTHR_INICIO_INTRP_UC`, quando houver ajuste parcial;
- `NUM_INTRP_INIC_MANOBRA_UCI`, quando houver ajuste parcial ou redirecionamento por `ESTADO_INTRP = 7`.

Registros que viram `ESTADO_INTRP = 7` nao entram na gold de apuracao.

Na criacao da gold, a coluna `NUM_INTRP_INIC_MANOBRA_UCI` e normalizada:

- nulo, vazio, `0` ou `0.0` viram `NULL`;
- valor igual a propria interrupcao (`NUM_INTRP_UCI` ou `NUM_SEQ_INTRP`) vira `NULL`;
- somente valor diferente da propria interrupcao permanece preenchido.

Motivo: quando o campo vem preenchido com a propria interrupcao, isso nao representa manobra anterior real e nao deve bloquear a contagem de CI/CHI.

## Tabela de UC apuravel

Tabela criada:

`gold_apuracao_uc`

Parte da `gold_interrupcao_tratada`, mas considera somente UCs sem motivo de tratamento diferenciado:

```sql
NUM_MOTIVO_TRAT_DIF_UCI IS NULL
```

Motivo: qualquer UC com `NUM_MOTIVO_TRAT_DIF_UCI` preenchido possui tratamento diferenciado e nao entra na apuracao previa de DEC/FEC liquido nem no calculo de DIC/FIC. A coluna `INDIC_SIT_PROCES_INDIC_UCI` permanece como atributo de auditoria do tratamento.

Tambem remove UCs vinculadas a uma interrupcao inicial de manobra:

```sql
NUM_INTRP_INIC_MANOBRA_UCI IS NOT NULL
```

Motivo: quando esse campo esta preenchido, a UC ja foi contada na interrupcao inicial de manobra e nao deve entrar novamente em CI/CHI.

### Interrupcao longa

A tabela `gold_apuracao_uc` tambem classifica se a UC deve entrar na apuracao por tempo minimo:

| Campo | Regra |
| --- | --- |
| `DURACAO_HORA` | duracao em horas entre `DTHR_INICIO_INTRP_UC` e `DATA_HORA_FIM_INTRP` |
| `INTERRUPCAO_LONGA` | `SIM` quando a duracao e maior ou igual a 3 minutos |
| `INTERRUPCAO_CONTABILIZAVEL` | `SIM`; a tabela ja filtra apenas registros com `NUM_INTRP_INIC_MANOBRA_UCI` nulo/vazio |

Regra de manobra:

- se `NUM_INTRP_INIC_MANOBRA_UCI` esta nulo apos normalizar vazio/espaco para `NULL`, a UC pode ser contada;
- se `NUM_INTRP_INIC_MANOBRA_UCI` esta preenchido, a interrupcao ja foi contada na interrupcao inicial de manobra e nao entra novamente em CI/CHI.

## Calculos

Na tabela `gold_apuracao_uc`:

| Campo | Regra |
| --- | --- |
| `CI_BRUTO` | `1` quando `INTERRUPCAO_LONGA = 'SIM'` e `INTERRUPCAO_CONTABILIZAVEL = 'SIM'` |
| `CHI_BRUTO` | `DURACAO_HORA` quando `INTERRUPCAO_LONGA = 'SIM'` e `INTERRUPCAO_CONTABILIZAVEL = 'SIM'` |
| `CI_LIQUIDO` | `CI_BRUTO` somente quando `TIPO_PROTOC_JUSTIF_UCI = '0'` |
| `CHI_LIQUIDO` | `CHI_BRUTO` somente quando `TIPO_PROTOC_JUSTIF_UCI = '0'` |

Na tabela `gold_apuracao_previa`, os dados sao agregados por:

- `REGIONAL`;
- `NUM_OCORRENCIA_ADMS`;
- `NUM_SEQ_INTRP`;
- `NUM_INTRP_UCI`;
- `NUM_POSTO_UCI`;
- `COD_CAUSA_INTRP`;
- `COD_COMP_INTRP`;
- `COD_TIPO_INTRP`.

A tabela previa exportada para BDO considera somente UCs que entram na apuracao:

```sql
INTERRUPCAO_LONGA = 'SIM'
AND INTERRUPCAO_CONTABILIZAVEL = 'SIM'
```

Ou seja, a duracao minima para somar `CI` e `CHI` e de 3 minutos.

| Campo | Regra |
| --- | --- |
| `CI_BRUTO` | `COUNT(DISTINCT NUM_UC_UCI)` das UCs longas e contabilizaveis |
| `CHI_BRUTO` | `SUM(DURACAO_HORA)` das UCs longas e contabilizaveis |
| `CI_LIQUIDO` | `COUNT(DISTINCT NUM_UC_UCI)` do bruto com `TIPO_PROTOC_JUSTIF_UCI = '0'` |
| `CHI_LIQUIDO` | `SUM(DURACAO_HORA)` do bruto com `TIPO_PROTOC_JUSTIF_UCI = '0'` |
| `DEC_BRUTO` | `CHI_BRUTO / TOTAL_CONSUMIDORES` |
| `FEC_BRUTO` | `CI_BRUTO / TOTAL_CONSUMIDORES` |
| `DEC_LIQUIDO` | `CHI_LIQUIDO / TOTAL_CONSUMIDORES` |
| `FEC_LIQUIDO` | `CI_LIQUIDO / TOTAL_CONSUMIDORES` |

As datas exportadas na BDO sao derivadas da agregacao:

| Campo | Regra |
| --- | --- |
| `DATA_HORA_INIC_INTRP` | menor inicio do grupo |
| `DATA_HORA_FIM_INTRP` | maior fim do grupo |

## Denominador DEC/FEC

O denominador oficial deve vir da extracao de consumidores do IQS.

SQL:

`IQS_consumidor.sql`

Execucao:

```bat
run.bat consumidores
```

Essa rotina materializa no DuckDB processado:

`gold_consumidores`

Campos principais:

| Campo | Descricao |
| --- | --- |
| `REGIONAL_TOTAL` | regional consolidada, incluindo `COPEL` no rollup |
| `SIGLA_REGIONAL` | sigla usada no IQS (`P`, `L`, `M`, `C`, `V`) |
| `SIGLA_SEVIDOR` | servidor regional |
| `ANOMES` | mes de referencia |
| `UC_FATURADA` | quantidade de consumidores faturados |

A apuracao usa o total `COPEL` como denominador unico da empresa para calcular:

```text
DEC_PREVIA = CHI / UC_FATURADA
FEC_PREVIA = CI / UC_FATURADA
```

Ou seja, a linha usada de `gold_consumidores` e sempre:

```sql
REGIONAL_TOTAL = 'COPEL'
```

Mesmo que a apuracao esteja agrupada por regional, `DEC_PREVIA` e `FEC_PREVIA` usam o total de consumidores da empresa.

### Fallback manual

Se `gold_consumidores` nao existir, ainda e possivel informar no `.env`:

```env
TOTAL_CONSUMIDORES=1234567
```

Nesse caso, o mesmo total e usado para todas as regionais.

Se nem `gold_consumidores` nem `TOTAL_CONSUMIDORES` existirem, o processo calcula CI/CHI bruto e liquido, mas deixa DEC/FEC nulos.

## Arquivo BDO

Arquivo gerado:

`data/export/BDO_interupcao_<yyyymmdd>.csv`

Formato:

- separador `|`;
- terminador de linha UNIX `LF`;
- datas em `DD/MM/YYYY HH24:MI:SS`.

Colunas:

- `REGIONAL`;
- `NUM_OCORRENCIA_ADMS`;
- `NUM_SEQ_INTRP`;
- `NUM_INTRP_UCI`;
- `NUM_POSTO_UCI`;
- `COD_CAUSA_INTRP`;
- `COD_COMP_INTRP`;
- `COD_TIPO_INTRP`;
- `DATA_HORA_INIC_INTRP`;
- `DATA_HORA_FIM_INTRP`;
- `CI_BRUTO`;
- `CHI_BRUTO`;
- `CI_LIQUIDO`;
- `CHI_LIQUIDO`;
- `TOTAL_CONSUMIDORES`;
- `DEC_BRUTO`;
- `FEC_BRUTO`;
- `DEC_LIQUIDO`;
- `FEC_LIQUIDO`.

## Execucao

Pelo CMD:

```bat
run.bat apuracao_parcial
```

Ou diretamente:

```bat
python -m midway.apuracao.previa
```

## Saidas auxiliares

Resumo:

`data/marts/Apuracao_Previa_<timestamp>_RESUMO.TXT`

Tabelas materializadas no DuckDB processado:

- `gold_interrupcao_tratada`;
- `gold_apuracao_uc`;
- `gold_apuracao_previa`.

## Ordem recomendada

```bat
run.bat reprocessar
run.bat consumidores
run.bat uc_fatura
run.bat apuracao_parcial
```
## Auditoria de interrupcao sem UC

## SQLs de apoio

As consultas Oracle usadas na apuracao ficam centralizadas na pasta `SQL/`:

```text
SQL/IQS_consumidor.sql
SQL/IQS_uc_fatura.sql
SQL/IQS_vrc.sql
SQL/IQS_METAS UC 2026.sql
```

As extracoes auxiliares do IQS sao gravadas primeiro em:

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

No inicio da apuracao, essas tabelas sao sincronizadas para o DuckDB processado como `silver_iqs_consumidores`, `silver_iqs_uc_fatura`, `silver_iqs_vrc` e `silver_iqs_metas_uc`. As tabelas `gold_consumidores`, `gold_uc_fatura`, `gold_vrc` e `gold_metas_uc` continuam sendo criadas por compatibilidade.

`SQL/IQS_consumidor.sql` alimenta a tabela raw `raw_iqs_consumidores`, a tabela `silver_iqs_consumidores` e a tabela de compatibilidade `gold_consumidores`.

`SQL/IQS_uc_fatura.sql` alimenta a tabela raw `raw_iqs_uc_fatura`, a tabela `silver_iqs_uc_fatura` e a tabela de compatibilidade `gold_uc_fatura`, usada para restringir a apuracao as UCs faturadas.

`SQL/IQS_vrc.sql` alimenta a tabela raw `raw_iqs_vrc`, a tabela `silver_iqs_vrc` e a tabela de compatibilidade `gold_vrc`. Essa extracao e sob demanda, por volume elevado, e deve ser executada somente quando necessaria:

```bat
run.bat vrc
```

Para forcar nova extracao:

```bat
run.bat reextrair_vrc
```

`SQL/IQS_METAS UC 2026.sql` alimenta a tabela raw `raw_iqs_metas_uc`, a tabela `silver_iqs_metas_uc` e a tabela de compatibilidade `gold_metas_uc`. Essa extracao tambem e sob demanda:

```bat
run.bat metas_uc
```

Para forcar nova extracao:

```bat
run.bat reextrair_metas_uc
```

Antes de montar a base de apuracao por UC, o processo materializa a tabela `gold_interrupcao_sem_uc`.

## Gold continuidade por UC

A apuracao parcial tambem materializa a tabela:

```text
gold_continuidade_uc
```

Essa tabela consolida os indicadores individuais por UC, usando a base canonica `silver_interrupcao_uc_apuravel` publicada tambem como `gold_apuracao_uc`, as UCs faturadas de `silver_iqs_uc_fatura`/`gold_uc_fatura` e as metas de `silver_iqs_metas_uc`/`gold_metas_uc`.

Campos principais:

| Campo | Regra |
| --- | --- |
| `UC` | unidade consumidora |
| `DIC` | soma da duracao em horas usando os mesmos filtros de `DEC_LIQUIDO` |
| `FIC` | quantidade de interrupcoes usando os mesmos filtros de `FEC_LIQUIDO` |
| `DMIC` | maior duracao individual usando os mesmos filtros de `DEC_LIQUIDO` / `FEC_LIQUIDO` |
| `DIC_DICRI` | soma da duracao em horas para `TIPO_PROTOC_JUSTIF_UCI = 1` |
| `FIC_DICRI` | quantidade de interrupcoes para `TIPO_PROTOC_JUSTIF_UCI = 1` |
| `DIC_ISE` | soma da duracao em horas para `TIPO_PROTOC_JUSTIF_UCI IN (5, 6)` |
| `FIC_ISE` | quantidade de interrupcoes para `TIPO_PROTOC_JUSTIF_UCI IN (5, 6)` |
| `FATURADA` | indica se a UC consta como faturada em `gold_uc_fatura` |
| `META_DIC`, `META_FIC`, `META_DMIC`, `META_DICRI`, `META_DISE` | metas vindas de `gold_metas_uc` |
| `GRUPO_TENSAO` | descricao do grupo/nivel de tensao |
| `VRC` | valor base de compensacao vindo de `gold_vrc` |
| `KEI` | fator por grupo/nivel de tensao |
| `DIC_BASE_COMPENSACAO`, `FIC_BASE_COMPENSACAO`, `DMIC_BASE_COMPENSACAO` | indicadores usados no calculo de compensacao, excluindo eventos nao compensaveis |
| `DICRI_BASE_COMPENSACAO`, `DISE_BASE_COMPENSACAO` | bases compensaveis para DICRI e DISE |
| `CHAVE_PARTICULAR` | `S` quando houve evento com `INDIC_PROPR_CHVP_INTRP = P`, `UC_ACESSANTE = S` e UC unica na chave do evento |
| `UC_ACESSANTE_COMPENSACAO` | `S` quando houve evento com `UC_ACESSANTE = S`, excluido da compensacao |
| `COMP52` | `S` quando houve evento com `COD_COMP_INTRP = '52'`, tratado como texto/string e excluido da compensacao |
| `COMP52_CAUSA71` | marcador complementar para evento com `COD_COMP_INTRP = '52'` e `COD_CAUSA_INTRP = '71'` |
| `POSTO_PARTICULAR` | `S` quando houve evento com `INDIC_PROPR_POSTO_INTRP = 'P'`, excluido da compensacao |
| `COMP_DIC`, `COMP_FIC`, `COMP_DMIC`, `COMP_DICRI`, `COMP_DISE` | compensacao previa por indicador |
| `COMP_GERAL` | maior valor entre `COMP_DIC`, `COMP_FIC` e `COMP_DMIC` |

Para calcular compensacao previa, executar antes:

```bat
run.bat vrc
run.bat metas_uc
```

A compensacao previa so e calculada para `FATURADA = 'S'`. Para UCs nao faturadas, os indicadores permanecem disponiveis para conferencia, mas `COMP_DIC`, `COMP_FIC`, `COMP_DMIC`, `COMP_DICRI`, `COMP_DISE` e `COMP_GERAL` ficam `0`.

Os percentuais `%_ULTRAPASSOU_META_*` indicam quanto o indicador excedeu a respectiva meta:

```text
((valor_apurado / meta) - 1) * 100
```

Quando a meta e nula, zero ou o indicador nao ultrapassa a meta, o percentual fica `0`.

Para `DIC`, `FIC` e `DMIC`, a base e a mesma dos indicadores liquidos `DEC_LIQUIDO` e `FEC_LIQUIDO`:

| Filtro | Regra |
| --- | --- |
| Duracao | interrupcao longa, maior ou igual a 3 minutos |
| Contabilizacao | `INTERRUPCAO_CONTABILIZAVEL = SIM` |
| Protocolo | `TIPO_PROTOC_JUSTIF_UCI = '0'` |
| UC | somente UCs validas/faturadas da apuracao |

Arquivo de conferencia:

```text
data/marts/Gold_Continuidade_UC_<ANOMES>_<timestamp>.CSV
data/marts/Gold_Continuidade_UC_<ANOMES>_<timestamp>_RESUMO.TXT
```

O resumo principal da apuracao previa tambem deve apresentar os totais:

```text
COMP_DIC total
COMP_FIC total
COMP_DMIC total
COMP_DICRI total
COMP_DISE total
COMP_GERAL total
```

Nao ha corte operacional de 24 horas na apuracao previa. Valores extremos devem ser acompanhados por auditorias proprias, sem alterar os totais de DEC/FEC, DIC/FIC ou compensacao.

Essa tabela identifica interrupcoes que permaneceram com `ESTADO_INTRP = 4`, mas ficaram sem nenhuma UC apuravel porque todas as UCs da interrupcao foram classificadas como sobreposicao total por UC:

| Campo | Criterio |
| --- | --- |
| `NUM_MOTIVO_TRAT_DIF_UCI` | `91` |
| `INDIC_SIT_PROCES_INDIC_UCI` | `D` |
| `QTD_UCS_DESCARTADAS_91_D` | igual a `QTD_UCS_TOTAL` |
| `QTD_UCS_APURAVEIS` | `0` |

O objetivo e auditar interrupcoes que ficaram sem contribuicao para CI/CHI por descarte total das UCs, mesmo a interrupcao permanecendo ativa.

Arquivos gerados em `data/marts`:

- `Auditoria_Interrupcao_Sem_UC_<ANOMES>_<timestamp>.CSV`
- `Auditoria_Interrupcao_Sem_UC_<ANOMES>_<timestamp>_RESUMO.TXT`
