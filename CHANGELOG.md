# Changelog

## 7.1.0 - 2026-07-22

Versão de reestruturação do Motor de Anomalias, centralização da orquestração e adoção de `JSONB`.

- Unifica todos os módulos analíticos legados (`ajuste_inicio_manobra`, `duplicidade_tipo_intrp`, `sobreposicao_uc`, `interrupcao_sem_uc`, `agente_comp_causa`, `suspeita_falha_ra`, `correcao_9282`) para herdar a classe escalável `BaseModulo`.
- Adiciona orquestrador central (`midway.modulos.orquestrador`), que impõe ordem de execução rigorosa das regras operacionais e evita anomalias sistêmicas (ex: sobreposição antes de validação de UC).
- Adota persistência unificada de propostas no PostgreSQL via execução em lote veloz (`execute_values`) gravando na tabela `ddcq.propostas_tratamento`.
- Adota coluna nativa `JSONB` (`evidencias`) no PostgreSQL para centralizar campos analíticos não estruturados, abolindo os joins densos com as tabelas `midway_evidencia` e `midway_sugestao`.
- Elimina mapeamentos isolados de execução do frontend (`EXECUCAO_MODULO_MAP`), introduzindo o acionador nativo "Executar Motor de Anomalias".
- Redesenha o modal `AnomalyDetailModal` do frontend (`App.jsx`) para renderizar dinamicamente os objetos `JSONB` como cards interativos de evidência ao invés de DataTables estáticas.
- Atualiza a rota de aprovação do painel executivo (92/82) para salvar o status "APROVADA" e conciliar justificativas nativamente no Orquestrador.
- Reduz consideravelmente a base de código; a pesada regra original da Correção 92/82, que contava com mais de 1.200 linhas de gerenciamento e manipulação manual, foi reduzida a cerca de 170 linhas de puro processo lógico de negócio (NLP/DuckDB).
## 7.0.0 - 2026-07-11

Versao de transicao arquitetural para React + FastAPI + PostgreSQL `ddcq`, mantendo DuckDB como motor analitico.

- Adiciona frontend React `MIDWAY 7.0.0` com navegação por páginas e visual executivo.
- Adiciona backend FastAPI como fronteira única entre tela, PostgreSQL, DuckDB e exportações.
- Adiciona `inicio.bat` para iniciar PostgreSQL local, API FastAPI e frontend React em fluxo único.
- Cria base PostgreSQL operacional no schema `ddcq` para parâmetros, fila técnica, auditoria, autorização executiva e ajustes IQS.
- Adiciona login local por e-mail com perfis `ADM`, `GESTOR` e `ANALISTA`.
- Adiciona administração de usuários para perfil `ADM`, com inclusão de usuário e senha inicial.
- Adiciona reset de senha governado com código de confirmação de 4 dígitos, expiração, revogação de sessões e monitoramento.
- Implementa governança de alterações: analista propõe, gestor aprova/rejeita e auditoria registra os eventos.
- Implementa geração IQS governada por pacote, com justificativa única para um ou vários modelos.
- Consolida no `Executivo 92/82` o fluxo do `GESTOR`: autorização em massa das alterações e geração do pacote/arquivo de envio ao IQS.
- Adiciona modelos iniciais de geração IQS: sobreposição total, sobreposição parcial, interrupção sem UC remanescente, ajuste 92/82 por reclamação e regra rígida grupo/componente/causa.
- Reorganiza o Dashboard Executivo para exibir `DEC/FEC Antes e Depois das Tratativas` como primeiro bloco após o título.
- Simplifica a navegação principal para quatro áreas: `Dashboard`, `Executivo`, `Análise Técnica` e `Administração`.
- Adiciona na `Análise Técnica` a priorização por impacto com filtros de `CHI`, `CI`, ressarcimento, duração suspeita, `92/82` e violação rígida grupo/componente/causa.
- Adiciona cache materializado `gold_analise_tecnica_impacto_base` para acelerar o ranking da `Análise Técnica`, com comando `run.bat analise_tecnica_cache [ANOMES]`.
- Move o status do banco para indicador compacto ao lado do `ANOMES`.
- Adiciona painel de ajustes de componente/causa para RA `92/82`.
- Adiciona comparação `DEC/FEC` RAW antes das tratativas contra `gold_apuracao_previa` após correções.
- Adiciona abertura de ganhos por tratamento e diagnóstico de filtros RAW, incluindo não faturados, manobra/remanejamento e motivo de tratamento diferenciado.
- Valida o ganho de sobreposição parcial por UC como ganho oficial faturado, separando duração total, ganho faturado e ganho não faturado.
- Substitui a prévia da `Fila Técnica 92/82` no Dashboard por `Busca`.
- Adiciona busca por ocorrência, interrupção ou UC em painéis expansíveis.
- Adiciona endpoint `GET /api/qualidade/busca` para consolidar interrupções, UCs, reclamações, componente/causa, `CHI/CI` e score de reclamação.
- Adiciona pop-up de ocorrência completa com resumo, interrupções distintas, serviços ADMS, apuração UC e reclamações vinculadas.
- Corrige a associação de serviços ADMS por interrupção usando `PID_INTRP_SRVE = NUM_SEQ_INTRP`, evitando repetição indevida por UC.
- Amplia documentação da versão `7.0.0` em `docs/31_plano_aperfeicoamento_telas_governanca.md`, `docs/32_dashboard_executivo_busca_tecnica_7_0_0.md` e `docs/sprint/03_MIDWAY_7_0_0_REACT_FASTAPI.md`.

