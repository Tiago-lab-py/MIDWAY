from __future__ import annotations

import csv
import os
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

import duckdb
from fastapi import APIRouter, Depends, Query

from midway.api.security import AuthUser, require_profiles
from midway.api.serialization import api_row, api_rows
from midway.auditoria.suspeita_falha_ra import analisar_suspeita_falha_ra
from midway.transform.iqs_raw_utils import processed_path

router = APIRouter(prefix="/api/produto", tags=["produto"])

ANOMES = os.getenv("ANOMES", "202606")
INPUT_DIR = Path("data") / "input"
CAUSA_CSV_PATH = Path(os.getenv("IQS_CAUSA_CSV", str(INPUT_DIR / "causa.csv")))
COMPONENTE_CSV_PATH = Path(os.getenv("IQS_COMPONENTE_CSV", str(INPUT_DIR / "componente.csv")))
ALIMENTADOR_CSV_PATH = Path(
    os.getenv("MIDWAY_ALIMENTADOR_CSV", str(INPUT_DIR / "Referencia_Alimentador_Copel.CSV"))
)
CONJUNTO_CSV_PATH = Path(
    os.getenv("MIDWAY_CONJUNTO_CSV", str(INPUT_DIR / "Referencia_DEC FEC CONJUNTO Ano_Copel.csv"))
)
DURACAO_MINIMA_ISE_HORA = 3.0 / 60.0
CAUSAS_ISE = (
    "2", "4", "5", "6", "7", "8", "9", "13", "15", "23",
    "24", "28", "39", "40", "41", "52", "54", "69", "82",
)
REGRAS_EXPURGO_DIC_BRUTO = ("DFC", "USU", "USI", "ACI", "FM", "ERR", "DUP", "CHP", "DFI", "PTP")
REGRAS_EXPURGO_FIC_BRUTO = REGRAS_EXPURGO_DIC_BRUTO + ("MAN",)


def _table_exists(con: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    return (
        con.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'main'
              AND table_name = ?
            """,
            [table_name],
        ).fetchone()[0]
        > 0
    )


def _table_columns(con: duckdb.DuckDBPyConnection, table_name: str) -> set[str]:
    return {
        row[0].upper()
        for row in con.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'main'
              AND table_name = ?
            """,
            [table_name],
        ).fetchall()
    }


def _connect_processed_readonly() -> tuple[duckdb.DuckDBPyConnection | None, dict[str, object]]:
    db_path = processed_path(ANOMES)
    fonte = {"fonte": str(db_path).replace("\\", "/"), "status": "ok"}
    if not db_path.exists():
        return None, {**fonte, "status": "ausente"}
    try:
        return duckdb.connect(str(db_path), read_only=True), fonte
    except (duckdb.Error, OSError) as exc:
        return None, {
            **fonte,
            "status": "indisponivel",
            "erro": str(exc).splitlines()[0],
            "acao_sugerida": "fechar outra aplicação usando o DuckDB ou executar novamente",
        }


def _clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]
    return text


def _display(codigo: str, nome: str) -> str:
    return f"{codigo} - {nome or 'descrição não disponível'}"


def _number(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _sql_lista_texto(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{valor}'" for valor in valores)


def _coluna_texto_expr(colunas: set[str], nome_coluna: str, padrao: str) -> str:
    if nome_coluna.upper() in colunas:
        return f"NULLIF(TRIM(CAST({nome_coluna} AS VARCHAR)), '')"
    return padrao


def _coluna_numero_expr(colunas: set[str], nome_coluna: str, padrao: str = "0") -> str:
    if nome_coluna.upper() in colunas:
        return f"COALESCE(TRY_CAST({nome_coluna} AS DOUBLE), 0)"
    return padrao


def _csv_count_latest(pattern: str) -> tuple[int, str]:
    files = sorted((Path("data") / "marts").glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    if not files:
        return 0, ""
    latest = files[0]
    with latest.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file, delimiter="|")
        rows = list(reader)
    return max(len(rows) - 1, 0), str(latest).replace("\\", "/")


def _module_metric(
    codigo: str,
    total: float = 0,
    chi: float = 0,
    ci: float = 0,
    ressarcimento: float = 0,
    fonte: str = "",
    status: str = "ok",
) -> dict[str, object]:
    return {
        "codigo": codigo,
        "total": total,
        "impacto_chi": chi,
        "impacto_ci": ci,
        "impacto_ressarcimento": ressarcimento,
        "fonte": fonte,
        "status": status,
    }


def _compensacao_dicri_dise(con: duckdb.DuckDBPyConnection) -> tuple[float, str]:
    if not _table_exists(con, "gold_ressarcimento_prodist"):
        return 0.0, ""
    colunas = _table_columns(con, "gold_ressarcimento_prodist")
    if not {"COMP_DICRI_PRODIST", "COMP_DISE_PRODIST"}.issubset(colunas):
        return 0.0, ""
    valor = con.execute(
        """
        SELECT
            COALESCE(SUM(COMP_DICRI_PRODIST), 0)
          + COALESCE(SUM(COMP_DISE_PRODIST), 0) AS COMP_DICRI_DISE
        FROM gold_ressarcimento_prodist
        """
    ).fetchone()[0]
    return _number(valor), "gold_ressarcimento_prodist · DICRI/DISE parcial por UC"


def _resumo_modulos_automatizados() -> dict[str, object]:
    con, fonte_processado = _connect_processed_readonly()
    modulos = {
        "INTERRUPCAO_SEM_UC": _module_metric("INTERRUPCAO_SEM_UC", status="ausente"),
        "DUPLICIDADE_TIPO": _module_metric("DUPLICIDADE_TIPO", status="ausente"),
        "DIA_CRITICO_ISE": _module_metric("DIA_CRITICO_ISE", status="ausente"),
        "RECLAMACOES_SERVICOS": _module_metric("RECLAMACOES_SERVICOS", status="ausente"),
    }

    if con is not None:
        try:
            comp_dicri_dise, fonte_comp_dicri_dise = _compensacao_dicri_dise(con)
            if _table_exists(con, "adms_iqs_interrupcao_sem_uc_export"):
                row = con.execute(
                    """
                    SELECT
                        COUNT(*) AS total,
                        SUM(DATE_DIFF('second', TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP), TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP)) / 3600.0) AS chi,
                        SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0' THEN 1 ELSE 0 END) AS ci
                    FROM adms_iqs_interrupcao_sem_uc_export
                    WHERE TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP) IS NOT NULL
                      AND TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP) IS NOT NULL
                      AND TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP) >= TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP)
                    """
                ).fetchone()
                modulos["INTERRUPCAO_SEM_UC"] = _module_metric(
                    "INTERRUPCAO_SEM_UC",
                    total=_number(row[0]),
                    chi=_number(row[1]),
                    ci=_number(row[2]),
                    fonte="adms_iqs_interrupcao_sem_uc_export",
                )

            if _table_exists(con, "gold_apuracao_uc"):
                colunas = _table_columns(con, "gold_apuracao_uc")
                obrigatorias = {"NUM_UC_UCI", "COD_CAUSA_INTRP", "DURACAO_HORA"}
                if obrigatorias.issubset(colunas):
                    causa = "NULLIF(TRIM(CAST(COD_CAUSA_INTRP AS VARCHAR)), '')"
                    uc = "NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '')"
                    duracao = _coluna_numero_expr(colunas, "DURACAO_HORA")
                    sigla_tiqs_dic = (
                        "COALESCE(NULLIF(TRIM(CAST(SIGLA_TIQS_DIC AS VARCHAR)), ''), 'DIC_')"
                        if "SIGLA_TIQS_DIC" in colunas
                        else "'DIC_'"
                    )
                    sigla_tiqs_fic = (
                        "COALESCE(NULLIF(TRIM(CAST(SIGLA_TIQS_FIC AS VARCHAR)), ''), 'FIC_')"
                        if "SIGLA_TIQS_FIC" in colunas
                        else "'FIC_'"
                    )
                    sigla_reid_dic = _coluna_texto_expr(colunas, "SIGLA_REID_DIC", "NULL")
                    sigla_reid_fic = _coluna_texto_expr(colunas, "SIGLA_REID_FIC", "NULL")
                    causa_ise_longa = (
                        f"{causa} IN ({_sql_lista_texto(CAUSAS_ISE)}) "
                        f"AND {duracao} >= {DURACAO_MINIMA_ISE_HORA}"
                    )
                    dic_liquido = f"SUBSTR({sigla_tiqs_dic}, 1, 4) = 'DIC_' AND {sigla_reid_dic} IS NULL"
                    fic_liquido = f"SUBSTR({sigla_tiqs_fic}, 1, 4) = 'FIC_' AND {sigla_reid_fic} IS NULL"
                    row = con.execute(
                        f"""
                        WITH uc_ise AS (
                            SELECT
                                {uc} AS uc,
                                SUM(CASE WHEN {causa_ise_longa} AND {dic_liquido} THEN {duracao} ELSE 0 END) AS chi,
                                SUM(CASE WHEN {causa_ise_longa} AND {fic_liquido} THEN 1 ELSE 0 END) AS ci
                            FROM gold_apuracao_uc
                            WHERE {uc} IS NOT NULL
                            GROUP BY {uc}
                        )
                        SELECT
                            SUM(CASE WHEN chi > 0 OR ci > 0 THEN 1 ELSE 0 END) AS total,
                            SUM(chi) AS chi,
                            SUM(ci) AS ci
                        FROM uc_ise
                        """
                    ).fetchone()
                    modulos["DIA_CRITICO_ISE"] = _module_metric(
                        "DIA_CRITICO_ISE",
                        total=_number(row[0]),
                        chi=_number(row[1]),
                        ci=_number(row[2]),
                        ressarcimento=comp_dicri_dise,
                        fonte=(
                            "gold_apuracao_uc · duração >= 3 min"
                            + (f"; {fonte_comp_dicri_dise}" if fonte_comp_dicri_dise else "")
                        ),
                    )
            elif _table_exists(con, "gold_simulacao_ise_uc"):
                row = con.execute(
                    """
                    SELECT
                        SUM(CASE WHEN ISE_POTENCIAL = 'S' OR ISE_RECLASSIFICAVEL = 'S' THEN 1 ELSE 0 END) AS total,
                        SUM(ISE_CHI_LIQUIDO_RECLASSIFICAVEL) AS chi,
                        SUM(ISE_CI_LIQUIDO_RECLASSIFICAVEL) AS ci
                    FROM gold_simulacao_ise_uc
                    """
                ).fetchone()
                modulos["DIA_CRITICO_ISE"] = _module_metric(
                    "DIA_CRITICO_ISE",
                    total=_number(row[0]),
                    chi=_number(row[1]),
                    ci=_number(row[2]),
                    ressarcimento=comp_dicri_dise,
                    fonte="gold_simulacao_ise_uc" + (f"; {fonte_comp_dicri_dise}" if fonte_comp_dicri_dise else ""),
                )

            if _table_exists(con, "gold_reclamacao_ocorrencia_resumo"):
                row = con.execute(
                    """
                    SELECT
                        COUNT(*) AS ocorrencias,
                        SUM(QTD_RECLAMACOES) AS reclamacoes,
                        SUM(FIC_OCORRENCIA) AS fic,
                        SUM(DIC_OCORRENCIA) AS dic
                    FROM gold_reclamacao_ocorrencia_resumo
                    """
                ).fetchone()
                modulos["RECLAMACOES_SERVICOS"] = _module_metric(
                    "RECLAMACOES_SERVICOS",
                    total=_number(row[0]),
                    chi=_number(row[3]),
                    ci=_number(row[2]) or _number(row[1]),
                    fonte="gold_reclamacao_ocorrencia_resumo",
                )
        finally:
            con.close()

    duplicidade_total, duplicidade_fonte = _csv_count_latest(f"Auditoria_Duplicidade_Tipo_INTRP_{ANOMES}_*_DUP_EXATA.CSV")
    if duplicidade_total:
        modulos["DUPLICIDADE_TIPO"] = _module_metric(
            "DUPLICIDADE_TIPO",
            total=duplicidade_total,
            fonte=duplicidade_fonte,
        )

    return {"modulos": modulos, "fonte_processado": fonte_processado}


def _read_latest_csv_sample(pattern: str, limite: int) -> tuple[list[dict[str, object]], str]:
    files = sorted((Path("data") / "marts").glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    if not files:
        return [], ""
    latest = files[0]
    rows: list[dict[str, object]] = []
    with latest.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, delimiter="|")
        for index, row in enumerate(reader):
            if index >= limite:
                break
            rows.append(dict(row))
    return rows, str(latest).replace("\\", "/")


def _amostra_modulo_automatizado(codigo: str, limite: int) -> dict[str, object]:
    codigo = codigo.upper().strip()
    if codigo == "DUPLICIDADE_TIPO":
        rows, fonte = _read_latest_csv_sample(f"Auditoria_Duplicidade_Tipo_INTRP_{ANOMES}_*_DUP_EXATA.CSV", limite)
        return {"codigo": codigo, "fonte": fonte or "data/marts", "items": rows}

    con, fonte_processado = _connect_processed_readonly()
    if con is None:
        return {"codigo": codigo, "fonte": fonte_processado, "items": []}

    try:
        if codigo == "INTERRUPCAO_SEM_UC" and _table_exists(con, "adms_iqs_interrupcao_sem_uc_export"):
            rows = con.execute(
                """
                SELECT
                    NUM_OCORRENCIA_ADMS,
                    NUM_SEQ_INTRP,
                    NUM_UC_UCI,
                    REGIONAL_EXPORT,
                    DATA_HORA_INIC_INTRP,
                    DATA_HORA_FIM_INTRP,
                    TIPO_PROTOC_JUSTIF_UCI
                FROM adms_iqs_interrupcao_sem_uc_export
                ORDER BY DATA_HORA_INIC_INTRP DESC, NUM_OCORRENCIA_ADMS
                LIMIT ?
                """,
                [limite],
            ).fetchdf().to_dict(orient="records")
            return {"codigo": codigo, "fonte": "adms_iqs_interrupcao_sem_uc_export", "items": rows}

        if codigo == "DIA_CRITICO_ISE" and _table_exists(con, "gold_simulacao_ise_uc"):
            rows = con.execute(
                """
                SELECT
                    UC,
                    ISE_POTENCIAL,
                    ISE_RECLASSIFICAVEL,
                    EVENTOS_CAUSA_ISE,
                    OCORRENCIAS_CAUSA_ISE,
                    ISE_CI_LIQUIDO_RECLASSIFICAVEL,
                    ISE_CHI_LIQUIDO_RECLASSIFICAVEL,
                    COD_CAUSAS_ISE
                FROM gold_simulacao_ise_uc
                WHERE ISE_POTENCIAL = 'S'
                   OR ISE_RECLASSIFICAVEL = 'S'
                ORDER BY ISE_CHI_LIQUIDO_RECLASSIFICAVEL DESC, ISE_CI_LIQUIDO_RECLASSIFICAVEL DESC
                LIMIT ?
                """,
                [limite],
            ).fetchdf().to_dict(orient="records")
            return {"codigo": codigo, "fonte": "gold_simulacao_ise_uc", "items": rows}

        if codigo == "RECLAMACOES_SERVICOS" and _table_exists(con, "gold_reclamacao_ocorrencia_resumo"):
            rows = con.execute(
                """
                SELECT
                    NUM_OCORRENCIA_ADMS,
                    QTD_RECLAMACOES,
                    QTD_UCS_RECLAMANTES,
                    FIC_OCORRENCIA,
                    DIC_OCORRENCIA,
                    MAX_SCORE_VINCULO_RECLAMACAO,
                    TIPOS_RECLAMACAO_PROVAVEIS,
                    CAUSAS_PROVAVEIS_RECLAMACAO
                FROM gold_reclamacao_ocorrencia_resumo
                ORDER BY QTD_RECLAMACOES DESC, MAX_SCORE_VINCULO_RECLAMACAO DESC
                LIMIT ?
                """,
                [limite],
            ).fetchdf().to_dict(orient="records")
            return {"codigo": codigo, "fonte": "gold_reclamacao_ocorrencia_resumo", "items": rows}

        if codigo == "SOBREPOSICAO_UC" and _table_exists(con, "export_sobreposicao_total_uc"):
            rows = con.execute(
                """
                SELECT *
                FROM export_sobreposicao_total_uc
                LIMIT ?
                """,
                [limite],
            ).fetchdf().to_dict(orient="records")
            return {"codigo": codigo, "fonte": "export_sobreposicao_total_uc", "items": rows}

        return {"codigo": codigo, "fonte": fonte_processado, "items": []}
    finally:
        con.close()


def _read_reference_rows(path: Path) -> tuple[list[dict[str, str]], dict[str, object]]:
    fonte = {"fonte": str(path).replace("\\", "/"), "status": "ok"}
    if not path.exists():
        return [], {**fonte, "status": "ausente"}

    last_error = ""
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            with path.open("r", encoding=encoding, newline="") as file:
                sample = file.read(4096)
                dialect = csv.Sniffer().sniff(sample, delimiters=";,|\t")
                file.seek(0)
                rows = [dict(row) for row in csv.DictReader(file, dialect=dialect)]
            return rows, {**fonte, "encoding": encoding, "delimitador": dialect.delimiter}
        except (csv.Error, UnicodeDecodeError, OSError) as exc:
            last_error = str(exc)

    return [], {**fonte, "status": "erro", "erro": last_error}


def _hierarchy_reference_maps() -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]], list[dict[str, object]]]:
    conjunto_rows, conjunto_fonte = _read_reference_rows(CONJUNTO_CSV_PATH)
    alimentador_rows, alimentador_fonte = _read_reference_rows(ALIMENTADOR_CSV_PATH)
    fontes = [conjunto_fonte, alimentador_fonte]

    conjuntos: dict[str, dict[str, str]] = {}
    for row in conjunto_rows:
        codigo = _clean(row.get("CEA"))
        nome = _clean(row.get("NOME_CEA"))
        ano = _clean(row.get("ANO"))
        if not codigo or not nome:
            continue
        atual = conjuntos.get(codigo)
        if not atual or (ano.isdigit() and atual.get("ano", "").isdigit() and int(ano) > int(atual["ano"])):
            conjuntos[codigo] = {
                "codigo": codigo,
                "nome": nome,
                "ano": ano,
                "fonte": str(CONJUNTO_CSV_PATH).replace("\\", "/"),
            }
        elif not atual:
            conjuntos[codigo] = {
                "codigo": codigo,
                "nome": nome,
                "ano": ano,
                "fonte": str(CONJUNTO_CSV_PATH).replace("\\", "/"),
            }

    alimentadores: dict[str, dict[str, str]] = {}
    for row in alimentador_rows:
        codigo = _clean(row.get("NUM_OPER_ALIM_ALOPER"))
        nome = _clean(row.get("NOME_ALOPER"))
        conjunto = _clean(row.get("CONJUNTO"))
        if not codigo or not nome:
            continue
        alimentadores[codigo] = {
            "codigo": codigo,
            "nome": nome,
            "conjunto_codigo": conjunto,
            "conjunto_nome": conjuntos.get(conjunto, {}).get("nome", ""),
            "fonte": str(ALIMENTADOR_CSV_PATH).replace("\\", "/"),
        }

    return conjuntos, alimentadores, fontes


