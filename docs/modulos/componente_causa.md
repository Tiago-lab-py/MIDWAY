# Módulo `COMPONENTE_CAUSA`

## Objetivo

Detectar divergências de componente/causa entre OMS/ADMS, serviços ADMS, reclamações DBGUO e referência oficial IQS.

## Escopo

- ocorrência;
- interrupção;
- serviço ADMS.

## Fontes

- `gold_interrupcao_tratada`;
- `raw_adms_servicos`;
- `gold_reclamacao_ocorrencia_resumo`;
- `gold_reclamacao_uc_vinculada`;
- `raw_iqs_referencia_componente_causa`;
- cache de análise técnica.

## Critérios de anomalia

1. Par componente/causa atual não é aderente à referência IQS.
2. Serviço ADMS sugere par válido diferente.
3. Reclamação reforça causa/componente divergente.
4. Há impacto relevante em CHI, CI/FIC ou ressarcimento.

## Evidências

- par atual `COD_COMP_INTRP/COD_CAUSA_INTRP`;
- nomes/descrições do grupo, componente e causa atuais;
- pares de serviço;
- nomes/descrições do grupo, componente e causa sugeridos;
- grupos IQS de componente/causa;
- score de reclamação;
- descrição textual da reclamação;
- quantidade de pares válidos/inválidos.

## Impacto

- qualidade cadastral;
- classificação regulatória;
- ressarcimento;
- risco de envio IQS com causa/componente incompatível.

## Ação sugerida

- Propor novo componente/causa quando serviço ou reclamação sustentam a troca.
- Enviar para fila técnica quando houver conflito de evidências.

## Campos IQS afetados

- `COD_COMP_INTRP`;
- `COD_CAUSA_INTRP`;
- `COD_GRUPO_COMP_INTRP`, quando derivado do componente.

Na interface, esses campos devem ser exibidos como código + nome/descrição. Exemplo: `92 - Religador/Chave automática`.

## Exportação IQS

- via ajuste governado aprovado;
- exportador deve usar layout oficial IQS e preservar campos não alterados;
- pacote final deve cumprir `docs/35_contrato_exportacao_iqs.md`.

## Risco de falso positivo

- Serviço pode estar associado por alimentador/dia, mas não diretamente à ocorrência.
- Reclamação textual pode ser ambígua.
- A referência IQS pode mudar e deve ser reextraída.
