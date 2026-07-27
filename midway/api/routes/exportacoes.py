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
        if f.name.startswith("~$"):
            continue
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
    # Sanitização básica contra Path Traversal e arquivos temporários do Excel (~$)
    if nome_arquivo.startswith("~$") or ".." in nome_arquivo or "/" in nome_arquivo or "\\" in nome_arquivo:
        raise HTTPException(status_code=400, detail="Nome de arquivo inválido.")
        
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
        
    return FileResponse(
        path=str(file_path.resolve()),
        filename=nome_arquivo,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@router.get("/ressarcimento/gerar-e-baixar")
def gerar_e_baixar_relatorio(user: AuthUser = Depends(require_profiles("ADM", "GESTOR", "ANALISTA"))):
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        # Executa de forma síncrona (otimizada)
        status_code = gerar_ressarcimento_diario(str(EXPORT_DIR))
        if status_code != 0:
            raise HTTPException(status_code=500, detail="A rotina de geração retornou código de erro.")
            
        # Localiza o arquivo recém-gerado (mais recente com padrão do mês, ignorando temporários do Excel)
        from midway.analytics.ressarcimento_diario import ANOMES
        arquivos = [f for f in EXPORT_DIR.glob(f"Relatorio_Ressarcimento_Preventivo_{ANOMES}_*.xlsx") if not f.name.startswith("~$")]
        if not arquivos:
            raise HTTPException(status_code=404, detail="Relatório gerado mas o arquivo correspondente não foi encontrado.")
            
        ultimo_arquivo = max(arquivos, key=lambda f: f.stat().st_mtime)
        return FileResponse(
            path=str(ultimo_arquivo.resolve()),
            filename=ultimo_arquivo.name,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar e baixar o relatório: {e}")
