# 41 - Página Ocorrência

Data de atualização: `2026-07-25`

## Objetivo

Definir a especificação funcional da página `Ocorrência` no frontend React do MIDWAY.

A página deve funcionar como uma bancada de investigação para o analista técnico. O objetivo principal não é apresentar resumo executivo, mas ajudar a resolver uma ocorrência, entender se há anomalia real ou falha de processo/automação, conferir os dados consolidados e registrar uma decisão governada quando houver evidência suficiente.

## Problema a resolver

O frontend ainda não aproveita integralmente os processamentos já desenvolvidos no backend e nas camadas `RAW`, `SILVER` e `GOLD`.

Na prática, o analista precisa responder perguntas como:

- esta ocorrência é um evento operacional real ou um erro de processamento?
- o problema está no dado de origem, na regra, na automação, no cadastro ou na classificação técnica?
- há impacto relevante em `DIC/FIC`, `DEC/FEC`, ressarcimento ou IQS?
- há evidência suficiente para propor correção?
- qual módulo da ferramenta deve ser usado para resolver o caso?

A página `Ocorrência` deve reduzir o tempo entre encontrar a suspeita e tomar uma decisão rastreável.

## Princípio de desenho

A página não deve duplicar a visão executiva já existente no Dashboard ou Produto.

Regra:

```text
Dashboard mostra onde está o problema.
Ocorrência ajuda o analista a resolver o problema.
Governança aprova e audita a decisão.
```

Portanto, a página `Ocorrência` deve priorizar:

- busca;
- evidência;
- comparação;
- diagnóstico provável;
- orientação por módulo;
- abertura do detalhe;
- registro de proposta.

Não deve priorizar:

- cards executivos repetidos;
- ranking gerencial amplo;
- resumo sem ação;
- métricas sem caminho de decisão.

## Público-alvo

Usuários principais:

- `ANALISTA`;
- `GESTOR`;
- `ADM`.

Uso esperado:

- analista usa diariamente para investigar casos;
- gestor usa pontualmente para revisar decisões e orientar priorização;
- administrador usa para validar funcionamento da integração e dos módulos.

## Fluxo de trabalho esperado

O fluxo da página deve ser:

```text
localizar caso
  -> escolher lente de análise
  -> conferir evidências
  -> comparar GOLD/detalhe
  -> classificar diagnóstico provável
  -> abrir ocorrência completa
  -> registrar proposta ou descartar
```

Etapas visuais recomendadas:

1. Localizar ocorrência, interrupção ou UC.
2. Escolher lente: impacto, fila, outlier, Gold ou módulo.
3. Conferir evidência e registrar decisão no detalhe.

## Estrutura da página

Abas recomendadas:

| Aba | Objetivo | Papel do analista |
| --- | --- | --- |
| `Busca` | Localizar ocorrência, interrupção ou UC | Encontrar rapidamente o caso e abrir detalhe |
| `Impacto` | Priorizar ocorrências relevantes | Separar casos por CHI, CI, duração, ressarcimento e violação |
| `Fila` | Trabalhar pendências técnicas | Filtrar, priorizar e classificar falha provável |
| `Outliers` | Ver anomalias estatísticas ou regras violadas | Avaliar se o desvio é real ou falha de dado/processo |
| `Gold` | Conferir dado consolidado | Validar campos finais, interrupções e apuração UC |
| `Como resolver` | Orientar por módulo | Saber qual função usar, o que verificar e qual decisão tomar |

## Busca

### Objetivo

Permitir que o analista encontre um caso específico sem depender de planilha ou consulta SQL.

### Tipos de busca

- ocorrência;
- interrupção;
- UC.

### Resultado esperado

Cada resultado deve mostrar:

- número da ocorrência;
- interrupções vinculadas;
- período;
- quantidade de UCs;
- reclamações;
- componente/causa;
- CHI e CI líquidos;
- score ou sinal de reclamação;
- grupos IQS;
- linha temporal quando disponível;
- botão para abrir ocorrência completa.

### Decisão apoiada

