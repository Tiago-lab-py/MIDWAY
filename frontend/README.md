# MIDWAY Frontend

Frontend React/Vite do MIDWAY 7.0.0.

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
VITE_MIDWAY_API_URL=http://127.0.0.1:8001
```

## MVP

O primeiro recorte consome:

- `GET /api/health`
- `GET /api/executivo/9282/painel`
- `GET /api/executivo/9282/fila-tecnica`

O objetivo inicial e provar a arquitetura React + FastAPI + PostgreSQL mantendo o Streamlit em paralelo.
