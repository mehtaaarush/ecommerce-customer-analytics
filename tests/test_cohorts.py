import pandas as pd

from retail import cohorts, config, db

from .conftest import line


def test_month_zero_is_full_retention_and_later_months_are_shares(connect):
    rows = [
        line("0001", "10001", 1, 5.0, "2010-12-03 10:00", 1),   # first cohort: dropped (left-censored)
        line("0002", "10001", 1, 5.0, "2011-01-10 10:00", 2),
        line("0003", "10001", 1, 5.0, "2011-01-12 10:00", 3),
        line("0004", "10001", 1, 5.0, "2011-02-15 10:00", 2),   # customer 2 comes back a month later
        line("C0005", "10001", -1, 5.0, "2011-03-15 10:00", 3),  # a cancellation alone is not activity
        line("0006", "10001", 2, 5.0, "2011-02-20 10:00", 4),
    ]
    act = db.query(connect(rows), "05_cohorts.sql", end=config.LAST_FULL_MONTH_END)
    mats = cohorts.matrices(act)
    ret = mats["retention"]
    assert list(ret.index) == [pd.Timestamp("2011-01-01"), pd.Timestamp("2011-02-01")]
    assert (ret[0] == 1.0).all()
    assert ret.loc[pd.Timestamp("2011-01-01"), 1] == 0.5
    assert ret.loc[pd.Timestamp("2011-01-01"), 2] == 0.0  # reached, nobody active
    assert mats["sizes"].tolist() == [2, 1]
    assert mats["value"].loc[pd.Timestamp("2011-01-01"), 1] == 7.5  # (5 + 5 + 5) / 2 customers


def test_average_curve_weights_by_cohort_size():
    idx = pd.to_datetime(["2011-01-01", "2011-02-01"])
    matrix = pd.DataFrame({0: [1.0, 1.0], 1: [0.5, 0.2]}, index=idx)
    sizes = pd.Series([100, 300], index=idx)
    curve = cohorts.average_curve(matrix, sizes, min_cohorts=1)
    assert curve[0] == 1.0
    assert abs(curve[1] - (0.5 * 100 + 0.2 * 300) / 400) < 1e-12
