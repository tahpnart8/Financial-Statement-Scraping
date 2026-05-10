import sys
import pandas as pd
from vnstock.api.financial import Finance

def test_kbs():
    try:
        finance = Finance(symbol="DMC", source="kbs")
        df = finance.income_statement(period="year", lang="vi")
        print(df.head())
        print(df.columns)
    except Exception as e:
        print(f"Error: {e}")

test_kbs()
