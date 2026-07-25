# Correção dos Arquivos de Exportação

Este documento estabelece as diretrizes e regras de negócio para prevenir, tratar e auditar inconsistências nos arquivos de exportação do IQS.

## 1. Tratamento Rigoroso de Datas (Tamanho e Formato)
O arquivo final IQS não deve conter inconsistências de tamanho em colunas de datas geradas por valores nulos ou faltantes de hora (ex: datas incompletas sem 19 caracteres).
**Regra:** O `helper` oficial de exportação deve garantir estritamente a máscara `"dd/mm/aaaa hh:mm:ss"` para as colunas `DATA_HORA_INIC_INTRP`, `DATA_HORA_FIM_INTRP` e `DTHR_INICIO_INTRP_UC`. Omissão da hora é proibida em qualquer pacote IQS ou de auditoria.

## 2. Duração Negativa (Hora Invertida)
Interrupções em que a `DATA_HORA_FIM_INTRP` é menor que a `DATA_HORA_INIC_INTRP` não devem ser ajustadas automaticamente para evitar corrupção dos dados de origem, e não pertencem ao exportador.
**Regra:** Não devem ser exportadas. A ocorrência deve ser identificada por um módulo específico de anomalia (Duração Negativa / Invertida) e encaminhada à **Fila Técnica** para tratamento 100% manual.

## 3. Recálculo Automático do CONS_INTRP (Usuários Afetados)
Divergências entre a contagem real de consumidores presentes no arquivo (após aplicação de regras de expurgo ou descarte) e o total indicado na coluna `CONS_INTRP` causam rejeição do pacote ou análises furadas.
**Regra:** Ao final do tratamento e antes da exportação, o sistema deve sobrescrever a coluna `CONS_INTRP` executando um `COUNT` definitivo agrupado pelo código da interrupção (`PID_INTRP_CONJTO_PIN`). Isso garante que a coluna represente a exata realidade do arquivo que está sendo exportado.

## 4. Inconsistência de Protocolos (Expurgos)
Discrepâncias entre o preenchimento de protocolo genérico da interrupção e o protocolo pontual da UC são esperadas em cenários de Dia Crítico ou ISE.
**Regra:** **Não fazer ajuste automático.** Se houver diferença entre os campos de protocolo e os respectivos campos de tipo de protocolo, isso deve ser levado para a **Fila Técnica** para tratativa manual. O sistema não pode forçar preenchimento ou limpeza.