def _dictionary_item(
    *,
    tipo: str,
    tipo_nome: str,
    codigo: Any,
    nome: Any = "",
    descricao: Any = "",
    fonte: str,
    status: str = "ativo",
    relacoes: dict[str, str] | None = None,
) -> dict[str, object]:
    codigo_texto = _clean(codigo)
    nome_texto = _clean(nome)
    descricao_texto = _clean(descricao)
    return {
        "id": "|".join([tipo, codigo_texto, *(relacoes or {}).values()]),
        "tipo": tipo,
        "tipo_nome": tipo_nome,
        "codigo": codigo_texto,
        "nome": nome_texto,
        "descricao": descricao_texto or nome_texto or "descrição não disponível",
        "exibicao": _display(codigo_texto, nome_texto or descricao_texto),
        "fonte": fonte,
        "status": status,
        "relacoes": relacoes or {},
        "descricao_disponivel": bool(nome_texto or descricao_texto),
    }


def _static_dictionaries() -> list[dict[str, object]]:
    items: list[dict[str, object]] = []

    for codigo, nome in [
        ("COPEL", "COPEL consolidado"),
        ("CSL", "Regional Centro-Sul"),
        ("LES", "Regional Leste"),
        ("NRT", "Regional Norte"),
        ("NRO", "Regional Noroeste"),
        ("OES", "Regional Oeste"),
    ]:
        items.append(
            _dictionary_item(
                tipo="regional",
                tipo_nome="Regional",
                codigo=codigo,
                nome=nome,
                fonte="contrato_midway",
            )
        )

    for codigo, nome in [("1", "Acidental"), ("2", "Programada"), ("3", "Voluntária")]:
        items.append(
            _dictionary_item(
                tipo="cod_tipo_intrp",
                tipo_nome="Tipo de interrupção",
                codigo=codigo,
                nome=nome,
                fonte="docs_ativos",
            )
        )

    for codigo, nome in [
        ("0", "Base DIC/FIC/DMIC"),
        ("1", "DICRI / dia crítico"),
        ("5", "ISE"),
        ("6", "DISE"),
    ]:
        items.append(
            _dictionary_item(
                tipo="tipo_protoc_justif_uci",
                tipo_nome="Protocolo de justificativa UC",
                codigo=codigo,
                nome=nome,
                fonte="docs_ativos",
            )
        )

    items.append(
        _dictionary_item(
            tipo="num_motivo_trat_dif_uci",
            tipo_nome="Motivo de tratamento diferenciado",
            codigo="91",
            nome="Tratamento diferenciado por regra governada",
            descricao="Usado em ajustes como sobreposição total/parcial de UC conforme contrato ativo.",
            fonte="docs_ativos",
        )
    )

    return items


def _read_csv_dictionary(path: Path, code_column: str, name_column: str, tipo: str, tipo_nome: str) -> list[dict[str, object]]:
    if not path.exists():
        return []

    items: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            codigo = _clean(row.get(code_column))
            if not codigo:
                continue
            items.append(
                _dictionary_item(
                    tipo=tipo,
                    tipo_nome=tipo_nome,
                    codigo=codigo,
                    nome=row.get(name_column),
                    fonte=str(path).replace("\\", "/"),
                )
            )
    return items


def _load_reference_dictionaries() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    items: list[dict[str, object]] = []
    fontes: list[dict[str, object]] = []
    conjuntos_ref, alimentadores_ref, hierarchy_fontes = _hierarchy_reference_maps()
    fontes.extend(hierarchy_fontes)

    for conjunto in conjuntos_ref.values():
        items.append(
            _dictionary_item(
                tipo="conjunto_eletrico",
                tipo_nome="Conjunto elétrico",
                codigo=conjunto["codigo"],
                nome=conjunto["nome"],
                fonte=conjunto["fonte"],
                relacoes={"ano_referencia": conjunto.get("ano", "")},
            )
        )

    for alimentador in alimentadores_ref.values():
        relacoes = {"conjunto_codigo": alimentador.get("conjunto_codigo", "")}
        if alimentador.get("conjunto_nome"):
            relacoes["conjunto_nome"] = alimentador["conjunto_nome"]
        items.append(
            _dictionary_item(
                tipo="alimentador",
                tipo_nome="Alimentador",
                codigo=alimentador["codigo"],
                nome=alimentador["nome"],
                fonte=alimentador["fonte"],
                relacoes=relacoes,
            )
        )

    con, fonte_processado = _connect_processed_readonly()
    fontes.append(fonte_processado)

    if con is None:
        items.extend(_read_csv_dictionary(COMPONENTE_CSV_PATH, "COD_COMP", "DESC_COMP", "componente", "Componente"))
        items.extend(_read_csv_dictionary(CAUSA_CSV_PATH, "COD_CAUSA", "DESC_CAUSA", "causa", "Causa"))
        return items, fontes

    try:
        if _table_exists(con, "gold_iqs_referencia_componente_causa"):
            fontes.append(
                {
                    "fonte": "gold_iqs_referencia_componente_causa",
                    "status": "ok",
                }
            )
            for codigo, nome in con.execute(
                """
                SELECT DISTINCT COD_GRUPO_GCR, DESC_GRUPO_GCR
                FROM gold_iqs_referencia_componente_causa
                WHERE NULLIF(TRIM(CAST(COD_GRUPO_GCR AS VARCHAR)), '') IS NOT NULL
                ORDER BY COD_GRUPO_GCR
                """
            ).fetchall():
                items.append(
                    _dictionary_item(
                        tipo="grupo_componente_causa",
                        tipo_nome="Grupo componente/causa",
                        codigo=codigo,
                        nome=nome,
                        fonte="gold_iqs_referencia_componente_causa",
                    )
                )

            for grupo, grupo_nome, componente, componente_nome in con.execute(
                """
                SELECT DISTINCT COD_GRUPO_GCR, DESC_GRUPO_GCR, COD_COMP, DESC_COMP
                FROM gold_iqs_referencia_componente_causa
                WHERE NULLIF(TRIM(CAST(COD_COMP AS VARCHAR)), '') IS NOT NULL
                ORDER BY COD_GRUPO_GCR, COD_COMP
                """
            ).fetchall():
                items.append(
                    _dictionary_item(
                        tipo="componente",
                        tipo_nome="Componente",
                        codigo=componente,
                        nome=componente_nome,
                        fonte="gold_iqs_referencia_componente_causa",
                        relacoes={
                            "grupo_codigo": _clean(grupo),
                            "grupo_nome": _clean(grupo_nome),
                        },
                    )
                )

            for grupo, grupo_nome, componente, componente_nome, causa, causa_nome in con.execute(
                """
                SELECT DISTINCT COD_GRUPO_GCR, DESC_GRUPO_GCR, COD_COMP, DESC_COMP, COD_CAUSA, DESC_CAUSA
                FROM gold_iqs_referencia_componente_causa
                WHERE NULLIF(TRIM(CAST(COD_CAUSA AS VARCHAR)), '') IS NOT NULL
                ORDER BY COD_GRUPO_GCR, COD_COMP, COD_CAUSA
                """
            ).fetchall():
                items.append(
                    _dictionary_item(
                        tipo="causa",
                        tipo_nome="Causa",
                        codigo=causa,
                        nome=causa_nome,
                        fonte="gold_iqs_referencia_componente_causa",
                        relacoes={
                            "grupo_codigo": _clean(grupo),
                            "grupo_nome": _clean(grupo_nome),
                            "componente_codigo": _clean(componente),
                            "componente_nome": _clean(componente_nome),
                        },
                    )
                )
        else:
            fontes.append({"fonte": "gold_iqs_referencia_componente_causa", "status": "ausente"})
            items.extend(_read_csv_dictionary(COMPONENTE_CSV_PATH, "COD_COMP", "DESC_COMP", "componente", "Componente"))
            items.extend(_read_csv_dictionary(CAUSA_CSV_PATH, "COD_CAUSA", "DESC_CAUSA", "causa", "Causa"))

        if _table_exists(con, "gold_interrupcao_tratada"):
            fontes.append(
                {
                    "fonte": "gold_interrupcao_tratada",
                    "status": "ok",
                }
            )
            for conjunto in con.execute(
                """
                SELECT DISTINCT COD_CONJTO_ELET_ANEEL_INTRP
                FROM gold_interrupcao_tratada
                WHERE NULLIF(TRIM(CAST(COD_CONJTO_ELET_ANEEL_INTRP AS VARCHAR)), '') IS NOT NULL
                ORDER BY COD_CONJTO_ELET_ANEEL_INTRP
                """
            ).fetchall():
                conjunto_codigo = _clean(conjunto[0])
                ref = conjuntos_ref.get(conjunto_codigo, {})
                if ref:
                    continue
                items.append(
                    _dictionary_item(
                        tipo="conjunto_eletrico",
                        tipo_nome="Conjunto elétrico",
                        codigo=conjunto_codigo,
                        nome=ref.get("nome", ""),
                        fonte="gold_interrupcao_tratada",
                        status="ativo" if ref.get("nome") else "nome_pendente",
                        relacoes={"fonte_nome": ref.get("fonte", "")} if ref.get("fonte") else {},
                    )
                )

            for regional, conjunto, alimentador in con.execute(
                """
                SELECT DISTINCT SIGLA_REGIONAL, COD_CONJTO_ELET_ANEEL_INTRP, ALIM_INTRP
                FROM gold_interrupcao_tratada
                WHERE NULLIF(TRIM(CAST(ALIM_INTRP AS VARCHAR)), '') IS NOT NULL
                ORDER BY SIGLA_REGIONAL, COD_CONJTO_ELET_ANEEL_INTRP, ALIM_INTRP
                """
            ).fetchall():
                alimentador_codigo = _clean(alimentador)
                conjunto_codigo = _clean(conjunto)
                ref = alimentadores_ref.get(alimentador_codigo, {})
                if ref:
                    continue
                items.append(
                    _dictionary_item(
                        tipo="alimentador",
                        tipo_nome="Alimentador",
                        codigo=alimentador_codigo,
                        nome=ref.get("nome", ""),
                        fonte="gold_interrupcao_tratada",
                        status="ativo" if ref.get("nome") else "nome_pendente",
                        relacoes={
                            "regional": _clean(regional),
                            "conjunto_codigo": conjunto_codigo,
                            "conjunto_nome": conjuntos_ref.get(conjunto_codigo, {}).get("nome", ""),
                            "fonte_nome": ref.get("fonte", ""),
                        },
                    )
                )
    finally:
        con.close()

    return items, fontes


