"""Market basket analysis: association rules between products bought on the same invoice."""
from __future__ import annotations

import pandas as pd

from . import config, db


def pairs(con) -> pd.DataFrame:
    return db.query(con, "07_basket_pairs.sql", top_n=config.BASKET_TOP_PRODUCTS, min_together=config.BASKET_MIN_TOGETHER)


def rules(pair_counts: pd.DataFrame) -> pd.DataFrame:
    """Both directions of every pair: support, confidence (P(B | A)) and lift (confidence / P(B))."""
    def direction(a: str, b: str) -> pd.DataFrame:
        return pd.DataFrame({
            "antecedent": pair_counts[f"item_{a}"], "consequent": pair_counts[f"item_{b}"],
            "together": pair_counts["together"], "antecedent_invoices": pair_counts[f"invoices_{a}"],
            "consequent_invoices": pair_counts[f"invoices_{b}"], "invoices": pair_counts["total_invoices"],
        })

    r = pd.concat([direction("a", "b"), direction("b", "a")], ignore_index=True)
    r["support"] = r["together"] / r["invoices"]
    r["confidence"] = r["together"] / r["antecedent_invoices"]
    r["lift"] = r["confidence"] / (r["consequent_invoices"] / r["invoices"])
    return r.sort_values(["lift", "together"], ascending=False, ignore_index=True)


def recommendations(r: pd.DataFrame, items: list[str], per_item: int = 6) -> pd.DataFrame:
    """'Frequently bought together' for each item: the consequents with the highest lift."""
    sub = r[r["antecedent"].isin(items)]
    return (sub.sort_values(["antecedent", "lift"], ascending=[True, False])
            .groupby("antecedent", sort=False).head(per_item).reset_index(drop=True))


def basket_sizes(con) -> dict:
    s = db.query(con, "11_basket_sizes.sql").iloc[0]
    return {k: float(v) for k, v in s.items()}
