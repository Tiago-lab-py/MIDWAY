import os
import json
import duckdb
import plotly.graph_objects as go
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
    id_evento: Optional[int] = None
    descritivo: Optional[str] = None
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
def delete_janela(janela_id: str):
    windows = load_windows()
    windows = [w for w in windows if w.get('id') != janela_id]
    save_windows(windows)
    return {"status": "ok"}

@router.put("/janelas/{janela_id}")
def update_janela(janela_id: str, janela: IseWindowConfig):
    windows = load_windows()
    updated = False
    for i, w in enumerate(windows):
        if w.get('id') == janela_id:
            w['regional'] = janela.regional
            w['data_inicio'] = janela.data_inicio
            w['data_fim'] = janela.data_fim
            w['anomes'] = janela.anomes
            w['id_evento'] = janela.id_evento
            w['descritivo'] = janela.descritivo
            w['status'] = 'Simulação'
            if 'resultado' in w:
                del w['resultado']
            updated = True
            break
            
    if not updated:
        raise HTTPException(status_code=404, detail="Janela não encontrada")
        
    save_windows(windows)
    return {"status": "ok"}

@router.get("/debug")
def debug_schema(anomes: str = "202607"):
    db_path = f"data/raw/adms_servicos_raw_{anomes}.duckdb"
    try:
        conn = duckdb.connect(db_path, read_only=True)
        tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
        schema = {}
        for t in tables:
            cols = conn.execute(f"DESCRIBE {t}").fetchall()
            schema[t] = [c[0] for c in cols]
        conn.close()
        return {"tables": schema}
    except Exception as e:
        return {"error": str(e)}

