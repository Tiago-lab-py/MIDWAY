# Sprint 01 - Teste de Extracao no Computador da Empresa

Data prevista: `2026-07-03`

## Objetivo

Validar o MIDWAY no computador da empresa, com foco em:

- preparar ambiente local;
- clonar a versao `6.0.1`;
- configurar acesso Oracle/IQS;
- executar e conferir as extracoes ADMS e IQS;
- gerar base processada inicial;
- validar se os dados extraidos permitem tratamento, apuracao e conferencia pelo painel.

## Resultado Esperado

Ao final do sprint, deve existir um ambiente funcional na empresa com:

```text
data/raw/iqs_adms_raw_<ANOMES>.duckdb
data/raw/iqs_raw_<ANOMES>.duckdb
data/processed/iqs_adms_processed_<ANOMES>.duckdb
data/marts/
data/export/
```

E os comandos principais devem executar sem erro:

```bat
run.bat extract
run.bat consumidores
run.bat uc_fatura
run.bat vrc
run.bat metas_uc
run.bat reprocessar
run.bat apuracao_parcial
run.bat validar_dados
run.bat painel
```

## Escopo

### Dentro do sprint

- Validar instalacao do Python e dependencias.
- Validar clone do GitHub.
- Criar `.env` com credenciais reais no computador da empresa.
- Testar conexao Oracle por meio das rotinas de extracao.
- Executar extracao ADMS principal.
- Executar extracoes auxiliares IQS:
  - consumidores;
  - UC faturada;
  - VRC;
  - metas UC.
- Conferir tabelas RAW criadas.
- Rodar tratamento, apuracao parcial e testes automatizados.
- Abrir painel Streamlit para conferencia visual.

### Fora do sprint

- Ajustes profundos de regra de negocio.
- Refatoracao grande de codigo.
- Alteracao estrutural de banco.
- Envio oficial dos CSVs ao IQS.
- Correcao manual massiva de ocorrencias.

## Pre-requisitos

### Acesso

- Usuario GitHub com acesso ao repositorio:

```text
https://github.com/Tiago-lab-py/MIDWAY.git
```

- Usuario, senha e DSN Oracle/IQS.
- Permissao de rede para conectar ao banco Oracle.
- Permissao de escrita na pasta local do projeto.

### Software

- Git instalado.
- Python 3.11 ou superior.
- CMD ou PowerShell.
- Navegador para o Streamlit.
- Opcional: DBeaver para inspecao do DuckDB.

### Recursos de maquina

Minimo recomendado:

- 16 GB RAM;
- 80 GB livres para temporarios e DuckDB;
- SSD preferencialmente;
- nenhum DuckDB aberto no DBeaver durante processamento.

## Preparacao Inicial

Escolher uma pasta local, por exemplo:

```bat
cd /d D:\
git clone https://github.com/Tiago-lab-py/MIDWAY.git
cd MIDWAY
```

Conferir versao:

```bat
run.bat versao
```

Instalar dependencias:

```bat
pip install -r requirements.txt
```

Criar `.env` na raiz do projeto:

```env
IQS_UID=usuario_real
IQS_PWD=senha_real
IQS_DB=dsn_real
IQS_CONFIG_DIR=C:\oracle\network\admin
ANOMES=202606
```

Se o Oracle exigir Instant Client:

```env
IQS_ORACLE_THICK_MODE=1
IQS_ORACLE_CLIENT_LIB_DIR=C:\oracle\instantclient_21_13
```

## Roteiro do Dia

### 08:30 - Preparar ambiente

Comandos:

```bat
cd /d D:\MIDWAY
run.bat versao
run.bat
```

Checklist:

- `run.bat versao` retorna `6.0.1`.
- `run.bat` lista comandos.
- `.env` existe e nao esta no Git.
- `data/` sera criada localmente.

### 09:00 - Validar extracao ADMS

Comandos:

```bat
set ANOMES=202606
set REEXTRAIR=1
run.bat extract
```

Conferir saida:

```text
data/raw/iqs_adms_raw_202606.duckdb
data/control/extract_202606.done.json
data/logs/
```

Conferencia minima:

```bat
python -c "import duckdb; con=duckdb.connect('data/raw/iqs_adms_raw_202606.duckdb', read_only=True); print(con.execute('select count(*) from hiadms_raw').fetchall()); con.close()"
```

Critério de aceite:

- DuckDB bruto criado.
- Tabela `hiadms_raw` existe.
- Quantidade de registros maior que zero.
- Controle `extract_<ANOMES>.done.json` criado.

### 10:00 - Validar extracoes IQS auxiliares

Comandos:

```bat
run.bat consumidores
run.bat uc_fatura
run.bat vrc
run.bat metas_uc
```

Conferir saida:

```text
data/raw/iqs_raw_202606.duckdb
```

Tabelas esperadas:

```text
raw_iqs_consumidores
raw_iqs_uc_fatura
raw_iqs_vrc
raw_iqs_metas_uc
```

Conferencia minima:

```bat
python -c "import duckdb; con=duckdb.connect('data/raw/iqs_raw_202606.duckdb', read_only=True); print(con.execute('show tables').fetchall()); con.close()"
```

Critério de aceite:

- DuckDB `iqs_raw_<ANOMES>.duckdb` criado.
- Tabelas RAW IQS existem.
- Pelo menos consumidores e UC fatura possuem registros.
- VRC e metas UC executam ou registram claramente erro de acesso/volume.

### 11:30 - Tratamento principal

Comandos:

```bat
set REPROCESSAR=1
run.bat reprocessar
```

Conferir saida:

```text
data/processed/iqs_adms_processed_202606.duckdb
data/export/
data/marts/
```

Critério de aceite:

- Banco processado criado.
- Tabela de exportacao IQS criada.
- CSVs por regional gerados ou auditoria bloqueante explicada.
- Nao ha erro de lock pendente.

### 13:30 - Apuracao parcial

Comando:

```bat
run.bat apuracao_parcial
```

Tabelas esperadas:

```text
gold_interrupcao_tratada
gold_apuracao_uc
gold_continuidade_uc
gold_ressarcimento_prodist
gold_interrupcao_sem_uc
gold_ocorrencia_sem_uc
```

Conferencia minima:

```bat
python -c "import duckdb; con=duckdb.connect('data/processed/iqs_adms_processed_202606.duckdb', read_only=True); print(con.execute('select count(1), sum(CI_LIQUIDO), sum(CHI_LIQUIDO) from gold_apuracao_uc').fetchall()); print(con.execute('select count(1), sum(FIC), sum(DIC) from gold_continuidade_uc').fetchall()); con.close()"
```

Critério de aceite:

- Camadas gold criadas.
- Soma de `CI_LIQUIDO` confere com `FIC`.
- Soma de `CHI_LIQUIDO` confere com `DIC`, respeitando pequenas diferencas de ponto flutuante.
- Auditorias sem UC geradas em `data/marts`.

### 14:30 - Validacao automatizada

Comando:

```bat
run.bat validar_dados
```

Critério de aceite:

- Testes automatizados passam.
- Metricas de qualidade sao geradas em `data/marts`.
- Criticos, se existirem, ficam listados no resumo de metricas.

### 15:00 - Painel Streamlit

Comando:

```bat
run.bat painel
```

Checklist no painel:

- Pagina `Conferencia ETL` abre.
- Aba `Qualidade` carrega metricas.
- Aba `Sobreposicao` carrega amostras.
- Aba `DIC/FIC` mostra totais.
- Aba `Ressarcimento` carrega `gold_ressarcimento_prodist`.
- Aba `Arquivos` lista `data/raw`, `data/processed`, `data/marts` e `data/export`.
- Aba `SQL` lista tabelas e permite consulta.
- Pagina `Analytics Pos-Operacao` gera ranking de ocorrencias para verificacao.

