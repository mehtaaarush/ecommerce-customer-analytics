import numpy as np
import pandas as pd
import pytest

from retail import db, repurchase

from .conftest import line

CUTOFF = pd.Timestamp("2011-06-01")


def _history():
    return [
        line("1001", "10001", 2, 5.0, "2011-01-10 10:00", 1),
        line("1002", "10002", 1, 8.0, "2011-04-20 10:00", 1),
        line("1003", "10001", 3, 5.0, "2011-05-30 16:00", 2),
        line("C1004", "10001", -1, 5.0, "2011-05-31 09:00", 2),
    ]


def test_features_ignore_everything_after_the_cutoff(connect):
    before = db.query(connect(_history()), "06_customer_features.sql", cutoff=CUTOFF, horizon=90)
    future = [
        line("2001", "10001", 50, 5.0, "2011-06-01 00:00", 1),   # at the cutoff: belongs to the label window
        line("2002", "10002", 7, 8.0, "2011-07-15 10:00", 2),
        line("C2003", "10002", -1, 8.0, "2011-07-16 10:00", 2),
        line("2004", "10001", 1, 5.0, "2011-07-01 10:00", 3),   # new customer after the cutoff: not in the frame
    ]
    after = db.query(connect(_history() + future), "06_customer_features.sql", cutoff=CUTOFF, horizon=90)
    features = [c for c in before.columns if c not in ("future_orders", "future_revenue")]
    pd.testing.assert_frame_equal(before[features], after[features])
    assert after["customer_id"].tolist() == [1, 2]
    assert after["future_orders"].tolist() == [1, 1]
    assert after["future_revenue"].tolist() == [250.0, 48.0]


def test_label_window_is_the_ninety_days_from_the_cutoff(connect):
    rows = _history() + [
        line("3001", "10001", 1, 5.0, "2011-08-29 23:59", 1),   # day 89: inside
        line("3002", "10001", 1, 5.0, "2011-08-30 00:00", 2),   # day 90: outside
    ]
    f = db.query(connect(rows), "06_customer_features.sql", cutoff=CUTOFF, horizon=90).set_index("customer_id")
    assert f.loc[1, "future_orders"] == 1
    assert f.loc[2, "future_orders"] == 0
    assert f.loc[2, "recency_days"] == 2
    assert f.loc[2, "cancel_share"] == pytest.approx(0.5)


def test_scores_and_gains_on_a_perfect_ranking():
    y = np.array([1, 1, 0, 0, 0, 0, 0, 0, 0, 0])
    rev = np.array([100.0, 50.0, 0, 0, 0, 0, 0, 0, 0, 0])
    p = np.linspace(1, 0, 10)
    s = repurchase.scores(y, p, rev, top_share=0.2)
    assert s["roc_auc"] == 1.0
    assert s["buyers_captured"] == 1.0 and s["revenue_captured"] == 1.0
    assert s["top_decile_lift"] == pytest.approx(1 / 0.2)
    g = repurchase.gains(y, p, rev, points=11)
    assert g["buyers"][0] == 0.0 and g["buyers"][-1] == 1.0 and g["buyers"][2] == 1.0


def test_rfm_baseline_maps_scores_to_training_rates():
    X = pd.DataFrame({"rfm_score": [3, 3, 15, 15]})
    m = repurchase.RFMBaseline().fit(X, pd.Series([0, 1, 1, 1]))
    p = m.predict_proba(pd.DataFrame({"rfm_score": [3, 15, 9]}))[:, 1]
    assert p.tolist() == [0.5, 1.0, 0.75]  # unseen score falls back to the overall rate
