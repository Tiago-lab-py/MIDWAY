# 27 - Qualidade de Interrupções com Reclamações e Serviços

## Objetivo

Melhorar a qualidade das interrupções cruzando três fontes de evidência:

- registro oficial IQS/ADMS da interrupção;
- reclamações DBGUO associadas à UC, horário e ocorrência provável;
- serviços ADMS associados à interrupção, equipe, causa, componente e fechamento.

A meta não é corrigir automaticamente o IQS na primeira versão. A meta é gerar evidência operacional para classificar causa, componente, improcedência, duplicidade e necessidade de revisão.

## Tese operacional

Reclamação descreve o sintoma percebido pelo cliente.

Serviço descreve a ação operacional executada ou encerrada pela equipe.

IQS/ADMS descreve o registro oficial da interrupção.

Quando as três fontes contam a mesma história, a qualidade da interrupção tende a estar boa. Quando divergem, nasce uma auditoria.

## Nova extração RAW de serviços

O notebook `notebooks/analise_exploratoria_sobreposicao_protocolos_v2.ipynb` lê arquivos de serviço em pasta de backup. Para produção, essa leitura passa a ter extrator próprio.

Comando:

```bat
set ANOMES=202606
run.bat extrair_adms_servicos
```

Saída RAW:

```text
data/raw/adms_servicos_raw_<ANOMES>.duckdb
```

Tabela:

```text
raw_adms_servicos
```

Fonte padrão:

```text
P:\Common\IQS\ADMS\Backup
```

Variáveis de ambiente:

```env
ADMS_SERVICOS_BACKUP_DIR=P:\Common\IQS\ADMS\Backup
ADMS_SERVICOS_PATTERN=IQS_SERVICOS_*.CSV
ADMS_SERVICOS_MARGEM_DIAS=2
ADMS_SERVICOS_MARGEM_ARQUIVOS_DIAS=10
REEXTRAIR_ADMS_SERVICOS=1
```

## Janela de apuração

O extrator filtra os serviços pela data de referência do serviço:

```text
DATA_REFERENCIA_SERVICO =
  DTHR_INIC_SRV
  ou DTHR_SOLIC_SRV
  ou DTHR_GERA_SRV
  ou DTHR_DESPACH_SRV
  ou DTHR_FECH_SRV
```

Janela:

```text
primeiro dia do ANOMES - ADMS_SERVICOS_MARGEM_DIAS
até
primeiro dia do mês seguinte + ADMS_SERVICOS_MARGEM_DIAS
```

Para `ANOMES=202606` e margem `2`:

```text
2026-05-30 00:00:00 <= DATA_REFERENCIA_SERVICO < 2026-07-03 00:00:00
```

## Campos mínimos esperados

| Campo | Uso |
| --- | --- |
| `PID_INTRP_SRVE` | vínculo do serviço com a interrupção |
| `NUM_SEQ_SERV` | identificador do serviço |
| `PID` | identificador interno do serviço |
| `COD_CAUSA_SRVE` | causa registrada no serviço |
| `COD_COMP_SRVE` | componente registrado no serviço |
| `COD_COND_CLIMA_SRVE` | condição climática do serviço |
| `COD_CONJTO_ELET_ANEEL` | conjunto elétrico do serviço |
| `ESTADO_SERVICO_ACOMP` | estado/acompanhamento do serviço |
| `NUM_ORG_EXEC_SRV` | órgão/equipe executora |
| `DTHR_SOLIC_SRV` | solicitação |
| `DTHR_GERA_SRV` | geração |
| `DTHR_DESPACH_SRV` | despacho |
| `DTHR_INIC_SRV` | início |
| `DTHR_TERM_SRV` | término |
| `DTHR_RETOR_SRV` | retorno |
| `DTHR_FECH_SRV` | fechamento |
| `ARQUIVO_ORIGEM` | arquivo CSV que alimentou o RAW |
| `DATA_REFERENCIA_SERVICO` | data usada no filtro do mês |

## Próximas camadas

### `silver_adms_servicos`

