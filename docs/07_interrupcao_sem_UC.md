# Interrupcao sem UC apos sobreposicao total por UC

## Objetivo

Identificar interrupcoes que permanecem em `ESTADO_INTRP = 4`, mas ficam sem nenhuma UC valida depois da regra de sobreposicao total por UC.

Essas interrupcoes podem precisar ser enviadas ao IQS como descarte integral, pois todas as UCs associadas foram descartadas parcialmente como `91/D`.

## Regra de negocio

Uma interrupcao entra na auditoria quando:

| Criterio | Regra |
| --- | --- |
| `ESTADO_INTRP` | `4` |
| Total de UCs da interrupcao | maior que `0` |
| `NUM_MOTIVO_TRAT_DIF_UCI` | todas as UCs com `91` |
| `INDIC_SIT_PROCES_INDIC_UCI` | todas as UCs com `D` |

Quando todos os registros de UC da interrupcao foram descartados por sobreposicao total de UC, a interrupcao fica sem UC apuravel.

## Excecao de manobra

Interrupcoes com `NUM_INTRP_INIC_MANOBRA_UCI` preenchido nao sao exportadas automaticamente como `ESTADO_INTRP = 7`.

Esses casos ficam somente na auditoria com:

```text
RESULTADO_AUDITORIA = NAO_EXPORTAR_MANOBRA_COM_REFERENCIA
```

O objetivo e evitar remover automaticamente uma interrupcao que ainda pode estar referenciada por outra interrupcao de manobra.

## Verificacao de origem de manobra

Alem da excecao acima, a rotina verifica se a interrupcao sem UC e usada como origem em `NUM_INTRP_INIC_MANOBRA_UCI` de outra interrupcao ainda valida e sem tratamento.

Uma interrupcao sem UC nao e exportada como `ESTADO_INTRP = 7` quando existe outra interrupcao com:

| Campo | Regra |
| --- | --- |
| `NUM_INTRP_INIC_MANOBRA_UCI` | igual ao `NUM_INTRP_UCI` ou `NUM_SEQ_INTRP` da interrupcao sem UC |
| `ESTADO_INTRP` | `4` |
| `NUM_MOTIVO_TRAT_DIF_UCI` | vazio/nulo |
| `INDIC_SIT_PROCES_INDIC_UCI` | vazio/nulo |

Esses casos ficam na auditoria com:

```text
RESULTADO_AUDITORIA = NAO_EXPORTAR_REFERENCIADA_COMO_MANOBRA
```

Motivo: se a interrupcao sem UC for excluida enquanto ainda e origem de manobra de outra interrupcao valida, o IQS pode perder o vinculo de continuidade da manobra.

## Saida para IQS

Quando a interrupcao fica sem UC e nao cai na excecao de manobra, a rotina gera arquivo no layout de entrada do IQS com:

| Campo | Valor exportado |
| --- | --- |
| `ESTADO_INTRP` | `7` |
| `NUM_MOTIVO_TRAT_DIF_UCI` | `91` |
| `INDIC_SIT_PROCES_INDIC_UCI` | `R` |

As demais colunas seguem o layout oficial do IQS, preservando os valores originais/materializados na tabela de exportacao.

## Tabelas materializadas

A rotina cria ou substitui no DuckDB processado:

| Tabela | Finalidade |
| --- | --- |
| `Auditoria_ESTADO_7` | lista interrupcoes sem UC e o resultado da auditoria |
| `adms_iqs_interrupcao_sem_uc_export` | linhas no layout IQS preparadas para exportacao |

## Arquivos gerados

Auditoria em `data/marts`:

```text
Auditoria_ESTADO_7_Interrupcao_Sem_UC_<ANOMES>_<timestamp>.CSV
Auditoria_ESTADO_7_Interrupcao_Sem_UC_<ANOMES>_<timestamp>_RESUMO.TXT
```

Arquivos para IQS em:

```text
data/export/interrupcao_sem_uc
```

Formato:

| Item | Valor |
| --- | --- |
| Separador | `|` |
| Terminador de linha | UNIX LF |
| Datas | `DD/MM/YYYY HH24:MI:SS` |
| Layout | colunas aceitas pelo IQS |

## Comando

Executar apos o tratamento:

```bat
run.bat interrupcao_sem_uc
```

Para gerar todas as exportacoes auxiliares na ordem sequencial recomendada:

```bat
run.bat exportacoes_auxiliares
```

Fluxo recomendado:

```bat
set REPROCESSAR=1
run.bat tratamento
run.bat exportacoes_auxiliares
```

## Relacao com a apuracao

A apuracao previa tambem materializa `gold_interrupcao_sem_uc` para controle analitico das interrupcoes sem UC apuravel.

Tambem materializa `gold_ocorrencia_sem_uc` para avaliar o nivel de ocorrencia, pois uma ocorrencia agrupa uma ou mais interrupcoes.

Quando todas as interrupcoes `ESTADO_INTRP = 4` de uma ocorrencia ficam sem UC apuravel, a auditoria sinaliza:

```text
ACAO_SUGERIDA_AUDITORIA = AVALIAR_MARCAR_INTERRUPCOES_DA_OCORRENCIA_COMO_ESTADO_7_91_R
```

Essa sinalizacao indica possibilidade de marcar as interrupcoes da ocorrencia como `ESTADO_INTRP = 7` e `91/R`, mas nao aplica essa marcacao automaticamente.

A diferenca entre as camadas e:

| Camada | Uso |
| --- | --- |
| `gold_interrupcao_sem_uc` | conferencia/apuracao previa |
| `gold_ocorrencia_sem_uc` | conferencia por ocorrencia sem UC apuravel |
| `Auditoria_ESTADO_7` | auditoria e decisao de exportacao para IQS |
| `adms_iqs_interrupcao_sem_uc_export` | arquivo final no layout IQS |