def process_ise_bg(janela: IseWindowConfig, db_path: str):
    try:
        from midway.apuracao.continuidade import criar_gold_continuidade_uc
        from midway.apuracao.ressarcimento import criar_gold_ressarcimento_prodist
        
        conn = duckdb.connect()
        conn.execute(f"ATTACH '{db_path}' AS adms (READ_ONLY)")
        try:
            conn.execute(f"ATTACH 'data/raw/adms_servicos_raw_{janela.anomes}.duckdb' AS servicos (READ_ONLY)")
        except Exception as e:
            pass
        
        # 1. Copiar tabelas necessárias
        for tbl in ["gold_apuracao_uc", "gold_interrupcao_tratada", "gold_uc_fatura", "gold_metas_uc", "gold_vrc", "gold_continuidade_uc", "gold_ressarcimento_prodist"]:
            try:
                conn.execute(f"CREATE TABLE main.{tbl} AS SELECT * FROM adms.{tbl}")
            except Exception:
                if tbl == "gold_interrupcao_tratada":
                    conn.execute("CREATE TABLE main.gold_interrupcao_tratada (NUM_OCORRENCIA_ADMS VARCHAR, NUM_SEQ_INTRP VARCHAR, NUM_OPER_CHV_INTRP VARCHAR, NUM_UC_UCI VARCHAR, INDIC_PROPR_CHVP_INTRP VARCHAR, UC_ACESSANTE VARCHAR)")
                
        # Tabela base da simulação
        conn.execute("CREATE TABLE main.gold_apuracao_uc_ise AS SELECT * FROM main.gold_apuracao_uc")
        
        # 2. Ler as janelas: Apenas as implantadas (Autorizada) + a janela atual da simulação
        all_windows = load_windows()
        windows = [w for w in all_windows if w.get('anomes') == janela.anomes and w.get('status') == 'Autorizada']
        
        # Garante que a janela atual será aplicada (se já não estiver na lista)
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
                WITH ocorrencias_com_servico AS (
                    SELECT DISTINCT CAST(PID_INTRP_SRVE AS VARCHAR) AS PID
                    FROM servicos.raw_adms_servicos
                    WHERE DTHR_SAIDA_SRV IS NOT NULL
                ),
                ocorrencias_diarias AS (
                    SELECT 
                        v.CEA,
                        CAST(a.DATA_HORA_INIC_INTRP AS DATE) AS DIA_EVENTO,
                        COUNT(DISTINCT a.NUM_OCORRENCIA_ADMS) AS QTD_OCORRENCIAS
                    FROM main.gold_apuracao_uc_ise a
                    INNER JOIN main.gold_vrc v ON CAST(a.NUM_UC_UCI AS VARCHAR) = CAST(v.ISN_UC AS VARCHAR)
                    INNER JOIN ocorrencias_com_servico s ON CAST(a.NUM_SEQ_INTRP AS VARCHAR) = s.PID
                    WHERE a.TIPO_PROTOC_JUSTIF_UCI != '6'
                    GROUP BY v.CEA, CAST(a.DATA_HORA_INIC_INTRP AS DATE)
                ),
                conjuntos_rebaixados AS (
                    SELECT c.CEA, c.DIA_EVENTO
                    FROM ocorrencias_diarias c
                    LEFT JOIN main.metas_dc m ON c.CEA = m.CEA
                    WHERE c.QTD_OCORRENCIAS < COALESCE(m.META, 999999)
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
        
        # Extrai também as Unidades e Horas que efetivamente geraram penalidade (Líquido - TIPO != 6) e o total absoluto (Bruto)
        def _parse_dt(d_str):
            d = d_str.replace('T', ' ')
            if len(d) == 16: d += ':00'
            return datetime.strptime(d, "%Y-%m-%d %H:%M:%S")
            
        start_dt = _parse_dt(janela.data_inicio)
        end_dt = _parse_dt(janela.data_fim)
        where_clause = f"WHERE DATA_HORA_INIC_INTRP <= CAST('{end_dt}' AS TIMESTAMP) AND DATA_HORA_INIC_INTRP + INTERVAL (COALESCE(DURACAO_HORA, 0) * 60) MINUTE >= CAST('{start_dt}' AS TIMESTAMP)"
        
        # Otimização: Consolida as consultas brutas e líquidas num único SCAN da tabela original
        df_orig_kpi = conn.execute(f"""
            SELECT 
                COUNT(DISTINCT NUM_UC_UCI) as CI_BRUTO, 
                SUM(COALESCE(DURACAO_HORA, 0)) as CHI_BRUTO,
                COUNT(DISTINCT CASE WHEN TIPO_PROTOC_JUSTIF_UCI != '6' THEN NUM_UC_UCI END) as CI_LIQ,
                SUM(CASE WHEN TIPO_PROTOC_JUSTIF_UCI != '6' THEN COALESCE(DURACAO_HORA, 0) ELSE 0 END) as CHI_LIQ
            FROM adms.gold_apuracao_uc 
            {where_clause}
        """).df()
        
        # Otimização: Consolida as consultas brutas e líquidas num único SCAN da tabela projetada
        df_ise_kpi = conn.execute(f"""
            SELECT 
                COUNT(DISTINCT NUM_UC_UCI) as CI_BRUTO, 
                SUM(COALESCE(DURACAO_HORA, 0)) as CHI_BRUTO,
                COUNT(DISTINCT CASE WHEN TIPO_PROTOC_JUSTIF_UCI != '6' THEN NUM_UC_UCI END) as CI_LIQ,
                SUM(CASE WHEN TIPO_PROTOC_JUSTIF_UCI != '6' THEN COALESCE(DURACAO_HORA, 0) ELSE 0 END) as CHI_LIQ
            FROM main.gold_apuracao_uc_ise 
            {where_clause}
        """).df()
        
        import pandas as pd
        def get_val(df, col, is_int=False):
            if df.empty: return 0
            val = df[col].iloc[0]
            if pd.isna(val): return 0
            return int(val) if is_int else float(val)
        
        dic_orig = float(df_orig['DIC'].iloc[0] or 0) if not df_orig.empty else 0
        fic_orig = float(df_orig['FIC'].iloc[0] or 0) if not df_orig.empty else 0
        dmic_orig = float(df_orig['DMIC'].iloc[0] or 0) if not df_orig.empty else 0
        dicri_orig = float(df_orig['DICRI'].iloc[0] or 0) if not df_orig.empty else 0
        dise_orig = float(df_orig['DISE'].iloc[0] or 0) if not df_orig.empty else 0
        
        chi_bruto_orig = get_val(df_orig_kpi, 'CHI_BRUTO')
        ci_bruto_orig = get_val(df_orig_kpi, 'CI_BRUTO', True)
        chi_orig = get_val(df_orig_kpi, 'CHI_LIQ')
        ci_orig = get_val(df_orig_kpi, 'CI_LIQ', True)
        
        dic_projetado = float(df_ise['DIC'].iloc[0] or 0) if not df_ise.empty else 0
        fic_projetado = float(df_ise['FIC'].iloc[0] or 0) if not df_ise.empty else 0
        dmic_projetado = float(df_ise['DMIC'].iloc[0] or 0) if not df_ise.empty else 0
        dicri_projetado = float(df_ise['DICRI'].iloc[0] or 0) if not df_ise.empty else 0
        dise_projetado = float(df_ise['DISE'].iloc[0] or 0) if not df_ise.empty else 0
        
        chi_bruto_projetado = get_val(df_ise_kpi, 'CHI_BRUTO')
        ci_bruto_projetado = get_val(df_ise_kpi, 'CI_BRUTO', True)
        chi_projetado = get_val(df_ise_kpi, 'CHI_LIQ')
        ci_projetado = get_val(df_ise_kpi, 'CI_LIQ', True)

        
        total_sem_ise = dic_orig + fic_orig + dmic_orig + dicri_orig + dise_orig
        total_com_ise = dic_projetado + fic_projetado + dmic_projetado + dicri_projetado + dise_projetado
        
        # 5. Métricas Executivas e Série Temporal
        
        # 5.1 KPIs de CI e CHI
        kpi_query = f"""
            SELECT
                COUNT(DISTINCT NUM_UC_UCI) AS ci_total,
                SUM(COALESCE(DURACAO_HORA, 0)) AS chi_total,
                COUNT(DISTINCT CASE WHEN TIPO_PROTOC_JUSTIF_UCI = '6' THEN NUM_UC_UCI END) AS ci_tipo6,
                SUM(CASE WHEN TIPO_PROTOC_JUSTIF_UCI = '6' THEN COALESCE(DURACAO_HORA, 0) ELSE 0 END) AS chi_tipo6,
                COUNT(DISTINCT CASE WHEN TIPO_PROTOC_JUSTIF_UCI = '0' THEN NUM_UC_UCI END) AS ci_tipo0,
                SUM(CASE WHEN TIPO_PROTOC_JUSTIF_UCI = '0' THEN COALESCE(DURACAO_HORA, 0) ELSE 0 END) AS chi_tipo0
            FROM main.gold_apuracao_uc_ise
            WHERE DATA_HORA_INIC_INTRP <= CAST('{end_dt}' AS TIMESTAMP)
              AND DATA_HORA_INIC_INTRP + INTERVAL (COALESCE(DURACAO_HORA, 0) * 60) MINUTE >= CAST('{start_dt}' AS TIMESTAMP)
        """
        df_kpi = conn.execute(kpi_query).df()
        
        ci_total = int(df_kpi['ci_total'].iloc[0])
        chi_total = float(df_kpi['chi_total'].iloc[0] or 0)
        ci_tipo6 = int(df_kpi['ci_tipo6'].iloc[0])
        chi_tipo6 = float(df_kpi['chi_tipo6'].iloc[0] or 0)
        ci_tipo0 = int(df_kpi['ci_tipo0'].iloc[0])
        chi_tipo0 = float(df_kpi['chi_tipo0'].iloc[0] or 0)
        
        # 5.2 Conjuntos Rebaixados (Perda de Dia Crítico)
        q_conj = f"""
            SELECT COUNT(DISTINCT v.CEA) AS conj
            FROM main.gold_apuracao_uc_ise a
            INNER JOIN main.gold_vrc v ON CAST(a.NUM_UC_UCI AS VARCHAR) = CAST(v.ISN_UC AS VARCHAR)
            WHERE a.TIPO_PROTOC_JUSTIF_UCI = '0'
              AND a.DATA_HORA_INIC_INTRP <= CAST('{end_dt}' AS TIMESTAMP)
              AND a.DATA_HORA_INIC_INTRP + INTERVAL (COALESCE(DURACAO_HORA, 0) * 60) MINUTE >= CAST('{start_dt}' AS TIMESTAMP)
        """
        conj_rebaixados = int(conn.execute(q_conj).df()['conj'].iloc[0])
        
        # 5.3 Série Temporal (CHI por Hora para Gráfico)
        serie_query = f"""
            WITH RECURSIVE horas(h) AS (
                SELECT date_trunc('hour', CAST('{start_dt}' AS TIMESTAMP))
                UNION ALL
                SELECT h + INTERVAL 1 HOUR FROM horas WHERE h < date_trunc('hour', CAST('{end_dt}' AS TIMESTAMP)) + INTERVAL 1 HOUR
            )
            SELECT 
                strftime(h.h, '%Y-%m-%d %H:00') AS hora,
                COALESCE(i.SIGLA_REGIONAL, 'N/I') AS regional,
                SUM(
                    CASE 
                        WHEN a.DATA_HORA_INIC_INTRP IS NOT NULL THEN 
                            (EXTRACT(EPOCH FROM LEAST(a.DATA_HORA_INIC_INTRP + INTERVAL (COALESCE(a.DURACAO_HORA, 0) * 60) MINUTE, h.h + INTERVAL 1 HOUR)) -
                             EXTRACT(EPOCH FROM GREATEST(a.DATA_HORA_INIC_INTRP, h.h))) / 3600.0
                        ELSE 0 
                    END
                ) AS chi_hora,
                COUNT(DISTINCT a.NUM_UC_UCI) AS ci_hora
            FROM horas h
            LEFT JOIN main.gold_apuracao_uc_ise a 
              ON a.DATA_HORA_INIC_INTRP <= h.h + INTERVAL 1 HOUR
             AND a.DATA_HORA_INIC_INTRP + INTERVAL (COALESCE(a.DURACAO_HORA, 0) * 60) MINUTE >= h.h
             AND TRIM(CAST(a.COD_CAUSA_INTRP AS VARCHAR)) IN {causas_ise}
            LEFT JOIN main.gold_interrupcao_tratada i
              ON CAST(a.NUM_OCORRENCIA_ADMS AS VARCHAR) = CAST(i.NUM_OCORRENCIA_ADMS AS VARCHAR)
             AND CAST(a.NUM_SEQ_INTRP AS VARCHAR) = CAST(i.NUM_SEQ_INTRP AS VARCHAR)
             AND CAST(a.NUM_UC_UCI AS VARCHAR) = CAST(i.NUM_UC_UCI AS VARCHAR)
            GROUP BY h.h, COALESCE(i.SIGLA_REGIONAL, 'N/I')
            ORDER BY h.h, COALESCE(i.SIGLA_REGIONAL, 'N/I')
        """
        df_serie = conn.execute(serie_query).df()
        
        mapa_reg = {
            'C': 'LES',
            'V': 'OES',
            'P': 'CSL',
            'M': 'MGA',
            'L': 'NRT'
        }
        
        import pandas as pd
        serie_dict = {}
        for h in df_serie['hora'].unique():
            if pd.isna(h): continue
            serie_dict[h] = {"hora": h, "chi_hora": 0, "ci": 0, "regionais": {}, "regionais_ci": {}}
            
        chi_acum = 0.0
        max_ci = 0
        sorted_hours = sorted(list(serie_dict.keys()))
        for h in sorted_hours:
            rows = df_serie[df_serie['hora'] == h]
            h_chi = 0
            h_ci = 0
            for _, row in rows.iterrows():
                v_chi = float(row['chi_hora'] or 0)
                v_ci = int(row['ci_hora'] or 0)
                
                reg_raw = str(row['regional']).upper()
                reg = mapa_reg.get(reg_raw, reg_raw)
                
                if v_chi > 0:
                    if reg not in serie_dict[h]["regionais"]:
                        serie_dict[h]["regionais"][reg] = 0
                    serie_dict[h]["regionais"][reg] += v_chi
                    h_chi += v_chi
                    
                if v_ci > 0:
                    if reg not in serie_dict[h]["regionais_ci"]:
                        serie_dict[h]["regionais_ci"][reg] = 0
                    serie_dict[h]["regionais_ci"][reg] += v_ci
                    h_ci += v_ci
            
            chi_acum += h_chi
            serie_dict[h]["chi_hora"] = round(h_chi, 2)
            serie_dict[h]["chi_acumulado"] = round(chi_acum, 2)
            serie_dict[h]["ci"] = h_ci
            if h_ci > max_ci: max_ci = h_ci
            for r in serie_dict[h]["regionais"]:
                serie_dict[h]["regionais"][r] = round(serie_dict[h]["regionais"][r], 2)
                
        # Calcula recomposição
        for h in sorted_hours:
            ci = serie_dict[h]["ci"]
            serie_dict[h]["rec_pct"] = (max_ci - ci) / max_ci if max_ci > 0 else 0
                
        serie_temporal = [serie_dict[h] for h in sorted_hours]
            
        # 5.4 Matriz de Conjuntos (Antes vs Depois)
        q_conjuntos = f"""
            WITH antes AS (
                SELECT 
                    COALESCE(v.NOME_CONJUNTO_ANEEL, 'DESCONHECIDO') AS conjunto,
                    a.TIPO_PROTOC_JUSTIF_UCI AS protocolo,
                    COUNT(DISTINCT a.NUM_UC_UCI) AS ci_antes,
                    SUM(COALESCE(a.DURACAO_HORA, 0)) AS chi_antes
                FROM adms.gold_apuracao_uc a
                LEFT JOIN main.gold_vrc v ON CAST(a.NUM_UC_UCI AS VARCHAR) = CAST(v.ISN_UC AS VARCHAR)
                {where_clause}
                GROUP BY 1, 2
            ),
            depois AS (
                SELECT 
                    COALESCE(v.NOME_CONJUNTO_ANEEL, 'DESCONHECIDO') AS conjunto,
                    a.TIPO_PROTOC_JUSTIF_UCI AS protocolo,
                    COUNT(DISTINCT a.NUM_UC_UCI) AS ci_depois,
                    SUM(COALESCE(a.DURACAO_HORA, 0)) AS chi_depois
                FROM main.gold_apuracao_uc_ise a
                LEFT JOIN main.gold_vrc v ON CAST(a.NUM_UC_UCI AS VARCHAR) = CAST(v.ISN_UC AS VARCHAR)
                {where_clause}
                GROUP BY 1, 2
            )
            SELECT 
                COALESCE(a.conjunto, d.conjunto) AS conjunto,
                COALESCE(a.protocolo, d.protocolo) AS protocolo,
                COALESCE(a.ci_antes, 0) AS ci_antes,
                COALESCE(d.ci_depois, 0) AS ci_depois,
                COALESCE(a.chi_antes, 0) AS chi_antes,
                COALESCE(d.chi_depois, 0) AS chi_depois
            FROM antes a
            FULL OUTER JOIN depois d ON a.conjunto = d.conjunto AND a.protocolo = d.protocolo
            ORDER BY 1, 2
        """
        df_conj = conn.execute(q_conjuntos).df()
        tabela_conjuntos = []
        for _, r in df_conj.iterrows():
            tabela_conjuntos.append({
                "conjunto": str(r["conjunto"]),
                "protocolo": str(r["protocolo"]),
                "ci_antes": int(r["ci_antes"]),
                "ci_depois": int(r["ci_depois"]),
                "chi_antes": round(float(r["chi_antes"]), 2),
                "chi_depois": round(float(r["chi_depois"]), 2)
            })
            
        resultado = {
            "status": "CONCLUIDO",
            "janela": janela.dict(),
            "ci_total": ci_total,
            "chi_total": round(chi_total, 2),
            "ci_tipo6": ci_tipo6,
            "chi_tipo6": round(chi_tipo6, 2),
            "ci_tipo0": ci_tipo0,
            "chi_tipo0": round(chi_tipo0, 2),
            "conjuntos_rebaixados": conj_rebaixados,
            "serie_temporal": serie_temporal,
            "tabela_conjuntos": tabela_conjuntos,
            "simulacao_financeira": {
                "CHI_BRUTO_ORIGINAL": chi_bruto_orig,
                "CHI_BRUTO_COM_ISE": chi_bruto_projetado,
                "CHI_ORIGINAL": chi_orig,
                "CHI_COM_ISE": chi_projetado,
                "CI_BRUTO_ORIGINAL": ci_bruto_orig,
                "CI_BRUTO_COM_ISE": ci_bruto_projetado,
                "CI_ORIGINAL": ci_orig,
                "CI_COM_ISE": ci_projetado,
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

class ImplantarLoteRequest(BaseModel):
    ids: List[str]

@router.post("/implantar_lote")
def implantar_lote(req: ImplantarLoteRequest):
    windows = load_windows()
    modificadas = 0
    for w in windows:
        if w.get('id') in req.ids:
            w['status'] = 'Autorizada'
            modificadas += 1
    if modificadas > 0:
        save_windows(windows)
    return {"message": f"{modificadas} janelas implantadas com sucesso"}

@router.get("/exportar_lote")
def exportar_lote(ids: str):
    lista_ids = ids.split(",")
    windows = [w for w in load_windows() if w.get('id') in lista_ids and w.get('status') == 'Autorizada']
    if not windows:
        raise HTTPException(status_code=400, detail="Nenhuma janela Autorizada encontrada.")
        
    anomes_set = set(w['anomes'] for w in windows)
    dfs = []
    
    causas_ise = "('2', '4', '5', '6', '7', '8', '9', '13', '15', '23', '24', '28', '39', '40', '41', '52', '54', '69', '82')"
    
    for anomes in anomes_set:
        db_path = f"data/processed/iqs_adms_processed_{anomes}.duckdb"
        if not os.path.exists(db_path): continue
            
        conn = duckdb.connect()
        conn.execute(f"ATTACH '{db_path}' AS adms (READ_ONLY)")
        
        # Copia apenas as tabelas necessarias para descobrir as alteracoes
        conn.execute("CREATE TABLE main.gold_apuracao_uc AS SELECT * FROM adms.gold_apuracao_uc")
        conn.execute("CREATE TABLE main.gold_vrc AS SELECT * FROM adms.gold_vrc")
        
        conn.execute("CREATE TABLE main.gold_apuracao_uc_ise AS SELECT * FROM main.gold_apuracao_uc")
        
        # Aplica a regra de ISE na tabela principal apenas para as janelas deste anomes
        for w in windows:
            if w['anomes'] != anomes: continue
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
            
        # Refaz o efeito gangorra
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
        
        # Filtra apenas quem mudou de tipo
        df_alterados = conn.execute("""
            SELECT 
                CAST(i.NUM_OCORRENCIA_ADMS AS VARCHAR) AS NUM_OCORRENCIA_ADMS,
                CAST(i.NUM_SEQ_INTRP AS VARCHAR) AS NUM_SEQ_INTRP,
                CAST(i.NUM_UC_UCI AS VARCHAR) AS NUM_UC_UCI,
                i.DATA_HORA_INIC_INTRP,
                CAST(a.TIPO_PROTOC_JUSTIF_UCI AS VARCHAR) AS TIPO_PROTOC_ANTERIOR,
                CAST(i.TIPO_PROTOC_JUSTIF_UCI AS VARCHAR) AS TIPO_PROTOC_NOVO,
                CAST(i.COD_CAUSA_INTRP AS VARCHAR) AS COD_CAUSA_INTRP
            FROM main.gold_apuracao_uc_ise i
            JOIN main.gold_apuracao_uc a 
              ON i.NUM_OCORRENCIA_ADMS = a.NUM_OCORRENCIA_ADMS 
             AND i.NUM_SEQ_INTRP = a.NUM_SEQ_INTRP 
             AND i.NUM_UC_UCI = a.NUM_UC_UCI
            WHERE i.TIPO_PROTOC_JUSTIF_UCI != a.TIPO_PROTOC_JUSTIF_UCI
        """).df()
        
        if not df_alterados.empty:
            dfs.append(df_alterados)
        conn.close()
        
    if not dfs:
        raise HTTPException(status_code=400, detail="Nenhuma ocorrência foi reclassificada por estas janelas.")
        
    import pandas as pd
    from midway.export.iqs_csv import exportar_dataframe_iqs
    import tempfile
    from fastapi.responses import FileResponse
    
    df_final = pd.concat(dfs, ignore_index=True)
    
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    tmp_file.close()
    
    exportar_dataframe_iqs(df_final, tmp_file.name)
    
    return FileResponse(
        tmp_file.name, 
        media_type='text/csv', 
        filename=f"ISE_ALTERACOES_IQS.csv"
    )

@router.get("/janelas/{janela_id}/relatorio")
def gerar_relatorio_html(janela_id: str):
    from fastapi.responses import HTMLResponse
    import plotly.graph_objects as go
    
    windows = load_windows()
    janela = next((w for w in windows if w.get('id') == janela_id), None)
    if not janela or 'resultado' not in janela:
        raise HTTPException(status_code=404, detail="Janela não encontrada ou não possui resultado calculado.")
        
    res = janela['resultado']
    nome_evento = janela.get('descritivo') or f"Evento {janela['regional']}"
    
    serie = res.get('serie_temporal', [])
    horas = [s['hora'] for s in serie]
    chi_acum = [s['chi_acumulado'] for s in serie]
    
    fig = go.Figure()
    
    colors = {
        'LESTE': '#3b82f6',
        'OESTE': '#10b981',
        'SUL': '#ef4444',
        'NORTE': '#f59e0b',
        'CENTRO': '#8b5cf6',
        'N/I': '#64748b'
    }
    
    palette = ['#3b82f6', '#10b981', '#ef4444', '#f59e0b', '#8b5cf6', '#06b6d4', '#ec4899', '#84cc16']
    
    all_regions = set()
    for s in serie:
        all_regions.update(s.get('regionais', {}).keys())
        
    for i, reg in enumerate(sorted(list(all_regions))):
        y_vals = [s.get('regionais', {}).get(reg, 0) for s in serie]
        
        # Usa a cor mapeada ou pega uma vibrante da paleta
        color = colors.get(str(reg).upper())
        if not color:
            color = palette[i % len(palette)]
            
        fig.add_trace(go.Bar(
            x=horas,
            y=y_vals,
            name=reg,
            marker_color=color,
            opacity=0.8,
            yaxis='y'
        ))
    
    fig.add_trace(go.Scatter(
        x=horas,
        y=chi_acum,
        name='CHI acumulado (Total)',
        mode='lines+markers',
        line=dict(color='#0f172a', width=3, dash='dot'),
        marker=dict(size=6, color='#0f172a'),
        yaxis='y2'
    ))
    
    fig.update_layout(
        title=f"Curva de Impacto Temporal por Regional: {nome_evento}",
        barmode='stack',
        xaxis=dict(title='Hora', showgrid=True, gridcolor='#e2e8f0'),
        yaxis=dict(title='CHI (UC-h) - Hora', showgrid=True, gridcolor='#e2e8f0', side='left'),
        yaxis2=dict(title='CHI (UC-h) - Acumulado', showgrid=False, overlaying='y', side='right'),
        plot_bgcolor='#ffffff',
        paper_bgcolor='#ffffff',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode='x unified',
        margin=dict(l=40, r=40, t=60, b=40)
    )
    
    plot_html = fig.to_html(full_html=False, include_plotlyjs='cdn')
    
    fig_ci = go.Figure()
    ci_vals = [s.get('ci', 0) for s in serie]
    rec_vals = [s.get('rec_pct', 0) for s in serie]
    
    fig_ci.add_trace(go.Bar(
        x=horas,
        y=ci_vals,
        name='CI (hora)',
        marker_color='#3b82f6',
        opacity=0.8,
        yaxis='y'
    ))
    
    fig_ci.add_trace(go.Scatter(
        x=horas,
        y=rec_vals,
        name='% recomposição',
        mode='lines+markers',
        line=dict(color='#f59e0b', width=3),
        marker=dict(size=6, color='#f59e0b'),
        yaxis='y2'
    ))
    
    fig_ci.update_layout(
        title=f"Curva de Recomposição de CI",
        barmode='group',
        xaxis=dict(title='Hora', showgrid=True, gridcolor='#e2e8f0'),
        yaxis=dict(title='CI (UC)', showgrid=True, gridcolor='#e2e8f0', side='left'),
        yaxis2=dict(title='% recomposição / pico', tickformat='.0%', showgrid=False, overlaying='y', side='right', range=[0, 1.1]),
        plot_bgcolor='#ffffff',
        paper_bgcolor='#ffffff',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode='x unified',
        margin=dict(l=40, r=40, t=60, b=40)
    )
    plot_ci_html = fig_ci.to_html(full_html=False, include_plotlyjs=False)
    
    tabela = res.get('tabela_conjuntos', [])
    tabela_html = """
    <table class="data-table">
        <thead>
            <tr>
                <th>Conjunto</th>
                <th>Protocolo</th>
                <th style="text-align: right">CI Antes</th>
                <th style="text-align: right">CI Depois (ISE)</th>
                <th style="text-align: right">CHI Antes</th>
                <th style="text-align: right">CHI Depois (ISE)</th>
            </tr>
        </thead>
        <tbody>
    """
    qtd_linhas = 0
    for r in tabela:
        if r.get('ci_antes') == r.get('ci_depois') and r.get('chi_antes') == r.get('chi_depois'):
            continue # Oculta os inalterados (Filtro aprovado no plano)
            
        ci_cor = "#10b981" if r.get('ci_depois',0) < r.get('ci_antes',0) else ("#ef4444" if r.get('ci_depois',0) > r.get('ci_antes',0) else "#eab308")
        chi_cor = "#10b981" if r.get('chi_depois',0) < r.get('chi_antes',0) else ("#ef4444" if r.get('chi_depois',0) > r.get('chi_antes',0) else "#eab308")
        
        tabela_html += f"""
            <tr>
                <td><strong>{r.get('conjunto', '')}</strong></td>
                <td>{r.get('protocolo', '')}</td>
                <td style="text-align: right">{r.get('ci_antes',0):,}</td>
                <td style="text-align: right; color: {ci_cor}; font-weight: bold;">{r.get('ci_depois',0):,}</td>
                <td style="text-align: right">{r.get('chi_antes',0):,.2f}</td>
                <td style="text-align: right; color: {chi_cor}; font-weight: bold;">{r.get('chi_depois',0):,.2f}</td>
            </tr>
        """
        qtd_linhas += 1
        
    if qtd_linhas == 0:
        tabela_html += '<tr><td colspan="6" style="text-align: center; color: #94a3b8; padding: 20px;">Nenhuma alteração nos conjuntos nesta janela.</td></tr>'
        
    tabela_html += "</tbody></table>"
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <title>Resumo Executivo ISE</title>
        <style>
            body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #f8fafc; color: #334155; margin: 0; padding: 20px; }}
            .container {{ max-width: 1200px; margin: 0 auto; background: #fff; padding: 30px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }}
            .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #f1f5f9; padding-bottom: 20px; margin-bottom: 30px; }}
            .header h1 {{ margin: 0; color: #0f172a; font-size: 24px; }}
            .header p {{ margin: 5px 0 0 0; color: #64748b; }}
            .kpis {{ display: flex; gap: 20px; margin-bottom: 40px; }}
            .kpi-card {{ flex: 1; background: #fff; border: 1px solid #e2e8f0; padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
            .kpi-title {{ font-size: 12px; font-weight: bold; color: #64748b; text-transform: uppercase; margin-bottom: 10px; }}
            .kpi-value {{ font-size: 28px; font-weight: bold; color: #0f172a; }}
            .kpi-sub {{ font-size: 14px; color: #94a3b8; margin-top: 5px; }}
            .kpi-card.highlight-green {{ border-left: 4px solid #10b981; }}
            .kpi-card.highlight-red {{ border-left: 4px solid #ef4444; }}
            .data-table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px; }}
            .data-table th, .data-table td {{ padding: 12px; border-bottom: 1px solid #e2e8f0; text-align: left; }}
            .data-table th {{ background: #f8fafc; color: #475569; font-weight: 600; text-transform: uppercase; font-size: 12px; }}
            .section-title {{ margin: 40px 0 15px 0; color: #0f172a; font-size: 18px; border-bottom: 2px solid #f1f5f9; padding-bottom: 10px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div>
                    <h1>Resumo Executivo ISE</h1>
                    <p>{janela['data_inicio'].replace('T', ' ')} &mdash; {janela['data_fim'].replace('T', ' ')}</p>
                </div>
                <div>
                    <span style="background: #e0f2fe; color: #0284c7; padding: 6px 12px; border-radius: 20px; font-weight: bold; font-size: 14px;">{nome_evento}</span>
                </div>
            </div>
            
            <div class="kpis">
                <div class="kpi-card">
                    <div class="kpi-title">CI TOTAL (Evento)</div>
                    <div class="kpi-value">{res.get('ci_total', 0):,}</div>
                    <div class="kpi-sub">UCs interrompidas</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-title">CHI TOTAL (Evento)</div>
                    <div class="kpi-value">{res.get('chi_total', 0):,.1f}</div>
                    <div class="kpi-sub">Horas de interrupção</div>
                </div>
                <div class="kpi-card highlight-green">
                    <div class="kpi-title">Isentado (TIPO 6)</div>
                    <div class="kpi-value">{res.get('chi_tipo6', 0):,.1f} h</div>
                    <div class="kpi-sub">{res.get('ci_tipo6', 0):,} UCs blindadas</div>
                </div>
                <div class="kpi-card highlight-red">
                    <div class="kpi-title">GANGORRA (TIPO 0)</div>
                    <div class="kpi-value">{res.get('chi_tipo0', 0):,.1f} h</div>
                    <div class="kpi-sub">{res.get('conjuntos_rebaixados', 0)} Conjuntos afetados</div>
                </div>
            </div>
            
            <div class="section-title">Análise Temporal</div>
            <div style="border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; margin-bottom: 20px;">
                {plot_html}
            </div>
            
            <div style="border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; margin-bottom: 40px;">
                {plot_ci_html}
            </div>
            
            <div class="section-title">Matriz de Impacto por Conjunto (Apenas Alterados)</div>
            <div style="background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; margin-bottom: 40px;">
                {tabela_html}
            </div>
        </div>
    </body>
    </html>
    """
    
    filename = f"Relatorio_Executivo_ISE_{janela_id}.html"
    return HTMLResponse(
        content=html_content,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
