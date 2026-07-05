import duckdb

from midway.transform.iqs_raw_utils import materializar_gold_de_iqs_raw
from midway.apuracao.auditoria_sem_uc import (
    criar_gold_interrupcao_sem_uc,
    criar_gold_ocorrencia_sem_uc,
    exportar_auditoria_interrupcao_sem_uc,
)
from midway.apuracao.exportacoes import (
    exportar_bdo_interrupcao as _exportar_bdo_interrupcao,
    exportar_gold_continuidade_uc as _exportar_gold_continuidade_uc,
    exportar_gold_ressarcimento_prodist as _exportar_gold_ressarcimento_prodist,
)
from midway.apuracao.resumos import (
    anexar_compensacao_resumo_principal as _anexar_compensacao_resumo_principal,
    gerar_resumo as _gerar_resumo,
    obter_resumo_compensacao as _obter_resumo_compensacao,
)
from midway.apuracao.continuidade import criar_gold_continuidade_uc
from midway.apuracao.ressarcimento import criar_gold_ressarcimento_prodist
from midway.apuracao.contexto import CONTEXTO
from midway.apuracao.conjunto import (
    criar_gold_impacto_conjunto_dia,
    criar_gold_meta_dia_critico_conjunto,
    exportar_gold_impacto_conjunto_dia as _exportar_gold_impacto_conjunto_dia,
    exportar_gold_meta_dia_critico_conjunto as _exportar_gold_meta_dia_critico_conjunto,
)
from midway.apuracao.duckdb_utils import sql_literal
from midway.apuracao.apuracao_previa import (
    criar_gold_apuracao_previa as _criar_gold_apuracao_previa,
)
from midway.apuracao.apuracao_uc import (
    criar_gold_apuracao_uc_base as _criar_gold_apuracao_uc_base,
)
from midway.apuracao.interrupcao_tratada import (
    criar_gold_interrupcao_tratada as _criar_gold_interrupcao_tratada,
)


ANOMES = CONTEXTO.anomes
TOTAL_CONSUMIDORES = CONTEXTO.total_consumidores

BASE_DIR = CONTEXTO.base_dir
EXPORT_DIR = CONTEXTO.export_dir
MARTS_DIR = CONTEXTO.marts_dir
PROCESSED_DUCKDB_PATH = CONTEXTO.processed_duckdb_path
RAW_DUCKDB_PATH = CONTEXTO.raw_duckdb_path

DATA_ARQ = CONTEXTO.data_arq
TIMESTAMP_ARQ = CONTEXTO.timestamp_arq

def materializar_compatibilidade_gold(con, tabela_silver: str, tabela_gold: str):
    con.execute(
        f"""
        CREATE OR REPLACE TABLE {tabela_gold} AS
        SELECT *
        FROM {tabela_silver}
        """
    )

def validar_tabela_export(con):
    tabelas = {
        linha[0]
        for linha in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
    }

    if "adms_iqs_export" not in tabelas:
        raise RuntimeError(
            "Tabela adms_iqs_export nao encontrada. Execute run.bat tratamento "
            "ou run.bat exportar antes da apuracao previa."
        )


def total_consumidores_sql():
    if TOTAL_CONSUMIDORES is None or not str(TOTAL_CONSUMIDORES).strip():
        return "NULL"

    return str(TOTAL_CONSUMIDORES).replace(",", ".")


def tabela_gold_consumidores_existe(con):
    return (
        con.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'main'
              AND table_name = 'gold_consumidores'
            """
        ).fetchone()[0]
        > 0
    )


def validar_gold_uc_fatura(con):
    existe = (
        con.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'main'
              AND table_name = 'gold_uc_fatura'
            """
        ).fetchone()[0]
        > 0
    )

    if not existe:
        raise RuntimeError(
            "Tabela gold_uc_fatura nao encontrada. Execute run.bat uc_fatura "
            "antes da apuracao."
        )


def criar_gold_apuracao_previa(con):
    return _criar_gold_apuracao_previa(
        con,
        total_consumidores_sql=total_consumidores_sql,
        tabela_gold_consumidores_existe=tabela_gold_consumidores_existe,
    )


def criar_gold_apuracao_uc_base(con):
    return _criar_gold_apuracao_uc_base(
        con,
        materializar_compatibilidade_gold=materializar_compatibilidade_gold,
    )


def anexar_raw(con):
    if not RAW_DUCKDB_PATH.exists():
        raise RuntimeError(f"DuckDB bruto nao encontrado: {RAW_DUCKDB_PATH}")

    con.execute(f"ATTACH {sql_literal(RAW_DUCKDB_PATH.as_posix())} AS raw_db (READ_ONLY)")


def criar_gold_interrupcao_tratada(con):
    return _criar_gold_interrupcao_tratada(con)


