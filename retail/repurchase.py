"""Repurchase propensity: will a customer order again in the next 90 days?

Each cutoff gives one row per customer with features from their history before the cutoff and a label
from the 90 days after it. Models train on four earlier quarters, are chosen on the most recent of them,
and are scored once on the held-out quarter (11 Sep - 9 Dec 2011). For the earliest cutoff the
"same quarter last year" window falls mostly before the data begin, so that feature is understated there."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from . import config, db, rfm

FEATURES = {
    "recency_days": "Days since last order",
    "frequency": "Orders to date",
    "orders_90d": "Orders in the last 90 days",
    "orders_prev_90d": "Orders 91–180 days ago",
    "orders_same_window_last_year": "Orders in the same quarter last year",
    "spend_90d": "Spend in the last 90 days",
    "monetary": "Net spend to date",
    "avg_order_value": "Average order value",
    "avg_products": "Products per order",
    "distinct_products": "Distinct products bought",
    "active_months": "Months with an order",
    "tenure_days": "Days since first order",
    "order_rate": "Orders per 30 days of tenure",
    "cancel_share": "Share of lines cancelled",
    "is_uk": "UK customer",
}


def frame(con, cutoff: pd.Timestamp) -> pd.DataFrame:
    """Customers with an order before `cutoff`: features, RFM scores at that date and the 90-day label."""
    df = rfm.score(db.query(con, "06_customer_features.sql", cutoff=cutoff, horizon=config.HORIZON_DAYS))
    df["order_rate"] = df["frequency"] / np.maximum(df["tenure_days"], 30) * 30
    df["is_uk"] = (df["country"] == "United Kingdom").astype(int)
    df["bought"] = (df["future_orders"] > 0).astype(int)
    df["cutoff"] = cutoff
    return df


def _signed_log(x):
    return np.sign(x) * np.log1p(np.abs(x))


class RFMBaseline:
    """The no-model benchmark: rank customers by their R + F + M score, with each score's repurchase rate
    in the training data as its probability."""

    def fit(self, X: pd.DataFrame, y: pd.Series):
        rates = pd.Series(np.asarray(y), index=X.index).groupby(X["rfm_score"]).mean()
        self.rates_ = rates
        self.prior_ = float(np.mean(y))
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        p = X["rfm_score"].map(self.rates_).fillna(self.prior_).to_numpy(dtype=float)
        return np.column_stack([1 - p, p])


@dataclass(frozen=True)
class Candidate:
    name: str
    columns: tuple
    make: callable


def candidates() -> dict[str, Candidate]:
    features = tuple(FEATURES)
    return {
        "rfm": Candidate("RFM score (baseline)", ("rfm_score",), RFMBaseline),
        "logit": Candidate("Logistic regression", features, lambda: make_pipeline(
            FunctionTransformer(_signed_log, feature_names_out="one-to-one"), StandardScaler(),
            LogisticRegression(C=0.5, max_iter=5000))),
        "gbm": Candidate("Gradient boosting", features, lambda: HistGradientBoostingClassifier(
            learning_rate=0.05, max_iter=250, max_leaf_nodes=15, min_samples_leaf=40, l2_regularization=1.0,
            early_stopping=False, random_state=config.RANDOM_STATE)),
    }


def _order(p: np.ndarray, seed: int = config.RANDOM_STATE) -> np.ndarray:
    """Indices from highest to lowest score; ties (the RFM score has 13 values) are broken at random."""
    tiebreak = np.random.default_rng(seed).random(len(p))
    return np.lexsort((tiebreak, -np.asarray(p)))


def scores(y, p, revenue, top_share: float = config.TOP_SHARE) -> dict:
    y, p, rev = np.asarray(y), np.asarray(p, dtype=float), np.clip(np.asarray(revenue, dtype=float), 0, None)
    order = _order(p)
    n = len(y)
    top, top10 = order[: int(round(top_share * n))], order[: int(round(0.1 * n))]
    return {
        "roc_auc": roc_auc_score(y, p),
        "pr_auc": average_precision_score(y, p),
        "brier": brier_score_loss(y, p),
        "log_loss": log_loss(y, np.clip(p, 1e-6, 1 - 1e-6)),
        "top_decile_lift": y[top10].mean() / y.mean(),
        "buyers_captured": y[top].sum() / y.sum(),
        "revenue_captured": rev[top].sum() / rev.sum(),
        "base_rate": y.mean(),
        "mean_predicted": p.mean(),
    }


def gains(y, p, revenue, points: int = 101) -> dict:
    """Cumulative share of buyers and of next-quarter revenue reached when contacting the top x% first."""
    y, rev = np.asarray(y, dtype=float), np.clip(np.asarray(revenue, dtype=float), 0, None)
    order = _order(p)
    buyers = np.r_[0, np.cumsum(y[order])] / y.sum()
    revenue_share = np.r_[0, np.cumsum(rev[order])] / rev.sum()
    fraction = np.linspace(0, 1, points)
    idx = np.round(fraction * len(y)).astype(int)
    return {"fraction": fraction, "buyers": buyers[idx], "revenue": revenue_share[idx]}


def deciles(y, p, revenue) -> pd.DataFrame:
    y, p, rev = np.asarray(y), np.asarray(p, dtype=float), np.asarray(revenue, dtype=float)
    order = _order(p)
    decile = np.empty(len(y), dtype=int)
    decile[order] = np.arange(len(y)) * 10 // len(y) + 1
    d = pd.DataFrame({"decile": decile, "y": y, "p": p, "rev": rev}).groupby("decile")
    out = pd.DataFrame({
        "customers": d.size(), "predicted": d["p"].mean(), "observed": d["y"].mean(),
        "revenue_per_customer": d["rev"].mean(), "revenue": d["rev"].sum(),
    })
    out["revenue_share"] = out["revenue"].clip(lower=0) / out["revenue"].clip(lower=0).sum()
    return out.reset_index()


def bootstrap_difference(y, p_model, p_base, revenue, n_boot: int = config.N_BOOT, seed: int = config.RANDOM_STATE) -> dict:
    """Paired bootstrap of the model-minus-baseline gap in ROC AUC and in revenue captured by the top 20%."""
    rng = np.random.default_rng(seed)
    y, p_model, p_base, rev = map(np.asarray, (y, p_model, p_base, revenue))
    diffs = {"roc_auc": [], "revenue_captured": []}
    for _ in range(n_boot):
        i = rng.integers(0, len(y), len(y))
        a, b = scores(y[i], p_model[i], rev[i]), scores(y[i], p_base[i], rev[i])
        for k in diffs:
            diffs[k].append(a[k] - b[k])
    return {k: {"low": float(np.quantile(v, 0.025)), "high": float(np.quantile(v, 0.975))} for k, v in diffs.items()}


def _fit(spec: Candidate, df: pd.DataFrame):
    return spec.make().fit(df[list(spec.columns)], df["bought"])


def _predict(model, spec: Candidate, df: pd.DataFrame) -> np.ndarray:
    return model.predict_proba(df[list(spec.columns)])[:, 1]


def evaluate(con) -> dict:
    frames = {c: frame(con, c) for c in [*config.TRAIN_CUTOFFS, config.TEST_CUTOFF]}
    train = pd.concat([frames[c] for c in config.TRAIN_CUTOFFS], ignore_index=True)
    test = frames[config.TEST_CUTOFF]
    specs = candidates()

    # 1. choose between the models on the most recent training quarter (fit on the three before it)
    valid_cut = max(config.TRAIN_CUTOFFS)
    fit_part, valid = train[train["cutoff"] < valid_cut], train[train["cutoff"] == valid_cut]
    selection = []
    for key, spec in specs.items():
        p = _predict(_fit(spec, fit_part), spec, valid)
        selection.append({"key": key, "name": spec.name, **scores(valid["bought"], p, valid["future_revenue"])})
    selection = pd.DataFrame(selection)
    selected = selection[selection["key"] != "rfm"].sort_values("pr_auc", ascending=False)["key"].iloc[0]

    # 2. refit on all four training quarters and score the untouched test quarter once
    models, preds, rows = {}, {}, []
    for key, spec in specs.items():
        models[key] = _fit(spec, train)
        preds[key] = _predict(models[key], spec, test)
        rows.append({"key": key, "name": spec.name, **scores(test["bought"], preds[key], test["future_revenue"])})
    metrics = pd.DataFrame(rows)

    y, rev = test["bought"].to_numpy(), test["future_revenue"].to_numpy()
    spec = specs[selected]
    imp = permutation_importance(models[selected], test[list(spec.columns)], y, scoring="average_precision",
                                 n_repeats=10, random_state=config.RANDOM_STATE)
    importance = pd.DataFrame({"feature": list(spec.columns), "label": [FEATURES[c] for c in spec.columns],
                               "importance": imp.importances_mean, "std": imp.importances_std}
                              ).sort_values("importance", ascending=False, ignore_index=True)

    # 3. refit the chosen model on every labelled quarter and score today's customers
    labelled = pd.concat([train, test], ignore_index=True)
    final = _fit(spec, labelled)
    now = frame(con, config.SNAPSHOT)
    now["propensity"] = _predict(final, spec, now)

    windows = pd.DataFrame([{
        "cutoff": c, "label_end": c + pd.Timedelta(days=config.HORIZON_DAYS - 1), "customers": len(f),
        "base_rate": f["bought"].mean(), "role": "test" if c == config.TEST_CUTOFF else ("validation" if c == valid_cut else "train"),
    } for c, f in sorted(frames.items())])

    return {
        "selected": selected,
        "selection": selection,
        "metrics": metrics,
        "gains": {k: gains(y, preds[k], rev) for k in ["rfm", selected]},
        "deciles": deciles(y, preds[selected], rev),
        "importance": importance,
        "bootstrap": bootstrap_difference(y, preds[selected], preds["rfm"], rev),
        "windows": windows,
        "test": test.assign(p_model=preds[selected], p_rfm=preds["rfm"]),
        "now": now,
        "n_train": len(train),
        "n_test": len(test),
    }


def segment_outlook(now: pd.DataFrame) -> pd.DataFrame:
    """Today's segments with the model's view of the next 90 days: who is likely to buy, and what they spent."""
    g = now.groupby("segment")
    out = pd.DataFrame({
        "customers": g.size(),
        "mean_propensity": g["propensity"].mean(),
        "expected_buyers": g["propensity"].sum(),
        "median_monetary": g["monetary"].median(),
        "revenue_to_date": g["monetary"].sum(),
    }).reindex(rfm.SEGMENT_ORDER).dropna(subset=["customers"])
    out["expected_buyer_share"] = out["expected_buyers"] / out["expected_buyers"].sum()
    return out.reset_index(names="segment")
