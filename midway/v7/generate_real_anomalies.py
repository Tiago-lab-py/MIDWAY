from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import duckdb
from dotenv import load_dotenv
from sqlalchemy import text

from midway.db.postgres import create_postgres_engine, get_config

CREATED_BY = "gerador_v7_raw_silver_gold"
PAGE_LIMIT_PER_RULE = 80


def stable_uuid(value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"midway-v7-real:{value}"))


def generate_real_anomalies(anomes: str | None = None) -> dict[str, int]:
    load_dotenv()
    anomes = anomes or os.getenv("ANOMES", "202606")
    processed_path = Path(os.getenv("MIDWAY_PROCESSED_DUCKDB_PATH", f"data/processed/iqs_adms_processed_{anomes}.duckdb"))
    if not processed_path.exists():
        raise FileNotFoundError(f"DuckDB processado não encontrado: {processed_path}")

    schema = _schema()
    engine = create_postgres_engine()
    anomalies = _collect_duckdb_anomalies(processed_path)

    with engine.begin() as pg:
        _clear_generated_anomalies(pg, schema)
        for anomaly in anomalies:
            _upsert_anomaly(pg, schema, anomaly, anomes)

    return {
        "anomalias": len(anomalies),
        "evidencias": sum(len(item["evidencias"]) for item in anomalies),
        "sugestoes": len(anomalies),
    }


def _collect_duckdb_anomalies(processed_path: Path) -> list[dict[str, object]]:
    with duckdb.connect(str(processed_path), read_only=True) as con:
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        anomalies: list[dict[str, object]] = []
        if "auditoria_outliers_bruto" in tables:
            anomalies.extend(_outlier_anomalies(con))
        if "export_sobreposicao_total_uc" in tables:
            anomalies.extend(_overlap_total_anomalies(con))
        if "adms_iqs_alterados" in tables:
            anomalies.extend(_overlap_partial_anomalies(con))
        if "Auditoria_ESTADO_7" in tables:
            anomalies.extend(_estado_7_anomalies(con))
        if "gold_analise_tecnica_impacto_base" in tables:
            anomalies.extend(_technical_impact_anomalies(con))
    return anomalies


