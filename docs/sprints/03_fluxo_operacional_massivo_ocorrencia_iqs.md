# Sprint 03 — Fluxo operacional massivo, ocorrência pontual e saída IQS

## Objetivo

Reorganizar o MIDWAY para contar uma história operacional clara para gestores, analistas de Pós Operação e TI.

A ferramenta não deve começar por cartões soltos ou telas genéricas de anomalia. O fluxo principal deve partir das tratativas em massa, seguir para aprovação governada e só então aprofundar em ocorrências pontuais quando houver exceção, dúvida ou discordância técnica.

## Princípio de desenho

O produto deve responder, nesta ordem:

1. O que a ferramenta encontrou?
2. O que consegue tratar em massa?
3. Qual foi o impacto regulatório, operacional e financeiro?
4. O algoritmo é coerente o suficiente para encaminhar aprovação?
5. Quais casos exigem análise pontual?
6. Qual alteração será implantada no IQS?
7. Quem decidiu, com qual justificativa e evidência?

## Fluxo operacional aprovado

### 1. Visão Geral

Página de entrada para gestores e apresentação executiva.

Deve mostrar:

- ganhos estimados da ferramenta;
- quantidade de ocorrências/interrupções analisadas;
- quantidade de tratativas automáticas;
- quantidade de pendências manuais;
- impacto em DEC/FEC, DIC/FIC e ressarcimento;
- situação do lote;
- prontidão ou bloqueio para IQS.

Não deve ser uma tela de investigação detalhada.

### 2. Tratativas em Massa

Página principal de trabalho dos algoritmos.

Deve permitir:

- selecionar o módulo ou agente de tratamento;
- rodar ou atualizar o algoritmo;
- visualizar o lote gerado;
- comparar valores originais e sugeridos;
- medir impacto do lote;
- avaliar coerência estatística e operacional;
- separar itens aprováveis automaticamente de itens que exigem revisão;
- encaminhar lote para aprovação.

Exemplos de módulos:

- componente/causa;
- suspeita de falha RA;
- sobreposição de UC;
- duração suspeita;
- ressarcimento atípico;
- interrupção sem UC;
- dia crítico/ISE;
- duplicidade de tipo.

Esta página deve responder: “posso confiar no lote gerado pelo algoritmo?”

### 3. Aprovação de Tratativas

Página para gestor ou perfil autorizado.

Deve permitir:

- aprovar lote automático;
- rejeitar lote automático;
- aprovar parcialmente quando previsto;
- ver impacto antes/depois;
- ver amostra de ocorrências afetadas;
- exigir justificativa em rejeição ou ajuste divergente;
- travar exportação IQS quando houver bloqueio.

A aprovação em massa ocorre antes do detalhamento manual, exceto quando o algoritmo indicar pendências.

### 4. Busca e Investigação de Ocorrência

Página do analista de Pós Operação.

Deve permitir localizar uma ocorrência com problema por:

- número da ocorrência;
- interrupção;
- UC;
- alimentador;
- conjunto;
- data/hora;
- grupo;
- componente;
- causa;
- status Pós;
- impacto em CHI/CI;
- ressarcimento;
- tipo de suspeita.

Esta tela deve ser voltada à localização rápida, não a cards genéricos.

### 5. Detalhe da Ocorrência

Ao abrir a ocorrência, o analista deve visualizar um dossiê objetivo.

Campos mínimos:

- ocorrência;
- interrupções vinculadas;
- UCs afetadas;
- data/hora início;
- data/hora fim;
- duração;
- regional;
- conjunto número e nome;
- alimentador número e nome;
- equipamento/chave;
- grupo original código e descrição;
- componente original código e descrição;
- causa original código e descrição;
- componente sugerido código e descrição;
- causa sugerida código e descrição;
- grupo sugerido código e descrição;
- justificativa do algoritmo;
- evidências usadas;
- impacto em DIC/FIC;
- impacto em DEC/FEC;
- impacto em ressarcimento;
- serviços e reclamações relacionados;
- status Pós;
- histórico de decisão.

