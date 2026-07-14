# 09 - Proposta de melhoria do projeto MIDWAY

Versao base registrada: `6.0.0`.

## Situacao atual

Em 2026-07-02, o projeto foi estabilizado para execucao local neste computador, sem acesso direto ao Oracle, usando os DuckDBs preservados em disco.

O fluxo completo foi validado para `ANOMES=202606`:

```text
RAW ADMS preservado
  -> tratamento
  -> exportacao oficial IQS
  -> exportacoes auxiliares
  -> sincronizacao IQS raw
  -> apuracao parcial
  -> BDO e camadas gold
```

## Organizacao atual dos dados

### Camada raw

Arquivos em `data/raw`:

```text
data/raw/iqs_adms_raw_202605.duckdb
data/raw/iqs_adms_raw_202606.duckdb
data/raw/iqs_raw_202606.duckdb
```

Papeis:

- `iqs_adms_raw_<ANOMES>.duckdb`: RAW principal ADMS/HIADMS, com tabela `hiadms_raw`.
- `iqs_raw_<ANOMES>.duckdb`: extracoes auxiliares do IQS usadas pela apuracao.

Tabelas em `iqs_raw_202606.duckdb`:

```text
raw_iqs_consumidores
raw_iqs_uc_fatura
raw_iqs_vrc
raw_iqs_metas_uc
```

### Camada processed

Arquivo principal:

```text
data/processed/iqs_adms_processed_202606.duckdb
```

Tabelas principais validadas:

| Tabela | Linhas |
| --- | ---: |
| `adms_iqs_alterados` | 464.628 |
| `adms_iqs_export` | 464.628 |
| `silver_iqs_consumidores` | sincronizado de `raw_iqs_consumidores` |
| `silver_iqs_uc_fatura` | sincronizado de `raw_iqs_uc_fatura` |
| `silver_iqs_vrc` | sincronizado de `raw_iqs_vrc` |
| `silver_iqs_metas_uc` | sincronizado de `raw_iqs_metas_uc` |
| `gold_consumidores` | 6 |
| `gold_uc_fatura` | 3.038.822 |
| `gold_vrc` | 5.455.688 |
| `gold_metas_uc` | 5.455.183 |
| `silver_interrupcao_tratada` | copia canonica da interrupcao tratada |
| `silver_interrupcao_uc_apuravel` | base canonica UC/interrupcao para DEC/FEC e DIC/FIC |
| `gold_apuracao_uc` | 9.390.187 |
| `gold_continuidade_uc` | 2.507.726 |
| `gold_apuracao_previa` | 369.317 |

As tabelas `gold_consumidores`, `gold_uc_fatura`, `gold_vrc` e `gold_metas_uc` sao materializadas no `processed` por compatibilidade com a apuracao, mas a camada canonica e `silver_iqs_*` e a origem oficial local delas e o arquivo:

```text
data/raw/iqs_raw_202606.duckdb
```

## Melhorias ja concluidas

### Recuperacao local

- Atualizado `duckdb` para versao compativel com os arquivos locais.
- Instaladas dependencias ausentes: `polars` e `oracledb`.
- Criado `requirements.txt` com versoes usadas neste computador.
- Criado `.env.example`.
- Configurado `DUCKDB_THREADS=4`.
- Configurado `IQS_RAW_DUCKDB_PATH=data\raw\iqs_raw_202606.duckdb`.

### Tratamento

- `run.bat reprocessar` executou com sucesso.
- Exportacao oficial IQS gerada com `464.628` registros alterados.
- Exportacoes auxiliares geradas:
  - `sobreposicao_total_uc`;
  - `sobreposicao_UC_parcial`;
  - `interrupcao_sem_uc`.
- Removida carga desnecessaria da regra legada de sobreposicao total por equipamento, que ja estava neutralizada no negocio.

### IQS raw

- Criada camada `data/raw/iqs_raw_<ANOMES>.duckdb`.
- Ajustados os extratores auxiliares para gravar primeiro em `raw_iqs_*`.
- Criado sincronizador:

```bat
run.bat sincronizar_iqs_raw
```

Esse comando materializa no `processed`:

