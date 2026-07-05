# 16 - Score Analytics Pós-Operação

## Objetivo

Definir a regra de interpretação do **score analytics** usado para priorizar ocorrências no painel **Analytics Pós-Operação**.

O score não substitui a análise técnica da pós-operação. Ele funciona como uma camada de priorização para destacar ocorrências com maior probabilidade de exigir conferência manual.

## Conceito

O score analytics mede o nível de atenção recomendado para uma ocorrência com base em sinais estatísticos, operacionais e de qualidade de dados.

Quanto maior o score, maior a prioridade de análise.

Em linguagem executiva:

```text
O score transforma sinais de risco operacional em uma nota de 0 a 100 para ordenar a fila de verificacao da pos-operacao.
```

Ele não é uma decisão automática. Ele indica **onde olhar primeiro**.

## Fórmula Atual do Painel

O painel calcula primeiro um `SCORE_BRUTO` por ocorrência e depois limita o resultado a `100`:

```text
SCORE_PRIORIDADE = menor valor entre 100 e SCORE_BRUTO
```

A pontuação atual é:

| Critério observado na ocorrência | Pontos |
| --- | ---: |
| Ocorrência completa sem UC apurável | `+100` |
| Pelo menos uma interrupção sem UC apurável | `+50` |
| Existe linha com duração maior ou igual a 24 horas | `+40` |
| Maior duração da ocorrência é maior ou igual a 24 horas | `+30` |
| Mais de um `COD_TIPO_INTRP` na mesma ocorrência | `+20` |
| Mais de um `TIPO_PROTOC_JUSTIF_UCI` na mesma ocorrência | `+15` |
| Existe impacto financeiro estimado em ressarcimento PRODIST | `+20` |
| Volume de UCs afetadas | até `+30` |
| DIC agregado da ocorrência | até `+30` |

Os dois componentes variáveis são calculados assim:

| Componente | Cálculo |
| --- | --- |
| Volume de UCs | `min(30, inteiro(QTD_UCS / 1000))` |
| DIC agregado | `min(30, inteiro(DIC / 100))` |

Exemplo:

```text
Interrupção sem UC apurável       +50
Duração >= 24h                    +40
Maior duração >= 24h              +30
Impacto financeiro estimado       +20
-------------------------------------
SCORE_BRUTO                       140
SCORE_PRIORIDADE                  100
Classificação                     Crítico
```

## Leitura Executiva

| Pergunta | Resposta |
| --- | --- |
| O que o score mede? | Prioridade de conferência manual da ocorrência |
| O que aumenta o score? | Risco de dado inconsistente, duração elevada, impacto financeiro e volume |
| O score muda DIC/FIC? | Não |
| O score descarta registros? | Não |
| O score substitui a pós-operação? | Não |
| Para que serve? | Reduzir ruído e ordenar a análise das ocorrências mais relevantes |

Exemplo de interpretação:

| Faixa | Classificação | Interpretação |
| --- | --- | --- |
| `0` a `29` | Baixo | Ocorrência sem indícios relevantes |
| `30` a `59` | Médio | Ocorrência merece acompanhamento |
| `60` a `79` | Alto | Ocorrência deve ser verificada |
| `80` a `100` | Crítico | Ocorrência prioritária para análise |

## Critérios Recomendados

O score pode considerar, quando disponível:

- duração elevada da interrupção;
- quantidade elevada de UCs afetadas;
- ocorrência com muitos registros contidos;
- sobreposição temporal residual;
- interrupção sem UC apurável;
- diferença relevante entre bases RAW, SILVER e GOLD;
- ausência de dados esperados para apuração;
- reincidência estatística por regional, ocorrência ou tipo de interrupção.

## Relação com `VALID_POS_OPERACAO`

A coluna `VALID_POS_OPERACAO` deve ser considerada na interpretação do score.

Quando `VALID_POS_OPERACAO = 'S'`, a ocorrência pode continuar aparecendo com score alto, mas deve ser entendida como:

```text
ocorrência já verificada e aceita pela pós-operação
```

Ou seja, o score permanece visível para rastreabilidade, mas a ocorrência não deve ser tratada como pendência comum.

## Regras de Exibição no Painel

Na página **Analytics Pós-Operação**, o painel deve exibir:

- score analytics da ocorrência;
- classificação do score;
- indicador `VALID_POS_OPERACAO`;
- status de validação operacional;
- filtros por faixa de score;
- filtros por validação pós-operação.

## Status Analítico

Recomenda-se derivar um status combinando score e validação:

| Condição | Status sugerido |
| --- | --- |
| Score alto/crítico e `VALID_POS_OPERACAO = 'N'` | Pendente prioritário |
| Score alto/crítico e `VALID_POS_OPERACAO = 'S'` | Validado pós-operação |
| Score baixo/médio e `VALID_POS_OPERACAO = 'N'` | Pendente comum |
| Score baixo/médio e `VALID_POS_OPERACAO = 'S'` | Validado |

## Filtros Recomendados

O painel deve permitir filtrar por:

| Filtro | Opções |
| --- | --- |
| Score | `Todos`, `Baixo`, `Médio`, `Alto`, `Crítico` |
| Validação Pós-Operação | `Todos`, `Somente validados`, `Somente não validados` |
| Pendência | `Todos`, `Pendentes`, `Validados` |

## Métricas Recomendadas

A página **Analytics Pós-Operação** deve apresentar:

- total de ocorrências avaliadas;
- total por faixa de score;
- total de ocorrências críticas;
- total de ocorrências críticas já validadas;
- total de ocorrências críticas ainda pendentes;
- percentual de validação por faixa de score.

## Uso Operacional

O score deve apoiar a fila de análise da pós-operação.

A prioridade recomendada é:

1. ocorrências críticas não validadas;
2. ocorrências altas não validadas;
3. ocorrências médias não validadas;
4. ocorrências já validadas, apenas para auditoria ou rastreabilidade.

## Observação

O score analytics não altera registros, não descarta ocorrências e não modifica os cálculos de continuidade.

Ele é uma camada de leitura analítica para orientar a conferência operacional e reduzir ruído em grandes volumes de dados.
