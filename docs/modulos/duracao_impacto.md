# Módulo `DURACAO_IMPACTO`

## Objetivo

Priorizar ocorrências/interrupções com duração, CHI, CI/FIC, DEC/FEC ou ressarcimento anormais para análise técnica.

## Escopo

- ocorrência;
- interrupção;
- UC, quando o impacto vem da apuração individual.

## Fontes

- `gold_apuracao_uc`;
- `gold_interrupcao_tratada`;
- `gold_continuidade_uc`;
- `gold_ressarcimento_prodist`;
- cache da análise técnica.

## Critérios de anomalia

1. Duração acima do limiar configurado.
2. CHI/CI/FIC incompatível com o padrão do conjunto.
3. Ressarcimento alto ou inesperado.
4. Score de impacto elevado.

## Evidências

- duração máxima;
- CHI líquido;
- CI/FIC líquido;
- ressarcimento estimado;
- quantidade de UCs;
- conjunto/alimentador;
- grupo/componente/causa.

## Impacto

- priorização operacional;
- risco financeiro;
- risco regulatório;
- seleção de casos para decisão humana.

## Ação sugerida

- Abrir ocorrência completa.
- Cruzar com serviços e reclamações.
- Criar proposta governada quando houver correção objetiva.

## Campos IQS afetados

Depende da causa raiz:

- datas de início/fim;
- componente/causa;
- motivo de tratamento;
- estado da interrupção.

## Exportação IQS

Somente após o módulo raiz gerar ajuste aprovado. Pacote final deve cumprir `docs/35_contrato_exportacao_iqs.md`.

## Risco de falso positivo

- Um impacto alto pode ser real e não anomalia.
- Deve ser triagem, não alteração automática.