```text
silver_iqs_consumidores
silver_iqs_uc_fatura
silver_iqs_vrc
silver_iqs_metas_uc
gold_consumidores
gold_uc_fatura
gold_vrc
gold_metas_uc
```

### Camada silver e filtro de sobreposicao

- Criadas tabelas `silver_iqs_*` para as extracoes auxiliares do IQS.
- Criada tabela `silver_interrupcao_tratada` como base tratada granular.
- Criada tabela `silver_interrupcao_uc_apuravel` como base canonica de UC/interrupcao.
- Mantida `gold_apuracao_uc` como tabela de compatibilidade gerada a partir de `silver_interrupcao_uc_apuravel`.
- Corrigida a regra de `NUM_MOTIVO_TRAT_DIF_UCI` na apuracao: somente registros com motivo nulo entram em DEC/FEC liquido e DIC/FIC.
- Registros com qualquer codigo de tratamento diferenciado em `NUM_MOTIVO_TRAT_DIF_UCI` deixam de seguir para a base apuravel.

### Teste local com arquivo old

Para viabilizar execucao local sem Oracle, foi criado:

```text
tools/copiar_iqs_raw_do_old.py
```

Ele copia as tabelas `gold_*` do arquivo:

```text
data/processed/iqs_adms_processed_202606_old.duckdb
```

para:

```text
data/raw/iqs_raw_202606.duckdb
```

como tabelas `raw_iqs_*`.

### Refatoracao incremental

- Organizada a raiz do projeto com chamadas oficiais via `run.bat` e modulos `python -m`.
- Movidos extratores para `midway/extract/`.
- Movidas auditorias/exportacoes auxiliares para `midway/auditoria/`.
- Movidos utilitarios de transformacao para `midway/transform/`.
- Movidos `exportar.py`, `controle_execucao.py`, `tratamento.py`, `apuracao_previa.py` e painel Streamlit para `midway/`.
- Extraida a auditoria de interrupcao/ocorrencia sem UC para `midway/apuracao/auditoria_sem_uc.py`.
- `apuracao_previa.py` passou a ser executado como `midway.apuracao.previa`.
- Eliminadas redefinicoes silenciosas em `tratamento.py` para:
  - `montar_select_exportacao_iqs`;
  - `consultar_exportacao_iqs_regional`.
- As versoes antigas foram marcadas como `_obsoleto_*` para reduzir risco durante a transicao.
- Nao permanecem scripts Python operacionais na raiz; os arquivos grandes agora estao dentro do pacote.

### Compensacao previa

- Ajustada a base financeira de compensacao para desconsiderar eventos com `COD_COMP_INTRP = '52'`, independentemente da causa.
- Ajustada a base financeira de compensacao para desconsiderar eventos com `INDIC_PROPR_POSTO_INTRP = 'P'`.
- Mantidos `DIC`, `FIC` e `DMIC` realizados para conferencia contra DEC/FEC.
- Mantidos `DIC_BASE_COMPENSACAO`, `FIC_BASE_COMPENSACAO` e `DMIC_BASE_COMPENSACAO` como bases financeiras, podendo ser menores que os indicadores realizados.
- Criadas flags de auditoria:
  - `COMP52`;
  - `POSTO_PARTICULAR`;
  - `COMP52_CAUSA71` como marcador complementar historico.
- Ajustado o painel Streamlit para separar o ranking de compensacoes entre:
  - UCs sem eventos excluidos;
  - todas as UCs;
  - somente UCs com eventos excluidos.

### Painel Analytics

- Criada navegacao no Streamlit por pagina:
  - `Conferencia ETL`;
  - `Analytics Pos-Operacao`.
- A pagina `Analytics Pos-Operacao` lista ocorrencias provaveis para verificacao manual pela pos-operacao.
- O ranking usa score baseado em:
  - ocorrencia/interrupcao sem UC apuravel;
  - duracao maior ou igual a 24 horas;
  - multiplos `COD_TIPO_INTRP`;
  - multiplos `TIPO_PROTOC_JUSTIF_UCI`;
  - volume de UCs;
  - DIC agregado;
  - impacto financeiro estimado.
