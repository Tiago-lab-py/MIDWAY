# 37 - Visão de produto e governança MIDWAY

## Objetivo

Definir a visão de produto do MIDWAY antes de evoluir as telas em React ou Streamlit.

O MIDWAY deve ser uma ferramenta para identificar divergências e suspeitas em dados OMS/ADMS, explicar tratamentos automatizados, orientar análise humana, medir ganhos e governar aprovações até a exportação IQS.

O produto não deve ser centrado em um único caso, como `92/82`. Ele deve operar como plataforma de qualidade de dados, continuidade, impacto regulatório, impacto financeiro e visão do cliente.

## Decisão de direção

| Frente | Papel recomendado |
| --- | --- |
| React | Interface principal de operação, governança e navegação executiva |
| Streamlit | Laboratório analítico, validação rápida de consultas e prototipação |
| API FastAPI | Camada única de dados, regras, evidências e decisões |
| DuckDB/PostgreSQL | DuckDB para processamento local; PostgreSQL para governança, filas e auditoria |

React deve ser corrigido para abandonar o viés de uma regra específica. Streamlit deve permanecer como bancada de experimentação enquanto as visões estabilizam.

## Princípios do produto

1. Mostrar primeiro o impacto no negócio, depois permitir drill-down técnico.
2. Separar visão regulatória da visão cliente/operação.
3. Explicar toda regra robotizada em linguagem curta.
4. Distinguir cálculo regulatório, suspeita/anomalia, tratamento automático e decisão manual.
5. Medir ganho antes/depois de cada correção.
6. Manter governança com aprovação, justificativa, auditoria e exportação rastreável.

## Lentes de análise

### Lente regulatória

Foco no PRODIST, IQS e apuração oficial:

- clientes faturados;
- `DIC/FIC`;
- `DEC/FEC`;
- `DMIC`, `DICRI`, `DISE`;
- compensação/ressarcimento PRODIST;
- arquivos aceitos pelo IQS;
- impacto de cada ajuste nos indicadores.

Documentos de referência:

- `docs/36_regras_prodist_copel.md`;
- `docs/modulos/dic_fic_prodist.md`;
- `docs/modulos/dec_fec_prodist.md`;
- `docs/modulos/ressarcimento_prodist.md`;
- `docs/35_contrato_exportacao_iqs.md`.

### Lente cliente/operação

Foco na experiência real e na qualidade do registro operacional:

- todos os clientes afetados, faturados e não faturados;
- reclamações;
- serviços;
- reincidência;
- alimentador, chave e equipamento;
- suspeita de falha de comunicação;
- divergência entre OMS, ADMS, Pós-operação e IQS.

Essa lente é essencial porque o OMS registra o universo operacional, enquanto o PRODIST regula principalmente a base faturada.

## Níveis de navegação

O sistema deve permitir navegação em três níveis.

### Nível macro

Usado para gestão e priorização.

| Dimensão | Exemplos |
| --- | --- |
| Empresa | COPEL |
| Regional | `CSL`, `NRT`, `NRO`, `LES`, `OES` |
| Regulatório | `DEC/FEC`, `DIC/FIC`, compensação |
| Cliente | clientes afetados, reclamações, clientes não faturados |
| Financeiro | compensação estimada, evitada, corrigida ou bloqueada |
| Qualidade | volume de anomalias, regras aplicadas, pendências |

Perguntas que este nível responde:

- Onde está o maior risco regulatório?
- Qual regional concentra suspeitas relevantes?
- Qual o ganho estimado das correções automáticas?
- Quanto ainda depende de decisão humana?
- O impacto regulatório e o impacto cliente contam a mesma história?

### Nível intermediário

Usado para direcionar investigação.

| Dimensão | Exemplos |
| --- | --- |
| Conjunto elétrico | impacto por conjunto e dia |
| Alimentador | recorrência, FIC alto, reclamação proporcional |
| Chave/religador | suspeita de falha de comunicação ou operação automática |
| Grupo/componente/causa | divergência técnica e referência IQS |
| Tipo de suspeita | sobreposição, sem UC, duração, ressarcimento, componente/causa |

No ranking por conjunto, a visão intermediária deve separar:

- ocorrências longas: duração maior ou igual a 3 minutos;
- ocorrências curtas: duração menor que 3 minutos;
- CHI/CI líquido regulatório;
- CHI/CI expurgado por Dia Crítico;
- CHI/CI expurgado por ISE/DISE;
- CHI/CI de UCs não faturadas, para visão cliente/operação.

Perguntas que este nível responde:

