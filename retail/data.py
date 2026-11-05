"""Download the UCI Online Retail II workbook once and cache it as Parquet for DuckDB."""
from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path

import pandas as pd
import requests

from . import config

# SHA-256 of the UCI archive, so a changed or truncated download is caught.
EXPECTED_SHA256 = "572e36277c2390fbfde10664750731e0a86f55e33470d91919085f0408e67bfb"

COLUMNS = {
    "Invoice": "invoice", "StockCode": "stock_code", "Description": "description", "Quantity": "quantity",
    "InvoiceDate": "invoice_date", "Price": "price", "Customer ID": "customer_id", "Country": "country",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(path: Path = config.ZIP_FILE, timeout: int = 300) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(config.DATA_URL, stream=True, timeout=timeout) as resp:
        resp.raise_for_status()
        with path.open("wb") as f:
            for chunk in resp.iter_content(1 << 20):
                f.write(chunk)
    digest = sha256(path)
    if digest != EXPECTED_SHA256:
        raise ValueError(f"Unexpected checksum for {path.name}: {digest}")
    return path


def read_workbook(zip_path: Path = config.ZIP_FILE) -> pd.DataFrame:
    """Both sheets (Dec 2009 - Dec 2010 and Dec 2010 - Dec 2011) as one frame with snake_case columns."""
    with zipfile.ZipFile(zip_path) as zf:
        member = next(n for n in zf.namelist() if n.lower().endswith(".xlsx"))
        book = io.BytesIO(zf.read(member))
    sheets = pd.read_excel(book, sheet_name=None, dtype={"Invoice": str, "StockCode": str, "Description": str, "Country": str},
                           engine="openpyxl")
    df = pd.concat(sheets.values(), ignore_index=True).rename(columns=COLUMNS)[list(COLUMNS.values())]
    df["invoice"] = df["invoice"].str.strip()
    df["stock_code"] = df["stock_code"].str.strip().str.upper()
    df["description"] = df["description"].str.strip()
    df["customer_id"] = df["customer_id"].astype("Int64")
    df["invoice_date"] = pd.to_datetime(df["invoice_date"])
    return df


def ensure_data(refresh: bool = False) -> Path:
    """Path to the cached Parquet file, downloading and converting the workbook if needed (a few minutes, once)."""
    if refresh or not config.ZIP_FILE.exists():
        download()
    if refresh or not config.PARQUET_FILE.exists():
        df = read_workbook()
        config.PARQUET_FILE.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(config.PARQUET_FILE, index=False)
    return config.PARQUET_FILE