- A aba SQL da conferencia ETL recebeu catalogo de tabelas, schema, previa e resumo numerico.

### Apuracao parcial

- `run.bat apuracao_parcial` executou com sucesso.
- Gerado arquivo:

```text
data/export/BDO_interupcao_20260702.csv
```

- Geradas conferencias:

```text
data/marts/Apuracao_Previa_<timestamp>_RESUMO.TXT
data/marts/Gold_Continuidade_UC_202606_<timestamp>.CSV
data/marts/Gold_Continuidade_UC_202606_<timestamp>_RESUMO.TXT
data/marts/Auditoria_Interrupcao_Sem_UC_202606_<timestamp>.CSV
data/marts/Auditoria_Interrupcao_Sem_UC_202606_<timestamp>_RESUMO.TXT
```

## Diagnostico da apuracao e ressarcimento

### Objetivo funcional do MIDWAY

O programa deve atuar como middleware entre ADMS e IQS:

1. ler o RAW ADMS/HIADMS sem destruir a origem;
2. tratar inconsistencias operacionais, principalmente sobreposicao temporal por UC;
3. gerar arquivo de alteracoes para o IQS;
4. montar uma base previa confiavel para DEC/FEC e continuidade individual;
5. permitir conferencia previa de DIC/FIC/DMIC e ressarcimentos antes do fechamento oficial.

O ponto central e que uma UC nao pode ser contada duas vezes em intervalos temporais sobrepostos. A regra de sobreposicao deve respeitar `COD_TIPO_INTRP`, ou seja, nao deve misturar eventos de tipos diferentes para classificar uma UC como sobreposta.

### Resultado da comparacao DEC/FEC x DIC/FIC

No arquivo local `data/processed/iqs_adms_processed_202606.duckdb`, os indicadores realizados estao saindo da mesma base de eventos por UC:

| Conferencia | CHI/DIC | CI/FIC |
| --- | ---: | ---: |
| `gold_apuracao_previa` - `CHI_LIQUIDO` / `CI_LIQUIDO` | 2.991.079,438333 | 1.693.476 |
| `gold_apuracao_uc` - `CHI_LIQUIDO` / `CI_LIQUIDO` | 2.991.079,438333 | 1.693.476 |
| `gold_continuidade_uc` - `DIC` / `FIC` | 2.991.079,438333 | 1.693.476 |

Conclusao: o DIC/FIC realizado esta coerente com o DEC/FEC liquido, porque ambos derivam de `gold_apuracao_uc`.

A diferenca aparece na base de compensacao:

| Campo | Valor |
| --- | ---: |
| `DIC` total | 2.991.079,438333 |
| `DIC_BASE_COMPENSACAO` total | 2.986.713,815278 |
| Reducao | 4.365,623056 |
| `FIC` total | 1.693.476 |
| `FIC_BASE_COMPENSACAO` total | 1.691.109 |
| Reducao | 2.367 |

Essa reducao ocorre por regras adicionais de compensacao, principalmente eventos com `COD_COMP_INTRP = '52'` e eventos de posto particular (`INDIC_PROPR_POSTO_INTRP = 'P'`). A combinacao historica `COD_COMP_INTRP = '52'` com `COD_CAUSA_INTRP = '71'` permanece como marcador complementar. Portanto, deve ficar documentado que:

- `DIC`, `FIC` e `DMIC` sao indicadores realizados e devem fechar com DEC/FEC liquido;
- `DIC_BASE_COMPENSACAO`, `FIC_BASE_COMPENSACAO` e `DMIC_BASE_COMPENSACAO` sao base financeira, podendo ser menores por regra especifica de ressarcimento.

### Problema confirmado no filtro de tratamento diferenciado

Existe um problema concreto na apuracao atual.

A regra de tratamento marca sobreposicao total por UC como:

```text
NUM_MOTIVO_TRAT_DIF_UCI = 91
INDIC_SIT_PROCES_INDIC_UCI = D
```

Porem, a regra correta e mais ampla: qualquer codigo em `NUM_MOTIVO_TRAT_DIF_UCI` representa tratamento diferenciado e nao deve compor DEC/FEC liquido nem DIC/FIC. Na base tratada ha, por exemplo, valores `91.0/D`, `90.0/R`, `1.0`, `10.0` e outros.