def _filter_dictionaries(
    items: list[dict[str, object]],
    *,
    tipo: str | None,
    q: str | None,
) -> list[dict[str, object]]:
    tipo_norm = _clean(tipo).lower()
    query = _clean(q).lower()
    filtered = items
    if tipo_norm:
        filtered = [item for item in filtered if str(item["tipo"]).lower() == tipo_norm]
    if query:
        filtered = [
            item
            for item in filtered
            if query
            in " ".join(
                [
                    str(item.get("tipo", "")),
                    str(item.get("tipo_nome", "")),
                    str(item.get("codigo", "")),
                    str(item.get("nome", "")),
                    str(item.get("descricao", "")),
                    str(item.get("exibicao", "")),
                    " ".join(str(value) for value in dict(item.get("relacoes", {})).values()),
                ]
            ).lower()
        ]
    return filtered


def _empty_cockpit(user: AuthUser, fontes: list[dict[str, object]]) -> dict[str, object]:
    return {
        "usuario": user.login,
        "anomes": ANOMES,
        "status": "fonte_indisponivel",
        "lente_padrao": "regulatoria",
        "nivel_padrao": "macro",
        "cards": [],
        "rankings": {"regional": [], "conjunto": []},
        "alertas": [
            {
                "tipo": "fonte",
                "mensagem": "Cockpit sem dados porque a base processada não está disponível no momento.",
            }
        ],
        "fontes": fontes,
        "regras": {
            "regulatoria": "usa bases faturadas/apuráveis quando disponíveis",
            "cliente_operacao": "mantém contadores operacionais para futura visão de todos os afetados",
            "ordenacao": "rankings priorizam CHI, CI e compensação PRODIST",
        },
    }


def _metric_card(codigo: str, titulo: str, valor: Any, unidade: str, descricao: str, lente: str) -> dict[str, object]:
    return {
        "codigo": codigo,
        "titulo": titulo,
        "valor": _number(valor),
        "unidade": unidade,
        "descricao": descricao,
        "lente": lente,
    }


def _fetchone_dict(con: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | None = None) -> dict[str, Any]:
    cursor = con.execute(sql, params or [])
    row = cursor.fetchone()
    if not row:
        return {}
    columns = [item[0] for item in cursor.description]
    return dict(zip(columns, row))


def _fetchall_dicts(
    con: duckdb.DuckDBPyConnection,
    sql: str,
    params: list[Any] | None = None,
) -> list[dict[str, Any]]:
    cursor = con.execute(sql, params or [])
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _df_records(df: Any, limite: int | None = None) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    if limite is not None:
        df = df.head(limite)
    clean_df = df.where(df.notna(), None)
    return api_rows(clean_df.to_dict(orient="records"))


@lru_cache(maxsize=4)
def _cached_suspeita_falha_ra(anomes: str) -> tuple[Any, Any]:
    return analisar_suspeita_falha_ra(anomes=anomes)


def _ranking_regional(con: duckdb.DuckDBPyConnection, limite: int) -> list[dict[str, object]]:
    if not _table_exists(con, "gold_apuracao_uc"):
        return []

    ressarcimento_cte = ""
    ressarcimento_join = ""
    ressarcimento_select = "CAST(0 AS DOUBLE) AS COMP_TOTAL_PRODIST, CAST(0 AS BIGINT) AS UCS_COM_COMPENSACAO"
    if _table_exists(con, "gold_ressarcimento_prodist"):
        ressarcimento_cte = """
        , ucs_regionais AS (
            SELECT DISTINCT
                COALESCE(NULLIF(TRIM(CAST(REGIONAL AS VARCHAR)), ''), 'SEM_REGIONAL') AS regional,
                TRIM(CAST(NUM_UC_UCI AS VARCHAR)) AS uc
            FROM gold_apuracao_uc
            WHERE NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '') IS NOT NULL
        ),
        ressarcimento AS (
            SELECT
                u.regional,
                COUNT(DISTINCT r.UC) AS ucs_com_compensacao,
                SUM(COALESCE(r.COMP_TOTAL_PRODIST, 0)) AS comp_total_prodist
            FROM ucs_regionais u
            JOIN gold_ressarcimento_prodist r
              ON TRIM(CAST(r.UC AS VARCHAR)) = u.uc
            WHERE COALESCE(r.COMP_TOTAL_PRODIST, 0) > 0
            GROUP BY u.regional
        )
        """
        ressarcimento_join = "LEFT JOIN ressarcimento r ON r.regional = b.regional"
        ressarcimento_select = (
            "COALESCE(r.comp_total_prodist, 0) AS COMP_TOTAL_PRODIST, "
            "COALESCE(r.ucs_com_compensacao, 0) AS UCS_COM_COMPENSACAO"
        )

    rows = con.execute(
        f"""
        WITH base AS (
            SELECT
                COALESCE(NULLIF(TRIM(CAST(REGIONAL AS VARCHAR)), ''), 'SEM_REGIONAL') AS regional,
                COUNT(DISTINCT NUM_OCORRENCIA_ADMS) AS ocorrencias,
                COUNT(DISTINCT NUM_SEQ_INTRP) AS interrupcoes,
                COUNT(DISTINCT NUM_UC_UCI) AS ucs,
                COUNT(DISTINCT COD_CONJTO_ELET_ANEEL_INTRP) AS conjuntos,
                SUM(COALESCE(CI_LIQUIDO, 0)) AS ci_liquido,
                SUM(COALESCE(CHI_LIQUIDO, 0)) AS chi_liquido,
                MAX(COALESCE(DURACAO_HORA, 0)) AS duracao_maxima_h
            FROM gold_apuracao_uc
            GROUP BY 1
        )
        {ressarcimento_cte}
        SELECT
            b.regional,
            b.ocorrencias,
            b.interrupcoes,
            b.ucs,
            b.conjuntos,
            b.ci_liquido,
            b.chi_liquido,
            b.duracao_maxima_h,
            {ressarcimento_select}
        FROM base b
        {ressarcimento_join}
        ORDER BY b.chi_liquido DESC, b.ci_liquido DESC, COMP_TOTAL_PRODIST DESC
        """,
    ).fetchall()

    official_regionals = {"CSL", "LES", "NRT", "NRO", "OES"}
    records = [
        {
            "regional": _clean(row[0]),
            "regional_exibicao": _display(_clean(row[0]), _static_region_name(_clean(row[0]))),
            "ocorrencias": _number(row[1]),
            "interrupcoes": _number(row[2]),
            "ucs": _number(row[3]),
            "conjuntos": _number(row[4]),
            "ci_liquido": _number(row[5]),
            "chi_liquido": _number(row[6]),
            "duracao_maxima_h": _number(row[7]),
            "comp_total_prodist": _number(row[8]),
            "ucs_com_compensacao": _number(row[9]),
        }
        for row in rows
    ]
    regional_records = [record for record in records if record["regional"] in official_regionals]
    regional_records.sort(
        key=lambda record: (
            float(record.get("chi_liquido") or 0),
            float(record.get("ci_liquido") or 0),
            float(record.get("comp_total_prodist") or 0),
        ),
        reverse=True,
    )
    copel_record = {
        "regional": "COPEL",
        "regional_exibicao": _display("COPEL", _static_region_name("COPEL")),
        "ocorrencias": sum(float(record.get("ocorrencias") or 0) for record in regional_records),
        "interrupcoes": sum(float(record.get("interrupcoes") or 0) for record in regional_records),
        "ucs": sum(float(record.get("ucs") or 0) for record in regional_records),
        "conjuntos": sum(float(record.get("conjuntos") or 0) for record in regional_records),
        "ci_liquido": sum(float(record.get("ci_liquido") or 0) for record in regional_records),
        "chi_liquido": sum(float(record.get("chi_liquido") or 0) for record in regional_records),
        "duracao_maxima_h": max((float(record.get("duracao_maxima_h") or 0) for record in regional_records), default=0),
        "comp_total_prodist": sum(float(record.get("comp_total_prodist") or 0) for record in regional_records),
        "ucs_com_compensacao": sum(float(record.get("ucs_com_compensacao") or 0) for record in regional_records),
    }
    return [copel_record, *regional_records[: max(limite, len(official_regionals))]]


def _static_region_name(codigo: str) -> str:
    nomes = {
        "COPEL": "COPEL consolidado",
        "CSL": "Regional Centro-Sul",
        "LES": "Regional Leste",
        "NRT": "Regional Norte",
        "NRO": "Regional Noroeste",
        "OES": "Regional Oeste",
    }
    return nomes.get(codigo, "descrição não disponível")


