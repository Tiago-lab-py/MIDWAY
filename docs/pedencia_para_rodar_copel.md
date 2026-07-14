# Pendências para rodar o MIDWAY na COPEL

## Objetivo

Registrar tudo que ainda precisa ser resolvido para executar o MIDWAY no ambiente empresarial da COPEL.

O desenvolvimento atual está fora da rede corporativa. Portanto, várias integrações foram simuladas, parametrizadas ou executadas com arquivos locais. Este documento separa o que já existe no projeto daquilo que depende de acesso, credencial, infraestrutura ou validação dentro da empresa.

## Situação atual

- Código, documentação, React, FastAPI, PostgreSQL local e DuckDB local estão em desenvolvimento externo.
- Dados sensíveis, credenciais reais e conexões corporativas não devem ser armazenados no repositório.
- Exportações IQS locais são artefatos de validação técnica e não substituem homologação dentro da COPEL.
- Nomes de conjunto e alimentador estão sendo enriquecidos por arquivos locais em `data/input`.
- A extração oficial de nomes de conjunto/alimentador diretamente do IQS/cadastro empresarial ainda está pendente.

## Pendências críticas

| Área | Pendência | Motivo |
| --- | --- | --- |
| Rede | Executar dentro da rede/VPN COPEL | Necessário para acessar Oracle IQS, bases internas, compartilhamentos e serviços corporativos |
| Oracle IQS | Configurar `IQS_UID`, `IQS_PWD`, `IQS_DB`, `IQS_CONFIG_DIR` | Extrair dados oficiais do IQS |
| Oracle Client | Validar modo thin/thick e `IQS_ORACLE_CLIENT_LIB_DIR` | Evitar falhas de conexão e incompatibilidade de client |
| PostgreSQL | Criar banco/schema corporativo para `MIDWAY_DATABASE_URL` e `MIDWAY_DB_SCHEMA` | Persistir usuários, perfis, decisões, auditoria e geração IQS |
| Segurança | Definir perfis, responsáveis e trilha de auditoria empresarial | Fluxo Analista → Gestor → IQS precisa ser auditável |
| Arquivos oficiais | Definir diretórios corporativos de entrada/saída | Evitar uso de caminhos locais de desenvolvimento |
| Homologação IQS | Testar arquivo final no IQS com lote controlado | Garantir layout, encoding, datas, LF/UNIX e carga correta |

## Variáveis de ambiente a revisar

Base em `.env.example`:

| Variável | Pendência empresarial |
| --- | --- |
| `IQS_UID` | Usuário Oracle/IQS de serviço ou usuário autorizado |
| `IQS_PWD` | Senha/secret externo ao repositório |
| `IQS_DB` | DSN real do IQS |
| `IQS_CONFIG_DIR` | Pasta corporativa de `tnsnames.ora`, se aplicável |
| `IQS_ORACLE_THICK_MODE` | Definir se o ambiente exige modo thick |
| `IQS_ORACLE_CLIENT_LIB_DIR` | Caminho do Instant Client homologado |
| `ANOMES` | Competência oficial de processamento |
| `MIDWAY_DATABASE_URL` | PostgreSQL corporativo |
| `MIDWAY_DB_SCHEMA` | Schema oficial, hoje previsto como `ddcq` |
| `IQS_RAW_DUCKDB_PATH` | Caminho corporativo do DuckDB raw IQS, se usado |
| `IQS_OLD_PROCESSED_PATH` | Base anterior para comparações, quando aplicável |
| `DUCKDB_THREADS` | Ajustar conforme servidor |
| `DUCKDB_MEMORY_LIMIT` | Ajustar conforme servidor |
| `DUCKDB_MAX_TEMP_DIRECTORY_SIZE` | Ajustar conforme volume real |

## Dados e extrações pendentes

### IQS/Oracle

Validar e executar dentro da rede:

- `SQL/IQS_consumidor.sql`;
- `SQL/IQS_uc_fatura.sql`;
- `SQL/IQS_vrc.sql`;
- `SQL/IQS_METAS UC 2026.sql`;
- `SQL/IQS_referencia_componente_causa.sql`;
- `SQL/IQS_DIC_FIC_Liq_Bruto_Mensal.sql`;
- `SQL/IQS_evidencia_volumetria_hcai.sql`;
- `SQL/IQS_evidencia_volumetria_hist_adms.sql`.

### Reclamações e serviços

Validar fonte, acesso e janela de dados:

- `SQL/DBGUO_reclamacoes.sql`;
- extração de serviços ADMS;
- diretórios corporativos de backup/serviços;
- regras de vínculo por UC, ocorrência, alimentador, data e horário.

### Conjunto e alimentador

Uso local atual:

- `data/input/Referencia_DEC FEC CONJUNTO Ano_Copel.csv`;
- `data/input/Referencia_Alimentador_Copel.CSV`.

