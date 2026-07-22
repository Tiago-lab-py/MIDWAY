# Status da Aplicação para Migração Cloud (GCP / DBGUO)

Este documento centraliza o estado atual do MIDWAY versão 7.x, documentando todos os módulos e infraestruturas que já estão **100% prontos** para implantação na nuvem (GCP) ou no ambiente empresarial on-premise da Copel.

## 1. Arquitetura e Orquestração (ETL e Anomalias)
Todo o acionamento do sistema foi desacoplado de dependências frágeis (como `.bat` do Windows) e unificado em orquestradores Python nativos, tornando-os totalmente compatíveis com contêineres Docker, Kubernetes (GKE) ou Cloud Composer (Airflow).

*   **ETL Unificado (`midway/pipeline/etl.py`)**: Centraliza as fases de Extração (ADMS), Tratamento de Tipos e Apuração Prévia (DuckDB).
*   **Orquestrador de Anomalias (`midway/modulos/orquestrador.py`)**: Centraliza a chamada de todas as regras regulatórias em lote e persiste os resultados de forma otimizada.

## 2. Algoritmos Analíticos (Migrados para `BaseModulo`)
Todos os scripts legados do Streamlit foram refatorados para um design pattern moderno. Estão ativos e gerando as propostas de tratamento via JSONB:

1.  **Duração Negativa** (`duracao_negativa.py`)
2.  **Sobreposição de UC** (`sobreposicao_uc.py`)
3.  **Ajuste de Início de Manobra** (`ajuste_inicio_manobra.py`)
4.  **Duplicidade de Tipo de Interrupção** (`duplicidade_tipo_intrp.py`)
5.  **Interrupção sem UC** (`interrupcao_sem_uc.py`)
6.  **Agente, Componente e Causa** (`agente_comp_causa.py`)
7.  **Suspeita de Falha RA** (`suspeita_falha_ra.py`)
8.  **Duração e Impacto** (`duracao_impacto.py`)
9.  **Ressarcimento Atípico** (`ressarcimento_atipico.py`)
10. **Reclamações vs Serviços** (`reclamacoes_servicos.py`)
11. **Dia Crítico ISE** (`dia_critico_ise.py`)
12. **Correção 92/82** (`correcao_9282.py`) - Agora unificado no orquestrador central.

## 3. Banco de Dados e API
A transição do armazenamento estático (arquivos) para o armazenamento relacional de transações está concluída.

*   **FastAPI** (`midway/api/`): API REST pronta para ser hospedada (Cloud Run ou GKE), expondo rotas protegidas (CORS) para consumo do Frontend.
*   **PostgreSQL**:
    *   Arquitetura de tabelas operacionais finalizada (Schema `ddcq`).
    *   Tabela central `ddcq.midway_propostas_tratamento` capaz de armazenar qualquer contexto de anomalia usando a coluna `evidencias_json` (JSONB).

## 4. Frontend (React)
A interface unificada (`midway-frontend`) em React está operacional, rodando via Vite, conectada à FastAPI e preparada para realizar aprovações de governança em massa (Tratativas de Governança).

---
## O que falta (Próximos Passos para Produção)

*   **Exportador IQS Final**: Finalizar a rotina que consulta as anomalias aprovadas na base PostgreSQL e gera o `.txt`/`.csv` final validado.
*   **Acessos Reais (Credenciais)**: Substituir as chaves e caminhos simulados no `.env` pelas credenciais reais de banco (GCP Cloud SQL ou DBGUO on-premise) e diretórios (Cloud Storage).
