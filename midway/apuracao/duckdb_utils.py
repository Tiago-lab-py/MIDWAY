from __future__ import annotations

from pathlib import Path


def sql_literal(valor: object) -> str:
    return "'" + str(valor).replace("'", "''") + "'"


def tabela_local_existe(con, nome_tabela: str) -> bool:
    return (
        con.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'main'
              AND table_name = ?
            """,
            [nome_tabela],
        ).fetchone()[0]
        > 0
    )


def normalizar_linhas_unix(caminho_csv: str | Path) -> None:
    caminho = Path(caminho_csv)
    conteudo = caminho.read_bytes()
    normalizado = conteudo.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if normalizado != conteudo:
        caminho.write_bytes(normalizado)
