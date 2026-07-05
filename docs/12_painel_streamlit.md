# 12 - Painel Streamlit para avaliacao dos resultados

## Objetivo

Facilitar a avaliacao dos resultados do MIDWAY sem depender da leitura manual de CSVs grandes.

O painel consulta diretamente:

```text
data/processed/iqs_adms_processed_<ANOMES>.duckdb
```

E usa os arquivos pequenos de apoio em:

```text
data/marts
```

## Como executar

Instale as dependencias, se necessario:

```bat
pip install -r requirements.txt
```

Abra o painel:

```bat
cd /d D:\MIDWAY
run.bat painel
```

Alternativa direta:

```bat
python -m streamlit run midway\web\streamlit_app.py
```

## Paginas disponiveis

O painel agora possui selecao de pagina no menu lateral:

- `Conferencia ETL`;
- `Analytics Pos-Operacao`.

## Pagina Conferencia ETL

Agrupa as abas de conferencia do fluxo de dados, arquivos e consultas.

## Abas disponiveis na Conferencia ETL

### Qualidade

Mostra o ultimo arquivo:

```text
Metricas_Qualidade_Dados_<ANOMES>_<timestamp>.CSV
```

Inclui:

- total de metricas;
- quantidade de criticos;
- quantidade de alertas;
- resumo TXT;
- filtros por severidade.

### Sobreposicao

Consulta o DuckDB processado e mostra:

- total de sobreposicoes residuais na base liquida;
- amostra priorizada por impacto;
- download da amostra exibida.

A regra respeita:

- mesma UC;
- mesmo `COD_TIPO_INTRP`;
- `CI_LIQUIDO = 1`;
- intervalo temporal sobreposto.

### DIC/FIC

Compara os fechamentos entre:

```text
gold_apuracao_uc
gold_continuidade_uc
gold_apuracao_previa
```

Tambem mostra distribuicao por `COD_TIPO_INTRP` e estatisticas de duracao.

### Ressarcimento

Mostra totais da tabela:

```text
gold_ressarcimento_prodist
```

Inclui:

- UCs avaliadas;
- UCs com compensacao;
- total estimado;
- ranking das maiores compensacoes.

### Conjunto Diario

Mostra a tabela:

```text
gold_impacto_conjunto_dia
```

Objetivo: identificar quais ocorrencias do dia mais consomem a meta `DEC/FEC` de cada conjunto eletrico.

Inclui:

- filtro por dia;
- filtro por conjunto;
- filtro por percentual minimo de meta consumida;
- ranking de ocorrencias por `PCT_META_MAX_CONSUMIDA`;
- resumo por conjunto no dia;
- download do ranking.

Detalhamento:

```text
docs/19_impacto_conjunto_dia.md
```

### Arquivos

Lista arquivos de `data/marts` por competencia e permite pre-visualizar apenas as primeiras linhas de CSVs.

Essa aba evita abrir arquivos muito grandes diretamente no Excel.

### SQL

Permite consultas somente leitura no DuckDB processado.

Inclui:

- catalogo de tabelas com quantidade de linhas e colunas;
- filtro por nome de tabela;
- previa da tabela selecionada;
- lista de colunas/schema;
- resumo numerico das primeiras colunas numericas;
- editor SQL preenchido automaticamente com a tabela selecionada.

Operacoes de escrita como `CREATE`, `DROP`, `INSERT`, `UPDATE`, `DELETE`, `COPY`, `ATTACH` e `ALTER` sao bloqueadas no painel.

## Pagina Analytics Pos-Operacao

Pagina voltada para orientar a verificacao manual pela pos-operacao.

Ela cria um ranking estatistico de ocorrencias provaveis para auditoria usando:

- ocorrencia completa sem UC apuravel;
- interrupcoes sem UC apuravel;
- duracao maior ou igual a 24 horas;
- ocorrencias com mais de um `COD_TIPO_INTRP`;
- ocorrencias com mais de um `TIPO_PROTOC_JUSTIF_UCI`;
- volume de UCs afetadas;
- DIC agregado elevado;
- impacto financeiro estimado em `gold_ressarcimento_prodist`.

Saidas exibidas:

- cards de resumo geral;
- filtro por `Score minimo`;
- ranking de ocorrencias prioritarias;
- motivos da priorizacao;
- download do ranking;
- detalhe das linhas UC/interrupcao da ocorrencia selecionada;
- download do detalhe da ocorrencia.

O score e uma priorizacao operacional para triagem; nao altera dados e nao substitui avaliacao tecnica.

## Fluxo recomendado

Depois de gerar ou atualizar os dados:

```bat
run.bat apuracao_parcial
run.bat metricas_qualidade
run.bat amostras_auditoria
run.bat painel
```

Para atualizar a tela depois de novos processamentos, use o botao:

```text
Limpar cache
```

## Observacoes

- O painel nao substitui os CSVs oficiais; ele e uma camada de avaliacao.
- Consultas pesadas devem ser feitas com filtros e `LIMIT`.
- O processamento continua sendo feito pelo pipeline existente.
