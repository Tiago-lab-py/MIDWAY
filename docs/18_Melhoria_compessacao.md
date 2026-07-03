# 18 - Melhoria de Compensação: Filtros IQS para DIC, FIC e DMIC

## Objetivo

Registrar a melhoria implementada para alinhar os cálculos do MIDWAY às regras de filtro usadas pelo IQS para `DIC`, `FIC` e `DMIC`.

A implementação incorpora as siglas do IQS quando esses campos estão disponíveis na base apurável. Quando os campos ainda não existem no DuckDB processado, o sistema usa comportamento compatível com a regra padrão, assumindo `DIC_` e `FIC_` sem regra de expurgo.

## Origem da Regra

A referência vem da consulta IQS baseada em:

- `HIST_CONS_AFETADO_INTERRUPCAO`;
- `INTERRUPCAO`;
- `MOTIVO_EXCL_CONS_AFETADO_INTRP`;
- `TIPO_INDICADOR_QUALID_SERV_DIS`;
- `REGRA_EXPURGO_INDIC_DISTR`.

As siglas que devem ser preservadas no MIDWAY são:

| Campo IQS | Uso |
| --- | --- |
| `SIGLA_TIQS_DIC` | Identifica se o motivo pertence ao indicador `DIC_` |
| `SIGLA_REID_DIC` | Identifica regra de expurgo aplicada ao DIC |
| `SIGLA_TIQS_FIC` | Identifica se o motivo pertence ao indicador `FIC_` |
| `SIGLA_REID_FIC` | Identifica regra de expurgo aplicada ao FIC |

## Regra DIC Líquido

O `DIC_LIQ` considera a duração da interrupção quando:

```sql
SUBSTR(NVL(SIGLA_TIQS_DIC, 'DIC_'), 1, 4) = 'DIC_'
AND SIGLA_REID_DIC IS NULL
```

Fórmula:

```sql
SUM((DATA_HORA_FIM_INTRP - DATA_HORA_INIC_INTRP) * 24)
```

Interpretação:

- se não houver motivo de exclusão para DIC, o evento entra no DIC líquido;
- se houver regra de expurgo para DIC, o evento não entra no DIC líquido.

## Regra DIC Bruto

O `DIC_BRT` considera a duração da interrupção quando:

```sql
SUBSTR(NVL(SIGLA_TIQS_DIC, 'DIC_'), 1, 4) = 'DIC_'
AND NVL(TRIM(SIGLA_REID_DIC), 'X') NOT IN
    ('DFC','USU','USI','ACI','FM','ERR','DUP','CHP','DFI','PTP')
```

Fórmula:

```sql
SUM((DATA_HORA_FIM_INTRP - DATA_HORA_INIC_INTRP) * 24)
```

## Regra FIC Líquido

O `FIC_LIQ` conta a interrupção quando:

```sql
SUBSTR(NVL(SIGLA_TIQS_FIC, 'FIC_'), 1, 4) = 'FIC_'
AND SIGLA_REID_FIC IS NULL
```

Fórmula:

```sql
COUNT(NUM_INTRP_HCAI)
```

Interpretação:

- se não houver motivo de exclusão para FIC, o evento conta no FIC líquido;
- se houver regra de expurgo para FIC, o evento não conta no FIC líquido.

## Regra FIC Bruto

O `FIC_BRT` conta a interrupção quando:

```sql
SUBSTR(NVL(SIGLA_TIQS_FIC, 'FIC_'), 1, 4) = 'FIC_'
AND NVL(TRIM(SIGLA_REID_FIC), 'X') NOT IN
    ('DFC','USU','USI','ACI','FM','ERR','DUP','CHP','DFI','PTP','MAN')
```

Fórmula:

```sql
COUNT(NUM_INTRP_HCAI)
```

Observação: para `FIC_BRT`, a lista de exclusão contém `MAN`, diferentemente da regra de `DIC_BRT`.

## Regra DMIC

O `DMIC` deve seguir a elegibilidade do `DIC`, pois é a maior duração individual considerada para a UC.

Regras recomendadas:

| Indicador | Base de elegibilidade | Cálculo |
| --- | --- | --- |
| `DMIC_LIQ` | Mesma regra do `DIC_LIQ` | `MAX(duração_hora)` |
| `DMIC_BRT` | Mesma regra do `DIC_BRT` | `MAX(duração_hora)` |

Assim, eventos excluídos do `DIC_LIQ` também não devem disputar `DMIC_LIQ`.

Eventos excluídos do `DIC_BRT` também não devem disputar `DMIC_BRT`.

## Normalização Obrigatória

Todos os campos de sigla devem ser tratados como texto:

```sql
TRIM(CAST(campo AS VARCHAR))
```

Para comparação de prefixo:

```sql
SUBSTR(COALESCE(TRIM(CAST(SIGLA_TIQS_DIC AS VARCHAR)), 'DIC_'), 1, 4) = 'DIC_'
SUBSTR(COALESCE(TRIM(CAST(SIGLA_TIQS_FIC AS VARCHAR)), 'FIC_'), 1, 4) = 'FIC_'
```

