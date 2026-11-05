"""Assemble the JSON the dashboard reads. Everything is computed in Python and SQL; the page only renders."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from . import config, rfm

BASKET_ITEMS = 150  # products offered in the dashboard's "bought together" picker
RULES_PER_ITEM = 6


def _clean(obj, digits: int = 6):
    """JSON-safe copy with floats rounded (numpy scalars, arrays and timestamps included)."""
    if isinstance(obj, dict):
        return {str(k): _clean(v, digits) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v, digits) for v in obj]
    if isinstance(obj, np.ndarray):
        return [_clean(v, digits) for v in obj.tolist()]
    if isinstance(obj, pd.DataFrame):
        return [_clean(r, digits) for r in obj.to_dict(orient="records")]
    if isinstance(obj, pd.Series):
        return _clean(obj.to_numpy(), digits)
    if isinstance(obj, pd.Timestamp):
        return obj.strftime("%Y-%m-%d")
    if obj is pd.NA or obj is pd.NaT:
        return None
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        return None if not np.isfinite(obj) else round(float(obj), digits)
    return obj


def _matrix(df: pd.DataFrame) -> list:
    return [[None if pd.isna(v) else float(v) for v in row] for row in df.to_numpy()]


def kpi_payload(yoy: pd.DataFrame) -> dict:
    keep = ["net_revenue", "orders", "aov", "customers", "repeat_rate", "revenue_guest"]
    out = {k: {"year1": yoy.loc[k, "year1"], "year2": yoy.loc[k, "year2"], "change": yoy.loc[k, "change"]} for k in keep}
    for year in ["year1", "year2"]:
        total = yoy.loc["net_revenue", year]
        out.setdefault("guest_share", {})[year] = yoy.loc["revenue_guest", year] / total
    out["guest_share"]["change"] = out["guest_share"]["year2"] - out["guest_share"]["year1"]
    out["mix_year2"] = {k: yoy.loc[f"revenue_{k}", "year2"] / yoy.loc["net_revenue", "year2"] for k in ["new", "returning", "guest"]}
    out["new_customers_year2"] = yoy.loc["new_customers", "year2"]
    return out


def cohort_payload(mats: dict, avg_retention: pd.Series, avg_value: pd.Series, milestones: pd.DataFrame) -> dict:
    ret, val = mats["retention"], mats["value"]
    return {
        "cohorts": [c.strftime("%Y-%m") for c in ret.index],
        "months": [int(m) for m in ret.columns],
        "sizes": mats["sizes"].to_numpy(),
        "retention": _matrix(ret),
        "value": _matrix(val),
        "avg_retention": {"months": avg_retention.index.to_numpy(), "value": avg_retention.to_numpy()},
        "avg_value": {"months": avg_value.index.to_numpy(), "value": avg_value.to_numpy()},
        "milestones": milestones.reset_index().assign(cohort=lambda d: d["cohort"].dt.strftime("%Y-%m")),
    }


def rfm_payload(summary: pd.DataFrame, grid: pd.DataFrame, validation: pd.DataFrame, outlook: pd.DataFrame) -> dict:
    v = validation.set_index("segment")[["repurchase_rate", "revenue_per_customer", "future_revenue_share", "customers"]]
    v = v.rename(columns={"customers": "validation_customers", "revenue_per_customer": "validation_revenue_per_customer"})
    o = outlook.set_index("segment")[["mean_propensity", "expected_buyers", "expected_buyer_share"]]
    seg = summary.set_index("segment").join(v).join(o).reset_index()
    return {
        "order": rfm.SEGMENT_ORDER,
        "segments": seg,
        "grid": grid,
        "f_labels": rfm.F_LABELS,
    }


def model_payload(res: dict) -> dict:
    test = res["test"]
    rev = test["future_revenue"].clip(lower=0)
    return {
        "selected": res["selected"],
        "selection": res["selection"],
        "metrics": res["metrics"],
        "bootstrap": res["bootstrap"],
        "gains": res["gains"],
        "deciles": res["deciles"],
        "importance": res["importance"],
        "windows": res["windows"],
        "n_train": res["n_train"],
        "n_test": res["n_test"],
        "test_buyers": int(test["bought"].sum()),
        "test_revenue": float(rev.sum()),
        "top_share": config.TOP_SHARE,
        "horizon_days": config.HORIZON_DAYS,
        "n_boot": config.N_BOOT,
    }


def basket_payload(rules: pd.DataFrame, prod: pd.DataFrame, sizes: dict) -> dict:
    names = prod.set_index("stock_code")["description"]
    invoices = rules.drop_duplicates("antecedent").set_index("antecedent")["antecedent_invoices"]
    items = invoices.sort_values(ascending=False).head(BASKET_ITEMS)
    picked = (rules[rules["antecedent"].isin(items.index)]
              .sort_values(["antecedent", "lift"], ascending=[True, False])
              .groupby("antecedent", sort=False).head(RULES_PER_ITEM))
    cols = ["antecedent", "consequent", "together", "support", "confidence", "lift"]
    # strongest pairs bought by at least 1% of orders, each shown once in its higher-confidence direction
    strong = rules[rules["support"] >= 0.01].sort_values(["lift", "confidence"], ascending=False)
    pair = np.where(strong["antecedent"] < strong["consequent"], strong["antecedent"] + "|" + strong["consequent"],
                    strong["consequent"] + "|" + strong["antecedent"])
    top = strong.assign(pair=pair).drop_duplicates("pair").head(10)
    return {
        "sizes": sizes,
        "items": [{"code": c, "name": names.get(c, c), "invoices": int(n)} for c, n in items.items()],
        "names": {c: names.get(c, c) for c in set(picked["antecedent"]) | set(picked["consequent"]) | set(top["antecedent"]) | set(top["consequent"])},
        "rules": picked[cols],
        "top_rules": top[cols],
        "n_rules": len(rules),
        "n_pairs": len(rules) // 2,
        "top_products": config.BASKET_TOP_PRODUCTS,
        "min_together": config.BASKET_MIN_TOGETHER,
    }


def dashboard_payload(funnel, monthly, yoy, weekday_hour, cohort, rfm_part, model, products, pareto, basket, countries,
                      raw_rows: int, date_range: tuple) -> dict:
    payload = {
        "meta": {
            "generated": date.today().isoformat(),
            "raw_rows": raw_rows,
            "first_invoice": date_range[0],
            "last_invoice": date_range[1],
            "year1": [d.strftime("%Y-%m-%d") for d in config.YEAR1],
            "year2": [d.strftime("%Y-%m-%d") for d in config.YEAR2],
            "snapshot": config.SNAPSHOT.strftime("%Y-%m-%d"),
            "currency": "GBP",
            "price_error_factor": config.PRICE_ERROR_FACTOR,
        },
        "kpis": kpi_payload(yoy),
        "funnel": funnel,
        "monthly": monthly,
        "weekday_hour": {
            "weekdays": list(weekday_hour.index),
            "hours": [int(h) for h in weekday_hour.columns],
            "orders": weekday_hour.to_numpy(),
        },
        "cohorts": cohort,
        "rfm": rfm_part,
        "model": model,
        "products": {"top": products.head(15), "pareto": pareto},
        "basket": basket,
        "countries": countries,
    }
    return _clean(payload)


def write_json(payload: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    return path
