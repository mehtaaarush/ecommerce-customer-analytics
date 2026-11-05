import pandas as pd
import pytest

from retail import db

COLUMNS = ["invoice", "stock_code", "description", "quantity", "invoice_date", "price", "customer_id", "country"]


def line(invoice, stock_code, quantity, price, when, customer=12345, description="ITEM", country="United Kingdom"):
    return {"invoice": invoice, "stock_code": stock_code, "description": description, "quantity": quantity,
            "invoice_date": pd.Timestamp(when), "price": float(price), "customer_id": customer, "country": country}


def frame(rows) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=COLUMNS)
    df["customer_id"] = df["customer_id"].astype("Int64")
    df["quantity"] = df["quantity"].astype("int64")
    return df


@pytest.fixture
def connect():
    """Open a DuckDB session over synthetic raw lines, with the real cleaning SQL applied."""
    def _connect(rows):
        return db.connect(raw=frame(rows))
    return _connect
