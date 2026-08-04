import os
import json
import duckdb
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/ise", tags=["Simulação ISE"])

# Caminho para persistência das janelas
CONTROL_DIR = "data/control"
WINDOW_DB_FILE = os.path.join(CONTROL_DIR, "janelas_ise.json")

class IseWindowConfig(BaseModel):
    id: Optional[str] = None
    anomes: str
    regional: str
    data_inicio: str # Formato YYYY-MM-DD HH:MM:SS
    data_fim: str    # Formato YYYY-MM-DD HH:MM:SS
    status: str = "Simulação" # Pode ser 'Simulação' ou 'Autorizada'
    
def load_windows() -> List[dict]:
    if not os.path.exists(WINDOW_DB_FILE):
        return []
    with open(WINDOW_DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
        
def save_windows(windows: List[dict]):
    os.makedirs(CONTROL_DIR, exist_ok=True)
    with open(WINDOW_DB_FILE, "w", encoding="utf-8") as f:
        json.dump(windows, f, indent=4, ensure_ascii=False)

@router.get("/janelas")
def listar_janelas():
    return {"janelas": load_windows()}

@router.post("/janelas")
def salvar_janela(janela: IseWindowConfig):
    windows = load_windows()
    if janela.id:
        # Atualizar
        for i, w in enumerate(windows):
            if w.get("id") == janela.id:
                windows[i] = janela.dict()
                break
        else:
            windows.append(janela.dict())
    else:
        import uuid
        janela.id = str(uuid.uuid4())
        windows.append(janela.dict())
        
    save_windows(windows)
    return {"mensagem": "Janela salva com sucesso", "janela": janela}

@router.get("/debug")
def debug_schema(anomes: str = "202607"):
    db_path = f"data/processed/iqs_adms_processed_{anomes}.duckdb"
    try:
        conn = duckdb.connect(db_path, read_only=True)
        cols = conn.execute("DESCRIBE gold_apuracao_uc").fetchall()
        conn.close()
        return {"columns": [c[0] for c in cols]}
    except Exception as e:
        return {"error": str(e)}

@router.post("/simular")
def simular_ise(janela: IseWindowConfig):
    anomes = janela.anomes
    db_path = f"data/processed/iqs_adms_processed_{anomes}.duckdb"
    meta_path = "data/input/META_CONJUNTO_DIA_CRITICO.csv"
    
    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail=f"Base processada não encontrada para o anomes {anomes}.")
        
    try:
        conn = duckdb.connect(db_path, read_only=True)
        
        # Carrega as Metas de Dia Crítico
        if os.path.exists(meta_path):
            conn.execute(f"CREATE TEMPORARY TABLE metas_dc AS SELECT CAST(CEA AS VARCHAR) AS CEA, CAST(META AS DOUBLE) AS META FROM read_csv_auto('{meta_path}')")
        else:
            # Fallback vazio caso o arquivo nao exista
            conn.execute("CREATE TEMPORARY TABLE metas_dc (CEA VARCHAR, META DOUBLE)")
        
        # Causas elegíveis para ISE
        causas_ise = "('2', '4', '5', '6', '7', '8', '9', '13', '15', '23', '24', '28', '39', '40', '41', '52', '54', '69', '82')"
        
        # A query principal precisa recalcular o CHI diário por Conjunto (CEA)
        
        query_ise = f"""
        WITH base_eventos AS (
            SELECT 
                a.NUM_OCORRENCIA_ADMS,
                CAST(a.NUM_UC_UCI AS VARCHAR) AS UC,
                COALESCE(CAST(v.CEA AS VARCHAR), 'N/I') AS CEA,
                CAST(a.DATA_HORA_INIC_INTRP AS DATE) AS DIA_EVENTO,
                a.DATA_HORA_INIC_INTRP,
                a.DATA_HORA_INIC_INTRP + INTERVAL (COALESCE(a.DURACAO_HORA, 0) * 60) MINUTE AS DATA_HORA_FIM_INTRP,
                CAST('{janela.data_inicio}' AS TIMESTAMP) AS JANELA_INICIO,
                CAST('{janela.data_fim}' AS TIMESTAMP) AS JANELA_FIM,
                COALESCE(a.CI_BRUTO, 0) AS CI_BRUTO,
                COALESCE(a.CI_LIQUIDO, 0) AS CI_LIQUIDO,
                COALESCE(TRIM(CAST(a.TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)), '0') AS TIPO_PROTOC,
                COALESCE(TRIM(CAST(a.COD_CAUSA_INTRP AS VARCHAR)), '') AS CAUSA
            FROM gold_apuracao_uc a
            LEFT JOIN gold_vrc v ON a.NUM_UC_UCI = v.ISN_UC
            WHERE a.NUM_UC_UCI IS NOT NULL
              AND a.DATA_HORA_INIC_INTRP >= CAST('{janela.data_inicio}' AS TIMESTAMP) - INTERVAL 2 DAY
              AND a.DATA_HORA_INIC_INTRP <= CAST('{janela.data_fim}' AS TIMESTAMP) + INTERVAL 2 DAY
        ),
        eventos_com_janela AS (
            SELECT 
                *,
                -- Verifica se o evento é elegível E intercepta a janela
                CASE WHEN CAUSA IN {causas_ise} 
                      AND DATA_HORA_INIC_INTRP <= JANELA_FIM 
                      AND DATA_HORA_FIM_INTRP >= JANELA_INICIO
                     THEN GREATEST(DATA_HORA_INIC_INTRP, JANELA_INICIO)
                     ELSE DATA_HORA_INIC_INTRP 
                END AS INICIO_SIMULADO,
                
                CASE WHEN CAUSA IN {causas_ise} 
                      AND DATA_HORA_INIC_INTRP <= JANELA_FIM 
                      AND DATA_HORA_FIM_INTRP >= JANELA_INICIO
                     THEN LEAST(DATA_HORA_FIM_INTRP, JANELA_FIM)
                     ELSE DATA_HORA_FIM_INTRP 
                END AS FIM_SIMULADO,
                
                CASE WHEN CAUSA IN {causas_ise} 
                      AND DATA_HORA_INIC_INTRP <= JANELA_FIM 
                      AND DATA_HORA_FIM_INTRP >= JANELA_INICIO
                     THEN 1 ELSE 0 END AS CAIU_NA_JANELA
            FROM base_eventos
        ),
        chi_diario_por_cea AS (
            -- Calcula o CHI total diário de cada Conjunto (após aplicar a janela ISE)
            SELECT 
                CEA, 
                DIA_EVENTO,
                SUM(EXTRACT(EPOCH FROM (FIM_SIMULADO - INICIO_SIMULADO)) / 3600.0) AS CHI_SIMULADO_DIA
            FROM eventos_com_janela
            GROUP BY CEA, DIA_EVENTO
        ),
        eventos_final_classificados AS (
            SELECT 
                e.*,
                c.CHI_SIMULADO_DIA,
                m.META,
                -- REGRA GANGORRA: Se o evento original era Dia Crítico (1), mas o novo CHI simulado ficou 
                -- abaixo da META, ele perde a isenção e vira Líquido (0)!
                CASE 
                    WHEN e.TIPO_PROTOC = '1' AND c.CHI_SIMULADO_DIA < COALESCE(m.META, 999999) THEN '0'
                    WHEN e.CAIU_NA_JANELA = 1 THEN '6' -- Aplica ISE (6) no que caiu na janela
                    ELSE e.TIPO_PROTOC
                END AS NOVO_TIPO_PROTOC
            FROM eventos_com_janela e
            LEFT JOIN chi_diario_por_cea c ON e.CEA = c.CEA AND e.DIA_EVENTO = c.DIA_EVENTO
            LEFT JOIN metas_dc m ON e.CEA = m.CEA
        )
        SELECT 
            -- Resultados Brutos ISE
            SUM(CASE WHEN CAIU_NA_JANELA = 1 THEN CI_BRUTO ELSE 0 END) AS ISE_CI_BRUTO_REFERENCIA,
            SUM(CASE WHEN CAIU_NA_JANELA = 1 AND TIPO_PROTOC IN ('0', '0.0', '') THEN CI_LIQUIDO ELSE 0 END) AS ISE_CI_LIQUIDO_RECLASSIFICAVEL,
            SUM(CASE WHEN CAIU_NA_JANELA = 1 THEN EXTRACT(EPOCH FROM (FIM_SIMULADO - INICIO_SIMULADO)) / 3600.0 ELSE 0 END) AS ISE_CHI_BRUTO_REFERENCIA,
            SUM(CASE WHEN CAIU_NA_JANELA = 1 AND TIPO_PROTOC IN ('0', '0.0', '') THEN EXTRACT(EPOCH FROM (FIM_SIMULADO - INICIO_SIMULADO)) / 3600.0 ELSE 0 END) AS ISE_CHI_LIQUIDO_RECLASSIFICAVEL,
            
            -- Auditoria da Gangorra do Dia Critico
            COUNT(CASE WHEN TIPO_PROTOC = '1' AND NOVO_TIPO_PROTOC = '0' THEN 1 END) AS QTD_UCS_PERDERAM_DIA_CRITICO
        FROM eventos_final_classificados
        """
        
        df_resultados = conn.execute(query_ise).df()
        
        # 2. Simulação Financeira (MOCK baseando-se no efeito de UCs perdidas vs Ganhadas)
        # O cálculo final exato em R$ requererá leitura de VRC/META_DIC
        qtd_perdida = int(df_resultados['QTD_UCS_PERDERAM_DIA_CRITICO'].iloc[0])
        chi_salvo = float(df_resultados['ISE_CHI_LIQUIDO_RECLASSIFICAVEL'].iloc[0])
        
        # Estimativa Mock de R$ (100 reais de economia por CHI isento, menos 500 reais de multa por UC que perdeu isenção)
        economia_ise = chi_salvo * 100
        multa_reversa = qtd_perdida * 500
        ganho_real = economia_ise - multa_reversa
        
        conn.close()
        
        return {
            "janela": janela.dict(),
            "resultados_ise": df_resultados.to_dict(orient="records")[0],
            "simulacao_financeira": {
                "DIC_ORIGINAL_RS": 152000.50,
                "DIC_COM_ISE_RS": 152000.50 - ganho_real,
                "FIC_ORIGINAL_RS": 85000.20,
                "FIC_COM_ISE_RS": 85000.20 - (ganho_real * 0.4),
                "DISE_GANHO_RS": ganho_real,
                "UCS_QUE_PERDERAM_ISENCAO_DC": qtd_perdida
            }
        }
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        raise HTTPException(status_code=500, detail=str(e))
