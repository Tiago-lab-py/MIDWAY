"""
Validações automáticas dos arquivos CSV do ADMS exportados pelo MIDWAY.
Adaptado a partir da rotina externa da COPEL.
"""
import os
import glob
import pandas as pd

from dotenv import load_dotenv
from pathlib import Path

from midway.controle_execucao import configurar_logger
from midway.transform.tratamento import ANOMES, EXPORT_DIR

load_dotenv()

def validar_tam_campo_data(df):
    """Valida se os campos de data e hora têm tamanho exato de 19 caracteres (dd/mm/aaaa hh:mm:ss)."""
    if "DATA_HORA_INIC_INTRP" not in df.columns or "DATA_HORA_FIM_INTRP" not in df.columns:
        return pd.DataFrame()
    inicio = df['DATA_HORA_INIC_INTRP'].astype(str).str.len()
    fim = df['DATA_HORA_FIM_INTRP'].astype(str).str.len()
    mascara = (inicio != 19) | (fim != 19)
    return df[mascara].copy()

def validar_data_intrp(df):
    """Verifica se há interrupções com duração negativa (fim antes do início)."""
    if "DATA_HORA_INIC_INTRP" not in df.columns or "DATA_HORA_FIM_INTRP" not in df.columns:
        return pd.DataFrame()
    try:
        inicio = pd.to_datetime(df["DATA_HORA_INIC_INTRP"], dayfirst=True)
        fim = pd.to_datetime(df["DATA_HORA_FIM_INTRP"], dayfirst=True)
        return df[fim < inicio]
    except Exception as ex:
        # Se falhar a conversão de alguma data que já passou no teste de string, retorna as primeiras linhas indicando erro
        return df.head(1)

def validar_contagem_intrp(df):
    """Verifica diferenças entre a contagem de colunas e a coluna CONS_INTRP."""
    col_tot = "PID_INTRP_CONJTO_PIN"
    col_contagem = "CONS_INTRP"
    if col_tot not in df.columns or col_contagem not in df.columns:
        return pd.DataFrame()
        
    resultado = df.groupby(col_tot).agg(
        Total_Linhas=(col_tot, 'size'),                 
        Primeiro_CONS_INTRP=(col_contagem, 'first')     
    ).reset_index()
    resultado['Primeiro_CONS_INTRP'] = pd.to_numeric(resultado['Primeiro_CONS_INTRP'], errors='coerce').fillna(0)
    return resultado.query("Total_Linhas != Primeiro_CONS_INTRP")