## Checklist de Evidencias

Registrar no fim do sprint:

| Item | Status | Evidencia |
| --- | --- | --- |
| Clone do GitHub realizado |  |  |
| `.env` criado localmente |  |  |
| `run.bat versao` OK |  |  |
| Dependencias instaladas |  |  |
| Extracao ADMS OK |  |  |
| Extracao consumidores OK |  |  |
| Extracao UC fatura OK |  |  |
| Extracao VRC OK |  |  |
| Extracao metas UC OK |  |  |
| Tratamento OK |  |  |
| Apuracao parcial OK |  |  |
| Testes automatizados OK |  |  |
| Painel Streamlit OK |  |  |
| `data/` fora do Git |  |  |

## Validacoes SQL Rapidas

### Listar tabelas do processado

```bat
python -c "import duckdb; con=duckdb.connect('data/processed/iqs_adms_processed_202606.duckdb', read_only=True); print(con.execute('show tables').fetchall()); con.close()"
```

### Conferir continuidade

```bat
python -c "import duckdb; con=duckdb.connect('data/processed/iqs_adms_processed_202606.duckdb', read_only=True); print(con.execute('select count(1), sum(FIC), sum(DIC), max(DMIC) from gold_continuidade_uc').fetchall()); con.close()"
```

### Conferir ressarcimento

```bat
python -c "import duckdb; con=duckdb.connect('data/processed/iqs_adms_processed_202606.duckdb', read_only=True); print(con.execute('select count(1), sum(COMP_GERAL) from gold_ressarcimento_prodist').fetchall()); con.close()"
```

### Conferir interrupcoes sem UC

```bat
python -c "import duckdb; con=duckdb.connect('data/processed/iqs_adms_processed_202606.duckdb', read_only=True); print(con.execute('select count(1) from gold_interrupcao_sem_uc').fetchall()); print(con.execute('select count(1), sum(case when OCORRENCIA_COMPLETA_SEM_UC then 1 else 0 end) from gold_ocorrencia_sem_uc').fetchall()); con.close()"
```

## Riscos e Plano de Contorno

| Risco | Sinal | Plano de contorno |
| --- | --- | --- |
| Sem acesso Oracle | Erro de conexao no `extract` | Validar DSN, VPN, `tnsnames.ora`, usuario e senha |
| Instant Client ausente | Erro de client Oracle | Usar modo thin ou configurar `IQS_ORACLE_THICK_MODE=1` |
| Dependencia Python ausente | `ModuleNotFoundError` | Rodar `pip install -r requirements.txt` |
| DuckDB bloqueado | Erro de arquivo em uso | Fechar DBeaver, Streamlit e outros processos |
| Lock pendente | Erro `.lock` em `data/control` | Confirmar que nao ha processo rodando e remover lock |
| Processamento lento | Uso alto de memoria/disco | Manter `threads=4`, fechar apps e rodar por etapas |
| VRC/metas muito pesados | Demora excessiva | Registrar tempo, validar filtros e rodar fora do horario critico |

## Decisoes Esperadas ao Final

- O computador da empresa esta apto para executar o MIDWAY?
- O acesso Oracle permite todas as extracoes necessarias?
- As tabelas RAW IQS vieram com layout esperado?
- O tratamento gerou CSVs sem bloqueio?
- A apuracao parcial gerou DIC/FIC e ressarcimento coerentes?
- Ha ocorrencias prioritarias para verificacao pela pos-operacao?
- O painel Streamlit atende a conferencia inicial?

## Saida do Sprint

Entregar:

- print ou anotacao do `run.bat versao`;
- contagens das tabelas principais;
- lista de arquivos gerados em `data/marts`;
- resultado do `run.bat validar_dados`;
- pendencias tecnicas encontradas;
- decisao: `aprovado`, `aprovado com ressalvas` ou `bloqueado`.
