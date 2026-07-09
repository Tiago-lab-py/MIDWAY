# 26 - Avaliar Reclamações

## Objetivo

Criar uma visão operacional para avaliar reclamações do DBGUO vinculadas às interrupções do IQS/ADMS por UC, horário e ocorrência provável.

A análise ajuda a responder três perguntas:

- a UC reclamou durante ou logo após uma interrupção?
- qual ocorrência/interrupção é a candidata mais provável para essa reclamação?
- a ocorrência já foi validada pela pós-operação e, portanto, não precisa ser reavaliada como pendência comum?

## Tabelas geradas

O comando de materialização DBGUO passa a gerar uma camada silver e três camadas gold.

### `silver_dbguo_reclamacoes`

Tabela detalhada com uma linha por reclamação e a melhor interrupção candidata, escolhida por score.

Campos principais:

| Campo | Descrição |
| --- | --- |
| `ID_RECLAMACAO` | identificador da reclamação no DBGUO |
| `UC` | unidade consumidora reclamante |
| `DTHR_RECLAMACAO` | data/hora da reclamação |
| `NUM_OCORRENCIA_ADMS` | ocorrência provável vinculada |
| `NUM_SEQ_INTRP` | interrupção provável vinculada |
| `DISTANCIA_MINUTOS` | distância entre a reclamação e a janela da interrupção |
| `POSICAO_RECLAMACAO` | antes, durante ou após a interrupção |
| `SCORE_VINCULO_RECLAMACAO` | força do vínculo reclamação/interrupção |
| `CLASSIFICACAO_VINCULO_RECLAMACAO` | classificação textual do vínculo |

### `gold_reclamacao_uc_vinculada`

Tabela principal para frontend. Enriquece a silver com dados de pós-operação, impacto e referência de ressarcimento da UC.

Campos adicionais:

| Campo | Descrição |
| --- | --- |
| `TEM_OCORRENCIA_PROVAVEL` | `S` quando há ocorrência provável vinculada |
| `VALID_POS_OPERACAO` | `S` quando a ocorrência já foi validada pela pós-operação |
| `UCS_APURAVEIS_OCORRENCIA` | UCs apuráveis na ocorrência provável |
| `FIC_OCORRENCIA` | FIC total da ocorrência provável |
| `DIC_OCORRENCIA` | DIC total da ocorrência provável |
| `COMP_TOTAL_PRODIST_UC` | compensação PRODIST da UC como referência |
| `STATUS_AVALIACAO_RECLAMACAO` | status operacional da avaliação |

### `gold_reclamacao_uc_resumo`

Resumo por UC para ranqueamento no painel.

Principais métricas:

- `QTD_RECLAMACOES`
- `QTD_COM_OCORRENCIA_PROVAVEL`
- `QTD_SEM_OCORRENCIA_PROVAVEL`
- `QTD_RECLAMACOES_OCORRENCIA_VALIDADA_POS`
- `MAX_SCORE_VINCULO_RECLAMACAO`
- `MENOR_DISTANCIA_MINUTOS`

### `gold_reclamacao_ocorrencia_resumo`

Resumo por ocorrência para cruzamento com Analytics Pós-Operação.

Principais métricas:

- `QTD_RECLAMACOES`
- `QTD_UCS_RECLAMANTES`
- `UCS_APURAVEIS_OCORRENCIA`
- `FIC_OCORRENCIA`
- `DIC_OCORRENCIA`
- `VALID_POS_OPERACAO`

## Regra de vínculo reclamação/interrupção

A reclamação é comparada com as interrupções da mesma UC dentro da janela:

```text
início da interrupção - 2 horas
até
fim da interrupção + 24 horas
```

A melhor candidata é escolhida por:

1. maior `SCORE_VINCULO_RECLAMACAO`;
2. menor `DISTANCIA_MINUTOS`;
3. interrupção mais recente em caso de empate.

## Score do vínculo

| Situação | Score |
| --- | ---: |
| reclamação durante a interrupção | 100 |
| reclamação até 60 minutos após o fim | 90 |
| reclamação entre 61 e 360 minutos após o fim | 80 |
| reclamação entre 361 e 1440 minutos após o fim | 65 |
| reclamação até 120 minutos antes do início | 50 |
| fora da janela avaliada | 0 |

Classificação:

| Score | Classificação |
| ---: | --- |
| `>= 100` | `VINCULO_FORTE_DURANTE_INTERRUPCAO` |
| `>= 80` | `VINCULO_FORTE_APOS_INTERRUPCAO` |
| `>= 60` | `VINCULO_PROVAVEL` |
| `>= 50` | `VINCULO_FRACO_ANTES_INTERRUPCAO` |
| `< 50` | `SEM_OCORRENCIA_PROVAVEL` |

## Validação Pós-Operação

Quando `VALID_POS_OPERACAO = S`, a reclamação continua visível, mas a ocorrência é tratada como já verificada.

Esse comportamento evita retrabalho: a reclamação pode ser consultada, mas deixa de ser uma pendência comum de análise.

## Frontend

A página `08 Avaliação de UC` passa a ter três abas:

```text
Outlier UC
Consulta UC
Reclamações UC
```

### Aba `Reclamações UC`

Filtros:

- UC específica, opcional;
- data inicial e final da reclamação;
- status do vínculo;
- score mínimo do vínculo.

Indicadores exibidos:

- total de reclamações;
- UCs com reclamação;
- reclamações com ocorrência provável;
- reclamações sem ocorrência provável.

Tabelas exibidas:

- ranking de UCs com reclamações;
- detalhe das reclamações com ocorrência/interrupção provável.

## Comandos

Após a extração DBGUO e a apuração IQS estarem disponíveis:

```bat
set ANOMES=202606
run.bat dbguo_reclamacoes
```

Também continua válido:

```bat
materializar_dbguo_reclamacoes_silver.bat
```

Para abrir o painel:

```bat
run.bat painel
```

## Ordem recomendada

```bat
set ANOMES=202606
run.bat apuracao_parcial
run.bat dbguo_reclamacoes
run.bat painel
```

Se o raw DBGUO ainda não existir, executar antes:

```bat
set REEXTRAIR_DBGUO=1
extrair_dbguo_reclamacoes.bat
```
