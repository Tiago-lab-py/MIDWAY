import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from sqlalchemy import text

load_dotenv(override=True)

from midway.db.postgres import create_postgres_engine

def _schema():
    return os.getenv("POSTGRES_SCHEMA", "ddcq")

def resetar_lotes_travados():
    print("Conectando ao banco de dados Postgres...")
    engine = create_postgres_engine()
    
    schema = _schema()
    
    with engine.begin() as con:
        resultado = con.execute(
            text(f"UPDATE {schema}.midway_execucao_lote SET status_lote = 'ERRO', mensagem = mensagem || '\n[SISTEMA] Processo travado cancelado manualmente.' WHERE status_lote = 'PROCESSANDO'")
        )
        linhas = resultado.rowcount
        
    print(f"Sucesso! {linhas} lote(s) que estava(m) travado(s) em 'PROCESSANDO' foram alterado(s) para 'ERRO'.")
    print("Voce ja pode voltar para a interface web, atualizar a pagina e clicar no botao para executar a Fase 3!")

if __name__ == "__main__":
    resetar_lotes_travados()