## 6.2.1 - 2026-07-09

Versao incremental com frontend de qualidade de interrupcoes.

- Adiciona pagina Streamlit `09 Qualidade de Interrupções`.
- Adiciona pagina Streamlit `10 Ajuste Manual IQS` para registrar ajustes aprovados e gerar CSV corrigido.
- Permite ajuste manual de data/hora da ocorrência e exibe evidências coloridas para decisão do analista.
- Cruza interrupcoes IQS/ADMS, reclamacoes DBGUO e servicos ADMS no painel.
- Usa `data/raw/adms_servicos_raw_<ANOMES>.duckdb` como fonte complementar de servicos.
- Classifica interrupcoes por evidencias de improcedencia, atendimento por outra ocorrencia, multiplos servicos e reclamacoes fortes.
- Corrige DIC/FIC da pagina de qualidade para usar `gold_apuracao_uc` como fonte de `CI_LIQUIDO` e `CHI_LIQUIDO`.
- Atualiza README, home e documentacao da avaliacao de qualidade.

## 6.2.0 - 2026-07-09

Versao de integracao IQS/DBGUO e endurecimento das exportacoes operacionais.

- Padroniza os CSVs de exportacao IQS com separador `|`, fim de linha UNIX/LF e codificacao ISO-8859-1 transliterada.
- Garante o layout obrigatorio de exportacao IQS para sobreposicao total por UC, sobreposicao parcial por UC e interrupcao sem UC.
- Adiciona utilitario comum de exportacao em `midway/export/iqs_csv.py` para evitar divergencia entre arquivos gerados.
- Centraliza a extracao DBGUO em `run.bat extrair_dbguo_reclamacoes` e remove BATs soltos obsoletos.
- Mantem a materializacao de reclamacoes DBGUO em `run.bat dbguo_reclamacoes`.
- Adiciona extrator `run.bat extrair_adms_servicos` para gerar `data/raw/adms_servicos_raw_<ANOMES>.duckdb`.
- Limita a extracao e a materializacao DBGUO ao mes de apuracao com margem operacional de dois dias antes/depois.
- Enriquece a analise de reclamacoes com causa provavel, tipo textual, aderencia com causa/componente IQS e previa operacional por reclamacao.
- Documenta a avaliacao de qualidade da interrupcao cruzando IQS/ADMS, reclamacoes DBGUO e servicos ADMS.
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
