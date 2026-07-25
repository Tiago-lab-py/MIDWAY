# Implantação MIDWAY - COPEL (GCP & DBGUO)

## Objetivo
Preparar o MIDWAY para rodar de forma escalável e nativa em nuvem (Google Cloud Platform - GCP), mantendo a governança no banco de dados DBGUO (PostgreSQL / Cloud SQL) utilizando o schema `ddcq`. 

O objetivo é evitar dependências locais de disco (armazenamento efêmero) e unificar as regras corporativas em torno dos serviços de nuvem da Copel.

---

## 1. Arquitetura Alvo no GCP

O MIDWAY possui três camadas lógicas que devem ser mapeadas para componentes do GCP:

| Camada | Componente GCP Recomendado | Responsabilidade |
| --- | --- | --- |
| **API Backend (Python/FastAPI)** | **Cloud Run** ou **GKE** (Google Kubernetes Engine) | Recebe requisições HTTP, orquestra tratamento DuckDB (em memória/disco temporário) e consolida regras. |
| **Frontend (React/Vite)** | **Cloud Storage** (Static Web Hosting) ou **Cloud Run** | Interface de usuário (SPA). |
| **Governança Operacional** | **Cloud SQL (PostgreSQL)** | Armazenar perfis, usuários, configurações de orquestração, trilhas de auditoria, histórico de decisões (Schema `ddcq`). |
| **Armazenamento Analítico / IQS** | **Cloud Storage (GCS Bucket)** | Substitui os diretórios locais `data/marts` e `data/export`. Hospeda arquivos massivos de RAW, processos DuckDB e pacotes ZIP finais para IQS. |

---

## 2. Variáveis de Ambiente e Cofre de Senhas

As variáveis não devem estar soltas em arquivos `.env` no repositório. Devemos utilizar o **Secret Manager** do GCP.

```env
# Ambiente e Banco de Dados DBGUO
MIDWAY_ENV=gcp
MIDWAY_DATABASE_URL=postgresql://<usuario>:<senha>@<host_cloud_sql>:5432/<database>
MIDWAY_DB_SCHEMA=ddcq
ANOMES=202606

# Armazenamento (Google Cloud Storage)
MIDWAY_STORAGE_BUCKET=copel-midway-iqs-export
GOOGLE_APPLICATION_CREDENTIALS=/app/secrets/gcp-sa-key.json
```

*(Conexões diretas Oracle/IQS, caso sejam feitas online, deverão possuir credenciais geridas de forma análoga pelo Secret Manager)*.

---

## 3. Estrutura de Banco de Dados (DBGUO / DDCQ)

Os scripts essenciais do produto para inicializar o Cloud SQL (PostgreSQL) estão em `SQL/postgres/ddcq/` e devem ser rodados em sequência pelo DBA Copel:

1. `001_schema.sql`
2. `002_tabelas_operacionais.sql`
3. `003_indices.sql`
4. `004_seed_parametros.sql`
5. `006_governanca.sql`
6. `007_iqs_geracao_governada.sql`
7. `008_nucleo_anomalias_v7.sql`

O banco é acessado **exclusivamente via API (FastAPI)**. O Frontend React *não* se comunica com o Postgres, operando de forma isolada pela API por segurança corporativa.

---

## 4. Exportação Cloud-Ready (Arquivos IQS)

No modelo local legado, o MIDWAY gerava vários `.csv` e `.txt` espalhados pelas pastas `marts/` e `export/`.
**No GCP, esse comportamento é modificado:**

- O processamento de anomalias roda via API / Orquestrador.
- Quando o **Gestor APROVA** uma geração IQS na interface, a API agrupa os módulos aprovados.
- Um processo dinâmico no backend gera o arquivo único do layout IQS na memória/pasta efêmera, empacota num arquivo `.zip` com log de auditoria, e disponibiliza a URL para **Download**, ou faz o push direto para o **Cloud Storage (Bucket)**.
- Essa abordagem resolve a fragilidade dos contêineres e elimina lixo deixado no disco do servidor.

---

## 5. Homologação IQS e Validação de Pacote

Antes de qualquer carga no IQS produtivo:
- O arquivo `.zip` exportado pela API deve ser validado.
- Encoding oficial exigido: `ISO-8859-1`.
- Quebra de linha oficial: `UNIX (LF)`.
- Separador oficial: `|`.
- Validar as regras vigentes do PRODIST (Módulo 8) aplicadas à COPEL.

---

## 6. Segurança e Rede

- **VPC e Firewall:** Garantir que o Cloud Run/GKE tenha peering ou conexão via VPC Serverless Access com a rede corporativa da Copel onde reside o IQS (Oracle) e o Cloud SQL.
- **CORS:** Configurar o backend FastAPI para aceitar requisições unicamente do domínio oficial onde o painel React será hospedado.
- **Auditoria:** Toda aprovação, envio e exportação de arquivo registra uma trilha no `ddcq.midway_iqs_geracao` vinculando o e-mail ou UUID corporativo do analista logado.

---

## Checklist de Aceite GCP

- [ ] Instância de Cloud SQL provisionada e tabelas do `ddcq` criadas.
- [ ] Bucket de Storage criado e acessível pelo backend.
- [ ] Segredos configurados no GCP Secret Manager.
- [ ] API backend operante sem erros de permissão de escrita de exportação.
- [ ] Interface Frontend rodando e comunicando via CORS permitido.
- [ ] Primeira exportação IQS gerada via painel baixada via ZIP/GCS e testada com sucesso.
