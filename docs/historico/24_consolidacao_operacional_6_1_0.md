# 24 - Consolidacao Operacional 6.1.0

## Objetivo

Manter o motor DuckDB local e absorver os melhores conceitos do projeto `analise_ocorrencia`, sem voltar a depender de banco corporativo para processamento analitico pesado.

O MIDWAY passa a seguir a regra:

```text
Banco corporativo e fonte ou destino.
DuckDB local e motor analitico/processamento.
CSV e interface de troca.
Streamlit e camada de decisao.
```

## Arquitetura Alvo

```text
Oracle IQS / ADMS
  -> DuckDB raw
  -> DuckDB silver
  -> DuckDB gold
  -> DuckDB marts
  -> Streamlit multipage
  -> CSV IQS / relatorios / evidencias
```

## Escopo da 6.1.0

### Streamlit Multipage

Organizacao fisica implantada no painel:

- `01 Conferencia ETL`;
- `02 Analytics Pos-Operacao`;
- `03 Dia Critico`;
- `04 Simulacao ISE`;
- `05 Validacao Pos-Operacao`;
- `06 Executivo`;
- `07 SQL`.

O painel agora usa `home.py` como orquestrador e a pasta `pages/` no padrao multipage do Streamlit:

```text
midway/web/home.py
midway/web/library/shared.py
midway/web/library/conferencia_etl.py
midway/web/library/analytics_pos_operacao.py
midway/web/library/dia_critico.py
midway/web/library/simulacao_ise.py
midway/web/library/validacao_pos_operacao.py
midway/web/library/executivo.py
midway/web/library/page_sql.py
midway/web/pages/01_Conferencia_ETL.py
midway/web/pages/02_Analytics_Pos_Operacao.py
midway/web/pages/03_Dia_Critico.py
midway/web/pages/04_Simulacao_ISE.py
midway/web/pages/05_Validacao_Pos_Operacao.py
midway/web/pages/06_Executivo.py
midway/web/pages/07_SQL.py
```

O arquivo `midway/web/streamlit_app.py` permanece apenas como compatibilidade, redirecionando para `home.py`.

## Filtros Compartilhados

Filtros alvo para todas as analises:

- competencia;
- data;
- regional;
- conjunto;
- ocorrencia;
- interrupcao;
- protocolo;
- causa;
- componente.

Na primeira entrega, `ANOMES`, limite de amostra e previa CSV permanecem no sidebar.

A proxima evolucao deve centralizar os demais filtros em um modulo reutilizavel do painel.

## Cadastro Local de Janelas ISE

Tabela alvo no DuckDB local:

```text
gold_janelas_ise
```

Campos previstos:

- regional;
- inicio;
- fim;
- tipo ISE;
- protocolo;
- justificativa;
- usuario;
- status.

Status previstos:

- `SIMULADO`;
- `APROVADO`;
- `APLICADO`;
- `CANCELADO`.

Na primeira entrega, a pagina `04 Simulacao ISE` faz simulacao por janela, mas ainda nao persiste o cadastro.

## Validacao Pos-Operacao Persistente

Tabela alvo no DuckDB local:

```text
gold_validacao_pos_operacao
```

Campos previstos:

- usuario;
- data/hora da decisao;
- ocorrencia;
- interrupcao;
- UC quando aplicavel;
- decisao;
- motivo;
- observacao.

A pagina `05 Validacao Pos-Operacao` ja concentra as ocorrencias e o resumo por validacao existente.

Proxima evolucao:

- salvar decisoes no DuckDB local;
- permitir revisar historico de decisoes;
- exportar CSV de aplicacao para tratamento/IQS.

## Dashboard Executivo

A pagina `06 Executivo` deve consolidar:

- indicadores de qualidade;
- top conjuntos por impacto;
- dias criticos provaveis;
- janelas ISE simuladas/aprovadas;
- compensacao estimada.

Primeira entrega implantada:

- ocorrencias apuraveis;
- UCs apuraveis;
- DIC/FIC liquido;
- compensacao estimada;
- grafico interativo de `DEC` e `FEC` da COPEL em visao diaria, acumulada diaria ou mensal;
- grafico interativo de `DEC` e `FEC` por conjunto, com opcao de todos os conjuntos ou conjunto selecionado;
- graficos interativos de pizza separando `DEC`, `FEC` e compensacao financeira estimada em `Provavel apurado` e `Deve ser tratado`;
- top conjuntos por impacto diario;
- dias criticos provaveis.

A classificacao executiva dos graficos de pizza usa o score de prioridade:

```text
score >= 60  -> Deve ser tratado
score < 60   -> Provavel apurado
```

Para compensacao financeira, o painel soma cada UC uma unica vez a partir de `gold_ressarcimento_prodist`. Isso evita inflar o valor quando a mesma UC participa de mais de uma ocorrencia.

## Marts de Tendencia

Marts alvo:

- causa;
- componente;
- tipo de equipamento;
- regional;
- conjunto.

Esses marts devem apoiar a priorizacao de analise pela pos-operacao e reduzir dependencia de consultas manuais CSV.

## Estado Atual

Implantado nesta etapa:

- reorganizacao fisica do painel em `home.py`, `pages/` e `library/`;
- separacao das telas em modulos menores por assunto;
- modulo compartilhado `library/shared.py` para conexao, filtros basicos e consultas auxiliares;
- pagina inicial de validacao pos-operacao;
- pagina executiva inicial;
- documentacao da consolidacao operacional.

Pendente para as proximas etapas:

- criar filtros compartilhados reais;
- persistir janelas ISE em DuckDB;
- persistir decisoes de pos-operacao em DuckDB;
- criar marts de tendencia dedicados.
