"""RFM segmentation: recency and monetary quintiles, fixed frequency bands, and an R x F segment map."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config, db

# Rows are the recency score (5 = most recent), columns the frequency score 1..5.
SEGMENT_GRID = {
    5: ["New customers", "Potential loyalists", "Potential loyalists", "Champions", "Champions"],
    4: ["Promising", "Potential loyalists", "Potential loyalists", "Loyal", "Loyal"],
    3: ["About to sleep", "About to sleep", "Need attention", "Loyal", "Loyal"],
    2: ["Hibernating", "Hibernating", "At risk", "At risk", "Can't lose them"],
    1: ["Lost", "Lost", "At risk", "At risk", "Can't lose them"],
}
SEGMENT_ORDER = ["Champions", "Loyal", "Potential loyalists", "New customers", "Promising", "Need attention",
                 "About to sleep", "Can't lose them", "At risk", "Hibernating", "Lost"]
ACTIONS = {
    "Champions": "Reward and retain: early access, referral asks; no discounts needed.",
    "Loyal": "Upsell higher-value ranges and bundles from their usual categories.",
    "Potential loyalists": "Push the next order: replenishment reminders and loyalty perks.",
    "New customers": "Onboard: welcome series and best-sellers to drive a second order.",
    "Promising": "Build the habit with recommendations based on the first basket.",
    "Need attention": "Time-limited offers on the categories they buy most.",
    "About to sleep": "Low-cost reactivation before they lapse: seasonal range launches.",
    "Can't lose them": "Former top buyers gone quiet: personal outreach from account managers.",
    "At risk": "Win-back campaign with a meaningful incentive.",
    "Hibernating": "Include only in low-cost seasonal campaigns.",
    "Lost": "Suppress from paid campaigns; one last-chance offer at most.",
}
# Frequency is heavily tied (a quarter of customers ordered once), so it uses fixed bands rather than quintiles.
F_BANDS = [0, 1, 2, 4, 9, np.inf]
F_LABELS = ["1 order", "2 orders", "3–4 orders", "5–9 orders", "10+ orders"]


def customers(con, as_of: pd.Timestamp = config.SNAPSHOT) -> pd.DataFrame:
    """Every identified customer with at least one completed order before `as_of`."""
    return db.query(con, "06_customer_features.sql", cutoff=as_of, horizon=config.HORIZON_DAYS)


def _quintile(values: pd.Series, ascending: bool = True) -> pd.Series:
    ranks = values.rank(method="first", ascending=ascending)
    return pd.qcut(ranks, 5, labels=[1, 2, 3, 4, 5]).astype(int)


def score(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["r_score"] = _quintile(out["recency_days"], ascending=False)  # fewest days since last order -> 5
    out["f_score"] = pd.cut(out["frequency"], F_BANDS, labels=[1, 2, 3, 4, 5]).astype(int)
    out["m_score"] = _quintile(out["monetary"])
    out["rfm_score"] = out["r_score"] + out["f_score"] + out["m_score"]
    out["segment"] = [SEGMENT_GRID[r][f - 1] for r, f in zip(out["r_score"], out["f_score"])]
    return out


def summary(scored: pd.DataFrame) -> pd.DataFrame:
    g = scored.groupby("segment")
    out = pd.DataFrame({
        "customers": g.size(),
        "revenue": g["monetary"].sum(),
        "median_recency": g["recency_days"].median(),
        "median_frequency": g["frequency"].median(),
        "median_monetary": g["monetary"].median(),
        "mean_monetary": g["monetary"].mean(),
    }).reindex(SEGMENT_ORDER).dropna(subset=["customers"])
    out["customer_share"] = out["customers"] / out["customers"].sum()
    out["revenue_share"] = out["revenue"] / out["revenue"].sum()
    out["action"] = out.index.map(ACTIONS)
    return out.reset_index(names="segment")


def grid(scored: pd.DataFrame) -> pd.DataFrame:
    """Customers and revenue in each R x F cell, with the segment the cell maps to."""
    g = scored.groupby(["r_score", "f_score"]).agg(customers=("customer_id", "size"), revenue=("monetary", "sum"))
    cells = pd.MultiIndex.from_product([[5, 4, 3, 2, 1], [1, 2, 3, 4, 5]], names=["r_score", "f_score"])
    g = g.reindex(cells, fill_value=0).reset_index()
    g["segment"] = [SEGMENT_GRID[r][f - 1] for r, f in zip(g["r_score"], g["f_score"])]
    return g


def validate(con, cutoff: pd.Timestamp = config.TEST_CUTOFF) -> pd.DataFrame:
    """Out-of-time check: segments assigned at `cutoff`, then who bought in the following 90 days."""
    scored = score(customers(con, cutoff))
    scored["bought"] = scored["future_orders"] > 0
    g = scored.groupby("segment")
    out = pd.DataFrame({
        "customers": g.size(),
        "repurchase_rate": g["bought"].mean(),
        "revenue_per_customer": g["future_revenue"].mean(),
        "future_revenue": g["future_revenue"].sum(),
    }).reindex(SEGMENT_ORDER).dropna(subset=["customers"])
    out["future_revenue_share"] = out["future_revenue"] / scored["future_revenue"].sum()
    return out.reset_index(names="segment")
