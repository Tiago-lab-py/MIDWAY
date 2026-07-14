# Sprint 02 - Drill-down de impacto regulatório e operação

## Objetivo

Permitir que o cockpit macro evolua para investigação intermediária sem perder a separação entre lente regulatória e lente cliente/operação.

A primeira entrega conecta o ranking de conjuntos elétricos ao detalhe do conjunto, abrindo a leitura por alimentador, ocorrência e código técnico com nome quando disponível.

## Escopo

- Corrigir o denominador macro de `DEC/FEC` para usar `UC_FATURADA` da COPEL.
- Criar endpoint de detalhe por conjunto elétrico.
- Permitir clique no `Top conjuntos` da tela Produto.
- Permitir clique nas ocorrências do detalhe para abrir o modal técnico existente.
- Permitir clique no alimentador para abrir detalhe intermediário por alimentador.
- Expor agente de `suspeita_falha_RA` na tela Produto.
- Acoplar serviços ADMS ao detalhe do alimentador e ao agente `suspeita_falha_RA`.
- Separar explicitamente lente regulatória e lente cliente/operação no detalhe do alimentador.
- Exibir pré-validação governada do pacote IQS sem gerar arquivo.
- Mostrar resumo do conjunto selecionado.
- Mostrar ranking de alimentadores do conjunto.
- Mostrar ocorrências críticas do conjunto.
- Manter códigos e nomes de conjunto/alimentador.
- Separar métricas regulatórias de evidências operacionais.

## Fora de escopo

- Não alterar exportação IQS.
- Não remover Streamlit.
- Não implementar aprovação humana nesta fatia.
- Não transformar o detalhe em tabela gigante.
- Não substituir a tela de Anomalias por este drill-down.

## Documentos de referência ativos

- `docs/37_visao_produto_governanca_midway.md`;
- `docs/36_regras_prodist_copel.md`;
- `docs/35_contrato_exportacao_iqs.md`;
- `docs/pedencia_para_rodar_copel.md`;
- `docs/sprints/01_transicao_segura_react_streamlit_governanca.md`.

## Entregáveis

1. Endpoint `GET /api/produto/detalhe-conjunto/{conjunto}`.
2. Endpoint `GET /api/produto/detalhe-alimentador/{alimentador}`.
3. Endpoint `GET /api/produto/suspeitas-ra`.
4. Endpoint `GET /api/produto/validacao-iqs`.
5. Painel de detalhe aberto a partir do `Top conjuntos`.
6. Cards do conjunto com CHI/CI, DEC/FEC estimado, expurgos e não faturados.
7. Tabela curta de alimentadores com ordenação e clique para detalhe.
8. Detalhe do alimentador com lente regulatória e cliente/operação.
9. Tabela curta de ocorrências críticas com ordenação.
10. Acesso ao detalhe técnico da ocorrência a partir da lista curta.
11. Indicação explícita das regras usadas.

## Contrato inicial da API

```text
GET /api/produto/detalhe-conjunto/{conjunto}
```

Parâmetros:

- `limite_alimentadores`: máximo de alimentadores retornados;
- `limite_ocorrencias`: máximo de ocorrências retornadas.

Resposta esperada:

- `resumo`: métricas consolidadas do conjunto;
- `alimentadores`: ranking intermediário por alimentador;
- `ocorrencias`: ocorrências mais relevantes para drill-down;
- `regras`: critérios de cálculo e ordenação;
- `fontes`: bases usadas e status.

```text
GET /api/produto/detalhe-alimentador/{alimentador}
```

Resposta esperada:

- `resumo`: métricas do alimentador por lente regulatória e cliente/operação;
- `dias`: reincidência diária, FIC recorrente, RA e serviços ADMS;
- `ocorrencias`: ocorrências priorizadas do alimentador com serviços e interrupções sem serviço;
- `suspeitas_ra`: recorte do agente RA para o alimentador.

```text
GET /api/produto/suspeitas-ra
```

Resposta esperada:

- resumo de equipamentos/dia suspeitos;
- compensação FIC estimada;
- FIC/CI e CHI/DIC associados;
- serviços ADMS vinculados e interrupções sem serviço;
- lista ordenada por score da suspeita.

```text
GET /api/produto/validacao-iqs
```

Resposta esperada:

- checks bloqueantes de base/layout;
- pendências físicas de arquivo: datas, UNIX/LF e encoding;
- referência explícita ao contrato `docs/35_contrato_exportacao_iqs.md`.

## Riscos de regressão

| Risco | Mitigação |
| --- | --- |
| Confundir CHI/CI com DEC/FEC | Exibir unidade e regra do denominador |
| Misturar faturados e não faturados | Separar campos regulatórios e cliente/operação |
| Travar tela com listas grandes | Limitar ranking e ocorrências |
| Exibir código sem nome | Usar referências locais e marcar nome pendente |
| Duplicar ressarcimento | Manter agregações por UC/ocorrência quando aplicável |
| Interpretar ausência de serviço como ajuste automático | Tratar ausência de serviço apenas como evidência de suspeita |

## Plano de validação

- Validar build do frontend.
- Validar compilação da rota FastAPI.
- Validar que o endpoint responde mesmo quando alguma tabela auxiliar estiver ausente.
- Validar clique no conjunto sem quebrar a ordenação da tabela.
- Validar clique no alimentador sem quebrar a ordenação da tabela.
- Validar clique na ocorrência abrindo o detalhe técnico existente.
- Validar que conjunto e alimentador exibem código + nome quando disponível.
- Validar que suspeita RA não gera alteração automática de IQS.
- Validar que serviços ADMS usam `PID_INTRP_SRVE = NUM_SEQ_INTRP`.
- Validar que pré-validação IQS não gera arquivo físico.

## Critério de aceite

A sprint 02 fica aceita quando:

- o cockpit macro permite abrir detalhe por conjunto;
- o painel mostra resumo, alimentadores e ocorrências;
- o detalhe do alimentador separa visão regulatória e cliente/operação;
- o agente RA aparece como fila técnica/suspeita, não como ajuste automático;
- os serviços ADMS aparecem como evidência operacional no alimentador e no score RA;
- a pré-validação IQS mostra bloqueios e pendências físicas;
- as ocorrências do painel permitem navegar para o detalhe técnico;
- a leitura fica útil para decisão humana sem exigir tabela extensa;
- `DEC/FEC` macro usa `UC_FATURADA` como denominador;
- nenhuma regra de exportação IQS é alterada.

## Rollback/contenção

- O endpoint novo é paralelo e pode ser removido sem afetar endpoints existentes.
- O clique no ranking é incremental; a tabela continua funcional se o detalhe falhar.
- O Streamlit permanece como laboratório analítico.
- A exportação IQS não é tocada nesta sprint.
