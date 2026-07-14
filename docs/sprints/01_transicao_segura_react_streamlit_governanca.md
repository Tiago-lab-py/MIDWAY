# Sprint 01 - Transição segura React/Streamlit/Governança

## Objetivo

Preparar a evolução do MIDWAY para uma ferramenta governada de qualidade OMS/ADMS/IQS, reduzindo o viés atual de telas específicas e preservando segurança operacional.

## Escopo

- Definir navegação macro, intermediária e detalhada.
- Separar lente regulatória da lente cliente/operação.
- Definir papel do React como interface principal.
- Manter Streamlit como laboratório analítico.
- Desenhar contratos de API antes de alterar telas.
- Planejar exibição de códigos com nomes/descrições.
- Planejar tabelas/listas interativas com ordenação e filtros.
- Planejar fluxo de decisão humana assistida.

## Fora de escopo

- Não remover Streamlit.
- Não alterar exportação IQS sem validação específica.
- Não substituir decisão humana por automação.
- Não centralizar a navegação em `92/82`.
- Não criar algoritmo novo sem contrato, teste e governança.

## Documentos de referência ativos

- `docs/33_reorientacao_anomalias_oms_iqs.md`;
- `docs/34_governanca_exportacao_iqs.md`;
- `docs/35_contrato_exportacao_iqs.md`;
- `docs/36_regras_prodist_copel.md`;
- `docs/37_visao_produto_governanca_midway.md`;
- `docs/modulos/README.md`.

## Entregáveis

1. Mapa de navegação React.
2. Inventário de páginas Streamlit que devem permanecer como laboratório.
3. Contratos de API para cockpit, anomalias, tratamentos, fila técnica, governança e detalhe.
4. Modelo de dados para decisão humana assistida.
5. Lista de dicionários humanos necessários para códigos e descrições.
6. Critérios de priorização por impacto regulatório, financeiro, operacional e cliente.

## Transição segura

### Fase 1 - Inventário

Mapear telas, endpoints, consultas e regras existentes.

Resultado esperado:

- o que fica;
- o que será refeito;
- o que será arquivado;
- o que precisa de dicionário humano;
- o que depende de dados ainda ausentes.

### Fase 2 - Contratos

Antes de alterar UI, definir respostas da API com:

- nível da navegação;
- lente regulatória/cliente;
- código + descrição;
- impacto;
- evidências;
- recomendação;
- status de governança;
- link para detalhe.

### Fase 3 - Implementação incremental

Implementar por fatias pequenas:

1. Cockpit macro.
2. Lista de anomalias por módulo.
3. Detalhe de ocorrência/interrupção/UC.
4. Tratamentos robotizados.
5. Fila técnica.
6. Governança e pacote IQS.

### Fase 4 - Convivência

React e Streamlit convivem até que:

- a tela React tenha dados equivalentes ou melhores;
- as regras estejam explicadas;
- os filtros estejam validados;
- o usuário consiga auditar antes/depois;
- não haja perda de visão analítica importante.

## Riscos de regressão

| Risco | Mitigação |
| --- | --- |
| Perder regra já testada no Streamlit | Inventariar consulta antes de migrar |
| Voltar ao viés `92/82` | Usar catálogo de módulos como fonte da navegação |
| Confundir faturados e não faturados | Separar lente PRODIST e lente cliente |
| Exportar arquivo fora do padrão IQS | Respeitar `docs/35_contrato_exportacao_iqs.md` |
| Mostrar código sem significado humano | Exigir dicionário `código - descrição` |
| Aprovar ajuste sem justificativa | Aplicar fluxo de decisão governada |

## Plano de validação

- Validar que cada tela mostra nível macro/intermediário/detalhado corretamente.
- Validar que conjunto e alimentador aparecem com número e nome.
- Validar que tabelas possuem ordenação e filtro.
- Validar que valores sugeridos têm valor atual, valor recomendado e descrição.
- Validar que decisão divergente exige justificativa.
- Validar que exportação IQS continua usando contrato rígido.
- Validar que Streamlit continua disponível para análises ainda não migradas.

## Critério de aceite

A sprint será aceita quando:

- existir mapa de navegação aprovado;
- contratos de API estiverem definidos;
- houver lista de dicionários humanos necessários;
- React tiver plano incremental sem quebrar Streamlit;
- governança de decisão humana estiver contemplada;
- nenhum documento ativo tratar `92/82` como objetivo principal.

## Rollback/contenção

Como a sprint é de transição segura:

- manter Streamlit funcionando;
- preservar endpoints antigos até substituição validada;
- não remover arquivos de exportação;
- usar flags ou rotas paralelas para novas telas;
- manter documentação histórica em `docs/historico/` para consulta.

