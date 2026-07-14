# Módulo `DIA_CRITICO_ISE`

## Objetivo

Avaliar efeitos de Dia Crítico e ISE sobre a apuração e sobre a interpretação de interrupções.

## Escopo

- conjunto;
- regional;
- dia;
- janela de ISE.

## Fontes

- calendário/janelas ISE;
- apuração por conjunto/dia;
- interrupções ADMS/IQS;
- dados de continuidade.

## Critérios de anomalia

1. Interrupções dentro de janela ISE ou Dia Crítico.
2. Indicadores classificados com protocolo/família incompatível.
3. Divergência entre janela oficial e classificação usada no cálculo.

## Evidências

- regional;
- conjunto;
- data;
- hora início/fim;
- protocolo;
- janela ISE;
- CHI/CI afetado.

## Impacto

- DISE;
- DICRI;
- exclusão/inclusão indevida na base líquida;
- explicação de impacto por conjunto/dia.

## Ação sugerida

- Validar a janela oficial.
- Ajustar classificação somente com evidência documental.

## Campos IQS afetados

- protocolo de justificativa;
- tipo de protocolo;
- campos de data/hora quando o erro for temporal.

## Exportação IQS

Somente após aprovação governada. Pacote final deve cumprir `docs/35_contrato_exportacao_iqs.md`.

## Risco de falso positivo

- Janelas oficiais podem variar por regional e data.
