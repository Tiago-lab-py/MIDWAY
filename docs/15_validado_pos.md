# 15 - Validação Pós-Operação

## Objetivo

Registrar a regra de uso da coluna `VALID_POS_OPERACAO` no painel **Analytics Pós-Operação**.

Essa coluna indica se uma ocorrência já foi analisada pela equipe de pós-operação e considerada correta, mesmo quando aparece em auditorias, rankings estatísticos ou listas de outliers.

## Campo de Controle

| Campo | Valores | Significado |
| --- | --- | --- |
| `VALID_POS_OPERACAO` | `S` | Ocorrência já validada pela pós-operação |
| `VALID_POS_OPERACAO` | `N` | Ocorrência ainda não validada pela pós-operação |
| `VALID_POS_OPERACAO` | vazio/nulo | Sem informação de validação |

## Regra de Negócio

Quando `VALID_POS_OPERACAO = 'S'`, a ocorrência deve ser tratada como **já verificada e aceita** pela pós-operação.

Mesmo que essa ocorrência apareça como outlier por critérios estatísticos, duração, quantidade de UCs afetadas, sobreposição ou outro indicador de risco, ela não deve ser interpretada como pendência operacional comum.

Ela continua sendo exibida para rastreabilidade, mas deve ser visualmente diferenciada como:

```text
Validado Pós-Operação
```

## Uso no Painel Streamlit

Na página **Analytics Pós-Operação**, deve existir um filtro para `VALID_POS_OPERACAO`.

Opções recomendadas:

| Opção | Comportamento |
| --- | --- |
| `Todos` | Exibe ocorrências validadas e não validadas |
| `Somente validados` | Exibe apenas `VALID_POS_OPERACAO = 'S'` |
| `Somente não validados` | Exibe apenas `VALID_POS_OPERACAO = 'N'` ou nulo |

O padrão recomendado é:

```text
Todos
```

Assim o painel não esconde registros automaticamente.

## Interpretação dos Outliers

Outliers com `VALID_POS_OPERACAO = 'S'` devem permanecer disponíveis para consulta, auditoria e histórico.

Porém, eles devem ser separados dos casos ainda pendentes de validação.

Exemplo:

| Situação | Interpretação |
| --- | --- |
| Outlier + `VALID_POS_OPERACAO = 'N'` | Requer análise da pós-operação |
| Outlier + `VALID_POS_OPERACAO = 'S'` | Já analisado e aceito |
| Não outlier + `VALID_POS_OPERACAO = 'S'` | Ocorrência validada |
| Não outlier + `VALID_POS_OPERACAO = 'N'` | Ocorrência sem validação registrada |

## Métricas Recomendadas

A página **Analytics Pós-Operação** deve apresentar, quando possível:

- total de ocorrências analisadas;
- total de ocorrências com `VALID_POS_OPERACAO = 'S'`;
- total de ocorrências com `VALID_POS_OPERACAO = 'N'` ou nulo;
- total de outliers já validados;
- total de outliers ainda pendentes.

## Benefício

Essa regra evita que ocorrências já conferidas continuem aparecendo como problemas pendentes.

Também preserva a rastreabilidade, pois a ocorrência validada continua visível no painel, mas com interpretação correta.

## Observação

A coluna `VALID_POS_OPERACAO` não elimina registros da base e não altera o cálculo técnico da interrupção.

Ela funciona como uma camada de governança operacional para diferenciar:

```text
outlier pendente
```

de:

```text
outlier já verificado e aceito pela pós-operação
```
