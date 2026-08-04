import os
import sys
from pathlib import Path

# Garante que a raiz do projeto seja lida pelo Python independentemente de onde o script for chamado
project_root = str(Path(__file__).resolve().parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Força o diretório de trabalho a ser a raiz do projeto para o DuckDB encontrar a pasta data
os.chdir(project_root)

import json
from midway.api.security import AuthUser
from midway.api.routes.produto import _build_cockpit, _resumo_modulos_automatizados, ANOMES

def materializar():
    print(f"Iniciando materialização do Cockpit para o ANOMES {ANOMES}...")
    
    # Simula um usuário admin para construir o cockpit
    user = AuthUser(
        id_usuario="00000000-0000-0000-0000-000000000000", 
        login="midway_batch", 
        nome="Rotina Batch", 
        email=None, 
        perfil="ADM"
    )
    
    try:
        # Executa as consultas pesadas no DuckDB
        print("Calculando Cockpit...")
        cockpit_data = _build_cockpit(user, limite=20)
        
        print("Calculando Resumo de Módulos...")
        modulos_data = _resumo_modulos_automatizados()
        
        print("Calculando Suspeitas RA...")
        # Limite = 20 para refletir exatamente a chamada inicial da página principal
        from midway.api.routes.produto import _painel_suspeitas_ra
        suspeitas_data = _painel_suspeitas_ra(user, limite=20)
        
        # Garante que o diretório de processed existe na RAIZ do projeto
        processed_dir = Path(project_root) / "data" / "processed"
        processed_dir.mkdir(parents=True, exist_ok=True)
        
        # Salva o JSON no disco
        cockpit_path = processed_dir / f"cockpit_{ANOMES}.json"
        with open(cockpit_path, "w", encoding="utf-8") as f:
            json.dump(cockpit_data, f, ensure_ascii=False, indent=2)
            
        modulos_path = processed_dir / f"modulos_resumo_{ANOMES}.json"
        with open(modulos_path, "w", encoding="utf-8") as f:
            json.dump(modulos_data, f, ensure_ascii=False, indent=2)
            
        suspeitas_path = processed_dir / f"suspeitas_ra_{ANOMES}.json"
        with open(suspeitas_path, "w", encoding="utf-8") as f:
            json.dump(suspeitas_data, f, ensure_ascii=False, indent=2)
            
        print(f"Materialização concluída com sucesso!")
        print(f"Arquivos gerados: {cockpit_path}, {modulos_path} e {suspeitas_path}")
        
    except Exception as e:
        print(f"Erro durante a materialização: {e}")

if __name__ == "__main__":
    materializar()
