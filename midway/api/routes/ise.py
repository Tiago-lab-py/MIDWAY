import os
import json
import duckdb
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks
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

@router.delete("/janelas/{janela_id}")
def deletar_janela(janela_id: str):
    windows = load_windows()
    windows = [w for w in windows if w.get("id") != janela_id]
    save_windows(windows)
    return {"mensagem": "Janela excluída com sucesso"}

@router.get("/debug")
def debug_schema(anomes: str = "202607"):
    db_path = f"data/processed/iqs_adms_processed_{anomes}.duckdb"
    try:
        conn = duckdb.connect(db_path, read_only=True)
        cols = conn.execute("DESCRIBE gold_ressarcimento_prodist").fetchall()
        conn.close()
        return {"columns": [c[0] for c in cols]}
    except Exception as e:
        return {"error": str(e)}

def process_ise_bg(janela: IseWindowConfig, db_path: str):
    try:
        from midway.apuracao.continuidade import criar_gold_continuidade_uc
        from midway.apuracao.ressarcimento import criar_gold_ressarcimento_prodist
        
        conn = duckdb.connect()
        conn.execute(f"ATTACH '{db_path}' AS adms (READ_ONLY)")
        
        # 1. Copiar tabelas necessárias
        for tbl in ["gold_apuracao_uc", "gold_interrupcao_tratada", "gold_uc_fatura", "gold_metas_uc", "gold_vrc", "gold_continuidade_uc", "gold_ressarcimento_prodist"]:
            try:
                conn.execute(f"CREATE TABLE main.{tbl} AS SELECT * FROM adms.{tbl}")
            except Exception:
                if tbl == "gold_interrupcao_tratada":
                    conn.execute("CREATE TABLE main.gold_interrupcao_tratada (NUM_OCORRENCIA_ADMS VARCHAR, NUM_SEQ_INTRP VARCHAR, NUM_OPER_CHV_INTRP VARCHAR, NUM_UC_UCI VARCHAR, INDIC_PROPR_CHVP_INTRP VARCHAR, UC_ACESSANTE VARCHAR)")
                
        # Tabela base da simulação
        conn.execute("CREATE TABLE main.gold_apuracao_uc_ise AS SELECT * FROM main.gold_apuracao_uc")
        
        # 2. Ler todas as janelas
        windows = [w for w in load_windows() if w.get('anomes') == janela.anomes and w.get('status') in ('Simulação', 'Autorizada')]
        if not any(w.get('id') == janela.id for w in windows):
            windows.append(janela.dict())
            
        causas_ise = "('2', '4', '5', '6', '7', '8', '9', '13', '15', '23', '24', '28', '39', '40', '41', '52', '54', '69', '82')"
        
        for w in windows:
            inicio = w['data_inicio'].replace('T', ' ')
            fim = w['data_fim'].replace('T', ' ')
            if len(inicio) == 16: inicio += ':00'
            if len(fim) == 16: fim += ':00'
            
            conn.execute(f"""
                UPDATE main.gold_apuracao_uc_ise
                SET TIPO_PROTOC_JUSTIF_UCI = '6'
                WHERE TRIM(CAST(COD_CAUSA_INTRP AS VARCHAR)) IN {causas_ise}
                  AND DATA_HORA_INIC_INTRP <= CAST('{fim}' AS TIMESTAMP)
                  AND DATA_HORA_INIC_INTRP + INTERVAL (COALESCE(DURACAO_HORA, 0) * 60) MINUTE >= CAST('{inicio}' AS TIMESTAMP)
            """)
            
        # 3. Efeito Gangorra
        meta_path = "data/input/META_CONJUNTO_DIA_CRITICO.csv"
        if os.path.exists(meta_path):
            conn.execute(f"CREATE TABLE main.metas_dc AS SELECT CAST(CEA AS VARCHAR) AS CEA, CAST(META AS DOUBLE) AS META FROM read_csv_auto('{meta_path}')")
        else:
            conn.execute("CREATE TABLE main.metas_dc (CEA VARCHAR, META DOUBLE)")

        conn.execute("""
            UPDATE main.gold_apuracao_uc_ise
            SET TIPO_PROTOC_JUSTIF_UCI = '0'
            FROM (
                WITH chi_diario AS (
                    SELECT 
                        v.CEA,
                        CAST(a.DATA_HORA_INIC_INTRP AS DATE) AS DIA_EVENTO,
                        SUM(COALESCE(a.DURACAO_HORA, 0)) AS CHI_TOTAL
                    FROM main.gold_apuracao_uc_ise a
                    INNER JOIN main.gold_vrc v ON CAST(a.NUM_UC_UCI AS VARCHAR) = CAST(v.ISN_UC AS VARCHAR)
                    WHERE a.TIPO_PROTOC_JUSTIF_UCI != '6'
                    GROUP BY v.CEA, CAST(a.DATA_HORA_INIC_INTRP AS DATE)
                ),
                conjuntos_rebaixados AS (
                    SELECT c.CEA, c.DIA_EVENTO
                    FROM chi_diario c
                    LEFT JOIN main.metas_dc m ON c.CEA = m.CEA
                    WHERE c.CHI_TOTAL < COALESCE(m.META, 999999)
                )
                SELECT CAST(a2.NUM_OCORRENCIA_ADMS AS VARCHAR) as ocorrencia, 
                       CAST(a2.NUM_SEQ_INTRP AS VARCHAR) as seq, 
                       CAST(a2.NUM_UC_UCI AS VARCHAR) as uc
                FROM main.gold_apuracao_uc_ise a2
                INNER JOIN main.gold_vrc v2 ON CAST(a2.NUM_UC_UCI AS VARCHAR) = CAST(v2.ISN_UC AS VARCHAR)
                INNER JOIN conjuntos_rebaixados cr ON v2.CEA = cr.CEA AND CAST(a2.DATA_HORA_INIC_INTRP AS DATE) = cr.DIA_EVENTO
                WHERE a2.TIPO_PROTOC_JUSTIF_UCI = '1'
            ) AS sub
            WHERE CAST(main.gold_apuracao_uc_ise.NUM_OCORRENCIA_ADMS AS VARCHAR) = sub.ocorrencia
              AND CAST(main.gold_apuracao_uc_ise.NUM_SEQ_INTRP AS VARCHAR) = sub.seq
              AND CAST(main.gold_apuracao_uc_ise.NUM_UC_UCI AS VARCHAR) = sub.uc
              AND main.gold_apuracao_uc_ise.TIPO_PROTOC_JUSTIF_UCI = '1'
        """)
        
        # 4. Rodar o PRODIST real!
        criar_gold_continuidade_uc(conn, sufixo="_ise")
        criar_gold_ressarcimento_prodist(conn, sufixo="_ise")
        
        # Extração Financeira
        df_orig = conn.execute("SELECT SUM(COMP_DIC_BRUTA_PRODIST) AS DIC, SUM(COMP_FIC_BRUTA_PRODIST) AS FIC, SUM(COMP_DMIC_BRUTA_PRODIST) AS DMIC, SUM(COMP_DICRI_BRUTA_PRODIST) AS DICRI, SUM(COMP_DISE_BRUTA_PRODIST) AS DISE FROM main.gold_ressarcimento_prodist").df()
        df_ise = conn.execute("SELECT SUM(COMP_DIC_BRUTA_PRODIST) AS DIC, SUM(COMP_FIC_BRUTA_PRODIST) AS FIC, SUM(COMP_DMIC_BRUTA_PRODIST) AS DMIC, SUM(COMP_DICRI_BRUTA_PRODIST) AS DICRI, SUM(COMP_DISE_BRUTA_PRODIST) AS DISE FROM main.gold_ressarcimento_prodist_ise").df()
        
        dic_orig = float(df_orig['DIC'].iloc[0] or 0) if not df_orig.empty else 0
        fic_orig = float(df_orig['FIC'].iloc[0] or 0) if not df_orig.empty else 0
        dmic_orig = float(df_orig['DMIC'].iloc[0] or 0) if not df_orig.empty else 0
        dicri_orig = float(df_orig['DICRI'].iloc[0] or 0) if not df_orig.empty else 0
        dise_orig = float(df_orig['DISE'].iloc[0] or 0) if not df_orig.empty else 0
        
        dic_projetado = float(df_ise['DIC'].iloc[0] or 0) if not df_ise.empty else 0
        fic_projetado = float(df_ise['FIC'].iloc[0] or 0) if not df_ise.empty else 0
        dmic_projetado = float(df_ise['DMIC'].iloc[0] or 0) if not df_ise.empty else 0
        dicri_projetado = float(df_ise['DICRI'].iloc[0] or 0) if not df_ise.empty else 0
        dise_projetado = float(df_ise['DISE'].iloc[0] or 0) if not df_ise.empty else 0
        
        total_sem_ise = dic_orig + fic_orig + dmic_orig + dicri_orig + dise_orig
        total_com_ise = dic_projetado + fic_projetado + dmic_projetado + dicri_projetado + dise_projetado
        
        # 5. Série Temporal para o gráfico (da janela atual apenas)
        def _parse_dt(d_str):
            d = d_str.replace('T', ' ')
            if len(d) == 16: d += ':00'
            return datetime.strptime(d, "%Y-%m-%d %H:%M:%S")
            
        start_dt = _parse_dt(janela.data_inicio)
        end_dt = _parse_dt(janela.data_fim)
        
        query_raw_events = f"""
            SELECT 
                GREATEST(DATA_HORA_INIC_INTRP, CAST('{start_dt}' AS TIMESTAMP)) AS INICIO_SIMULADO,
                LEAST(DATA_HORA_INIC_INTRP + INTERVAL (COALESCE(DURACAO_HORA, 0) * 60) MINUTE, CAST('{end_dt}' AS TIMESTAMP)) AS FIM_SIMULADO,
                CAST(NUM_UC_UCI AS VARCHAR) AS UC
            FROM main.gold_apuracao_uc_ise
            WHERE TRIM(CAST(COD_CAUSA_INTRP AS VARCHAR)) IN {causas_ise}
              AND DATA_HORA_INIC_INTRP <= CAST('{end_dt}' AS TIMESTAMP)
              AND DATA_HORA_INIC_INTRP + INTERVAL (COALESCE(DURACAO_HORA, 0) * 60) MINUTE >= CAST('{start_dt}' AS TIMESTAMP)
        """
        df_raw = conn.execute(query_raw_events).df()
        
        serie_temporal = []
        peak_time = None
        peak_ci = 0
        if not df_raw.empty:
            from datetime import timedelta
            start_hour = start_dt.replace(minute=0, second=0, microsecond=0)
            end_hour = end_dt.replace(minute=0, second=0, microsecond=0)
            if end_dt > end_hour: end_hour += timedelta(hours=1)
            curr_hour = start_hour
            hourly_ci = []
            while curr_hour <= end_hour:
                mask = (df_raw['INICIO_SIMULADO'] <= curr_hour) & (df_raw['FIM_SIMULADO'] >= curr_hour)
                ci_count = int(df_raw[mask]['UC'].nunique())
                hourly_ci.append((curr_hour, ci_count))
                curr_hour += timedelta(hours=1)
            for h, c in hourly_ci:
                if c > peak_ci: peak_ci, peak_time = c, h
            for h, c in hourly_ci:
                rec_pct = max(0.0, min(1.0, c / peak_ci)) if peak_time and h > peak_time and peak_ci > 0 else None
                serie_temporal.append({"hora": h.strftime("%Y-%m-%d %H:%M"), "ci": c, "rec_pct": rec_pct})
            peak_time = peak_time.strftime("%Y-%m-%d %H:%M") if peak_time else None
            
        resultado = {
            "status": "CONCLUIDO",
            "janela": janela.dict(),
            "simulacao_financeira": {
                "DIC_ORIGINAL_RS": dic_orig,
                "DIC_COM_ISE_RS": dic_projetado,
                "FIC_ORIGINAL_RS": fic_orig,
                "FIC_COM_ISE_RS": fic_projetado,
                "DMIC_ORIGINAL_RS": dmic_orig,
                "DMIC_COM_ISE_RS": dmic_projetado,
                "DICRI_ORIGINAL_RS": dicri_orig,
                "DICRI_COM_ISE_RS": dicri_projetado,
                "DISE_ORIGINAL_RS": dise_orig,
                "DISE_COM_ISE_RS": dise_projetado,
                "DISE_GANHO_RS": total_sem_ise - total_com_ise,
            },
            "serie_temporal": serie_temporal,
            "metadados_grafico": {
                "peak_time": peak_time if not df_raw.empty else None,
                "peak_val": peak_ci if not df_raw.empty else 0
            }
        }
        
        # Salva resultado final
        windows_final = load_windows()
        for i, w in enumerate(windows_final):
            if w.get('id') == janela.id:
                windows_final[i]['resultado'] = resultado
                break
        else:
            jdict = janela.dict()
            jdict['resultado'] = resultado
            windows_final.append(jdict)
        save_windows(windows_final)
        
    except Exception as e:
        import traceback
        print(f"Erro no background ISE: {traceback.format_exc()}")
        resultado = {"status": "ERRO", "mensagem": str(e)}
        windows_final = load_windows()
        for i, w in enumerate(windows_final):
            if w.get('id') == janela.id:
                windows_final[i]['resultado'] = resultado
                break
        save_windows(windows_final)
    finally:
        if 'conn' in locals():
            conn.close()

@router.post("/simular")
def simular_ise(janela: IseWindowConfig, background_tasks: BackgroundTasks):
    anomes = janela.anomes
    db_path = f"data/processed/iqs_adms_processed_{anomes}.duckdb"
    
    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail=f"Base processada não encontrada para o anomes {anomes}.")
        
    import uuid
    if not janela.id:
        janela.id = str(uuid.uuid4())
        windows = load_windows()
        windows.append(janela.dict())
        save_windows(windows)
        
    background_tasks.add_task(process_ise_bg, janela, db_path)
    return {"status": "PROCESSANDO", "janela_id": janela.id}

@router.get("/resultado/{janela_id}")
def get_resultado(janela_id: str):
    windows = load_windows()
    for w in windows:
        if w.get('id') == janela_id:
            if 'resultado' in w:
                return w['resultado']
            else:
                return {"status": "PROCESSANDO"}
    raise HTTPException(status_code=404, detail="Janela não encontrada")
