# Plano de Aperfeiçoamento das Telas - MIDWAY 7.0.0

Data: `2026-07-11`

## Objetivo

Evoluir as telas atuais do MIDWAY, que ainda estão em nível inicial, para uma aplicação operacional com:

- análise avançada dos dados;
- interação por perfil;
- governança de alterações;
- fluxo `Analista -> Gestor -> IQS`;
- controle administrativo de usuários e permissões;
- rastreabilidade completa das decisões.

As referências informadas foram:

- `Tiago-lab-py/analise_ocorrencia`;
- `Tiago-lab-py/ADMStoIQS`.

Observação: nesta etapa, os repositórios não estavam acessíveis pelo índice público/web utilizado no ambiente. Portanto, este plano usa essas referências como direção conceitual: análise de ocorrência, transformação ADMS para IQS, revisão operacional, aprovação e exportação governada.

## Princípio de Produto

O MIDWAY deve deixar de ser apenas um painel e passar a ser uma esteira governada:

```text
Dados ADMS/IQS
  -> Análise avançada
  -> Sugestão de ajuste
  -> Registro de alteração
  -> Aprovação do gestor
  -> Implantação/exportação IQS
  -> Auditoria
```

## Perfis e Responsabilidades

### Analista

Pode:

- consultar dados;
- filtrar ocorrências;
- comparar ADMS x IQS;
- analisar evidências;
- registrar proposta de alteração;
- anexar/registrar justificativa;
- acompanhar status das propostas.

Não pode:

- aprovar alteração final;
- exportar ajuste para implantação oficial no IQS;
- criar usuários;
- alterar perfis.

### Gestor

Pode:

- consultar análises consolidadas;
- revisar propostas do analista;
- aprovar ou rejeitar alterações;
- autorizar tratativas em massa;
- liberar implantação/exportação no IQS;
- acompanhar indicadores de qualidade e risco.

Não deve:

- alterar dados sem justificativa;
- atuar como administrador de usuários, exceto se também tiver perfil `ADM`.

### ADM

Pode:

- criar usuários;
- bloquear/inativar usuários;
- alterar perfis;
- consultar sessões;
- revisar auditoria;
- aplicar scripts SQL versionados;
- configurar parâmetros operacionais.

Não deve:

- aprovar tecnicamente alterações de negócio sem papel gestor.

## Transformar Páginas em Funções Controladas por Perfil

Cada página deve ser composta por funções/módulos com permissões explícitas.

Modelo sugerido:

```text
pagina
  -> função de leitura
  -> função de análise
  -> função de proposta
  -> função de aprovação
  -> função de exportação
  -> função administrativa
```

Exemplo:

```text
Executivo 92/82
  leitura_painel_9282: ANALISTA, GESTOR, ADM
  propor_ajuste_9282: ANALISTA, GESTOR
  aprovar_ajuste_9282: GESTOR
  autorizar_massa_9282: GESTOR
  auditar_9282: GESTOR, ADM
```

## Matriz Inicial de Permissões

| Função | Analista | Gestor | ADM |
|---|---:|---:|---:|
| Ver dashboard | Sim | Sim | Sim |
| Ver qualidade de interrupções | Sim | Sim | Sim |
| Ver SQL versionado | Não | Sim | Sim |
| Executar SQL | Não | Não | Sim |
| Ver fila técnica | Sim | Sim | Sim |
| Criar proposta de alteração | Sim | Sim | Não recomendado |
| Editar proposta própria pendente | Sim | Sim | Não recomendado |
| Aprovar proposta | Não | Sim | Não recomendado |
| Rejeitar proposta | Não | Sim | Não recomendado |
| Autorizar massa 92/82 | Não | Sim | Sim, emergencial |
| Exportar para IQS | Não | Sim | Sim |
| Criar usuário | Não | Não | Sim |
| Alterar perfil | Não | Não | Sim |
| Ver sessões ativas | Não | Não | Sim |
| Ver auditoria completa | Não | Sim | Sim |

## Novo Desenho das Páginas

## 1. Dashboard

Objetivo:

- visão geral da saúde operacional.

Melhorias:

- filtros por `ANOMES`;
- cards com tendência;
- alertas de pendências;
- volume de propostas pendentes;
- propostas aprovadas aguardando exportação;
- jobs em execução;
- qualidade dos dados;
- indicador de risco.

Componentes:

- card `Dados processados`;
- card `Alterações pendentes`;
- card `Aprovações pendentes`;
- card `Exportações IQS`;
- card `Falhas de validação`;
- gráfico de status das propostas;
- lista de alertas recentes.

## 2. Qualidade de Interrupções

Objetivo:

- permitir análise avançada dos dados antes da proposta.

Melhorias:

- filtros por regional, conjunto, alimentador, causa, componente;
- busca por ocorrência/interrupção;
- comparação ADMS x IQS;
- detecção de inconsistências;
- ranking por DIC/FIC/UCS;
- evidências de serviço;
- evidências de reclamação;
- histórico de alterações anteriores;
- botão `Criar proposta de alteração`.

Funções:

```text
visualizar_interrupcao
comparar_adms_iqs
listar_evidencias
calcular_risco
criar_proposta_alteracao
```

Perfil:

- `ANALISTA`: cria proposta;
- `GESTOR`: cria ou aprova;
- `ADM`: consulta.

## 3. Executivo

Objetivo:

- tomada de decisão e aprovação.

Melhorias:

- separar `recomendações automáticas`, `pendências do analista`, `risco alto`;
- detalhe de impacto antes da aprovação;
- simulação do efeito da aprovação;
- aprovação individual;
- aprovação em lote;
- rejeição com justificativa;
- trilha de auditoria visível.

Funções:

```text
listar_pendencias_aprovacao
simular_impacto_iqs
aprovar_alteracao
rejeitar_alteracao
autorizar_lote
liberar_exportacao_iqs
```

Perfil:

- `GESTOR`: aprova/rejeita/libera;
- `ADM`: consulta e emergência;
- `ANALISTA`: consulta status, sem aprovação.

## 4. Ajuste Manual / Fila Técnica

Objetivo:

- tratar registros problemáticos.

Melhorias:

- fila com filtros por prioridade/status/fonte/evidência;
- abrir item em painel lateral;
- visualizar evidências;
- preencher nova causa/componente;
- salvar rascunho;
- enviar para aprovação;
- anexar justificativa;
- histórico do item.

Status sugeridos:

```text
ABERTA
EM_ANALISE
PROPOSTA_CRIADA
AGUARDANDO_APROVACAO
APROVADA
REJEITADA
APLICADA
CANCELADA
```

## 5. SQL

Objetivo:

- governar estrutura do banco e consultas.

Melhorias:

- listar scripts versionados;
- mostrar status aplicado/não aplicado;
- mostrar checksum do script;
- registrar aplicação;
- bloquear execução livre para não-ADM;
- permitir consultas somente leitura para Gestor.

Funções:

```text
listar_scripts
validar_checksum
registrar_aplicacao_sql
executar_sql_controlado
```

Perfil:

- `ADM`: aplica;
- `GESTOR`: consulta;
- `ANALISTA`: sem acesso ou acesso restrito.

## 6. Alterações

Objetivo:

- controlar todo ciclo de vida das mudanças.

Melhorias:

- criar proposta;
- editar proposta pendente;
- comparar antes/depois;
- aprovar/rejeitar;
- implantar no IQS;
- cancelar;
- exportar trilha.

Campos essenciais:

```text
id_alteracao
anomes
modulo
entidade
id_entidade
tipo_alteracao
status_alteracao
antes
depois
justificativa
solicitado_por
aprovado_por
criado_em
atualizado_em
```

## 7. Auditoria

Objetivo:

- rastrear quem fez o quê, quando e por quê.

Melhorias:

- filtro por usuário;
- filtro por evento;
- filtro por entidade;
- linha do tempo;
- exportação da auditoria;
- destaque para ações sensíveis.

Eventos mínimos:

```text
LOGIN
LOGOUT
PROPOSTA_CRIADA
PROPOSTA_EDITADA
PROPOSTA_APROVADA
PROPOSTA_REJEITADA
AUTORIZACAO_MASSA
EXPORTACAO_IQS
USUARIO_CRIADO
PERFIL_ALTERADO
SQL_APLICADO
```

## 8. Governança / Usuários

Objetivo:

- administração de usuários e perfis.

Melhorias:

- criar usuário;
- alterar perfil;
- bloquear usuário;
- resetar senha;
- ver sessões ativas;
- revogar sessão;
- exigir justificativa para mudança de perfil.

Perfil:

- apenas `ADM`.

## 9. Configurações

Objetivo:

- parametrizar ambiente.

Melhorias:

- ambiente atual;
- schema;
- API URL;
- versão;
- parâmetros de regra;
- limites de lote;
- status PostgreSQL;
- status DuckDB;
- status de jobs.

## Modelo de Fluxo de Alteração

### Passo 1 - Analista cria proposta

```text
Status: PENDENTE
Solicitado por: analista
Justificativa obrigatória
Antes/depois obrigatórios
```

### Passo 2 - Gestor revisa

```text
Pode aprovar
Pode rejeitar
Pode pedir correção
Justificativa obrigatória
```

### Passo 3 - Implantação IQS

```text
Somente propostas aprovadas
Geração de exportação controlada
Registro em midway_exportacao_iqs
Auditoria de exportação
```

## Arquitetura Técnica Recomendada

### Backend FastAPI

Criar serviços por domínio:

```text
midway/api/routes/
  auth.py
  dashboard.py
  qualidade.py
  executivo.py
  fila_tecnica.py
  ajustes.py
  alteracoes.py
  auditoria.py
  governanca.py
  sql.py

midway/api/services/
  auth_service.py
  permissao_service.py
  alteracao_service.py
  auditoria_service.py
  exportacao_iqs_service.py
  qualidade_service.py
```

### Frontend React

Separar por páginas e componentes:

```text
frontend/src/
  api/
  components/
  pages/
  auth/
  layouts/
  hooks/
```

### Banco PostgreSQL

