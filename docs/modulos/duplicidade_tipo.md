# Módulo `DUPLICIDADE_TIPO`

## Objetivo

Detectar duplicidade ou sobreposição indevida entre interrupções de tipos `1`, `2` e `3`.

## Escopo

- interrupção;
- UC;
- equipamento;
- período.

## Fontes

- `adms_iqs_alterados`;
- `gold_apuracao_uc`;
- auditoria de duplicidade por tipo.

## Critérios de anomalia

1. Mesmo período e UC aparecendo em mais de um tipo.
2. Sobreposição entre tipos incompatíveis.
3. Duplicidade exata de intervalo ou equipamento.

## Evidências

- `COD_TIPO_INTRP`;
- `NUM_SEQ_INTRP`;
- `NUM_UC_UCI`;
- início/fim;
- equipamento;
- sobreposição calculada.

## Impacto

- duplicidade de FIC/DIC;
- distorção de DEC/FEC;
- duplicidade de ressarcimento.

## Ação sugerida

- Enviar para análise técnica.
- Propor remoção/ajuste apenas quando a duplicidade for inequívoca.

## Campos IQS afetados

- datas de início/fim;
- motivo de tratamento;
- estado;
- tipo de interrupção, quando confirmado erro cadastral.

## Exportação IQS

Via ajuste aprovado.

## Risco de falso positivo

- Eventos de naturezas diferentes podem se sobrepor legitimamente em algumas situações operacionais.
