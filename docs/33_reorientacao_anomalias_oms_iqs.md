# 33 - Reorientação: Anomalias OMS/ADMS para Exportação IQS

Data de atualização: `2026-07-14`

## Objetivo principal

O MIDWAY deve ser tratado como uma plataforma de detecção, análise, decisão e exportação de anomalias dos dados OMS/ADMS para o IQS.

O objetivo não é resolver apenas um caso específico, como `92/82`. Esse caso permanece como um módulo já implementado e útil, mas deve ser entendido como uma especialização dentro de um motor mais amplo.

Fluxo alvo:

```text
Dados OMS/ADMS/IQS
  -> RAW/SILVER/GOLD
  -> detecção de anomalias por módulos
  -> evidências e impacto regulatório/financeiro
  -> decisão humana governada
  -> geração de exportação no layout aceito pelo IQS
  -> auditoria do que foi alterado, rejeitado ou enviado
```

## Regra de arquitetura

Todo desenvolvimento novo deve responder a quatro perguntas:

1. Qual anomalia dos dados OMS/ADMS está sendo detectada?
2. Qual evidência sustenta a suspeita?
3. Qual alteração, se aprovada, deve ser exportada ao IQS?
4. Como a decisão humana fica auditável?

Se a resposta for apenas “tratar `92/82`”, o desenho está estreito demais.

## Módulos de anomalia

### Módulos centrais

| Módulo | Propósito | Saída esperada |
| --- | --- | --- |
| Sobreposição total/parcial por UC | Identificar conflito temporal por UC | Ajuste de início, motivo `91/D`, exportação IQS |
| Interrupção/ocorrência sem UC apurável | Detectar eventos que perderam base apurável | Evidência e possível classificação controlada |
| Duração suspeita | Priorizar eventos com duração incoerente ou extrema | Fila técnica e proposta de ajuste |
| Componente/causa divergente | Comparar OMS/ADMS, serviços, reclamações e referência IQS | Proposta de novo componente/causa |
| Falha de equipamento/comunicação | Detectar religadores/equipamentos com FIC recorrente e baixa reclamação | Fila técnica, evidência operacional e possível ajuste |
| Ressarcimento atípico | Detectar valores financeiros incompatíveis com filtros e granularidade | Auditoria de cálculo e bloqueio de duplicidade |
| Reclamação sem ocorrência compatível | Identificar demanda operacional sem evento IQS aderente | Evidência para investigação ou abertura de ajuste |

### Módulo especializado existente

| Módulo | Status | Observação |
| --- | --- | --- |
| `92/82` | Especialização existente | Deve ser preservado, mas não deve comandar a arquitetura visual, documental ou de exportação. |

## Organização desejada da interface

### Aba Anomalias

Propósito: explorar outliers do conjunto de dados.

Estrutura desejada:

1. Título e contexto do lote.
2. Cards resumo.
3. Abas por tipo de anomalia.
4. Filtros de validação, incluindo `VALID_POS_OPERACAO`.
5. Cards de casos priorizados, não tabela extensa.
6. Suporte à tomada de decisão:
   - resumo humano;
   - impacto `DEC/FEC/DIC/FIC/ressarcimento`;
   - evidências;
   - timeline da ocorrência/interrupção/UC;
   - comparação antes/depois.
7. Painel de decisão e edição:
   - aprovar;
   - rejeitar;
   - editar proposta;
   - enviar para fila técnica;
   - registrar justificativa.

### Aba Análise Técnica

Propósito: investigar tecnicamente ocorrências, interrupções e UCs.

Ela não deve ser apenas uma tabela de ranking. Deve funcionar como uma lente operacional para:

- confirmar evidências;
- comparar serviço, reclamação, causa/componente e referência IQS;
- abrir a ocorrência completa;
- gerar proposta governada.

### Executivo/Governança

Propósito: aprovar pacotes, acompanhar impacto e liberar exportação IQS.

Não deve ser uma tela exclusiva de `92/82`. `92/82` entra como um lote/módulo dentro da governança.

## Documentação ativa: leitura recomendada

### Referência principal

| Documento | Uso |
| --- | --- |
| `README.md` | Entrada operacional do projeto |
| `docs/README.md` | Índice ativo da documentação |
| `docs/00_especificacao.md` | Especificação geral do pipeline OMS/ADMS -> IQS |
| `docs/14_fluxo_oficial_atual.md` | Fluxo operacional mensal |
| `docs/modulos/README.md` | Catálogo oficial de módulos de anomalia |
| `docs/34_governanca_exportacao_iqs.md` | Decisão humana, aprovação e pacote IQS |

### Histórico arquivado

| Documento | Ação recomendada |
| --- | --- |
| `docs/historico/` | Usar apenas como memória técnica; não usar como especificação vigente |
| `docs/historico/sprint/` | Sprints antigas; migrar conceitos úteis para docs ativos antes de reutilizar |
| `old_v1/` | Usar apenas como referência conceitual de cards e fluxo investigativo; não misturar no produto atual |

### Regra para conteúdo antigo

Não recupere um documento inteiro do histórico como especificação. Primeiro extraia o conceito útil, generalize para o modelo multi-anomalias e registre no catálogo de módulos ou na governança de exportação.

## Critério para novas anomalias

Um novo módulo de anomalia deve gerar, no mínimo:

- identificador do módulo;
- escopo (`ocorrencia`, `interrupcao`, `uc`, `equipamento`, `alimentador`, `conjunto`);
- evidências objetivas;
- impacto estimado;
- sugestão de ação;
- campos IQS afetados;
- risco de falso positivo;
- status de decisão;
- caminho de exportação ou justificativa de não exportação.

## Norte de implementação

O próximo ciclo deve priorizar:

1. consolidar catálogo de módulos de anomalia;
2. padronizar saída dos agentes em uma estrutura comum;
3. fazer a aba `Anomalias` consumir esse catálogo;
4. fazer a exportação IQS receber ajustes aprovados de qualquer módulo;
5. reduzir referências visuais e documentais que fazem `92/82` parecer o produto principal.