Impacto medido em `ANOMES=202606`:

| Cenario | Linhas | CI/FIC | CHI/DIC |
| --- | ---: | ---: | ---: |
| Registros com `NUM_MOTIVO_TRAT_DIF_UCI` preenchido presentes na base antiga | 177.091 | 44.050 | 60.540,385278 |
| Base liquida antiga | - | 1.693.476 | 2.991.079,438333 |
| Base liquida somente com `NUM_MOTIVO_TRAT_DIF_UCI` nulo | - | 1.649.426 | 2.930.539,053055 |

Conclusao: a percepcao de problema no ressarcimento procede. A causa imediata nao esta na formula de DIC/FIC, mas no filtro da base apuravel, que estava permitindo registros com tratamento diferenciado.

### Divergencia entre documentacao e codigo

A documentacao de apuracao diz que `gold_apuracao_uc` deve considerar somente UCs sem motivo de tratamento diferenciado:

```sql
NUM_MOTIVO_TRAT_DIF_UCI IS NULL
AND INDIC_SIT_PROCES_INDIC_UCI IS NULL
```

O codigo antigo excluia apenas a combinacao `91/D`. A regra oficial definida agora e usar somente registros com `NUM_MOTIVO_TRAT_DIF_UCI` nulo:

| Cenario | CI/FIC liquido | CHI/DIC liquido |
| --- | ---: | ---: |
| Base antiga | 1.693.476 | 2.991.079,438333 |
| Corrigir apenas `91` e `91.0` com `D` | 1.685.340 | 2.961.978,216667 |
| Regra oficial: `NUM_MOTIVO_TRAT_DIF_UCI IS NULL` | 1.649.426 | 2.930.539,053055 |

Decisao registrada: `NUM_MOTIVO_TRAT_DIF_UCI` deve estar nulo para compor a previa. Codigos preenchidos sao motivos de tratamento diferenciado e nao devem ser considerados no calculo de DIC/FIC.

### Sobreposicao temporal por UC

No tratamento, a regra de sobreposicao por UC compara eventos da mesma UC, do mesmo `COD_TIPO_INTRP` e do mesmo `TIPO_PROTOC_JUSTIF_UCI`.

Pontos observados:

- a sobreposicao total por UC compara `COD_TIPO_INTRP` entre evento contido e evento dominante, sem restringir a lista de tipos, pois a apuracao tambem considera tipos como `2` e `3`;
- a sobreposicao parcial tambem exige mesmo `COD_TIPO_INTRP`;
- tambem ha comparacao de `TIPO_PROTOC_JUSTIF_UCI`, evitando misturar a base liquida (`0`), Dia Critico/DICRI (`1`) e ISE/DISE (`5`/`6`);
- o filtro por `INDIC_SIT_PROCES_INDIC_UCI` nao deve excluir registros da avaliacao de sobreposicao quando `NUM_MOTIVO_TRAT_DIF_UCI` estiver nulo, pois o motivo e a regra decisiva para entrar ou sair da base apuravel.

Conclusao: a regra deve respeitar o mesmo `COD_TIPO_INTRP` e o mesmo `TIPO_PROTOC_JUSTIF_UCI`, mas nao deve limitar artificialmente os tipos avaliados. Essa regra esta protegida pelo teste automatizado de sobreposicao residual.

### Ocorrencia/interrupcao sem UC apos sobreposicao

Apos aplicar sobreposicao total e parcial por UC, o programa deve verificar se existem interrupcoes que permaneceram em `ESTADO_INTRP = 4`, mas ficaram sem UC apuravel.

Essa analise existe em dois niveis:

| Nivel | Tabela | Objetivo |
| --- | --- | --- |
| Interrupcao | `gold_interrupcao_sem_uc` | identificar interrupcoes individuais sem UC apuravel |
| Ocorrencia | `gold_ocorrencia_sem_uc` | identificar ocorrencias em que todas as interrupcoes ficaram sem UC apuravel |

Regra de sinalizacao por ocorrencia:

