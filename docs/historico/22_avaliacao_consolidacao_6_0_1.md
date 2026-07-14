# 22 - Avaliacao de Consolidacao 6.0.1

## Objetivo

Avaliar a versao atual `6.0.1` do MIDWAY contra os aprendizados dos projetos anteriores:

- `Tiago-lab-py/analise_ocorrencia`;
- `Tiago-lab-py/ADMStoIQS`.

O objetivo nao e copiar os projetos antigos integralmente, mas identificar o que deve ser absorvido para formar uma versao consolidada, estavel e performatica.

## Diagnostico Executivo

A versao `6.0.1` deve ser considerada a base consolidada atual.

Motivos:

- usa processamento local com DuckDB, reduzindo dependencia de banco corporativo para grandes volumes;
- separa camadas `raw`, `silver`, `gold`, `marts` e `export`;
- possui `run.bat` como ponto unico operacional;
- ja executa tratamento, apuracao, ressarcimento, validacao automatizada e painel;
- possui testes automatizados de contratos e regras criticas;
- organiza o conhecimento em documentacao incremental.

Os projetos anteriores devem ser tratados como fontes de aprendizado e componentes conceituais, nao como bases principais de execucao.

## Comparativo

| Projeto | Papel historico | Ponto forte | Limitacao observada | Decisao |
|---|---|---|---|---|
| `analise_ocorrencia` | plataforma ampla de pos-operacao | UX, governanca, login, filtros, validacao e baseline ISE | dependencia de `dbguo` e processamento orientado a pandas/db externo | absorver conceitos, nao o motor |
| `ADMStoIQS` | tentativa anterior focada em ADMS para IQS | aprendizado de fluxo e regras de exportacao | baixa performance e documentacao minima | manter apenas como referencia historica |
| `MIDWAY 6.0.1` | base operacional atual | DuckDB local, testes, ETL e painel integrados | ainda precisa modularizar mais apuracao e persistir decisoes operacionais | evoluir como projeto principal |

## Aprendizados do `analise_ocorrencia`

O `analise_ocorrencia` trouxe ideias importantes:

- separacao entre ETL e interface;
- Streamlit multipage;
- filtros padronizados por competencia, data, conjunto, alimentador, ocorrencia e protocolo;
- governanca de acesso e auditoria;
- validacao de pos-operacao com status e historico;
- dashboard executivo;
- baseline historico para ISE;
- score estatistico para anomalias;
- exportacao amigavel para analistas.

O problema central foi a dependencia do `dbguo` como camada de persistencia e processamento. Para grandes volumes, isso aumentou latencia, risco de falha de carga e dependencia do ambiente corporativo.

### O que absorver

| Item | Absorver? | Forma correta no MIDWAY |
|---|---:|---|
| Filtros padronizados | Sim | criar utilitario de filtros no Streamlit atual |
| Dashboard executivo | Sim | nova pagina `Executivo` lendo DuckDB gold/marts |
| Login/perfis | Parcial | somente quando houver uso multiusuario real |
| Auditoria de acao do usuario | Sim | salvar em DuckDB local, nao em dbguo |
| Validacao pos-operacao | Sim | tabela local `gold_validacao_pos_operacao` ou `mart_validacao_pos` |
| Baseline historico ISE | Sim | calcular em DuckDB por safra historica local |
| Tendencia de falha | Sim | criar mart por componente/causa/equipamento |
| API FastAPI | Nao agora | evitar complexidade antes de necessidade real |
| Persistencia em dbguo | Nao | manter opcional/exportavel, nao motor principal |

## Aprendizados do `ADMStoIQS`

O `ADMStoIQS` serviu como etapa de aprendizado para transformar ADMS em insumo IQS. A principal limitacao informada foi baixa performance.

Como o README publico e minimo, a avaliacao deve ser conservadora:

- nao usar como base principal;
- nao reintroduzir processamento linha-a-linha;
- nao reintroduzir leitura CSV pesada como motor;
- reaproveitar apenas conhecimento de layout, nomes de campos, validacoes manuais e regras que tenham sido comprovadas.

### O que absorver

| Item | Absorver? | Forma correta no MIDWAY |
|---|---:|---|
| Layout IQS e mapeamentos | Sim, se houver diferenca | comparar contra `docs/00_especificacao.md` e exportador atual |
| Regras operacionais anotadas | Sim | migrar para docs e testes |
| Scripts lentos | Nao | substituir por SQL DuckDB vetorizado |
| CSV como base principal | Nao | manter CSV apenas como entrada/saida e amostra |

## Estado Atual do MIDWAY 6.0.1

### Pontos fortes

