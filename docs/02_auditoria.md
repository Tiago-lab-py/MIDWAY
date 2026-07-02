# Auditorias de sobreposicao

## Objetivo

As auditorias conferem se as classificacoes de sobreposicao respeitam a ordem de negocio:

1. descartar interrupcao inteira duplicada por equipamento com `ESTADO_INTRP = 7`;
2. descartar parcialmente UC totalmente contida com `NUM_MOTIVO_TRAT_DIF_UCI = 91` e `INDIC_SIT_PROCES_INDIC_UCI = D`;
3. ajustar tempo de UC em sobreposicao parcial.

## Auditoria preventiva de outliers do bruto

Antes do tratamento principal, o processo avalia o dado bruto para identificar interrupcoes fora do padrao que podem remover muitos dados por sobreposicao.

Essa auditoria e nao bloqueante: ela gera arquivos de conferencia, mas nao impede o tratamento.

Arquivos gerados em `data/marts`:

```text
data/marts/Auditoria_Outliers_Bruto_IQS_<YYYYMMDDHHMMSS>.CSV
data/marts/Auditoria_Outliers_Bruto_IQS_<YYYYMMDDHHMMSS>_RESUMO.TXT
```

O CSV lista apenas as colunas:

```text
NUM_OCORRENCIA_ADMS
NUM_SEQ_INTRP
DATA_HORA_INIC_INTRP
DATA_HORA_FIM_INTRP
COD_CAUSA_INTRP
COD_COMP_INTRP
COD_TIPO_INTRP
TIPO_PROTOC_JUSTIF_UCI
NUM_PROTOC_JUSTIF_RESP_UCI
```

Observacao: as analises de protocolo da auditoria usam os campos da UC (`*_UCI`), nao os campos da interrupcao (`*_INTRP`), para manter consistencia com as regras de apuracao por UC.

### Criterios de outlier

Uma interrupcao entra na auditoria quando atingir pelo menos um dos limiares:

| Variavel | Padrao | Descricao |
| --- | --- | --- |
| `OUTLIER_DURACAO_HORAS` | `24` | Duracao da interrupcao em horas |
| `OUTLIER_QTD_UCS` | `10000` | Quantidade de UCs na interrupcao |
| `OUTLIER_QTD_INTRP_CONTIDAS` | `100` | Quantidade de interrupcoes contidas no mesmo equipamento |
| `OUTLIER_QTD_UCS_AFETADAS` | `50000` | Quantidade de UCs potencialmente afetadas por sobreposicao |

O calculo e feito no nivel de interrupcao agregada, nao no nivel de UC, para evitar multiplicacao de linhas.

## Auditoria do ESTADO_INTRP 7

A auditoria confere se cada registro classificado com `ESTADO_INTRP = 7` possui outro registro que justifica sua classificacao por equipamento.

O `ESTADO_INTRP = 7` deve marcar apenas o registro contido/duplicado. O registro maior, que cobre o intervalo do duplicado, deve permanecer como registro mantido.

A auditoria trabalha no nivel de interrupcao/equipamento, e nao no nivel de UC. Isso evita multiplicacao de linhas em bases grandes, porque a tabela bruta possui uma linha por UC.

## Regra auditada

Um registro ja classificado como `ESTADO_INTRP = 7` e auditado procurando outro registro quando:

- possui `ESTADO_INTRP_ORIG = 4`;
- possui `TIPO_EQP_INTRP = C`;
- possui `NUM_OPER_CHV_INTRP` preenchido;
- existe outro registro de interrupcao com o mesmo `NUM_OPER_CHV_INTRP`;
- o outro registro inicia antes ou junto;
- o outro registro termina depois ou junto;
- o outro registro tem intervalo maior ou, em empate, menor `NUM_SEQ_INTRP`.

## Saida gerada

O `midway.transform.tratamento` gera a tabela:

```text
auditoria_estado_7
```

No DuckDB processado:

```text
data/processed/iqs_adms_processed_<ANOMES>.duckdb
```

Tambem gera o CSV em `data/marts`:

```text
data/marts/Auditoria_ESTADO_7_IQS_<YYYYMMDDHHMMSS>.CSV
```

Tambem sao gerados:

```text
data/marts/Auditoria_ESTADO_7_IQS_<YYYYMMDDHHMMSS>_ANOMALIAS.CSV
data/marts/Auditoria_ESTADO_7_IQS_<YYYYMMDDHHMMSS>_ANOMALIAS_PENDENTES.CSV
data/marts/Auditoria_ESTADO_7_IQS_<YYYYMMDDHHMMSS>_ANOMALIAS_ACEITAS.CSV
data/marts/Auditoria_ESTADO_7_IQS_<YYYYMMDDHHMMSS>_RESUMO.TXT
```

O caminho do CSV e registrado em:

```text
data/control/tratamento_<ANOMES>.done.json
```

## Campos principais