Para regra de expurgo:

```sql
COALESCE(TRIM(CAST(SIGLA_REID_DIC AS VARCHAR)), 'X')
COALESCE(TRIM(CAST(SIGLA_REID_FIC AS VARCHAR)), 'X')
```

## Campos a Materializar no MIDWAY

A camada tratada/apurada deve preservar, quando possível:

| Campo | Descrição |
| --- | --- |
| `SIGLA_TIQS_DIC` | Sigla do tipo de indicador IQS para DIC |
| `SIGLA_REID_DIC` | Sigla da regra de expurgo IQS para DIC |
| `SIGLA_TIQS_FIC` | Sigla do tipo de indicador IQS para FIC |
| `SIGLA_REID_FIC` | Sigla da regra de expurgo IQS para FIC |
| `DIC_LIQ_IQS` | Duração líquida conforme regra IQS |
| `DIC_BRT_IQS` | Duração bruta conforme regra IQS |
| `FIC_LIQ_IQS` | Contagem líquida conforme regra IQS |
| `FIC_BRT_IQS` | Contagem bruta conforme regra IQS |
| `DMIC_LIQ_IQS` | Maior duração líquida conforme regra IQS |
| `DMIC_BRT_IQS` | Maior duração bruta conforme regra IQS |

Na implementação local, os campos agregados na camada de continuidade usam os nomes:

| Campo MIDWAY | Significado |
| --- | --- |
| `DIC` | `DIC_LIQ` conforme elegibilidade IQS |
| `FIC` | `FIC_LIQ` conforme elegibilidade IQS |
| `DMIC` | `DMIC_LIQ` conforme elegibilidade IQS |
| `DIC_BRT` | DIC bruto conforme lista de expurgos IQS |
| `FIC_BRT` | FIC bruto conforme lista de expurgos IQS |
| `DMIC_BRT` | DMIC bruto conforme lista de expurgos IQS |
| `SIGLAS_TIQS_DIC` | Siglas DIC encontradas para a UC |
| `SIGLAS_REID_DIC` | Regras DIC encontradas para a UC |
| `SIGLAS_TIQS_FIC` | Siglas FIC encontradas para a UC |
| `SIGLAS_REID_FIC` | Regras FIC encontradas para a UC |

## Relação com Componente 52 e Causa 71

As regras documentadas em `docs/17_ressarcimento_comp52.md` continuam válidas.

Portanto:

| Condição | Efeito |
| --- | --- |
| `COD_COMP_INTRP = 52` | Não compõe `DIC`, `FIC`, `DMIC` nem compensação |
| `COD_CAUSA_INTRP = 71` | Não compõe `DIC`, `FIC`, `DMIC` nem compensação |

Essas exclusões devem ser aplicadas em conjunto com as regras de siglas IQS.

## Implementação Aplicada

1. O cálculo verifica se as siglas IQS existem em `gold_apuracao_uc`.
2. Quando existem, usa `SIGLA_TIQS_DIC`, `SIGLA_REID_DIC`, `SIGLA_TIQS_FIC` e `SIGLA_REID_FIC`.
3. Quando não existem, usa fallback compatível:
   - `SIGLA_TIQS_DIC = 'DIC_'`;
   - `SIGLA_REID_DIC = NULL`;
   - `SIGLA_TIQS_FIC = 'FIC_'`;
   - `SIGLA_REID_FIC = NULL`.
4. Calcula elegibilidade equivalente às flags:
   - `IND_DIC_LIQ_IQS`;
   - `IND_DIC_BRT_IQS`;
   - `IND_FIC_LIQ_IQS`;
   - `IND_FIC_BRT_IQS`.
5. Calcula `DIC/FIC/DMIC` líquidos com base nessas regras.
6. Calcula `DIC_BRT`, `FIC_BRT` e `DMIC_BRT` para conferência contra o IQS.
7. Aplica também as exclusões por `COD_COMP_INTRP = 52` e `COD_CAUSA_INTRP = 71`.
8. Expõe os campos no painel Streamlit para conferência.

## Critério de Aceite

Para uma UC e período informados, os totais do MIDWAY devem bater com a consulta IQS de referência:

- `DIC_LIQ`;
- `DIC_BRT`;
- `FIC_LIQ`;
- `FIC_BRT`;
- `DMIC_LIQ`;
- `DMIC_BRT`.

As divergências devem ser auditáveis por registro, exibindo:

- UC;
- ocorrência;
- interrupção;
- duração;
- `SIGLA_TIQS_DIC`;
- `SIGLA_REID_DIC`;
- `SIGLA_TIQS_FIC`;
- `SIGLA_REID_FIC`;
- motivo da inclusão ou exclusão.

## Observação

Essa melhoria aproxima o MIDWAY da regra oficial do IQS, reduzindo divergências entre a pré-apuração local e os indicadores calculados no sistema de origem.
