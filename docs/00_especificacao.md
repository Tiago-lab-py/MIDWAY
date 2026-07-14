# Especificação - MIDWAY OMS/ADMS para IQS

## Objetivo

O processo identifica, trata e audita anomalias dos dados OMS/ADMS que podem afetar a apuracao regulatoria e a carga no IQS.

O foco do MIDWAY não é uma regra isolada. O foco é manter um motor governado de anomalias capaz de:

- detectar inconsistencias em ocorrencias, interrupcoes, UCs, equipamentos, alimentadores e conjuntos;
- comparar OMS/ADMS com servicos, reclamacoes, referencia IQS e apuracao;
- estimar impacto em `DEC/FEC`, `DIC/FIC`, ressarcimento e qualidade dos dados;
- apoiar decisao humana auditavel;
- gerar arquivos CSV por regional no layout esperado pelo IQS quando houver ajuste aprovado.

O fluxo e dividido em duas etapas para evitar reextracao acidental de grande volume de dados:

1. `midway.extract.adms`: extrai dados do Oracle IQS e cria o DuckDB bruto.
2. `midway.transform.tratamento`: usa o DuckDB bruto, aplica as regras de tratamento e exporta os CSVs finais.

As regras operacionais de execucao, auditoria e fechamento mensal estao consolidadas em `docs/14_fluxo_oficial_atual.md`.
O catalogo oficial dos modulos de anomalia esta em `docs/modulos/README.md`.
O norte multi-anomalias atual esta detalhado em `docs/33_reorientacao_anomalias_oms_iqs.md`.

## Estrutura de pastas

```text
data/
  amostra/
  control/
  export/
  input/
  logs/
  marts/
  processed/
  raw/
  temp/
```

### `data/amostra`

Contem o arquivo de referencia de formato:

```text
data/amostra/amostra.csv
```

Esse arquivo e usado como molde para a exportacao final.

### `data/raw`

Armazena o DuckDB bruto gerado pela extracao Oracle.

```text
data/raw/iqs_adms_raw_<ANOMES>.duckdb
```

Tabela:

```text
hiadms_raw
```

### `data/processed`

Armazena o DuckDB processado com a tabela tratada.

```text
data/processed/iqs_adms_processed_<ANOMES>.duckdb
```

Tabela:

```text
adms_iqs_alterados
```

### `data/export`

Armazena somente os arquivos finais que vao para o IQS e o resumo da exportacao.

```text
Interrupcoes_IQS_<YYYYMMDDHHMMSS>_<REGIONAL>.CSV
Exportacao_IQS_<YYYYMMDDHHMMSS>_RESUMO.TXT
```

### `data/marts`

Armazena arquivos de auditoria e conferencia do tratamento. Esses arquivos nao sao enviados para o IQS.

```text
Auditoria_Outliers_Bruto_IQS_<YYYYMMDDHHMMSS>.CSV
Auditoria_Outliers_Bruto_IQS_<YYYYMMDDHHMMSS>_RESUMO.TXT
Auditoria_Manobra_HCAI_IQS_<YYYYMMDDHHMMSS>.CSV
Auditoria_Manobra_HCAI_IQS_<YYYYMMDDHHMMSS>_ANOMALIAS.CSV
Auditoria_Manobra_HCAI_IQS_<YYYYMMDDHHMMSS>_RESUMO.TXT
Auditoria_ESTADO_7_IQS_<YYYYMMDDHHMMSS>.CSV
Auditoria_ESTADO_7_IQS_<YYYYMMDDHHMMSS>_ANOMALIAS.CSV
Auditoria_ESTADO_7_IQS_<YYYYMMDDHHMMSS>_RESUMO.TXT
Auditoria_UC_91_D_IQS_<YYYYMMDDHHMMSS>.CSV
Auditoria_UC_91_D_IQS_<YYYYMMDDHHMMSS>_ANOMALIAS.CSV
Auditoria_UC_91_D_IQS_<YYYYMMDDHHMMSS>_RESUMO.TXT
PRE_EXPORT_Interrupcoes_IQS_<YYYYMMDDHHMMSS>_<REGIONAL>.CSV
PRE_EXPORT_Interrupcoes_IQS_<YYYYMMDDHHMMSS>_RESUMO.TXT
Mapeamento_Layout_IQS_<YYYYMMDDHHMMSS>.CSV
```

