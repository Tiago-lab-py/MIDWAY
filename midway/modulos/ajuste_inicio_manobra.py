import os
from pathlib import Path
from typing import List

import duckdb
from dotenv import load_dotenv

from .base_modulo import BaseModulo, PropostaTratamento
from midway.controle_execucao import configurar_logger

class ModuloAjusteInicioManobra(BaseModulo):
    """
    Identifica registros que tiveram o ponteiro de início de manobra redirecionado 
    (substituindo ponteiro para ESTADO_INTRP=7 pelo pai mantido).
    """
    
    @property
    def codigo_modulo(self) -> str:
        return "AJUSTE_INICIO_MANOBRA"
        
    @property
    def escopo(self) -> str:
        return "uc"

    @property
    def criterio_anomalia(self) -> str:
        return "NUM_INTRP_INIC_MANOBRA_UCI apontava para interrupção de estado 7 (excluída) e precisa apontar para a principal."

    @property
    def risco_falso_positivo(self) -> str:
        return "O pai mapeado precisa existir na mesma ocorrência."

    def detectar_anomalias(self) -> List[PropostaTratamento]:
        load_dotenv()
        anomes = os.getenv("ANOMES", "202606")
        logger = configurar_logger("modulo_ajuste_inicio_manobra", anomes)
        logger.info(f"[{self.codigo_modulo}] Iniciando detecção...")

        base_dir = Path("data")
        processed_duckdb_path = base_dir / "processed" / f"iqs_adms_processed_{anomes}.duckdb"

        if not processed_duckdb_path.exists():
            logger.error(f"DuckDB processado nao encontrado: {processed_duckdb_path}")
            return []

        con = duckdb.connect(str(processed_duckdb_path))
        propostas = []
        
        try:
            tables = {row[0] for row in con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'").fetchall()}

            if "adms_iqs_alterados" not in tables:
                logger.error("Tabela adms_iqs_alterados nao encontrada.")
                return []
            
            # Garante que as colunas existam (o script original fazia essa validação)
            cols = {row[0] for row in con.execute("DESCRIBE adms_iqs_alterados").fetchall()}
            if "ACAO_REDIREC_MANOBRA_ESTADO_7" not in cols:
                return []
            
            con.execute("""
                CREATE OR REPLACE TEMPORARY TABLE Temp_Ajuste_Manobra AS
                SELECT 
                    CAST(NUM_SEQ_INTRP AS VARCHAR) AS NUM_SEQ_INTRP,
                    CAST(NUM_UC_UCI AS VARCHAR) AS NUM_UC_UCI,
                    CAST(NUM_OCORRENCIA_ADMS AS VARCHAR) AS NUM_OCORRENCIA_ADMS,
                    CAST(NUM_INTRP_INIC_MANOBRA_UCI_ANTES_REDIREC AS VARCHAR) AS ANTES,
                    CAST(NUM_INTRP_MANOBRA_PAI_REDIREC AS VARCHAR) AS DEPOIS,
                    ACAO_REDIREC_MANOBRA_ESTADO_7
                FROM adms_iqs_alterados
                WHERE ACAO_REDIREC_MANOBRA_ESTADO_7 IS NOT NULL
            """)
            
            df = con.execute("SELECT * FROM Temp_Ajuste_Manobra").df()
            records = df.to_dict(orient="records")
            
            for row in records:
                chave_negocio = f"{row['NUM_SEQ_INTRP']}-{row['NUM_UC_UCI']}"
                
                evidencias = {
                    "num_seq_intrp": row['NUM_SEQ_INTRP'],
                    "num_uc_uci": row['NUM_UC_UCI'],
                    "num_ocorrencia": row['NUM_OCORRENCIA_ADMS'],
                    "manobra_antes": str(row['ANTES']),
                    "manobra_depois": str(row['DEPOIS']),
                    "acao_tomada": str(row['ACAO_REDIREC_MANOBRA_ESTADO_7'])
                }
                
                propostas.append(PropostaTratamento(
                    chave_negocio=chave_negocio,
                    evidencias=evidencias,
                    impacto="Perda da rastreabilidade da manobra que originou a interrupção.",
                    acao_sugerida="Redirecionar NUM_INTRP_INIC_MANOBRA_UCI para a interrupção pai válida.",
                    campos_iqs_afetados=["NUM_INTRP_INIC_MANOBRA_UCI"],
                    exportacao_iqs=None
                ))
            
            logger.info(f"[{self.codigo_modulo}] Detecção concluída. {len(propostas)} anomalias encontradas.")
            
        finally:
            con.close()
            
        return propostas
