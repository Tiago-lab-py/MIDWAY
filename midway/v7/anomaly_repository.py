from __future__ import annotations

from typing import Any

from sqlalchemy import text

from midway.db.postgres import create_postgres_engine, get_config

V7_TABLES = {
    "midway_anomalia",
    "midway_evidencia",
    "midway_sugestao",
    "midway_decisao",
}

ANOMALY_MODULES: list[dict[str, object]] = [
    {
        "codigo": "SOBREPOSICAO_UC",
        "nome": "Sobreposição de UC",
        "descricao": "Registros de UC total ou parcialmente sobrepostos que podem duplicar DIC/FIC.",
        "escopo": "UC/interrupção",
        "criterio_curto": "mesma UC, mesmo tipo/protocolo e janela temporal sobreposta",
        "impacto": ["DIC/FIC", "DEC/FEC", "IQS"],
        "orientacao_analista": "Confirmar se a correção 91/D ou ajuste parcial preserva rastreabilidade antes de exportar.",
        "documento": "docs/modulos/sobreposicao_uc.md",
        "codigos_anomalia": ["SOBREPOSICAO_TOTAL_UC", "SOBREPOSICAO_PARCIAL_UC"],
        "categorias": ["sobreposição"],
    },
    {
        "codigo": "DURACAO_IMPACTO",
        "nome": "Duração e impacto atípico",
        "descricao": "Outliers de duração, volume de UCs ou impacto fora do padrão esperado.",
        "escopo": "ocorrência/interrupção",
        "criterio_curto": "duração alta, muitas UCs afetadas ou contenções fora do padrão",
        "impacto": ["DIC/FIC", "DEC/FEC", "qualidade"],
        "orientacao_analista": "Verificar se o outlier é evento real, erro de data/hora ou problema de composição do RAW.",
        "documento": "docs/modulos/duracao_impacto.md",
        "codigos_anomalia": ["OUTLIER_BRUTO"],
        "categorias": ["integridade"],
    },
    {
        "codigo": "COMPONENTE_CAUSA",
        "nome": "Componente/causa",
        "descricao": "Divergência de grupo, componente e causa frente à referência IQS, serviços e reclamações.",
        "escopo": "ocorrência/interrupção",
        "criterio_curto": "par componente/causa inválido ou divergente das evidências",
        "impacto": ["classificação IQS", "ressarcimento", "qualidade"],
        "orientacao_analista": "Comparar código e descrição atuais com sugestão, serviços, reclamações e referência IQS.",
        "documento": "docs/modulos/componente_causa.md",
        "codigos_anomalia": ["VIOLACAO_COMP_CAUSA", "ANALISE_TECNICA_9282"],
        "categorias": ["regulatória"],
    },
    {
        "codigo": "FALHA_EQUIPAMENTO_RA",
        "nome": "Suspeita falha RA",
        "descricao": "Religadores/equipamentos com FIC recorrente, baixa reclamação e possível falha de comunicação.",
        "escopo": "equipamento/alimentador/conjunto",
        "criterio_curto": "ocorrências sucessivas no equipamento/dia com FIC recorrente e reclamação incompatível",
        "impacto": ["FIC", "ressarcimento", "operação"],
        "orientacao_analista": "Conferir serviços, sequência de eventos, reclamações e atuação automática do equipamento.",
        "documento": "docs/modulos/falha_equipamento_ra.md",
        "codigos_anomalia": ["SUSPEITA_FALHA_RA", "SUSPEITA_FORTE_FALHA_RA"],
        "categorias": ["equipamento", "operacional"],
    },
    {
        "codigo": "INTERRUPCAO_SEM_UC",
        "nome": "Interrupção sem UC",
        "descricao": "Interrupções ou ocorrências sem UC apurável que podem indicar lacuna de integração ou exportação indevida.",
        "escopo": "interrupção/ocorrência",
        "criterio_curto": "interrupção relevante sem UC associada ou sem lastro apurável",
        "impacto": ["qualidade", "IQS"],
        "orientacao_analista": "Confirmar se a interrupção deve ser bloqueada, complementada ou mantida como evidência operacional.",
        "documento": "docs/modulos/interrupcao_sem_uc.md",
        "codigos_anomalia": ["INTERRUPCAO_SEM_UC", "OCORRENCIA_SEM_UC"],
        "categorias": ["sem_uc"],
    },
    {
        "codigo": "DUPLICIDADE_TIPO",
        "nome": "Duplicidade de tipo",
        "descricao": "Duplicidades ou mistura de tipo de interrupção/protocolo que podem afetar apuração.",
        "escopo": "UC/interrupção",
        "criterio_curto": "mesma UC/interrupção com tipos ou protocolos incompatíveis",
        "impacto": ["DIC/FIC", "qualidade"],
        "orientacao_analista": "Separar evento real de duplicidade sistêmica antes de sugerir correção.",
        "documento": "docs/modulos/duplicidade_tipo.md",
        "codigos_anomalia": ["DUPLICIDADE_TIPO", "TIPO_PROTOCOLO_DIVERGENTE"],
        "categorias": ["duplicidade"],
    },
    {
        "codigo": "DIA_CRITICO_ISE",
        "nome": "Dia crítico / ISE",
        "descricao": "Eventos vinculados a dia crítico, ISE ou DISE que exigem validação regulatória específica.",
        "escopo": "conjunto/dia/regional",
        "criterio_curto": "protocolo ou janela crítica com impacto regulatório",
        "impacto": ["DICRI", "DISE", "ressarcimento"],
        "orientacao_analista": "Validar janela, conjunto, protocolo e evidência antes de alterar apuração.",
        "documento": "docs/modulos/dia_critico_ise.md",
        "codigos_anomalia": ["DIA_CRITICO", "ISE", "DISE"],
        "categorias": ["ise", "dia_critico"],
    },
    {
        "codigo": "RESSARCIMENTO_ATIPICO",
        "nome": "Ressarcimento atípico",
        "descricao": "Compensações incompatíveis, duplicadas ou fora do filtro esperado para a ocorrência/UC.",
        "escopo": "UC/ocorrência",
        "criterio_curto": "ressarcimento estimado positivo, divergente ou concentrado fora do padrão",
        "impacto": ["ressarcimento", "DIC/FIC", "IQS"],
        "orientacao_analista": "Conferir duplicidade, filtros PRODIST/COPEL, UC faturada e vínculo com ocorrência antes de aprovar.",
        "documento": "docs/modulos/ressarcimento_atipico.md",
        "codigos_anomalia": ["RESSARCIMENTO_ATIPICO", "RESSARCIMENTO_DUPLICADO"],
        "categorias": ["ressarcimento"],
    },
    {
        "codigo": "RECLAMACOES_SERVICOS",
        "nome": "Reclamações e serviços",
        "descricao": "Cruzamento entre reclamações, serviços e ocorrências para sustentar ou questionar a classificação.",
        "escopo": "reclamação/serviço/ocorrência",
        "criterio_curto": "reclamação, serviço ou ausência deles altera confiança da suspeita",
        "impacto": ["qualidade", "operação", "governança"],
        "orientacao_analista": "Comparar evidências de atendimento, reclamações e serviços antes de aceitar sugestão automática.",
        "documento": "docs/modulos/reclamacoes_servicos.md",
        "codigos_anomalia": ["RECLAMACAO_SERVICO", "SERVICO_CONFLITO"],
        "categorias": ["reclamacao", "servico"],
    },
    {
        "codigo": "GOVERNANCA_IQS",
        "nome": "Governança IQS",
        "descricao": "Itens que dependem de decisão humana, auditoria ou regra operacional antes do pacote IQS.",
        "escopo": "governança/exportação",
        "criterio_curto": "ajuste com impacto em exportação IQS ou regra operacional auditável",
        "impacto": ["IQS", "governança"],
        "orientacao_analista": "Registrar decisão, justificativa e valores atuais/sugeridos antes de aprovar.",
        "documento": "docs/modulos/ajuste_manual_iqs.md",
        "codigos_anomalia": ["ESTADO_7_MANOBRA"],
        "categorias": ["operacional", "governança"],
    },
]