Camada normalizada para análise, com códigos padronizados, datas tipadas e descrições de causa/componente quando disponíveis.

### `gold_servicos_interrupcao`

Resumo por interrupção:

- quantidade de serviços;
- serviços distintos;
- causas de serviço;
- componentes de serviço;
- primeira solicitação;
- primeiro despacho;
- primeiro início;
- último término;
- último fechamento;
- presença de causa `22`;
- presença de causa `85`.

### `gold_avaliacao_qualidade_interrupcao`

Camada final combinando:

- `gold_interrupcao_tratada`;
- `gold_reclamacao_ocorrencia_resumo`;
- `gold_servicos_interrupcao`.

## Classificação proposta

| Classificação | Regra inicial |
| --- | --- |
| `QUALIDADE_OK` | reclamação, serviço e interrupção são coerentes |
| `CAUSA_COMPONENTE_CONFIRMADOS` | texto da reclamação e serviço reforçam causa/componente IQS |
| `CAUSA_PROVAVEL_DIVERGENTE` | causa do serviço ou reclamação diverge da causa IQS |
| `COMPONENTE_PROVAVEL_DIVERGENTE` | componente do serviço diverge do componente IQS |
| `SUSPEITA_IMPROCEDENTE` | serviço associado possui causa `85` ou fechamento improcedente |
| `SUSPEITA_ATENDIDO_OUTRA_OCORRENCIA` | serviço associado possui causa `22` |
| `SUSPEITA_DUPLICIDADE_OCORRENCIA` | mesma UC/chave/conjunto tem serviços ou interrupções muito próximos |
| `RECLAMACAO_SEM_INTERRUPCAO_COMPATIVEL` | reclamação forte sem ocorrência IQS provável |
| `INTERRUPCAO_COM_RECLAMACAO_FORTE_SEM_CAUSA_CLARA` | muitas reclamações, mas causa/componente pouco explicativos |
| `REVISAR_MANUALMENTE` | evidência insuficiente ou conflitante |

## Evidências para score

| Evidência | Peso sugerido |
| --- | ---: |
| reclamações vinculadas à ocorrência | `+20` |
| múltiplas UCs reclamantes | `+15` |
| serviço com mesmo `PID_INTRP_SRVE` | `+20` |
| causa de serviço `22` ou `85` | `+25` |
| mesmo `NUM_OPER_CHV_INTRP` em ocorrências próximas | `+20` |
| causa/componente de serviço divergente do IQS | `+15` |
| fechamento de serviço até 10 minutos de outro serviço próximo | `+10` |

## Uso recomendado

Na primeira entrega, a classificação deve ser tratada como triagem:

- priorizar maiores impactos em CHI/DIC/VRC;
- exibir evidências no painel;
- permitir validação do analista antes de qualquer ajuste de exportação IQS.

## Frontend

A primeira visualização operacional está na página:

```text
09 Qualidade de Interrupções
```

Ela usa:

```text
data/processed/iqs_adms_processed_<ANOMES>.duckdb
data/raw/adms_servicos_raw_<ANOMES>.duckdb
```

E monta dinamicamente:

- cartões de cobertura de serviços, reclamações e causas `22`/`85`;
- ranking de interrupções para revisão;
- resumo por classificação;
- distribuição dos serviços por causa/componente/estado.

O ranking prioriza evidências complementares:

- serviço associado à interrupção;
- reclamação vinculada à ocorrência;
- causa de serviço `22`;
- causa de serviço `85`;
- divergência entre causa/componente IQS e serviço;
- múltiplos serviços na mesma interrupção.

## Comandos

Extrair serviços:

```bat
set ANOMES=202606
run.bat extrair_adms_servicos
```

Reextrair:

```bat
set ANOMES=202606
set REEXTRAIR_ADMS_SERVICOS=1
run.bat extrair_adms_servicos
```

Fluxo alvo futuro:

```bat
run.bat extrair_adms_servicos
run.bat dbguo_reclamacoes
run.bat qualidade_interrupcoes
run.bat painel
```
