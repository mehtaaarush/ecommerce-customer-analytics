import numpy as np
import pandas as pd

from retail import rfm


def test_segment_map_covers_every_cell_and_every_segment_has_an_action():
    cells = {(r, f) for r in rfm.SEGMENT_GRID for f in range(1, 6)}
    assert cells == {(r, f) for r in range(1, 6) for f in range(1, 6)}
    assert all(len(row) == 5 for row in rfm.SEGMENT_GRID.values())
    used = {seg for row in rfm.SEGMENT_GRID.values() for seg in row}
    assert used == set(rfm.SEGMENT_ORDER) == set(rfm.ACTIONS)


def test_scores_are_monotone_and_frequency_uses_fixed_bands():
    rng = np.random.default_rng(0)
    df = pd.DataFrame({
        "customer_id": range(500),
        "recency_days": rng.integers(0, 700, 500),
        "frequency": rng.integers(1, 30, 500),
        "monetary": rng.gamma(2.0, 400.0, 500),
    })
    s = rfm.score(df)
    assert s.sort_values(["recency_days", "r_score"], ascending=[True, False])["r_score"].is_monotonic_decreasing
    assert s.sort_values(["monetary", "m_score"])["m_score"].is_monotonic_increasing
    assert s["r_score"].value_counts().tolist() == [100] * 5  # quintiles
    bands = {1: 1, 2: 2, 3: 3, 4: 3, 5: 4, 9: 4, 10: 5, 29: 5}
    for freq, band in bands.items():
        assert (s.loc[s["frequency"] == freq, "f_score"] == band).all()
    assert s["rfm_score"].between(3, 15).all()


def test_best_cell_is_champions_and_worst_is_lost():
    df = pd.DataFrame({"customer_id": range(10), "recency_days": range(10), "frequency": [20] * 5 + [1] * 5,
                       "monetary": np.linspace(1000, 10, 10)})
    s = rfm.score(df).set_index("customer_id")
    assert s.loc[0, "segment"] == "Champions"
    assert s.loc[9, "segment"] == "Lost"