- ocorrencia e agrupador de interrupcoes;
- se todas as interrupcoes `ESTADO_INTRP = 4` da ocorrencia ficarem sem UC apuravel, a ocorrencia deve ser sinalizada;
- a sinalizacao sugere avaliar se as interrupcoes da ocorrencia podem ser marcadas como `ESTADO_INTRP = 7` e `91/R`;
- essa marcacao nao deve ser automatica sem aceite/regra operacional, pois altera a interrupcao no nivel da ocorrencia.

Saidas esperadas em `data/marts`:

```text
Auditoria_Interrupcao_Sem_UC_<ANOMES>_<timestamp>.CSV
Auditoria_Ocorrencia_Sem_UC_<ANOMES>_<timestamp>.CSV
```

### Diagnostico do modelo de dados

O modelo atual funciona, mas mistura responsabilidades:

| Camada/tabela atual | Problema |
| --- | --- |
| `raw_iqs_*` em `data/raw` | Correto como origem local das extracoes IQS. |
| `gold_uc_fatura`, `gold_vrc`, `gold_metas_uc` | Sao tabelas auxiliares/dimensionais, mas estao nomeadas como `gold`. |
| `gold_interrupcao_tratada` | Tem caracteristica de camada `silver`, pois ainda e fato tratado em nivel granular. |
| `gold_apuracao_uc` | Deveria ser a base canonica `silver` de UC-evento apuravel. |
| `gold_apuracao_previa` | E uma agregacao final de DEC/FEC, portanto faz sentido como `gold`. |
| `gold_continuidade_uc` | Mistura indicador realizado, enriquecimento por metas/VRC e calculo financeiro. |

Ha tambem tabelas repetidas por compatibilidade:

- `raw_iqs_uc_fatura` no DuckDB de raw e `gold_uc_fatura` no processed;
- `raw_iqs_vrc` no DuckDB de raw e `gold_vrc` no processed;
- `raw_iqs_metas_uc` no DuckDB de raw e `gold_metas_uc` no processed.

Isso nao quebra o fluxo, mas aumenta risco de usar uma tabela errada ou desatualizada.

### Proposta de arquitetura corrigida

Criar uma camada `silver` explicita dentro do processed, mantendo as tabelas `gold_*` atuais como compatibilidade enquanto o codigo e migrado.

Modelo proposto:

```text
raw
  iqs_adms_raw_<ANOMES>.duckdb
    hiadms_raw

  iqs_raw_<ANOMES>.duckdb
    raw_iqs_consumidores
    raw_iqs_uc_fatura
    raw_iqs_vrc
    raw_iqs_metas_uc

processed
  silver_iqs_consumidores
  silver_iqs_uc_fatura
  silver_iqs_vrc
  silver_iqs_metas_uc
  silver_interrupcao_tratada
  silver_interrupcao_uc_apuravel

gold
  gold_apuracao_previa
  gold_continuidade_uc
  gold_ressarcimento_previo
```

A tabela mais importante deve ser `silver_interrupcao_uc_apuravel`, com uma linha por UC/interrupcao ja tratada, contendo:

- chaves da interrupcao e da UC;
- `COD_TIPO_INTRP`;
- `TIPO_PROTOC_JUSTIF_UCI`;
- inicio/fim original e inicio ajustado por UC;
- duracao em horas;
- indicador de UC faturada;
- flag de interrupcao longa;
- flag de interrupcao contabilizavel;
- flag de sobreposicao total;
- flag de sobreposicao parcial;
- motivo de tratamento diferenciado normalizado (`91`, nao `91.0`);
- flags de exclusao especificas para compensacao.

A partir dela:

- DEC/FEC deve agregar por interrupcao/regional;
- DIC/FIC/DMIC deve agregar por UC;
- ressarcimento deve usar os mesmos indicadores realizados, aplicando somente depois as exclusoes financeiras.

### Correcoes recomendadas em ordem