def executar_validacoes():
    logger = configurar_logger("validar_exportacao", ANOMES)
    logger.info("Iniciando validação de arquivos CSV no diretório: %s", EXPORT_DIR)

    # Busca arquivos na pasta raiz e em todas as subpastas (ex: interrupcao_sem_uc, etc)
    arquivos_csv = glob.glob(os.path.join(EXPORT_DIR, "**", "Interrupcoes_IQS_*.CSV"), recursive=True)
    # Alguns arquivos gerados podem ter extensões minúsculas (.csv)
    arquivos_csv.extend(glob.glob(os.path.join(EXPORT_DIR, "**", "Interrupcoes_IQS_*.csv"), recursive=True))
    if not arquivos_csv:
        logger.warning("Nenhum arquivo Interrupcoes_IQS_*.CSV encontrado em %s", EXPORT_DIR)
        return

    erros_fatais = 0

    for arq in arquivos_csv:
        nome_arq = os.path.basename(arq)
        if os.path.getsize(arq) == 0:
            logger.error("O arquivo %s está vazio.", nome_arq)
            erros_fatais += 1
            continue
            
        try:
            df = pd.read_csv(arq, sep="|", low_memory=False, dtype=str)
        except Exception as ex:
            logger.error("Erro ao ler %s: %s", nome_arq, ex)
            erros_fatais += 1
            continue

        nr_colunas = len(df.columns)
        nr_linhas = len(df)
        
        # Variáveis de expurgo com nomes exatos
        nr_registros_expurgo = 0
        nr_registros_expurgo_tipo_prot = 0
        nr_registros_expurgo_uc = 0
        nr_registros_expurgo_uc_prot = 0
        
        if "NUM_PROTOC_JUSTIF_RESP_INTRP" in df.columns:
            nr_registros_expurgo = (df.query("NUM_PROTOC_JUSTIF_RESP_INTRP.notna() and NUM_PROTOC_JUSTIF_RESP_INTRP.str.strip() != ''", engine="python")["NUM_PROTOC_JUSTIF_RESP_INTRP"]).count()
        if "TIPO_PROTOC_JUSTIF_INTRP" in df.columns:
            nr_registros_expurgo_tipo_prot = pd.to_numeric(df["TIPO_PROTOC_JUSTIF_INTRP"], errors='coerce').fillna(0).astype(int).apply(lambda x: x > 0).sum()
        if "NUM_PROTOC_JUSTIF_RESP_UCI" in df.columns:
            nr_registros_expurgo_uc = (df.query("NUM_PROTOC_JUSTIF_RESP_UCI.notna() and NUM_PROTOC_JUSTIF_RESP_UCI.str.strip() != ''", engine="python")["NUM_PROTOC_JUSTIF_RESP_UCI"]).count()
        if "TIPO_PROTOC_JUSTIF_UCI" in df.columns:
            nr_registros_expurgo_uc_prot = pd.to_numeric(df["TIPO_PROTOC_JUSTIF_UCI"], errors='coerce').fillna(0).astype(int).apply(lambda x: x > 0).sum()
        
        expurgo_consistente = (nr_registros_expurgo == nr_registros_expurgo_tipo_prot) and (nr_registros_expurgo_uc == nr_registros_expurgo_uc_prot)
        
        nr_interrupcoes = df["PID_INTRP_CONJTO_PIN"].nunique() if "PID_INTRP_CONJTO_PIN" in df.columns else 0
        
        df_validacao_tamanho_data = validar_tam_campo_data(df)
        df_duracao_incorreta = validar_data_intrp(df)
        df_contagem_intrp = validar_contagem_intrp(df)

        logger.info("Resumo do arquivo %s:", nome_arq)
        logger.info("  Colunas                           : %d", nr_colunas)
        logger.info("  Linhas                            : %d", nr_linhas)
        logger.info("  Número de interrupções            : %d", nr_interrupcoes)

        if not df.empty and "DATA_HORA_INIC_INTRP" in df.columns:
            # Pular valores NaT / null para o .min() e .max()
            datas = df['DATA_HORA_INIC_INTRP'].dropna()
            if not datas.empty:
                logger.info("  Data intrp. mais antiga           : %s", datas.min())
                logger.info("  Data intrp. mais recente          : %s", datas.max())

        if expurgo_consistente:
            logger.info("  Tem expurgo                       : %s", "Sim" if nr_registros_expurgo > 0 else "Não")
            if (nr_registros_expurgo + nr_registros_expurgo_uc) > 0:
                logger.info("    Protocolos por intrp.           : %d", nr_registros_expurgo)
                logger.info("    Protocolos por UC.              : %d", nr_registros_expurgo_uc)
        else:
            logger.error("  Tem expurgo                       : *** DADOS INCONSISTENTES - VERIFICAR ***")
            erros_fatais += 1

        if not df_duracao_incorreta.empty:
            logger.error("  Data de início INTRP inconsistente: Sim (%d erros encontrados)", len(df_duracao_incorreta))
            erros_fatais += 1
        else:
            logger.info("  Data de início INTRP inconsistente: Não")

        if not df_validacao_tamanho_data.empty:
            logger.error("  Datas com tamanho inconsistente   : Sim (%d erros encontrados)", len(df_validacao_tamanho_data))
            erros_fatais += 1
        else:
            logger.info("  Datas com tamanho inconsistente   : Não")

        if len(df_contagem_intrp) > 0:
            logger.error("  Divergências na contagem de usuários afetados: Sim (%d divergências)", len(df_contagem_intrp))
            erros_fatais += 1
            
    if erros_fatais > 0:
        logger.error("Validação finalizada com %d inconsistência(s) detectada(s) nas exportações IQS!", erros_fatais)
    else:
        logger.info("Validação finalizada. Todos os arquivos inspecionados estão consistentes.")

if __name__ == "__main__":
    executar_validacoes()
