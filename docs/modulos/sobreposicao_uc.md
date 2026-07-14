# Módulo `SOBREPOSICAO_UC`

## Objetivo

Detectar sobreposição temporal entre interrupções da mesma UC e gerar tratamento compatível com o layout IQS.

## Escopo

- UC;
- interrupção;
- ocorrência, quando todas as interrupções/UCs perdem base apurável.

## Fontes

- `hiadms_raw`;
- `adms_iqs_alterados`;
- `gold_apuracao_uc`;
- `export_sobreposicao_total_uc`;
- `export_sobreposicao_parcial_uc`.

## Critérios de anomalia

1. Mesma UC em janelas de interrupção sobrepostas.
2. Mesmo `COD_TIPO_INTRP`.
3. Mesmo `TIPO_PROTOC_JUSTIF_UCI`.
4. Sobreposição total ou parcial que afeta a base apurável.

## Evidências

- `NUM_SEQ_INTRP`;
- `NUM_UC_UCI`;
- `DATA_HORA_INIC_INTRP`;
- `DATA_HORA_FIM_INTRP`;
- duração original e duração ajustada;
- `NUM_MOTIVO_TRAT_DIF_UCI`;
- `INDIC_SIT_PROCES_INDIC_UCI`;
- `NUM_INTRP_INIC_MANOBRA_UCI`.

## Impacto

- DIC/FIC;
- DEC/FEC;
- ressarcimento PRODIST;
- consistência da base apurável.

## Ação sugerida

- Sobreposição total: classificar a UC contida como `91/D`.
- Sobreposição parcial: ajustar início do trecho posterior.
- Quando necessário, registrar manobra em `NUM_INTRP_INIC_MANOBRA_UCI`.

## Campos IQS afetados

- `DTHR_INICIO_INTRP_UC`;
- `NUM_MOTIVO_TRAT_DIF_UCI`;
- `INDIC_SIT_PROCES_INDIC_UCI`;
- `NUM_INTRP_INIC_MANOBRA_UCI`;
- campos de data/hora derivados, quando o layout exigir.

## Exportação IQS

- `data/export/sobreposicao_total_uc`;
- `data/export/sobreposicao_UC_parcial`;
- layout validado por `midway.export.csv_iqs`.

## Risco de falso positivo

- Não comparar interrupções de `COD_TIPO_INTRP` diferentes.
- Não tratar ISE/Dia Crítico junto com base líquida sem respeitar `TIPO_PROTOC_JUSTIF_UCI`.
- Conferir manobras antes de descartar ou ajustar integralmente.