Responder:

```text
Este é o caso certo para investigar?
Há evidência suficiente para abrir o detalhe?
```

## Impacto

### Objetivo

Priorizar ocorrências que merecem atenção humana.

### Filtros mínimos

- CHI mínimo;
- CI mínimo;
- ressarcimento mínimo;
- duração suspeita;
- grupo;
- componente;
- causa;
- tipo de problema;
- limite de registros.

### Critérios de priorização

O ranking deve considerar:

- impacto regulatório;
- impacto financeiro;
- volume de UCs;
- duração;
- violação de componente/causa;
- sinais de regra 92/82 ou equivalente;
- reincidência quando disponível.

### Decisão apoiada

Responder:

```text
Qual ocorrência devo analisar primeiro?
O impacto justifica revisão humana?
```

## Fila técnica

### Objetivo

Transformar pendências em uma fila de trabalho acionável, não apenas uma tabela.

### Campos mínimos

- score de impacto;
- prioridade;
- ocorrência;
- interrupção;
- fonte da sugestão;
- nível de evidência;
- diagnóstico provável;
- sugestão;
- status.

### Filtros mínimos

- busca livre;
- status;
- prioridade;
- diagnóstico provável;
- módulo.

### Diagnóstico provável

A fila deve ajudar a separar:

| Diagnóstico | Quando usar |
| --- | --- |
| `Anomalia operacional provável` | O comportamento parece real e relevante |
| `Falha processual provável` | Há inconsistência de fluxo, reclamação, encerramento ou classificação |
| `Falha de automação provável` | Regra, integração ou processamento parecem não ter aplicado corretamente |
| `Necessita validação humana` | Evidência insuficiente para decidir automaticamente |

### Decisão apoiada

Responder:

```text
Este item exige correção, descarte, melhoria de regra ou investigação operacional?
```

## Outliers

### Objetivo

Expor anomalias detectadas por processamento prévio, com impacto e contexto.

### Requisitos

A aba deve permitir:

- buscar por regional, conjunto, UC, ocorrência ou tipo de anomalia;
- ordenar por data, impacto, duração, CHI, CI ou ressarcimento;
- ver severidade e status;
- diferenciar impacto bruto e líquido quando disponível.

### Interpretação esperada

O outlier não deve ser tratado automaticamente como erro.

Ele deve ser classificado pelo analista como:

- evento real;
- erro de data/hora;
- falha de integração;
- duplicidade;
- classificação incorreta;
- regra incompleta;
- dado insuficiente.

## Dados Gold

### Objetivo

Permitir que o analista visualize os dados consolidados diretamente no frontend para novas análises.

### Camadas de leitura

| Camada | Conteúdo |
| --- | --- |
| `Resumo Gold` | Métricas consolidadas da ocorrência |
| `Ocorrência` | Campos principais da ocorrência |
| `Interrupções` | Interrupções vinculadas e campos técnicos |
| `Apuração UC` | UCs, DIC/FIC, motivos e situação de processamento |

### Campos prioritários

- ocorrência;
- interrupções;
- UCs apuradas;
- CHI líquido;
- CI líquido;
- componente;
- causa;
- estado da interrupção;
- validação pós-operação;
- situação da UC;
- motivo de tratamento diferenciado.

### Decisão apoiada

Responder:

```text
A suspeita vem do evento real ou de transformação incorreta entre origem e Gold?
```

## Como resolver por módulo

### Objetivo

Explicar ao analista qual função da ferramenta usar para resolver cada tipo de problema.

Essa aba não deve depender apenas de existir volume carregado na API. Ela deve apresentar um catálogo operacional mínimo dos módulos, enriquecido por contagens e exemplos quando existirem.

### Conteúdo por módulo

Cada módulo deve mostrar:

- código;
- nome;
- escopo;
- descrição;
- função da página;
- critério de detecção;
- orientação do analista;
- documento técnico;
- sinais carregados;
- ocorrências de exemplo, quando disponíveis.

### Módulos mínimos

