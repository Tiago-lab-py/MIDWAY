# Changelog

## 6.2.0 - 2026-07-09

Versao de integracao IQS/DBGUO e endurecimento das exportacoes operacionais.

- Padroniza os CSVs de exportacao IQS com separador `|`, fim de linha UNIX/LF e codificacao ISO-8859-1 transliterada.
- Garante o layout obrigatorio de exportacao IQS para sobreposicao total por UC, sobreposicao parcial por UC e interrupcao sem UC.
- Adiciona utilitario comum de exportacao em `midway/export/iqs_csv.py` para evitar divergencia entre arquivos gerados.
- Centraliza a extracao DBGUO em `run.bat extrair_dbguo_reclamacoes` e remove BATs soltos obsoletos.
- Mantem a materializacao de reclamacoes DBGUO em `run.bat dbguo_reclamacoes`.
- Limita a extracao e a materializacao DBGUO ao mes de apuracao com margem operacional de dois dias antes/depois.
- Enriquece a analise de reclamacoes com causa provavel, tipo textual, aderencia com causa/componente IQS e previa operacional por reclamacao.
- Adiciona ranking de ocorrencias com reclamacoes no painel Streamlit.
- Versiona os dicionarios em `data/input` para evitar falhas por ausencia de `causa.csv`, `componente.csv` e listas auxiliares.
- Atualiza a documentacao tecnica das exportacoes IQS, extracao DBGUO e avaliacao de reclamacoes.

## 6.1.0 - 2026-07-05

Versao de consolidacao tecnica do MIDWAY.

- Inicia a refatoracao de `midway/apuracao/previa.py` em modulos menores.
- Extrai utilitarios DuckDB/CSV para `midway/apuracao/duckdb_utils.py`.
- Extrai rotinas de impacto por conjunto e dia critico para `midway/apuracao/conjunto.py`.
- Extrai a criacao de `gold_continuidade_uc` para `midway/apuracao/continuidade.py`.
- Extrai a criacao de `gold_ressarcimento_prodist` para `midway/apuracao/ressarcimento.py`.
- Extrai exportacoes de BDO, continuidade e ressarcimento para `midway/apuracao/exportacoes.py`.
- Extrai resumos e anexos de compensacao para `midway/apuracao/resumos.py`.
- Extrai a criacao de `gold_interrupcao_tratada` para `midway/apuracao/interrupcao_tratada.py`.
- Extrai a base apuravel por UC para `midway/apuracao/apuracao_uc.py`.
- Extrai a criacao de `gold_apuracao_previa` para `midway/apuracao/apuracao_previa.py`.
- Move funcoes obsoletas para `midway/apuracao/legacy.py`.
- Centraliza `ANOMES`, paths e timestamp em `midway/apuracao/contexto.py`.
- Reorganiza o painel Streamlit em `home.py`, `pages/` e `library/`.
- Adiciona paginas iniciais de validacao pos-operacao e dashboard executivo.
- Adiciona graficos executivos interativos de DEC/FEC COPEL e conjuntos com visao diaria, acumulada diaria e mensal.
- Adiciona graficos de compensacao financeira e participacao provavel/tratar.
- Corrige compensacao executiva para somar cada UC compensada uma unica vez.
- Documenta a arquitetura operacional alvo em `docs/24_consolidacao_operacional_6_1_0.md`.
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
