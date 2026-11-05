"""End-to-end run: python -m retail.pipeline

Downloads the transactions (once), cleans them in DuckDB, runs the KPI, cohort, RFM, repurchase-model
and market-basket analyses, and writes docs/data/dashboard.json, reports/*.csv and reports/figures/*.png."""
from __future__ import annotations

import argparse
import time

import pandas as pd

from . import basket, cohorts, config, data, db, export, figures, kpis, repurchase, rfm


def run(refresh: bool = False) -> dict:
    t0 = time.time()
    con = db.connect(data.ensure_data(refresh))
    raw_rows = con.execute("SELECT COUNT(*) FROM raw_lines").fetchone()[0]
    first, last = con.execute("SELECT MIN(invoice_date), MAX(invoice_date) FROM raw_lines").fetchone()
    print(f"Loaded and cleaned {raw_rows:,} lines ({time.time() - t0:.0f}s)")

    funnel = kpis.funnel(con)
    monthly = kpis.monthly(con)
    yoy = kpis.yoy(kpis.yearly(con, monthly))
    timing = kpis.weekday_hour(con)
    saturday_orders = int(timing.loc["Sat"].sum()) if "Sat" in timing.index else 0
    timing = timing.drop(index="Sat", errors="ignore")  # the business barely trades on Saturdays
    products = kpis.products(con)
    pareto = kpis.pareto(products)
    countries = kpis.countries(con)

    mats = cohorts.matrices(cohorts.cohort_activity(con))
    avg_retention = cohorts.average_curve(mats["retention"], mats["sizes"])
    avg_value = cohorts.average_curve(mats["value"], mats["sizes"])
    milestones = cohorts.milestone_retention(mats["retention"])

    scored = rfm.score(rfm.customers(con))
    summary, grid, validation = rfm.summary(scored), rfm.grid(scored), rfm.validate(con)
    print(f"KPIs, cohorts and RFM done ({time.time() - t0:.0f}s): {len(scored):,} customers segmented")

    model = repurchase.evaluate(con)
    outlook = repurchase.segment_outlook(model["now"])
    test_auc = model["metrics"].set_index("key")["roc_auc"]
    print(f"Repurchase model done ({time.time() - t0:.0f}s): selected {model['selected']}, test ROC AUC "
          f"{test_auc[model['selected']]:.3f} vs RFM {test_auc['rfm']:.3f}")

    rules = basket.rules(basket.pairs(con))
    sizes = basket.basket_sizes(con)

    payload = export.dashboard_payload(
        funnel=funnel, monthly=monthly, yoy=yoy, weekday_hour=timing,
        cohort=export.cohort_payload(mats, avg_retention, avg_value, milestones),
        rfm_part=export.rfm_payload(summary, grid, validation, outlook),
        model=export.model_payload(model), products=products, pareto=pareto,
        basket=export.basket_payload(rules, products, sizes), countries=countries,
        raw_rows=raw_rows, date_range=(first.strftime("%Y-%m-%d %H:%M"), last.strftime("%Y-%m-%d %H:%M")),
    )
    payload["meta"]["saturday_orders"] = saturday_orders
    out = export.write_json(payload, config.DOCS_DATA_DIR / "dashboard.json")
    print(f"Wrote {out.relative_to(config.ROOT)} ({out.stat().st_size / 1e3:.0f} KB)")

    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    funnel.to_csv(config.REPORTS_DIR / "cleaning_funnel.csv", index=False)
    yoy.round(4).to_csv(config.REPORTS_DIR / "yearly_kpis.csv", index_label="metric")
    monthly.assign(month=monthly["month"].dt.strftime("%Y-%m")).round(2).to_csv(
        config.REPORTS_DIR / "monthly_kpis.csv", index=False)
    mats["retention"].round(4).rename(index=lambda c: c.strftime("%Y-%m")).to_csv(
        config.REPORTS_DIR / "cohort_retention.csv", index_label="cohort")
    summary.merge(validation[["segment", "repurchase_rate", "future_revenue_share"]], on="segment").merge(
        outlook[["segment", "mean_propensity", "expected_buyers"]], on="segment").round(4).to_csv(
        config.REPORTS_DIR / "rfm_segments.csv", index=False)
    pd.concat([model["selection"].assign(split="validation"), model["metrics"].assign(split="test")]).round(4).to_csv(
        config.REPORTS_DIR / "repurchase_model_metrics.csv", index=False)
    names = products.set_index("stock_code")["description"]
    rules.head(1000).assign(antecedent_name=lambda d: d["antecedent"].map(names),
                            consequent_name=lambda d: d["consequent"].map(names)).round(4).to_csv(
        config.REPORTS_DIR / "basket_rules.csv", index=False)

    model_names = {k: c.name for k, c in repurchase.candidates().items()}
    for path in figures.all_figures(monthly, mats["retention"], summary, export.model_payload(model), model_names):
        print(f"Wrote {path.relative_to(config.ROOT)}")
    print(f"Done in {time.time() - t0:.0f}s")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="re-download and re-convert the source data")
    run(parser.parse_args().refresh)
