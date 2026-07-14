from __future__ import annotations

from typing import Any

from sqlalchemy import text

from midway.db.postgres import create_postgres_engine, get_config

V7_TABLES = {
    "midway_v7_anomalia",
    "midway_v7_evidencia",
    "midway_v7_sugestao",
    "midway_v7_decisao",
}


def list_anomalies() -> dict[str, object]:
    rows = _list_postgres_anomalies()
    return {
        "resumo": _summary_from_rows(rows, "RAW/SILVER/GOLD"),
        "items": rows,
        "fonte": "postgres",
    }


def anomaly_detail(id_anomalia: str) -> dict[str, object] | None:
    detail = _postgres_anomaly_detail(id_anomalia)
    if detail:
        return {
            **detail,
            "fonte": "postgres",
        }
    return None


def _schema() -> str:
    schema = get_config().schema
    if not schema.replace("_", "").isalnum():
        raise RuntimeError("Schema PostgreSQL inválido.")
    return schema


def _ensure_tables(schema: str) -> bool:
    engine = create_postgres_engine()
    with engine.connect() as con:
        rows = con.execute(
            text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = :schema
                  AND table_name = ANY(:tables)
                """
            ),
            {"schema": schema, "tables": sorted(V7_TABLES)},
        ).fetchall()
    return {str(row[0]) for row in rows} == V7_TABLES


def _list_postgres_anomalies() -> list[dict[str, object]]:
    schema = _schema()
    if not _ensure_tables(schema):
        return []

    engine = create_postgres_engine()
    with engine.connect() as con:
        rows = con.execute(
            text(
                f"""
                SELECT
                    a.id_anomalia::text,
                    a.registro_id,
                    a.anomalia_codigo,
                    a.nome,
                    a.categoria,
                    a.severidade,
                    a.confianca,
                    a.status_anomalia,
                    a.origem,
                    a.regional,
                    a.conjunto,
                    a.equipamento,
                    a.uc,
                    a.ocorrencia,
                    a.interrupcao,
                    a.criado_em,
                    a.descricao,
                    COALESCE(
                        a.dados_originais ->> 'VALID_POS_OPERACAO',
                        a.dados_sugeridos ->> 'VALID_POS_OPERACAO',
                        ''
                    ) AS valid_pos_operacao,
                    COALESCE(s.acao, 'sem_sugestao') AS acao_sugerida,
                    COALESCE(s.nivel_confianca, 'inconclusiva') AS confianca_sugestao,
                    COALESCE(s.requer_aprovacao, true) AS requer_aprovacao,
                    COALESCE((a.impacto ->> 'dec')::numeric, 0) AS impacto_dec,
                    COALESCE((a.impacto ->> 'fec')::numeric, 0) AS impacto_fec,
                    COALESCE((a.impacto ->> 'dic')::numeric, 0) AS impacto_dic,
                    COALESCE((a.impacto ->> 'fic')::numeric, 0) AS impacto_fic,
                    COALESCE((a.impacto ->> 'ressarcimento')::numeric, 0) AS impacto_ressarcimento
                FROM {schema}.midway_v7_anomalia a
                LEFT JOIN LATERAL (
                    SELECT *
                    FROM {schema}.midway_v7_sugestao s
                    WHERE s.id_anomalia = a.id_anomalia
                    ORDER BY s.criado_em DESC
                    LIMIT 1
                ) s ON true
                ORDER BY
                    CASE a.severidade
                        WHEN 'crítica' THEN 1
                        WHEN 'alta' THEN 2
                        WHEN 'média' THEN 3
                        ELSE 4
                    END,
                    a.confianca DESC,
                    a.criado_em DESC
                LIMIT 500
                """
            )
        ).mappings().all()
    return [_summary_row(dict(row)) for row in rows]


def _postgres_anomaly_detail(id_anomalia: str) -> dict[str, object] | None:
    schema = _schema()
    if not _ensure_tables(schema):
        return None

    engine = create_postgres_engine()
    with engine.connect() as con:
        row = con.execute(
            text(
                f"""
                SELECT
                    id_anomalia::text,
                    registro_id,
                    anomalia_codigo,
                    nome,
                    categoria,
                    severidade,
                    confianca,
                    status_anomalia,
                    origem,
                    regional,
                    conjunto,
                    equipamento,
                    uc,
                    ocorrencia,
                    interrupcao,
                    criado_em,
                    descricao,
                    explicacao_simples,
                    explicacao_tecnica,
                    regra_violada,
                    impacto_possivel,
                    campos_envolvidos,
                    dados_originais,
                    dados_sugeridos,
                    impacto,
                    linha_tempo
                FROM {schema}.midway_v7_anomalia
                WHERE id_anomalia::text = :id_anomalia
                """
            ),
            {"id_anomalia": id_anomalia},
        ).mappings().first()
        if not row:
            return None

        evidences = con.execute(
            text(
                f"""
                SELECT campo, valor, origem, detalhe
                FROM {schema}.midway_v7_evidencia
                WHERE id_anomalia::text = :id_anomalia
                ORDER BY criado_em, campo
                """
            ),
            {"id_anomalia": id_anomalia},
        ).mappings().all()

        suggestion = con.execute(
            text(
                f"""
                SELECT
                    id_sugestao::text,
                    acao,
                    valor_original,
                    valor_sugerido,
                    justificativa,
                    nivel_confianca,
                    risco_regulatorio,
                    risco_operacional,
                    risco_juridico,
                    requer_aprovacao
                FROM {schema}.midway_v7_sugestao
                WHERE id_anomalia::text = :id_anomalia
                ORDER BY criado_em DESC
                LIMIT 1
                """
            ),
            {"id_anomalia": id_anomalia},
        ).mappings().first()

    return _detail_row(dict(row), [dict(item) for item in evidences], dict(suggestion) if suggestion else None)


def _summary_row(row: dict[str, Any]) -> dict[str, object]:
    return {
        "id_anomalia": row["id_anomalia"],
        "registro_id": row["registro_id"],
        "anomalia_codigo": row["anomalia_codigo"],
        "nome": row["nome"],
        "categoria": row["categoria"],
        "severidade": row["severidade"],
        "confianca": float(row["confianca"] or 0),
        "status": _status_label(row["status_anomalia"]),
        "origem": row["origem"],
        "regional": row["regional"],
        "conjunto": row["conjunto"],
        "equipamento": row["equipamento"],
        "uc": row["uc"],
        "ocorrencia": row["ocorrencia"],
        "interrupcao": row["interrupcao"],
        "criado_em": row["criado_em"],
        "descricao": row["descricao"],
        "valid_pos_operacao": row.get("valid_pos_operacao") or "",
        "acao_sugerida": row["acao_sugerida"],
        "confianca_sugestao": row["confianca_sugestao"],
        "requer_aprovacao": bool(row["requer_aprovacao"]),
        "impacto_dec": float(row["impacto_dec"] or 0),
        "impacto_fec": float(row["impacto_fec"] or 0),
        "impacto_dic": float(row["impacto_dic"] or 0),
        "impacto_fic": float(row["impacto_fic"] or 0),
        "impacto_ressarcimento": float(row["impacto_ressarcimento"] or 0),
    }


def _detail_row(
    row: dict[str, Any],
    evidences: list[dict[str, object]],
    suggestion: dict[str, object] | None,
) -> dict[str, object]:
    impact = row.get("impacto") or {}
    suggestion = suggestion or {}
    return {
        "id_anomalia": row["id_anomalia"],
        "registro_id": row["registro_id"],
        "anomalia_codigo": row["anomalia_codigo"],
        "nome": row["nome"],
        "categoria": row["categoria"],
        "severidade": row["severidade"],
        "confianca": float(row["confianca"] or 0),
        "status": _status_label(row["status_anomalia"]),
        "origem": row["origem"],
        "regional": row["regional"],
        "conjunto": row["conjunto"],
        "equipamento": row["equipamento"],
        "uc": row["uc"],
        "ocorrencia": row["ocorrencia"],
        "interrupcao": row["interrupcao"],
        "criado_em": row["criado_em"],
        "descricao": row["descricao"],
        "explicacao_simples": row["explicacao_simples"],
        "explicacao_tecnica": row["explicacao_tecnica"],
        "regra_violada": row["regra_violada"],
        "impacto_possivel": row["impacto_possivel"],
        "campos_envolvidos": row.get("campos_envolvidos") or [],
        "evidencias": evidences,
        "sugestao": {
            "id_sugestao": suggestion.get("id_sugestao"),
            "acao": suggestion.get("acao") or "sem_sugestao",
            "valor_original": suggestion.get("valor_original"),
            "valor_sugerido": suggestion.get("valor_sugerido"),
            "justificativa": suggestion.get("justificativa") or "Sem sugestão registrada.",
            "confianca": suggestion.get("nivel_confianca") or "inconclusiva",
            "risco_regulatorio": suggestion.get("risco_regulatorio"),
            "risco_operacional": suggestion.get("risco_operacional"),
            "risco_juridico": suggestion.get("risco_juridico"),
            "requer_aprovacao": bool(suggestion.get("requer_aprovacao", True)),
        },
        "impacto": {
            "dic": float(impact.get("dic") or 0),
            "fic": float(impact.get("fic") or 0),
            "dec": float(impact.get("dec") or 0),
            "fec": float(impact.get("fec") or 0),
            "ressarcimento": float(impact.get("ressarcimento") or 0),
        },
        "original": row.get("dados_originais") or {},
        "tratado_sugerido": row.get("dados_sugeridos") or {},
        "linha_tempo": row.get("linha_tempo") or [],
    }


def _summary_from_rows(rows: list[dict[str, object]], source: str) -> dict[str, object]:
    total = len(rows)
    return {
        "total": total,
        "pendentes": sum(1 for row in rows if row["status"] == "pendente"),
        "alto_risco": sum(1 for row in rows if row["severidade"] in {"alta", "crítica"}),
        "confianca_media": round(sum(float(row["confianca"]) for row in rows) / total, 3) if total else 0,
        "impacto_dec": round(sum(float(row["impacto_dec"]) for row in rows), 4),
        "impacto_ressarcimento": round(sum(float(row["impacto_ressarcimento"]) for row in rows), 2),
        "fonte": source,
    }


def _status_label(value: str | None) -> str:
    labels = {
        "PENDENTE": "pendente",
        "EM_ANALISE": "em análise",
        "APROVADA": "aprovada",
        "REJEITADA": "rejeitada",
        "APLICADA": "aplicada",
        "CANCELADA": "cancelada",
    }
    return labels.get(str(value or "").upper(), str(value or "pendente").lower())
