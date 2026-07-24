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
ANOMES = os.getenv("ANOMES", datetime.now().strftime("%Y%m"))

def conectar_oracle():
    connect_kwargs = {
        "user": IQS_UID,
        "password": IQS_PWD,
        "dsn": IQS_DB,
    }
    if IQS_CONFIG_DIR:
        connect_kwargs["config_dir"] = IQS_CONFIG_DIR
        oracledb.defaults.config_dir = IQS_CONFIG_DIR
    
    return oracledb.connect(**connect_kwargs)

def gerar_ressarcimento_diario(pasta_destino: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Iniciando Rotina Diaria de Ressarcimento Preventivo...")
    print(f"Competencia: {ANOMES}")
    
    if not os.path.exists(pasta_destino):
        try:
            os.makedirs(pasta_destino)
        except Exception as e:
            print(f"Erro ao criar pasta de destino {pasta_destino}: {e}")
            print("Usando pasta atual como fallback.")
            pasta_destino = "."

    try:
        conn = conectar_oracle()
    except Exception as e:
        print(f"Erro ao conectar no Oracle: {e}")
        return

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Buscando interrupcoes do Oracle...")
    
    query_interrupcoes = """
    SELECT 
        PID_OCOR_INTRP_ULT_HIADMS AS NUM_OCORRENCIA_ADMS,
        NUM_UC_UCI_CHVP_HIADMS AS UC,
        DTHR_INC_REGIS_HIADMS AS DATA_REGISTRO,
        (DATA_HORA_FIM_INTRP_ULT_HIADMS - DATA_HORA_INIC_INTRP_ULT_HIADMS) * 24 * 60 AS DURACAO_MIN,
        1 AS FREQUENCIA
    FROM IQS.HIST_INTEGRACAO_ADMS
    WHERE TO_CHAR(DTHR_INC_REGIS_HIADMS, 'yyyymm') = :anomes
      AND DATA_HORA_FIM_INTRP_ULT_HIADMS IS NOT NULL
      AND DATA_HORA_INIC_INTRP_ULT_HIADMS IS NOT NULL
    """
    
    try:
        df_intrp = pd.read_sql(query_interrupcoes, conn, params={"anomes": ANOMES})
    except Exception as e:
        print(f"Erro ao buscar interrupcoes: {e}")
        return
        
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Interrupcoes brutas no mes: {len(df_intrp)}")

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Buscando Metas de UC...")
    # Oracle IQS might not have a simple METAS_UC table like that.
    # The metas extraction script reads from IQS.METAS_UC or similar. Let's assume we can fetch it, 
    # but if it fails, we fall back to duckdb if available.
    try:
        query_metas = """
        SELECT 
            ISN_UC AS UC,
            META_DIC,
            META_FIC
        FROM IQS.METAS_UC
        """
        df_metas = pd.read_sql(query_metas, conn)
    except Exception as e:
        print(f"Metas_UC nao encontrado no oracle: {e}. Lendo do DuckDB Processado...")
        try:
            import duckdb
            duck_conn = duckdb.connect(f"data/processed/iqs_adms_processed_{ANOMES}.duckdb")
            df_metas = duck_conn.execute("SELECT ISN_UC AS UC, META_DIC, META_FIC FROM gold_metas_uc").df()
            duck_conn.close()
        except Exception as ex:
            print(f"Erro ao ler duckdb: {ex}. Prosseguindo sem metas.")
            df_metas = pd.DataFrame(columns=["UC", "META_DIC", "META_FIC"])
        
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Buscando VRC...")
    try:
        query_vrc = """
        SELECT 
            ISN_UC AS UC,
            VRC
        FROM IQS.VRC_COMPENSACAO
        """
        df_vrc = pd.read_sql(query_vrc, conn)
    except Exception as e:
        print(f"VRC nao encontrado no oracle: {e}. Lendo do DuckDB Processado...")
        try:
            import duckdb
            duck_conn = duckdb.connect(f"data/processed/iqs_adms_processed_{ANOMES}.duckdb")
            df_vrc = duck_conn.execute("SELECT ISN_UC AS UC, VRC FROM gold_vrc").df()
            duck_conn.close()
        except Exception as ex:
            print(f"Erro ao ler duckdb: {ex}. Prosseguindo sem VRC.")
            df_vrc = pd.DataFrame(columns=["UC", "VRC"])

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Calculando impacto...")
    
    df_intrp['UC'] = df_intrp['UC'].astype(str)
    df_metas['UC'] = df_metas['UC'].astype(str)
    df_vrc['UC'] = df_vrc['UC'].astype(str)

    df_acumulado = df_intrp.groupby('UC').agg(
        DIC_ACUMULADO=('DURACAO_MIN', lambda x: x.sum() / 60.0),
        FIC_ACUMULADO=('FREQUENCIA', 'sum')
    ).reset_index()

    df_analise = df_acumulado.merge(df_metas, on='UC', how='left')
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
        return

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
    
    with pd.ExcelWriter(arquivo_saida, engine='openpyxl') as writer:
        df_resumo_ocorrencia.to_excel(writer, sheet_name='Ocorrencias_Prioritarias', index=False)
        df_violadas.sort_values(by='RISCO_R$', ascending=False).to_excel(writer, sheet_name='UCs_Violadas_Detalhe', index=False)
        
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Concluido com sucesso!")

if __name__ == "__main__":
    pasta_destino = r"Y:\VDSED\dados_pos\ressarcimento"
    if len(sys.argv) > 1:
        pasta_destino = sys.argv[1]
    
    gerar_ressarcimento_diario(pasta_destino)
