# Sprint 02 - Drill-down de impacto regulatório e operação

## Objetivo

Permitir que o cockpit macro evolua para investigação intermediária sem perder a separação entre lente regulatória e lente cliente/operação.

A primeira entrega conecta o ranking de conjuntos elétricos ao detalhe do conjunto, abrindo a leitura por alimentador, ocorrência e código técnico com nome quando disponível.

## Escopo

- Corrigir o denominador macro de `DEC/FEC` para usar `UC_FATURADA` da COPEL.
- Criar endpoint de detalhe por conjunto elétrico.
- Permitir clique no `Top conjuntos` da tela Produto.
- Permitir clique nas ocorrências do detalhe para abrir o modal técnico existente.
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
2. Painel de detalhe aberto a partir do `Top conjuntos`.
3. Cards do conjunto com CHI/CI, DEC/FEC estimado, expurgos e não faturados.
4. Tabela curta de alimentadores com ordenação.
5. Tabela curta de ocorrências críticas com ordenação.
6. Acesso ao detalhe técnico da ocorrência a partir da lista curta.
7. Indicação explícita das regras usadas.

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

## Riscos de regressão

| Risco | Mitigação |
| --- | --- |
| Confundir CHI/CI com DEC/FEC | Exibir unidade e regra do denominador |
| Misturar faturados e não faturados | Separar campos regulatórios e cliente/operação |
| Travar tela com listas grandes | Limitar ranking e ocorrências |
| Exibir código sem nome | Usar referências locais e marcar nome pendente |
| Duplicar ressarcimento | Manter agregações por UC/ocorrência quando aplicável |

## Plano de validação

- Validar build do frontend.
- Validar compilação da rota FastAPI.
- Validar que o endpoint responde mesmo quando alguma tabela auxiliar estiver ausente.
- Validar clique no conjunto sem quebrar a ordenação da tabela.
- Validar clique na ocorrência abrindo o detalhe técnico existente.
- Validar que conjunto e alimentador exibem código + nome quando disponível.

## Critério de aceite

A sprint 02 fica aceita quando:

- o cockpit macro permite abrir detalhe por conjunto;
- o painel mostra resumo, alimentadores e ocorrências;
- as ocorrências do painel permitem navegar para o detalhe técnico;
- a leitura fica útil para decisão humana sem exigir tabela extensa;
- `DEC/FEC` macro usa `UC_FATURADA` como denominador;
- nenhuma regra de exportação IQS é alterada.

## Rollback/contenção

- O endpoint novo é paralelo e pode ser removido sem afetar endpoints existentes.
- O clique no ranking é incremental; a tabela continua funcional se o detalhe falhar.
- O Streamlit permanece como laboratório analítico.
- A exportação IQS não é tocada nesta sprint.