def _ranking_conjunto(
    con: duckdb.DuckDBPyConnection,
    limite: int,
    conjuntos_ref: dict[str, dict[str, str]],
) -> list[dict[str, object]]:
    if not _table_exists(con, "gold_apuracao_uc"):
        return []

    extra_cte = ""
    extra_join = ""
    extra_select = """
            CAST(0 AS BIGINT) AS ocorrencias_longas,
            CAST(0 AS BIGINT) AS ocorrencias_curtas,
            CAST(0 AS DOUBLE) AS chi_nao_faturado,
            CAST(0 AS DOUBLE) AS ci_nao_faturado
    """
    if _table_exists(con, "gold_interrupcao_tratada") and _table_exists(con, "gold_uc_fatura"):
        extra_cte = """
        , tratada AS (
            SELECT
                COALESCE(NULLIF(TRIM(CAST(i.COD_CONJTO_ELET_ANEEL_INTRP AS VARCHAR)), ''), 'SEM_CONJUNTO') AS conjunto,
                COALESCE(NULLIF(TRIM(CAST(i.NUM_OCORRENCIA_ADMS AS VARCHAR)), ''), 'SEM_OCORRENCIA') AS ocorrencia,
                NULLIF(TRIM(CAST(i.NUM_UC_UCI AS VARCHAR)), '') AS uc,
                DATE_DIFF('second', i.DATA_HORA_INIC_INTRP, i.DATA_HORA_FIM_INTRP) / 3600.0 AS duracao_hora,
                CASE
                    WHEN COALESCE(NULLIF(TRIM(CAST(f.FATURADO AS VARCHAR)), ''), 'N') = 'S' THEN 1
                    ELSE 0
                END AS faturado
            FROM gold_interrupcao_tratada i
            LEFT JOIN gold_uc_fatura f
              ON TRIM(CAST(f.UC AS VARCHAR)) = TRIM(CAST(i.NUM_UC_UCI AS VARCHAR))
            WHERE i.DATA_HORA_INIC_INTRP IS NOT NULL
              AND i.DATA_HORA_FIM_INTRP IS NOT NULL
              AND i.DATA_HORA_FIM_INTRP >= i.DATA_HORA_INIC_INTRP
        ),
        extra AS (
            SELECT
                conjunto,
                COUNT(DISTINCT CASE WHEN duracao_hora >= (3.0 / 60.0) THEN ocorrencia END) AS ocorrencias_longas,
                COUNT(DISTINCT CASE WHEN duracao_hora < (3.0 / 60.0) THEN ocorrencia END) AS ocorrencias_curtas,
                SUM(CASE WHEN faturado = 0 AND duracao_hora >= (3.0 / 60.0) THEN duracao_hora ELSE 0 END) AS chi_nao_faturado,
                SUM(CASE WHEN faturado = 0 AND duracao_hora >= (3.0 / 60.0) THEN 1 ELSE 0 END) AS ci_nao_faturado
            FROM tratada
            GROUP BY conjunto
        )
        """
        extra_join = "LEFT JOIN extra e ON e.conjunto = b.conjunto"
        extra_select = """
            COALESCE(e.ocorrencias_longas, 0) AS ocorrencias_longas,
            COALESCE(e.ocorrencias_curtas, 0) AS ocorrencias_curtas,
            COALESCE(e.chi_nao_faturado, 0) AS chi_nao_faturado,
            COALESCE(e.ci_nao_faturado, 0) AS ci_nao_faturado
        """

    rows = con.execute(
        f"""
        WITH base AS (
            SELECT
                COALESCE(NULLIF(TRIM(CAST(REGIONAL AS VARCHAR)), ''), 'SEM_REGIONAL') AS regional,
                COALESCE(NULLIF(TRIM(CAST(COD_CONJTO_ELET_ANEEL_INTRP AS VARCHAR)), ''), 'SEM_CONJUNTO') AS conjunto,
                COUNT(DISTINCT NUM_OCORRENCIA_ADMS) AS ocorrencias,
                COUNT(DISTINCT NUM_SEQ_INTRP) AS interrupcoes,
                COUNT(DISTINCT NUM_UC_UCI) AS ucs,
                SUM(COALESCE(CI_LIQUIDO, 0)) AS ci_liquido,
                SUM(COALESCE(CHI_LIQUIDO, 0)) AS chi_liquido,
                SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '1' THEN COALESCE(CI_BRUTO, 0) ELSE 0 END) AS ci_expurgo_dia_critico,
                SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '1' THEN COALESCE(CHI_BRUTO, 0) ELSE 0 END) AS chi_expurgo_dia_critico,
                SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) IN ('5', '6') THEN COALESCE(CI_BRUTO, 0) ELSE 0 END) AS ci_expurgo_ise,
                SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) IN ('5', '6') THEN COALESCE(CHI_BRUTO, 0) ELSE 0 END) AS chi_expurgo_ise,
                MAX(COALESCE(DURACAO_HORA, 0)) AS duracao_maxima_h
            FROM gold_apuracao_uc
            GROUP BY 1, 2
        )
        {extra_cte}
        SELECT
            b.regional,
            b.conjunto,
            b.ocorrencias,
            b.interrupcoes,
            b.ucs,
            b.ci_liquido,
            b.chi_liquido,
            b.chi_expurgo_dia_critico,
            b.ci_expurgo_dia_critico,
            b.chi_expurgo_ise,
            b.ci_expurgo_ise,
            {extra_select},
            b.duracao_maxima_h
        FROM base b
        {extra_join}
        ORDER BY b.chi_liquido DESC, b.ci_liquido DESC
        LIMIT ?
        """,
        [limite],
    ).fetchall()

    return [
        {
            "regional": _clean(row[0]),
            "regional_exibicao": _display(_clean(row[0]), _static_region_name(_clean(row[0]))),
            "conjunto": _clean(row[1]),
            "conjunto_nome": conjuntos_ref.get(_clean(row[1]), {}).get("nome", ""),
            "conjunto_exibicao": _display(_clean(row[1]), conjuntos_ref.get(_clean(row[1]), {}).get("nome", "")),
            "ocorrencias": _number(row[2]),
            "interrupcoes": _number(row[3]),
            "ucs": _number(row[4]),
            "ci_liquido": _number(row[5]),
            "chi_liquido": _number(row[6]),
            "chi_expurgo_dia_critico": _number(row[7]),
            "ci_expurgo_dia_critico": _number(row[8]),
            "chi_expurgo_ise": _number(row[9]),
            "ci_expurgo_ise": _number(row[10]),
            "ocorrencias_longas": _number(row[11]),
            "ocorrencias_curtas": _number(row[12]),
            "chi_nao_faturado": _number(row[13]),
            "ci_nao_faturado": _number(row[14]),
            "duracao_maxima_h": _number(row[15]),
            "status_nome": "ativo" if conjuntos_ref.get(_clean(row[1]), {}).get("nome") else "nome_pendente",
        }
        for row in rows
    ]


def _denominador_copel(con: duckdb.DuckDBPyConnection) -> float:
    if not _table_exists(con, "gold_consumidores"):
        return 0.0
    return _number(
        con.execute(
            """
            SELECT SUM(COALESCE(TRY_CAST(UC_FATURADA AS DOUBLE), 0))
            FROM gold_consumidores
            WHERE REGIONAL_TOTAL = 'COPEL'
            """
        ).fetchone()[0]
    )


def _component_cause_lookup(con: duckdb.DuckDBPyConnection) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {"grupo": {}, "componente": {}, "causa": {}}
    if not _table_exists(con, "gold_iqs_referencia_componente_causa"):
        return lookup

    rows = con.execute(
        """
        SELECT DISTINCT
            COD_GRUPO_GCR,
            DESC_GRUPO_GCR,
            COD_COMP,
            DESC_COMP,
            COD_CAUSA,
            DESC_CAUSA
        FROM gold_iqs_referencia_componente_causa
        """
    ).fetchall()
    for grupo, grupo_nome, componente, componente_nome, causa, causa_nome in rows:
        grupo_codigo = _clean(grupo)
        componente_codigo = _clean(componente)
        causa_codigo = _clean(causa)
        if grupo_codigo and _clean(grupo_nome):
            lookup["grupo"][grupo_codigo] = _clean(grupo_nome)
        if componente_codigo and _clean(componente_nome):
            lookup["componente"][componente_codigo] = _clean(componente_nome)
        if componente_codigo and causa_codigo and _clean(causa_nome):
            lookup["causa"][f"{componente_codigo}|{causa_codigo}"] = _clean(causa_nome)
        if causa_codigo and _clean(causa_nome):
            lookup["causa"].setdefault(causa_codigo, _clean(causa_nome))
    return lookup


def _detail_empty(user: AuthUser, conjunto: str, fontes: list[dict[str, object]], status: str = "fonte_indisponivel") -> dict[str, object]:
    return {
        "usuario": user.login,
        "anomes": ANOMES,
        "status": status,
        "nivel": "intermediario",
        "lente_padrao": "regulatoria",
        "conjunto": _clean(conjunto),
        "resumo": {},
        "alimentadores": [],
        "ocorrencias": [],
        "componentes_causas": [],
        "fontes": fontes,
        "regras": {
            "longa": "ocorrência com duração maior ou igual a 3 minutos",
            "ordenacao": "prioriza CHI líquido, CI líquido e volume de ocorrências",
            "exibicao": "sempre mostrar código e nome quando a referência estiver disponível",
        },
    }


