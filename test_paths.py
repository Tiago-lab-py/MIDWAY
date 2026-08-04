import os
from pathlib import Path
from midway.api.routes.produto import ANOMES

def test():
    project_root = Path("d:/MIDWAY/midway/api/routes/produto.py").resolve().parent.parent.parent.parent
    anomes_str = str(ANOMES).strip()
    
    cockpit = project_root / "data" / "processed" / f"cockpit_{anomes_str}.json"
    modulos = project_root / "data" / "processed" / f"modulos_resumo_{anomes_str}.json"
    suspeitas = project_root / "data" / "processed" / f"suspeitas_ra_{anomes_str}.json"
    
    print(f"Project root: {project_root}")
    print(f"ANOMES str: '{anomes_str}'")
    print(f"Cockpit path: {cockpit} - Exists: {cockpit.exists()}")
    print(f"Modulos path: {modulos} - Exists: {modulos.exists()}")
    print(f"Suspeitas path: {suspeitas} - Exists: {suspeitas.exists()}")

if __name__ == "__main__":
    test()
