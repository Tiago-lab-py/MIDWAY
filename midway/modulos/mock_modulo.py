from .base_modulo import BaseModulo, PropostaTratamento
from typing import List

class MockModulo(BaseModulo):
    """
    Implementação simulada (Mock) para testar a persistência no banco.
    """
    
    @property
    def codigo_modulo(self) -> str:
        return "MOCK_SOBREPOSICAO"
        
    @property
    def escopo(self) -> str:
        return "interrupcao"

    @property
    def criterio_anomalia(self) -> str:
        return "Duas interrupções para a mesma UC no mesmo segundo."

    @property
    def risco_falso_positivo(self) -> str:
        return "Nenhum no mock."

    def detectar_anomalias(self) -> List[PropostaTratamento]:
        proposta = PropostaTratamento(
            chave_negocio="INTRP-12345",
            evidencias={
                "uc": "98765432",
                "inicio_1": "2023-01-01 10:00:00",
                "inicio_2": "2023-01-01 10:00:00",
                "duracao": 120,
                "msg": "Sobreposição detectada."
            },
            impacto="Aumento irreal de FIC",
            acao_sugerida="Excluir interrupção duplicada",
            campos_iqs_afetados=["COD_SITUACAO_INTRP"],
            exportacao_iqs="auditoria_sobreposicoes.csv"
        )
        return [proposta]

# Teste simples de persistência se rodado isoladamente
if __name__ == "__main__":
    modulo = MockModulo()
    anomalias = modulo.detectar_anomalias()
    print(f"Módulo {modulo.codigo_modulo} detectou {len(anomalias)} anomalias.")
    
    # Para salvar no banco, normalmente o orquestrador faria isso:
    import json
    from midway.db.postgres import create_postgres_engine
    from sqlalchemy import text
    
    engine = create_postgres_engine()
    try:
        with engine.connect() as conn:
            for p in anomalias:
                conn.execute(
                    text("""
                    INSERT INTO ddcq.propostas_tratamento 
                    (codigo_modulo, chave_negocio, evidencias, impacto, acao_sugerida, campos_iqs_afetados, exportacao_iqs)
                    VALUES (:codigo, :chave, :evidencias, :impacto, :acao, :campos, :exportacao)
                    """),
                    {
                        "codigo": modulo.codigo_modulo,
                        "chave": p.chave_negocio,
                        "evidencias": json.dumps(p.evidencias),
                        "impacto": p.impacto,
                        "acao": p.acao_sugerida,
                        "campos": p.campos_iqs_afetados,
                        "exportacao": p.exportacao_iqs
                    }
                )
                print(f"Gravado com sucesso no Postgres!")
            conn.commit()
    except Exception as e:
        print(f"Erro ao gravar no banco: {e}")