| Campo | Descricao |
| --- | --- |
| `NUM_SEQ_INTRP_REGISTRO_7` | Interrupcao marcada como `ESTADO_INTRP = 7` |
| `DATA_HORA_INIC_REGISTRO_7` | Inicio do registro marcado como 7 |
| `DATA_HORA_FIM_REGISTRO_7` | Fim do registro marcado como 7 |
| `NUM_SEQ_INTRP_REGISTRO_MANTIDO` | Interrupcao que cobre o registro 7 |
| `DATA_HORA_INIC_REGISTRO_MANTIDO` | Inicio do registro mantido |
| `DATA_HORA_FIM_REGISTRO_MANTIDO` | Fim do registro mantido |
| `REGISTRO_MANTIDO_TAMBEM_EXPORTADO_COM_ACAO` | Indica se o registro mantido tambem apareceu na tabela de alterados |
| `REGISTRO_MANTIDO_TAMBEM_ESTADO_7` | Indica se o registro mantido tambem foi marcado como 7 |
| `RESULTADO_AUDITORIA` | Resultado final da validacao do par |

## Interpretacao

Cada auditoria gera um arquivo `_RESUMO.TXT` com:

- `Status: OK` quando nao ha anomalias;
- `Status: NAO OK` quando ha anomalias;
- total auditado;
- total de anomalias;
- caminho do CSV completo;
- caminho do CSV de anomalias.

### Resultado OK

```text
OK: SOMENTE O REGISTRO CONTIDO FOI MARCADO COMO 7
```

Significa que o registro classificado como `7` possui outro registro em `ESTADO_INTRP = 4` que cobre o periodo do equipamento, e esse registro mantido nao foi marcado como `7`.

### Resultado com alerta

```text
ALERTA: REGISTRO 7 SEM INTERRUPCAO 4 MANTIDA COBRINDO O PERIODO
ALERTA: REGISTRO MANTIDO NAO ESTA COM ESTADO 4
ALERTA: REGISTRO MANTIDO TAMBEM FOI MARCADO COMO 7
```

Esses casos indicam que a classificacao `7` nao possui confirmacao segura de um registro `4` mantido cobrindo o periodo do equipamento.

Quando qualquer alerta de `ESTADO_INTRP = 7` existir, o tratamento falha antes de exportar os CSVs regionais finais e nao grava o controle `tratamento_<ANOMES>.done.json`.

Anomalias revisadas podem ser liberadas com o arquivo:

```text
data/input/estado_7_aceitas.csv
```

Layout:

```text
NUM_SEQ_INTRP_REGISTRO_7|NUM_SEQ_INTRP_REGISTRO_MANTIDO|RESULTADO_AUDITORIA|MOTIVO_ACEITE|APROVADO_POR|DATA_APROVACAO
```

Regras:

- se a anomalia estiver em `estado_7_aceitas.csv`, ela deixa de bloquear;
- se nao estiver no arquivo de aceite, permanece pendente e bloqueia;
- `estado_7_desconsideradas.csv` e documental e nao libera exportacao;
- o arquivo `_ANOMALIAS_PENDENTES.CSV` mostra somente o que ainda bloqueia;
- o arquivo `_ANOMALIAS_ACEITAS.CSV` mostra o que foi liberado por aceite.

Nesse caso, o processo gera uma previa bloqueada em `data/marts`:

```text
data/marts/PRE_EXPORT_Interrupcoes_IQS_<YYYYMMDDHHMMSS>_<REGIONAL>.CSV
data/marts/PRE_EXPORT_Interrupcoes_IQS_<YYYYMMDDHHMMSS>_RESUMO.TXT
```

Esses arquivos servem apenas para conferencia. Os arquivos oficiais do IQS continuam sendo gerados somente em `data/export`, e apenas quando a auditoria `ESTADO_INTRP = 7` estiver sem anomalias.

## Auditoria de manobra HCAI

Interrupcoes com `NUM_INTRP_INIC_MANOBRA_HCAI` preenchido representam manobras e nao devem ser classificadas automaticamente como `ESTADO_INTRP = 7` pela regra de sobreposicao por equipamento.

Quando essa referencia existir, ela e usada como referencia da interrupcao pai no campo `NUM_INTRP_INIC_MANOBRA_UCI`.

Arquivos gerados em `data/marts`:

```text
data/marts/Auditoria_Manobra_HCAI_IQS_<YYYYMMDDHHMMSS>.CSV
data/marts/Auditoria_Manobra_HCAI_IQS_<YYYYMMDDHHMMSS>_ANOMALIAS.CSV
data/marts/Auditoria_Manobra_HCAI_IQS_<YYYYMMDDHHMMSS>_RESUMO.TXT
```

### Alertas possiveis

```text
ALERTA: MANOBRA FOI MARCADA COMO ESTADO 7
ALERTA: MANOBRA SEM INTERRUPCAO PAI NO BRUTO
ALERTA: INTERRUPCAO PAI NAO COBRE PERIODO DA MANOBRA
```

Essa auditoria e de conferencia. O alerta mais critico e `MANOBRA FOI MARCADA COMO ESTADO 7`, pois indica quebra da excecao de manobra.

## Memoria e temporarios

