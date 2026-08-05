# 43 - Simulação ISE por Janela

## Objetivo

A Simulação ISE por Janela calcula o potencial de Interrupção em Situação de Emergência (ISE) apenas dentro de janelas de tempo informadas pelo usuário (por Regional). 
Além do cálculo bruto de indicadores (CHI/CI), o módulo simula o impacto financeiro no ressarcimento, projetando a economia gerada (DISE) caso aquelas ocorrências sejam reclassificadas.

## 1. Regra de Janela (Intersecção de Tempo)

Só entram no cálculo eventos que cruzam a janela selecionada pela Regional.

Quando o evento começa antes da janela ou termina depois dela, a duração considerada para o ISE é **apenas a interseção** entre o evento e a janela.
- `Início Válido = MAX(início do evento, início da janela)`
- `Fim Válido = MIN(fim do evento, fim da janela)`

Assim, o CHI da simulação por janela não usa automaticamente a duração total do evento. Ele usa a duração estritamente limitada pela janela.

## 2. Indicadores (Bruto e Líquido)

| Campo | Interpretação |
| --- | --- |
| `ISE_CHI_BRUTO_REFERENCIA` | CHI bruto (em horas) dentro da janela para verificar se houve potencial ISE. |
| `ISE_CHI_LIQUIDO_RECLASSIFICAVEL` | CHI líquido dentro da janela para medir quanto poderá ser reclassificado (eventos que já não possuem outra isenção). |
| `ISE_CI_BRUTO_REFERENCIA` | CI bruto dentro da janela. |
| `ISE_CI_LIQUIDO_RECLASSIFICAVEL` | CI líquido dentro da janela. |

## 3. Causas Elegíveis

São elegíveis para cômputo no ISE apenas as seguintes causas (`COD_CAUSA_INTRP`):
`2, 4, 5, 6, 7, 8, 9, 13, 15, 23, 24, 28, 39, 40, 41, 52, 54, 69, 82`

**Observação sobre o código 52:**
A causa de interrupção `COD_CAUSA_INTRP = 52` é elegível para ISE. No entanto, ela não deve ser confundida com a regra de compensação `COD_COMP_INTRP = 52`, que continua sendo uma regra separada.

## 4. O "Efeito Gangorra" do Dia Crítico

Esta é a regra de negócio mais sensível da simulação financeira.
A aplicação de uma janela ISE isenta as interrupções que ocorrem dentro dela. No entanto, isso reduz a volumetria de ocorrências no dia para o Conjunto Elétrico (CEA), o que pode fazer com que ele perca o enquadramento no "Dia Crítico".

Para que a simulação seja exata à norma da ANEEL, a Gangorra segue o seguinte algoritmo no banco de dados DuckDB:

1. O sistema faz um `ATTACH` dinâmico do banco bruto de serviços (`adms_servicos_raw_{anomes}.duckdb`).
2. Verifica-se o cruzamento da chave `PID_INTRP_SRVE` = `NUM_SEQ_INTRP`.
3. **Regra de Deslocamento:** Apenas ocorrências isentadas que possuam o campo `DTHR_SAIDA_SRV` preenchido (ou seja, houve real despacho e deslocamento de equipe a campo) são computadas para abater da meta oficial daquele conjunto.
4. O sistema cruza esse número com o arquivo base de metas: `data\input\META_CONJUNTO_DIA_CRITICO.csv`.
5. **Perda de Isenção (TIPO 0):** Se a volumetria cair abaixo da `META` estabelecida, as ocorrências que restaram naquele dia **perdem a classificação de Dia Crítico TIPO 1**, passando a ser TIPO 0 (Ocorrências normais penalizáveis).
6. Como consequência, essas ocorrências passam a gerar multas de ressarcimento (DIC, FIC, DMIC).

A simulação financeira final exibida pelo módulo (Ganho DISE) já contabiliza essa possível perda de Dia Crítico para refletir o cenário real financeiro.

## 5. Gestão, Relatórios e Implantação Oficial (IQS)

O sistema possui uma interface (React) para Gestão de Janelas com ciclo de vida completo:

1. **Gestão e Reprocessamento:** Janelas em estado de `Simulação` podem ser editadas, excluídas ou "Reprocessadas" a qualquer momento. O recálculo garante que apenas a própria janela em simulação seja processada por vez (além daquelas que já foram autorizadas).
2. **Relatório Executivo HTML:** Ao final do cálculo, a plataforma gera dinamicamente um relatório em formato Standalone HTML através da API.
   - O relatório utiliza a biblioteca **Plotly** para demonstrar visualmente a "Curva S" da Tempestade (CHI Acumulado) somada ao Histograma Horário.
   - O Histograma é apresentado na modalidade de *Stacked Bar Chart* (Barras Empilhadas), separando o impacto horário pelas diferentes Regionais afetadas.
3. **Implantação (Injeção no IQS):** Quando aprovadas, as janelas recebem o status `Autorizada`. A partir deste momento, ao se processar o relatório de exportação do painel `Saídas IQS`, o motor de extração oficial lê as janelas autorizadas e injeta a regra (mudando ocorrências para TIPO 6 e processando a Gangorra), garantindo que o arquivo `.csv` enviado à ANEEL possua exatamente a mesma matemática do simulador.

## 6. Arquitetura do Módulo (Simulação Exata via PRODIST)

O módulo foi refatorado para garantir **100% de precisão matemática**, abandonando estimativas teóricas e reaproveitando as funções oficiais de cálculo da concessionária:

- **Backend (FastAPI - Background Tasks):** `api/routes/ise.py`. 
  - Ao disparar a simulação, a API não trava. O cálculo pesado é deslocado para uma rotina assíncrona.
  - Um banco volátil em memória RAM (`:memory:`) do DuckDB é criado. A tabela oficial de ocorrências (`gold_apuracao_uc`) é clonada para `gold_apuracao_uc_ise`.
  - A manipulação de eventos ISE e o recálculo do Dia Crítico (Gangorra) ocorrem estritamente na memória, preservando a base oficial (`adms_iqs_processed`).
- **Reaproveitamento Oficial:** O motor executa nativamente as funções `criar_gold_continuidade_uc` e `criar_gold_ressarcimento_prodist` (passando o parâmetro `sufixo="_ise"`), garantindo que as regras da ANEEL sejam aplicadas exatamente da mesma forma que o faturamento de produção.
- **Controle Auditável:** As janelas criadas serão salvas localmente em `data/control/janelas_ise.json`.
- **Frontend (React):** `IseSimulation.jsx`. Nova tela contendo a Gestão de Janelas (com polling assíncrono) e o Simulador Financeiro que confronta as apurações reais `Sem ISE` vs `Com ISE`.