Arquivos `PRE_EXPORT_...` sao gerados apenas quando existe anomalia bloqueante. Eles servem para conferencia e nao devem ser enviados ao IQS.
O arquivo `Mapeamento_Layout_IQS_...CSV` mostra, para cada coluna do layout final, se a origem veio do bruto, do tratamento, de calculo ou se ficou sem origem.

Esse arquivo deve ser conferido quando aparecerem campos vazios indevidos no CSV final.

### `data/input`

Armazena arquivos informados pelo usuario para controlar excecoes revisadas.

```text
estado_7_aceitas.csv
estado_7_desconsideradas.csv
```

O arquivo `estado_7_aceitas.csv` libera anomalias de `ESTADO_INTRP = 7` ja revisadas. Anomalias que nao estiverem nesse arquivo continuam bloqueando a exportacao oficial.

### `data/temp`

Area temporaria usada pelo DuckDB durante consultas grandes e auditorias.

O conteudo pode ser recriado pelo processo.

## Variaveis de ambiente

As variaveis sao lidas do arquivo `.env`.

| Variavel | Obrigatoria | Usada por | Descricao |
| --- | --- | --- | --- |
| `IQS_UID` | Sim | `midway.extract.adms` | Usuario Oracle IQS |
| `IQS_PWD` | Sim | `midway.extract.adms` | Senha Oracle IQS |
| `IQS_DB` | Sim | `midway.extract.adms` | DSN Oracle IQS |
| `IQS_CONFIG_DIR` | Nao | `midway.extract.adms` | Diretorio com configuracoes Oracle, como `tnsnames.ora` |
| `IQS_ORACLE_THICK_MODE` | Nao | `midway.extract.adms` | Ativa modo thick quando `1`, `true`, `yes` ou `sim` |
| `IQS_ORACLE_CLIENT_LIB_DIR` | Nao | `midway.extract.adms` | Diretorio da biblioteca 64-bit do Oracle Instant Client |
| `ANOMES` | Nao | Ambos | Competencia no formato `YYYYMM`; padrao `202605` |
| `REEXTRAIR` | Nao | `midway.extract.adms` | Quando `1`, refaz a extracao mesmo se o DuckDB bruto ja existir |
| `OUTLIER_DURACAO_HORAS` | Nao | `midway.transform.tratamento` | Limiar de duracao para auditoria preventiva do bruto; padrao `24` |
| `OUTLIER_QTD_UCS` | Nao | `midway.transform.tratamento` | Limiar de UCs por interrupcao; padrao `10000` |
| `OUTLIER_QTD_INTRP_CONTIDAS` | Nao | `midway.transform.tratamento` | Limiar de interrupcoes contidas no mesmo equipamento; padrao `100` |
| `OUTLIER_QTD_UCS_AFETADAS` | Nao | `midway.transform.tratamento` | Limiar de UCs potencialmente afetadas por sobreposicao; padrao `50000` |

## Conexao Oracle

O `midway.extract.adms` usa o modo thin do `python-oracledb` por padrao, sem exigir Oracle Instant Client.

Quando `IQS_CONFIG_DIR` estiver definido, ele sera usado como diretorio de configuracao da conexao, sem ativar automaticamente o modo thick.

Use modo thick somente quando o ambiente exigir Oracle Client:

```env
IQS_ORACLE_THICK_MODE=1
IQS_ORACLE_CLIENT_LIB_DIR=C:\oracle\instantclient_21_13
IQS_CONFIG_DIR=C:\oracle\network\admin
```

## Etapa 1 - Extracao

Comando:

```bash
python -m midway.extract.adms
```

Responsabilidades:

1. conectar no Oracle IQS;
2. consultar `IQS.HIST_INTEGRACAO_ADMS`;
3. filtrar registros da competencia `ANOMES`;
4. selecionar o ultimo registro por ocorrencia, interrupcao e UC;
5. gravar a tabela `hiadms_raw` em `data/raw`.

Filtros principais:

- `DATA_HORA_INIC_INTRP_ULT_HIADMS` dentro da competencia;
- `DATA_HORA_FIM_INTRP_ULT_HIADMS` dentro da competencia;
- `ESTADO_INTRP_ULT_HIADMS = '4'`.

A deduplicacao usa `ROW_NUMBER()` particionado por:

- `PID_OCOR_INTRP_ULT_HIADMS`;
- `NUM_SEQ_INTRP_CHVP_HIADMS`;
- `NUM_UC_UCI_CHVP_HIADMS`.

A ordenacao prioriza:

- `DTHR_INC_REGIS_HIADMS DESC NULLS LAST`;
- `NOME_ARQ_ADMS_HIADMS DESC NULLS LAST`.

Se o DuckDB bruto ja existir e `REEXTRAIR` nao estiver ativo, a extracao nao e refeita.

## Etapa 2 - Tratamento

Comando:

```bash
python -m midway.transform.tratamento
```

Responsabilidades:

1. validar a existencia de `data/raw/iqs_adms_raw_<ANOMES>.duckdb`;
2. conectar o DuckDB bruto como `raw_db`;
3. criar `data/processed/iqs_adms_processed_<ANOMES>.duckdb`;
4. gerar a tabela `adms_iqs_alterados`;
5. executar auditorias obrigatorias;
6. exportar CSVs finais por regional em `data/export`.

O `midway.transform.tratamento` nao conecta no Oracle e nao executa extracao.

## Regras de tratamento

As regras sao executadas em ordem. Cada etapa considera somente os registros que sobreviveram as etapas anteriores.

Quando identificada:

| Campo | Valor |
| --- | --- |
| `ESTADO_INTRP` | `7` |
| `NUM_MOTIVO_TRAT_DIF_UCI` | `91` |
| `INDIC_SIT_PROCES_INDIC_UCI` | `R` |
| `ACAO_SOBREPOSICAO_INTERRUPCAO` | `CLASSIFICAR_INTERRUPCAO_CONTIDA` |

### 2. Sobreposicao total por UC

Identifica registros de UC totalmente contidos em outra interrupcao da mesma UC, mesmo `COD_TIPO_INTRP` e mesmo protocolo de justificativa.

Essa regra e aplicada diretamente sobre os registros validos de interrupcao/UC, sem etapa previa de descarte por equipamento.

A mesma UC pode estar em interrupcoes e equipamentos diferentes. Quando a sobreposicao e total apenas na UC, a interrupcao permanece em `ESTADO_INTRP = 4`; o descarte e parcial, somente da UC.

A analise da sobreposicao total por UC e feita separadamente por `COD_TIPO_INTRP`, sem restringir artificialmente a lista de tipos. `COD_TIPO_INTRP = 1` representa interrupcao acidental, `2` programada e `3` voluntaria. Uma interrupcao de um tipo nao pode descartar UC de outro tipo.

Quando identificada:

| Campo | Valor |
| --- | --- |
| `ESTADO_INTRP` | permanece `4` |
| `NUM_MOTIVO_TRAT_DIF_UCI` | `91` |
| `INDIC_SIT_PROCES_INDIC_UCI` | `D` |
| `ACAO_SOBREPOSICAO_TOTAL_UC` | `CLASSIFICAR_91_UC_CONTIDA` |

### 3. Interrupcao sem UC apos sobreposicao total por UC

Identifica interrupcoes que permaneceram em `ESTADO_INTRP = 4`, mas ficaram sem nenhuma UC valida depois da analise de sobreposicao total por UC.

Regra de negocio: quando todas as UCs de uma mesma interrupcao foram classificadas como `NUM_MOTIVO_TRAT_DIF_UCI = 91` e `INDIC_SIT_PROCES_INDIC_UCI = D`, a interrupcao passa a ser uma candidata a descarte integral em arquivo separado.

Quando identificada e nao houver excecao de manobra:

| Campo | Valor |
| --- | --- |
| `ESTADO_INTRP` | `7` |
| `NUM_MOTIVO_TRAT_DIF_UCI` | `91` |
| `INDIC_SIT_PROCES_INDIC_UCI` | `R` |

Excecao: interrupcoes com `NUM_INTRP_INIC_MANOBRA_UCI` preenchido nao sao classificadas automaticamente como `ESTADO_INTRP = 7`. Nesses casos, a ocorrencia fica na auditoria com resultado `NAO_EXPORTAR_MANOBRA_COM_REFERENCIA`.

Tambem nao sao exportadas como `ESTADO_INTRP = 7` as interrupcoes sem UC que aparecem como origem em `NUM_INTRP_INIC_MANOBRA_UCI` de outra interrupcao ainda valida e sem tratamento. Esses casos ficam na auditoria com resultado `NAO_EXPORTAR_REFERENCIADA_COMO_MANOBRA`.

O processo popula a tabela `Auditoria_ESTADO_7` no DuckDB processado e gera arquivos no layout de entrada do IQS em:

```text
data/export/interrupcao_sem_uc
```

Comando:

```bat
run.bat interrupcao_sem_uc
```