- Qual alimentador ou chave explica o maior volume de suspeitas?
- O problema é de dado, regra, comunicação, equipamento ou classificação?
- Há FIC recorrente sem reclamação proporcional?
- A suspeita merece ajuste automático, fila técnica ou bloqueio?

### Nível detalhado

Usado para evidência, decisão e auditoria.

| Entidade | Papel |
| --- | --- |
| Ocorrência | agrupador operacional de interrupções |
| Interrupção | evento técnico a ser classificado/tratado |
| UC | unidade afetada, faturada ou não |
| Cliente | perspectiva de impacto e reclamação |
| Serviço | evidência operacional complementar |
| Ajuste | alteração proposta ou aprovada |

Perguntas que este nível responde:

- Qual era o valor antes e depois?
- Qual regra robotizada sugeriu ou executou o tratamento?
- Quais evidências sustentam a decisão?
- O cliente era faturado?
- O ajuste afeta PRODIST, visão cliente ou ambos?

## Tipos de informação que a ferramenta deve exibir

### Legibilidade humana: códigos e descrições

Todo código técnico exibido ao usuário deve vir acompanhado de nome ou descrição.

Regra visual:

```text
código - descrição
```

Exemplos:

| Campo | Exibição recomendada |
| --- | --- |
| `COD_GRUPO_COMP_INTRP` | `L - Linha/Rede` |
| `COD_COMP_INTRP` | `92 - Religador/Chave automática` |
| `COD_CAUSA_INTRP` | `82 - causa cadastrada` |
| `COD_TIPO_INTRP` | `1 - Acidental` |
| `TIPO_PROTOC_JUSTIF_UCI` | `0 - Base DIC/FIC/DMIC` |
| `NUM_MOTIVO_TRAT_DIF_UCI` | `91 - Tratamento diferenciado` |
| `SIGLA_REGIONAL` | `NRT - Norte` |
| `COD_CONJTO_ELET_ANEEL_INTRP` | `12345 - Nome do conjunto elétrico` |
| `ALIM_INTRP` | `ABC123 - Nome do alimentador` |

Quando o dicionário oficial não estiver disponível, a interface deve mostrar o código e sinalizar `descrição não disponível`, em vez de ocultar o código.

Campos de busca e filtros devem aceitar código ou texto. Para o analista, selecionar `92 - Religador` é melhor que digitar apenas `92`.

Na tela `Produto`, dicionários devem aparecer como cobertura estatística e qualidade da legibilidade, não como listas extensas. A busca detalhada por código deve ficar nas telas operacionais que precisam do campo ou em uma tela administrativa específica de dicionários.

Na hierarquia elétrica, conjunto e alimentador são campos obrigatórios de leitura humana:

- número do conjunto + nome do conjunto;
- número/código do alimentador + nome do alimentador.

Na fase local, esses nomes são enriquecidos pelos arquivos:

- `data/input/Referencia_DEC FEC CONJUNTO Ano_Copel.csv`;
- `data/input/Referencia_Alimentador_Copel.CSV`.

Pendência para migração empresarial: extrair e versionar os nomes diretamente do IQS/cadastro oficial da empresa, substituindo a referência local.

Se o nome não estiver disponível na base, a tela deve exibir o número/código e marcar `nome não disponível`, preservando a rastreabilidade.

### Divergências e suspeitas

Cada suspeita deve ter:

- tipo;
- severidade;
- escopo;
- impacto regulatório;
- impacto cliente;
- impacto financeiro;
- evidências;
- regra de detecção;
- sugestão de ação.

Exemplo de texto curto:

```text
Suspeita de falha de religador: múltiplas interrupções no mesmo alimentador/dia, FIC recorrente e reclamação abaixo do esperado para o volume de consumidores afetados.
```

### Tratamentos robotizados

Cada tratamento automático deve mostrar:

- regra aplicada;
- critério objetivo;
- quantidade de registros tratados;
- antes/depois;
- impacto estimado;
- risco de falso positivo;
- motivo de confiança.

Exemplo:

```text
Sobreposição total por UC: a UC estava integralmente contida em outra interrupção da mesma UC e mesmo tipo. O registro contido foi marcado como tratamento 91/D para não duplicar DIC/FIC.
```

### Itens para análise humana

Cada fila técnica deve orientar o analista:

- o que verificar;
- onde olhar;
- quais evidências comparar;
- qual decisão possível;
- qual impacto de aprovar ou rejeitar.

Exemplo:

```text
Verificar se o religador atuou automaticamente sem recomposição real. Conferir serviços, reclamações, sequência de eventos e consumidores afetados no alimentador.
```

## Medição de ganhos

