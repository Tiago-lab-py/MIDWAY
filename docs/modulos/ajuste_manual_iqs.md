# Módulo `AJUSTE_MANUAL_IQS`

## Objetivo

Permitir que analistas e gestores registrem decisões humanas governadas e gerem arquivo IQS apenas com ajustes aprovados.

## Escopo

- ocorrência;
- interrupção;
- UC;
- pacote de exportação.

## Fontes

- propostas de alteração;
- `midway_ajuste_iqs`;
- `midway_autorizacao_executiva`;
- `midway_exportacao_iqs`;
- `adms_iqs_export`;
- módulos de anomalia.

## Critérios de uso

1. Existe evidência suficiente para ajuste.
2. A proposta foi registrada com antes/depois.
3. O gestor aprovou.
4. O exportador encontrou a linha original no layout IQS.

## Evidências

- módulo de origem;
- justificativa;
- campos antes/depois;
- usuário solicitante;
- usuário aprovador;
- data/hora da decisão.

## Impacto

- governança;
- rastreabilidade;
- controle de envio ao IQS;
- redução de ajustes manuais fora do sistema.

## Ação sugerida

- Registrar proposta.
- Aprovar/rejeitar.
- Gerar pacote de exportação IQS.

## Campos IQS afetados

Qualquer campo permitido pelo contrato de exportação, com destaque para:

- datas;
- estado;
- causa/componente;
- motivo de tratamento;
- validação Pós.

## Exportação IQS

Somente ajustes aprovados. O arquivo deve respeitar `docs/35_contrato_exportacao_iqs.md`: layout oficial, separador `|`, UNIX/LF, `ISO-8859-1`, datas `dd/mm/aaaa hh:mm:ss`, inteiros sem decimal e regionalização aceita pelo IQS.

## Risco de falso positivo

- Ajuste manual sem evidência suficiente.
- Alteração de campo que não resolve a anomalia raiz.
