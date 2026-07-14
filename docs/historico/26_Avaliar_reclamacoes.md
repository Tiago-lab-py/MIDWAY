# 26 - Avaliar Reclamações

## Objetivo

Criar uma visão operacional para avaliar reclamações do DBGUO vinculadas às interrupções do IQS/ADMS por UC, horário e ocorrência provável.

A análise ajuda a responder três perguntas:

- a UC reclamou durante ou logo após uma interrupção?
- qual ocorrência/interrupção é a candidata mais provável para essa reclamação?
- qual é a causa provável da reclamação pelo texto informado no DBGUO?
- a ocorrência já foi validada pela pós-operação e, portanto, não precisa ser reavaliada como pendência comum?

## Tabelas geradas

O comando de materialização DBGUO passa a gerar uma camada silver e três camadas gold.

### `silver_dbguo_reclamacoes`

Tabela detalhada com uma linha por reclamação e a melhor interrupção candidata, escolhida por score.

Campos principais:

| Campo | Descrição |
| --- | --- |
| `ID_RECLAMACAO` | identificador da reclamação no DBGUO |
| `UC` | unidade consumidora reclamante |
| `DTHR_RECLAMACAO` | data/hora da reclamação |
| `TEXTO_RECLAMACAO` | texto bruto da reclamação no DBGUO |
| `TEXTO_RETORNO` | informação de retorno/atendimento quando disponível |
| `TIPO_RECLAMACAO_PROVAVEL` | classificação textual da reclamação |
| `CAUSA_PROVAVEL_RECLAMACAO` | causa provável combinando texto e vínculo com a ocorrência |
| `DESC_CAUSA_INTRP` | descrição da causa IQS/ADMS vinda de `causa.csv` |
| `DESC_COMP_INTRP` | descrição do componente IQS/ADMS vinda de `componente.csv` |
| `GRUPO_CAUSA_IQS` | agrupamento operacional da causa IQS |
| `GRUPO_COMPONENTE_IQS` | agrupamento operacional do componente IQS |
| `ADERENCIA_RECLAMACAO_CAUSA_IQS` | aderência entre texto da reclamação e causa/componente da ocorrência |
| `PREVIA_CAUSA_RECLAMACAO` | prévia operacional combinando reclamação, causa e componente |
| `NUM_OCORRENCIA_ADMS` | ocorrência provável vinculada |
| `NUM_SEQ_INTRP` | interrupção provável vinculada |
| `DISTANCIA_MINUTOS` | distância entre a reclamação e a janela da interrupção |
| `POSICAO_RECLAMACAO` | antes, durante ou após a interrupção |
| `SCORE_VINCULO_RECLAMACAO` | força do vínculo reclamação/interrupção |
| `CLASSIFICACAO_VINCULO_RECLAMACAO` | classificação textual do vínculo |

### `gold_reclamacao_uc_vinculada`

Tabela principal para frontend. Enriquece a silver com dados de pós-operação, impacto e referência de ressarcimento da UC.

Campos adicionais:

| Campo | Descrição |
| --- | --- |
| `TEM_OCORRENCIA_PROVAVEL` | `S` quando há ocorrência provável vinculada |
| `VALID_POS_OPERACAO` | `S` quando a ocorrência já foi validada pela pós-operação |
| `UCS_APURAVEIS_OCORRENCIA` | UCs apuráveis na ocorrência provável |
| `FIC_OCORRENCIA` | FIC total da ocorrência provável |
| `DIC_OCORRENCIA` | DIC total da ocorrência provável |
| `COMP_TOTAL_PRODIST_UC` | compensação PRODIST da UC como referência |
| `STATUS_AVALIACAO_RECLAMACAO` | status operacional da avaliação |
| `TIPO_RECLAMACAO_PROVAVEL` | tipo textual da reclamação |
| `CAUSA_PROVAVEL_RECLAMACAO` | causa provável para triagem operacional |
| `PREVIA_CAUSA_RECLAMACAO` | prévia enriquecida com causa/componente IQS |
| `ADERENCIA_RECLAMACAO_CAUSA_IQS` | `ALTA`, `MEDIA`, `BAIXA`, `SEM_OCORRENCIA_IQS` ou `INDEFINIDA` |

