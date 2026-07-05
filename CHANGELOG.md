# Changelog

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
