# Índice ativo da documentação MIDWAY

Data de organização: `2026-07-14`

Este índice define a documentação oficial do MIDWAY. Arquivos fora desta lista não devem ser usados como especificação atual sem revisão.

## Norte atual

| Documento | Função |
| --- | --- |
| `docs/33_reorientacao_anomalias_oms_iqs.md` | Norte de produto: plataforma multi-anomalias OMS/ADMS para exportação IQS |
| `docs/00_especificacao.md` | Especificação geral do pipeline, dados, apuração e exportação |
| `docs/14_fluxo_oficial_atual.md` | Fluxo mensal operacional vigente |
| `docs/13_organizacao_arquivos.md` | Organização de pastas, código, dados e documentação |
| `docs/34_governanca_exportacao_iqs.md` | Governança comum para decisão humana e pacote IQS |
| `docs/35_contrato_exportacao_iqs.md` | Contrato rígido de layout, encoding, datas e quebra UNIX/LF |
| `docs/36_regras_prodist_copel.md` | Regras PRODIST Módulo 8 e filtros particulares COPEL |
| `docs/37_visao_produto_governanca_midway.md` | Visão de produto, níveis de navegação, React/Streamlit e governança |
| `docs/sprints/README.md` | Planejamento ativo de sprints e regra de transição segura |

## Catálogo de módulos

| Documento | Função |
| --- | --- |
| `docs/modulos/README.md` | Catálogo oficial de módulos de anomalia |
| `docs/modulos/dic_fic_prodist.md` | Cálculo regulatório de DIC, FIC, DMIC, DICRI e DISE |
| `docs/modulos/dec_fec_prodist.md` | Cálculo regulatório de DEC e FEC |
| `docs/modulos/ressarcimento_prodist.md` | Cálculo regulatório da compensação por continuidade |
| `docs/modulos/sobreposicao_uc.md` | Sobreposição total/parcial por UC |
| `docs/modulos/interrupcao_sem_uc.md` | Interrupção/ocorrência sem UC apurável |
| `docs/modulos/componente_causa.md` | Divergência de grupo, componente e causa |
| `docs/modulos/duracao_impacto.md` | Duração suspeita e impacto operacional |
| `docs/modulos/ressarcimento_atipico.md` | Auditoria de ressarcimento incompatível, duplicado ou fora de filtro |
| `docs/modulos/reclamacoes_servicos.md` | Cruzamento com reclamações e serviços |
| `docs/modulos/falha_equipamento_ra.md` | Suspeita de falha de religador/RA |
| `docs/modulos/dia_critico_ise.md` | Dia crítico e ISE |
| `docs/modulos/duplicidade_tipo.md` | Duplicidade por tipo de interrupção |
| `docs/modulos/ajuste_manual_iqs.md` | Ajuste manual governado para IQS |
| `docs/modulos/correcao_9282.md` | Correção especializada `92/82`, sem centralidade no produto |

## Histórico

Os documentos antigos foram movidos para `docs/historico/`.

Eles preservam decisões e contexto, mas não são especificação vigente. Se algum conceito antigo ainda for útil, ele deve ser migrado para um documento ativo ou para um módulo em `docs/modulos/`.

Sprints ativas devem ficar em `docs/sprints/`. Sprints antigas em `docs/historico/sprint/` são apenas memória técnica.

## Regra de manutenção

Antes de criar ou editar documentação, classifique o conteúdo como:

1. norte atual;
2. fluxo operacional;
3. módulo de anomalia;
4. governança/exportação;
5. histórico.

Se o texto fizer `92/82` parecer objetivo principal, reescreva como módulo especializado em `docs/modulos/correcao_9282.md`.