Complementar tabelas:

```text
midway_usuario
midway_sessao
midway_permissao_funcao
midway_alteracao_registro
midway_aprovacao_alteracao
midway_exportacao_iqs
midway_auditoria_evento
midway_sql_aplicado
```

## Backlog por Sprint

## Sprint A - Refatorar Frontend por Função

Entregas:

- separar `App.jsx` em páginas;
- criar `authContext`;
- criar `apiClient`;
- criar `ProtectedPage`;
- criar matriz de permissões no frontend;
- esconder botões por perfil.

## Sprint B - Alterações Governadas

Entregas:

- tela de criação de proposta;
- API de proposta;
- status de proposta;
- antes/depois;
- justificativa obrigatória;
- auditoria.

## Sprint C - Aprovação Gestor

Entregas:

- fila de aprovação;
- aprovar/rejeitar;
- simular impacto;
- bloquear aprovação pelo próprio solicitante;
- registrar aprovado por.

## Sprint D - Exportação IQS Governada

Entregas:

- exportar somente aprovados;
- registrar exportação;
- download controlado;
- lote de exportação;
- auditoria de envio.

## Sprint E - Administração e Segurança

Entregas:

- criar usuário;
- alterar perfil;
- bloquear usuário;
- resetar senha;
- trocar senha;
- revogar sessão;
- tela de permissões.

## Sprint F - Análise Avançada

Entregas:

- filtros avançados;
- ranking de risco;
- drill-down de ocorrência;
- timeline ADMS/IQS;
- gráficos por regional/conjunto/alimentador;
- comparação serviço/reclamação/referência IQS.

## Boas Práticas

- Nenhuma alteração sem justificativa.
- Nenhuma aprovação sem perfil `GESTOR`.
- Nenhum SQL livre para usuário comum.
- Nenhuma senha em texto puro.
- Nenhum token salvo em banco sem hash.
- Toda ação sensível deve gerar auditoria.
- Toda exportação IQS deve ter lote e responsável.
- A tela deve mostrar ao usuário por que uma ação está bloqueada.

## Prioridade Recomendada

1. Refatorar frontend por páginas/componentes.
2. Criar fluxo de proposta de alteração para Analista.
3. Criar fluxo de aprovação para Gestor.
4. Criar implantação/exportação IQS governada.
5. Criar administração completa de usuários.
6. Evoluir análise avançada e dashboards.

## Checkpoint Implementado

Primeira implementação operacional:

- API para criar proposta de alteração;
- API para aprovar proposta;
- API para rejeitar proposta;
- bloqueio de autoaprovação pelo próprio solicitante;
- auditoria dos eventos de decisão;
- tela React `Alterações` com formulário de proposta;
- ações de aprovação/rejeição visíveis apenas para `GESTOR` e `ADM`;
- teste local do fluxo `ANALISTA -> GESTOR`.

Segunda implementação operacional:

- tabela de geração IQS governada por pacote;
- justificativa única do gestor para um ou vários modelos/arquivos;
- modelos iniciais:
  - sobreposição total por UC;
  - sobreposição parcial por UC;
  - interrupção sem UC remanescente;
  - ajuste componente/causa `92/82` por reclamação;
  - regra rígida grupo/componente/causa;
- página React `Geração IQS`;
- histórico de pacotes aprovados;
- endpoint de detalhe completo da ocorrência;
- pop-up/modal ao clicar na ocorrência com resumo, interrupções, serviços ADMS, apuração UC e reclamações vinculadas.
- painel executivo com DEC/FEC antes e depois das tratativas, comparando RAW contra apuração prévia pós-correções.

Observação de evidência:

- o serviço ADMS é buscado no RAW `adms_servicos_raw_{anomes}.duckdb`;
- o vínculo usa `PID_INTRP_SRVE` do serviço contra `NUM_SEQ_INTRP` das interrupções da ocorrência;
- quando não houver serviço, a tela mantém a evidência de reclamação e apuração UC para orientar a revisão técnica.

Observação metodológica DEC/FEC:

- `DEC_BRUTO` e `DEC_LIQUIDO` não representam, por si só, antes/depois da tratativa; eles separam famílias de apuração por protocolo;
- o ganho executivo deve comparar o RAW antes das correções contra o resultado da apuração prévia;
- a implementação operacional usa `raw_db.hiadms_raw` para o cenário antes e `gold_apuracao_previa` para o cenário depois;
- o cenário RAW usa `ESTADO_INTRP = 4`, duração mínima de 3 minutos e UC faturada;
- o cenário pós-tratamento usa a apuração prévia já resultante das correções de sobreposição total, sobreposição parcial e interrupção sem UC remanescente;
- bruto considera todos os protocolos e líquido considera `TIPO_PROTOC_JUSTIF_UCI = 0`.

Próxima implementação recomendada:

- substituir `prompt` de aprovação/rejeição por modal governado;
- criar tela administrativa para criar usuários;
- criar tela de troca de senha;
- ligar propostas aprovadas ao lote físico de exportação IQS;
- implementar a geração física dos CSVs a partir dos pacotes aprovados.
