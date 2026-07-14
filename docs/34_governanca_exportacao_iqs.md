# 34 - Governança de decisão e exportação IQS

## Objetivo

Definir a regra comum para transformar suspeitas de anomalia em ajustes aprovados e arquivos aceitos pelo IQS.

Este documento substitui a leitura operacional dos planos antigos focados em um caso específico. A regra vale para qualquer módulo de anomalia do catálogo em `docs/modulos/README.md`.

## Princípios

1. Nenhuma anomalia deve ser exportada automaticamente sem decisão governada.
2. Toda proposta precisa indicar evidência, impacto, campos IQS afetados e risco de falso positivo.
3. A exportação final deve aceitar ajustes aprovados de qualquer módulo, não apenas `92/82`.
4. O arquivo gerado em `data/export/` deve seguir o layout aceito pelo IQS.
5. Auditorias e arquivos de apoio devem ficar fora do pacote oficial de carga.

## Estados da decisão

| Estado | Uso |
| --- | --- |
| `pendente` | Caso detectado, ainda sem análise humana |
| `fila_tecnica` | Precisa de validação operacional adicional |
| `aprovado` | Pode compor pacote IQS |
| `rejeitado` | Não deve alterar o IQS |
| `exportado` | Já entrou em pacote gerado |

## Contrato mínimo de uma proposta

Cada módulo deve produzir:

| Campo | Descrição |
| --- | --- |
| `modulo` | Identificador do módulo de anomalia |
| `escopo` | Ocorrência, interrupção, UC, equipamento, alimentador ou conjunto |
| `chave_negocio` | Chave rastreável usada na origem |
| `evidencias` | Métricas e fatos que sustentam a suspeita |
| `impacto_estimado` | Efeito em DEC/FEC, DIC/FIC, ressarcimento ou qualidade |
| `campos_iqs_afetados` | Campos que seriam alterados no layout IQS |
| `acao_sugerida` | Ajustar, rejeitar, revisar, bloquear ou enviar para fila técnica |
| `justificativa` | Texto compreensível para auditoria e operação |

## Saídas esperadas

| Saída | Pasta | Envia ao IQS |
| --- | --- | --- |
| Auditoria e evidências | `data/marts/` | Não |
| Rascunhos e pré-exportação | `data/marts/` ou subpasta técnica | Não |
| Pacote aprovado | `data/export/` | Sim |
| Resumo de pacote | `data/export/` | Sim, como conferência |

## Critério de aceite do pacote IQS

Antes de liberar a exportação:

- o módulo deve existir no catálogo ativo;
- a proposta deve estar aprovada;
- os campos obrigatórios do layout IQS devem estar preenchidos;
- não pode haver duplicidade pela chave de negócio do ajuste;
- o pacote deve conter somente registros aprovados;
- o resumo deve informar módulo, quantidade, impacto e responsável pela decisão.

## Papel das telas

A aba `Anomalias` deve priorizar outliers por módulo, com cards, gráficos, timeline e painel de decisão.

A aba `Análise Técnica` deve explicar evidências, cruzar ocorrência, interrupção, UC, equipamento, reclamação e serviço, e permitir encaminhar uma decisão governada.

A governança deve consolidar propostas aprovadas de todos os módulos para gerar pacote único ou pacotes por regional no padrão IQS.
