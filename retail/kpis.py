"""Trading KPIs from the cleaned lines: the cleaning funnel, monthly and yearly trends, order timing,
products and countries. The heavy lifting is SQL; this module only reshapes the results."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config, db

STATUS_ORDER = ["sale", "cancellation", "duplicate", "non-product", "invalid quantity or price", "price error"]
STATUS_LABELS = {
    "sale": "Product sales",
    "cancellation": "Cancellations (netted from revenue)",
    "duplicate": "Exact duplicate lines",
    "non-product": "Postage, fees and manual adjustments",
    "invalid quantity or price": "Zero-price lines and stock write-offs",
    "price error": "Price keying errors",
}
KEPT = {"sale", "cancellation"}
WEEKDAYS = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun"}


def funnel(con) -> pd.DataFrame:
    f = db.query(con, "02_funnel.sql").set_index("status").reindex(STATUS_ORDER, fill_value=0).reset_index()
    f["share"] = f["lines"] / f["lines"].sum()
    f["label"] = f["status"].map(STATUS_LABELS)
    f["kept"] = f["status"].isin(KEPT)
    return f


def monthly(con) -> pd.DataFrame:
    m = db.query(con, "03_monthly.sql")
    m["aov"] = m["gross_sales"] / m["orders"]
    m["partial"] = m["month"] >= config.LAST_FULL_MONTH_END
    return m


def _period(month: pd.Series) -> pd.Series:
    out = pd.Series(pd.NA, index=month.index, dtype="object")
    for name, (start, end) in {"year1": config.YEAR1, "year2": config.YEAR2}.items():
        out[(month >= start) & (month < end)] = name
    return out


def yearly(con, monthly_kpis: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per comparable year with revenue, orders, customers, AOV, repeat rate and the revenue mix."""
    y = db.query(con, "04_yearly.sql", year1_start=config.YEAR1[0], year1_end=config.YEAR1[1],
                 year2_start=config.YEAR2[0], year2_end=config.YEAR2[1]).set_index("period")
    y["aov"] = y["gross_sales"] / y["orders"]
    m = monthly(con) if monthly_kpis is None else monthly_kpis
    mix = m.assign(period=_period(m["month"])).dropna(subset=["period"]).groupby("period")[
        ["new_customers", "revenue_new", "revenue_returning", "revenue_guest"]].sum()
    return y.join(mix)


def yoy(y: pd.DataFrame) -> pd.DataFrame:
    """Year-on-year comparison: relative change for amounts and counts, point change for rates."""
    out = y.T.copy()
    out["change"] = out["year2"] / out["year1"] - 1
    out.loc["repeat_rate", "change"] = out.loc["repeat_rate", "year2"] - out.loc["repeat_rate", "year1"]
    return out


def weekday_hour(con) -> pd.DataFrame:
    """Orders by weekday (rows, Monday first) and hour of day (columns)."""
    w = db.query(con, "10_weekday_hour.sql")
    grid = w.pivot(index="weekday", columns="hour", values="orders").fillna(0).astype(int)
    return grid.rename(index=WEEKDAYS)


def products(con) -> pd.DataFrame:
    return db.query(con, "08_products.sql")


def pareto(prod: pd.DataFrame, points: int = 101) -> dict:
    """How concentrated revenue is: the cumulative revenue share against the share of products."""
    rev = np.sort(prod["net_revenue"].clip(lower=0).to_numpy())[::-1]
    cum = np.cumsum(rev) / rev.sum()
    n = len(rev)
    grid = np.linspace(0, 1, points)
    idx = np.clip(np.ceil(grid * n).astype(int) - 1, 0, n - 1)
    curve = np.where(grid == 0, 0.0, cum[idx])
    n80 = int(np.searchsorted(cum, 0.8) + 1)
    return {
        "products": n,
        "products_for_80": n80,
        "share_for_80": n80 / n,
        "top20_share": float(cum[int(np.ceil(0.2 * n)) - 1]),
        "curve": {"product_share": grid, "revenue_share": curve},
    }


def countries(con, top: int = 8) -> pd.DataFrame:
    c = db.query(con, "09_countries.sql")
    head, tail = c.iloc[:top].copy(), c.iloc[top:]
    other = pd.DataFrame([{"country": f"Other ({len(tail)} countries)", "net_revenue": tail["net_revenue"].sum(),
                           "orders": tail["orders"].sum(), "customers": tail["customers"].sum()}])
    out = pd.concat([head, other], ignore_index=True)
    out["revenue_share"] = out["net_revenue"] / c["net_revenue"].sum()
    return out
