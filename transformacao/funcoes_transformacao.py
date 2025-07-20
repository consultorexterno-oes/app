import pandas as pd
from configuracoes.config import COLUNAS_ID

def converter_para_longo(df, semana, colunas_meses):
    # Garante que só colunas de meses realmente existentes serão usadas
    colunas_meses_validas = [col for col in colunas_meses if col in df.columns]
    if not colunas_meses_validas:
        raise ValueError("Nenhuma coluna de mês válida encontrada no DataFrame.")

    # Garante que as colunas de ID também estão presentes
    colunas_id_validas = [col for col in COLUNAS_ID if col in df.columns]
    if len(colunas_id_validas) < len(COLUNAS_ID):
        faltantes = list(set(COLUNAS_ID) - set(colunas_id_validas))
        raise ValueError(f"As seguintes colunas de ID estão faltando no DataFrame: {faltantes}")

    # Executa o melt
    df_longo = pd.melt(
        df,
        id_vars=colunas_id_validas,
        value_vars=colunas_meses_validas,
        var_name="Mes",
        value_name="Valor"
    )

    # Adiciona a semana
    df_longo["Semana"] = semana
    return df_longo
