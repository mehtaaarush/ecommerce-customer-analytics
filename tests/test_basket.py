import pytest

from retail import basket, db

from .conftest import line


def test_support_confidence_and_lift_on_toy_baskets(connect):
    # four orders: {A, B}, {A, B}, {A, C}, {C}
    rows = [
        line("1", "10001", 1, 1.0, "2011-01-01 10:00"), line("1", "10002", 1, 1.0, "2011-01-01 10:00"),
        line("2", "10001", 2, 1.0, "2011-01-02 10:00"), line("2", "10002", 1, 1.0, "2011-01-02 10:00"),
        line("3", "10001", 1, 1.0, "2011-01-03 10:00"), line("3", "10003", 1, 1.0, "2011-01-03 10:00"),
        line("4", "10003", 1, 1.0, "2011-01-04 10:00"),
    ]
    pairs = db.query(connect(rows), "07_basket_pairs.sql", top_n=10, min_together=1)
    r = basket.rules(pairs).set_index(["antecedent", "consequent"])
    assert len(r) == 4  # A-B and A-C, both directions
    ab, ba = r.loc[("10001", "10002")], r.loc[("10002", "10001")]
    assert ab["support"] == pytest.approx(2 / 4)
    assert ab["confidence"] == pytest.approx(2 / 3)
    assert ba["confidence"] == pytest.approx(1.0)
    assert ab["lift"] == pytest.approx(2 * 4 / (3 * 2)) == ba["lift"]
    ac = r.loc[("10001", "10003")]
    assert ac["lift"] == pytest.approx(1 * 4 / (3 * 2))


def test_min_together_and_top_n_filter_pairs(connect):
    rows = [line("1", "10001", 1, 1.0, "2011-01-01 10:00"), line("1", "10002", 1, 1.0, "2011-01-01 10:00"),
            line("2", "10001", 1, 1.0, "2011-01-02 10:00"), line("2", "10003", 1, 1.0, "2011-01-02 10:00"),
            line("3", "10001", 1, 1.0, "2011-01-03 10:00"), line("3", "10002", 1, 1.0, "2011-01-03 10:00")]
    con = connect(rows)
    assert len(db.query(con, "07_basket_pairs.sql", top_n=10, min_together=2)) == 1
    assert len(db.query(con, "07_basket_pairs.sql", top_n=1, min_together=1)) == 0


def test_recommendations_rank_by_lift():
    import pandas as pd
    r = pd.DataFrame({"antecedent": ["a", "a", "a", "b"], "consequent": ["b", "c", "d", "a"],
                      "lift": [2.0, 5.0, 1.0, 2.0]})
    rec = basket.recommendations(r, ["a"], per_item=2)
    assert rec["consequent"].tolist() == ["c", "b"]
