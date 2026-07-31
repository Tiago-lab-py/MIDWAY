# 42 - Orquestrador Power BI: Arquitetura Desacoplada e Efetividade de Tratamento

## 1. Visão Geral da Arquitetura Híbrida
Esta documentação descreve a arquitetura de dados definitiva para o processo de Ressarcimento Preventivo (Midway). O modelo abandona a dependência exclusiva de arquivos Excel estáticos e introduz o **Power BI como Orquestrador Central**, unindo a robustez do processamento local (Python/DuckDB) com a flexibilidade e colaboração da nuvem (Microsoft Lists).

---

## 2. O Papel do Microsoft Lists (A Interface do Analista)

Para que o analista tenha a melhor experiência possível e **não precise abrir duas telas** (um arquivo para ler e outro para digitar), a lista no Microsoft Lists (SharePoint) será construída de forma autossuficiente.

### 2.1. Estrutura da Lista
A lista será criada espelhando as principais colunas que hoje existem no Excel, garantindo que o analista tenha todo o contexto visual imediatamente:
* **Colunas de Contexto (Vindas da Carga Inicial):** `NUM_OCORRENCIA_ADMS`, `RA_1_UC`, `DURACAO`, `RISCO_TOTAL_ESTIMADO`, etc.
* **Colunas de Input Humano (Tratamento):** `Status da Análise`, `Plano de Ação`, `Data do Tratamento`, `Responsável`, `Comentários`.

### 2.2. Vantagens Operacionais
- **Single Pane of Glass:** O analista entra em apenas um lugar (O Lists no navegador ou no Teams) e toma sua decisão baseada nas colunas de contexto que já estão ali na tela.
- **Auditoria Nativa:** O Lists grava automaticamente o Histórico de Versão (quem alterou o status e a que horas).
- **Sem Travamentos:** Edição simultânea em tempo real por dezenas de analistas sem bloqueios de arquivo.

---

## 3. O Papel do Python e Parquet (A Fonte da Verdade do Midway)

O script Python local (`ressarcimento_diario.py`) é o motor de engenharia de dados. Ele se encarrega do trabalho pesado e atua de forma totalmente autônoma.

### 3.1. Processo Incremental Diário
1. O Python calcula todas as durações, métricas e cruza com os bancos de dados brutos (ADMS, GEO, DBGUO).
2. Ele exporta o resultado atualizado para um formato ultraleve: **Arquivo Parquet** na rede `Y:\VDSED\dados_pos\ressarcimento`.
3. A lógica de atualização (Upsert) de novos registros é feita no próprio Python (ou via substituição do Parquet Mestre). O Parquet sempre reflete a "Realidade Atual" registrada no sistema.

---

## 4. O Cérebro: Power BI (Medição de Efetividade)

O Power BI atua como o Maestro da arquitetura. Ele não apenas exibe gráficos, mas **cruza dois mundos diferentes para gerar inteligência de negócio**.

### 4.1. Conexão de Múltiplas Fontes
O Power BI realiza a leitura simultânea de:
- **Fonte A (Realidade Sistêmica):** O arquivo `.parquet` gerado pelo Python na rede VDSED.
- **Fonte B (Ação Humana):** A tabela do Microsoft Lists via conector nativo da nuvem.
- Ambas as fontes são conectadas (relacionadas) no Power BI utilizando a chave primária `NUM_OCORRENCIA_ADMS`.

### 4.2. Avaliação de Efetividade (O Grande Valor do Negócio)
Ao ler o Parquet na atualização diária, o Power BI compara automaticamente os dados frescos que vêm do sistema Midway com o que está preenchido no Microsoft Lists.

**Exemplo de Caso de Uso no PBI:**
1. O Analista entrou no Lists e marcou a ocorrência X como *"Tratada: Despachada equipe de poda"*.
2. O Power BI cruza essa informação com o Parquet dos dias seguintes.
3. Se a duração das falhas associadas àquela chave reduziu a zero (segundo o Parquet), o Power BI exibe no painel gerencial: **Ação Efetiva (Verde)**.
4. Se o sistema Midway (Parquet) mostra que a chave continuou caindo e estourou as metas, o Power BI exibe: **Tratamento Ineficiente (Vermelho)**.

Dessa forma, abandonamos as "planilhas de preenchimento" cegas e passamos a ter um **Ciclo de Vida completo da ocorrência**, onde medimos se o esforço humano da equipe de análise realmente refletiu em melhorias físicas no sistema elétrico.
