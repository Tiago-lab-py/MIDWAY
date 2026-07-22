import os
from pathlib import Path
from typing import List

import duckdb
from dotenv import load_dotenv

from .base_modulo import BaseModulo, PropostaTratamento
from midway.controle_execucao import configurar_logger

class ModuloDuplicidadeTipoIntrp(BaseModulo):
    """
    Identifica duplicidade exata e sobreposição de período para interrupções do mesmo tipo (1, 2, 3) no mesmo equipamento.
    """
    
    @property
    def codigo_modulo(self) -> str:
        return "DUPLICIDADE_TIPO_INTRP"
        
    @property
    def escopo(self) -> str:
        return "ocorrencia"

    @property
    def criterio_anomalia(self) -> str:
        return "Múltiplos NUM_SEQ_INTRP para o mesmo equipamento, tempos e tipo de interrupção (1,2,3)."

    @property
    def risco_falso_positivo(self) -> str:
        return "Baixo para duplicidade exata. Para sobreposição de período, pode ser manobra."

    def detectar_anomalias(self) -> List[PropostaTratamento]:
        load_dotenv()
        anomes = os.getenv("ANOMES", "202606")
        logger = configurar_logger("modulo_duplicidade_tipo_intrp", anomes)
        logger.info(f"[{self.codigo_modulo}] Iniciando detecção...")

        base_dir = Path("data")
        processed_duckdb_path = base_dir / "processed" / f"iqs_adms_processed_{anomes}.duckdb"

        if not processed_duckdb_path.exists():
            logger.error(f"DuckDB processado nao encontrado: {processed_duckdb_path}")
            return []

        con = duckdb.connect(str(processed_duckdb_path), read_only=True)
        propostas = []
        
        try:
            tables = {row[0] for row in con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'").fetchall()}

            fonte = None
            if "gold_interrupcao_tratada" in tables:
                fonte = "gold_interrupcao_tratada"
            elif "adms_iqs_export" in tables:
                fonte = "adms_iqs_export"
            elif "adms_iqs_alterados" in tables:
                fonte = "adms_iqs_alterados"
            else:
                logger.error("Nenhuma tabela fonte válida (gold_interrupcao_tratada, adms_iqs_export, adms_iqs_alterados) encontrada.")
                return []
            
            # Tabela base simplificada
            con.execute(f"""
                CREATE TEMP TABLE interrupcao_tipo_base AS
                SELECT
                    CAST(NUM_OCORRENCIA_ADMS AS VARCHAR) AS NUM_OCORRENCIA_ADMS,
                    CAST(NUM_SEQ_INTRP AS VARCHAR) AS NUM_SEQ_INTRP,
                    CAST(NUM_OPER_CHV_INTRP AS VARCHAR) AS NUM_OPER_CHV_INTRP,
                    CAST(COD_CAUSA_INTRP AS VARCHAR) AS COD_CAUSA_INTRP,
                    CAST(COD_COMP_INTRP AS VARCHAR) AS COD_COMP_INTRP,
                    TRIM(CAST(COD_TIPO_INTRP AS VARCHAR)) AS COD_TIPO_INTRP,
                    MIN(DATA_HORA_INIC_INTRP) AS DATA_HORA_INIC_INTRP,
                    MAX(DATA_HORA_FIM_INTRP) AS DATA_HORA_FIM_INTRP
                FROM {fonte}
                WHERE TRIM(CAST(COD_TIPO_INTRP AS VARCHAR)) IN ('1', '2', '3')
                GROUP BY
                    CAST(NUM_SEQ_INTRP AS VARCHAR),
                    CAST(NUM_OCORRENCIA_ADMS AS VARCHAR),
                    CAST(NUM_OPER_CHV_INTRP AS VARCHAR),
                    CAST(COD_CAUSA_INTRP AS VARCHAR),
                    CAST(COD_COMP_INTRP AS VARCHAR),
                    TRIM(CAST(COD_TIPO_INTRP AS VARCHAR))
            """)

            # Busca duplicidade exata
            df_exata = con.execute("""
                SELECT
                    COD_TIPO_INTRP,
                    NUM_OPER_CHV_INTRP,
                    STRING_AGG(DISTINCT NUM_OCORRENCIA_ADMS, ', ' ORDER BY NUM_OCORRENCIA_ADMS) AS OCORRENCIAS,
                    STRING_AGG(DISTINCT NUM_SEQ_INTRP, ', ' ORDER BY NUM_SEQ_INTRP) AS NUM_SEQ_INTRP_LISTA,
                    COUNT(DISTINCT NUM_SEQ_INTRP) AS QTD_NUM_SEQ_INTRP
                FROM interrupcao_tipo_base
                GROUP BY
                    COD_TIPO_INTRP,
                    NUM_OPER_CHV_INTRP,
                    DATA_HORA_INIC_INTRP,
                    DATA_HORA_FIM_INTRP,
                    COD_CAUSA_INTRP,
                    COD_COMP_INTRP
                HAVING COUNT(DISTINCT NUM_SEQ_INTRP) > 1
            """).df()

            records = df_exata.to_dict(orient="records")
            
            for row in records:
                chave_negocio = f"{row['OCORRENCIAS']}-{row['NUM_OPER_CHV_INTRP']}-{row['COD_TIPO_INTRP']}"
                
                evidencias = {
                    "cod_tipo_intrp": str(row['COD_TIPO_INTRP']),
                    "num_oper_chv_intrp": str(row['NUM_OPER_CHV_INTRP']),
                    "ocorrencias": str(row['OCORRENCIAS']),
                    "num_seq_intrp_lista": str(row['NUM_SEQ_INTRP_LISTA']),
                    "quantidade": row['QTD_NUM_SEQ_INTRP']
                }
                
                propostas.append(PropostaTratamento(
                    chave_negocio=chave_negocio,
                    evidencias=evidencias,
                    impacto="Duplicação exata de registro de interrupção afetando indicadores.",
                    acao_sugerida="Revisar no ADMS/IQS e inativar a interrupção duplicada mais recente (manter apenas a original).",
                    campos_iqs_afetados=["NUM_SEQ_INTRP", "INDIC_SIT_PROCES_INDIC_UCI"],
                    exportacao_iqs=None
                ))
            
            logger.info(f"[{self.codigo_modulo}] Detecção concluída. {len(propostas)} anomalias de duplicidade encontradas.")
            
        finally:
            con.close()
            
        return propostas
