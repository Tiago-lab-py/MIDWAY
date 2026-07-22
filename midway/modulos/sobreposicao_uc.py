import os
from pathlib import Path
from typing import List

import duckdb
import pandas as pd
from dotenv import load_dotenv

from .base_modulo import BaseModulo, PropostaTratamento
from midway.controle_execucao import configurar_logger

class ModuloSobreposicaoUC(BaseModulo):
    """
    Detecta sobreposição total de interrupções para a mesma UC.
    """
    
    @property
    def codigo_modulo(self) -> str:
        return "SOBREPOSICAO_UC"
        
    @property
    def escopo(self) -> str:
        return "uc"

    @property
    def criterio_anomalia(self) -> str:
        return "UC em janelas de interrupção sobrepostas (Sobreposição Total)."

    @property
    def risco_falso_positivo(self) -> str:
        return "Não deve misturar interrupções de tipos diferentes (ex: programada vs acidental)."

    def detectar_anomalias(self) -> List[PropostaTratamento]:
        load_dotenv()
        anomes = os.getenv("ANOMES", "202606")
        logger = configurar_logger("modulo_sobreposicao_uc", anomes)
        logger.info(f"[{self.codigo_modulo}] Iniciando detecção (Sobreposição Total)...")

        base_dir = Path("data")
        processed_duckdb_path = base_dir / "processed" / f"iqs_adms_processed_{anomes}.duckdb"

        if not processed_duckdb_path.exists():
            logger.error(f"DuckDB processado nao encontrado: {processed_duckdb_path}")
            return []

        con = duckdb.connect(str(processed_duckdb_path))
        propostas = []
        
        try:
            # Verifica se a tabela tratada existe
            tables = {
                row[0]
                for row in con.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
                ).fetchall()
            }

            if "adms_iqs_alterados" not in tables:
                logger.error("Tabela adms_iqs_alterados nao encontrada. Execute run.bat tratamento antes.")
                return []
            
            # =========================================================================
            # 1. SOBREPOSIÇÃO TOTAL
            # =========================================================================
            con.execute("""
                CREATE OR REPLACE TEMPORARY TABLE Temp_Sobreposicao_Total AS
                SELECT 
                    CAST(NUM_SEQ_INTRP AS VARCHAR) AS NUM_SEQ_INTRP,
                    CAST(NUM_UC_UCI AS VARCHAR) AS NUM_UC_UCI,
                    CAST(NUM_OCORRENCIA_ADMS AS VARCHAR) AS NUM_OCORRENCIA_ADMS,
                    DATA_HORA_INIC_INTRP,
                    DATA_HORA_FIM_INTRP,
                    NUM_MOTIVO_TRAT_DIF_UCI,
                    INDIC_SIT_PROCES_INDIC_UCI,
                    ACAO_SOBREPOSICAO_TOTAL_UC
                FROM adms_iqs_alterados
                WHERE ACAO_SOBREPOSICAO_TOTAL_UC IS NOT NULL
                   OR (
                       TRIM(CAST(NUM_MOTIVO_TRAT_DIF_UCI AS VARCHAR)) = '91'
                       AND TRIM(CAST(INDIC_SIT_PROCES_INDIC_UCI AS VARCHAR)) = 'D'
                   )
            """)
            
            df_total = con.execute("SELECT * FROM Temp_Sobreposicao_Total").df()
            for row in df_total.to_dict(orient="records"):
                chave = f"TOTAL-{row['NUM_SEQ_INTRP']}-{row['NUM_UC_UCI']}"
                propostas.append(PropostaTratamento(
                    chave_negocio=chave,
                    evidencias={
                        "num_seq_intrp": row['NUM_SEQ_INTRP'],
                        "num_uc_uci": row['NUM_UC_UCI'],
                        "num_ocorrencia": row['NUM_OCORRENCIA_ADMS'],
                        "acao_sobreposicao": str(row['ACAO_SOBREPOSICAO_TOTAL_UC'])
                    },
                    impacto="Dupla contabilização de DIC/FIC para a mesma UC (Total).",
                    acao_sugerida="Classificar a UC totalmente contida como 91/D.",
                    campos_iqs_afetados=["NUM_MOTIVO_TRAT_DIF_UCI", "INDIC_SIT_PROCES_INDIC_UCI"],
                    exportacao_iqs="sobreposicao_total_uc"
                ))

            # =========================================================================
            # 2. SOBREPOSIÇÃO PARCIAL
            # =========================================================================
            con.execute("""
                CREATE OR REPLACE TEMPORARY TABLE Temp_Sobreposicao_Parcial AS
                SELECT 
                    CAST(NUM_SEQ_INTRP AS VARCHAR) AS NUM_SEQ_INTRP,
                    CAST(NUM_UC_UCI AS VARCHAR) AS NUM_UC_UCI,
                    CAST(NUM_OCORRENCIA_ADMS AS VARCHAR) AS NUM_OCORRENCIA_ADMS,
                    DATA_HORA_INIC_INTRP,
                    DATA_HORA_FIM_INTRP,
                    ACAO_AJUSTE_PARCIAL,
                    DTHR_INICIO_INTRP_UC_AJUSTADO
                FROM adms_iqs_alterados
                WHERE ACAO_AJUSTE_PARCIAL IS NOT NULL
                   OR DTHR_INICIO_INTRP_UC_AJUSTADO IS NOT NULL
            """)
            
            df_parcial = con.execute("SELECT * FROM Temp_Sobreposicao_Parcial").df()
            for row in df_parcial.to_dict(orient="records"):
                chave = f"PARCIAL-{row['NUM_SEQ_INTRP']}-{row['NUM_UC_UCI']}"
                propostas.append(PropostaTratamento(
                    chave_negocio=chave,
                    evidencias={
                        "num_seq_intrp": row['NUM_SEQ_INTRP'],
                        "num_uc_uci": row['NUM_UC_UCI'],
                        "num_ocorrencia": row['NUM_OCORRENCIA_ADMS'],
                        "acao_sobreposicao": str(row['ACAO_AJUSTE_PARCIAL']),
                        "dthr_ajustado": str(row['DTHR_INICIO_INTRP_UC_AJUSTADO'])
                    },
                    impacto="Sobreposição parcial de interrupção afetando cálculo DIC/FIC.",
                    acao_sugerida="Ajustar a DTHR_INICIO_INTRP_UC para o término da interrupção anterior.",
                    campos_iqs_afetados=["DTHR_INICIO_INTRP_UC"],
                    exportacao_iqs="sobreposicao_parcial_uc"
                ))
            
            logger.info(f"[{self.codigo_modulo}] Detecção concluída. {len(propostas)} anomalias encontradas (Total e Parcial).")
            
        finally:
            con.close()
            
        return propostas


# Teste simples isolado
if __name__ == "__main__":
    import json
    from midway.db.postgres import create_postgres_engine
    from sqlalchemy import text
    
    modulo = ModuloSobreposicaoUC()
    anomalias = modulo.detectar_anomalias()
    
    if anomalias:
        engine = create_postgres_engine()
        try:
            with engine.connect() as conn:
                for p in anomalias:
                    conn.execute(
                        text("""
                        INSERT INTO ddcq.propostas_tratamento 
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