def exportar_bdo_interrupcao(con):
    return _exportar_bdo_interrupcao(
        con,
        export_dir=EXPORT_DIR,
        data_arq=DATA_ARQ,
        timestamp=TIMESTAMP_ARQ,
    )


def gerar_resumo(con, caminho_csv):
    return _gerar_resumo(
        con,
        caminho_csv,
        marts_dir=MARTS_DIR,
        timestamp=TIMESTAMP_ARQ,
        anomes=ANOMES,
        processed_duckdb_path=PROCESSED_DUCKDB_PATH,
        tabela_gold_consumidores_existe=tabela_gold_consumidores_existe,
    )


def exportar_gold_ressarcimento_prodist(con):
    return _exportar_gold_ressarcimento_prodist(
        con,
        marts_dir=MARTS_DIR,
        anomes=ANOMES,
        timestamp=TIMESTAMP_ARQ,
    )


def exportar_gold_continuidade_uc(con):
    return _exportar_gold_continuidade_uc(
        con,
        marts_dir=MARTS_DIR,
        anomes=ANOMES,
        timestamp=TIMESTAMP_ARQ,
    )


def obter_resumo_compensacao(con):
    return _obter_resumo_compensacao(con)


def anexar_compensacao_resumo_principal(con):
    return _anexar_compensacao_resumo_principal(
        con,
        export_dir=EXPORT_DIR,
        anomes=ANOMES,
        obter_resumo_compensacao=obter_resumo_compensacao,
    )

def apuracao_previa():
    if not PROCESSED_DUCKDB_PATH.exists():
        raise RuntimeError(f"DuckDB processado nao encontrado: {PROCESSED_DUCKDB_PATH}")

    con = duckdb.connect(str(PROCESSED_DUCKDB_PATH))
    con.execute("SET preserve_insertion_order=false")
    anexar_raw(con)
    tabelas_iqs = materializar_gold_de_iqs_raw(con, ANOMES)
    if tabelas_iqs:
        print("Tabelas IQS sincronizadas do raw: " + ", ".join(tabelas_iqs))
    validar_gold_uc_fatura(con)

    print("Criando gold_interrupcao_tratada completa do RAW...")
    criar_gold_interrupcao_tratada(con)

    print("Criando gold_apuracao_uc...")
    criar_gold_apuracao_uc(con)

    print("Criando gold_apuracao_previa...")
    criar_gold_apuracao_previa(con)

    print("Exportando BDO_interupcao...")
    caminho_csv = exportar_bdo_interrupcao(con)
    caminho_resumo = gerar_resumo(con, caminho_csv)

    con.close()

    print(f"BDO exportado: {caminho_csv}")
    print(f"Resumo exportado: {caminho_resumo}")
    print("Apuracao previa concluida.")


def exportar_gold_impacto_conjunto_dia(con):
    return _exportar_gold_impacto_conjunto_dia(
        con,
        marts_dir=MARTS_DIR,
        anomes=ANOMES,
        timestamp=TIMESTAMP_ARQ,
        processed_duckdb_path=PROCESSED_DUCKDB_PATH,
    )


def exportar_gold_meta_dia_critico_conjunto(con):
    return _exportar_gold_meta_dia_critico_conjunto(
        con,
        marts_dir=MARTS_DIR,
        anomes=ANOMES,
        timestamp=TIMESTAMP_ARQ,
        processed_duckdb_path=PROCESSED_DUCKDB_PATH,
    )


_criar_gold_apuracao_uc_original = criar_gold_apuracao_uc_base


def criar_gold_apuracao_uc(con):
    if not globals().get("_AUDITORIA_INTERRUPCAO_SEM_UC_EXECUTADA", False):
        criar_gold_interrupcao_sem_uc(con)
        criar_gold_ocorrencia_sem_uc(con)
        exportar_auditoria_interrupcao_sem_uc(
            con,
            marts_dir=MARTS_DIR,
            anomes=ANOMES,
            timestamp=TIMESTAMP_ARQ,
        )
        globals()["_AUDITORIA_INTERRUPCAO_SEM_UC_EXECUTADA"] = True

    resultado = _criar_gold_apuracao_uc_original(con)
    criar_gold_continuidade_uc(con)
    criar_gold_ressarcimento_prodist(con)
    criar_gold_impacto_conjunto_dia(con)
    criar_gold_meta_dia_critico_conjunto(con)
    exportar_gold_continuidade_uc(con)
    exportar_gold_ressarcimento_prodist(con)
    exportar_gold_impacto_conjunto_dia(con)
    exportar_gold_meta_dia_critico_conjunto(con)
    anexar_compensacao_resumo_principal(con)
    return resultado


if __name__ == "__main__":
    apuracao_previa()
