"""Monthly acquisition cohorts: retention and cumulative revenue per acquired customer."""
from __future__ import annotations

import pandas as pd

from . import config, db


def cohort_activity(con) -> pd.DataFrame:
    return db.query(con, "05_cohorts.sql", end=config.LAST_FULL_MONTH_END)


def matrices(activity: pd.DataFrame, drop_first: bool = True) -> dict:
    """Retention (share of the cohort active N months later) and cumulative revenue per acquired customer.

    The first cohort is dropped by default: the data begin in December 2009, so that month mixes newly
    acquired customers with everyone who was already buying."""
    act = activity.copy()
    if drop_first:
        act = act[act["cohort"] > act["cohort"].min()]
    last = config.LAST_FULL_MONTH_END - pd.offsets.MonthBegin(1)

    def reached(cohort: pd.Timestamp) -> int:
        return (last.year - cohort.year) * 12 + last.month - cohort.month

    active = act.pivot(index="cohort", columns="months_since", values="active_customers")
    ages = range(0, max(reached(c) for c in active.index) + 1)
    active = active.reindex(columns=ages)
    revenue = act.pivot(index="cohort", columns="months_since", values="revenue").reindex(columns=ages)
    sizes = active[0].astype(int)
    retention = active.div(sizes, axis=0)
    # months a cohort could not yet have reached stay empty; months it reached with nobody active are 0
    for cohort in retention.index:
        seen = retention.columns <= reached(cohort)
        retention.loc[cohort, seen] = retention.loc[cohort, seen].fillna(0)
        revenue.loc[cohort, seen] = revenue.loc[cohort, seen].fillna(0)
    value = revenue.cumsum(axis=1, skipna=False).div(sizes, axis=0)
    return {"sizes": sizes, "retention": retention, "value": value}


def average_curve(matrix: pd.DataFrame, sizes: pd.Series, min_cohorts: int = 6) -> pd.Series:
    """Size-weighted average across the cohorts that have reached each age (ages reached by too few are dropped)."""
    observed = matrix.notna()
    weights = observed.mul(sizes, axis=0)
    curve = (matrix.fillna(0) * weights).sum() / weights.sum()
    return curve[observed.sum() >= min_cohorts]


def milestone_retention(retention: pd.DataFrame, months=(1, 3, 6)) -> pd.DataFrame:
    """Retention at fixed ages for each cohort, to see whether newer cohorts hold on to customers worse."""
    return pd.DataFrame({f"m{m}": retention[m] for m in months if m in retention.columns})