1. [x] Corrigir `NUM_MOTIVO_TRAT_DIF_UCI` na apuracao para aceitar somente motivo nulo.
2. [x] Decidir regra oficial para os demais motivos/situacoes (`90/R`, `1`, `10`, etc.): ficam fora da previa quando `NUM_MOTIVO_TRAT_DIF_UCI` estiver preenchido.
3. [x] Criar teste de regressao garantindo que registros com `NUM_MOTIVO_TRAT_DIF_UCI` preenchido nao entram em `gold_apuracao_uc`.
4. [x] Criar teste garantindo que sobreposicao de UCs so compara eventos com o mesmo `COD_TIPO_INTRP`.
5. [x] Separar `DIC/FIC/DMIC` realizados de `*_BASE_COMPENSACAO`, deixando claro que a base financeira pode ser menor.
6. [x] Migrar gradualmente `gold_uc_fatura`, `gold_vrc` e `gold_metas_uc` para nomes `silver_*`, mantendo tabelas de compatibilidade.
7. [x] Criar auditoria por ocorrencia sem UC apuravel apos sobreposicao total/parcial por UC.
8. [~] Refatorar `apuracao_previa.py`: auditoria sem UC ja foi extraida; ainda falta separar continuidade, ressarcimento e exportacoes.
9. [x] Corrigir regra financeira de compensacao para excluir eventos `COD_COMP_INTRP = '52'` e posto particular.
10. [x] Corrigir auditoria de duplicidade por `COD_TIPO_INTRP` para dominio vigente `1`, `2` e `3`.

## Fluxo operacional recomendado

### Rodar usando somente arquivos locais

Use quando o computador nao tem acesso ao Oracle, mas possui os DuckDBs em `data/raw`.

```bat
set REPROCESSAR=1
run.bat reprocessar
run.bat exportacoes_auxiliares
run.bat sincronizar_iqs_raw
run.bat apuracao_parcial
```

Se o `iqs_raw_<ANOMES>.duckdb` ainda nao existir, mas houver um `processed_old` com as tabelas auxiliares:

```bat
python tools\copiar_iqs_raw_do_old.py
run.bat sincronizar_iqs_raw
run.bat apuracao_parcial
```

### Rodar com acesso ao Oracle

Use quando o computador tem acesso ao banco IQS.

```bat
run.bat consumidores
run.bat uc_fatura
run.bat vrc
run.bat metas_uc
run.bat sincronizar_iqs_raw
run.bat apuracao_parcial
```

Os extratores gravam primeiro em:

```text
data/raw/iqs_raw_<ANOMES>.duckdb
```

e depois refletem as tabelas no `processed` para compatibilidade.

### Reprocessar tratamento mantendo RAW

```bat
set REPROCESSAR=1
run.bat tratamento
run.bat exportacoes_auxiliares
```

## Proximas melhorias priorizadas

### 1. Consolidar documentacao oficial do fluxo

Objetivo: remover ambiguidades entre regra antiga e regra vigente.

Acao proposta:

1. Criar `docs/14_fluxo_oficial_atual.md`.
2. Declarar explicitamente as camadas:
   - `data/raw/iqs_adms_raw_<ANOMES>.duckdb`;
   - `data/raw/iqs_raw_<ANOMES>.duckdb`;
   - `data/processed/iqs_adms_processed_<ANOMES>.duckdb`;
   - `data/export`;
   - `data/marts`.
3. Marcar sobreposicao total por equipamento como regra historica/removida do fluxo principal.
4. Padronizar exemplos para usar sempre `run.bat`.

### 2. Criar checklist de fechamento mensal

Objetivo: reduzir risco operacional na virada de competencia.

Checklist recomendado:

Checklist oficial consolidado em `docs/14_fluxo_oficial_atual.md`.

### 3. Modularizar `apuracao_previa.py`

Objetivo: reduzir risco de manutencao.

Problema atual:

- `apuracao_previa.py` possui varias redefinicoes de funcoes.
- O arquivo acumula apuracao BDO, interrupcao sem UC, continuidade UC e compensacao previa.

Proposta de separacao:

```text
apuracao/
  caminhos.py
  gold_interrupcao.py
  gold_apuracao_uc.py
  gold_apuracao_previa.py
  interrupcao_sem_uc.py
  continuidade_uc.py
  compensacao_previa.py
  exportacao.py
```

Status atual:

- `midway/apuracao/auditoria_sem_uc.py` criado.
- `apuracao_previa.py` ainda concentra:
  - criacao de `gold_continuidade_uc`;
  - criacao de `gold_ressarcimento_prodist`;
  - exportacoes de continuidade/ressarcimento;
  - BDO e resumo principal.
- Proximo passo recomendado: extrair `continuidade_uc.py` e `ressarcimento_prodist.py`.

### 4. Modularizar `tratamento.py`

Objetivo: separar regra de negocio, exportacao e auditoria.

Proposta:

```text
tratamento/
  caminhos.py
  sql_tratamento.py
  exportacao_iqs.py
  auditoria_outliers.py
  auditoria_estado_7.py
  auditoria_uc_91_d.py
```

Essa refatoracao deve ocorrer somente depois de criar testes de regressao.

Status atual:

- Redefinicoes silenciosas de funcoes de exportacao IQS foram neutralizadas por renomeacao das versoes antigas para `_obsoleto_*`.
- Ainda falta separar o SQL de tratamento e as auditorias em modulos menores.

### 5. Criar testes minimos com DuckDB pequeno

Objetivo: validar regras sem depender dos arquivos grandes.

Proposta detalhada de testes automatizados e estatisticos:

```text
docs/11_testes_automatizados_estatisticos.md
```

Casos minimos:

1. UC totalmente contida por outra interrupcao.
2. UC com sobreposicao parcial.
3. Interrupcao sem UC apuravel.
4. Manobra com `NUM_INTRP_INIC_MANOBRA_UCI`.
5. Exportacao por regional.
6. Sincronizacao de `iqs_raw` para `gold_*`.

Estrutura proposta:

```text
tests/
  fixtures/
  test_tratamento_sobreposicao.py
  test_iqs_raw_sync.py
  test_apuracao_previa.py
```

### 6. Governanca da compensacao previa

Objetivo: nao tratar calculos ainda nao validados como oficiais.

Analise normativa criada em:

```text
docs/10_prodist_modulo8.md
```

Pendencias:

1. Confirmar formula vigente no PRODIST Modulo 8.
2. Confirmar divisor `730`.
3. Confirmar regra de FIC.
4. Confirmar se DICRI e DISE geram compensacao financeira.
5. Confirmar arredondamento, teto, minimo e acumulacao.
6. Registrar fonte, data de validacao e responsavel.

Enquanto isso, manter `COMP_*` como valor previo/de conferencia.

## Criterios de sucesso revisados

O projeto sera considerado estabilizado quando:

- o fluxo completo rodar localmente a partir dos DuckDBs em `data/raw`;
- as extracoes auxiliares do IQS forem mantidas em `iqs_raw_<ANOMES>.duckdb`;
- o `processed` puder ser reconstruido sem depender do `processed_old`;
- a documentacao apontar um unico fluxo oficial;
- houver testes pequenos para as regras principais;
- compensacao previa estiver validada ou claramente marcada como nao oficial.

## Status resumido

```text
[x] Abrir RAWs locais
[x] Reprocessar tratamento local
[x] Gerar exportacao oficial IQS
[x] Gerar exportacoes auxiliares
[x] Criar camada iqs_raw
[x] Copiar auxiliares do processed_old para iqs_raw
[x] Sincronizar iqs_raw para processed
[x] Criar camada silver_iqs no processed
[x] Criar silver_interrupcao_uc_apuravel
[x] Corrigir filtro de NUM_MOTIVO_TRAT_DIF_UCI nulo na apuracao
[x] Criar gold_ressarcimento_prodist conforme PRODIST Modulo 8
[x] Rodar apuracao parcial
[x] Gerar BDO local
[x] Criar testes automatizados
[x] Corrigir 300 sobreposicoes residuais encontradas na base liquida
[x] Consolidar docs em fluxo oficial unico
[x] Criar auditoria de ocorrencia sem UC apuravel
[x] Organizar scripts auxiliares em pastas `midway/*` com wrappers na raiz
[x] Criar pagina Analytics Pos-Operacao no Streamlit
[x] Registrar versao inicial 6.0.0
[~] Refatorar apuracao_previa.py
[~] Refatorar tratamento.py
[ ] Validar compensacao previa contra PRODIST
```