### `gold_reclamacao_uc_resumo`

Resumo por UC para ranqueamento no painel.

Principais métricas:

- `QTD_RECLAMACOES`
- `QTD_COM_OCORRENCIA_PROVAVEL`
- `QTD_SEM_OCORRENCIA_PROVAVEL`
- `QTD_RECLAMACOES_OCORRENCIA_VALIDADA_POS`
- `MAX_SCORE_VINCULO_RECLAMACAO`
- `MENOR_DISTANCIA_MINUTOS`

### `gold_reclamacao_ocorrencia_resumo`

Resumo por ocorrência para cruzamento com Analytics Pós-Operação.

Principais métricas:

- `QTD_RECLAMACOES`
- `QTD_UCS_RECLAMANTES`
- `UCS_APURAVEIS_OCORRENCIA`
- `FIC_OCORRENCIA`
- `DIC_OCORRENCIA`
- `VALID_POS_OPERACAO`
- `TIPOS_RECLAMACAO_PROVAVEIS`
- `CAUSAS_PROVAVEIS_RECLAMACAO`
- `PREVIAS_CAUSA_RECLAMACAO`
- `GRUPOS_CAUSA_IQS`
- `GRUPOS_COMPONENTE_IQS`
- `QTD_ADERENCIA_ALTA`
- `QTD_ADERENCIA_MEDIA`
- `QTD_RECLAMACOES_FALTA_ENERGIA`
- `QTD_RECLAMACOES_OSCILACAO`

## Diagnóstico da base atual

Na avaliação local com `ANOMES=202606`, o RAW DBGUO contém reclamações de período mais amplo que a apuração IQS:

| Métrica | Valor |
| --- | ---: |
| Reclamações RAW DBGUO | `818.014` |
| Período RAW DBGUO | `26/03/2026` a `08/07/2026` |
| Janela da apuração IQS | `01/06/2026` a `30/06/2026` |
| Reclamações em junho/2026 | `238.641` |
| Reclamações dentro da janela operacional da apuração (`-2h` a `+24h`) | `247.531` |
| Reclamações com ocorrência provável no processamento avaliado | `193.167` |
| Ocorrências com reclamação provável | `38.764` |

Conclusão operacional: sem filtrar a janela da apuração, o painel exibe muitas reclamações antigas ou futuras como `SEM_OCORRENCIA_PROVAVEL`. A análise continua rastreável, mas o recorte recomendado para validação por ocorrência deve priorizar a janela operacional do mês apurado.

A extração DBGUO e a materialização silver aplicam a janela:

```text
primeiro dia do ANOMES - 2 dias
até
primeiro dia do mês seguinte + 2 dias
```

Para `ANOMES=202606`, a janela fica:

```text
2026-05-30 00:00:00 <= DATA_RECLAMACAO < 2026-07-03 00:00:00
```

Mesmo que um RAW antigo tenha sido extraído sem filtro de período, a materialização `run.bat dbguo_reclamacoes` também restringe a silver a essa janela.

## Regra de vínculo reclamação/interrupção

A reclamação é comparada com as interrupções da mesma UC dentro da janela:

```text
início da interrupção - 2 horas
até
fim da interrupção + 24 horas
```

A melhor candidata é escolhida por:

1. maior `SCORE_VINCULO_RECLAMACAO`;
2. menor `DISTANCIA_MINUTOS`;
3. interrupção mais recente em caso de empate.

## Score do vínculo

| Situação | Score |
| --- | ---: |
| reclamação durante a interrupção | 100 |
| reclamação até 60 minutos após o fim | 90 |
| reclamação entre 61 e 360 minutos após o fim | 80 |
| reclamação entre 361 e 1440 minutos após o fim | 65 |
| reclamação até 120 minutos antes do início | 50 |
| fora da janela avaliada | 0 |

