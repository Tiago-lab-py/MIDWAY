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
4. O sistema cruza esse número com o arquivo base de metas: `data/input/META_CONJUNTO_DIA_CRITICO.csv`.
5. **Perda de Isenção (TIPO 0):** Se a volumetria cair abaixo da `META` estabelecida, as ocorrências que restaram naquele dia **perdem a classificação de Dia Crítico TIPO 1**, passando a ser TIPO 0 (Ocorrências normais penalizáveis).
6. Como consequência, essas ocorrências passam a gerar multas de ressarcimento (DIC, FIC, DMIC).

A simulação financeira final exibida pelo módulo (Ganho DISE) já contabiliza essa possível perda de Dia Crítico para refletir o cenário real financeiro.

### 4.1 Cenário Otimizado (Algoritmo da Mochila / Knapsack)

Como o "Efeito Gangorra" pode gerar enormes prejuízos financeiros em determinados Conjuntos, o módulo possui uma passagem adicional de otimização de cenário:
- A regra de negócio principal exige que a soma do indicador `CHI` justificado por ISE no evento ultrapasse a cota mínima de **700.000 horas** na janela.
- O algoritmo calcula individualmente o prejuízo ou lucro de cada Conjunto após a aplicação da janela do ISE.
- Todos os Conjuntos que geram lucro (Economia líquida $\ge$ 0) são automaticamente selecionados para implantação.
- Se a soma de CHI desses conjuntos já for $\ge$ 700k, a seleção encerra. Caso contrário, o algoritmo ordena os conjuntos que dão "prejuízo" (Efeito Gangorra) do menor impacto negativo para o maior, adicionando-os gradativamente à seleção até bater a cota de 700k de CHI.
- Os Conjuntos restantes (com os maiores prejuízos gerados pela quebra do Dia Crítico) ficam de fora e são "blindados" do ISE, preservando o benefício anterior.

## 5. Gestão, Relatórios e Implantação Oficial (IQS)

O sistema possui uma interface (React) para Gestão de Janelas com ciclo de vida completo:

1. **Gestão e Reprocessamento:** Janelas em estado de `Simulação` podem ser editadas, excluídas ou "Reprocessadas" a qualquer momento. O recálculo garante que apenas a própria janela em simulação seja processada por vez. O nome oficial dos Conjuntos (`NOME_CEA`) é cruzado em tela usando o arquivo oficial `data/input/Referencia_DEC FEC CONJUNTO Ano_Copel.csv`.
2. **Relatório Executivo HTML:** Ao final do cálculo, a plataforma gera dinamicamente um relatório em formato HTML Standalone:
   - Utiliza a biblioteca **Plotly** para demonstrar a "Curva S" da Tempestade (CHI Acumulado) somada ao Histograma Horário (Stacked Bar Chart).
   - Apresenta uma **Matriz de Impacto por Conjunto**, no formato pivotado, isolando as transições de CI e CHI entre os protocolos *0 - Líquido*, *1 - Dia Crítico* e *6 - ISE* lado a lado.
3. **Implantação (Injeção no IQS):** O sistema agora oferece dois caminhos de implantação distintos:
   - **Implantar Completo:** Transforma em ISE (TIPO 6) todas as ocorrências elegíveis mapeadas na janela.
   - **Implantar Otimizado:** Transforma em ISE (TIPO 6) *apenas* as ocorrências pertencentes aos Conjuntos Elétricos selecionados pelo Algoritmo da Mochila (preservando o Dia Crítico nos conjuntos mais onerosos).
   
   Quando aprovadas, as janelas recebem o status `Autorizada`. O motor de extração oficial `Saídas IQS` lerá o tipo de implantação gravado (`completo` ou `otimizado`) e fará a reclassificação exata no banco consolidado e envio à ANEEL.

## 6. Arquitetura do Módulo (Simulação Exata via PRODIST)

O módulo foi refatorado para garantir **100% de precisão matemática**, abandonando estimativas teóricas e reaproveitando as funções oficiais de cálculo da concessionária:

- **Backend (FastAPI - Background Tasks):** `api/routes/ise.py`. 
  - O cálculo pesado é deslocado para uma rotina assíncrona.
  - Um banco volátil em memória RAM (`:memory:`) do DuckDB é criado, gerando tabelas simuladas (`_ise` para completo, e `_otimizado` para o filtro da mochila).
  - A manipulação de eventos ISE e o recálculo do Dia Crítico ocorrem estritamente na memória, preservando a base oficial (`adms_iqs_processed`).
- **Reaproveitamento Oficial:** O motor executa nativamente as funções `criar_gold_continuidade_uc` e `criar_gold_ressarcimento_prodist`, passando o sufixo apropriado para garantir que as regras ANEEL da simulação sejam idênticas ao faturamento real.
- **Controle Auditável:** As janelas são persistidas localmente em `data/control/janelas_ise.json`.
- **Frontend (React):** `IseSimulation.jsx`. Tela de Simulador Financeiro que confronta as apurações reais `Sem ISE`, `Com ISE (Projeção Completa)` e `ISE Otimizado`, exibindo indicadores detalhados, matriz de ganhos em R$ e sinalização visual (⭐) das UCs incluídas na blindagem financeira.
