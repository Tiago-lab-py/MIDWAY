# 13 - Proposta de organizacao dos arquivos do projeto

## Objetivo

Organizar o projeto MIDWAY para separar codigo, comandos, documentacao, dados, testes e aplicacoes de apoio.

A organizacao deve:

- reduzir a quantidade de arquivos soltos na raiz;
- deixar claro o fluxo `extract -> tratamento -> apuracao -> auditoria -> painel`;
- manter compatibilidade com `run.bat`;
- evitar mover dados grandes;
- permitir migracao gradual sem quebrar o processamento atual.

## Diagnostico da estrutura anterior

Antes da reorganizacao, a raiz misturava responsabilidades:

```text
D:\MIDWAY
  extract.py
  tratamento.py
  apuracao_previa.py
  exportar_*.py
  auditar_*.py
  app_streamlit.py
  controle_execucao.py
  iqs_raw_utils.py
  *.bat
  docs/
  tests/
  tools/
  data/
```

Problemas principais:

- muitos scripts operacionais na raiz;
- arquivos `.bat` duplicando responsabilidades do `run.bat`;
- mistura entre ETL principal, auditorias, exportacoes auxiliares e app visual;
- nomes historicos importantes, mas sem agrupamento por dominio;
- dificuldade de entender quais scripts sao oficiais e quais sao auxiliares.

## Estrutura atual implantada

Em `2026-07-02`, a raiz foi reduzida aos arquivos de entrada e configuracao do projeto:

```text
D:\MIDWAY
  README.md
  CHANGELOG.md
  VERSION
  requirements.txt
  .env.example
  run.bat

  midway/
  docs/
  tests/
  tools/
  scripts/
  SQL/
  notebooks/
  data/
```

Nao existem mais scripts Python operacionais soltos na raiz. O ponto oficial para operador continua sendo:

```bat
run.bat <acao>
```

E o ponto oficial para desenvolvedor e automacao passa a ser:

```bat
python -m midway.<dominio>.<modulo>
```

## Estrutura-alvo proposta

```text
D:\MIDWAY
  README.md
  CHANGELOG.md
  VERSION
  requirements.txt
  .env.example
  run.bat

  midway/
    __init__.py
    controle_execucao.py

    extract/
      __init__.py
      adms.py
      consumidores.py
      uc_fatura.py
      vrc.py
      metas_uc.py

    transform/
      __init__.py
      tratamento.py
      iqs_raw_utils.py
      normalizar_csv_unix.py

    apuracao/
      __init__.py
      previa.py
      auditoria_sem_uc.py

    auditoria/
      __init__.py
      sobreposicoes.py
      interrupcao_sem_uc.py
      motivo.py
      ajuste_inicio_manobra.py
      duplicidade_tipo_intrp.py

    export/
      __init__.py
      csv_iqs.py

    web/
      __init__.py
      streamlit_app.py

  scripts/
    legacy/
      apuracao_previa.bat
      auditar_ajuste_inicio_manobra.bat
      auditar_duplicidade_tipo.bat
      exportar_interrupcao_sem_uc.bat
      exportar_motivo.bat
      exportar_sobreposicoes.bat
      extract_consumidores.bat
      extract_uc_fatura.bat

  tools/
    copiar_iqs_raw_do_old.py
    exportar_amostra_raw.py
    exportar_amostras_auditoria.py
    gerar_metricas_qualidade.py
    sincronizar_iqs_raw.py

  tests/
    __init__.py
    utils.py
    test_contratos_tabelas.py
    test_apuracao_dic_fic.py
    test_sobreposicao_uc.py
    test_ressarcimento_prodist.py

  docs/
    00_especificacao.md
    ...
    13_organizacao_arquivos.md

  SQL/
    IQS_evidencia_volumetria_hcai.sql

  notebooks/
    verificacao_compensacoes.ipynb

  data/
    raw/
    processed/
    export/
    marts/
    control/
    logs/
    temp/
    input/
```

## Responsabilidade de cada pasta

### `midway/`

Pacote Python principal do projeto.

Tudo que faz parte do pipeline oficial deve morar aqui.

### `midway/extract/`

Extracoes de origem:

- Oracle ADMS/HIADMS;
- consumidores IQS;
- UCs faturadas;
- VRC;
- metas UC.

### `midway/transform/`

Transformacoes e normalizacoes:

- tratamento ADMS para IQS;
- sincronizacao RAW IQS para processed;
- criacao de camadas `silver_*`;
- utilitarios de normalizacao.

### `midway/apuracao/`

Calculos de indicadores:

- apuracao previa;
- `gold_apuracao_uc`;
- `gold_continuidade_uc`;
- ressarcimento PRODIST.

### `midway/auditoria/`

Auditorias e evidencias:

- sobreposicoes;
- interrupcoes sem UC;
- motivos de tratamento;
- manobras;
- duplicidades.

### `midway/export/`

Exportacoes oficiais:

- CSVs IQS finais;
- resumos de exportacao;
- funcoes comuns de escrita.

### `midway/web/`

Interface Streamlit:

- painel local de avaliacao;
- consultas agregadas;
- visualizacao de metricas e amostras.

### `scripts/legacy/`

Arquivos `.bat` antigos ou atalhos especificos.

O comando oficial deve continuar sendo:

```bat
run.bat <acao>
```

### `tools/`

Ferramentas auxiliares que nao fazem parte direta do pipeline principal.

Exemplos:

- copiar dados do `processed_old`;
- gerar metricas de qualidade;
- exportar amostras de auditoria;
- sincronizar bases locais.

### `tests/`

Testes automatizados dos dados tratados e contratos das tabelas.

### `notebooks/`

Anotacoes exploratorias e verificacoes manuais.

Notebook nao deve ser dependencia do pipeline oficial.

### `data/`

Mantem a estrutura atual.

Nao mover dados grandes sem necessidade.

## Mapeamento dos arquivos atuais

| Arquivo atual | Destino proposto |
| --- | --- |
| `extract.py` | `midway/extract/adms.py` |
| `extract_consumidores.py` | `midway/extract/consumidores.py` |
| `extract_uc_fatura.py` | `midway/extract/uc_fatura.py` |
| `extract_vrc.py` | `midway/extract/vrc.py` |
| `extract_metas_uc.py` | `midway/extract/metas_uc.py` |
| `tratamento.py` | `midway/transform/tratamento.py` |
| `iqs_raw_utils.py` | `midway/transform/iqs_raw_utils.py` |
| `normalizar_csv_unix.py` | `midway/transform/normalizar_csv_unix.py` |
| `apuracao_previa.py` | `midway/apuracao/previa.py` |
| `exportar.py` | `midway/export/csv_iqs.py` |
| `exportar_sobreposicoes.py` | `midway/auditoria/sobreposicoes.py` |
| `exportar_interrupcao_sem_uc.py` | `midway/auditoria/interrupcao_sem_uc.py` |
| `exportar_motivo.py` | `midway/auditoria/motivo.py` |
| `auditar_ajuste_inicio_manobra.py` | `midway/auditoria/ajuste_inicio_manobra.py` |
| `auditar_duplicidade_tipo_intrp.py` | `midway/auditoria/duplicidade_tipo_intrp.py` |
| `controle_execucao.py` | `midway/controle_execucao.py` |
| `app_streamlit.py` | `midway/web/streamlit_app.py` |
| `verificação compensações.ipynb` | `notebooks/verificacao_compensacoes.ipynb` |
| `*.bat`, exceto `run.bat` | `scripts/legacy/` |

## Migracao recomendada por fases

## Status atual

Fase 1 executada em `2026-07-02`:

- criada a pasta `midway/` com `__init__.py`;
- criada a pasta `scripts/legacy/`;
- criada a pasta `notebooks/`;
- movidos os atalhos `.bat` antigos para `scripts/legacy/`;
- movido o notebook de verificacao para `notebooks/verificacao_compensacoes.ipynb`;
- mantidos na raiz os scripts principais para nao quebrar o pipeline.

Fase 2 executada em `2026-07-02`:

- criadas as pastas:
  - `midway/extract/`;
  - `midway/transform/`;
  - `midway/auditoria/`;
  - `midway/export/`;
  - `midway/web/`.
- movidos para `midway/extract/`:
  - `extract.py` -> `midway/extract/adms.py`;
  - `extract_consumidores.py` -> `midway/extract/consumidores.py`;
  - `extract_uc_fatura.py` -> `midway/extract/uc_fatura.py`;
  - `extract_vrc.py` -> `midway/extract/vrc.py`;
  - `extract_metas_uc.py` -> `midway/extract/metas_uc.py`.
- movidos para `midway/auditoria/`:
  - `exportar_motivo.py` -> `midway/auditoria/motivo.py`;
  - `exportar_sobreposicoes.py` -> `midway/auditoria/sobreposicoes.py`;
  - `exportar_interrupcao_sem_uc.py` -> `midway/auditoria/interrupcao_sem_uc.py`;
  - `auditar_ajuste_inicio_manobra.py` -> `midway/auditoria/ajuste_inicio_manobra.py`;
  - `auditar_duplicidade_tipo_intrp.py` -> `midway/auditoria/duplicidade_tipo_intrp.py`.