def _outlier_anomalies(con: duckdb.DuckDBPyConnection) -> list[dict[str, object]]:
    rows = con.execute(
        """
        SELECT
            NUM_OCORRENCIA_ADMS,
            NUM_SEQ_INTRP,
            DATA_HORA_INIC_INTRP,
            DATA_HORA_FIM_INTRP,
            COD_CAUSA_INTRP,
            COD_COMP_INTRP,
            COD_TIPO_INTRP,
            TIPO_PROTOC_JUSTIF_UCI,
            NUM_PROTOC_JUSTIF_RESP_UCI,
            QTD_UCS,
            DURACAO_HORAS,
            QTD_INTRP_CONTIDAS,
            QTD_UCS_AFETADAS
        FROM auditoria_outliers_bruto
        ORDER BY
            COALESCE(DURACAO_HORAS, 0) DESC,
            COALESCE(QTD_UCS, 0) DESC,
            COALESCE(QTD_UCS_AFETADAS, 0) DESC
        LIMIT ?
        """,
        [PAGE_LIMIT_PER_RULE],
    ).fetchdf().to_dict(orient="records")
    anomalies = []
    for row in rows:
        anomalies.append(
            _anomaly(
                key=f"OUTLIER_BRUTO:{row['NUM_SEQ_INTRP']}",
                code="OUTLIER_BRUTO",
                name="Outlier bruto de duração, UCs ou contenção",
                category="integridade",
                severity="alta" if float(row.get("DURACAO_HORAS") or 0) >= 24 else "média",
                confidence=0.86,
                status="PENDENTE",
                origin="RAW/SILVER",
                occurrence=row.get("NUM_OCORRENCIA_ADMS"),
                interruption=row.get("NUM_SEQ_INTRP"),
                regional=None,
                uc=None,
                equipment=None,
                description="Registro real sinalizado pela auditoria preventiva do RAW.",
                simple=(
                    "O registro veio do RAW e foi sinalizado por duração, quantidade de UCs, "
                    "interrupções contidas ou UCs afetadas fora do padrão esperado."
                ),
                technical=(
                    "Fonte: tabela auditoria_outliers_bruto gerada no tratamento. A regra usa "
                    "métricas calculadas a partir do RAW ADMS antes da exportação IQS."
                ),
                rule="auditoria_outliers_bruto",
                impact_text="Pode distorcer CHI, DIC/FIC, DEC/FEC e priorização de correção.",
                fields=["DURACAO_HORAS", "QTD_UCS", "QTD_INTRP_CONTIDAS", "QTD_UCS_AFETADAS"],
                original={
                    "data_hora_inicio": row.get("DATA_HORA_INIC_INTRP"),
                    "data_hora_fim": row.get("DATA_HORA_FIM_INTRP"),
                    "cod_causa": row.get("COD_CAUSA_INTRP"),
                    "cod_componente": row.get("COD_COMP_INTRP"),
                    "cod_tipo": row.get("COD_TIPO_INTRP"),
                    "tipo_protocolo_uci": row.get("TIPO_PROTOC_JUSTIF_UCI"),
                    "protocolo_uci": row.get("NUM_PROTOC_JUSTIF_RESP_UCI"),
                },
                suggested={
                    "acao": "manter_em_auditoria_antes_exportacao_iqs",
                    "status": "revisão técnica",
                    "origem_correcao": "auditoria_outliers_bruto",
                },
                impact={
                    "dic": float(row.get("DURACAO_HORAS") or 0) * 60,
                    "fic": 0,
                    "dec": 0,
                    "fec": 0,
                    "ressarcimento": 0,
                },
                evidence=[
                    ("DURACAO_HORAS", row.get("DURACAO_HORAS"), "auditoria_outliers_bruto"),
                    ("QTD_UCS", row.get("QTD_UCS"), "auditoria_outliers_bruto"),
                    ("QTD_INTRP_CONTIDAS", row.get("QTD_INTRP_CONTIDAS"), "auditoria_outliers_bruto"),
                    ("QTD_UCS_AFETADAS", row.get("QTD_UCS_AFETADAS"), "auditoria_outliers_bruto"),
                ],
                suggestion_action="revisar_outlier_raw",
                suggestion_original="registro RAW/SILVER sinalizado",
                suggestion_value="bloquear correção automática e revisar antes de envio IQS",
                suggestion_reason="Auditoria preventiva identificou comportamento fora do padrão no dado bruto.",
            )
        )
    return anomalies


