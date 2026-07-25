# MIDWAY Frontend

Frontend React/Vite do MIDWAY 7.1.0.

## Uso Local

Em um terminal:

```bat
run.bat api
```

Em outro terminal:

```bat
cd frontend
npm install
npm run dev
```

Ou, depois das dependencias instaladas:

```bat
run.bat frontend
```

## Configuracao

Copiar `frontend/.env.example` para `frontend/.env` se precisar alterar a URL da API:

```env
VITE_MIDWAY_API_URL=http://127.0.0.1:8000
```

## Validacao local fora da rede COPEL

Mesmo fora da rede corporativa, e possivel validar:

- build do React/Vite;
- login e navegacao quando a API local estiver apontando para PostgreSQL local;
- contratos de tela com os endpoints FastAPI;
- textos, perfis de menu, estados vazios e mensagens de erro;
- documentacao operacional e checklist de implantacao.

Dependem do ambiente COPEL:

- conexao Oracle/IQS real;
- acesso DBGUO corporativo;
- extracao oficial de reclamacoes/servicos;
- diretorios corporativos de entrada e saida;
- homologacao de carga do pacote IQS.

## MVP

O primeiro recorte consome:

- `GET /api/health`
- `GET /api/executivo/9282/painel`
- `GET /api/executivo/9282/fila-tecnica`

O objetivo inicial e provar a arquitetura React + FastAPI + PostgreSQL mantendo o Streamlit em paralelo.