O MIDWAY deve medir ganhos em quatro famílias.

| Família | Métricas |
| --- | --- |
| Regulatório | variação de `DEC/FEC`, `DIC/FIC`, `DMIC`, `DICRI`, `DISE` |
| Financeiro | compensação calculada, evitada, corrigida, bloqueada ou justificada |
| Operacional | anomalias resolvidas, duplicidades removidas, eventos sem UC esclarecidos |
| Cliente | clientes afetados totais, faturados/não faturados, reclamações aderentes, reincidência |

Todo ganho deve ter comparação:

```text
antes -> depois
```

E deve separar:

- ganho por tratamento automático;
- ganho por ajuste manual aprovado;
- ganho potencial ainda pendente;
- risco de ganho indevido por falso positivo.

## Governança e fluxo de aprovação

Fluxo recomendado:

```text
detecção
  -> evidência
  -> proposta
  -> classificação de impacto
  -> fila técnica, quando necessário
  -> aprovação/rejeição
  -> pacote IQS
  -> auditoria
```

Estados:

| Estado | Significado |
| --- | --- |
| `detectado` | suspeita criada pelo motor |
| `tratado_auto` | regra robotizada aplicou tratamento seguro |
| `pendente_analise` | precisa de revisão humana |
| `fila_tecnica` | precisa de evidência operacional adicional |
| `aprovado` | pode compor pacote governado |
| `rejeitado` | não deve alterar dados/exportação |
| `exportado` | entrou em pacote IQS |

## Decisão humana assistida e aprendizado governado

Regra de ouro:

```text
Algoritmo sugere.
Analista decide.
Gestor aprova quando houver impacto relevante.
MIDWAY audita.
Equipe melhora a regra.
```

O MIDWAY deve apoiar a decisão humana, não substituir o analista.

### Valores sugeridos

Toda proposta de correção deve apresentar, no mínimo:

| Informação | Descrição |
| --- | --- |
| Valor atual | Campo como está no OMS/ADMS/IQS |
| Valor sugerido | Campo recomendado pelo algoritmo |
| Nome/descrição | Descrição humana do valor atual e do valor sugerido |
| Regra usada | Explicação curta da regra que gerou a sugestão |
| Evidências | Dados que sustentam a recomendação |
| Impacto estimado | Efeito regulatório, financeiro, operacional e/ou cliente |
| Confiança | Nível de confiança ou severidade da recomendação |
| Risco | Principal risco de falso positivo |

Exemplo:

```text
Campo: COD_CAUSA_INTRP
Atual: 82 - causa atual cadastrada
Sugerido: 13 - causa sugerida pela evidência
Regra: serviço ADMS dominante no mesmo alimentador/dia indica causa aderente à reclamação.
Impacto: altera classificação técnica e pode afetar priorização de ressarcimento.
```

### Decisão do analista

O analista deve poder:

- aceitar a sugestão;
- rejeitar a sugestão;
- editar o valor sugerido;
- enviar para fila técnica;
- anexar observação ou evidência;
- marcar como exceção operacional.

A decisão humana prevalece sobre a sugestão automática.

Quando a decisão for diferente da recomendação, o sistema deve exigir justificativa. Essa justificativa deve ser curta, estruturada e auditável.

Motivos mínimos:

| Motivo | Uso |
| --- | --- |
| `evidencia_operacional_nova` | Analista encontrou evidência fora da regra atual |
| `falso_positivo_algoritmo` | A regra sugeriu ajuste indevido |
| `dados_insuficientes` | Não há segurança para aprovar |
| `excecao_operacional` | Caso real que foge do padrão |
| `regra_incompleta` | A regra precisa evoluir |
| `ajuste_manual_melhor` | Analista propôs valor diferente e justificado |

### Painel de detalhe como captura de conhecimento

O painel detalhado deve permitir que o humano interprete uma nova decisão a partir de:

- timeline da ocorrência;
- interrupções associadas;
- UCs faturadas e não faturadas;
- reclamações;
- serviços;
- alimentador, chave e equipamento;
- histórico de recorrência;
- impacto PRODIST;
- impacto cliente.

Quando o analista tomar uma decisão diferente da recomendação, o painel deve registrar qual evidência sustentou a divergência.

### Aprendizado governado

O sistema deve aprender no sentido de criar uma base de decisões humanas e padrões recorrentes.

Ele não deve alterar regra produtiva sozinho.

Fluxo de aprendizado:

```text
decisão humana divergente
  -> justificativa estruturada
  -> agrupamento de casos semelhantes
  -> análise de recorrência
  -> proposta de nova regra
  -> validação técnica
  -> teste automatizado
  -> aprovação
  -> novo algoritmo ou ajuste de algoritmo
```

