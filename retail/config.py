"""Paths, source and analysis constants."""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
INTERIM_DIR = ROOT / "data" / "interim"
SQL_DIR = ROOT / "sql"
DOCS_DATA_DIR = ROOT / "docs" / "data"
REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"

DATA_URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
ZIP_FILE = RAW_DIR / "online_retail_ii.zip"
PARQUET_FILE = INTERIM_DIR / "transactions.parquet"

# A sale line priced above this multiple of its product's median price is a keying error (the data
# have a clean gap: nothing between 75x and 100x, then a 60-piece price charged per piece and similar).
PRICE_ERROR_FACTOR = 100

# Two comparable 12-month years (the data run from 1 Dec 2009 to 9 Dec 2011)
YEAR1 = (pd.Timestamp("2009-12-01"), pd.Timestamp("2010-12-01"))
YEAR2 = (pd.Timestamp("2010-12-01"), pd.Timestamp("2011-12-01"))
LAST_FULL_MONTH_END = YEAR2[1]  # December 2011 has only eight trading days
SNAPSHOT = pd.Timestamp("2011-12-10")  # day after the last invoice, for RFM recency

# Repurchase model: predict a purchase in the 90 days after a cutoff from history before it.
# Training cutoffs step back a quarter at a time, so the oldest covers the same season as the test.
HORIZON_DAYS = 90
TEST_CUTOFF = pd.Timestamp("2011-09-11")  # labels: 11 Sep - 9 Dec 2011
TRAIN_CUTOFFS = [TEST_CUTOFF - pd.Timedelta(days=HORIZON_DAYS * k) for k in (1, 2, 3, 4)]
TOP_SHARE = 0.2  # campaign size used for the "revenue captured" metric

BASKET_TOP_PRODUCTS = 400
BASKET_MIN_TOGETHER = 60
RANDOM_STATE = 11
N_BOOT = 300