Comando recomendado para gerar todas as exportacoes auxiliares em ordem sequencial:

```bat
run.bat exportacoes_auxiliares
```

Documento detalhado: `docs/modulos/interrupcao_sem_uc.md`.

### 4. Sobreposicao parcial por UC

Identifica registros em que a interrupcao da UC comeca antes do fim de uma interrupcao anterior da mesma UC, mas termina depois dela.

Essa regra e aplicada somente sobre UCs que nao foram descartadas totalmente como `91/D` e sobre interrupcoes que permaneceram validas.

A analise tambem e feita por `COD_TIPO_INTRP`, sem restringir artificialmente a lista de tipos. O ajuste parcial so pode ocorrer entre registros da mesma UC, mesmo protocolo de justificativa e mesmo `COD_TIPO_INTRP`.

Quando identificada:

| Campo | Regra |
| --- | --- |
| `DTHR_INICIO_INTRP_UC` | recebe o fim da interrupcao anterior |
| `NUM_INTRP_INIC_MANOBRA_UCI` | recebe `NUM_INTRP_UCI` da interrupcao pai anterior |
| `ACAO_AJUSTE_PARCIAL` | `AJUSTAR_SOBREPOSICAO_PARCIAL_UC` |

## Regional

O tratamento detecta automaticamente a coluna regional disponivel no DuckDB bruto.

Ordem de preferencia:

1. `INDIC_REG_ORIG_INTRP_HCAI`;
2. `SIGLA_REGIONAL_INTRP_PRIM_HIADMS`;
3. `SIGLA_REGIONAL_INTRP_ULT_HIADMS`;
4. `SIGLA_REGIONAL_HIADMS`;
5. `SIGLA_REGIONAL`.

Mapeamento para nome do arquivo:

| Valor origem | Regional |
| --- | --- |
| `P` | `CSL` |
| `L` | `NRT` |
| `M` | `NRO` |
| `C` | `LES` |
| `V` | `OES` |
| Outros | `COPEL` |

No CSV final, a coluna `SIGLA_REGIONAL` recebe a sigla original detectada.

## Exportacao CSV

Os CSVs sao gerados em `data/export`, separados por regional.

O layout final possui nomes fixos aceitos pelo IQS. Os valores sao recompostos a partir do dado bruto original (`hiadms_raw`) e apenas os campos efetivamente tratados sao sobrescritos.

Na pratica:

```text
CSV final = RAW original renomeado para o layout IQS + ajustes do tratamento
```

O mapeamento usa os nomes reais do RAW HIADMS. A diferenca entre RAW e arquivo final e basicamente a grafia/sufixo das colunas. Exemplo:

| Campo no CSV IQS | Origem no RAW |
| --- | --- |
| `PID_POSTO_PIN` | `PID_POSTO_PIN_PRIM_HIADMS` |
| `INDIC_AREA_REDE_POSTO_PIN` | `INDIC_AREA_REDE_POSTO_PIN_PRIM_HIADMS` |
| `ALIM_INTRP_PIN` | `NUM_ALIM_INTRP_PIN_PRIM_HIADMS` |
| `ALIM_INTRP` | `ALIM_INTRP_PRIM_HIADMS` |
| `CAR_SE` | `CAR_SE_INTRP_PRIM_HIADMS` |
| `INDIC_INTRP_SE_ALIM` | `INDIC_INTRP_SE_ALIM_INTRP_ULT_HIADMS` |
| `NUM_OCORRENCIA_ADMS` | `PID_OCOR_INTRP_ULT_HIADMS` |
| `VALID_POS_OPERACAO` | `INDIC_VALID_POS_OPER_INTRP_ULT_HIADMS` |
| `NUM_SEQ_INTRP` | `NUM_SEQ_INTRP_CHVP_HIADMS` |
| `NUM_UC_UCI` | `NUM_UC_UCI_CHVP_HIADMS` |
| `PID_PIN` | `PID_PIN_PRIM_HIADMS` |

Antes da exportacao oficial, o processo executa uma auditoria de join entre `adms_iqs_alterados` e `hiadms_raw`. Se alguma linha tratada nao encontrar a linha original no RAW, a exportacao e bloqueada para evitar campos vazios indevidos.

Campos sobrescritos pelo tratamento quando aplicavel:

- `ESTADO_INTRP`;
- `DTHR_INICIO_INTRP_UC`;
- `NUM_INTRP_INIC_MANOBRA_UCI`;
- `NUM_MOTIVO_TRAT_DIF_UCI`;
- `INDIC_SIT_PROCES_INDIC_UCI`.

