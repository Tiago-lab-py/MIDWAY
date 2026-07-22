import os
from pathlib import Path
from typing import List

import duckdb
import pandas as pd
from dotenv import load_dotenv

from .base_modulo import BaseModulo, PropostaTratamento
from midway.controle_execucao import configurar_logger

class ModuloDuracaoNegativa(BaseModulo):
    """
    Módulo que identifica interrupções cuja data de fim é anterior à data de início.
    """
    
    @property
    def codigo_modulo(self) -> str:
        return "DURACAO_NEGATIVA"
        
    @property
    def escopo(self) -> str:
        return "interrupcao"

    @property
    def criterio_anomalia(self) -> str:
        return "Data de fim da interrupção é estritamente menor que a data de início."

    @property
    def risco_falso_positivo(self) -> str:
        return "Cuidado com interrupções com datas zeradas ou nulas (1970). Devem ser validadas."

    def detectar_anomalias(self) -> List[PropostaTratamento]:
        load_dotenv()
        anomes = os.getenv("ANOMES", "202606")
        logger = configurar_logger("modulo_duracao_negativa", anomes)
        logger.info(f"[{self.codigo_modulo}] Iniciando detecção...")

        base_dir = Path("data")
        processed_duckdb_path = base_dir / "processed" / f"iqs_adms_processed_{anomes}.duckdb"
        raw_duckdb_path = base_dir / "raw" / f"iqs_adms_raw_{anomes}.duckdb"

        if not processed_duckdb_path.exists():
            logger.error(f"DuckDB processado nao encontrado: {processed_duckdb_path}")
            return []

        con = duckdb.connect(str(processed_duckdb_path))
        propostas = []
        
        try:
            tables = {
                row[0]
                for row in con.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
                ).fetchall()
            }

            if "adms_iqs_alterados" not in tables:
                logger.error("Tabela adms_iqs_alterados nao encontrada. Execute run.bat tratamento antes.")
                return []
            
            con.execute(f"ATTACH '{raw_duckdb_path.resolve()}' AS raw_db (READ_ONLY)")

            con.execute("""
                CREATE OR REPLACE TEMPORARY TABLE Temp_Duracao_Negativa AS
                SELECT 
                    CAST(r.NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR) AS NUM_SEQ_INTRP,
                    CAST(r.NUM_UC_UCI_CHVP_HIADMS AS VARCHAR) AS NUM_UC_UCI,
                    CAST(r.PID_OCOR_INTRP_ULT_HIADMS AS VARCHAR) AS NUM_OCORRENCIA_ADMS,
                    r.DATA_HORA_INIC_INTRP_ULT_HIADMS AS DATA_HORA_INIC_INTRP,
                    r.DATA_HORA_FIM_INTRP_ULT_HIADMS AS DATA_HORA_FIM_INTRP
                FROM adms_iqs_alterados t
                JOIN raw_db.hiadms_raw r
                  ON CAST(r.NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR) = t.NUM_SEQ_INTRP
                 AND CAST(r.NUM_UC_UCI_CHVP_HIADMS AS VARCHAR) = t.NUM_UC_UCI
                 AND CAST(r.PID_OCOR_INTRP_ULT_HIADMS AS VARCHAR) = t.NUM_OCORRENCIA_ADMS
                WHERE r.DATA_HORA_FIM_INTRP_ULT_HIADMS < r.DATA_HORA_INIC_INTRP_ULT_HIADMS
            """)
            
            # Recupera em lista de dicionários para facilitar
            df = con.execute("SELECT * FROM Temp_Duracao_Negativa").df()
            records = df.to_dict(orient="records")
            
            for row in records:
                chave_negocio = f"{row['NUM_SEQ_INTRP']}-{row['NUM_UC_UCI']}"
                
                # Formata datas para string se existirem
                inicio_str = row['DATA_HORA_INIC_INTRP'].strftime('%Y-%m-%d %H:%M:%S') if pd.notnull(row['DATA_HORA_INIC_INTRP']) else None
                fim_str = row['DATA_HORA_FIM_INTRP'].strftime('%Y-%m-%d %H:%M:%S') if pd.notnull(row['DATA_HORA_FIM_INTRP']) else None
                
                evidencias = {
                    "num_seq_intrp": row['NUM_SEQ_INTRP'],
                    "num_uc_uci": row['NUM_UC_UCI'],
                    "num_ocorrencia": row['NUM_OCORRENCIA_ADMS'],
                    "data_hora_inicio": inicio_str,
                    "data_hora_fim": fim_str
                }
                
                propostas.append(PropostaTratamento(
                    chave_negocio=chave_negocio,
                    evidencias=evidencias,
                    impacto="Erro de cálculo de indicadores de duração na UC.",
                    acao_sugerida="Verificar com o centro de operação o horário real da manobra e ajustar.",
                    campos_iqs_afetados=["DATA_HORA_FIM_INTRP", "DATA_HORA_INIC_INTRP"],
                    exportacao_iqs=None  # Tratar via frontend primeiro
                ))
            
            logger.info(f"[{self.codigo_modulo}] Detecção concluída. {len(propostas)} anomalias encontradas.")
            
        finally:
            con.close()
            
        return propostas

# Teste simples (Orquestrador isolado)
if __name__ == "__main__":
    import json
    from midway.db.postgres import create_postgres_engine
    from sqlalchemy import text
    
    modulo = ModuloDuracaoNegativa()
    anomalias = modulo.detectar_anomalias()
    
    if anomalias:
        engine = create_postgres_engine()
        try:
            with engine.connect() as conn:
                for p in anomalias:
                    conn.execute(
                        text("""
                        INSERT INTO ddcq.midway_propostas_tratamento 
                        (codigo_modulo, chave_negocio, evidencias, impacto, acao_sugerida, campos_iqs_afetados, exportacao_iqs)
                        VALUES (:codigo, :chave, :evidencias, :impacto, :acao, :campos, :exportacao)
                        """),
                        {
                            "codigo": modulo.codigo_modulo,
                            "chave": p.chave_negocio,
                            "evidencias": json.dumps(p.evidencias),
                            "impacto": p.impacto,
                            "acao": p.acao_sugerida,
                            "campos": p.campos_iqs_afetados,
                            "exportacao": p.exportacao_iqs
                        }
                    )
                conn.commit()
                print(f"Gravado com sucesso no Postgres! Total: {len(anomalias)}")
        except Exception as e:
            print(f"Erro ao gravar no banco: {e}")
