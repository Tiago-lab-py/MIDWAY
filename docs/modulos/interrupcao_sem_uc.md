# Módulo `INTERRUPCAO_SEM_UC`

## Objetivo

Identificar interrupções ou ocorrências que ficaram sem UC apurável após os tratamentos e avaliar se devem gerar ajuste no IQS.

## Escopo

- interrupção;
- ocorrência.

## Fontes

- `gold_interrupcao_sem_uc`;
- `gold_ocorrencia_sem_uc`;
- `adms_iqs_interrupcao_sem_uc_export`;
- `adms_iqs_alterados`.

## Critérios de anomalia

1. Interrupção permanece em `ESTADO_INTRP = 4`.
2. Todas as UCs vinculadas foram removidas da base apurável.
3. Não existe exceção de manobra que impeça ajuste.

## Evidências

- `NUM_SEQ_INTRP`;
- `NUM_OCORRENCIA_ADMS`;
- total de UCs originais;
- total de UCs apuráveis;
- motivo de perda da base;
- existência de manobra ou referência cruzada.

## Impacto

- FEC/DEC;
- DIC/FIC;
- quantidade de interrupções indevidamente remanescentes;
- risco de exportar evento sem base de UC.

## Ação sugerida

- Enviar para fila técnica quando houver referência de manobra.
- Quando aprovado, exportar ajuste para `ESTADO_INTRP = 7`, `NUM_MOTIVO_TRAT_DIF_UCI = 90` e `INDIC_SIT_PROCES_INDIC_UCI = R`.

## Campos IQS afetados

- `ESTADO_INTRP`;
- `NUM_MOTIVO_TRAT_DIF_UCI`;
- `INDIC_SIT_PROCES_INDIC_UCI`.

## Exportação IQS

- `data/export/interrupcao_sem_uc`;
- pacote final deve cumprir `docs/35_contrato_exportacao_iqs.md`.

## Risco de falso positivo

- Interrupção pode ser origem de manobra válida.
- Ocorrência pode conter outra interrupção ainda apurável.