Critérios para virar novo algoritmo:

- recorrência relevante;
- evidência objetiva disponível nos dados;
- baixo risco de falso positivo;
- ganho regulatório, financeiro, operacional ou cliente mensurável;
- regra explicável em linguagem simples;
- teste automatizado possível.

### Métricas de aprendizado

O MIDWAY deve medir:

- recomendações aceitas;
- recomendações rejeitadas;
- recomendações editadas;
- decisões divergentes por módulo;
- principais motivos de divergência;
- regras com maior falso positivo;
- regras com maior ganho confirmado;
- oportunidades de novo algoritmo.

## Proposta de telas React

### 1. Cockpit

Visão macro com:

- cards de risco regulatório, financeiro, cliente e qualidade;
- ranking por regional, conjunto, alimentador e tipo de suspeita;
- ganho automático, ganho manual aprovado e pendência;
- alertas de divergência entre visão PRODIST e visão cliente.

### 2. Anomalias

Visão por tipo de suspeita:

- abas por módulo;
- cards em vez de tabelas longas;
- filtros por nível elétrico;
- campos de busca com código + nome/descrição;
- gráficos de tendência e distribuição;
- explicação curta da regra;
- botão para abrir detalhe.

### 3. Tratamentos Robotizados

Visão do que o algoritmo já fez:

- regra;
- quantidade;
- impacto;
- exemplos;
- confiança;
- possibilidade de auditoria.

### 4. Fila Técnica

Visão do que precisa de analista:

- prioridade;
- tipo de suspeita;
- evidências necessárias;
- roteiro de verificação;
- decisão recomendada.

### 5. Governança

Visão de aprovação:

- propostas pendentes;
- antes/depois;
- código e descrição dos valores atuais e sugeridos;
- justificativa;
- aprovador;
- trilha de auditoria;
- geração de pacote IQS conforme `docs/35_contrato_exportacao_iqs.md`.

### 6. Detalhe

Visão drill-down:

```text
COPEL
  -> regional
  -> conjunto elétrico
  -> alimentador
  -> chave/equipamento
  -> ocorrência
  -> interrupção
  -> UC/cliente
```

## Tabelas e listas interativas

Tabelas não devem ser a forma principal de navegação quando houver muitos registros, mas quando forem usadas precisam ser interativas.

Requisitos mínimos:

- cabeçalho com ordenação por coluna;
- filtro por coluna ou busca rápida;
- colunas com código + descrição para campos técnicos;
- destaque visual para impacto regulatório, financeiro e cliente;
- opção de abrir detalhe sem perder o filtro atual;
- exportação de visão filtrada apenas para conferência, não como pacote IQS;
- remoção de colunas sem valor para decisão humana, como identificadores internos redundantes.

Colunas prioritárias em listas operacionais:

| Tipo | Colunas recomendadas |
| --- | --- |
| Hierarquia elétrica | regional, número/nome do conjunto, número/nome do alimentador, chave/equipamento |
| Ocorrência/interrupção | ocorrência, interrupção, início, fim, duração, tipo |
| Indicadores | `DIC/FIC`, `DEC/FEC`, clientes faturados, clientes totais |
| Financeiro | compensação estimada, bloqueada, corrigida ou aprovada |
| Governança | recomendação, decisão humana, justificativa, status, aprovador |

## Papel do Streamlit

Streamlit deve continuar existindo como:

- bancada de validação;
- exploração SQL;
- protótipo de gráficos;
- comparação rápida antes/depois;
- apoio ao desenvolvimento de novas regras.

Quando uma análise amadurecer, ela deve migrar para React/API como funcionalidade governada.

## Regras de implementação futura

Antes de alterar frontend ou backend, cada nova tela ou endpoint deve declarar:

1. qual lente atende: regulatória, cliente/operação ou ambas;
2. qual nível atende: macro, intermediário ou detalhado;
3. qual módulo alimenta a informação;
4. qual decisão humana será apoiada;
5. qual ganho será medido;
6. se pode gerar pacote IQS ou apenas evidência.
7. quais códigos precisam de nome/descrição para leitura humana.

## Próximo passo recomendado

Antes de codificar, desenhar o mapa de navegação React:

```text
Cockpit
  -> Anomalias
  -> Tratamentos Robotizados
  -> Fila Técnica
  -> Governança
  -> Detalhe Operacional
```

Depois, definir contratos de API para cada visão, evitando que a interface volte a ficar enviesada por um único módulo.