def _detalhe_conjunto(
    user: AuthUser,
    conjunto: str,
    limite_alimentadores: int,
    limite_ocorrencias: int,
) -> dict[str, object]:
    conjunto_codigo = _clean(conjunto)
    conjuntos_ref, alimentadores_ref, hierarchy_fontes = _hierarchy_reference_maps()
    con, fonte_processado = _connect_processed_readonly()
    fontes = [*hierarchy_fontes, fonte_processado]
    if con is None:
        return _detail_empty(user, conjunto_codigo, fontes)

    try:
        if not _table_exists(con, "gold_apuracao_uc"):
            fontes.append({"fonte": "gold_apuracao_uc", "status": "ausente"})
            return _detail_empty(user, conjunto_codigo, fontes)

        fontes.append({"fonte": "gold_apuracao_uc", "status": "ok"})
        has_tratada = _table_exists(con, "gold_interrupcao_tratada")
        if has_tratada:
            fontes.append({"fonte": "gold_interrupcao_tratada", "status": "ok"})
        else:
            fontes.append({"fonte": "gold_interrupcao_tratada", "status": "ausente"})
        if _table_exists(con, "gold_iqs_referencia_componente_causa"):
            fontes.append({"fonte": "gold_iqs_referencia_componente_causa", "status": "ok"})

        denominador = _denominador_copel(con)
        if _table_exists(con, "gold_consumidores"):
            fontes.append({"fonte": "gold_consumidores", "status": "ok"})
        else:
            fontes.append({"fonte": "gold_consumidores", "status": "ausente"})

        resumo = _fetchone_dict(
            con,
            """
            SELECT
                COALESCE(NULLIF(TRIM(CAST(REGIONAL AS VARCHAR)), ''), 'SEM_REGIONAL') AS regional,
                COALESCE(NULLIF(TRIM(CAST(COD_CONJTO_ELET_ANEEL_INTRP AS VARCHAR)), ''), 'SEM_CONJUNTO') AS conjunto,
                COUNT(DISTINCT NUM_OCORRENCIA_ADMS) AS ocorrencias,
                COUNT(DISTINCT NUM_SEQ_INTRP) AS interrupcoes,
                COUNT(DISTINCT NUM_UC_UCI) AS ucs,
                SUM(COALESCE(CI_LIQUIDO, 0)) AS ci_liquido,
                SUM(COALESCE(CHI_LIQUIDO, 0)) AS chi_liquido,
                SUM(CASE WHEN COALESCE(DURACAO_HORA, 0) >= (3.0 / 60.0) THEN 1 ELSE 0 END) AS linhas_longas,
                SUM(CASE WHEN COALESCE(DURACAO_HORA, 0) < (3.0 / 60.0) THEN 1 ELSE 0 END) AS linhas_curtas,
                SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '1' THEN COALESCE(CI_BRUTO, 0) ELSE 0 END) AS ci_expurgo_dia_critico,
                SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '1' THEN COALESCE(CHI_BRUTO, 0) ELSE 0 END) AS chi_expurgo_dia_critico,
                SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) IN ('5', '6') THEN COALESCE(CI_BRUTO, 0) ELSE 0 END) AS ci_expurgo_ise,
                SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) IN ('5', '6') THEN COALESCE(CHI_BRUTO, 0) ELSE 0 END) AS chi_expurgo_ise,
                MAX(COALESCE(DURACAO_HORA, 0)) AS duracao_maxima_h
            FROM gold_apuracao_uc
            WHERE COALESCE(NULLIF(TRIM(CAST(COD_CONJTO_ELET_ANEEL_INTRP AS VARCHAR)), ''), 'SEM_CONJUNTO') = ?
            GROUP BY 1, 2
            """,
            [conjunto_codigo],
        )
        if not resumo:
            return {
                **_detail_empty(user, conjunto_codigo, fontes, status="sem_registros"),
                "mensagem": "Nenhum registro encontrado para o conjunto informado.",
            }

        resumo["conjunto_nome"] = conjuntos_ref.get(conjunto_codigo, {}).get("nome", "")
        resumo["conjunto_exibicao"] = _display(conjunto_codigo, str(resumo["conjunto_nome"]))
        resumo["regional_exibicao"] = _display(_clean(resumo.get("regional")), _static_region_name(_clean(resumo.get("regional"))))
        resumo["dec_liquido_estimado"] = _number(resumo.get("chi_liquido")) / denominador if denominador else 0
        resumo["fec_liquido_estimado"] = _number(resumo.get("ci_liquido")) / denominador if denominador else 0
        resumo["denominador_copel"] = denominador

        lookup = _component_cause_lookup(con)

        alimentadores: list[dict[str, object]] = []
        ocorrencias: list[dict[str, object]] = []
        componentes_causas: list[dict[str, object]] = []

        if has_tratada:
            alimentador_rows = con.execute(
                """
                WITH apuracao AS (
                    SELECT
                        COALESCE(NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), ''), 'SEM_OCORRENCIA') AS ocorrencia,
                        COALESCE(NULLIF(TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)), ''), 'SEM_SEQ') AS sequencia,
                        NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '') AS uc,
                        COALESCE(CI_LIQUIDO, 0) AS ci_liquido,
                        COALESCE(CHI_LIQUIDO, 0) AS chi_liquido,
                        COALESCE(DURACAO_HORA, 0) AS duracao_hora
                    FROM gold_apuracao_uc
                    WHERE COALESCE(NULLIF(TRIM(CAST(COD_CONJTO_ELET_ANEEL_INTRP AS VARCHAR)), ''), 'SEM_CONJUNTO') = ?
                ),
                mapa AS (
                    SELECT DISTINCT
                        COALESCE(NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), ''), 'SEM_OCORRENCIA') AS ocorrencia,
                        COALESCE(NULLIF(TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)), ''), 'SEM_SEQ') AS sequencia,
                        NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '') AS uc,
                        COALESCE(NULLIF(TRIM(CAST(ALIM_INTRP AS VARCHAR)), ''), 'SEM_ALIMENTADOR') AS alimentador
                    FROM gold_interrupcao_tratada
                    WHERE COALESCE(NULLIF(TRIM(CAST(COD_CONJTO_ELET_ANEEL_INTRP AS VARCHAR)), ''), 'SEM_CONJUNTO') = ?
                ),
                unido AS (
                    SELECT
                        COALESCE(m.alimentador, 'SEM_ALIMENTADOR') AS alimentador,
                        a.*
                    FROM apuracao a
                    LEFT JOIN mapa m
                      ON m.ocorrencia = a.ocorrencia
                     AND m.sequencia = a.sequencia
                     AND COALESCE(m.uc, '') = COALESCE(a.uc, '')
                )
                SELECT
                    alimentador,
                    COUNT(DISTINCT ocorrencia) AS ocorrencias,
                    COUNT(DISTINCT sequencia) AS interrupcoes,
                    COUNT(DISTINCT uc) AS ucs,
                    SUM(ci_liquido) AS ci_liquido,
                    SUM(chi_liquido) AS chi_liquido,
                    COUNT(DISTINCT CASE WHEN duracao_hora >= (3.0 / 60.0) THEN ocorrencia END) AS ocorrencias_longas,
                    COUNT(DISTINCT CASE WHEN duracao_hora < (3.0 / 60.0) THEN ocorrencia END) AS ocorrencias_curtas,
                    MAX(duracao_hora) AS duracao_maxima_h
                FROM unido
                GROUP BY 1
                ORDER BY chi_liquido DESC, ci_liquido DESC, ocorrencias DESC
                LIMIT ?
                """,
                [conjunto_codigo, conjunto_codigo, limite_alimentadores],
            ).fetchall()
            for row in alimentador_rows:
                alimentador_codigo = _clean(row[0])
                alimentador_ref = alimentadores_ref.get(alimentador_codigo, {})
                alimentadores.append(
                    {
                        "alimentador": alimentador_codigo,
                        "alimentador_nome": alimentador_ref.get("nome", ""),
                        "alimentador_exibicao": _display(alimentador_codigo, alimentador_ref.get("nome", "")),
                        "ocorrencias": _number(row[1]),
                        "interrupcoes": _number(row[2]),
                        "ucs": _number(row[3]),
                        "ci_liquido": _number(row[4]),
                        "chi_liquido": _number(row[5]),
                        "ocorrencias_longas": _number(row[6]),
                        "ocorrencias_curtas": _number(row[7]),
                        "duracao_maxima_h": _number(row[8]),
                        "status_nome": "ativo" if alimentador_ref.get("nome") else "nome_pendente",
                    }
                )

            ocorrencia_rows = con.execute(
                """
                WITH apuracao AS (
                    SELECT
                        COALESCE(NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), ''), 'SEM_OCORRENCIA') AS ocorrencia,
                        COALESCE(NULLIF(TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)), ''), 'SEM_SEQ') AS sequencia,
                        NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '') AS uc,
                        DATA_HORA_INIC_INTRP AS inicio,
                        DATA_HORA_FIM_INTRP AS fim,
                        COALESCE(CI_LIQUIDO, 0) AS ci_liquido,
                        COALESCE(CHI_LIQUIDO, 0) AS chi_liquido,
                        COALESCE(DURACAO_HORA, 0) AS duracao_hora,
                        NULLIF(TRIM(CAST(COD_COMP_INTRP AS VARCHAR)), '') AS componente,
                        NULLIF(TRIM(CAST(COD_CAUSA_INTRP AS VARCHAR)), '') AS causa
                    FROM gold_apuracao_uc
                    WHERE COALESCE(NULLIF(TRIM(CAST(COD_CONJTO_ELET_ANEEL_INTRP AS VARCHAR)), ''), 'SEM_CONJUNTO') = ?
                ),
                mapa AS (
                    SELECT DISTINCT
                        COALESCE(NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), ''), 'SEM_OCORRENCIA') AS ocorrencia,
                        COALESCE(NULLIF(TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)), ''), 'SEM_SEQ') AS sequencia,
                        NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '') AS uc,
                        COALESCE(NULLIF(TRIM(CAST(ALIM_INTRP AS VARCHAR)), ''), 'SEM_ALIMENTADOR') AS alimentador
                    FROM gold_interrupcao_tratada
                    WHERE COALESCE(NULLIF(TRIM(CAST(COD_CONJTO_ELET_ANEEL_INTRP AS VARCHAR)), ''), 'SEM_CONJUNTO') = ?
                ),
                unido AS (
                    SELECT
                        COALESCE(m.alimentador, 'SEM_ALIMENTADOR') AS alimentador,
                        a.*
                    FROM apuracao a
                    LEFT JOIN mapa m
                      ON m.ocorrencia = a.ocorrencia
                     AND m.sequencia = a.sequencia
                     AND COALESCE(m.uc, '') = COALESCE(a.uc, '')
                )
                SELECT
                    ocorrencia,
                    MIN(alimentador) AS alimentador,
                    MIN(inicio) AS inicio,
                    MAX(fim) AS fim,
                    COUNT(DISTINCT sequencia) AS interrupcoes,
                    COUNT(DISTINCT uc) AS ucs,
                    SUM(ci_liquido) AS ci_liquido,
                    SUM(chi_liquido) AS chi_liquido,
                    MAX(duracao_hora) AS duracao_maxima_h,
                    STRING_AGG(DISTINCT componente, ', ') AS componentes,
                    STRING_AGG(DISTINCT causa, ', ') AS causas
                FROM unido
                GROUP BY 1
                ORDER BY chi_liquido DESC, ci_liquido DESC, duracao_maxima_h DESC
                LIMIT ?
                """,
                [conjunto_codigo, conjunto_codigo, limite_ocorrencias],
            ).fetchall()
            for row in ocorrencia_rows:
                alimentador_codigo = _clean(row[1])
                alimentador_ref = alimentadores_ref.get(alimentador_codigo, {})
                ocorrencias.append(
                    {
                        "ocorrencia": _clean(row[0]),
                        "alimentador": alimentador_codigo,
                        "alimentador_nome": alimentador_ref.get("nome", ""),
                        "alimentador_exibicao": _display(alimentador_codigo, alimentador_ref.get("nome", "")),
                        "inicio": row[2],
                        "fim": row[3],
                        "interrupcoes": _number(row[4]),
                        "ucs": _number(row[5]),
                        "ci_liquido": _number(row[6]),
                        "chi_liquido": _number(row[7]),
                        "duracao_maxima_h": _number(row[8]),
                        "componentes": _clean(row[9]),
                        "causas": _clean(row[10]),
                    }
                )

            component_rows = con.execute(
                """
                WITH apuracao AS (
                    SELECT
                        COALESCE(NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), ''), 'SEM_OCORRENCIA') AS ocorrencia,
                        COALESCE(NULLIF(TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)), ''), 'SEM_SEQ') AS sequencia,
                        NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '') AS uc,
                        NULLIF(TRIM(CAST(COD_COMP_INTRP AS VARCHAR)), '') AS componente,
                        NULLIF(TRIM(CAST(COD_CAUSA_INTRP AS VARCHAR)), '') AS causa,
                        COALESCE(CI_LIQUIDO, 0) AS ci_liquido,
                        COALESCE(CHI_LIQUIDO, 0) AS chi_liquido
                    FROM gold_apuracao_uc
                    WHERE COALESCE(NULLIF(TRIM(CAST(COD_CONJTO_ELET_ANEEL_INTRP AS VARCHAR)), ''), 'SEM_CONJUNTO') = ?
                ),
                mapa AS (
                    SELECT DISTINCT
                        COALESCE(NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), ''), 'SEM_OCORRENCIA') AS ocorrencia,
                        COALESCE(NULLIF(TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)), ''), 'SEM_SEQ') AS sequencia,
                        NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '') AS uc,
                        NULLIF(TRIM(CAST(COD_GRUPO_COMP_INTRP AS VARCHAR)), '') AS grupo
                    FROM gold_interrupcao_tratada
                    WHERE COALESCE(NULLIF(TRIM(CAST(COD_CONJTO_ELET_ANEEL_INTRP AS VARCHAR)), ''), 'SEM_CONJUNTO') = ?
                ),
                unido AS (
                    SELECT
                        m.grupo,
                        a.*
                    FROM apuracao a
                    LEFT JOIN mapa m
                      ON m.ocorrencia = a.ocorrencia
                     AND m.sequencia = a.sequencia
                     AND COALESCE(m.uc, '') = COALESCE(a.uc, '')
                )
                SELECT
                    grupo,
                    componente,
                    causa,
                    COUNT(DISTINCT ocorrencia) AS ocorrencias,
                    COUNT(DISTINCT uc) AS ucs,
                    SUM(ci_liquido) AS ci_liquido,
                    SUM(chi_liquido) AS chi_liquido
                FROM unido
                GROUP BY 1, 2, 3
                ORDER BY chi_liquido DESC, ci_liquido DESC, ocorrencias DESC
                LIMIT 20
                """,
                [conjunto_codigo, conjunto_codigo],
            ).fetchall()
            for row in component_rows:
                grupo_codigo = _clean(row[0])
                componente_codigo = _clean(row[1])
                causa_codigo = _clean(row[2])
                componentes_causas.append(
                    {
                        "grupo": grupo_codigo,
                        "grupo_nome": lookup["grupo"].get(grupo_codigo, ""),
                        "grupo_exibicao": _display(grupo_codigo, lookup["grupo"].get(grupo_codigo, "")) if grupo_codigo else "—",
                        "componente": componente_codigo,
                        "componente_nome": lookup["componente"].get(componente_codigo, ""),
                        "componente_exibicao": _display(componente_codigo, lookup["componente"].get(componente_codigo, "")) if componente_codigo else "—",
                        "causa": causa_codigo,
                        "causa_nome": lookup["causa"].get(f"{componente_codigo}|{causa_codigo}", lookup["causa"].get(causa_codigo, "")),
                        "causa_exibicao": _display(causa_codigo, lookup["causa"].get(f"{componente_codigo}|{causa_codigo}", lookup["causa"].get(causa_codigo, ""))) if causa_codigo else "—",
                        "ocorrencias": _number(row[3]),
                        "ucs": _number(row[4]),
                        "ci_liquido": _number(row[5]),
                        "chi_liquido": _number(row[6]),
                    }
                )

        return {
            "usuario": user.login,
            "anomes": ANOMES,
            "status": "ok",
            "nivel": "intermediario",
            "lente_padrao": "regulatoria",
            "conjunto": conjunto_codigo,
            "resumo": resumo,
            "alimentadores": alimentadores,
            "ocorrencias": ocorrencias,
            "componentes_causas": componentes_causas,
            "fontes": fontes,
            "regras": {
                "longa": "ocorrência com duração maior ou igual a 3 minutos",
                "dec_fec": "estimativa macro: CHI/CI líquido do conjunto dividido pela soma UC_FATURADA COPEL",
                "ordenacao_alimentadores": "CHI líquido, CI líquido e ocorrências",
                "ordenacao_ocorrencias": "CHI líquido, CI líquido e duração máxima",
                "codigo_descricao": "conjunto/alimentador usam referências locais em data/input; componente/causa usa referência IQS quando disponível",
            },
        }
    except (duckdb.Error, OSError) as exc:
        fontes.append({"fonte": "detalhe_conjunto", "status": "erro", "erro": str(exc).splitlines()[0]})
        return _detail_empty(user, conjunto_codigo, fontes, status="erro")
    finally:
        con.close()


def _detail_alimentador_empty(
    user: AuthUser,
    alimentador: str,
    fontes: list[dict[str, object]],
    status: str = "fonte_indisponivel",
) -> dict[str, object]:
    return {
        "usuario": user.login,
        "anomes": ANOMES,
        "status": status,
        "nivel": "intermediario",
        "lente_padrao": "cliente_operacao",
        "alimentador": _clean(alimentador),
        "resumo": {},
        "dias": [],
        "ocorrencias": [],
        "suspeitas_ra": [],
        "fontes": fontes,
        "regras": {
            "fic_recorrente": "UC com 3 ou mais FIC no mesmo alimentador e dia",
            "baixa_reclamacao": "esperado mínimo de 1 reclamação a cada 250 UCs com FIC recorrente",
            "longa": "ocorrência com duração maior ou igual a 3 minutos",
        },
    }