- DuckDB local como motor principal.
- Processamento em 4 threads configurado.
- Separacao em pacote `midway/`.
- Fluxo operacional claro via `run.bat`.
- Documentacao extensa em `docs/`.
- Testes automatizados em `tests/`.
- Painel Streamlit com:
  - conferencia ETL;
  - SQL somente leitura;
  - analytics pos-operacao;
  - impacto diario por conjunto;
  - dia critico por conjunto;
  - simulacao ISE por janela regional.

### Pontos que ainda precisam consolidar

- `midway/apuracao/previa.py` ainda concentra muitas responsabilidades.
- Validacao pos-operacao ainda e mais analitica do que transacional.
- Janelas ISE ainda sao simuladas, nao persistidas.
- Meta real de dia critico por conjunto ainda nao existe.
- Ressarcimento `DICRI/DISE` ainda precisa evoluir para granularidade por evento.
- Painel Streamlit esta funcional, mas pode virar multipage organizado.

## Proposta de Versao Consolidada

Recomendacao: tratar a consolidacao como uma linha `6.1.x`.

Status em `2026-07-05`: a linha `6.1.0` foi iniciada com a refatoracao segura de `midway/apuracao/previa.py`, extraindo utilitarios e rotinas de conjunto/dia critico para modulos menores.

### 6.1.0 - Consolidacao Operacional

Objetivo: manter o motor DuckDB local e absorver os melhores conceitos do `analise_ocorrencia`.

Escopo recomendado:

1. **Streamlit multipage**
   - `01_Conferencia_ETL`;
   - `02_Analytics_Pos_Operacao`;
   - `03_Dia_Critico`;
   - `04_Simulacao_ISE`;
   - `05_Validacao_Pos_Operacao`;
   - `06_Executivo`;
   - `07_SQL`.

2. **Filtros compartilhados**
   - competencia;
   - data;
   - regional;
   - conjunto;
   - ocorrencia;
   - interrupcao;
   - protocolo;
   - causa;
   - componente.

3. **Cadastro local de janelas ISE**
   - tabela local em DuckDB;
   - campos: regional, inicio, fim, tipo ISE, protocolo, justificativa, usuario, status;
   - status: `SIMULADO`, `APROVADO`, `APLICADO`, `CANCELADO`.

4. **Validacao pos-operacao persistente**
   - salvar decisoes em DuckDB local;
   - registrar usuario, data, decisao, motivo e observacao;
   - permitir exportar CSV de aplicacao.

5. **Dashboard executivo**
   - indicadores de qualidade;
   - top conjuntos por impacto;
   - dias criticos provaveis;
   - janelas ISE simuladas/aprovadas;
   - compensacao estimada.

6. **Marts de tendencia**
   - causa;
   - componente;
   - tipo de equipamento;
   - regional;
   - conjunto.

## Arquitetura Alvo

```text
Oracle IQS / ADMS
  -> DuckDB raw
  -> DuckDB silver
  -> DuckDB gold
  -> DuckDB marts
  -> Streamlit multipage
  -> CSV IQS / relatórios / evidencias
```

Regra de ouro:

```text
Banco corporativo e fonte ou destino.
DuckDB local e motor analitico/processamento.
CSV e interface de troca.
Streamlit e camada de decisao.
```

## O que Nao Reintroduzir

- Dependencia obrigatoria de `dbguo` para processar grandes volumes.
- Persistencia linha-a-linha para tabelas grandes.
- Pandas como motor principal de agregacoes massivas.
- FastAPI antes de existir necessidade clara de uso multiusuario/API.
- Duplicacao de regras entre scripts diferentes.
- Telas que calculam tudo em memoria sem usar DuckDB.

## Plano de Absorcao

### Fase 1 - Baixo risco

- criar filtros compartilhados no Streamlit;
- criar pagina executiva simples;
- documentar equivalencia dos conceitos antigos;
- adicionar testes de contratos das novas marts.

### Fase 2 - Medio risco

- persistir validacao pos-operacao em DuckDB;
- persistir janelas ISE;
- gerar CSV de aplicacao ISE aprovado;
- criar marts de tendencia por causa/componente.

### Fase 3 - Alto impacto

- evoluir ressarcimento `DICRI/DISE` por evento;
- revisar aplicacao oficial de ISE;
- criar modo multiusuario/login se a ferramenta for usada por varias pessoas simultaneamente;
- avaliar integracao opcional com banco corporativo apenas para publicar resultados aprovados.

## Conclusao

A consolidacao deve partir do MIDWAY `6.0.1`.

O `analise_ocorrencia` deve contribuir com:

- experiencia de uso;
- filtros;
- governanca;
- validacao pos-operacao;
- dashboard executivo;
- baseline ISE e tendencias.

O `ADMStoIQS` deve contribuir apenas com memoria de regras e layout, se houver algo ainda nao migrado.

A decisao tecnica principal e manter o DuckDB local como motor, evitando repetir os gargalos ja observados em `dbguo`, pandas pesado e leitura CSV como base principal.