Classificação:

| Score | Classificação |
| ---: | --- |
| `>= 100` | `VINCULO_FORTE_DURANTE_INTERRUPCAO` |
| `>= 80` | `VINCULO_FORTE_APOS_INTERRUPCAO` |
| `>= 60` | `VINCULO_PROVAVEL` |
| `>= 50` | `VINCULO_FRACO_ANTES_INTERRUPCAO` |
| `< 50` | `SEM_OCORRENCIA_PROVAVEL` |

## Causa provável da reclamação

A causa provável é uma classificação de triagem. Ela não substitui a análise técnica da pós-operação nem altera os dados oficiais do IQS.

### Tipo textual

O campo `TIPO_RECLAMACAO_PROVAVEL` é inferido a partir de `RECLAMACAO` e `INFORMACAO_RETORNO` do DBGUO.

| Tipo | Indícios textuais |
| --- | --- |
| `FALTA_ENERGIA` | falta de energia, sem energia, chave caída, desligamento, apagado |
| `OSCILACAO_TENSAO` | oscilação, piscando, tensão, meia fase |
| `DANO_EQUIPAMENTO` | queima, dano, equipamento |
| `VEGETACAO_REDE` | árvore, poda |
| `REDE_EQUIPAMENTO` | poste, cabo, fio, transformador |
| `SEM_TEXTO` | reclamação e retorno vazios |
| `OUTROS` | texto sem padrão reconhecido |

### Causa operacional

O campo `CAUSA_PROVAVEL_RECLAMACAO` combina o tipo textual com a ocorrência provável:

| Situação | Causa provável |
| --- | --- |
| falta de energia durante interrupção vinculada | `INTERRUPCAO_CONFIRMADA_DURANTE_RECLAMACAO` |
| falta de energia após fim da interrupção vinculada | `INTERRUPCAO_PROVAVEL_POS_RETORNO` |
| oscilação com ocorrência vinculada | `OSCILACAO_TENSAO_ASSOCIADA_A_OCORRENCIA` |
| vegetação/rede/dano com ocorrência vinculada | `<TIPO>_COM_OCORRENCIA_PROVAVEL` |
| falta de energia sem ocorrência IQS próxima | `FALTA_ENERGIA_SEM_OCORRENCIA_IQS` |
| oscilação sem ocorrência IQS próxima | `OSCILACAO_SEM_OCORRENCIA_IQS` |
| sem ocorrência IQS próxima | `SEM_OCORRENCIA_IQS` |
| ocorrência vinculada sem causa textual específica | `OCORRENCIA_PROVAVEL_SEM_CAUSA_TEXTUAL_ESPECIFICA` |

Uso recomendado: priorizar ocorrências com muitas reclamações, muitas UCs reclamantes e causas prováveis concentradas em `FALTA_ENERGIA` ou `OSCILACAO_TENSAO`.

## Prévia por reclamação usando causa e componente

A prévia enriquecida usa dois dicionários operacionais:

```text
data/input/causa.csv
data/input/componente.csv
```

Esses arquivos devem conter, no mínimo:

| Arquivo | Colunas usadas |
| --- | --- |
| `causa.csv` | `COD_CAUSA`, `DESC_CAUSA` |
| `componente.csv` | `COD_COMP`, `DESC_COMP` |

Também é possível sobrescrever os caminhos via `.env`:

```env
IQS_CAUSA_CSV=D:\caminho\causa.csv
IQS_COMPONENTE_CSV=D:\caminho\componente.csv
```

### Agrupamento da causa IQS

