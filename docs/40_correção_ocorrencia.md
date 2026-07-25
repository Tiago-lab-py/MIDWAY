# Correção de Ocorrência

## Objetivo

Definir o fluxo seguro para transformar a interpretação técnica de uma ocorrência em uma proposta de correção governada, sem alterar diretamente a base regulatória ou o arquivo IQS.

A tela de ocorrências já apoia a leitura humana da ocorrência, interrupções, UC, serviços, reclamações, sobreposições e impactos. A próxima etapa é permitir que o analista registre uma proposta de correção com justificativa, evidências e trilha de aprovação.

## Princípio de Governança

A correção não deve ser aplicada diretamente na base tratada.

Toda ação deve primeiro gerar um registro governado com status, usuário, justificativa, valores originais, valores sugeridos e valores propostos. Somente registros aprovados devem seguir para implantação ou exportação IQS.

## Fluxo Proposto

1. **Buscar e interpretar**
   - Analista localiza ocorrência, interrupção ou UC.
   - Sistema apresenta timeline, serviços, reclamações, apuração UC, ressarcimento e sobreposições.

2. **Propor correção**
   - Analista informa o tipo de correção.
   - Sistema apresenta valor atual e, quando existir, sugestão do algoritmo.
   - Analista informa novo valor e justificativa.

3. **Validar evidências**
   - Sistema registra as evidências usadas na decisão.
   - Regras automáticas podem apontar conflito, baixa confiança ou impacto regulatório.

4. **Enviar para aprovação**
   - Correções pontuais seguem para fila governada.
   - Gestor aprova ou rejeita.

5. **Implantar / exportar IQS**
   - Somente propostas aprovadas entram na geração final do arquivo IQS.

## Tipos de Correção

- **Componente/causa**
  - Ajuste de componente e/ou causa da interrupção.
  - A seleção deve ser guiada por catálogo: **Grupo → Componente → Causa**.
  - O grupo não vem do OMS, mas funciona como filtro humano para reduzir erro de seleção.
  - Campos de componente e causa não devem ser texto livre; o usuário seleciona valores pré-cadastrados da referência IQS.

- **Expurgo / justificativa**
  - Registro de protocolo, motivo ou regra que afeta apuração.

- **UC / interrupção**
  - Ajuste pontual em vínculo de UC, interrupção ou sobreposição identificada.

- **Horário início / fim**
  - Ajuste manual de `DATA_HORA_INIC_INTRP` ou `DATA_HORA_FIM_INTRP`.
  - Deve aparecer como opção direta em **Campo alterado**: `Horário início` ou `Horário fim`.
  - Deve exigir justificativa clara, pois altera duração, DIC/DMIC, DEC/FEC e possível ressarcimento.

- **Sem alteração**
  - Analista registra apenas justificativa técnica para manter o dado original.
  - Na interface, esta ação aparece como botão **Validar sem alteração** ao lado de **Salvar proposta**.
  - A proposta registra `VALID_POS_OPERACAO = S`, sem troca de componente/causa.

- **Cancelar alvo**
  - Cancela uma ocorrência, interrupção ou UC por proposta governada.
  - Não aplica diretamente no IQS sem aprovação.
  - Na interface, esta ação aparece como botão **Cancelar** ao lado de **Salvar proposta**.

## Regras de Cancelamento

Quando o analista selecionar **Cancelar alvo**, o sistema deve montar automaticamente a proposta conforme o alvo:

### Ocorrência ou Interrupção

Para cancelamento de ocorrência inteira ou interrupção específica:

| Campo | Valor proposto |
| --- | --- |
| `ESTADO_INTRP` | `7` |
| `VALID_POS_OPERACAO` | `S` |

Quando o alvo for ocorrência, a regra representa aplicação para todas as interrupções da ocorrência após aprovação.

### UC

Para cancelamento/tratamento de UC:

| Campo | Valor proposto |
| --- | --- |
| `ESTADO_INTRP` | `4` |
| `NUM_MOTIVO_TRAT_DIF_UCI` | `90` |
| `INDIC_SIT_PROCES_INDIC_UCI` | `D` |

Quando o alvo for UC, a regra representa aplicação para todas as linhas da UC selecionada após aprovação.

## Comparação Visual

A tela da proposta deve exibir os dados do alvo selecionado e uma comparação por campo:

- **Verde**: valor original da base.
- **Amarelo**: valor sugerido pelo algoritmo ou regra.
- **Vermelho**: valor editado manualmente pelo analista.

Toda proposta deve preservar os valores originais em `antes` e registrar valores sugeridos/propostos em `depois`.

