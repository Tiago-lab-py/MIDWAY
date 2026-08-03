import sys
from pathlib import Path

# Garante que o diretório atual está no path para importar o módulo midway
sys.path.append(str(Path(__file__).parent))

from midway.auditoria.suspeita_falha_ra import analisar_suspeita_falha_ra

print("=== Testando cálculo de Suspeita Falha RA ===")
print("Processando dados do DuckDB...")

try:
    detalhe, resumo = analisar_suspeita_falha_ra()
    
    print("\n[Sucesso] Executado sem erros!")
    print(f"Número de ocorrências detalhadas de RA encontradas: {len(detalhe)}")
    print(f"Número de equipamentos/dia com suspeitas: {len(resumo)}")
    
    if not resumo.empty:
        print("\nExemplo das primeiras 5 suspeitas identificadas:")
        print(resumo[["REGIONAL", "CONJUNTO", "ALIM_INTRP", "NUM_OPER_CHV_INTRP", "DIA_OPERACAO", "SCORE_SUSPEITA_RA"]].head())
    else:
        print("\nNenhuma suspeita que atenda aos critérios foi encontrada para o mês selecionado.")
        
except Exception as e:
    print(f"\n[Erro] Falha ao executar o cálculo: {e}")
