# Módulo `RESSARCIMENTO_PRODIST`

## Objetivo

Calcular a compensação financeira por transgressão de indicadores de continuidade do fornecimento.

Este módulo segue o PRODIST Módulo 8 vigente e os filtros COPEL descritos em `docs/36_regras_prodist_copel.md`.

## Escopo

- UC;
- indicador individual;
- classe de tensão;
- valor de compensação.

## Fontes

- `gold_continuidade_uc`;
- `gold_ressarcimento_prodist`;
- `gold_metas_uc`;
- `gold_vrc`.

## Base de cálculo

A compensação usa a base compensável, não necessariamente a mesma base total realizada.

Exclusões COPEL da base financeira:

- `COD_COMP_INTRP = '52'`;
- `COD_CAUSA_INTRP = '71'`;
- posto particular;
- chave particular/acessante;
- UC acessante.

## Classe de tensão e coeficientes

| Classe | Regra operacional | Coeficiente continuidade |
| --- | --- | --- |
| `AT` | grupo `A`, níveis `1`, `2`, `3` | `108` |
| `MT` | grupo `A`, níveis `3a`, `3A`, `4`, `S` | `40` |
| `BT` | grupo `B` | `34` |

Para `DICRI` e `DISE`, o módulo usa coeficientes próprios para MT/BT conforme implementado em `gold_ressarcimento_prodist`.

## Fórmulas operacionais

| Parcela | Regra |
| --- | --- |
| `COMP_DIC_BRUTA_PRODIST` | `DIC_BASE_COMPENSACAO * VRC / 730 * KEI1` quando `DIC_BASE_COMPENSACAO > META_DIC` |
| `COMP_FIC_BRUTA_PRODIST` | `(FIC_BASE_COMPENSACAO / META_FIC) * META_DIC * VRC / 730 * KEI1` quando `FIC_BASE_COMPENSACAO > META_FIC` |
| `COMP_DMIC_BRUTA_PRODIST` | `DMIC_BASE_COMPENSACAO * VRC / 730 * KEI1` quando `DMIC_BASE_COMPENSACAO > META_DMIC` |
| `COMP_DICRI_BRUTA_PRODIST` | `DICRI_BASE_COMPENSACAO * VRC / 730 * KEI2` quando `DICRI_BASE_COMPENSACAO > META_DICRI` |
| `COMP_DISE_BRUTA_PRODIST` | `DISE_BASE_COMPENSACAO * VRC / 730 * KEI3` quando `DISE_BASE_COMPENSACAO > META_DISE` |

Cada parcela positiva respeita:

- piso de `R$ 0,01`;
- teto de `18 * VRC`.

O total usa:

```text
COMP_TOTAL_PRODIST =
  max(COMP_DIC_PRODIST, COMP_FIC_PRODIST, COMP_DMIC_PRODIST)
  + COMP_DICRI_PRODIST
  + COMP_DISE_PRODIST
```

## Saída

| Tabela | Uso |
| --- | --- |
| `gold_ressarcimento_prodist` | compensação por UC e indicador |

## Testes associados

- `tests/test_ressarcimento_prodist.py`;
- `tests/test_contratos_tabelas.py`.

## Relação com exportação IQS

Este módulo não gera pacote IQS diretamente. Ele calcula impacto financeiro e pode bloquear, priorizar ou justificar decisões de ajuste em outros módulos.
