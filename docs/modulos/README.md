# Catálogo oficial de módulos MIDWAY

Este diretório é a documentação ativa dos módulos do MIDWAY.

O produto principal é detectar, analisar, decidir e exportar correções de anomalias dos dados OMS/ADMS para o IQS. Um módulo deve gerar evidência, impacto, proposta e caminho de exportação, quando aplicável.

## Contrato comum de módulo

Todo módulo deve declarar:

| Campo | Obrigatório | Descrição |
| --- | --- | --- |
| `codigo_modulo` | Sim | Identificador estável do módulo |
| `escopo` | Sim | `ocorrencia`, `interrupcao`, `uc`, `equipamento`, `alimentador`, `conjunto` ou combinação |
| `fontes` | Sim | Tabelas DuckDB/PostgreSQL/arquivos usados |
| `criterio_anomalia` | Sim | Regra objetiva de detecção |
| `evidencias` | Sim | Campos que sustentam a suspeita |
| `impacto` | Sim | DEC/FEC/DIC/FIC/ressarcimento/qualidade |
| `acao_sugerida` | Sim | O que o analista/gestor deve avaliar |
| `campos_iqs_afetados` | Quando exportável | Campos do layout IQS que podem mudar |
| `exportacao_iqs` | Quando aplicável | Pasta, arquivo e condição de exportação |
| `risco_falso_positivo` | Sim | Cuidados para evitar ajuste indevido |
| `status_governanca` | Sim | Pendente, em análise, aprovada, rejeitada, aplicada |

## Contrato de exportação IQS

Todo módulo que gerar arquivo final para carga deve cumprir `docs/35_contrato_exportacao_iqs.md`.

Isso inclui separador `|`, quebra UNIX/LF, encoding `ISO-8859-1`, transliteração de caracteres especiais, datas `dd/mm/aaaa hh:mm:ss`, inteiros sem decimal e layout oficial sem colunas faltantes, extras ou fora de ordem.

Arquivos de detalhe, resumo e auditoria podem usar formato amigável para análise, mas não podem ser confundidos com pacote IQS.

## Módulos regulatórios ativos

Estes módulos calculam indicadores e compensações conforme PRODIST Módulo 8 vigente e filtros COPEL registrados em `docs/36_regras_prodist_copel.md`.

| Código | Documento | Escopo |
| --- | --- | --- |
| `DIC_FIC_PRODIST` | `dic_fic_prodist.md` | UC/indicador individual |
| `DEC_FEC_PRODIST` | `dec_fec_prodist.md` | conjunto/regional/empresa |
| `RESSARCIMENTO_PRODIST` | `ressarcimento_prodist.md` | UC/compensação |

## Módulos de anomalia ativos

| Código | Documento | Escopo |
| --- | --- | --- |
| `SOBREPOSICAO_UC` | `sobreposicao_uc.md` | UC/interrupção |
| `INTERRUPCAO_SEM_UC` | `interrupcao_sem_uc.md` | Interrupção/ocorrência |
| `COMPONENTE_CAUSA` | `componente_causa.md` | Ocorrência/interrupção |
| `DURACAO_IMPACTO` | `duracao_impacto.md` | Ocorrência/interrupção |
| `RESSARCIMENTO_ATIPICO` | `ressarcimento_atipico.md` | UC/ocorrência |
| `RECLAMACOES_SERVICOS` | `reclamacoes_servicos.md` | Reclamação/serviço/ocorrência |
| `FALHA_EQUIPAMENTO_RA` | `falha_equipamento_ra.md` | Equipamento/alimentador/conjunto |
| `DIA_CRITICO_ISE` | `dia_critico_ise.md` | Conjunto/dia/regional |
| `DUPLICIDADE_TIPO` | `duplicidade_tipo.md` | UC/interrupção |
| `AJUSTE_MANUAL_IQS` | `ajuste_manual_iqs.md` | Governança/exportação |
| `CORRECAO_9282` | `correcao_9282.md` | Especialização componente/causa |

## Regra sobre 92/82

`CORRECAO_9282` é um módulo específico. Ele não deve aparecer como objetivo principal do MIDWAY em documentos ativos.

Se uma nova documentação disser “Executivo 92/82” como fluxo principal, ela deve ser reescrita para “Governança de Anomalias” ou arquivada em `docs/historico/`.