O analista deve conseguir entender:

- o que estava no OMS;
- o que o algoritmo sugeriu;
- por que sugeriu;
- qual campo mudaria no IQS;
- qual impacto regulatório;
- qual justificativa será registrada.

### 6. Ajuste Manual

Usado somente quando:

- a tratativa em massa não resolve;
- o algoritmo não tem confiança suficiente;
- o analista discorda da sugestão;
- há evidência operacional adicional;
- há necessidade de correção excepcional.

Regras:

- decisão humana prevalece sobre o algoritmo;
- divergência contra recomendação exige justificativa;
- antes/depois devem ficar auditáveis;
- alteração manual deve entrar em fluxo de aprovação;
- caso recorrente pode originar novo algoritmo futuramente.

### 7. Saída IQS

Última etapa operacional antes da Administração.

Deve permitir:

- validar pré-requisitos do pacote;
- confirmar aprovações;
- bloquear geração se houver pendência crítica;
- gerar arquivo físico no padrão IQS;
- registrar lote gerado;
- mostrar caminho do arquivo;
- mostrar resumo do conteúdo exportado;
- manter trilha de auditoria.

Regras rígidas:

- separador `|`;
- quebra UNIX/LF;
- encoding `ISO-8859-1`;
- datas em `dd/mm/aaaa hh:mm:ss`;
- sem colunas extras;
- sem colunas faltantes;
- sem mudança fora do layout oficial;
- códigos com descrições visíveis na interface, mas arquivo final no padrão IQS.

## Navegação alvo

Ordem sugerida:

1. `Visão Geral`
2. `Tratativas em Massa`
3. `Aprovação`
4. `Ocorrências`
5. `Ajustes Manuais`
6. `Saída IQS`
7. `Administração`

## Papéis

### Gestor

Precisa ver:

- ganho;
- risco;
- impacto;
- volume;
- aprovação;
- prontidão para IQS.

Não deve depender de investigação linha a linha.

### Analista de Pós Operação

Precisa ver:

- ocorrência;
- datas;
- componente/causa;
- evidências;
- justificativa;
- serviços;
- reclamações;
- recomendação do algoritmo;
- campo alterado.

Deve conseguir discordar do algoritmo com justificativa.

### TI

Precisa ver:

- origem dos dados;
- materialização;
- status dos agentes;
- logs;
- erros;
- regras aplicadas;
- rastreabilidade entre OMS, processamento e IQS.

## O que deve sair do desenho atual

- excesso de cards sem decisão clara;
- etapas visuais soltas sem ação;
- página de anomalia como ponto central do produto;
- navegação baseada em exemplos iniciais como `92/82`;
- mistura de investigação, aprovação e exportação na mesma tela;
- zeros apresentados como resultado quando o cálculo ainda não foi materializado.

## Critérios de aceite da sprint

- A navegação reflete o fluxo operacional aprovado.
- Tratativa em massa aparece antes da investigação pontual.
- A página de ocorrência permite localizar e abrir casos problemáticos.
- O detalhe da ocorrência mostra original, sugerido, evidência e justificativa.
- A aprovação em massa fica separada da alteração manual.
- A saída IQS é a etapa final antes de Administração.
- Nenhuma tela apresenta métrica zerada quando o correto é “não calculado” ou “pendente de materialização”.
- O usuário entende qual ação executar em cada página.

## Pendências técnicas

- Definir endpoints consolidados para resumo de cada agente.
- Materializar impactos por módulo em tabela governada.
- Padronizar contrato de “original/sugerido/justificativa/evidência”.
- Criar busca única de ocorrência.
- Criar dossiê técnico da ocorrência.
- Separar lote automático de proposta manual no frontend.
- Manter exportação IQS apenas após aprovação governada.

## Decisão

Esta sprint substitui a tentativa de organizar o produto a partir da página genérica de anomalias.

O MIDWAY deve ser apresentado como uma ferramenta de:

1. detecção;
2. tratativa massiva;
3. investigação pontual;
4. decisão humana governada;
5. exportação segura ao IQS.