| Grupo | Exemplos de descrição da causa |
| --- | --- |
| `VEGETACAO` | árvore, galho |
| `TENSAO_OSCILACAO` | tensão, desequilíbrio |
| `FALHA_COMPONENTE` | componente avariado, falha, defeito, corrosão/oxidação, ponto quente, manutenção corretiva |
| `CLIMA_AMBIENTE` | descarga atmosférica, vento/vendaval, animais/insetos/pássaros, objetos estranhos |
| `TERCEIROS` | abalroamento, terceiros, vandalismo, furto |
| `OPERACAO_REDE` | manobra, transferência de carga, retorno de configuração |
| `QUEIMADA_INCENDIO` | queimada, incêndio |
| `INSPECAO_EMERGENCIA` | inspeção/manutenção de equipe de emergência |
| `NAO_IDENTIFICADA` | causa IQS não identificada |
| `OUTRA_CAUSA_IQS` | causa sem grupo específico |
| `SEM_CAUSA_IQS` | código ausente ou sem dicionário |

### Agrupamento do componente IQS

| Grupo | Exemplos de descrição do componente |
| --- | --- |
| `CHAVE_PROTECAO` | chave, elo fusível, fusível |
| `CONEXAO` | conector, grampo, jumper, terminais |
| `CONDUTOR_RAMAL` | condutor, cabo, ramal |
| `REDE_DISTRIBUICAO` | rede de distribuição |
| `TRANSFORMADOR` | transformador, trafo |
| `ESTRUTURA_REDE` | poste, cruzeta, isolador |
| `MEDICAO` | medição, medidor |
| `OUTRO_COMPONENTE_IQS` | componente sem grupo específico |
| `SEM_COMPONENTE_IQS` | código ausente ou sem dicionário |

### Aderência

| Aderência | Interpretação |
| --- | --- |
| `ALTA` | texto da reclamação é compatível com causa/componente IQS da ocorrência |
| `MEDIA` | há ocorrência provável e o texto é relevante, mas a causa/componente não confirma diretamente |
| `BAIXA` | ocorrência provável existe, mas o texto ficou em `OUTROS` |
| `SEM_OCORRENCIA_IQS` | não há ocorrência IQS vinculada pela janela temporal |
| `INDEFINIDA` | caso residual para revisão |

Exemplos:

| Texto da reclamação | Causa/componente IQS | Prévia |
| --- | --- | --- |
| falta de energia | falha de componente + chave/fusível | `FALTA_ENERGIA | FALHA_COMPONENTE | CHAVE_PROTECAO` |
| oscilação | desequilíbrio de carga/tensão | `OSCILACAO_TENSAO | TENSAO_OSCILACAO | ...` |
| árvore/poda | árvore/galho | `VEGETACAO_REDE | VEGETACAO | ...` |
| cabo/fio/poste | condutor, ramal ou estrutura | `REDE_EQUIPAMENTO | ... | CONDUTOR_RAMAL` |

## Validação Pós-Operação

Quando `VALID_POS_OPERACAO = S`, a reclamação continua visível, mas a ocorrência é tratada como já verificada.

Esse comportamento evita retrabalho: a reclamação pode ser consultada, mas deixa de ser uma pendência comum de análise.

## Frontend

A página `08 Avaliação de UC` passa a ter três abas:

```text
Outlier UC
Consulta UC
Reclamações UC
```

### Aba `Reclamações UC`

Filtros:

- UC específica, opcional;
- data inicial e final da reclamação;
- status do vínculo;
- score mínimo do vínculo.

Indicadores exibidos:

- total de reclamações;
- UCs com reclamação;
- reclamações com ocorrência provável;
- reclamações sem ocorrência provável.

Tabelas exibidas:

- ranking de UCs com reclamações;
- ranking de ocorrências com reclamações;
- detalhe das reclamações com ocorrência/interrupção provável.

## Comandos

Após a extração DBGUO e a apuração IQS estarem disponíveis:

```bat
set ANOMES=202606
run.bat dbguo_reclamacoes
```

Para abrir o painel:

```bat
run.bat painel
```

## Ordem recomendada

```bat
set ANOMES=202606
run.bat apuracao_parcial
run.bat dbguo_reclamacoes
run.bat painel
```

Se o raw DBGUO ainda não existir, executar antes:

```bat
set REEXTRAIR_DBGUO=1
run.bat extrair_dbguo_reclamacoes
```