Pendência empresarial:

- extrair nomes de conjunto diretamente do IQS/cadastro oficial;
- extrair nomes de alimentador diretamente do IQS/cadastro oficial;
- versionar a data/fonte oficial usada;
- substituir ou validar os arquivos locais contra a fonte oficial;
- garantir exibição `código - nome` em todas as telas e exportações de evidência.

## Banco PostgreSQL corporativo

Executar scripts em ambiente controlado:

1. `SQL/postgres/ddcq/001_schema.sql`;
2. `SQL/postgres/ddcq/002_tabelas_operacionais.sql`;
3. `SQL/postgres/ddcq/003_indices.sql`;
4. `SQL/postgres/ddcq/004_seed_parametros.sql`;
5. `SQL/postgres/ddcq/006_governanca.sql`;
6. `SQL/postgres/ddcq/007_iqs_geracao_governada.sql`;
7. `SQL/postgres/ddcq/008_nucleo_anomalias_v7.sql`.

Observação: `005_views_9282.sql` deve ser tratado como suporte histórico/especializado, não como centro do produto.

## Segurança e governança

Pendências:

- definir perfis reais: `ADM`, `GESTOR`, `ANALISTA`, `CONSULTA`, `AUDITOR`;
- definir política de senha/token/sessão;
- definir responsáveis por aprovação de exportação IQS;
- armazenar credenciais em cofre corporativo, não em `.env` versionado;
- revisar logs para não expor dados sensíveis;
- validar trilha de auditoria de decisões humanas;
- exigir justificativa quando a decisão humana divergir da recomendação do algoritmo.

## Validação regulatória

Validar com equipe responsável:

- regras PRODIST Módulo 8 vigentes;
- filtros particulares COPEL;
- cálculo DIC/FIC;
- cálculo DEC/FEC;
- cálculo de compensação/ressarcimento por continuidade;
- exclusões por componente/causa;
- tratamento de faturados versus todos os afetados;
- separação entre visão regulatória e visão cliente/operação.

Referência ativa: `docs/36_regras_prodist_copel.md`.

## Exportação IQS

Antes de qualquer carga real:

- validar layout oficial de colunas;
- validar separador `|`;
- validar encoding `ISO-8859-1`;
- validar quebra de linha UNIX/LF;
- validar datas `dd/mm/aaaa hh:mm:ss`;
- validar inteiros sem decimal;
- validar ausência de colunas extras/faltantes;
- validar pacote único ou por regional;
- testar carga em ambiente controlado/homologação IQS.

Referência ativa: `docs/35_contrato_exportacao_iqs.md`.

## Frontend e operação

Pendências:

- definir URL corporativa da API FastAPI;
- definir autenticação/SSO se aplicável;
- definir servidor para React;
- definir servidor para FastAPI;
- definir se Streamlit continuará disponível como laboratório interno;
- configurar CORS apenas para origens corporativas autorizadas;
- validar performance com volume real;
- validar acesso por perfil.

## Rotina operacional sugerida na COPEL

1. Configurar ambiente e credenciais fora do repositório.
2. Executar scripts PostgreSQL.
3. Extrair bases IQS/ADMS/DBGUO/serviços.
4. Materializar DuckDB raw, silver e gold.
5. Executar módulos regulatórios: DIC/FIC, DEC/FEC e ressarcimento.
6. Executar módulos de anomalia.
7. Revisar cockpit macro.
8. Revisar anomalias por módulo.
9. Registrar decisões humanas governadas.
10. Gerar pacote IQS somente com ajustes aprovados.
11. Homologar carga IQS.
12. Registrar evidências, auditoria e resultado da carga.

## Não fazer fora da rede

- Não armazenar credenciais reais no repositório.
- Não versionar dados sensíveis.
- Não tratar exportação local como carga oficial.
- Não aprovar alteração IQS sem responsável humano.
- Não substituir fonte oficial empresarial por arquivo manual sem registro de origem.
- Não centralizar o produto em `92/82`; esse caso é apenas um módulo especializado.

## Checklist de aceite para rodar na empresa

- [ ] Acesso Oracle/IQS validado.
- [ ] PostgreSQL corporativo criado.
- [ ] Scripts `ddcq` aplicados.
- [ ] Variáveis de ambiente corporativas configuradas.
- [ ] Extrações IQS executadas.
- [ ] Extrações DBGUO/serviços executadas.
- [ ] Nomes de conjunto/alimentador extraídos ou validados contra cadastro oficial.
- [ ] DIC/FIC validado.
- [ ] DEC/FEC validado.
- [ ] Ressarcimento PRODIST validado.
- [ ] Anomalias geradas por módulo.
- [ ] Governança de decisão humana testada.
- [ ] Exportação IQS homologada.
- [ ] Perfis e auditoria revisados.
- [ ] Procedimento operacional aprovado pela equipe COPEL.