def _overlap_total_anomalies(con: duckdb.DuckDBPyConnection) -> list[dict[str, object]]:
    rows = con.execute(
        """
        SELECT
            NUM_OCORRENCIA_ADMS,
            NUM_SEQ_INTRP,
            SIGLA_REGIONAL,
            COD_CONJTO_ELET_ANEEL_INTRP,
            NUM_OPER_CHV_INTRP,
            MIN(DATA_HORA_INIC_INTRP) AS DATA_HORA_INIC_INTRP,
            MAX(DATA_HORA_FIM_INTRP) AS DATA_HORA_FIM_INTRP,
            COUNT(*) AS QTD_UCS,
            COUNT(DISTINCT NUM_UC_UCI) AS QTD_UCS_DISTINTAS,
            MIN(NUM_MOTIVO_TRAT_DIF_UCI) AS MOTIVO_EXPORT,
            MIN(INDIC_SIT_PROCES_INDIC_UCI) AS SIT_PROCESSAMENTO
        FROM export_sobreposicao_total_uc
        GROUP BY 1,2,3,4,5
        ORDER BY QTD_UCS DESC
        LIMIT ?
        """,
        [PAGE_LIMIT_PER_RULE],
    ).fetchdf().to_dict(orient="records")
    anomalies = []
    for row in rows:
        anomalies.append(
            _anomaly(
                key=f"SOBREPOSICAO_TOTAL_UC:{row['NUM_SEQ_INTRP']}",
                code="SOBREPOSICAO_TOTAL_UC",
                name="Sobreposição total por UC tratada para IQS",
                category="sobreposição",
                severity="alta",
                confidence=0.94,
                status="PENDENTE",
                origin="GOLD/EXPORT",
                occurrence=row.get("NUM_OCORRENCIA_ADMS"),
                interruption=row.get("NUM_SEQ_INTRP"),
                regional=row.get("SIGLA_REGIONAL"),
                uc=None,
                equipment=row.get("NUM_OPER_CHV_INTRP"),
                description="Interrupção real presente no arquivo de exportação de sobreposição total por UC.",
                simple=(
                    "A interrupção possui UCs totalmente sobrepostas e já aparece no conjunto de "
                    "correções preparado para envio ao IQS."
                ),
                technical="Fonte: export_sobreposicao_total_uc, derivada do tratamento RAW→SILVER→GOLD.",
                rule="export_sobreposicao_total_uc",
                impact_text="Evita dupla contagem regulatória de DIC/FIC para UCs contidas.",
                fields=["NUM_UC_UCI", "NUM_SEQ_INTRP", "DTHR_INICIO_INTRP_UC", "NUM_MOTIVO_TRAT_DIF_UCI"],
                original={
                    "qtd_ucs_exportadas": row.get("QTD_UCS"),
                    "qtd_ucs_distintas": row.get("QTD_UCS_DISTINTAS"),
                    "motivo_export": row.get("MOTIVO_EXPORT"),
                    "situacao_processamento": row.get("SIT_PROCESSAMENTO"),
                },
                suggested={
                    "acao": "usar_export_sobreposicao_total_uc",
                    "arquivo_iqs": "export_sobreposicao_total_uc",
                    "motivo_tratamento": row.get("MOTIVO_EXPORT"),
                },
                impact={"dic": 0, "fic": row.get("QTD_UCS_DISTINTAS") or 0, "dec": 0, "fec": 0, "ressarcimento": 0},
                evidence=[
                    ("QTD_UCS_EXPORTADAS", row.get("QTD_UCS"), "export_sobreposicao_total_uc"),
                    ("QTD_UCS_DISTINTAS", row.get("QTD_UCS_DISTINTAS"), "export_sobreposicao_total_uc"),
                    ("MOTIVO_EXPORT", row.get("MOTIVO_EXPORT"), "export_sobreposicao_total_uc"),
                ],
                suggestion_action="exportar_correcao_sobreposicao_total",
                suggestion_original="UCs com sobreposição total no GOLD",
                suggestion_value="aplicar registros de export_sobreposicao_total_uc no envio IQS",
                suggestion_reason="A tabela de exportação já contém a correção calculada pelo tratamento.",
            )
        )
    return anomalies


