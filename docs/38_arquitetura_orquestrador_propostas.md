# Arquitetura de Módulos Analíticos e Orquestrador Central

O MIDWAY evoluiu para um modelo padronizado, seguro e escalável de detecção de anomalias, abandonando a criação de scripts Python soltos que manipulavam o banco de dados diretamente. Todo novo motor de negócio (anomalia regulatória, heurística ou NLP) deve seguir a estrutura baseada na interface `BaseModulo`.

Esta arquitetura isola o processamento lógico da persistência de dados. O módulo preocupa-se unicamente em *encontrar problemas* e *propor soluções*, enquanto o Orquestrador Central se encarrega de gravar essas propostas de forma rápida e segura no PostgreSQL.

## 1. O Contrato `BaseModulo`

Qualquer regra de negócio deve ser uma classe que herde de `BaseModulo`. Essa classe abstrata força a implementação das seguintes propriedades e métodos:

- `codigo_modulo`: Identificador único no sistema (ex: `CORRECAO_9282`).
- `escopo`: Nível de atuação da anomalia (ex: `ocorrencia`, `interrupcao`, `uc`, `alimentador`).
- `criterio_anomalia`: Breve descrição técnica do filtro aplicado (usado para exibir metadados na UI).
- `risco_falso_positivo`: Informa se a ação gerada pelo algoritmo tem risco Alto, Médio ou Baixo.
- `detectar_anomalias()`: O coração do motor. É o único método invocado pelo orquestrador. Retorna obrigatoriamente uma lista de objetos `PropostaTratamento`.

## 2. A `PropostaTratamento`

O objeto `PropostaTratamento` é um Dataclass que padroniza o que todo módulo deve devolver quando encontra algo errado:

```python
@dataclass
class PropostaTratamento:
    chave_negocio: str           # UUID, NUM_SEQ_INTRP, ou chave composta
    evidencias: Dict[str, Any]   # JSON com todos os motivos técnicos do alerta
    impacto: str                 # Ex: "Sobreposição inflaciona DIC em X horas"
    acao_sugerida: str           # Ex: "Truncar horário de início", "Anular UC"
    campos_iqs_afetados: List[str] # Lista de colunas IQS que sofrerão alteração
    exportacao_iqs: Optional[Dict[str, Any]] # Opcional: Payload já formatado para exportação
```

A grande vantagem é que as `evidencias` sendo um JSON, permitem que módulos complexos (como o de NLP das reclamações) enviem *Scores*, *Termos coincidentes* ou arrays complexos para o banco, sem precisar criar colunas novas. O Frontend em React lerá esse JSON para desenhar o dashboard de tomada de decisão.

## 3. O Orquestrador Central (`orquestrador.py`)

Em vez de múltiplos arquivos `.bat`, temos um único `run.bat orquestrador` que chama `orquestrador.py`.

As responsabilidades do Orquestrador:
1. Instanciar todos os módulos ativos.
2. Garantir a ordem de execução. Isso é vital! Exemplo: O módulo de *Durações Negativas* deve rodar antes do *Sobreposição*, e a *Interrupção Sem UC* **apenas após** a sobreposição.
3. Consolidar todas as listas de `PropostaTratamento`.
4. Executar um **Bulk Insert Ultrarrápido** via `psycopg2.extras.execute_values` numa `raw_connection`. 

O orquestrador varre milhões de linhas em segundos e as despacha para a tabela PostgreSQL `ddcq.propostas_tratamento` em questão de milissegundos.

## 4. Como criar um novo Módulo

Se houver uma nova exigência de auditoria:
1. Crie um arquivo em `midway/modulos/seu_novo_modulo.py`.
2. Herde de `BaseModulo` e crie as queries DuckDB localizadas, evitando ao máximo o Pandas para tarefas que possam ser feitas no banco de dados para poupar memória.
3. Retorne uma lista de `PropostaTratamento`.
4. Adicione sua classe no final da lista `MODULOS_ATIVOS` dentro de `midway/modulos/orquestrador.py`.
5. Pronto. A UI Web e o sistema de aprovações/filas vão carregar os dados instantaneamente na próxima execução.
