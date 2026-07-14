# Módulo `CORRECAO_9282`

## Objetivo

Tratar o caso especializado de correção componente/causa relacionado à regra `92/82`.

## Status

Módulo específico e legado operacional do primeiro desenvolvimento. Ele deve permanecer documentado, mas não deve definir a arquitetura geral do MIDWAY.

## Escopo

- ocorrência;
- interrupção;
- componente/causa.

## Fontes

- `gold_interrupcao_tratada`;
- `raw_adms_servicos`;
- `gold_reclamacao_ocorrencia_resumo`;
- referência IQS de grupo/componente/causa;
- PostgreSQL governança.

## Critérios de anomalia

1. Evidência de componente/causa crítica.
2. Par atual associado ao caso `92/82`.
3. Serviço, reclamação ou referência IQS sustentam alteração.

## Evidências

- par atual;
- par sugerido;
- serviço ADMS;
- reclamação vinculada;
- grupos IQS;
- score de evidência.

## Impacto

- qualidade da classificação;
- fila técnica;
- exportação IQS de ajuste específico.

## Ação sugerida

- Aprovar ajuste automático quando a evidência for robusta.
- Enviar para fila técnica quando houver conflito.

## Campos IQS afetados

- `COD_COMP_INTRP`;
- `COD_CAUSA_INTRP`;
- `VALID_POS_OPERACAO`, quando aplicável.

## Exportação IQS

- `data/export/correcao_9282`;
- layout IQS obrigatório;
- pacote final deve cumprir `docs/35_contrato_exportacao_iqs.md`.

## Risco de falso positivo

- Usar o caso `92/82` como regra geral para todas as anomalias.
- Aprovar em massa sem validar evidência por módulo.