def _overlap_partial_anomalies(con: duckdb.DuckDBPyConnection) -> list[dict[str, object]]:
    rows = con.execute(
        """
        SELECT
            NUM_OCORRENCIA_ADMS,
            NUM_SEQ_INTRP,
            REGIONAL,
            NUM_OPER_CHV_INTRP,
            MIN(DATA_HORA_INIC_INTRP) AS DATA_HORA_INIC_INTRP,
            MAX(DATA_HORA_FIM_INTRP) AS DATA_HORA_FIM_INTRP,
            COUNT(*) AS QTD_UCS_AJUSTADAS,
            MIN(DURACAO_MINUTOS_ORIG) AS MENOR_DURACAO_ORIG,
            MAX(DURACAO_MINUTOS_ORIG) AS MAIOR_DURACAO_ORIG,
            MIN(DURACAO_MINUTOS_AJUSTADA) AS MENOR_DURACAO_AJUSTADA,
            MAX(DURACAO_MINUTOS_AJUSTADA) AS MAIOR_DURACAO_AJUSTADA,
            MIN(ACAO_AJUSTE_PARCIAL) AS ACAO_AJUSTE_PARCIAL
        FROM adms_iqs_alterados
        WHERE ACAO_AJUSTE_PARCIAL IS NOT NULL
          AND TRIM(CAST(ACAO_AJUSTE_PARCIAL AS VARCHAR)) <> ''
        GROUP BY 1,2,3,4
        ORDER BY QTD_UCS_AJUSTADAS DESC
        LIMIT ?
        """,
        [PAGE_LIMIT_PER_RULE],
    ).fetchdf().to_dict(orient="records")
    anomalies = []
    for row in rows:
        anomalies.append(
            _anomaly(
                key=f"SOBREPOSICAO_PARCIAL_UC:{row['NUM_SEQ_INTRP']}",
                code="SOBREPOSICAO_PARCIAL_UC",
                name="Sobreposição parcial por UC ajustada",
                category="sobreposição",
                severity="média",
                confidence=0.9,
                status="PENDENTE",
                origin="SILVER/GOLD",
                occurrence=row.get("NUM_OCORRENCIA_ADMS"),
                interruption=row.get("NUM_SEQ_INTRP"),
                regional=row.get("REGIONAL"),
                uc=None,
                equipment=row.get("NUM_OPER_CHV_INTRP"),
                description="Interrupção com ajuste parcial de início/duração por UC no tratamento.",
                simple="O tratamento reduziu ou deslocou janelas de UC para eliminar sobreposição parcial.",
                technical="Fonte: adms_iqs_alterados.ACAO_AJUSTE_PARCIAL, produzido a partir da camada tratada.",
                rule="ACAO_AJUSTE_PARCIAL IS NOT NULL",
                impact_text="Altera DIC por UC e evita dupla contagem parcial.",
                fields=["DURACAO_MINUTOS_ORIG", "DURACAO_MINUTOS_AJUSTADA", "DTHR_INICIO_INTRP_UC_AJUSTADO"],
                original={
                    "menor_duracao_original_min": row.get("MENOR_DURACAO_ORIG"),
                    "maior_duracao_original_min": row.get("MAIOR_DURACAO_ORIG"),
                },
                suggested={
                    "acao_ajuste": row.get("ACAO_AJUSTE_PARCIAL"),
                    "menor_duracao_ajustada_min": row.get("MENOR_DURACAO_AJUSTADA"),
                    "maior_duracao_ajustada_min": row.get("MAIOR_DURACAO_AJUSTADA"),
                },
                impact={"dic": row.get("MAIOR_DURACAO_ORIG") or 0, "fic": row.get("QTD_UCS_AJUSTADAS") or 0, "dec": 0, "fec": 0, "ressarcimento": 0},
                evidence=[
                    ("QTD_UCS_AJUSTADAS", row.get("QTD_UCS_AJUSTADAS"), "adms_iqs_alterados"),
                    ("ACAO_AJUSTE_PARCIAL", row.get("ACAO_AJUSTE_PARCIAL"), "adms_iqs_alterados"),
                    ("MAIOR_DURACAO_ORIG", row.get("MAIOR_DURACAO_ORIG"), "adms_iqs_alterados"),
                    ("MAIOR_DURACAO_AJUSTADA", row.get("MAIOR_DURACAO_AJUSTADA"), "adms_iqs_alterados"),
                ],
                suggestion_action="exportar_correcao_sobreposicao_parcial",
                suggestion_original="duração original por UC",
                suggestion_value="duração ajustada em adms_iqs_alterados",
                suggestion_reason="Ajuste calculado para remover interseção parcial entre eventos.",
            )
        )
    return anomalies


