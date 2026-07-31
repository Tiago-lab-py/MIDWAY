import os
import sys
import pandas as pd
import numpy as np
import oracledb
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(override=True)

IQS_UID = os.getenv("IQS_UID")
IQS_PWD = os.getenv("IQS_PWD")
IQS_DB = os.getenv("IQS_DB")
IQS_CONFIG_DIR = os.getenv("IQS_CONFIG_DIR")
IQS_ORACLE_THICK_MODE = os.getenv("IQS_ORACLE_THICK_MODE")
IQS_ORACLE_CLIENT_LIB_DIR = os.getenv("IQS_ORACLE_CLIENT_LIB_DIR")
ANOMES = os.getenv("ANOMES", datetime.now().strftime("%Y%m"))
_ORACLE_CLIENT_INITIALIZED = False

def env_truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "s", "sim", "yes", "y"}

def conectar_oracle():
    global _ORACLE_CLIENT_INITIALIZED
    if IQS_CONFIG_DIR and not os.path.isdir(IQS_CONFIG_DIR):
        raise RuntimeError(f"IQS_CONFIG_DIR nao encontrado ou inacessivel: {IQS_CONFIG_DIR}")

    if env_truthy(IQS_ORACLE_THICK_MODE) and not _ORACLE_CLIENT_INITIALIZED:
        init_kwargs = {}
        if IQS_ORACLE_CLIENT_LIB_DIR:
            if not os.path.isdir(IQS_ORACLE_CLIENT_LIB_DIR):
                raise RuntimeError(f"IQS_ORACLE_CLIENT_LIB_DIR nao encontrado ou inacessivel: {IQS_ORACLE_CLIENT_LIB_DIR}")
            init_kwargs["lib_dir"] = IQS_ORACLE_CLIENT_LIB_DIR
        if IQS_CONFIG_DIR:
            init_kwargs["config_dir"] = IQS_CONFIG_DIR
        oracledb.init_oracle_client(**init_kwargs)
        _ORACLE_CLIENT_INITIALIZED = True

    connect_kwargs = {
        "user": IQS_UID,
        "password": IQS_PWD,
        "dsn": IQS_DB,
    }
    if IQS_CONFIG_DIR:
        connect_kwargs["config_dir"] = IQS_CONFIG_DIR
        oracledb.defaults.config_dir = IQS_CONFIG_DIR
    
    missing = [name for name, value in {
        "IQS_UID": IQS_UID,
        "IQS_PWD": IQS_PWD,
        "IQS_DB": IQS_DB,
    }.items() if not value]
    if missing:
        raise RuntimeError(f"Variaveis obrigatorias ausentes: {', '.join(missing)}")

    return oracledb.connect(**connect_kwargs)