Como o bruto possui uma linha por UC, uma auditoria feita diretamente com `JOIN` bruto contra bruto pode multiplicar linhas e consumir muito disco temporario.

A implementacao reduz esse risco criando uma base deduplicada por:

- `NUM_SEQ_INTRP`;
- `NUM_OPER_CHV_INTRP`.

O tratamento tambem configura o DuckDB para consultas grandes:

```sql
SET temp_directory = 'data/temp';
SET preserve_insertion_order = false;
SET threads = 4;
```

O diretorio `data/temp` e area temporaria de trabalho e pode crescer durante o processamento.

## Quando a auditoria roda

A auditoria roda sempre dentro do `midway.transform.tratamento`, depois da criacao da tabela `adms_iqs_alterados` e antes da gravacao do controle de sucesso.

Comando:

```bash
run.bat tratamento
```

Para refazer a auditoria e o tratamento:

```bash
run.bat reprocessar
```

## Mapeamento do layout IQS

Durante a exportacao, o processo gera:

```text
data/marts/Mapeamento_Layout_IQS_<YYYYMMDDHHMMSS>.CSV
```

Esse arquivo mostra a origem de cada coluna do layout final:

- `RAW`: valor veio do `hiadms_raw`;
- `TRATAMENTO`: valor veio das regras aplicadas;
- `CALCULADO`: valor montado pelo processo;
- `SEM_ORIGEM`: coluna sem origem encontrada.

O esperado e que quase todos os campos venham do `RAW`, exceto:

- `ESTADO_INTRP`;
- `DTHR_INICIO_INTRP_UC`;
- `NUM_INTRP_INIC_MANOBRA_UCI`;
- `NUM_MOTIVO_TRAT_DIF_UCI`;
- `INDIC_SIT_PROCES_INDIC_UCI`.

## Auditoria de join RAW/export

Antes de exportar os arquivos oficiais, o processo valida se toda linha de `adms_iqs_alterados` encontra a linha original correspondente em `hiadms_raw`.

Arquivo gerado:

```text
data/marts/Auditoria_Join_RAW_Export_<YYYYMMDDHHMMSS>.CSV
```

Se houver qualquer linha sem RAW correspondente, a exportacao oficial e bloqueada. Isso evita que o arquivo final seja gerado com varias colunas vazias por falha de join.

## Controle

O resumo da auditoria fica no `.done.json` do tratamento:

```json
{
  "auditoria_estado_7": {
    "path": "data/export/Auditoria_ESTADO_7_IQS_20260626093000.CSV",
    "rows": 100,
    "alerts_both_estado_7": 0
  }
}
```

O campo `alerts_both_estado_7` deve ser `0` para confirmar que nenhum registro mantido tambem foi marcado como `7`.

## Auditoria da UC 91/D

A auditoria confere se cada UC marcada como `91/D` possui outro registro da mesma UC que cobre totalmente seu intervalo.

Essa classificacao nao deve mudar a interrupcao para `ESTADO_INTRP = 7`. O descarte e parcial, somente da UC, e a interrupcao deve permanecer em `ESTADO_INTRP = 4`.

### Saida gerada

Tabela no DuckDB processado:

```text
auditoria_uc_91_d
```

CSV em `data/marts`:

```text
data/marts/Auditoria_UC_91_D_IQS_<YYYYMMDDHHMMSS>.CSV
data/marts/Auditoria_UC_91_D_IQS_<YYYYMMDDHHMMSS>_ANOMALIAS.CSV
data/marts/Auditoria_UC_91_D_IQS_<YYYYMMDDHHMMSS>_RESUMO.TXT
```

Resumo no controle:

```json
{
  "auditoria_uc_91_d": {
    "path": "data/marts/Auditoria_UC_91_D_IQS_20260626103000.CSV",
    "anomalies_path": "data/marts/Auditoria_UC_91_D_IQS_20260626103000_ANOMALIAS.CSV",
    "summary_path": "data/marts/Auditoria_UC_91_D_IQS_20260626103000_RESUMO.TXT",
    "rows": 100,
    "alerts": 0
  }
}
```

### Resultado esperado

```text
OK: UC CONTIDA MARCADA COMO 91/D E INTERRUPCAO PERMANECE 4
```

Esse resultado confirma que:

- a UC marcada como `91/D` tem uma UC mantida correspondente;
- a interrupcao da UC descartada permaneceu `ESTADO_INTRP = 4`;
- a UC mantida nao esta em interrupcao `ESTADO_INTRP = 7`;
- a UC mantida tambem nao foi marcada como `91/D`.

### Alertas possiveis

```text
ALERTA: UC 91/D SEM REGISTRO MANTIDO
ALERTA: UC MANTIDA ESTA EM INTERRUPCAO ESTADO 7
ALERTA: UC MANTIDA TAMBEM FOI MARCADA COMO 91/D
ALERTA: UC 91/D NAO PERMANECEU COM ESTADO_INTRP 4
```

Qualquer alerta deve ser revisado antes de considerar a exportacao final validada.