O tratamento tambem gera arquivos de auditoria em `data/marts`:

```text
Auditoria_ESTADO_7_IQS_<YYYYMMDDHHMMSS>.CSV
Auditoria_ESTADO_7_IQS_<YYYYMMDDHHMMSS>_ANOMALIAS.CSV
Auditoria_ESTADO_7_IQS_<YYYYMMDDHHMMSS>_RESUMO.TXT
Auditoria_UC_91_D_IQS_<YYYYMMDDHHMMSS>.CSV
Auditoria_UC_91_D_IQS_<YYYYMMDDHHMMSS>_ANOMALIAS.CSV
Auditoria_UC_91_D_IQS_<YYYYMMDDHHMMSS>_RESUMO.TXT
```

As auditorias rodam antes dos CSVs regionais finais. Se a auditoria de `ESTADO_INTRP = 7` encontrar anomalias, o processo gera os arquivos de auditoria, gera uma previa bloqueada em `data/marts` e falha antes de exportar os arquivos regionais oficiais em `data/export`.

O arquivo `data/amostra/amostra.csv` e usado como referencia de formato. Quando a amostra existir, o processo replica:

- delimitador;
- codificacao;
- quebra de linha;
- formato das colunas de data/hora.

Valores ausentes sao exportados vazios. O processo nao preenche campos com espaco em branco quando eles nao fazem parte das regras de tratamento.

Quando a amostra nao existir, os padroes sao:

- delimitador `|`;
- codificacao `utf-8`;
- quebra de linha `\n`;
- datas no formato `dd/mm/yyyy hh:mm:ss`.

Layout do CSV:

```text
PID_INTRP_CONJTO_PIN|PID_POSTO_PIN|INDIC_AREA_REDE_POSTO_PIN|ALIM_INTRP_PIN|ESTADO_INTRP|ALIM_INTRP|CAR_SE|INDIC_INTRP_SE_ALIM|NUM_OCORRENCIA_ADMS|INDIC_INTRP_AT|CONS_INTRP|KVA_INTRP|NUM_OPER_CHV_INTRP|NUM_FUNCAO_ELET_HCAI|DESC_INTRP|VALID_POS_OPERACAO|DATA_HORA_INIC_INTRP|DATA_HORA_FIM_INTRP|TIPO_EQP_INTRP|COORD_X_INTRP|COORD_Y_INTRP|NUM_SEQ_INTRP|COD_CAUSA_INTRP|COD_COMP_INTRP|COD_AREA_ELET_INTRP|COD_GRUPO_COMP_INTRP|COD_COND_CLIMA_INTRP|COD_TIPO_INTRP|INDIC_JUMP_INTRP|NUM_PROTOC_JUSTIF_RESP_INTRP|TIPO_PROTOC_JUSTIF_INTRP|COD_CONJTO_ELET_ANEEL_INTRP|INDIC_CALC_DMIC_INTRP|INDIC_PONTO_CONEX_INTRP|NUM_GEO_CHV_INTRP|TIPO_REDE_CHV_INTRP|TIPO_CHV_INTRP|INDIC_PROPR_POSTO_INTRP|TENSAO_OPER_ALIM_INTRP|INDIC_DESLIG_ENT_SERV_INTRP|INDIC_PROPR_CHVP_INTRP|INDIC_CHVP_INIC_ALIM_INTRP|PID|PID_INTRP_UCI|NUM_INTRP_UCI|NUM_POSTO_UCI|NUM_UC_UCI|TIPO_SIT_UC_UCI|DTHR_INICIO_INTRP_UC|NUM_INTRP_INIC_MANOBRA_UCI|NUM_MOTIVO_TRAT_DIF_UCI|UC_ACESSANTE|SIGLA_REGIONAL|NUM_PROTOC_JUSTIF_RESP_UCI|TIPO_PROTOC_JUSTIF_UCI|PID_PIN|INDIC_PROCES_IND_PIN|INDIC_SIT_PROCES_INDIC_UCI
```

## Execucao recomendada

Primeira execucao da competencia:

```bash
python -m midway.extract.adms
python -m midway.transform.tratamento
```

Reprocessar apenas o tratamento usando o DuckDB bruto ja extraido:

```bash
python -m midway.transform.tratamento
```

Registrar um DuckDB bruto existente criado antes do controle:

```bash
run.bat registrar
```

Forcar nova extracao:

```env
REEXTRAIR=1
```
