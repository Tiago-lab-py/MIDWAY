# Changelog

## 6.1.0 - 2026-07-05

Versao de consolidacao tecnica do MIDWAY.

- Inicia a refatoracao de `midway/apuracao/previa.py` em modulos menores.
- Extrai utilitarios DuckDB/CSV para `midway/apuracao/duckdb_utils.py`.
- Extrai rotinas de impacto por conjunto e dia critico para `midway/apuracao/conjunto.py`.
- Extrai a criacao de `gold_continuidade_uc` para `midway/apuracao/continuidade.py`.
- Extrai a criacao de `gold_ressarcimento_prodist` para `midway/apuracao/ressarcimento.py`.
- Extrai exportacoes de BDO, continuidade e ressarcimento para `midway/apuracao/exportacoes.py`.
- Extrai resumos e anexos de compensacao para `midway/apuracao/resumos.py`.
- Mantem compatibilidade operacional com `run.bat apuracao_parcial`.
- Preserva as regras de negocio existentes, reduzindo risco de quebra durante evolucoes futuras.

## 6.0.1 - 2026-07-05

Versao incremental com melhorias de analytics e apoio operacional.

- Analise diaria de impacto por conjunto eletrico.
- Verificacao de dia critico por conjunto com meta sintetica.
- Simulacao de ISE por janela regional.
- Documentacao das novas analises operacionais.
- Contratos de dados atualizados para as novas tabelas gold.

## 6.0.0 - 2026-07-02

Versao inicial versionada do MIDWAY.

- Fluxo local estabilizado para `ANOMES=202606`.
- Tratamento ADMS/IQS com 4 threads.
- Camadas `raw`, `processed`, `silver` e `gold` organizadas.
- Apuracao previa, continuidade UC e ressarcimento PRODIST.
- Auditorias de sobreposicao, interrupcao/ocorrencia sem UC e qualidade dos dados.
- Painel Streamlit com conferencia ETL, SQL e Analytics Pos-Operacao.
- Testes automatizados de dados tratados.