def _detalhe_alimentador(
    user: AuthUser,
    alimentador: str,
    conjunto: str | None,
    limite_ocorrencias: int,
) -> dict[str, object]:
    alimentador_codigo = _clean(alimentador)
    conjunto_codigo = _clean(conjunto)
    conjuntos_ref, alimentadores_ref, hierarchy_fontes = _hierarchy_reference_maps()
    con, fonte_processado = _connect_processed_readonly()
    fontes = [*hierarchy_fontes, fonte_processado]
    if con is None:
        return _detail_alimentador_empty(user, alimentador_codigo, fontes)

    try:
        if not _table_exists(con, "gold_interrupcao_tratada") or not _table_exists(con, "gold_apuracao_uc"):
            fontes.append({"fonte": "gold_interrupcao_tratada/gold_apuracao_uc", "status": "ausente"})
            return _detail_alimentador_empty(user, alimentador_codigo, fontes)

        fontes.append({"fonte": "gold_interrupcao_tratada", "status": "ok"})
        fontes.append({"fonte": "gold_apuracao_uc", "status": "ok"})
        has_reclamacao = _table_exists(con, "gold_reclamacao_ocorrencia_resumo")
        fontes.append({"fonte": "gold_reclamacao_ocorrencia_resumo", "status": "ok" if has_reclamacao else "ausente"})
        servicos_path = Path("data") / "raw" / f"adms_servicos_raw_{ANOMES}.duckdb"
        has_servicos = servicos_path.exists()
        if has_servicos:
            servicos_sql_path = str(servicos_path).replace("\\", "/").replace("'", "''")
            con.execute(f"ATTACH '{servicos_sql_path}' AS serv_raw (READ_ONLY)")
        fontes.append({"fonte": str(servicos_path).replace("\\", "/"), "status": "ok" if has_servicos else "ausente"})

        conjunto_filter = (
            "AND COALESCE(NULLIF(TRIM(CAST(COD_CONJTO_ELET_ANEEL_INTRP AS VARCHAR)), ''), 'SEM_CONJUNTO') = ?"
            if conjunto_codigo
            else ""
        )
        params = [alimentador_codigo, *( [conjunto_codigo] if conjunto_codigo else [] )]
        reclamacao_cte = ""
        reclamacao_join = ""
        reclamacao_select = "CAST(0 AS DOUBLE) AS reclamacoes, CAST(0 AS DOUBLE) AS ucs_reclamantes"
        if has_reclamacao:
            reclamacao_cte = """
            , reclamacoes AS (
                SELECT
                    TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)) AS ocorrencia,
                    SUM(COALESCE(QTD_RECLAMACOES, 0)) AS reclamacoes,
                    SUM(COALESCE(QTD_UCS_RECLAMANTES, 0)) AS ucs_reclamantes
                FROM gold_reclamacao_ocorrencia_resumo
                WHERE NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '') IS NOT NULL
                GROUP BY 1
            )
            """
            reclamacao_join = "LEFT JOIN reclamacoes r ON r.ocorrencia = b.ocorrencia"
            reclamacao_select = "COALESCE(r.reclamacoes, 0) AS reclamacoes, COALESCE(r.ucs_reclamantes, 0) AS ucs_reclamantes"

        servicos_cte = """
            , servico_alim AS (
                SELECT
                    CAST(0 AS DOUBLE) AS servicos,
                    CAST(0 AS DOUBLE) AS reclamacoes_servico,
                    CAST(0 AS DOUBLE) AS interrupcoes_com_servico,
                    CAST(0 AS DOUBLE) AS interrupcoes_sem_servico
            )
        """
        if has_servicos:
            servicos_cte = """
            , servicos AS (
                SELECT
                    TRIM(CAST(PID_INTRP_SRVE AS VARCHAR)) AS sequencia,
                    COUNT(DISTINCT NULLIF(TRIM(CAST(NUM_SEQ_SERV AS VARCHAR)), '')) AS servicos,
                    SUM(COALESCE(TRY_CAST(QTDE_RECLAM_SRVE AS DOUBLE), 0)) AS reclamacoes_servico
                FROM serv_raw.raw_adms_servicos
                WHERE NULLIF(TRIM(CAST(PID_INTRP_SRVE AS VARCHAR)), '') IS NOT NULL
                GROUP BY 1
            ),
            servico_alim AS (
                SELECT
                    SUM(COALESCE(s.servicos, 0)) AS servicos,
                    SUM(COALESCE(s.reclamacoes_servico, 0)) AS reclamacoes_servico,
                    COUNT(DISTINCT CASE WHEN COALESCE(s.servicos, 0) > 0 THEN b.sequencia END) AS interrupcoes_com_servico,
                    COUNT(DISTINCT CASE WHEN COALESCE(s.servicos, 0) <= 0 THEN b.sequencia END) AS interrupcoes_sem_servico
                FROM (SELECT DISTINCT sequencia FROM base_intrp) b
                LEFT JOIN servicos s
                  ON b.sequencia = s.sequencia
            )
            """

        resumo = _fetchone_dict(
            con,
            f"""
            WITH base_intrp AS (
                SELECT
                    COALESCE(NULLIF(TRIM(CAST(SIGLA_REGIONAL AS VARCHAR)), ''), 'SEM_REGIONAL') AS regional,
                    COALESCE(NULLIF(TRIM(CAST(COD_CONJTO_ELET_ANEEL_INTRP AS VARCHAR)), ''), 'SEM_CONJUNTO') AS conjunto,
                    COALESCE(NULLIF(TRIM(CAST(ALIM_INTRP AS VARCHAR)), ''), 'SEM_ALIMENTADOR') AS alimentador,
                    COALESCE(NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), ''), 'SEM_OCORRENCIA') AS ocorrencia,
                    COALESCE(NULLIF(TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)), ''), 'SEM_SEQ') AS sequencia,
                    MIN(DATA_HORA_INIC_INTRP) AS inicio,
                    MAX(DATA_HORA_FIM_INTRP) AS fim,
                    MAX(NULLIF(TRIM(CAST(TIPO_CHV_INTRP AS VARCHAR)), '')) AS tipo_chave,
                    MAX(NULLIF(TRIM(CAST(NUM_OPER_CHV_INTRP AS VARCHAR)), '')) AS equipamento,
                    COUNT(DISTINCT NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '')) AS ucs_operacionais,
                    DATE_DIFF('second', MIN(DATA_HORA_INIC_INTRP), MAX(DATA_HORA_FIM_INTRP)) / 3600.0 AS duracao_hora
                FROM gold_interrupcao_tratada
                WHERE COALESCE(NULLIF(TRIM(CAST(ALIM_INTRP AS VARCHAR)), ''), 'SEM_ALIMENTADOR') = ?
                {conjunto_filter}
                GROUP BY 1, 2, 3, 4, 5
            ),
            seqs AS (
                SELECT DISTINCT sequencia FROM base_intrp
            ),
            apuracao AS (
                SELECT
                    COUNT(DISTINCT NUM_UC_UCI) AS ucs_apuraveis,
                    SUM(COALESCE(CI_LIQUIDO, 0)) AS ci_liquido,
                    SUM(COALESCE(CHI_LIQUIDO, 0)) AS chi_liquido
                FROM gold_apuracao_uc
                WHERE TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)) IN (SELECT sequencia FROM seqs)
            )
            {reclamacao_cte},
            reclamacao_alim AS (
                SELECT
                    SUM(reclamacoes) AS reclamacoes,
                    SUM(ucs_reclamantes) AS ucs_reclamantes
                FROM (
                    SELECT DISTINCT b.ocorrencia, {reclamacao_select}
                    FROM base_intrp b
                    {reclamacao_join}
                )
            )
            {servicos_cte}
            SELECT
                MIN(regional) AS regional,
                MIN(conjunto) AS conjunto,
                MIN(alimentador) AS alimentador,
                COUNT(DISTINCT ocorrencia) AS ocorrencias,
                COUNT(DISTINCT sequencia) AS interrupcoes,
                SUM(ucs_operacionais) AS ucs_operacionais,
                COALESCE(MAX(a.ucs_apuraveis), 0) AS ucs_apuraveis,
                COALESCE(MAX(a.ci_liquido), 0) AS ci_liquido,
                COALESCE(MAX(a.chi_liquido), 0) AS chi_liquido,
                COUNT(DISTINCT CASE WHEN duracao_hora >= (3.0 / 60.0) THEN ocorrencia END) AS ocorrencias_longas,
                COUNT(DISTINCT CASE WHEN duracao_hora < (3.0 / 60.0) THEN ocorrencia END) AS ocorrencias_curtas,
                COUNT(DISTINCT CASE WHEN UPPER(tipo_chave) = 'RA' THEN sequencia END) AS interrupcoes_ra,
                COUNT(DISTINCT CASE WHEN UPPER(tipo_chave) = 'RA' THEN equipamento END) AS equipamentos_ra,
                MAX(duracao_hora) AS duracao_maxima_h,
                COALESCE(MAX(r.reclamacoes), 0) AS reclamacoes,
                COALESCE(MAX(r.ucs_reclamantes), 0) AS ucs_reclamantes,
                COALESCE(MAX(s.servicos), 0) AS servicos,
                COALESCE(MAX(s.reclamacoes_servico), 0) AS reclamacoes_servico,
                COALESCE(MAX(s.interrupcoes_com_servico), 0) AS interrupcoes_com_servico,
                COALESCE(MAX(s.interrupcoes_sem_servico), 0) AS interrupcoes_sem_servico
            FROM base_intrp
            CROSS JOIN apuracao a
            CROSS JOIN reclamacao_alim r
            CROSS JOIN servico_alim s
            """,
            params,
        )
        if not resumo or not resumo.get("alimentador"):
            return {
                **_detail_alimentador_empty(user, alimentador_codigo, fontes, status="sem_registros"),
                "mensagem": "Nenhum registro encontrado para o alimentador informado.",
            }

        alimentador_ref = alimentadores_ref.get(alimentador_codigo, {})
        conjunto_resumo = _clean(resumo.get("conjunto"))
        resumo["alimentador_nome"] = alimentador_ref.get("nome", "")
        resumo["alimentador_exibicao"] = _display(alimentador_codigo, alimentador_ref.get("nome", ""))
        resumo["conjunto_nome"] = conjuntos_ref.get(conjunto_resumo, {}).get("nome", "")
        resumo["conjunto_exibicao"] = _display(conjunto_resumo, conjuntos_ref.get(conjunto_resumo, {}).get("nome", ""))
        resumo["regional_exibicao"] = _display(_clean(resumo.get("regional")), _static_region_name(_clean(resumo.get("regional"))))

        servicos_base_cte = """
            , servicos AS (
                SELECT
                    CAST(NULL AS VARCHAR) AS sequencia,
                    CAST(0 AS DOUBLE) AS servicos,
                    CAST(0 AS DOUBLE) AS reclamacoes_servico
                WHERE FALSE
            )
        """
        if has_servicos:
            servicos_base_cte = """
            , servicos AS (
                SELECT
                    TRIM(CAST(PID_INTRP_SRVE AS VARCHAR)) AS sequencia,
                    COUNT(DISTINCT NULLIF(TRIM(CAST(NUM_SEQ_SERV AS VARCHAR)), '')) AS servicos,
                    SUM(COALESCE(TRY_CAST(QTDE_RECLAM_SRVE AS DOUBLE), 0)) AS reclamacoes_servico
                FROM serv_raw.raw_adms_servicos
                WHERE NULLIF(TRIM(CAST(PID_INTRP_SRVE AS VARCHAR)), '') IS NOT NULL
                GROUP BY 1
            )
            """

        dias = _fetchall_dicts(
            con,
            f"""
            WITH base_intrp AS (
                SELECT
                    COALESCE(NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), ''), 'SEM_OCORRENCIA') AS ocorrencia,
                    COALESCE(NULLIF(TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)), ''), 'SEM_SEQ') AS sequencia,
                    DATE(MIN(DATA_HORA_INIC_INTRP)) AS dia,
                    MAX(NULLIF(TRIM(CAST(TIPO_CHV_INTRP AS VARCHAR)), '')) AS tipo_chave,
                    COUNT(DISTINCT NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '')) AS ucs_operacionais,
                    DATE_DIFF('second', MIN(DATA_HORA_INIC_INTRP), MAX(DATA_HORA_FIM_INTRP)) / 3600.0 AS duracao_hora
                FROM gold_interrupcao_tratada
                WHERE COALESCE(NULLIF(TRIM(CAST(ALIM_INTRP AS VARCHAR)), ''), 'SEM_ALIMENTADOR') = ?
                {conjunto_filter}
                GROUP BY 1, 2
            ),
            fic_uc AS (
                SELECT
                    b.dia,
                    TRIM(CAST(a.NUM_UC_UCI AS VARCHAR)) AS uc,
                    COUNT(DISTINCT b.sequencia) AS fic_dia
                FROM gold_apuracao_uc a
                JOIN base_intrp b
                  ON TRIM(CAST(a.NUM_SEQ_INTRP AS VARCHAR)) = b.sequencia
                WHERE NULLIF(TRIM(CAST(a.NUM_UC_UCI AS VARCHAR)), '') IS NOT NULL
                GROUP BY 1, 2
            )
            {servicos_base_cte}
            SELECT
                b.dia,
                COUNT(DISTINCT b.ocorrencia) AS ocorrencias,
                COUNT(DISTINCT b.sequencia) AS interrupcoes,
                COUNT(DISTINCT CASE WHEN UPPER(b.tipo_chave) = 'RA' THEN b.sequencia END) AS interrupcoes_ra,
                COUNT(DISTINCT CASE WHEN b.duracao_hora >= (3.0 / 60.0) THEN b.ocorrencia END) AS ocorrencias_longas,
                COUNT(DISTINCT CASE WHEN b.duracao_hora < (3.0 / 60.0) THEN b.ocorrencia END) AS ocorrencias_curtas,
                SUM(b.ucs_operacionais) AS ucs_operacionais,
                COALESCE(MAX(f.ucs_fic_recorrente), 0) AS ucs_fic_recorrente,
                COALESCE(MAX(s.servicos), 0) AS servicos,
                COALESCE(MAX(s.reclamacoes_servico), 0) AS reclamacoes_servico,
                COALESCE(MAX(s.interrupcoes_sem_servico), 0) AS interrupcoes_sem_servico
            FROM base_intrp b
            LEFT JOIN (
                SELECT dia, COUNT(DISTINCT uc) AS ucs_fic_recorrente
                FROM fic_uc
                WHERE fic_dia >= 3
                GROUP BY 1
            ) f
              ON b.dia = f.dia
            LEFT JOIN (
                SELECT
                    b.dia,
                    SUM(COALESCE(s.servicos, 0)) AS servicos,
                    SUM(COALESCE(s.reclamacoes_servico, 0)) AS reclamacoes_servico,
                    COUNT(DISTINCT CASE WHEN COALESCE(s.servicos, 0) <= 0 THEN b.sequencia END) AS interrupcoes_sem_servico
                FROM (SELECT DISTINCT dia, sequencia FROM base_intrp) b
                LEFT JOIN servicos s
                  ON b.sequencia = s.sequencia
                GROUP BY 1
            ) s
              ON b.dia = s.dia
            GROUP BY 1
            ORDER BY ocorrencias DESC, interrupcoes_ra DESC, dia
            LIMIT 30
            """,
            params,
        )

        ocorrencias = _fetchall_dicts(
            con,
            f"""
            WITH base_intrp AS (
                SELECT
                    COALESCE(NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), ''), 'SEM_OCORRENCIA') AS ocorrencia,
                    COALESCE(NULLIF(TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)), ''), 'SEM_SEQ') AS sequencia,
                    MIN(DATA_HORA_INIC_INTRP) AS inicio,
                    MAX(DATA_HORA_FIM_INTRP) AS fim,
                    MAX(NULLIF(TRIM(CAST(TIPO_CHV_INTRP AS VARCHAR)), '')) AS tipo_chave,
                    MAX(NULLIF(TRIM(CAST(NUM_OPER_CHV_INTRP AS VARCHAR)), '')) AS equipamento,
                    COUNT(DISTINCT NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '')) AS ucs_operacionais,
                    DATE_DIFF('second', MIN(DATA_HORA_INIC_INTRP), MAX(DATA_HORA_FIM_INTRP)) / 3600.0 AS duracao_hora
                FROM gold_interrupcao_tratada
                WHERE COALESCE(NULLIF(TRIM(CAST(ALIM_INTRP AS VARCHAR)), ''), 'SEM_ALIMENTADOR') = ?
                {conjunto_filter}
                GROUP BY 1, 2
            ),
            seqs AS (
                SELECT DISTINCT sequencia FROM base_intrp
            ),
            apuracao AS (
                SELECT
                    TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)) AS sequencia,
                    SUM(COALESCE(CI_LIQUIDO, 0)) AS ci_liquido,
                    SUM(COALESCE(CHI_LIQUIDO, 0)) AS chi_liquido,
                    COUNT(DISTINCT NUM_UC_UCI) AS ucs_apuraveis
                FROM gold_apuracao_uc
                WHERE TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)) IN (SELECT sequencia FROM seqs)
                GROUP BY 1
            )
            {servicos_base_cte}
            SELECT
                b.ocorrencia,
                MIN(b.inicio) AS inicio,
                MAX(b.fim) AS fim,
                COUNT(DISTINCT b.sequencia) AS interrupcoes,
                COUNT(DISTINCT CASE WHEN UPPER(b.tipo_chave) = 'RA' THEN b.sequencia END) AS interrupcoes_ra,
                STRING_AGG(DISTINCT b.equipamento, ', ') AS equipamentos,
                SUM(b.ucs_operacionais) AS ucs_operacionais,
                SUM(COALESCE(a.ucs_apuraveis, 0)) AS ucs_apuraveis,
                SUM(COALESCE(a.ci_liquido, 0)) AS ci_liquido,
                SUM(COALESCE(a.chi_liquido, 0)) AS chi_liquido,
                MAX(b.duracao_hora) AS duracao_maxima_h,
                COALESCE(MAX(s.servicos), 0) AS servicos,
                COALESCE(MAX(s.reclamacoes_servico), 0) AS reclamacoes_servico,
                COALESCE(MAX(s.interrupcoes_sem_servico), 0) AS interrupcoes_sem_servico
            FROM base_intrp b
            LEFT JOIN apuracao a
              ON b.sequencia = a.sequencia
            LEFT JOIN (
                SELECT
                    b.ocorrencia,
                    SUM(COALESCE(s.servicos, 0)) AS servicos,
                    SUM(COALESCE(s.reclamacoes_servico, 0)) AS reclamacoes_servico,
                    COUNT(DISTINCT CASE WHEN COALESCE(s.servicos, 0) <= 0 THEN b.sequencia END) AS interrupcoes_sem_servico
                FROM (SELECT DISTINCT ocorrencia, sequencia FROM base_intrp) b
                LEFT JOIN servicos s
                  ON b.sequencia = s.sequencia
                GROUP BY 1
            ) s
              ON b.ocorrencia = s.ocorrencia
            GROUP BY 1
            ORDER BY chi_liquido DESC, ci_liquido DESC, duracao_maxima_h DESC
            LIMIT ?
            """,
            [*params, limite_ocorrencias],
        )

        suspeitas_ra = _suspeitas_ra_records(conjunto=conjunto_resumo, alimentador=alimentador_codigo, limite=10)

        return {
            "usuario": user.login,
            "anomes": ANOMES,
            "status": "ok",
            "nivel": "intermediario",
            "lente_padrao": "cliente_operacao",
            "alimentador": alimentador_codigo,
            "resumo": api_row(resumo),
            "dias": api_rows(dias),
            "ocorrencias": api_rows(ocorrencias),
            "suspeitas_ra": suspeitas_ra,
            "fontes": fontes,
            "regras": {
                "fic_recorrente": "UC com 3 ou mais FIC no mesmo alimentador e dia",
                "baixa_reclamacao": "esperado mínimo de 1 reclamação a cada 250 UCs com FIC recorrente",
                "longa": "ocorrência com duração maior ou igual a 3 minutos",
                "servicos": "contagem de serviços fica pendente até acoplar raw adms_servicos ao processado",
            },
        }
    except (duckdb.Error, OSError) as exc:
        fontes.append({"fonte": "detalhe_alimentador", "status": "erro", "erro": str(exc).splitlines()[0]})
        return _detail_alimentador_empty(user, alimentador_codigo, fontes, status="erro")
    finally:
        con.close()


