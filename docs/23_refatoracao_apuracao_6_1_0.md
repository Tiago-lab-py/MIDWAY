# 23 - Refatoracao da Apuracao na Versao 6.1.0

## Objetivo

Iniciar a consolidacao tecnica da apuracao parcial, reduzindo o tamanho e o risco de manutencao de:

```text
midway/apuracao/previa.py
```

A regra principal da versao `6.1.0` e:

```text
refatorar sem alterar regra de negocio
```

## Situacao Anterior

O arquivo `previa.py` concentrava:

- utilitarios DuckDB;
- normalizacao de CSV;
- criacao de camadas gold;
- apuracao de continuidade;
- ressarcimento PRODIST;
- impacto por conjunto;
- dia critico;
- exportacoes;
- orquestracao do fluxo.

Isso dificultava evolucoes, pois qualquer mudanca pequena aumentava o risco de quebrar outras etapas.

## Mudanca Implementada

Foram criados os modulos:

```text
midway/apuracao/duckdb_utils.py
midway/apuracao/conjunto.py
midway/apuracao/continuidade.py
midway/apuracao/ressarcimento.py
midway/apuracao/exportacoes.py
midway/apuracao/resumos.py
```

### `duckdb_utils.py`

Centraliza utilitarios reutilizaveis:

- `sql_literal`;
- `tabela_local_existe`;
- `normalizar_linhas_unix`.

### `conjunto.py`

Centraliza rotinas ligadas a conjunto eletrico:

- `criar_gold_impacto_conjunto_dia`;
- `criar_gold_meta_dia_critico_conjunto`;
- `exportar_gold_impacto_conjunto_dia`;
- `exportar_gold_meta_dia_critico_conjunto`.

### `continuidade.py`

Centraliza a criacao da camada:

```text
gold_continuidade_uc
```

Essa etapa agrega os indicadores individuais por UC e preserva as regras de filtros para `DIC`, `FIC`, `DMIC`, `DICRI`, `DISE` e bases de compensacao.

### `ressarcimento.py`

Centraliza a criacao da camada:

```text
gold_ressarcimento_prodist
```

Essa etapa calcula a previa PRODIST a partir de `gold_continuidade_uc`, mantendo as regras de piso, teto, `KEI1`, `KEI2`, `KEI3`, `COMP52`, `CAUSA71` e demais exclusoes ja implementadas.

### `exportacoes.py`

Centraliza exportacoes operacionais e arquivos de conferencia:

- BDO de apuracao previa;
- conferencia `gold_continuidade_uc`;
- conferencia `gold_ressarcimento_prodist`.

### `resumos.py`

Centraliza resumos textuais e anexos:

- resumo principal da apuracao previa;
- resumo de compensacoes;
- anexo de compensacao no resumo principal.

## Compatibilidade

O fluxo operacional continua o mesmo:

```bat
run.bat apuracao_parcial
```

O arquivo `previa.py` continua sendo o orquestrador da apuracao, mas agora delega parte da logica para modulos especializados.

## Resultado

Primeira reducao de complexidade:

```text
previa.py: 2335 linhas -> aproximadamente 978 linhas
```

Essa reducao e intencionalmente incremental. O objetivo e evitar uma grande reescrita que poderia quebrar o processamento ja validado.

## Proximas Extracoes Recomendadas

### Fase 1 - Baixo risco

- criar dataclass de contexto para `ANOMES`, paths e timestamp.
- mover funcoes obsoletas para `midway/apuracao/legacy.py`.

### Fase 2 - Medio risco

- separar SQL longo de continuidade e ressarcimento em arquivos `.sql`;
- criar testes unitarios de schema SQL para cada modulo.

### Fase 3 - Alto impacto

- separar SQL longo em arquivos `.sql` versionados;
- substituir wrappers por uma orquestracao declarativa;
- criar pipeline de dependencias entre tabelas gold.

## Regra de Manutencao

Toda nova funcionalidade de apuracao deve preferir modulo proprio quando:

- tiver mais de uma funcao;
- criar tabela propria;
- exportar CSV/resumo proprio;
- puder ser testada isoladamente.

`previa.py` deve evoluir para ser apenas o orquestrador.
