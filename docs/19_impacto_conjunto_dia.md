# 19 - Impacto Diário por Conjunto Elétrico

## Objetivo

Criar uma visão diária para identificar quais ocorrências mais consomem a meta `DEC/FEC` de cada conjunto elétrico.

A análise apoia a pergunta executiva:

```text
Quais ocorrências de hoje mais afetam a meta do conjunto?
```

## Camada Criada

A apuração parcial gera a tabela:

```text
gold_impacto_conjunto_dia
```

Granularidade:

```text
DATA_OCORRENCIA + COD_CONJUNTO_ANEEL + NUM_OCORRENCIA_ADMS
```

Ou seja, cada linha representa o impacto de uma ocorrência em um conjunto elétrico em um dia.

## Fontes

| Fonte | Uso |
| --- | --- |
| `gold_apuracao_uc` | Base liquidada de DIC/FIC por UC e interrupção |
| `gold_metas_uc` | Código do conjunto e metas `DEC/FEC` |

O código do conjunto vem prioritariamente de:

```text
COD_CONJTO_ELET_ANEEL_INTRP
```

Quando necessário, usa o conjunto associado à UC em `gold_metas_uc`.

## Indicadores

| Coluna | Descrição |
| --- | --- |
| `DIC_IMPACTO` | Soma de `CHI_LIQUIDO` da ocorrência no conjunto |
| `FIC_IMPACTO` | Soma de `CI_LIQUIDO` da ocorrência no conjunto |
| `TOTAL_UCS_CONJUNTO` | Quantidade de UCs do conjunto |
| `DEC_IMPACTO_CONJUNTO` | `DIC_IMPACTO / TOTAL_UCS_CONJUNTO` |
| `FEC_IMPACTO_CONJUNTO` | `FIC_IMPACTO / TOTAL_UCS_CONJUNTO` |
| `META_DEC_CONJUNTO` | Meta DEC do conjunto |
| `META_FEC_CONJUNTO` | Meta FEC do conjunto |
| `PCT_META_DEC_CONSUMIDA` | Percentual da meta DEC consumido pela ocorrência |
| `PCT_META_FEC_CONSUMIDA` | Percentual da meta FEC consumido pela ocorrência |
| `PCT_META_MAX_CONSUMIDA` | Maior percentual entre DEC e FEC |

## Fórmulas

```text
DEC_IMPACTO_CONJUNTO = DIC_IMPACTO / TOTAL_UCS_CONJUNTO
FEC_IMPACTO_CONJUNTO = FIC_IMPACTO / TOTAL_UCS_CONJUNTO
```

```text
PCT_META_DEC_CONSUMIDA = DEC_IMPACTO_CONJUNTO / META_DEC_CONJUNTO * 100
PCT_META_FEC_CONSUMIDA = FEC_IMPACTO_CONJUNTO / META_FEC_CONJUNTO * 100
```

```text
PCT_META_MAX_CONSUMIDA = maior valor entre PCT_META_DEC_CONSUMIDA e PCT_META_FEC_CONSUMIDA
```

## Leitura Executiva

| Pergunta | Resposta |
| --- | --- |
| O que a tabela mostra? | Quanto cada ocorrência consome da meta do conjunto |
| Qual campo prioriza a análise? | `PCT_META_MAX_CONSUMIDA` |
| O cálculo muda DEC/FEC oficial? | Não |
| O cálculo muda DIC/FIC? | Não |
| Para que serve? | Priorização diária da operação e pós-operação |

## Exemplo

Uma ocorrência com:

```text
DIC_IMPACTO = 500 horas
TOTAL_UCS_CONJUNTO = 10.000 UCs
META_DEC_CONJUNTO = 10 horas
```

Gera:

```text
DEC_IMPACTO_CONJUNTO = 500 / 10.000 = 0,05
PCT_META_DEC_CONSUMIDA = 0,05 / 10 * 100 = 0,5%
```

Interpretação:

```text
Essa ocorrência consumiu 0,5% da meta DEC do conjunto.
```

## Painel Streamlit

A aba **Conjunto Diário** mostra:

- filtro por dia;
- filtro por conjunto;
- filtro por percentual mínimo de meta consumida;
- ranking de ocorrências;
- resumo por conjunto no dia;
- download do ranking.

Comando:

```bat
run.bat painel
```

## Fluxo de Atualização

Depois de atualizar tratamento ou metas:

```bat
set REPROCESSAR=1
run.bat reprocessar
run.bat apuracao_parcial
run.bat validar_dados
```

## Arquivos Gerados

A apuração exporta uma conferência em:

```text
data/marts/Gold_Impacto_Conjunto_Dia_<ANOMES>_<timestamp>.CSV
data/marts/Gold_Impacto_Conjunto_Dia_<ANOMES>_<timestamp>_RESUMO.TXT
```

## Observações

- A visão é analítica e diária.
- Ela usa a base liquidada `CI_LIQUIDO` e `CHI_LIQUIDO`.
- O objetivo é priorizar ocorrências que pressionam a meta do conjunto.
- A análise não substitui a apuração oficial regulatória.
