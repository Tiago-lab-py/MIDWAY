# Dashboard Executivo e Busca Técnica - MIDWAY 7.0.0

Data de atualização: `2026-07-11`

## Objetivo

Documentar a evolução do Dashboard Executivo da versão `7.0.0`, com foco em:

- priorizar o impacto `DEC/FEC` logo após o título da página;
- separar o painel de ajustes de componente/causa;
- disponibilizar busca técnica por ocorrência, interrupção ou UC;
- manter a investigação detalhada em painéis expansíveis e pop-up de ocorrência.

## Organização da Página Dashboard

Ordem visual definida:

1. título `Dashboard Executivo`;
2. cards compactos laterais:
   - `ANOMES`;
   - status do `Banco`;
3. painel `DEC/FEC Antes e Depois das Tratativas`;
4. painel `Ajustes de Componente/Causa`;
5. painel `Busca`.

Essa ordem privilegia a leitura executiva:

- primeiro o ganho regulatório;
- depois o volume de tratativas;
- por fim a investigação operacional.

## DEC/FEC Antes e Depois

O painel compara:

- cenário antes: `raw_db.hiadms_raw`;
- cenário depois: `gold_apuracao_previa`.

Premissas do cenário antes:

- `ESTADO_INTRP = 4`;
- duração mínima de 3 minutos;
- UC faturada;
- bruto com todos os protocolos;
- líquido com `TIPO_PROTOC_JUSTIF_UCI = 0`.

Indicadores exibidos:

- `DEC bruto`;
- `FEC bruto`;
- `DEC líquido`;
- `FEC líquido`.

Também são exibidas as aberturas de ganho por tratamento:

- sobreposição parcial por UC;
- sobreposição total por UC;
- interrupção sem UC remanescente;
- demais filtros/ajustes da apuração;
- total do ganho.

## Abertura Diagnóstica dos Filtros

Além do fechamento oficial do ganho, o Dashboard mostra uma abertura diagnóstica do RAW:

- não faturados;
- faturados com manobra/remanejamento;
- faturados com motivo de tratamento diferenciado;
- faturados com manobra e motivo.

Importante:

- não faturados ficam fora do `DEC/FEC` oficial;
- a abertura diagnóstica não substitui o fechamento validado;
- a tabela serve para explicar ordens de grandeza e apoiar auditoria.

## Validação da Sobreposição Parcial UC

O valor exibido de sobreposição parcial por UC representa o ganho oficial faturado:

```text
CHI ganho faturado: 32.880,7
```

Esse valor não é a soma bruta da duração do CSV. Ele é calculado como:

```text
duração original - duração ajustada
```

Resultado validado:

```text
ganho total parcial: 41.383,4
ganho parcial faturado/oficial: 32.880,7
ganho parcial não faturado: 8.502,6
```

## Painel de Ajustes de Componente/Causa

O painel de ajustes consolida a tratativa RA `92/82`:

- ajustes automáticos;
- fila técnica;
- conflitos de serviço;
- sugestões por reclamação.

Objetivo:

- permitir leitura rápida da massa automatizável;
- separar o que exige revisão técnica;
- apoiar a decisão do gestor na autorização em lote.

## Busca

O antigo bloco de prévia da fila no Dashboard foi substituído por busca ativa.

Tipos de busca:

- ocorrência;
- interrupção;
- UC.

Endpoint:

```text
GET /api/qualidade/busca?tipo=<ocorrencia|interrupcao|uc>&valor=<valor>&anomes=<ANOMES>&limit=20
```

Perfil permitido:

- `ANALISTA`;
- `GESTOR`;
- `ADM`.

## Resultado da Busca

Cada resultado aparece em painel expansível com:

- ocorrência;
- quantidade de interrupções;
- quantidade de UCs;
- quantidade de reclamações;
- período da ocorrência;
- pares componente/causa;
- `CHI` e `CI` líquidos;
- score de reclamação;
- grupos IQS;
- interrupções vinculadas;
- tipos e causas prováveis das reclamações.

O botão `Abrir ocorrência completa` aciona o pop-up já existente.

## Pop-up de Ocorrência

O pop-up completo permanece como tela de investigação profunda:

- resumo da ocorrência;
- interrupções distintas por `NUM_SEQ_INTRP`;
- serviços ADMS vinculados por interrupção;
- apuração UC;
- reclamações vinculadas.

A associação de serviços usa:

```text
raw_adms_servicos.PID_INTRP_SRVE = gold_interrupcao_tratada.NUM_SEQ_INTRP
```

Essa premissa evita multiplicação indevida por UC.

## Arquivos Envolvidos

Frontend:

```text
frontend/src/App.jsx
frontend/src/styles.css
```

Backend:

```text
midway/api/routes/qualidade.py
midway/api/routes/executivo_9282.py
```

## Validação Técnica

Validações executadas:

```text
python -m compileall midway/api/routes/qualidade.py
python -m compileall midway/api/routes/executivo_9282.py
npm run build
```

Também foi validada busca direta por:

- ocorrência;
- interrupção;
- UC.
