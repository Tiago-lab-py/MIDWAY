# Módulo `RECLAMACOES_SERVICOS`

## Objetivo

Cruzar reclamações DBGUO, serviços ADMS e interrupções IQS/ADMS para detectar divergência operacional.

## Escopo

- reclamação;
- UC;
- ocorrência;
- serviço ADMS;
- alimentador/conjunto.

## Fontes

- `silver_dbguo_reclamacoes`;
- `silver_dbguo_reclamacoes_candidatas`;
- `gold_reclamacao_uc_vinculada`;
- `gold_reclamacao_ocorrencia_resumo`;
- `raw_adms_servicos`;
- `gold_interrupcao_tratada`.

## Critérios de anomalia

1. Reclamação forte sem ocorrência IQS compatível.
2. Reclamação/serviço indicam causa diferente da ocorrência.
3. Serviço ADMS possui par componente/causa divergente.
4. Baixa reclamação incompatível com quantidade de consumidores afetados.

## Evidências

- texto da reclamação;
- score de vínculo;
- UC reclamante;
- ocorrência provável;
- serviço vinculado;
- componente/causa do serviço;
- quantidade de reclamações por ocorrência.

## Impacto

- qualidade da classificação;
- priorização de investigação;
- confiabilidade da relação OMS/ADMS x cliente.

## Ação sugerida

- Confirmar aderência da reclamação.
- Propor componente/causa quando houver evidência convergente.
- Sinalizar ausência de ocorrência compatível.

## Campos IQS afetados

Quando gerar ajuste:

- `COD_COMP_INTRP`;
- `COD_CAUSA_INTRP`;
- campos de estado/motivo se a ocorrência for improcedente ou sem base.

## Exportação IQS

Via ajuste aprovado em módulo raiz. Pacote final deve cumprir `docs/35_contrato_exportacao_iqs.md`.

## Risco de falso positivo

- Texto de reclamação pode se referir a evento próximo, mas não ao evento analisado.