- movidos para outros pacotes:
  - `exportar.py` -> `midway/export/csv_iqs.py`;
  - `app_streamlit.py` -> `midway/web/streamlit_app.py`;
  - `controle_execucao.py` -> `midway/controle_execucao.py`;
  - `iqs_raw_utils.py` -> `midway/transform/iqs_raw_utils.py`;
  - `normalizar_csv_unix.py` -> `midway/transform/normalizar_csv_unix.py`;
  - `verificar_duplicados_csv.py` -> `tools/verificar_duplicados_csv.py`.
- mantidos wrappers pequenos na raiz para compatibilidade com `run.bat` e comandos antigos.

Fase 3 executada em `2026-07-02`:

- movidos os arquivos grandes de negocio:
  - `tratamento.py` -> `midway/transform/tratamento.py`;
  - `apuracao_previa.py` -> `midway/apuracao/previa.py`.
- atualizado `run.bat` para executar modulos Python com `python -m`;
- removidos os wrappers Python da raiz;
- corrigido `run.bat registrar` para usar `REGISTRAR_RAW=1` em `midway.extract.adms`;
- corrigidos os atalhos em `scripts/legacy/` para chamarem `run.bat`.

A raiz agora fica reservada a documentacao principal, configuracao, versionamento e `run.bat`.

### Fase 1 - Sem mover scripts principais

Objetivo: organizar sem risco.

Acao:

- criar pastas `midway/`, `scripts/legacy/` e `notebooks/`;
- mover somente notebooks e `.bat` antigos;
- manter scripts principais na raiz;
- atualizar README indicando que `run.bat` e o ponto oficial.

Risco: baixo.

### Fase 2 - Criar pacote `midway`

Objetivo: preparar importacoes limpas.

Acao:

- criar `midway/config.py`;
- mover `controle_execucao.py`;
- ajustar imports dos scripts principais;
- manter wrappers na raiz para compatibilidade.

Exemplo de wrapper:

```python
from midway.transform.tratamento import main

if __name__ == "__main__":
    main()
```

Risco: medio, porque envolve imports.

### Fase 3 - Migrar ETL principal

Objetivo: mover os scripts oficiais para dentro do pacote.

Acao:

- mover `extract.py`;
- mover `tratamento.py`;
- mover `apuracao_previa.py`;
- mover `exportar.py`;
- atualizar `run.bat` para chamar modulo Python:

```bat
python -m midway.transform.tratamento
python -m midway.apuracao.previa
```

Risco: medio/alto, porque mexe no caminho de execucao.

Status: concluido em `2026-07-02`.

### Fase 4 - Separar arquivos grandes por dominio

Objetivo: reduzir tamanho e complexidade dos arquivos principais.

Acao:

- quebrar `tratamento.py` em SQLs e funcoes por regra;
- separar ressarcimento PRODIST de `apuracao_previa.py`;
- centralizar funcoes comuns de DuckDB/exportacao.

Risco: alto se feito sem testes.

Requisito antes da fase 4:

```bat
run.bat testar_dados
```

## Padrao operacional atual

Use sempre `run.bat` para execucao operacional:

```bat
run.bat reprocessar
run.bat apuracao_parcial
run.bat validar_dados
run.bat painel
```

Use `python -m` somente para desenvolvimento, testes pontuais ou automacao controlada:

```bat
python -m midway.transform.tratamento
python -m midway.apuracao.previa
python -m midway.web.streamlit_app
```

## Regras de organizacao

1. `run.bat` continua sendo o ponto unico para operadores.
2. `data/` nao deve ser reorganizado nesta etapa.
3. Scripts grandes so devem ser movidos depois de testes automatizados.
4. CSVs gerados nunca devem ficar na raiz.
5. Notebooks ficam em `notebooks/`.
6. Documentos de decisao ficam em `docs/`.
7. Ferramentas temporarias ou auxiliares ficam em `tools/`.
8. O Streamlit fica em `midway/web/` quando o pacote for criado.

## Resultado esperado

Ao final da reorganizacao:

- raiz com poucos arquivos;
- fluxo operacional mais claro;
- codigo dividido por responsabilidade;
- testes protegendo as regras de negocio;
- painel visual separado do ETL;
- menor risco de alterar acidentalmente scripts oficiais.

## Recomendacao

Manter a raiz limpa daqui para frente.

Novos codigos operacionais devem entrar em `midway/`, ferramentas auxiliares em `tools/`, documentos em `docs/` e atalhos historicos em `scripts/legacy/`.