def _suspeitas_ra_records(
    *,
    conjunto: str | None = None,
    alimentador: str | None = None,
    limite: int = 20,
) -> list[dict[str, Any]]:
    _, resumo = _cached_suspeita_falha_ra(ANOMES)
    if resumo.empty:
        return []
    filtered = resumo
    if conjunto:
        filtered = filtered[filtered["CONJUNTO"].astype(str).str.strip() == _clean(conjunto)]
    if alimentador:
        filtered = filtered[filtered["ALIM_INTRP"].astype(str).str.strip() == _clean(alimentador)]
    return _df_records(filtered, limite)


def _painel_suspeitas_ra(user: AuthUser, limite: int) -> dict[str, object]:
    try:
        detalhe, resumo = _cached_suspeita_falha_ra(ANOMES)
    except Exception as exc:
        return {
            "usuario": user.login,
            "anomes": ANOMES,
            "status": "erro",
            "resumo": {},
            "items": [],
            "detalhe_amostra": [],
            "erro": str(exc).splitlines()[0],
            "regras": {
                "zero_reclamacao": "nível alto quando equipamento/dia não tem reclamação e gera compensação FIC",
                "baixa_reclamacao": "nível crítico quando há FIC recorrente no alimentador/dia e menos de 1 reclamação a cada 250 consumidores recorrentes",
            },
        }

    items = _df_records(resumo, limite)
    return {
        "usuario": user.login,
        "anomes": ANOMES,
        "status": "ok",
        "resumo": {
            "equipamentos_dia": len(resumo),
            "ocorrencias_detalhadas": len(detalhe),
            "comp_fic_estimado": _number(resumo["COMP_FIC_ESTIMADA"].sum()) if not resumo.empty else 0,
            "comp_total_estimado": _number(resumo["COMP_TOTAL_ESTIMADA"].sum()) if not resumo.empty else 0,
            "ci_liquido": _number(resumo["CI_LIQUIDO_TOTAL"].sum()) if not resumo.empty else 0,
            "chi_liquido": _number(resumo["CHI_LIQUIDO_TOTAL"].sum()) if not resumo.empty else 0,
            "zero_reclamacao": int(resumo["SINAL_ZERO_RECLAMACAO_EQUIPAMENTO"].sum()) if not resumo.empty else 0,
            "baixa_reclamacao": int(resumo["SINAL_BAIXA_RECLAMACAO_ALIM_DIA"].sum()) if not resumo.empty else 0,
            "servicos": _number(resumo["QTD_SERVICOS_TOTAL"].sum()) if not resumo.empty and "QTD_SERVICOS_TOTAL" in resumo else 0,
            "interrupcoes_sem_servico": _number(resumo["QTD_INTERRUPCOES_SEM_SERVICO"].sum()) if not resumo.empty and "QTD_INTERRUPCOES_SEM_SERVICO" in resumo else 0,
            "reclamacoes_servico": _number(resumo["QTD_RECLAMACOES_SERVICO_TOTAL"].sum()) if not resumo.empty and "QTD_RECLAMACOES_SERVICO_TOTAL" in resumo else 0,
        },
        "items": items,
        "detalhe_amostra": _df_records(detalhe, min(limite, 50)),
        "regras": {
            "zero_reclamacao": "nível alto quando equipamento/dia não tem reclamação e gera compensação FIC",
            "baixa_reclamacao": "nível crítico quando há FIC recorrente no alimentador/dia e menos de 1 reclamação a cada 250 consumidores recorrentes",
            "score": "ocorrências RA, CI/FIC, compensação FIC, baixa reclamação e janela operacional",
            "decisao": "gera suspeita e fila técnica; não altera IQS automaticamente",
        },
    }


def _validacao_iqs_governada(user: AuthUser) -> dict[str, object]:
    con, fonte_processado = _connect_processed_readonly()
    fontes = [fonte_processado]
    checks: list[dict[str, object]] = []
    if con is None:
        return {
            "usuario": user.login,
            "anomes": ANOMES,
            "status": "fonte_indisponivel",
            "checks": [],
            "fontes": fontes,
        }

    try:
        required_tables = ["adms_iqs_export", "gold_apuracao_uc", "gold_consumidores", "gold_uc_fatura"]
        for table in required_tables:
            exists = _table_exists(con, table)
            checks.append(
                {
                    "codigo": f"tabela_{table}",
                    "titulo": f"Tabela {table}",
                    "status": "ok" if exists else "bloqueante",
                    "mensagem": "disponível" if exists else "ausente no DuckDB processado",
                    "severidade": "bloqueante" if not exists else "ok",
                }
            )

        if _table_exists(con, "adms_iqs_export"):
            total_export = _number(con.execute("SELECT COUNT(*) FROM adms_iqs_export").fetchone()[0])
            checks.append(
                {
                    "codigo": "exportacao_tem_linhas",
                    "titulo": "Arquivo IQS com registros",
                    "status": "ok" if total_export > 0 else "bloqueante",
                    "mensagem": f"{int(total_export)} linha(s) candidatas à exportação",
                    "severidade": "bloqueante" if total_export <= 0 else "ok",
                }
            )

            columns = {row[0].upper() for row in con.execute("DESCRIBE adms_iqs_export").fetchall()}
            for column in ["NUM_OCORRENCIA_ADMS", "NUM_SEQ_INTRP", "DATA_HORA_INIC_INTRP", "DATA_HORA_FIM_INTRP"]:
                checks.append(
                    {
                        "codigo": f"coluna_{column.lower()}",
                        "titulo": f"Coluna obrigatória {column}",
                        "status": "ok" if column in columns else "bloqueante",
                        "mensagem": "presente no layout candidato" if column in columns else "ausente no layout candidato",
                        "severidade": "bloqueante" if column not in columns else "ok",
                    }
                )

        checks.extend(
            [
                {
                    "codigo": "datas_ddmmaaaa",
                    "titulo": "Datas no padrão IQS",
                    "status": "pendente_execucao",
                    "mensagem": "validar no arquivo físico: campos data/hora em dd/mm/aaaa hh:mm:ss",
                    "severidade": "atenção",
                },
                {
                    "codigo": "unix_lf",
                    "titulo": "Quebra de linha UNIX",
                    "status": "pendente_execucao",
                    "mensagem": "validar no arquivo físico gerado em data/export antes de enviar ao IQS",
                    "severidade": "atenção",
                },
                {
                    "codigo": "encoding_iso_8859_1",
                    "titulo": "Encoding ISO-8859-1",
                    "status": "pendente_execucao",
                    "mensagem": "validar encoding do CSV final aceito pelo IQS",
                    "severidade": "atenção",
                },
                {
                    "codigo": "regional_nrt",
                    "titulo": "Regional NRT preservada",
                    "status": "ok",
                    "mensagem": "validação lógica permanece obrigatória quando o pacote for regionalizado",
                    "severidade": "ok",
                },
            ]
        )
        bloqueantes = sum(1 for check in checks if check["severidade"] == "bloqueante")
        pendentes = sum(1 for check in checks if check["status"] == "pendente_execucao")
        return {
            "usuario": user.login,
            "anomes": ANOMES,
            "status": "bloqueado" if bloqueantes else "pendente_validacao_fisica" if pendentes else "ok",
            "resumo": {
                "checks": len(checks),
                "bloqueantes": bloqueantes,
                "pendentes": pendentes,
                "ok": sum(1 for check in checks if check["severidade"] == "ok"),
            },
            "checks": checks,
            "fontes": fontes,
            "regras": {
                "nao_exporta": "esta validação é prévia e não gera arquivo",
                "contrato": "docs/35_contrato_exportacao_iqs.md",
                "pendencia_empresa": "validar arquivo físico final dentro da rede/ambiente da empresa antes do envio ao IQS",
            },
        }
    finally:
        con.close()


