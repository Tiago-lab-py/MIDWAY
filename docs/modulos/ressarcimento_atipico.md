# Módulo `RESSARCIMENTO_ATIPICO`

## Objetivo

Detectar valores de ressarcimento incompatíveis com a granularidade correta de UC, ocorrência e interrupção.

## Escopo

- UC;
- ocorrência;
- interrupção;
- conjunto de ocorrências associadas.

## Fontes

- `gold_ressarcimento_prodist`;
- `gold_apuracao_uc`;
- `gold_continuidade_uc`;
- análise técnica/cache.

## Critérios de anomalia

1. Ressarcimento agregado muito maior que o esperado.
2. Soma sem filtro por ocorrência/interrupção.
3. Duplicidade de compensação de uma UC em várias ocorrências.
4. Divergência entre FIC/DIC apurado e valor estimado.

## Evidências

- `COMP_FIC_PRODIST`;
- `COMP_TOTAL_PRODIST`;
- UC;
- ocorrência;
- interrupção;
- quantidade de ocorrências por UC;
- valor alocado por ocorrência.

## Impacto

- risco financeiro;
- erro de priorização técnica;
- decisão gerencial baseada em valor inflado.

## Ação sugerida

- Alocar ressarcimento por ocorrência/interrupção antes de somar.
- Bloquear ranking quando houver duplicidade detectada.
- Exibir a granularidade usada no cálculo.

## Campos IQS afetados

Normalmente não altera diretamente o layout IQS. Este módulo audita cálculo e priorização.

## Exportação IQS

Não exporta sozinho. Pode gerar bloqueio ou evidência para outro módulo.

## Risco de falso positivo

- Ressarcimento alto pode ser legítimo em conjunto com muitas UCs afetadas.