| Módulo | Função | O que ajuda a resolver |
| --- | --- | --- |
| `DURACAO_IMPACTO` | Abrir Impacto | Duração, CHI, CI ou ressarcimento fora do padrão |
| `COMPONENTE_CAUSA` | Filtrar componente/causa | Classificação técnica divergente ou inválida |
| `RECLAMACOES_SERVICOS` | Buscar ocorrência | Divergência entre atendimento, reclamação e ocorrência |
| `INTERRUPCAO_SEM_UC` | Conferir Gold | Lacuna de vínculo entre interrupção e UC |
| `SOBREPOSICAO_UC` | Buscar UC | Duplicidade ou sobreposição de janelas |
| `RESSARCIMENTO_ATIPICO` | Ver Gold | Compensação incompatível, duplicada ou concentrada |

### Decisão apoiada

Responder:

```text
Qual ferramenta devo usar para resolver este tipo de ocorrência?
O problema é de evento, processo, automação, cadastro ou integração?
```

## Pop-up de ocorrência completa

O detalhe completo continua sendo o ponto de decisão.

Deve concentrar:

- ocorrência;
- interrupções;
- serviços;
- apuração UC;
- reclamações;
- evidências;
- comparação antes/depois;
- proposta de correção;
- justificativa.

O analista deve conseguir registrar:

- correção de componente/causa;
- cancelamento/validação;
- alteração de campo;
- justificativa técnica;
- proposta para governança.

## Requisitos de UX

### A página deve

- reduzir cliques para abrir a ocorrência completa;
- manter filtros visíveis e úteis;
- permitir busca livre;
- ordenar tabelas por impacto;
- apresentar diagnósticos em linguagem humana;
- mostrar código e descrição sempre que possível;
- orientar a próxima ação do analista;
- evitar cards executivos repetidos.

### A página não deve

- repetir o Dashboard;
- esconder o dado técnico necessário;
- exibir módulo vazio sem orientação;
- mostrar resumo sem ação;
- tratar todo outlier como erro;
- tomar decisão automática sem evidência e governança.

## Contratos de API envolvidos

Endpoints usados ou previstos:

```text
GET /api/qualidade/busca
GET /api/qualidade/ocorrencias/{num_ocorrencia}
GET /api/qualidade/uc-visao
GET /api/qualidade/analise-tecnica
GET /api/qualidade/analise-tecnica/opcoes
GET /api/executivo/9282/fila-tecnica
GET /api/anomalias
GET /api/anomalias/modulos
GET /api/anomalias/outliers/raw
POST /api/governanca/alteracoes
```

## Critérios de aceite

A página será considerada aderente quando:

- o analista conseguir localizar ocorrência, interrupção ou UC;
- a fila técnica permitir filtrar e priorizar casos;
- a aba de módulos nunca ficar vazia sem explicação;
- cada módulo orientar claramente como resolver o problema;
- os dados Gold puderem ser consultados por ocorrência;
- outliers puderem ser pesquisados e ordenados;
- a página não duplicar os cards executivos do Dashboard;
- a ocorrência completa puder ser aberta a partir das principais lentes;
- uma proposta governada puder ser registrada quando houver evidência.

## Arquivos envolvidos

Frontend:

```text
frontend/src/App.jsx
frontend/src/styles.css
```

Backend:

```text
midway/api/routes/qualidade.py
midway/api/routes/anomalias.py
midway/api/routes/executivo_9282.py
midway/api/routes/governanca.py
midway/v7/anomaly_repository.py
```

## Próximas melhorias recomendadas

1. Enriquecer códigos com descrição humana nos resultados de busca e Gold.
2. Adicionar histórico de decisões anteriores por ocorrência/interrupção.
3. Permitir marcação de causa raiz: evento real, processo, automação, cadastro, integração.
4. Adicionar filtros por regional, conjunto, alimentador e equipamento na busca operacional.
5. Exibir divergência entre valores originais, sugeridos e aprovados no detalhe.
6. Criar métrica de aprendizado por módulo: aceito, rejeitado, editado e falso positivo.