def _build_cockpit(user: AuthUser, limite: int) -> dict[str, object]:
    conjuntos_ref, _, hierarchy_fontes = _hierarchy_reference_maps()
    con, fonte_processado = _connect_processed_readonly()
    fontes = [*hierarchy_fontes, fonte_processado]
    if con is None:
        return _empty_cockpit(user, fontes)

    try:
        if not _table_exists(con, "gold_apuracao_uc"):
            fontes.append({"fonte": "gold_apuracao_uc", "status": "ausente"})
            return _empty_cockpit(user, fontes)

        fontes.append({"fonte": "gold_apuracao_uc", "status": "ok"})
        if _table_exists(con, "gold_ressarcimento_prodist"):
            fontes.append({"fonte": "gold_ressarcimento_prodist", "status": "ok"})
        else:
            fontes.append({"fonte": "gold_ressarcimento_prodist", "status": "ausente"})

        denominador = 0.0
        if _table_exists(con, "gold_consumidores"):
            fontes.append({"fonte": "gold_consumidores", "status": "ok"})
            denominador = _denominador_copel(con)

        base = _fetchone_dict(
            con,
            """
            SELECT
                COUNT(*) AS linhas_uc,
                COUNT(DISTINCT NUM_OCORRENCIA_ADMS) AS ocorrencias,
                COUNT(DISTINCT NUM_SEQ_INTRP) AS interrupcoes,
                COUNT(DISTINCT NUM_UC_UCI) AS ucs,
                COUNT(DISTINCT REGIONAL) AS regionais,
                COUNT(DISTINCT COD_CONJTO_ELET_ANEEL_INTRP) AS conjuntos,
                SUM(COALESCE(CI_LIQUIDO, 0)) AS ci_liquido,
                SUM(COALESCE(CHI_LIQUIDO, 0)) AS chi_liquido,
                MAX(COALESCE(DURACAO_HORA, 0)) AS duracao_maxima_h,
                SUM(CASE WHEN COALESCE(DURACAO_HORA, 0) >= 24 THEN 1 ELSE 0 END) AS linhas_duracao_suspeita
            FROM gold_apuracao_uc
            """,
        )

        ressarcimento = {"ucs_com_compensacao": 0, "comp_total_prodist": 0}
        if _table_exists(con, "gold_ressarcimento_prodist"):
            ressarcimento = _fetchone_dict(
                con,
                """
                SELECT
                    COUNT(DISTINCT CASE WHEN COALESCE(COMP_TOTAL_PRODIST, 0) > 0 THEN UC END) AS ucs_com_compensacao,
                    SUM(COALESCE(COMP_TOTAL_PRODIST, 0)) AS comp_total_prodist
                FROM gold_ressarcimento_prodist
                """,
            )

        chi_liquido = _number(base.get("chi_liquido"))
        ci_liquido = _number(base.get("ci_liquido"))
        dec_liquido = chi_liquido / denominador if denominador else 0
        fec_liquido = ci_liquido / denominador if denominador else 0

        cards = [
            _metric_card("ocorrencias", "Ocorrências", base.get("ocorrencias"), "qtd", "Ocorrências com UC apurável na base regulatória.", "regulatoria"),
            _metric_card("ucs", "UCs apuráveis", base.get("ucs"), "qtd", "UCs faturadas/apuráveis consideradas na base de DIC/FIC.", "regulatoria"),
            _metric_card("dic_liquido", "DIC líquido", chi_liquido, "hora", "Soma de CHI líquido na base de apuração UC.", "regulatoria"),
            _metric_card("fic_liquido", "FIC líquido", ci_liquido, "qtd", "Soma de CI líquido na base de apuração UC.", "regulatoria"),
            _metric_card("dec_liquido", "DEC líquido estimado", dec_liquido, "hora/cons", "CHI líquido dividido pelo denominador COPEL quando disponível.", "regulatoria"),
            _metric_card("fec_liquido", "FEC líquido estimado", fec_liquido, "freq/cons", "CI líquido dividido pelo denominador COPEL quando disponível.", "regulatoria"),
            _metric_card("comp_total_prodist", "Compensação PRODIST", ressarcimento.get("comp_total_prodist"), "BRL", "Soma única por UC em gold_ressarcimento_prodist.", "regulatoria"),
            _metric_card("duracao_suspeita", "Duração suspeita", base.get("linhas_duracao_suspeita"), "qtd", "Linhas UC com duração maior ou igual a 24h.", "cliente_operacao"),
        ]

        return {
            "usuario": user.login,
            "anomes": ANOMES,
            "status": "ok",
            "lente_padrao": "regulatoria",
            "nivel_padrao": "macro",
            "cards": cards,
            "rankings": {
                "regional": _ranking_regional(con, limite),
                "conjunto": _ranking_conjunto(con, limite, conjuntos_ref),
            },
            "alertas": [
                {
                    "tipo": "hierarquia",
                    "mensagem": "Nomes de conjunto/alimentador usam referências locais em data/input; extração direta do IQS fica pendente para migração empresarial.",
                }
            ],
            "fontes": fontes,
            "regras": {
                "regulatoria": "DIC/FIC e compensação usam bases gold regulatórias disponíveis.",
                "cliente_operacao": "duração suspeita e rankings preservam visão operacional para investigação.",
                "ordenacao": "rankings priorizam CHI líquido, CI líquido e compensação PRODIST.",
                "denominador_dec_fec": "soma de UC_FATURADA em gold_consumidores com REGIONAL_TOTAL = COPEL",
            },
        }
    except (duckdb.Error, OSError) as exc:
        fontes.append({"fonte": "consulta_cockpit", "status": "erro", "erro": str(exc).splitlines()[0]})
        return _empty_cockpit(user, fontes)
    finally:
        con.close()


@router.get("/visao")
def visao_produto(
    user: AuthUser = Depends(require_profiles("ADM", "GESTOR", "ANALISTA", "CONSULTA", "AUDITOR")),
) -> dict[str, object]:
    return {
        "usuario": user.login,
        "sprint": {
            "codigo": "SPRINT_02_DRILLDOWN_IMPACTO",
            "titulo": "Drill-down de impacto regulatório e operação",
            "status": "iniciada",
            "documento": "docs/sprints/02_drilldown_impacto.md",
        },
        "direcao": {
            "react": "Interface principal para operação, governança e navegação executiva.",
            "streamlit": "Laboratório analítico e validação rápida durante a transição.",
            "api": "Camada única de contratos para dados, evidências, recomendações e decisões.",
        },
        "lentes": [
            {
                "codigo": "regulatoria",
                "nome": "Regulatória",
                "descricao": "PRODIST, IQS, faturados, DIC/FIC, DEC/FEC e compensação.",
                "principais_metricas": ["DIC/FIC", "DEC/FEC", "DMIC", "DICRI", "DISE", "compensação"],
            },
            {
                "codigo": "cliente_operacao",
                "nome": "Cliente/operação",
                "descricao": "Todos os clientes do OMS, reclamações, serviços, reincidência e impacto percebido.",
                "principais_metricas": ["clientes totais", "clientes faturados", "clientes não faturados", "reclamações", "serviços"],
            },
        ],
        "niveis": [
            {
                "codigo": "macro",
                "nome": "Macro",
                "descricao": "COPEL, regionais, risco regulatório, financeiro, cliente e qualidade.",
            },
            {
                "codigo": "intermediario",
                "nome": "Intermediário",
                "descricao": "Conjunto, alimentador, chave/equipamento, tipo de suspeita e módulo.",
            },
            {
                "codigo": "detalhado",
                "nome": "Detalhado",
                "descricao": "Ocorrência, interrupção, UC, cliente, serviço, evidências e decisão.",
            },
        ],
        "paginas_react": [
            {
                "codigo": "cockpit",
                "nome": "Cockpit",
                "objetivo": "Priorizar risco e ganho por lente e nível.",
                "status": "implementado_inicial",
            },
            {
                "codigo": "anomalias",
                "nome": "Anomalias",
                "objetivo": "Exibir suspeitas por módulo, impacto e evidência curta.",
                "status": "existente_a_reorientar",
            },
            {
                "codigo": "tratamentos_robotizados",
                "nome": "Tratamentos Robotizados",
                "objetivo": "Explicar regras automáticas, antes/depois e ganho estimado.",
                "status": "planejada",
            },
            {
                "codigo": "fila_tecnica",
                "nome": "Fila Técnica",
                "objetivo": "Orientar o que o analista deve verificar por tipo de suspeita.",
                "status": "planejada",
            },
            {
                "codigo": "governanca",
                "nome": "Governança",
                "objetivo": "Aprovar, rejeitar, justificar e montar pacote IQS.",
                "status": "existente_a_expandir",
            },
            {
                "codigo": "detalhe_operacional",
                "nome": "Detalhe Operacional",
                "objetivo": "Drill-down COPEL > regional > conjunto > alimentador > chave > ocorrência > interrupção > UC.",
                "status": "implementado_inicial",
            },
        ],
        "hierarquia_eletrica": [
            {"campo": "regional", "exibicao": "sigla - nome da regional", "obrigatorio": True},
            {"campo": "conjunto", "exibicao": "número do conjunto - nome do conjunto", "obrigatorio": True},
            {"campo": "alimentador", "exibicao": "número/código do alimentador - nome do alimentador", "obrigatorio": True},
            {"campo": "chave_equipamento", "exibicao": "código da chave/equipamento - descrição", "obrigatorio": False},
        ],
        "dicionarios_humanos": [
            {"codigo": "grupo_componente_causa", "descricao": "Grupo, componente e causa com código e descrição."},
            {"codigo": "tipo_interrupcao", "descricao": "Tipo de interrupção com código e nome."},
            {"codigo": "protocolo_justificativa", "descricao": "Protocolo com impacto em DIC/FIC, DICRI e DISE."},
            {"codigo": "motivo_tratamento", "descricao": "Motivo de tratamento diferenciado com significado humano."},
            {"codigo": "regional_conjunto_alimentador", "descricao": "Regional, conjunto e alimentador com número/código e nome."},
        ],
        "decisao_humana": {
            "regra_ouro": "Algoritmo sugere; analista decide; gestor aprova quando houver impacto relevante; MIDWAY audita; equipe melhora a regra.",
            "campos_obrigatorios": [
                "valor_atual",
                "valor_sugerido",
                "descricao_atual",
                "descricao_sugerida",
                "regra_curta",
                "evidencias",
                "impacto_estimado",
                "confianca",
                "risco_falso_positivo",
            ],
            "acoes": ["aceitar", "rejeitar", "editar", "enviar_fila_tecnica"],
            "justificativa_obrigatoria_quando": "decisão humana diferente da recomendação",
        },
        "tabelas_interativas": {
            "ordenacao_cabecalho": True,
            "filtro_por_coluna": True,
            "busca_codigo_ou_texto": True,
            "codigo_descricao": True,
            "preservar_filtro_ao_abrir_detalhe": True,
        },
        "contratos_api_planejados": [
            {"endpoint": "/api/produto/visao", "status": "implementado"},
            {"endpoint": "/api/produto/cockpit", "status": "implementado_inicial"},
            {"endpoint": "/api/produto/detalhe-conjunto/{conjunto}", "status": "implementado_inicial"},
            {"endpoint": "/api/produto/detalhe-alimentador/{alimentador}", "status": "implementado_inicial"},
            {"endpoint": "/api/produto/suspeitas-ra", "status": "implementado_inicial"},
            {"endpoint": "/api/produto/validacao-iqs", "status": "implementado_inicial"},
            {"endpoint": "/api/produto/hierarquia", "status": "planejado"},
            {"endpoint": "/api/produto/dicionarios", "status": "implementado"},
            {"endpoint": "/api/produto/decisoes/aprendizado", "status": "planejado"},
        ],
    }


@router.get("/dicionarios")
def dicionarios_produto(
    tipo: str | None = Query(None, description="Filtra por tipo de dicionário."),
    q: str | None = Query(None, description="Busca por código, nome, descrição ou relação."),
    limite: int = Query(5000, ge=1, le=10000, description="Limite máximo de itens retornados."),
    user: AuthUser = Depends(require_profiles("ADM", "GESTOR", "ANALISTA", "CONSULTA", "AUDITOR")),
) -> dict[str, object]:
    items = _static_dictionaries()
    dynamic_items, fontes = _load_reference_dictionaries()
    items.extend(dynamic_items)

    filtered = _filter_dictionaries(items, tipo=tipo, q=q)
    resumo_por_tipo = Counter(str(item["tipo"]) for item in filtered)
    limited = filtered[:limite]

    return {
        "usuario": user.login,
        "anomes": ANOMES,
        "items": limited,
        "resumo": {
            "total_disponivel": len(items),
            "total_filtrado": len(filtered),
            "total_retornado": len(limited),
            "tipos": dict(sorted(resumo_por_tipo.items())),
            "limite": limite,
        },
        "fontes": fontes,
        "regras": {
            "exibicao_humana": "código - nome/descrição",
            "sem_descricao": "mostrar o código e sinalizar descrição não disponível",
            "conjunto_alimentador": "nomes locais vêm de data/input/Referencia_DEC FEC CONJUNTO Ano_Copel.csv e data/input/Referencia_Alimentador_Copel.CSV",
            "pendencia_iqs_empresa": "extrair nomes de conjunto e alimentador diretamente do IQS após migração para o ambiente empresarial",
            "filtros": ["tipo", "q", "limite"],
        },
    }


@router.get("/cockpit")
def cockpit_produto(
    limite: int = Query(20, ge=1, le=100, description="Quantidade máxima por ranking."),
    user: AuthUser = Depends(require_profiles("ADM", "GESTOR", "ANALISTA", "CONSULTA", "AUDITOR")),
) -> dict[str, object]:
    return _build_cockpit(user, limite)


@router.get("/modulos-resumo")
def modulos_resumo_produto(
    user: AuthUser = Depends(require_profiles("ADM", "GESTOR", "ANALISTA", "CONSULTA", "AUDITOR")),
) -> dict[str, object]:
    return _resumo_modulos_automatizados()


@router.get("/modulos-amostra/{codigo}")
def modulos_amostra_produto(
    codigo: str,
    limite: int = Query(20, ge=1, le=100, description="Quantidade máxima de linhas de amostra."),
    user: AuthUser = Depends(require_profiles("ADM", "GESTOR", "ANALISTA", "CONSULTA", "AUDITOR")),
) -> dict[str, object]:
    return _amostra_modulo_automatizado(codigo, limite)


@router.get("/detalhe-conjunto/{conjunto}")
def detalhe_conjunto_produto(
    conjunto: str,
    limite_alimentadores: int = Query(20, ge=1, le=100, description="Quantidade máxima de alimentadores."),
    limite_ocorrencias: int = Query(30, ge=1, le=200, description="Quantidade máxima de ocorrências."),
    user: AuthUser = Depends(require_profiles("ADM", "GESTOR", "ANALISTA", "CONSULTA", "AUDITOR")),
) -> dict[str, object]:
    return _detalhe_conjunto(user, conjunto, limite_alimentadores, limite_ocorrencias)


@router.get("/detalhe-alimentador/{alimentador}")
def detalhe_alimentador_produto(
    alimentador: str,
    conjunto: str | None = Query(None, description="Opcional: restringe o alimentador ao conjunto selecionado."),
    limite_ocorrencias: int = Query(30, ge=1, le=200, description="Quantidade máxima de ocorrências."),
    user: AuthUser = Depends(require_profiles("ADM", "GESTOR", "ANALISTA", "CONSULTA", "AUDITOR")),
) -> dict[str, object]:
    return _detalhe_alimentador(user, alimentador, conjunto, limite_ocorrencias)


@router.get("/suspeitas-ra")
def suspeitas_ra_produto(
    limite: int = Query(20, ge=1, le=100, description="Quantidade máxima de suspeitas retornadas."),
    user: AuthUser = Depends(require_profiles("ADM", "GESTOR", "ANALISTA", "CONSULTA", "AUDITOR")),
) -> dict[str, object]:
    return _painel_suspeitas_ra(user, limite)


@router.get("/validacao-iqs")
def validacao_iqs_produto(
    user: AuthUser = Depends(require_profiles("ADM", "GESTOR", "ANALISTA", "CONSULTA", "AUDITOR")),
) -> dict[str, object]:
    return _validacao_iqs_governada(user)
