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

## Fatias de implementação

### Fatia 1 - Base paralela de visão de produto

Status: `implementada`

Entrega:

- endpoint `GET /api/produto/visao`;
- página React `Produto`;
- contrato inicial de lentes, níveis, páginas planejadas, hierarquia elétrica, dicionários humanos, decisão assistida e tabelas interativas;
- inclusão da página `produto` na matriz de permissões.

Critério desta fatia:

- não alterar Streamlit;
- não alterar exportação IQS;
- não remover telas existentes;
- permitir validação visual e técnica do desenho antes das próximas telas.

### Fatia 2 - Dicionários humanos e hierarquia elétrica

Status: `implementada`

Entrega:

- endpoint `GET /api/produto/dicionarios`;
- resumo estatístico de cobertura na página `Produto`, sem lista extensa de códigos;
- exibição padronizada `código - nome/descrição`;
- endpoint com busca por código, nome, descrição e relações para uso por telas operacionais;
- dicionários mínimos para regional, tipo de interrupção, protocolo de justificativa e motivo de tratamento;
- leitura da referência IQS `gold_iqs_referencia_componente_causa` para grupo, componente e causa;
- leitura de `gold_interrupcao_tratada` para códigos de conjunto elétrico e alimentador;
- enriquecimento dos nomes por arquivos locais em `data/input/Referencia_DEC FEC CONJUNTO Ano_Copel.csv` e `data/input/Referencia_Alimentador_Copel.CSV`.

Observação importante:

- quando o nome do conjunto ou alimentador não existir nos arquivos locais, a tela mantém o código visível e marca o item como `nome_pendente`;
- pendência empresarial: após migração para a empresa, extrair nomes de conjunto e alimentador diretamente do IQS/cadastro oficial, substituindo a referência local.

Critério desta fatia:

- não alterar Streamlit;
- não alterar exportação IQS;
- não bloquear o analista quando a descrição estiver ausente;
- sinalizar explicitamente a ausência de descrição em vez de esconder o código;
- manter a tela `Produto` como visão macro, com gráficos e resumos estatísticos, não como catálogo operacional gigante.

### Fatia 3 - Cockpit macro inicial por impacto

Status: `implementada`

Entrega:

- endpoint `GET /api/produto/cockpit`;
- cards macro para ocorrências, UCs, DIC/CHI, FIC/CI, DEC/FEC estimado, compensação PRODIST e duração suspeita;
- ranking regional por impacto regulatório;
- ranking de conjuntos elétricos por impacto, com ocorrências longas/curtas, expurgos Dia Crítico/ISE e não faturados;
- tratamento seguro quando o DuckDB processado estiver bloqueado por outra aplicação;
- alertas explícitos quando nomes oficiais de conjunto/alimentador ainda estiverem pendentes.

Observação importante:

- o cockpit inicial usa as bases `gold_apuracao_uc`, `gold_ressarcimento_prodist` e `gold_consumidores` quando disponíveis;
- `DEC/FEC` é apresentado como estimativa macro derivada de `CHI/CI líquido ÷ denominador COPEL`;
- no ranking de conjuntos, ocorrência longa usa critério de duração maior ou igual a 3 minutos;
- expurgos de Dia Crítico usam `TIPO_PROTOC_JUSTIF_UCI = '1'`;
- expurgos ISE/DISE usam `TIPO_PROTOC_JUSTIF_UCI IN ('5', '6')`;
- não faturados são estimados a partir da base tratada cruzada com `gold_uc_fatura`;
- nomes de conjunto e alimentador usam referência local em `data/input`;
- pendência empresarial: extrair nomes diretamente do IQS/cadastro oficial após migração para a empresa.

Critério desta fatia:

- não alterar Streamlit;
- não alterar exportação IQS;
- não misturar decisão automática com decisão humana;
- manter leitura macro para priorização, não para aprovação final.

### Fatia 4 - Anomalias por módulos e decisão assistida

Status: `implementada`

Entrega:

- catálogo governado de módulos de anomalia na API;
- resposta de `GET /api/anomalias` enriquecida com `modulo_codigo`, `modulo_nome`, descrição, orientação e documento;
- endpoint `GET /api/anomalias/modulos`;
- tela React `Anomalias` com abas por módulo, não por exemplo específico;
- painel de orientação do módulo com impacto e ação esperada do analista;
- detalhe da anomalia exibindo módulo, escopo, critério curto, documento e orientação;
- validação Pós tratada como evidência da decisão, não como filtro principal da navegação.

Observação importante:

- a tela não deve depender de tabelas longas como forma primária de análise;
- a decisão humana continua obrigatória para aprovar, rejeitar, editar ou pedir análise;
- novos padrões encontrados pelo analista podem virar novos módulos ou algoritmos governados.

Critério desta fatia:

- não alterar exportação IQS;
- não remover telas antigas;
- não transformar uma anomalia específica, como `92/82`, no fluxo principal;
- manter códigos, nomes, descrições e documentos visíveis para o usuário humano.

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