Para correções manuais comuns, o valor `VALID_POS_OPERACAO = S` deve ser incluído no payload proposto quando aplicável, indicando que a correção proposta considera a validação pela Pós Operação após aprovação.

`Validação pós-operação` não deve aparecer como tipo isolado no combo de correção. A validação sem troca de dados deve ser feita pelo botão **Validar sem alteração**.

Para campos de componente e causa, a interface deve exibir **código + descrição** para facilitar a interpretação humana. A persistência e futura alteração na tabela/IQS devem manter apenas o **código** no campo técnico:

- `COD_COMP_INTRP`: exibir `código - descrição`, salvar apenas `código`.
- `COD_CAUSA_INTRP`: exibir `código - descrição`, salvar apenas `código`.
- `COD_GRUPO_GCR`: usar apenas como filtro funcional de tela; não criar campo técnico no OMS quando a origem não possuir grupo.

Campos temporais como `DATA_HORA_INIC_INTRP` e `DATA_HORA_FIM_INTRP` devem ser editados com controle de data/hora da interface (`datetime-local`) e registrados no formato aceito pela camada técnica/API. A alteração deve ser revisada antes da exportação IQS, pois impacta diretamente os cálculos de duração.

## Campos Mínimos da Proposta

- ANOMES
- Número da ocorrência
- Número da interrupção, quando aplicável
- UC, quando aplicável
- Tipo de correção
- Campo alterado
- Valor original
- Valor sugerido pelo algoritmo
- Valor proposto pelo analista
- Justificativa obrigatória
- Evidências usadas
- Impacto estimado em DIC/CHI
- Impacto estimado em FIC/CI
- Impacto estimado em ressarcimento
- Usuário solicitante
- Status da proposta
- Data/hora da criação
- Usuário aprovador
- Data/hora da aprovação ou rejeição

## Status Sugeridos

- `RASCUNHO`
- `PROPOSTA_PELO_ANALISTA`
- `EM_REVISAO`
- `APROVADA_GESTOR`
- `REJEITADA`
- `EXPORTADA_IQS`
- `CANCELADA`

## Modelo de Tabela Governada

Tabela sugerida: `gov_correcao_ocorrencia`

Campos sugeridos:

- `id_correcao`
- `anomes`
- `num_ocorrencia_adms`
- `num_seq_intrp`
- `num_uc`
- `tipo_correcao`
- `campo_alterado`
- `valor_original`
- `valor_sugerido`
- `valor_proposto`
- `justificativa`
- `evidencias_json`
- `impacto_chi`
- `impacto_ci`
- `impacto_ressarcimento`
- `status`
- `criado_por`
- `criado_em`
- `atualizado_por`
- `atualizado_em`
- `aprovado_por`
- `aprovado_em`
- `motivo_rejeicao`
- `lote_iqs`

## Comportamento na Tela

No modal de ocorrência completa, adicionar uma seção recolhida por padrão:

**Proposta de Correção**

Conteúdo:

- seleção do alvo: ocorrência, interrupção ou UC;
- seleção do valor do alvo em uma única lista dependente do alvo escolhido;
- derivação automática do tipo técnico da correção a partir do campo alterado ou dos botões de ação;
- seleção de grupo, componente e causa em sequência quando a correção for de componente/causa;
- seleção de `Horário início` ou `Horário fim` quando a correção for temporal;
- valor atual;
- sugestão do algoritmo, quando existir;
- novo valor proposto;
- justificativa obrigatória;
- resumo de impacto;
- botão `Cancelar` em vermelho;
- botão `Validar sem alteração` em verde;
- botão `Salvar proposta`;
- botão `Enviar para aprovação`, quando a proposta estiver completa.

## Regras de Segurança

- Não permitir proposta sem justificativa.
- Não permitir edição direta da base IQS.
- Não permitir exportação sem aprovação.
- Registrar usuário e data/hora em todas as ações.
- Se o analista divergir da sugestão do algoritmo, exigir justificativa explícita.
- Manter o valor original sempre preservado.

## Integração com Telas Existentes

- **Ocorrências**
  - Origem da interpretação e criação de proposta.

- **Ajustes Manuais**
  - Lista operacional das propostas humanas.

- **Aprovação**
  - Decisão do gestor.

- **Saída IQS**
  - Exportação final somente de itens aprovados.

## Primeira Implementação Recomendada

Implementar primeiro uma versão segura e limitada:

1. Criar tabela governada.
2. Adicionar formulário de proposta manual no modal da ocorrência.
3. Salvar proposta sem aplicar alteração.
4. Exibir propostas em Ajustes Manuais.
5. Enviar proposta para Aprovação.

Aplicação no IQS deve ficar para uma etapa posterior, após validação do fluxo com analistas e gestores.
