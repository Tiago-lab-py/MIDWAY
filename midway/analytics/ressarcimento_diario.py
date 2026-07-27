import os
import sys
import pandas as pd
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

    df_intrp = None
    try:
        import duckdb
        duck_path = f"data/processed/iqs_adms_processed_{ANOMES}.duckdb"
        if os.path.exists(duck_path):
            duck_conn = duckdb.connect(duck_path, read_only=True)
            tabelas = {row[0] for row in duck_conn.execute("SHOW TABLES").fetchall()}
            if "gold_apuracao_uc" in tabelas:
                df_intrp = duck_conn.execute("""
                    SELECT 
                        NUM_OCORRENCIA_ADMS,
                        CAST(NUM_UC_UCI AS VARCHAR) AS UC,
                        DATA_HORA_INIC_INTRP AS DATA_REGISTRO,
                        COALESCE(DURACAO_HORA, 0) * 60 AS DURACAO_MIN,
                        1 AS FREQUENCIA
                    FROM gold_apuracao_uc
                    WHERE NUM_UC_UCI IS NOT NULL
                """).df()
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Interrupcoes lidas do DuckDB local com sucesso: {len(df_intrp)} registros.")
            duck_conn.close()
    except Exception as ex:
        print(f"Aviso ao tentar ler interrupcoes do DuckDB ({ex}). Buscando do Oracle...")

    if df_intrp is None or df_intrp.empty:
        try:
            conn = conectar_oracle()
        except Exception as e:
            print(f"Erro ao conectar no Oracle: {e}")
            return 3

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Buscando interrupcoes do Oracle (Query Otimizada por Indice)...")
        
        query_interrupcoes = """
        SELECT 
            PID_OCOR_INTRP_ULT_HIADMS AS NUM_OCORRENCIA_ADMS,
            NUM_UC_UCI_CHVP_HIADMS AS UC,
            DTHR_INC_REGIS_HIADMS AS DATA_REGISTRO,
            (DATA_HORA_FIM_INTRP_ULT_HIADMS - DATA_HORA_INIC_INTRP_ULT_HIADMS) * 24 * 60 AS DURACAO_MIN,
            1 AS FREQUENCIA
        FROM IQS.HIST_INTEGRACAO_ADMS
        WHERE DTHR_INC_REGIS_HIADMS >= TO_DATE(:anomes || '01', 'YYYYMMDD')
          AND DTHR_INC_REGIS_HIADMS < ADD_MONTHS(TO_DATE(:anomes || '01', 'YYYYMMDD'), 1)
          AND DATA_HORA_FIM_INTRP_ULT_HIADMS IS NOT NULL
          AND DATA_HORA_INIC_INTRP_ULT_HIADMS IS NOT NULL
        """
        
        try:
            df_intrp = pd.read_sql(query_interrupcoes, conn, params={"anomes": ANOMES})
            conn.close()
        except Exception as e:
            print(f"Erro ao buscar interrupcoes do Oracle: {e}")
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
        duck_conn = duckdb.connect(f"data/processed/iqs_adms_processed_{ANOMES}.duckdb")
        df_metas = duck_conn.execute("SELECT ISN_UC AS UC, META_DIC, META_FIC FROM gold_metas_uc").df()
        duck_conn.close()
        print("Metas de UC carregadas com sucesso do DuckDB.")
    except Exception as ex:
        print(f"Nao foi possivel ler metas do DuckDB ({ex}). Buscando do Oracle...")
        try:
            query_metas = """
            SELECT 
                ISN_UC AS UC,
                META_DIC,
                META_FIC
            FROM IQS.METAS_UC
            WHERE ISN_UC IN (
                SELECT DISTINCT NUM_UC_UCI_CHVP_HIADMS
                FROM IQS.HIST_INTEGRACAO_ADMS
                WHERE TO_CHAR(DTHR_INC_REGIS_HIADMS, 'yyyymm') = :anomes
                  AND DATA_HORA_FIM_INTRP_ULT_HIADMS IS NOT NULL
                  AND DATA_HORA_INIC_INTRP_ULT_HIADMS IS NOT NULL
            )
            """
            df_metas = pd.read_sql(query_metas, conn, params={"anomes": ANOMES})
        except Exception as e:
            print(f"Erro ao buscar Metas do Oracle: {e}. Prosseguindo sem metas.")
            df_metas = pd.DataFrame(columns=["UC", "META_DIC", "META_FIC"])
        
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Buscando VRC...")
    df_vrc = None
    try:
        import duckdb
        duck_conn = duckdb.connect(f"data/processed/iqs_adms_processed_{ANOMES}.duckdb")
        df_vrc = duck_conn.execute("SELECT ISN_UC AS UC, VRC FROM gold_vrc").df()
        duck_conn.close()
        print("VRC carregado com sucesso do DuckDB.")
    except Exception as ex:
        print(f"Nao foi possivel ler VRC do DuckDB ({ex}). Buscando do Oracle...")
        try:
            query_vrc = """
            SELECT 
                ISN_UC AS UC,
                VRC
            FROM IQS.VRC_COMPENSACAO
            WHERE ISN_UC IN (
                SELECT DISTINCT NUM_UC_UCI_CHVP_HIADMS
                FROM IQS.HIST_INTEGRACAO_ADMS
                WHERE TO_CHAR(DTHR_INC_REGIS_HIADMS, 'yyyymm') = :anomes
                  AND DATA_HORA_FIM_INTRP_ULT_HIADMS IS NOT NULL
                  AND DATA_HORA_INIC_INTRP_ULT_HIADMS IS NOT NULL
            )
            """
            df_vrc = pd.read_sql(query_vrc, conn, params={"anomes": ANOMES})
        except Exception as e:
            print(f"Erro ao buscar VRC do Oracle: {e}. Prosseguindo sem VRC.")
            df_vrc = pd.DataFrame(columns=["UC", "VRC"])

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Calculando impacto...")
    
    df_intrp['UC'] = df_intrp['UC'].astype(str)
    df_metas['UC'] = df_metas['UC'].astype(str)
    df_vrc['UC'] = df_vrc['UC'].astype(str)

    df_acumulado = df_intrp.groupby('UC').agg(
        QTD_OCORRENCIAS=('NUM_OCORRENCIA_ADMS', 'nunique'),
        DIC_ACUMULADO=('DURACAO_MIN', lambda x: x.sum() / 60.0),
        FIC_ACUMULADO=('FREQUENCIA', 'sum')
    ).reset_index()

    # Calcular as 3 maiores ocorrências (em duração) por UC
    df_sorted_intrp = df_intrp.sort_values(by=['UC', 'DURACAO_MIN'], ascending=[True, False])
    df_top_ocorrencias = (
        df_sorted_intrp.groupby('UC')
        .head(3)
        .groupby('UC')
        .apply(lambda g: ", ".join([f"{r.NUM_OCORRENCIA_ADMS} ({round(r.DURACAO_MIN, 1)}min)" for r in g.itertuples()]))
        .reset_index(name='TOP_3_OCORRENCIAS')
    )

    df_analise = df_acumulado.merge(df_top_ocorrencias, on='UC', how='left')
    df_analise = df_analise.merge(df_metas, on='UC', how='left')
    df_analise = df_analise.merge(df_vrc, on='UC', how='left')

    df_analise['META_DIC'] = pd.to_numeric(df_analise['META_DIC'], errors='coerce').fillna(9999)
    df_analise['META_FIC'] = pd.to_numeric(df_analise['META_FIC'], errors='coerce').fillna(9999)
    df_analise['VRC'] = pd.to_numeric(df_analise['VRC'], errors='coerce').fillna(0)

    # Identificando violacoes
    df_analise['VIOLOU_DIC'] = df_analise['DIC_ACUMULADO'] > df_analise['META_DIC']
    df_analise['VIOLOU_FIC'] = df_analise['FIC_ACUMULADO'] > df_analise['META_FIC']
    
    df_violadas = df_analise[df_analise['VIOLOU_DIC'] | df_analise['VIOLOU_FIC']].copy()
    
    if df_violadas.empty:
        print("Nenhuma UC violou metas neste periodo.")
        try:
            conn.close()
        except Exception:
            pass
        return 0

    # Calculo estimado bruto de compensacao
    KEI_BT = 34
    df_violadas['RISCO_R$'] = 0.0
    
    mask_dic = df_violadas['VIOLOU_DIC']
    df_violadas.loc[mask_dic, 'RISCO_R$'] = (df_violadas.loc[mask_dic, 'DIC_ACUMULADO'] * df_violadas.loc[mask_dic, 'VRC'] / 730.0) * KEI_BT

    mask_fic = df_violadas['VIOLOU_FIC'] & ~df_violadas['VIOLOU_DIC']
    df_violadas.loc[mask_fic, 'RISCO_R$'] = ((df_violadas.loc[mask_fic, 'FIC_ACUMULADO'] / df_violadas.loc[mask_fic, 'META_FIC']) * df_violadas.loc[mask_fic, 'META_DIC'] * df_violadas.loc[mask_fic, 'VRC'] / 730.0) * KEI_BT

    ucs_violadas_list = df_violadas['UC'].tolist()
    df_ocorrencias_violadas = df_intrp[df_intrp['UC'].isin(ucs_violadas_list)].copy()
    
    df_ocorrencias_violadas = df_ocorrencias_violadas.merge(df_violadas[['UC', 'RISCO_R$']], on='UC', how='left')

    df_resumo_ocorrencia = df_ocorrencias_violadas.groupby('NUM_OCORRENCIA_ADMS').agg(
        QTD_UCS_VIOLADAS=('UC', 'nunique'),
        RISCO_TOTAL_ESTIMADO=('RISCO_R$', 'sum')
    ).reset_index()

    df_resumo_ocorrencia = df_resumo_ocorrencia.sort_values(by='RISCO_TOTAL_ESTIMADO', ascending=False)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    arquivo_saida = os.path.join(pasta_destino, f"Relatorio_Ressarcimento_Preventivo_{ANOMES}_{timestamp}.xlsx")
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Gerando Excel em {arquivo_saida}...")
    
    colunas_ordenadas = [
        'UC', 'QTD_OCORRENCIAS', 'DIC_ACUMULADO', 'FIC_ACUMULADO', 
        'META_DIC', 'META_FIC', 'VRC', 'VIOLOU_DIC', 'VIOLOU_FIC', 
        'RISCO_R$', 'TOP_3_OCORRENCIAS'
    ]
    cols_existentes = [c for c in colunas_ordenadas if c in df_violadas.columns]
    df_violadas_export = df_violadas[cols_existentes].sort_values(by='RISCO_R$', ascending=False)

    try:
        with pd.ExcelWriter(arquivo_saida, engine='openpyxl') as writer:
            df_resumo_ocorrencia.to_excel(writer, sheet_name='Ocorrencias_Prioritarias', index=False)
            df_violadas_export.to_excel(writer, sheet_name='UCs_Violadas_Detalhe', index=False)
    except Exception as e:
        print(f"Erro ao gerar Excel: {e}")
        try:
            conn.close()
        except Exception:
            pass
        return 5

    conn.close()
        
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Concluido com sucesso!")
    return 0

if __name__ == "__main__":
    pasta_destino = os.getenv("RESSARCIMENTO_DIARIO_DESTINO", "data/marts/ressarcimento_diario")
    if len(sys.argv) > 1:
        pasta_destino = sys.argv[1]
    
    sys.exit(gerar_ressarcimento_diario(pasta_destino))