def _estado_7_anomalies(con: duckdb.DuckDBPyConnection) -> list[dict[str, object]]:
    rows = con.execute(
        """
        SELECT *
        FROM Auditoria_ESTADO_7
        ORDER BY QTD_UCS_FILHAS_REFERENCIANDO DESC, QTD_INTERRUPCOES_FILHAS_REFERENCIANDO DESC
        LIMIT ?
        """,
        [PAGE_LIMIT_PER_RULE],
    ).fetchdf().to_dict(orient="records")
    anomalies = []
    for row in rows:
        anomalies.append(
            _anomaly(
                key=f"ESTADO_7_MANOBRA:{row['NUM_SEQ_INTRP']}",
                code="ESTADO_7_MANOBRA",
                name="Interrupção ESTADO 7 referenciada por manobra",
                category="operacional",
                severity="alta",
                confidence=0.92,
                status="PENDENTE",
                origin="GOLD/AUDITORIA",
                occurrence=row.get("NUM_OCORRENCIA_ADMS"),
                interruption=row.get("NUM_SEQ_INTRP"),
                regional=row.get("REGIONAL_EXPORT"),
                uc=None,
                equipment=row.get("NUM_OPER_CHV_INTRP"),
                description="Interrupção real ESTADO 7 avaliada para exportação ou bloqueio.",
                simple="A interrupção ESTADO 7 está relacionada a manobras e precisa preservar rastreabilidade antes de envio ao IQS.",
                technical="Fonte: Auditoria_ESTADO_7 gerada no tratamento oficial.",
                rule="Auditoria_ESTADO_7.RESULTADO_AUDITORIA",
                impact_text="Evita exportar indevidamente interrupção filha ou sem lastro de UC.",
                fields=["QTD_UCS_91_D", "QTD_INTERRUPCOES_FILHAS_REFERENCIANDO", "RESULTADO_AUDITORIA"],
                original={
                    "qtd_ucs_total": row.get("QTD_UCS_TOTAL"),
                    "qtd_ucs_91_d": row.get("QTD_UCS_91_D"),
                    "filhas_referenciando": row.get("NUM_SEQ_INTRP_FILHAS_REFERENCIANDO"),
                },
                suggested={"resultado_auditoria": row.get("RESULTADO_AUDITORIA")},
                impact={"dic": 0, "fic": row.get("QTD_UCS_TOTAL") or 0, "dec": 0, "fec": 0, "ressarcimento": 0},
                evidence=[
                    ("RESULTADO_AUDITORIA", row.get("RESULTADO_AUDITORIA"), "Auditoria_ESTADO_7"),
                    ("QTD_UCS_FILHAS_REFERENCIANDO", row.get("QTD_UCS_FILHAS_REFERENCIANDO"), "Auditoria_ESTADO_7"),
                    ("NUM_SEQ_INTRP_FILHAS_REFERENCIANDO", row.get("NUM_SEQ_INTRP_FILHAS_REFERENCIANDO"), "Auditoria_ESTADO_7"),
                ],
                suggestion_action="seguir_resultado_auditoria_estado_7",
                suggestion_original="registro ESTADO 7 auditado",
                suggestion_value=str(row.get("RESULTADO_AUDITORIA") or ""),
                suggestion_reason="Auditoria operacional calculou a regra de exportação/bloqueio para ESTADO 7.",
            )
        )
    return anomalies


