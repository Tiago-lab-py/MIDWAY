from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import os
from pathlib import Path
from datetime import datetime
from midway.api.security import AuthUser, require_profiles
from midway.analytics.ressarcimento_diario import gerar_ressarcimento_diario

router = APIRouter(prefix="/api/exportacoes", tags=["exportacoes"])

EXPORT_DIR = Path("data/marts/ressarcimento_diario")

@router.get("/ressarcimento/arquivos")
def listar_arquivos(user: AuthUser = Depends(require_profiles("ADM", "GESTOR", "ANALISTA"))):
    if not EXPORT_DIR.exists():
        return []
    
    arquivos = []
    for f in EXPORT_DIR.glob("*.xlsx"):
        stat = f.stat()
        arquivos.append({
            "nome": f.name,
            "tamanho": stat.st_size,
            "criado_em": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "caminho": str(f.resolve())
        })
    # Ordena pelo mais recente
    arquivos.sort(key=lambda x: x["criado_em"], reverse=True)
    return arquivos

@router.post("/ressarcimento/gerar")
def gerar_relatorio(
    background_tasks: BackgroundTasks,
    user: AuthUser = Depends(require_profiles("ADM", "GESTOR", "ANALISTA"))
):
    # Garantir que a pasta existe
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Executar em background para não bloquear a resposta HTTP
    def _run_generation():
        try:
            gerar_ressarcimento_diario(str(EXPORT_DIR))
        except Exception as e:
            print(f"Erro em background ao gerar ressarcimento: {e}")
        
    background_tasks.add_task(_run_generation)
    return {"mensagem": "Geração do relatório iniciada em segundo plano."}

@router.get("/ressarcimento/download/{nome_arquivo}")
def download_arquivo(
    nome_arquivo: str,
    user: AuthUser = Depends(require_profiles("ADM", "GESTOR", "ANALISTA"))
):
    file_path = EXPORT_DIR / nome_arquivo
    # Sanitização básica contra Path Traversal
    if ".." in nome_arquivo or "/" in nome_arquivo or "\\" in nome_arquivo:
        raise HTTPException(status_code=400, detail="Nome de arquivo inválido.")
        
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
        
    return FileResponse(
        path=str(file_path.resolve()),
        filename=nome_arquivo,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
