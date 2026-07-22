# Arquitetura Modular Baseada em Pipelines (Tratamentos Pluggáveis)

## 1. Visão do Problema
Você identificou o gargalo principal do código fonte atual: apesar do projeto já ter uma **excelente definição conceitual em `DOCs/modulos/`**, a implementação em código (Python/SQL) ainda não reflete essa separação perfeitamente. 
A evolução do sistema exige incorporar novos modelos, mas não podemos reescrever o fluxo de aprovação e de geração de CSV para cada novo modelo inserido.

## 2. Padrão de Projeto no Código (Python Plugins)
A solução é fazer com que o código reflita exatamente o "Contrato Comum de Módulo" definido em `DOCs/modulos/README.md`.

O ciclo de vida completo do sistema será regido por **3 pilares inegociáveis e centralizados**, isolando as regras de negócio no meio.

### Pilar 1: O Motor de Tratamentos (Pipeline de Modelos)
Em vez de um arquivo gigante `tratamento.py`, a estrutura de código espelhará os módulos documentados.
* **Como Funciona:** Cada módulo regulatório (`DIC_FIC_PRODIST`, `DEC_FEC_PRODIST`) ou de anomalia (`SOBREPOSICAO_UC`, `DURACAO_IMPACTO`) será um arquivo/classe Python independente.
* **Interface Única:** O desenvolvedor do módulo é obrigado a retornar um objeto padrão que contenha os campos exigidos no README (`evidencias`, `impacto`, `acao_sugerida`, `campos_iqs_afetados`).
* **Orquestração:** O motor central apenas varre a pasta de módulos, roda as queries no DuckDB independentemente e empilha as anomalias detectadas numa **tabela unificada de propostas no Postgres**.

### Pilar 2: Fluxo de Aprovação Universal (Frontend + Postgres)
Essa tabela unificada será a espinha dorsal do Frontend (React). 
* **Fluxo Único:** A tela de aprovação da ferramenta não saberá (e não precisará saber) os detalhes internos se a correção veio do `INTERRUPCAO_SEM_UC` ou do `DURACAO_IMPACTO`. 
* Ela apenas lerá a tabela central, mostrando aos gestores: *Ocorrência X, Motivo Y, Ação Sugerida Z, Status Pendente*.
* O workflow de Governança é garantido pelo sistema base. A aprovação carimba a ocorrência para exportação.

### Pilar 3: Motor Padrão de Exportação (CSV para IQS)
A geração do CSV para o IQS sempre terá o **mesmo layout e fluxo**, cumprindo estritamente a documentação `docs/35_contrato_exportacao_iqs.md`.
* **Como Funciona:** Um único módulo (`exportador_iqs.py`) lerá *apenas* as ocorrências que passaram pelo Pilar 2 com o carimbo de "Aprovado" e que possuem `exportacao_iqs` aplicável.
* Ele gera o arquivo `.CSV` de exportação.
* Dessa forma, você nunca mais terá que criar um "Exportador CSV" para cada regra de negócio que for inventada. A regra só gera a proposta; o sistema base aprova e exporta.

---

## Estrutura de Diretórios Proposta para o Backend

```text
midway/
├── core/                   # O motor imutável (Aprovação, Controle de Acesso)
│   ├── orquestrador.py     # Roda os modelos Python
│   └── exportador_iqs.py   # Único gerador de CSV (Contrato 35)
│
├── modulos/                # Pasta Pluggável em Código (Espelho de DOCs/modulos)
│   ├── base_modulo.py      # Classe que implementa o contrato do README.md
│   ├── sobreposicao_uc.py  # Implementa SOBREPOSICAO_UC
│   ├── duracao_impacto.py  # Implementa DURACAO_IMPACTO
│   ├── correcao_9282.py    # Implementa CORRECAO_9282
│   └── seu_novo_modulo.py  
```

## Benefícios Desta Estrutura
1. **Fidelidade à Documentação:** O código passa a falar a mesma língua dos documentos de negócio já existentes na pasta `DOCs`.
2. **Escalabilidade:** Se amanhã uma nova equipe criar o tratamento `NOVA_REGRA`, basta criar o `.py` correspondente e herdar a `base_modulo.py`. Ele herdará automaticamente a governança do Postgres, as telas do React e a exportação oficial do IQS.