def _technical_impact_anomalies(con: duckdb.DuckDBPyConnection) -> list[dict[str, object]]:
    rows = con.execute(
        """
        SELECT *
        FROM gold_analise_tecnica_impacto_base
        WHERE COALESCE(QTD_VIOLACAO_COMP_CAUSA, 0) > 0
           OR COALESCE(TEM_9282, 0) = 1
           OR COALESCE(RESSARCIMENTO_ESTIMADO, 0) > 0
        ORDER BY
            COALESCE(RESSARCIMENTO_ESTIMADO, 0) DESC,
            COALESCE(CHI_LIQUIDO, 0) DESC,
            COALESCE(QTD_RECLAMACOES, 0) DESC
        LIMIT ?
        """,
        [PAGE_LIMIT_PER_RULE],
    ).fetchdf().to_dict(orient="records")
    anomalies = []
    for row in rows:
        code = "VIOLACAO_COMP_CAUSA" if int(row.get("QTD_VIOLACAO_COMP_CAUSA") or 0) > 0 else "ANALISE_TECNICA_9282"
        anomalies.append(
            _anomaly(
                key=f"{code}:{row['NUM_OCORRENCIA_ADMS']}",
                code=code,
                name="Análise técnica de impacto para correção IQS",
                category="regulatória",
                severity="alta" if float(row.get("RESSARCIMENTO_ESTIMADO") or 0) > 1000 else "média",
                confidence=0.84,
                status="PENDENTE",
                origin="GOLD",
                occurrence=row.get("NUM_OCORRENCIA_ADMS"),
                interruption=None,
                regional=None,
                uc=None,
                equipment=None,
                description="Ocorrência real priorizada por impacto técnico, reclamação, ressarcimento ou causa/componente.",
                simple="A ocorrência tem impacto técnico relevante e pode exigir correção antes do envio final ao IQS.",
                technical="Fonte: gold_analise_tecnica_impacto_base materializada a partir de GOLD, reclamações e ressarcimento.",
                rule="gold_analise_tecnica_impacto_base",
                impact_text="Pode alterar DEC/FEC, ressarcimento estimado e classificação causa/componente.",
                fields=["CHI_LIQUIDO", "CI_LIQUIDO", "RESSARCIMENTO_ESTIMADO", "PARES_COMPONENTE_CAUSA"],
                original={
                    "pares_componente_causa": row.get("PARES_COMPONENTE_CAUSA"),
                    "cod_comp_principal": row.get("COD_COMP_PRINCIPAL"),
                    "cod_causa_principal": row.get("COD_CAUSA_PRINCIPAL"),
                    "violacoes": row.get("VIOLACOES_COMPONENTE_CAUSA"),
                },
                suggested={
                    "acao": "priorizar_revisao_tecnica",
                    "grupos_componente_iqs": row.get("GRUPOS_COMPONENTE_IQS"),
                    "grupos_causa_iqs": row.get("GRUPOS_CAUSA_IQS"),
                },
                impact={
                    "dic": row.get("CHI_LIQUIDO") or 0,
                    "fic": row.get("CI_LIQUIDO") or 0,
                    "dec": 0,
                    "fec": 0,
                    "ressarcimento": row.get("RESSARCIMENTO_ESTIMADO") or 0,
                },
                evidence=[
                    ("RESSARCIMENTO_ESTIMADO", row.get("RESSARCIMENTO_ESTIMADO"), "gold_analise_tecnica_impacto_base"),
                    ("QTD_RECLAMACOES", row.get("QTD_RECLAMACOES"), "gold_analise_tecnica_impacto_base"),
                    ("MAX_SCORE_RECLAMACAO", row.get("MAX_SCORE_RECLAMACAO"), "gold_analise_tecnica_impacto_base"),
                    ("VIOLACOES_COMPONENTE_CAUSA", row.get("VIOLACOES_COMPONENTE_CAUSA"), "gold_analise_tecnica_impacto_base"),
                ],
                suggestion_action="priorizar_revisao_para_envio_iqs",
                suggestion_original="classificação e impacto apurados no GOLD",
                suggestion_value="revisão técnica antes de aprovar correção/exportação IQS",
                suggestion_reason="A ocorrência concentra impacto regulatório, financeiro ou indício técnico relevante.",
            )
        )
    return anomalies


