import pandas as pd

# ============================
# Funções para cálculo de indicadores
# ============================

def calcular_receita_bruta_total(df: pd.DataFrame) -> float:
    """
    Calcula Receita Bruta Total = RECEITA DE INDENIZAÇÃO + RECEITA MAO DE OBRA + RECEITA LOCAÇÃO
    """
    receitas = ["RECEITA DE INDENIZAÇÃO", "RECEITA MAO DE OBRA", "RECEITA LOCAÇÃO"]
    return df[df["Análise de emissão"].isin(receitas)].select_dtypes(include="number").sum().sum()


def calcular_impostos_sobre_receita(receita_bruta_total: float) -> float:
    """
    Calcula Impostos sobre Receita = 11% da Receita Bruta Total
    """
    return receita_bruta_total * 0.11


def calcular_custo_total(df: pd.DataFrame) -> float:
    """
    Calcula Custo Total = CUSTO COM MAO DE OBRA + CUSTO COM INSUMOS + Depreciação de ativo (+) + LOCAÇÃO DE EQUIPAMENTOS
    """
    custos = [
        "CUSTO COM MAO DE OBRA",
        "CUSTO COM INSUMOS",
        "Depreciação de ativo (+)",
        "LOCAÇÃO DE EQUIPAMENTOS"
    ]
    return df[df["Análise de emissão"].isin(custos)].select_dtypes(include="number").sum().sum()


def calcular_lucro_bruto(df: pd.DataFrame) -> float:
    """
    Calcula Lucro Bruto (MC) = Receita Bruta Total - Impostos sobre Receita - Custo Total
    """
    receita_bruta = calcular_receita_bruta_total(df)
    impostos = calcular_impostos_sobre_receita(receita_bruta)
    custo_total = calcular_custo_total(df)

    return receita_bruta - impostos - custo_total


def calcular_todos_indicadores(df: pd.DataFrame) -> dict:
    """
    Retorna um dicionário com todos os indicadores para exibição.
    """
    receita_bruta = calcular_receita_bruta_total(df)
    impostos = calcular_impostos_sobre_receita(receita_bruta)
    custo_total = calcular_custo_total(df)
    lucro_bruto = receita_bruta - impostos - custo_total

    return {
        "Receita Bruta Total (R$)": receita_bruta,
        "Impostos sobre Receita (R$)": impostos,
        "Custo Total (R$)": custo_total,
        "Lucro Bruto (MC) (R$)": lucro_bruto
    }
