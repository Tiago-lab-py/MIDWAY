import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import List

from midway.controle_execucao import configurar_logger

class CloudExporter:
    """
    Exportador cloud-ready (GCP) para gerar arquivos do IQS e compactar 
    tudo num unico .zip estruturado, ao inves de gravar na arvore de
    diretorios da aplicacao localmente.
    """
    
    def __init__(self, anomes: str, id_geracao: str):
        self.anomes = anomes
        self.id_geracao = id_geracao
        self.logger = configurar_logger(f"cloud_export_{id_geracao}", anomes)

    def exportar_pacote_zip(self, gerar_arquivos_callback) -> Path:
        """
        Cria um diretorio temporario, chama o callback para gerar 
        fisicamente os arquivos e depois compacta num ZIP unico.
        """
        # Criar uma pasta 'cloud_export' temporaria controlada
        export_base_dir = Path("data/export/cloud")
        export_base_dir.mkdir(parents=True, exist_ok=True)
        
        zip_path = export_base_dir / f"iqs_export_{self.anomes}_{self.id_geracao}.zip"
        
        # Se ja existir, retornamos (poderia estar num bucket GCS)
        if zip_path.exists():
            return zip_path
            
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            
            # O callback preenche o diretorio temporario
            self.logger.info(f"Gerando arquivos para ZIP temporario: {tmp_path}")
            gerar_arquivos_callback(tmp_path)
            
            # Gerar zip
            self.logger.info(f"Compactando arquivos em: {zip_path}")
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(tmp_path):
                    for file in files:
                        file_path = Path(root) / file
                        arcname = file_path.relative_to(tmp_path)
                        zf.write(file_path, arcname)
                        
        return zip_path