def _anomaly(
    *,
    key: str,
    code: str,
    name: str,
    category: str,
    severity: str,
    confidence: float,
    status: str,
    origin: str,
    occurrence: object,
    interruption: object,
    regional: object,
    uc: object,
    equipment: object,
    description: str,
    simple: str,
    technical: str,
    rule: str,
    impact_text: str,
    fields: list[str],
    original: dict[str, object],
    suggested: dict[str, object],
    impact: dict[str, object],
    evidence: list[tuple[str, object, str]],
    suggestion_action: str,
    suggestion_original: str,
    suggestion_value: str,
    suggestion_reason: str,
) -> dict[str, object]:
    anomaly_id = stable_uuid(key)
    suggestion_id = stable_uuid(f"{key}:sugestao")
    return {
        "id_anomalia": anomaly_id,
        "id_sugestao": suggestion_id,
        "registro_id": str(interruption or occurrence or key),
        "anomalia_codigo": code,
        "nome": name,
        "categoria": category,
        "severidade": severity,
        "confianca": confidence,
        "status_anomalia": status,
        "origem": origin,
        "regional": _str_or_none(regional),
        "conjunto": None,
        "equipamento": _str_or_none(equipment),
        "uc": _str_or_none(uc),
        "ocorrencia": _str_or_none(occurrence),
        "interrupcao": _str_or_none(interruption),
        "descricao": description,
        "explicacao_simples": simple,
        "explicacao_tecnica": technical,
        "regra_violada": rule,
        "impacto_possivel": impact_text,
        "campos_envolvidos": fields,
        "dados_originais": original,
        "dados_sugeridos": suggested,
        "impacto": impact,
        "linha_tempo": [],
        "evidencias": [
            {
                "id_evidencia": stable_uuid(f"{key}:evidencia:{index}:{field}"),
                "campo": field,
                "valor": _str_or_none(value),
                "origem": source,
                "detalhe": {},
            }
            for index, (field, value, source) in enumerate(evidence, start=1)
        ],
        "sugestao": {
            "acao": suggestion_action,
            "valor_original": suggestion_original,
            "valor_sugerido": suggestion_value,
            "justificativa": suggestion_reason,
            "nivel_confianca": "alta" if confidence >= 0.9 else "média",
            "risco_regulatorio": "médio",
            "risco_operacional": "médio",
            "risco_juridico": "médio",
            "requer_aprovacao": True,
        },
    }


def _clear_generated_anomalies(pg, schema: str) -> None:
    pg.execute(
        text(
            f"""
            DELETE FROM {schema}.midway_anomalia a
            WHERE a.criado_por IN ('seed_v7_sintetico', :created_by)
              AND NOT EXISTS (
                  SELECT 1
                  FROM {schema}.midway_decisao d
                  WHERE d.id_anomalia = a.id_anomalia
              )
            """
        ),
        {"created_by": CREATED_BY},
    )


