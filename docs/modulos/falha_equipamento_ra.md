# Módulo `FALHA_EQUIPAMENTO_RA`

## Objetivo

Detectar suspeita de falha de comunicação ou automação em religadores automáticos e equipamentos com FIC recorrente.

## Escopo

- equipamento;
- alimentador;
- conjunto;
- dia de operação.

## Fontes

- `gold_interrupcao_tratada`;
- `gold_apuracao_uc`;
- `gold_reclamacao_ocorrencia_resumo`;
- `gold_ressarcimento_prodist`;
- `raw_adms_servicos`, quando disponível.

## Critérios de anomalia

1. `TIPO_CHV_INTRP = RA`.
2. Ocorrências sucessivas no mesmo equipamento e dia.
3. FIC/CI recorrente.
4. Zero reclamação no equipamento/dia ou baixa reclamação proporcional no alimentador/conjunto/dia.
5. Ressarcimento FIC positivo ou impacto técnico relevante.

## Evidências

- `NUM_OPER_CHV_INTRP`;
- `ALIM_INTRP`;
- `COD_CONJTO_ELET_ANEEL_INTRP`;
- dia de operação;
- quantidade de ocorrências RA;
- CI/FIC líquido;
- ressarcimento FIC estimado;
- quantidade de reclamações;
- consumidores com FIC recorrente.

## Impacto

- FIC;
- ressarcimento;
- confiabilidade de comunicação do equipamento;
- risco de registro indevido no OMS/ADMS.

## Ação sugerida

- Abrir investigação técnica do equipamento.
- Comparar serviços no mesmo alimentador/conjunto/dia.
- Propor ajuste apenas quando a causa raiz for confirmada.

## Campos IQS afetados

Depende da decisão:

- estado da interrupção;
- causa/componente;
- motivo de tratamento;
- validação Pós.

## Exportação IQS

O agente exporta evidência em `data/export/suspeita_falha_RA`. Alteração IQS deve passar por governança antes de compor arquivo oficial.

## Risco de falso positivo

- Baixa reclamação pode ocorrer por perfil rural ou baixa taxa de contato.
- Evento real de rede pode gerar várias atuações no mesmo equipamento.