def module_catalog() -> list[dict[str, object]]:
    return [dict(item) for item in ANOMALY_MODULES]


def list_anomalies() -> dict[str, object]:
    rows = _list_postgres_anomalies()
    return {
        "resumo": _summary_from_rows(rows, "RAW/SILVER/GOLD"),
        "items": rows,
        "modulos": _modules_with_counts(rows),
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
                FROM {schema}.midway_anomalia a
                LEFT JOIN LATERAL (
                    SELECT *
                    FROM {schema}.midway_sugestao s
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
                FROM {schema}.midway_anomalia
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
                FROM {schema}.midway_evidencia
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
                FROM {schema}.midway_sugestao
                WHERE id_anomalia::text = :id_anomalia
                ORDER BY criado_em DESC
                LIMIT 1
                """
            ),
            {"id_anomalia": id_anomalia},
        ).mappings().first()

    return _detail_row(dict(row), [dict(item) for item in evidences], dict(suggestion) if suggestion else None)


def _summary_row(row: dict[str, Any]) -> dict[str, object]:
    module = _module_for(row["anomalia_codigo"], row["categoria"])
    return {
        "id_anomalia": row["id_anomalia"],
        "registro_id": row["registro_id"],
        "anomalia_codigo": row["anomalia_codigo"],
        "nome": row["nome"],
        "categoria": row["categoria"],
        "modulo_codigo": module["codigo"],
        "modulo_nome": module["nome"],
        "modulo_descricao": module["descricao"],
        "modulo_orientacao": module["orientacao_analista"],
        "modulo_documento": module["documento"],
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
    module = _module_for(row["anomalia_codigo"], row["categoria"])
    return {
        "id_anomalia": row["id_anomalia"],
        "registro_id": row["registro_id"],
        "anomalia_codigo": row["anomalia_codigo"],
        "nome": row["nome"],
        "categoria": row["categoria"],
        "modulo": module,
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


def _modules_with_counts(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    modules = []
    for module in ANOMALY_MODULES:
        module_rows = [row for row in rows if row.get("modulo_codigo") == module["codigo"]]
        modules.append(
            {
                **module,
                "total": len(module_rows),
                "pendentes": sum(1 for row in module_rows if row.get("status") == "pendente"),
                "alto_risco": sum(1 for row in module_rows if row.get("severidade") in {"alta", "crítica"}),
                "impacto_ressarcimento": round(sum(float(row.get("impacto_ressarcimento") or 0) for row in module_rows), 2),
                "impacto_dec": round(sum(float(row.get("impacto_dec") or 0) for row in module_rows), 4),
            }
        )
    return modules


def _module_for(code: str | None, category: str | None) -> dict[str, object]:
    normalized_code = str(code or "").upper()
    normalized_category = str(category or "").lower()
    for module in ANOMALY_MODULES:
        if normalized_code in {str(item).upper() for item in module["codigos_anomalia"]}:
            return module
    for module in ANOMALY_MODULES:
        if normalized_category in {str(item).lower() for item in module["categorias"]}:
            return module
    return {
        "codigo": "OUTRAS_ANOMALIAS",
        "nome": "Outras anomalias",
        "descricao": "Suspeitas ainda não classificadas em módulo específico.",
        "escopo": "variável",
        "criterio_curto": "critério registrado no detalhe da anomalia",
        "impacto": ["qualidade"],
        "orientacao_analista": "Revisar detalhe, evidências e decidir se deve virar módulo governado.",
        "documento": "docs/modulos/README.md",
        "codigos_anomalia": [],
        "categorias": [],
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