def _upsert_anomaly(pg, schema: str, anomaly: dict[str, object], anomes: str) -> None:
    pg.execute(
        text(
            f"""
            INSERT INTO {schema}.midway_anomalia (
                id_anomalia, anomes, registro_id, anomalia_codigo, nome, categoria,
                severidade, confianca, status_anomalia, origem, regional, conjunto,
                equipamento, uc, ocorrencia, interrupcao, descricao, explicacao_simples,
                explicacao_tecnica, regra_violada, impacto_possivel, campos_envolvidos,
                dados_originais, dados_sugeridos, impacto, linha_tempo, criado_por, atualizado_por
            )
            VALUES (
                :id_anomalia, :anomes, :registro_id, :anomalia_codigo, :nome, :categoria,
                :severidade, :confianca, :status_anomalia, :origem, :regional, :conjunto,
                :equipamento, :uc, :ocorrencia, :interrupcao, :descricao, :explicacao_simples,
                :explicacao_tecnica, :regra_violada, :impacto_possivel, CAST(:campos_envolvidos AS jsonb),
                CAST(:dados_originais AS jsonb), CAST(:dados_sugeridos AS jsonb),
                CAST(:impacto AS jsonb), CAST(:linha_tempo AS jsonb), :criado_por, :atualizado_por
            )
            ON CONFLICT (id_anomalia) DO UPDATE
            SET
                status_anomalia = EXCLUDED.status_anomalia,
                confianca = EXCLUDED.confianca,
                descricao = EXCLUDED.descricao,
                explicacao_simples = EXCLUDED.explicacao_simples,
                explicacao_tecnica = EXCLUDED.explicacao_tecnica,
                dados_originais = EXCLUDED.dados_originais,
                dados_sugeridos = EXCLUDED.dados_sugeridos,
                impacto = EXCLUDED.impacto,
                atualizado_por = EXCLUDED.atualizado_por,
                atualizado_em = now()
            """
        ),
        {
            **{k: anomaly[k] for k in [
                "id_anomalia", "registro_id", "anomalia_codigo", "nome", "categoria",
                "severidade", "confianca", "status_anomalia", "origem", "regional",
                "conjunto", "equipamento", "uc", "ocorrencia", "interrupcao", "descricao",
                "explicacao_simples", "explicacao_tecnica", "regra_violada", "impacto_possivel",
            ]},
            "anomes": anomes,
            "campos_envolvidos": _json(anomaly["campos_envolvidos"]),
            "dados_originais": _json(anomaly["dados_originais"]),
            "dados_sugeridos": _json(anomaly["dados_sugeridos"]),
            "impacto": _json(anomaly["impacto"]),
            "linha_tempo": _json(anomaly["linha_tempo"]),
            "criado_por": CREATED_BY,
            "atualizado_por": CREATED_BY,
        },
    )
    for evidence in anomaly["evidencias"]:
        pg.execute(
            text(
                f"""
                INSERT INTO {schema}.midway_evidencia (
                    id_evidencia, id_anomalia, campo, valor, origem, detalhe
                )
                VALUES (
                    :id_evidencia, :id_anomalia, :campo, :valor, :origem, CAST(:detalhe AS jsonb)
                )
                ON CONFLICT (id_evidencia) DO UPDATE
                SET campo = EXCLUDED.campo,
                    valor = EXCLUDED.valor,
                    origem = EXCLUDED.origem,
                    detalhe = EXCLUDED.detalhe
                """
            ),
            {
                "id_evidencia": evidence["id_evidencia"],
                "id_anomalia": anomaly["id_anomalia"],
                "campo": evidence["campo"],
                "valor": evidence["valor"],
                "origem": evidence["origem"],
                "detalhe": _json(evidence["detalhe"]),
            },
        )
    suggestion = anomaly["sugestao"]
    pg.execute(
        text(
            f"""
            INSERT INTO {schema}.midway_sugestao (
                id_sugestao, id_anomalia, acao, valor_original, valor_sugerido,
                justificativa, nivel_confianca, risco_regulatorio, risco_operacional,
                risco_juridico, requer_aprovacao, criado_por
            )
            VALUES (
                :id_sugestao, :id_anomalia, :acao, :valor_original, :valor_sugerido,
                :justificativa, :nivel_confianca, :risco_regulatorio, :risco_operacional,
                :risco_juridico, :requer_aprovacao, :criado_por
            )
            ON CONFLICT (id_sugestao) DO UPDATE
            SET acao = EXCLUDED.acao,
                valor_original = EXCLUDED.valor_original,
                valor_sugerido = EXCLUDED.valor_sugerido,
                justificativa = EXCLUDED.justificativa,
                nivel_confianca = EXCLUDED.nivel_confianca,
                risco_regulatorio = EXCLUDED.risco_regulatorio,
                risco_operacional = EXCLUDED.risco_operacional,
                risco_juridico = EXCLUDED.risco_juridico,
                requer_aprovacao = EXCLUDED.requer_aprovacao
            """
        ),
        {
            "id_sugestao": anomaly["id_sugestao"],
            "id_anomalia": anomaly["id_anomalia"],
            "acao": suggestion["acao"],
            "valor_original": suggestion["valor_original"],
            "valor_sugerido": suggestion["valor_sugerido"],
            "justificativa": suggestion["justificativa"],
            "nivel_confianca": suggestion["nivel_confianca"],
            "risco_regulatorio": suggestion["risco_regulatorio"],
            "risco_operacional": suggestion["risco_operacional"],
            "risco_juridico": suggestion["risco_juridico"],
            "requer_aprovacao": suggestion["requer_aprovacao"],
            "criado_por": CREATED_BY,
        },
    )


def _schema() -> str:
    schema = get_config().schema
    if not schema.replace("_", "").isalnum():
        raise RuntimeError("Schema PostgreSQL inválido.")
    return schema


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _str_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text and text.lower() != "nan" else None


def main() -> None:
    result = generate_real_anomalies()
    print(
        "Carga de anomalias reais concluída: "
        f"{result['anomalias']} anomalia(s), "
        f"{result['evidencias']} evidência(s), "
        f"{result['sugestoes']} sugestão(ões)."
    )


if __name__ == "__main__":
    main()