def gerar_ressarcimento_diario(pasta_destino: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Iniciando Rotina Diaria de Ressarcimento Preventivo...")
    print(f"Competencia: {ANOMES}")
    
    if not os.path.exists(pasta_destino):
        try:
            os.makedirs(pasta_destino)
        except Exception as e:
            print(f"Erro ao criar pasta de destino {pasta_destino}: {e}")
            return 2

    conn = None
    df_intrp = None
    try:
        import duckdb
        duck_path = f"data/processed/iqs_adms_processed_{ANOMES}.duckdb"
        if os.path.exists(duck_path):
            duck_conn = duckdb.connect(duck_path, read_only=True)
            tabelas = {row[0] for row in duck_conn.execute("SHOW TABLES").fetchall()}
            if "gold_apuracao_uc" in tabelas:
                cols = {r[0].upper() for r in duck_conn.execute("DESCRIBE gold_apuracao_uc").fetchall()}
                area_filter = "AND COALESCE(TRIM(CAST(a.COD_AREA_ELET_INTRP AS VARCHAR)), '') NOT IN ('7', '8', '9')" if "COD_AREA_ELET_INTRP" in cols else ""
                posto_filter = "AND COALESCE(TRIM(CAST(a.INDIC_PROPR_POSTO_INTRP AS VARCHAR)), 'N') <> 'P'" if "INDIC_PROPR_POSTO_INTRP" in cols else ""
                chvp_filter = "AND COALESCE(TRIM(CAST(a.INDIC_PROPR_CHVP_INTRP AS VARCHAR)), 'N') <> 'P'" if "INDIC_PROPR_CHVP_INTRP" in cols else ""
                acess_filter = "AND COALESCE(TRIM(CAST(a.UC_ACESSANTE AS VARCHAR)), 'N') <> 'S'" if "UC_ACESSANTE" in cols else ""

                df_intrp = duck_conn.execute(f"""
                    SELECT 
                        a.NUM_OCORRENCIA_ADMS,
                        CAST(a.NUM_UC_UCI AS VARCHAR) AS UC,
                        a.DATA_HORA_INIC_INTRP AS DATA_REGISTRO,
                        COALESCE(a.DURACAO_HORA, 0) * 60 AS DURACAO_MIN,
                        1 AS FREQUENCIA,
                        COALESCE(a.CI_BRUTO, 0) AS CI_BRUTO,
                        COALESCE(a.CHI_BRUTO, 0) AS CHI_BRUTO,
                        COALESCE(a.CI_LIQUIDO, 0) AS CI_LIQUIDO,
                        COALESCE(a.CHI_LIQUIDO, 0) AS CHI_LIQUIDO
                    FROM gold_apuracao_uc a
                    WHERE a.NUM_UC_UCI IS NOT NULL
                      AND COALESCE(a.DURACAO_HORA, 0) * 60 >= 3.0
                      AND COALESCE(TRIM(CAST(a.TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)), '0') IN ('0', '0.0', '')
                      AND (a.NUM_MOTIVO_TRAT_DIF_UCI IS NULL OR TRIM(CAST(a.NUM_MOTIVO_TRAT_DIF_UCI AS VARCHAR)) IN ('', '0', '0.0', 'NONE', 'NULL'))
                      AND COALESCE(TRIM(CAST(a.COD_COMP_INTRP AS VARCHAR)), '') NOT IN ('46', '48', '52', '54')
                      AND COALESCE(TRIM(CAST(a.COD_CAUSA_INTRP AS VARCHAR)), '') NOT IN ('22', '71', '75', '83', '85', '88')
                      {area_filter}
                      {posto_filter}
                      {chvp_filter}
                      {acess_filter}
                      AND COALESCE(TRIM(CAST(a.ESTADO_INTRP AS VARCHAR)), '') NOT IN ('7')
                """).df()
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Interrupcoes lidas do DuckDB local (filtros COPEL COMP/CAUSA/AREA/ESTADO/POSTO_PART/PTP): {len(df_intrp)} registros.")
            duck_conn.close()
    except Exception as ex:
        print(f"Aviso ao tentar ler interrupcoes do DuckDB ({ex}). Buscando do Oracle...")

    if df_intrp is None or df_intrp.empty:
        try:
            conn = conectar_oracle()
        except Exception as e:
            print(f"Erro ao conectar no Oracle: {e}")
            return 3

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Buscando interrupcoes do Oracle (Query Otimizada + Longas >= 3min + Filtros COPEL)...")
        
        query_interrupcoes = """
        SELECT 
            PID_OCOR_INTRP_ULT_HIADMS AS NUM_OCORRENCIA_ADMS,
            NUM_UC_UCI_CHVP_HIADMS AS UC,
            DTHR_INC_REGIS_HIADMS AS DATA_REGISTRO,
            (DATA_HORA_FIM_INTRP_ULT_HIADMS - DATA_HORA_INIC_INTRP_ULT_HIADMS) * 24 * 60 AS DURACAO_MIN,
            1 AS FREQUENCIA,
            1 AS CI_BRUTO,
            (DATA_HORA_FIM_INTRP_ULT_HIADMS - DATA_HORA_INIC_INTRP_ULT_HIADMS) * 24 AS CHI_BRUTO,
            1 AS CI_LIQUIDO,
            (DATA_HORA_FIM_INTRP_ULT_HIADMS - DATA_HORA_INIC_INTRP_ULT_HIADMS) * 24 AS CHI_LIQUIDO
        FROM IQS.HIST_INTEGRACAO_ADMS
        WHERE DTHR_INC_REGIS_HIADMS >= TO_DATE(:anomes || '01', 'YYYYMMDD')
          AND DTHR_INC_REGIS_HIADMS < ADD_MONTHS(TO_DATE(:anomes || '01', 'YYYYMMDD'), 1)
          AND DATA_HORA_FIM_INTRP_ULT_HIADMS IS NOT NULL
          AND DATA_HORA_INIC_INTRP_ULT_HIADMS IS NOT NULL
          AND (DATA_HORA_FIM_INTRP_ULT_HIADMS - DATA_HORA_INIC_INTRP_ULT_HIADMS) * 24 * 60 >= 3.0
          AND COALESCE(TRIM(TIPO_PROTOC_JUSTIF_INTRP_ULT_HIADMS), '0') = '0'
          AND COALESCE(TRIM(COD_COMP_INTRP_ULT_HIADMS), '0') NOT IN ('46', '48', '52', '54')
          AND COALESCE(TRIM(COD_CAUSA_INTRP_ULT_HIADMS), '0') NOT IN ('22', '71', '75', '83', '85', '88')
          AND COALESCE(TRIM(COD_AREA_ELET_INTRP_ULT_HIADMS), '0') NOT IN ('7', '8', '9')
          AND COALESCE(TRIM(ESTADO_INTRP_ULT_HIADMS), '0') NOT IN ('7')
          AND COALESCE(TRIM(INDIC_PROPR_POSTO_INTRP_PRIM_HIADMS), 'N') <> 'P'
          AND COALESCE(TRIM(INDIC_PROPR_CHVP_INTRP_PRIM_HIADMS), 'N') <> 'P'
          AND COALESCE(TRIM(INDIC_UC_ACESS_UCI_PRIM_HIADMS), 'N') <> 'S'
        """
        
        try:
            df_intrp = pd.read_sql(query_interrupcoes, conn, params={"anomes": ANOMES})
        except Exception as e:
            print(f"Erro ao buscar interrupcoes do Oracle: {e}")
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
            return 4
        
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Interrupcoes brutas no mes: {len(df_intrp)}")

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Buscando Metas de UC...")
    df_metas = None
    try:
        import duckdb
        duck_path = f"data/processed/iqs_adms_processed_{ANOMES}.duckdb"
        if os.path.exists(duck_path):
            duck_conn = duckdb.connect(duck_path, read_only=True)
            df_metas = duck_conn.execute("SELECT CAST(ISN_UC AS BIGINT)::VARCHAR AS UC, META_DIC, META_FIC, META_DMIC FROM gold_metas_uc WHERE ISN_UC IS NOT NULL").df()
            duck_conn.close()
            print("Metas de UC carregadas com sucesso do DuckDB.")
    except Exception as ex:
        print(f"Nao foi possivel ler metas do DuckDB ({ex}). Buscando do Oracle...")
        try:
            if conn is None:
                conn = conectar_oracle()
            query_metas = """
            SELECT 
                CAST(ISN_UC AS VARCHAR2(50)) AS UC,
                META_DIC,
                META_FIC,
                META_DMIC
            FROM IQS.METAS_UC
            WHERE ISN_UC IN (
                SELECT DISTINCT NUM_UC_UCI_CHVP_HIADMS
                FROM IQS.HIST_INTEGRACAO_ADMS
                WHERE DTHR_INC_REGIS_HIADMS >= TO_DATE(:anomes || '01', 'YYYYMMDD')
                  AND DTHR_INC_REGIS_HIADMS < ADD_MONTHS(TO_DATE(:anomes || '01', 'YYYYMMDD'), 1)
                  AND DATA_HORA_FIM_INTRP_ULT_HIADMS IS NOT NULL
                  AND DATA_HORA_INIC_INTRP_ULT_HIADMS IS NOT NULL
            )
            """
            df_metas = pd.read_sql(query_metas, conn, params={"anomes": ANOMES})
        except Exception as e:
            print(f"Erro ao buscar Metas do Oracle: {e}. Prosseguindo sem metas.")
            df_metas = pd.DataFrame(columns=["UC", "META_DIC", "META_FIC", "META_DMIC"])
        
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Buscando VRC...")
    df_vrc = None
    try:
        import duckdb
        duck_path = f"data/processed/iqs_adms_processed_{ANOMES}.duckdb"
        if os.path.exists(duck_path):
            duck_conn = duckdb.connect(duck_path, read_only=True)
            df_vrc = duck_conn.execute("SELECT CAST(ISN_UC AS BIGINT)::VARCHAR AS UC, VRC FROM gold_vrc WHERE ISN_UC IS NOT NULL").df()
            duck_conn.close()
            print("VRC carregado com sucesso do DuckDB.")
    except Exception as ex:
        print(f"Nao foi possivel ler VRC do DuckDB ({ex}). Buscando do Oracle...")
        try:
            if conn is None:
                conn = conectar_oracle()
            query_vrc = """
            SELECT 
                CAST(ISN_UC AS VARCHAR2(50)) AS UC,
                VRC
            FROM IQS.VRC_COMPENSACAO
            WHERE ISN_UC IN (
                SELECT DISTINCT NUM_UC_UCI_CHVP_HIADMS
                FROM IQS.HIST_INTEGRACAO_ADMS
                WHERE DTHR_INC_REGIS_HIADMS >= TO_DATE(:anomes || '01', 'YYYYMMDD')
                  AND DTHR_INC_REGIS_HIADMS < ADD_MONTHS(TO_DATE(:anomes || '01', 'YYYYMMDD'), 1)
                  AND DATA_HORA_FIM_INTRP_ULT_HIADMS IS NOT NULL
                  AND DATA_HORA_INIC_INTRP_ULT_HIADMS IS NOT NULL
            )
            """
            df_vrc = pd.read_sql(query_vrc, conn, params={"anomes": ANOMES})
        except Exception as e:
            print(f"Erro ao buscar VRC do Oracle: {e}. Prosseguindo sem VRC.")
            df_vrc = pd.DataFrame(columns=["UC", "VRC"])

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Buscando atributos de tipo/tensão de UC...")
    df_atributos_uc = None
    try:
        import duckdb
        duck_path = f"data/processed/iqs_adms_processed_{ANOMES}.duckdb"
        if os.path.exists(duck_path):
            duck_conn = duckdb.connect(duck_path, read_only=True)
            tables = [row[0] for row in duck_conn.execute("SHOW TABLES").fetchall()]
            target_table = "gold_vrc" if "gold_vrc" in tables else "gold_consumidores" if "gold_consumidores" in tables else None
            if target_table:
                cols = [c[1].upper() for c in duck_conn.execute(f"PRAGMA table_info('{target_table}')").fetchall()]
                uc_col = "UC" if "UC" in cols else "ISN_UC" if "ISN_UC" in cols else "NUM_UC_UCI"
                urb_col = "URB_RUR" if "URB_RUR" in cols else "TIPO_URB_RUR" if "TIPO_URB_RUR" in cols else "'U'"
                grupo_col = "COD_GRUPO_NIVEL_TENSAO_UC" if "COD_GRUPO_NIVEL_TENSAO_UC" in cols else "'N/I'"
                nivel_col = "COD_NIVEL_TENSAO_UC" if "COD_NIVEL_TENSAO_UC" in cols else "'N/I'"
                
                df_atributos_uc = duck_conn.execute(f"""
                    SELECT DISTINCT
                        CAST({uc_col} AS BIGINT)::VARCHAR AS UC,
                        CAST({urb_col} AS VARCHAR) AS URB_RUR,
                        CAST({grupo_col} AS VARCHAR) AS COD_GRUPO_NIVEL_TENSAO_UC,
                        CAST({nivel_col} AS VARCHAR) AS COD_NIVEL_TENSAO_UC
                    FROM {target_table}
                    WHERE {uc_col} IS NOT NULL
                """).df()
            duck_conn.close()
    except Exception as ex:
        print(f"Nao foi possivel ler atributos de UC do DuckDB ({ex}).")

    if df_atributos_uc is None or df_atributos_uc.empty:
        df_atributos_uc = pd.DataFrame(columns=["UC", "URB_RUR", "COD_GRUPO_NIVEL_TENSAO_UC", "COD_NIVEL_TENSAO_UC"])

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Calculando impacto...")
    
    def clean_uc(series):
        return series.astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

    df_intrp['UC'] = clean_uc(df_intrp['UC'])
    df_metas['UC'] = clean_uc(df_metas['UC'])
    df_vrc['UC'] = clean_uc(df_vrc['UC'])
    df_atributos_uc['UC'] = clean_uc(df_atributos_uc['UC'])

    # 1. Agregação Vetorizada C-Level do Pandas
    df_acumulado = df_intrp.groupby('UC', as_index=False).agg(
        QTD_OCORRENCIAS=('NUM_OCORRENCIA_ADMS', 'nunique'),
        DURACAO_MIN_SUM=('DURACAO_MIN', 'sum'),
        DMIC_MIN_MAX=('DURACAO_MIN', 'max'),
        FIC_ACUMULADO=('FREQUENCIA', 'sum')
    )
    df_acumulado['DIC_ACUMULADO'] = df_acumulado['DURACAO_MIN_SUM'] / 60.0
    df_acumulado['DMIC_ACUMULADO'] = df_acumulado['DMIC_MIN_MAX'] / 60.0
    df_acumulado.drop(columns=['DURACAO_MIN_SUM', 'DMIC_MIN_MAX'], inplace=True)

    # Identificar a ocorrência DMIC (aquela que causou a maior duração contínua)
    idx_dmic = df_intrp.groupby('UC')['DURACAO_MIN'].idxmax()
    df_dmic_ocor = df_intrp.loc[idx_dmic, ['UC', 'NUM_OCORRENCIA_ADMS']].rename(columns={'NUM_OCORRENCIA_ADMS': 'DMIC_OCORRENCIA'})
    df_acumulado = df_acumulado.merge(df_dmic_ocor, on='UC', how='left')

    # 2. Merge com Metas, VRC e Atributos de UC
    df_analise = df_acumulado.merge(df_metas, on='UC', how='left')
    df_analise = df_analise.merge(df_vrc, on='UC', how='left')
    df_analise = df_analise.merge(df_atributos_uc, on='UC', how='left')

    df_analise['URB_RUR'] = np.where(df_analise['URB_RUR'].astype(str).str.upper().str.strip() == 'R', 'R', 'U')
    df_analise['COD_GRUPO_NIVEL_TENSAO_UC'] = df_analise['COD_GRUPO_NIVEL_TENSAO_UC'].fillna('N/I')
    df_analise['COD_NIVEL_TENSAO_UC'] = df_analise['COD_NIVEL_TENSAO_UC'].fillna('N/I')

    df_analise['META_DIC'] = pd.to_numeric(df_analise['META_DIC'], errors='coerce').fillna(9999)
    df_analise['META_FIC'] = pd.to_numeric(df_analise['META_FIC'], errors='coerce').fillna(9999)
    df_analise['META_DMIC'] = pd.to_numeric(df_analise['META_DMIC'], errors='coerce').fillna(9999)
    df_analise['VRC'] = pd.to_numeric(df_analise['VRC'], errors='coerce').fillna(0)

    # 3. Identificando violacoes
    df_analise['VIOLOU_DIC'] = df_analise['DIC_ACUMULADO'] > df_analise['META_DIC']
    df_analise['VIOLOU_FIC'] = df_analise['FIC_ACUMULADO'] > df_analise['META_FIC']
    df_analise['VIOLOU_DMIC'] = df_analise['DMIC_ACUMULADO'] > df_analise['META_DMIC']
    df_analise['VIOLOU_DICRI'] = (df_analise['DICRI_ACUMULADO'] > df_analise['META_DICRI']) if ('META_DICRI' in df_analise.columns and 'DICRI_ACUMULADO' in df_analise.columns) else False
    df_analise['VIOLOU_DISE'] = (df_analise['DISE_ACUMULADO'] > df_analise['META_DISE']) if ('META_DISE' in df_analise.columns and 'DISE_ACUMULADO' in df_analise.columns) else False
    
    df_violadas = df_analise[df_analise['VIOLOU_DIC'] | df_analise['VIOLOU_FIC'] | df_analise['VIOLOU_DMIC'] | df_analise['VIOLOU_DICRI'] | df_analise['VIOLOU_DISE']].copy()
    
    if df_violadas.empty:
        print("Nenhuma UC violou metas de forma estrita. Exportando top UCs com maior impacto...")
        df_violadas = df_analise.sort_values(by='DIC_ACUMULADO', ascending=False).head(100).copy()

    # 4. Calculo das TOP 3 Ocorrências SOMENTE para as UCs que de fato violaram (100x mais rápido)
    ucs_violadas_set = set(df_violadas['UC'])
    df_intrp_violadas = df_intrp[df_intrp['UC'].isin(ucs_violadas_set)].sort_values(
        by=['UC', 'DURACAO_MIN'], ascending=[True, False]
    )
    
    df_top_ocorrencias = (
        df_intrp_violadas.groupby('UC')
        .head(3)
        .groupby('UC')
        .apply(lambda g: ", ".join([f"{r.NUM_OCORRENCIA_ADMS} ({round(r.DURACAO_MIN, 1)}min)" for r in g.itertuples()]))
        .reset_index(name='TOP_3_OCORRENCIAS')
    )

    df_violadas = df_violadas.merge(df_top_ocorrencias, on='UC', how='left')

    # 5. Calculo estimado bruto de compensacao (PRODIST: MAX(DIC, FIC, DMIC) + DICRI + DISE)
    grupo = df_violadas['COD_GRUPO_NIVEL_TENSAO_UC'].astype(str).str.strip().str.upper()
    nivel = df_violadas['COD_NIVEL_TENSAO_UC'].astype(str).str.strip().str.upper()
    
    cond_a_108 = (grupo == 'A') & (nivel.isin(['1', '2', '3']))
    cond_a_40 = (grupo == 'A') & (nivel.isin(['3A', '4', 'S']))
    
    # 34 é o padrão (Grupo B e demais não identificados)
    df_violadas['KEI'] = np.select([cond_a_108, cond_a_40], [108, 40], default=34)

    KEI2_DICRI = 14
    KEI3_DISE = 14
    df_violadas['RISCO_R$'] = 0.0
    df_violadas['COMP_DICRI'] = 0.0
    df_violadas['COMP_DISE'] = 0.0
    
    comp_dic = np.where(df_violadas['VIOLOU_DIC'], (df_violadas['DIC_ACUMULADO'] * df_violadas['VRC'] / 730.0) * df_violadas['KEI'], 0.0)
    comp_fic = np.where(df_violadas['VIOLOU_FIC'], (df_violadas['FIC_ACUMULADO'] * df_violadas['VRC'] / 730.0) * df_violadas['KEI'], 0.0)
    comp_dmic = np.where(df_violadas.get('VIOLOU_DMIC', False), (df_violadas.get('DMIC_ACUMULADO', 0) * df_violadas['VRC'] / 730.0) * df_violadas['KEI'], 0.0)

    comp_regular_max = np.maximum(comp_dic, np.maximum(comp_fic, comp_dmic))

    if 'DICRI_ACUMULADO' in df_violadas.columns and 'META_DICRI' in df_violadas.columns:
        mask_dicri = df_violadas['VIOLOU_DICRI']
        df_violadas.loc[mask_dicri, 'COMP_DICRI'] = (df_violadas.loc[mask_dicri, 'DICRI_ACUMULADO'] * df_violadas.loc[mask_dicri, 'VRC'] / 730.0) * KEI2_DICRI

    if 'DISE_ACUMULADO' in df_violadas.columns and 'META_DISE' in df_violadas.columns:
        mask_dise = df_violadas['VIOLOU_DISE']
        df_violadas.loc[mask_dise, 'COMP_DISE'] = (df_violadas.loc[mask_dise, 'DISE_ACUMULADO'] * df_violadas.loc[mask_dise, 'VRC'] / 730.0) * KEI3_DISE

    # RISCO_R$ total: MAX(DIC, FIC, DMIC) + DICRI + DISE
    df_violadas['RISCO_R$'] = comp_regular_max + df_violadas['COMP_DICRI'] + df_violadas['COMP_DISE']

    ucs_violadas_list = df_violadas['UC'].tolist()
    df_ocorrencias_violadas = df_intrp[df_intrp['UC'].isin(ucs_violadas_list)].copy()
    
    df_ocorrencias_violadas = df_ocorrencias_violadas.merge(df_violadas[['UC', 'RISCO_R$']], on='UC', how='left')

    df_resumo_ocorrencia = df_ocorrencias_violadas.groupby('NUM_OCORRENCIA_ADMS').agg(
        DURACAO_OCORRENCIA_MIN=('DURACAO_MIN', 'max'),
        QTD_UCS_VIOLADAS=('UC', 'nunique'),
        RISCO_TOTAL_ESTIMADO=('RISCO_R$', 'sum')
    ).reset_index()

    # Garante a existência e o tratamento de CI/CHI antes da agregação
    for c_col in ['CI_BRUTO', 'CI_LIQUIDO']:
        if c_col not in df_intrp.columns:
            df_intrp[c_col] = 1
    for h_col in ['CHI_BRUTO', 'CHI_LIQUIDO']:
        if h_col not in df_intrp.columns:
            df_intrp[h_col] = df_intrp['DURACAO_MIN'] / 60.0

    df_totais_ocorrencia = df_intrp.groupby('NUM_OCORRENCIA_ADMS').agg(
        TOTAL_UCS=('UC', 'nunique'),
        CI_BRUTO=('CI_BRUTO', 'sum'),
        CHI_BRUTO=('CHI_BRUTO', 'sum'),
        CI_LIQUIDO=('CI_LIQUIDO', 'sum'),
        CHI_LIQUIDO=('CHI_LIQUIDO', 'sum')
    ).reset_index()

    df_resumo_ocorrencia = df_resumo_ocorrencia.merge(df_totais_ocorrencia, on='NUM_OCORRENCIA_ADMS', how='left')
    
    # TIPO_CHV and RA_1_UC are calculated later in duckdb block!
    # df_resumo_ocorrencia['RA_1_UC'] ...

    df_resumo_ocorrencia = df_resumo_ocorrencia[df_resumo_ocorrencia['DURACAO_OCORRENCIA_MIN'] >= 3.0].copy()

    df_resumo_ocorrencia['QTD_RECLAMACOES'] = 0
    df_resumo_ocorrencia['QTD_SERVICOS'] = 0
    
    try:
        import duckdb
        duck_path = f"data/processed/iqs_adms_processed_{ANOMES}.duckdb"
        serv_path = f"data/raw/adms_servicos_raw_{ANOMES}.duckdb"
        
        if os.path.exists(duck_path) and not df_resumo_ocorrencia.empty:
            duck_conn = duckdb.connect(duck_path, read_only=True)
            tables = [row[0] for row in duck_conn.execute("SHOW TABLES").fetchall()]
            
            ocorrencias_list = df_resumo_ocorrencia['NUM_OCORRENCIA_ADMS'].dropna().astype(str).unique().tolist()
            if ocorrencias_list:
                duck_conn.register("tmp_ocorrencias", pd.DataFrame({'NUM_OCORRENCIA_ADMS': ocorrencias_list}))
                
                # Fetch TIPO_CHV and NUM_OPER_CHVP using JOIN instead of loading them in the main 5M row query
                if "gold_interrupcao_tratada" in tables:
                    df_chv = duck_conn.execute("""
                        SELECT CAST(t.NUM_OCORRENCIA_ADMS AS VARCHAR) AS NUM_OCORRENCIA_ADMS,
                               FIRST(t.NUM_OPER_CHV_INTRP) AS NUM_OPER_CHVP,
                               FIRST(t.TIPO_CHV_INTRP) AS TIPO_CHV,
                               FIRST(t.VALID_POS_OPERACAO) AS VALID_POS_OPERACAO
                        FROM gold_interrupcao_tratada t
                        JOIN tmp_ocorrencias tmp ON CAST(t.NUM_OCORRENCIA_ADMS AS VARCHAR) = tmp.NUM_OCORRENCIA_ADMS
                        GROUP BY CAST(t.NUM_OCORRENCIA_ADMS AS VARCHAR)
                    """).df()
                    df_resumo_ocorrencia['NUM_OCORRENCIA_ADMS'] = df_resumo_ocorrencia['NUM_OCORRENCIA_ADMS'].astype(str)
                    df_resumo_ocorrencia = df_resumo_ocorrencia.merge(df_chv, on='NUM_OCORRENCIA_ADMS', how='left')
                else:
                    df_resumo_ocorrencia['NUM_OPER_CHVP'] = None
                    df_resumo_ocorrencia['TIPO_CHV'] = None
                    df_resumo_ocorrencia['VALID_POS_OPERACAO'] = None
                
                if "gold_reclamacao_ocorrencia_resumo" in tables:
                    df_rec = duck_conn.execute("""
                        SELECT CAST(r.NUM_OCORRENCIA_ADMS AS VARCHAR) AS NUM_OCORRENCIA_ADMS, 
                               r.QTD_RECLAMACOES 
                        FROM gold_reclamacao_ocorrencia_resumo r 
                        JOIN tmp_ocorrencias tmp ON CAST(r.NUM_OCORRENCIA_ADMS AS VARCHAR) = tmp.NUM_OCORRENCIA_ADMS
                    """).df()
                    if not df_rec.empty:
                        df_resumo_ocorrencia = df_resumo_ocorrencia.merge(df_rec, on='NUM_OCORRENCIA_ADMS', how='left')
                        if 'QTD_RECLAMACOES_y' in df_resumo_ocorrencia.columns:
                            df_resumo_ocorrencia['QTD_RECLAMACOES'] = df_resumo_ocorrencia['QTD_RECLAMACOES_y'].fillna(df_resumo_ocorrencia['QTD_RECLAMACOES_x']).fillna(0)
                            df_resumo_ocorrencia = df_resumo_ocorrencia.drop(columns=['QTD_RECLAMACOES_x', 'QTD_RECLAMACOES_y'])
                
                if os.path.exists(serv_path) and "gold_interrupcao_tratada" in tables:
                    duck_conn.execute(f"ATTACH '{serv_path}' AS serv_raw (READ_ONLY)")
                    query_serv = """
                        SELECT CAST(i.NUM_OCORRENCIA_ADMS AS VARCHAR) AS NUM_OCORRENCIA_ADMS, COUNT(DISTINCT s.PID_INTRP_SRVE) AS QTD_SERVICOS
                        FROM gold_interrupcao_tratada i
                        JOIN tmp_ocorrencias tmp ON CAST(i.NUM_OCORRENCIA_ADMS AS VARCHAR) = tmp.NUM_OCORRENCIA_ADMS
                        JOIN serv_raw.raw_adms_servicos s ON TRIM(CAST(i.NUM_SEQ_INTRP AS VARCHAR)) = TRIM(CAST(s.PID_INTRP_SRVE AS VARCHAR))
                        GROUP BY CAST(i.NUM_OCORRENCIA_ADMS AS VARCHAR)
                    """
                    df_serv = duck_conn.execute(query_serv).df()
                    if not df_serv.empty:
                        df_resumo_ocorrencia = df_resumo_ocorrencia.merge(df_serv, on='NUM_OCORRENCIA_ADMS', how='left')
                        if 'QTD_SERVICOS_y' in df_resumo_ocorrencia.columns:
                            df_resumo_ocorrencia['QTD_SERVICOS'] = df_resumo_ocorrencia['QTD_SERVICOS_y'].fillna(df_resumo_ocorrencia['QTD_SERVICOS_x']).fillna(0)
                            df_resumo_ocorrencia = df_resumo_ocorrencia.drop(columns=['QTD_SERVICOS_x', 'QTD_SERVICOS_y'])
                if "gold_geo_chaves_ra" in tables and 'NUM_OPER_CHVP' in df_resumo_ocorrencia.columns:
                    df_geo_ra = duck_conn.execute("""
                        SELECT DISTINCT CAST(NUM_OPER_CHVP AS VARCHAR) AS NUM_OPER_CHVP,
                               'SIM' AS RA_GEO
                        FROM gold_geo_chaves_ra
                    """).df()
                    # Garante que a coluna base de merge e string
                    df_resumo_ocorrencia['NUM_OPER_CHVP'] = df_resumo_ocorrencia['NUM_OPER_CHVP'].astype(str)
                    df_resumo_ocorrencia = df_resumo_ocorrencia.merge(df_geo_ra, on='NUM_OPER_CHVP', how='left')
                    df_resumo_ocorrencia['RA_1_UC'] = df_resumo_ocorrencia['RA_GEO'].fillna('NAO')
                    df_resumo_ocorrencia = df_resumo_ocorrencia.drop(columns=['RA_GEO'])
                else:
                    df_resumo_ocorrencia['RA_1_UC'] = 'NAO'
                    
            duck_conn.close()
            
            # Removida logica errada do TIPO_CHV, pois o filtro real e do GEO (realizado acima)
                
            df_resumo_ocorrencia['QTD_RECLAMACOES'] = df_resumo_ocorrencia.get('QTD_RECLAMACOES', pd.Series([0]*len(df_resumo_ocorrencia))).fillna(0).astype(int)
            df_resumo_ocorrencia['QTD_SERVICOS'] = df_resumo_ocorrencia.get('QTD_SERVICOS', pd.Series([0]*len(df_resumo_ocorrencia))).fillna(0).astype(int)
            
    except Exception as e:
        print(f"Aviso: erro ao buscar reclamacoes/servicos no DuckDB: {e}")

    # Arredondamentos e criação de DURACAO_OCORRENCIA_HORA
    df_resumo_ocorrencia['DURACAO_OCORRENCIA_MIN'] = df_resumo_ocorrencia['DURACAO_OCORRENCIA_MIN'].round(2)
    df_resumo_ocorrencia['DURACAO_OCORRENCIA_HORA'] = (df_resumo_ocorrencia['DURACAO_OCORRENCIA_MIN'] / 60.0).round(2)
    df_resumo_ocorrencia['RISCO_TOTAL_ESTIMADO'] = df_resumo_ocorrencia['RISCO_TOTAL_ESTIMADO'].round(2)
    df_resumo_ocorrencia['CI_BRUTO'] = df_resumo_ocorrencia.get('CI_BRUTO', pd.Series([0]*len(df_resumo_ocorrencia))).fillna(0).astype(int)
    df_resumo_ocorrencia['CHI_BRUTO'] = df_resumo_ocorrencia.get('CHI_BRUTO', pd.Series([0.0]*len(df_resumo_ocorrencia))).fillna(0.0).round(3)
    df_resumo_ocorrencia['CI_LIQUIDO'] = df_resumo_ocorrencia.get('CI_LIQUIDO', pd.Series([0]*len(df_resumo_ocorrencia))).fillna(0).astype(int)
    df_resumo_ocorrencia['CHI_LIQUIDO'] = df_resumo_ocorrencia.get('CHI_LIQUIDO', pd.Series([0.0]*len(df_resumo_ocorrencia))).fillna(0.0).round(3)

    cols_resumo = [
        'NUM_OCORRENCIA_ADMS', 'NUM_OPER_CHVP', 'RA_1_UC', 'VALID_POS_OPERACAO', 
        'DURACAO_OCORRENCIA_MIN', 'DURACAO_OCORRENCIA_HORA', 'TOTAL_UCS', 
        'CI_BRUTO', 'CHI_BRUTO', 'CI_LIQUIDO', 'CHI_LIQUIDO',
        'QTD_UCS_VIOLADAS', 'QTD_RECLAMACOES', 'QTD_SERVICOS', 'RISCO_TOTAL_ESTIMADO'
    ]
    cols_resumo_existentes = [c for c in cols_resumo if c in df_resumo_ocorrencia.columns]
    df_resumo_ocorrencia = df_resumo_ocorrencia[cols_resumo_existentes].sort_values(by='RISCO_TOTAL_ESTIMADO', ascending=False)

    # Arredondamentos da aba detalhe (df_violadas)
    num_cols_violadas = ['DIC_ACUMULADO', 'FIC_ACUMULADO', 'DMIC_ACUMULADO', 'META_DIC', 'META_FIC', 'META_DMIC', 'VRC', 'RISCO_R$']
    for c in num_cols_violadas:
        if c in df_violadas.columns:
            df_violadas[c] = pd.to_numeric(df_violadas[c], errors='ignore').round(2)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    arquivo_saida = os.path.join(pasta_destino, f"Relatorio_Ressarcimento_Preventivo_{ANOMES}_{timestamp}.xlsx")
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Gerando Excel em {arquivo_saida}...")
    
    colunas_ordenadas = [
        'UC', 'URB_RUR', 'COD_GRUPO_NIVEL_TENSAO_UC', 'COD_NIVEL_TENSAO_UC',
        'QTD_OCORRENCIAS', 'DIC_ACUMULADO', 'FIC_ACUMULADO', 'DMIC_ACUMULADO', 'DMIC_OCORRENCIA',
        'META_DIC', 'META_FIC', 'META_DMIC', 'VRC', 'VIOLOU_DIC', 'VIOLOU_FIC', 'VIOLOU_DMIC',
        'VIOLOU_DICRI', 'VIOLOU_DISE', 'RISCO_R$', 'TOP_3_OCORRENCIAS'
    ]
    cols_existentes = [c for c in colunas_ordenadas if c in df_violadas.columns]
    df_violadas_export = df_violadas[cols_existentes].sort_values(by='RISCO_R$', ascending=False)

    try:
        # Retornado ao openpyxl pois a causa do OOM era o LEFT JOIN gerando explosao cartesiana!
        with pd.ExcelWriter(arquivo_saida, engine='openpyxl') as writer:
            df_resumo_ocorrencia.to_excel(writer, sheet_name='Ocorrencias_Prioritarias', index=False)
            df_violadas_export.to_excel(writer, sheet_name='UCs_Violadas_Detalhe', index=False)
            
        import shutil
        pasta_rede = r"Y:\VDSED\dados_pos\ressarcimento"
        try:
            if not os.path.exists(pasta_rede):
                os.makedirs(pasta_rede, exist_ok=True)
            arquivo_rede = os.path.join(pasta_rede, os.path.basename(arquivo_saida))
            shutil.copy2(arquivo_saida, arquivo_rede)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Cópia de rede (Excel) enviada com sucesso para: {arquivo_rede}")
            
            # --- Gerar arquivos Parquet/CSV para consumo direto no Power BI ---
            pasta_pbi = os.path.join(pasta_rede, "base_automatica")
            os.makedirs(pasta_pbi, exist_ok=True)
            
            try:
                df_resumo_ocorrencia.to_parquet(os.path.join(pasta_pbi, f"Ocorrencias_Prioritarias_{ANOMES}.parquet"), index=False)
                df_violadas_export.to_parquet(os.path.join(pasta_pbi, f"UCs_Violadas_{ANOMES}.parquet"), index=False)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Arquivos Parquet gerados com sucesso para o Power BI em: {pasta_pbi}")
            except ImportError:
                df_resumo_ocorrencia.to_csv(os.path.join(pasta_pbi, f"Ocorrencias_Prioritarias_{ANOMES}.csv"), sep=';', index=False, encoding='utf-8-sig')
                df_violadas_export.to_csv(os.path.join(pasta_pbi, f"UCs_Violadas_{ANOMES}.csv"), sep=';', index=False, encoding='utf-8-sig')
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Bibliotecas Parquet não encontradas. Arquivos CSV gerados com sucesso em: {pasta_pbi}")
                
        except Exception as e_rede:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] AVISO: Não foi possível copiar para a rede ou gerar base PBI: {e_rede}")
            
    except Exception as e:
        print(f"Erro ao gerar Excel: {e}")
        try:
            conn.close()
        except Exception:
            pass
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
        
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Concluido com sucesso!")
    return 0

if __name__ == "__main__":
    pasta_destino = os.getenv("RESSARCIMENTO_DIARIO_DESTINO", "data/marts/ressarcimento_diario")
    if len(sys.argv) > 1:
        pasta_destino = sys.argv[1]
    
    sys.exit(gerar_ressarcimento_diario(pasta_destino))
