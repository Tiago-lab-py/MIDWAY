# Proposta de Arquitetura: Governança, Rastreabilidade e Validação IQS

## 1. Análise do Fluxo Atual (As-Is)
Atualmente, os **Outliers Brutos** estão sendo capturados e marcados no banco de dados (`auditoria_outliers_bruto`) durante o tratamento automático. No entanto, foi verificado que o sistema **não bloqueia a exportação dessas ocorrências para o IQS**, tratando-as apenas como uma "auditoria preventiva" que segue no fluxo de massa.
Após a geração dos arquivos CSV, a plataforma perde a visibilidade se o sistema da Aneel (IQS) de fato internalizou as alterações e não apura com precisão o "antes e depois" efetivo.

## 2. Proposta de Solução (To-Be)
Para atuar como Analista Sênior garantindo total Governança, Auditoria e Rastreabilidade, o novo fluxo deve incorporar um ciclo fechado (Closed-loop) de validação e cálculo de ganhos.

### 2.1. Bloqueio Preventivo (Fila de Aprovação)
As anomalias classificadas como `OUTLIER_BRUTO` e `ANALISE_TECNICA_9282` devem ter a opção de **exclusão automática do lote atual do IQS** até que um analista dê o "De Acordo". 
* **Ação:** Modificar a geração dos arquivos CSV para omitir ocorrências com status pendente nessas filas.

### 2.2. Integração de Retorno do IQS (Feedback Loop)
A entrada de dados no IQS é feita via CSV e possui críticas/validações próprias.
* **Ação:** Criar um módulo de importação de **Log de Processamento do IQS** (ou integração via API, se disponível).
* **Mecanismo:** O sistema lerá o relatório de retorno do IQS, fará o parse cruzando os protocolos processados com a tabela `midway_anomalia` através do `NUM_OCORRENCIA_ADMS` e atualizará o status final da tratativa (ex: `EFETIVADO_IQS`, `REJEITADO_IQS`).

### 2.3. Painel do Gestor / Auditoria (Rastreabilidade)
Para garantir que Gestores e Auditores tenham segurança sobre o processo:
* Criação de uma tabela/painel de conciliação: `Lote Enviado` x `Lote Aprovado IQS` x `Registros Rejeitados`.
* Log inalterável (Append-only) de todas as edições manuais e de massa vinculadas diretamente a qual remessa CSV do IQS aquele registro foi enviado.

### 2.4. Cálculo Efetivo dos Ganhos (DEC, FEC, DIC, FIC e Ressarcimento)
Para sabermos os ganhos reais, a plataforma irá registrar o "Antes" e o "Depois".
* **Ganhos Individuais (DIC / FIC / Ressarcimento):**
  * O cálculo subtrairá a métrica final validada pelo IQS da métrica "Bruta" original do ADMS. 
  * `Ganho Financeiro = SUM(RESSARCIMENTO_BRUTO - RESSARCIMENTO_IQS)`
* **Ganhos Coletivos (DEC / FEC):**
  * O recálculo ocorrerá no nível de conjunto, aferindo as penalidades evitadas de ultrapassagem dos limites regulatórios devido à correção do outlier.

## Open Questions (Questões para Definição Conjunta)

> [!WARNING]
> Como a concessionária tem acesso aos logs de retorno do IQS hoje? É um arquivo de validação baixado manualmente no portal da ANEEL ou existe alguma API de integração? Isso define se precisaremos construir uma tela de upload de "Retorno IQS" ou um Job automático.

> [!IMPORTANT]
> Devemos travar *todas* as anomalias da geração CSV automática até serem aprovadas (Opt-in) ou deixamos seguir com exceção dos Outliers que marcaremos para retenção (Opt-out)?
