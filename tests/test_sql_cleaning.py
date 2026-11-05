import pandas as pd

from retail import db, kpis

from .conftest import line


def test_every_raw_line_gets_exactly_one_status(connect):
    rows = [
        line("1001", "85123A", 6, 2.55, "2011-01-03 10:00"),
        line("1001", "85123A", 6, 2.55, "2011-01-03 10:00"),          # exact copy -> duplicate
        line("1001", "POST", 1, 18.00, "2011-01-03 10:00"),           # postage -> non-product
        line("C1002", "85123A", -2, 2.55, "2011-01-04 09:00"),        # cancellation
        line("C1002", "M", -1, 5.00, "2011-01-04 09:00"),             # cancelled manual line -> non-product
        line("C1002", "M", -1, 5.00, "2011-01-04 09:00"),             # ...repeated -> duplicate (checked first)
        line("1003", "22423", 4, 0.00, "2011-01-05 12:00", None),     # zero price
        line("1004", "22423", -10, 0.00, "2011-01-05 12:00", None),   # stock write-off
        line("1005", "DCGS0076", 1, 16.00, "2011-01-06 12:00"),       # gift-shop product -> sale
        line("1006", "GIFT_0001_20", 1, 20.00, "2011-01-06 12:00"),   # voucher -> non-product
    ]
    rows += [line(f"20{i:02d}", "21212", 10, 0.55, "2011-02-01 10:00") for i in range(5)]
    rows.append(line("2099", "21212", 10, 649.50, "2011-02-02 10:00"))  # > 100x the usual price -> price error
    con = connect(rows)

    funnel = db.query(con, "02_funnel.sql").set_index("status")["lines"]
    assert funnel.sum() == len(rows)
    assert funnel.to_dict() == {"sale": 7, "duplicate": 2, "non-product": 3, "cancellation": 1,
                                "invalid quantity or price": 2, "price error": 1}


def test_revenue_is_net_of_cancellations_and_excludes_removed_lines(connect):
    rows = [
        line("1001", "85123A", 10, 2.00, "2011-03-01 10:00"),
        line("1001", "POST", 1, 18.00, "2011-03-01 10:00"),
        line("C1002", "85123A", -3, 2.00, "2011-03-05 10:00"),
    ]
    monthly = kpis.monthly(connect(rows))
    assert monthly["net_revenue"].iloc[0] == 14.0
    assert monthly["gross_sales"].iloc[0] == 20.0
    assert monthly["cancelled"].iloc[0] == 6.0
    assert monthly["orders"].iloc[0] == 1


def test_funnel_follows_the_display_order(connect):
    f = kpis.funnel(connect([line("1001", "85123A", 1, 1.0, "2011-01-01 09:00")]))
    assert f["status"].tolist() == kpis.STATUS_ORDER
    assert f["lines"].sum() == 1
    assert f.loc[f["status"] == "sale", "share"].iloc[0] == 1.0


def test_pareto_counts_products_needed_for_80_percent():
    prod = pd.DataFrame({"net_revenue": [50.0, 30.0, 10.0, 5.0, 5.0, -2.0]})
    p = kpis.pareto(prod)
    assert p["products_for_80"] == 2
    assert p["curve"]["revenue_share"][0] == 0.0 and abs(p["curve"]["revenue_share"][-1] - 1.0) < 1e-12
