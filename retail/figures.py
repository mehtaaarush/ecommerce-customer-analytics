"""Static figures for the README (matplotlib, same palette as the dashboard's light theme)."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mticker  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

from . import config, rfm  # noqa: E402

SURFACE, INK, INK2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, BASELINE = "#e1e0d9", "#c3c2b7"
BLUE, ORANGE = "#2a78d6", "#eb6834"
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]


def _style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
            "font.family": ["Segoe UI", "DejaVu Sans", "sans-serif"], "font.size": 10,
            "axes.edgecolor": BASELINE, "axes.labelcolor": INK2, "axes.titlesize": 12.5,
            "axes.titleweight": "bold", "axes.titlecolor": INK, "axes.titlelocation": "left", "axes.titlepad": 12,
            "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
            "axes.grid": True, "axes.grid.axis": "y", "axes.axisbelow": True, "grid.color": GRID, "grid.linewidth": 0.8,
            "xtick.color": MUTED, "ytick.color": MUTED, "xtick.major.size": 0, "ytick.major.size": 0,
            "legend.frameon": False, "legend.labelcolor": INK2, "lines.solid_capstyle": "round",
            "axes.unicode_minus": True,
        }
    )


def _save(fig, name: str) -> Path:
    config.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = config.FIGURES_DIR / name
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return path


def _gbp_compact(v, _p=None) -> str:
    if v == 0:
        return "£0"
    return f"£{v / 1e6:.1f}M" if abs(v) >= 1e6 else f"£{v / 1e3:.0f}k"


def _share(v: float) -> str:
    return "<1%" if 0 < v < 0.005 else f"{v:.0%}"


def monthly_figure(monthly: pd.DataFrame) -> Path:
    """Net revenue by calendar month, year 2 against year 1."""
    fig, ax = plt.subplots(figsize=(9, 3.6))
    labels = None
    for name, (start, end), color, style in [("Year 1 (Dec 2009 – Nov 2010)", config.YEAR1, MUTED, (0, (4, 3))),
                                             ("Year 2 (Dec 2010 – Nov 2011)", config.YEAR2, BLUE, "solid")]:
        sub = monthly[(monthly["month"] >= start) & (monthly["month"] < end)]
        labels = sub["month"].dt.strftime("%b").tolist()
        ax.plot(range(len(sub)), sub["net_revenue"], color=color, lw=2.2, ls=style, label=name, marker="o", ms=4,
                mec=SURFACE, mew=1.2)
    ax.set_xticks(range(len(labels)), labels)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(_gbp_compact))
    ax.set_ylim(bottom=0)
    ax.set_title("Net merchandise revenue by month", pad=30)
    ax.legend(loc="lower left", ncol=2, bbox_to_anchor=(0, 1.0), fontsize=9.5, borderaxespad=0.3)
    return _save(fig, "monthly_revenue.png")


def cohort_figure(retention: pd.DataFrame) -> Path:
    """Share of each monthly cohort ordering again N months after its first order."""
    # month 0 is 100% by definition, and the newest cohort has nothing after it; both are left out
    data = retention.drop(columns=0).iloc[:-1]
    fig, ax = plt.subplots(figsize=(10, 5.6))
    cmap = LinearSegmentedColormap.from_list("seq", SEQ)
    cmap.set_bad(SURFACE)
    im = ax.imshow(data.to_numpy(dtype=float) * 100, cmap=cmap, aspect="auto", vmin=0, vmax=40)
    ax.set_yticks(range(len(data)), [c.strftime("%b %Y") for c in data.index], fontsize=8.5)
    ticks = list(range(0, data.shape[1], 2))
    ax.set_xticks(ticks, [str(data.columns[i]) for i in ticks])
    ax.set_xlabel("Months since first order")
    ax.grid(False)
    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.outline.set_visible(False)
    cbar.ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _p: f"{v:.0f}%"))
    cbar.ax.tick_params(colors=MUTED)
    ax.set_title("Cohort retention: share of each month's new customers ordering again")
    return _save(fig, "cohort_retention.png")


def rfm_figure(summary: pd.DataFrame) -> Path:
    s = summary.set_index("segment").reindex(rfm.SEGMENT_ORDER).dropna(subset=["customers"])[::-1]
    y = np.arange(len(s))
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    h = 0.36
    ax.barh(y + h / 2, s["customer_share"] * 100, height=h, color=BLUE, label="Share of customers")
    ax.barh(y - h / 2, s["revenue_share"] * 100, height=h, color=ORANGE, label="Share of revenue")
    for yi, v in zip(y, s["revenue_share"]):
        ax.annotate(_share(v), (v * 100, yi - h / 2), xytext=(4, 0), textcoords="offset points", va="center",
                    fontsize=8.5, color=INK2)
    ax.set_yticks(y, s.index)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _p: f"{v:.0f}%"))
    ax.set_title("RFM segments: customers vs revenue", pad=30)
    ax.legend(loc="lower left", ncol=2, bbox_to_anchor=(0, 1.0), fontsize=9.5, borderaxespad=0.3)
    return _save(fig, "rfm_segments.png")


def gains_figure(model: dict, names: dict) -> Path:
    g = model["gains"]
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    frac = g[model["selected"]]["fraction"] * 100
    ax.plot(frac, frac, color=BASELINE, lw=1.6, ls=(0, (4, 3)), label="Random")
    ax.plot(frac, g["rfm"]["buyers"] * 100, color=ORANGE, lw=2.2, label=names["rfm"])
    ax.plot(frac, g[model["selected"]]["buyers"] * 100, color=BLUE, lw=2.2, label=names[model["selected"]])
    ax.set_xlabel("Customers contacted, highest score first (%)")
    ax.set_ylabel("Next-quarter buyers reached (%)")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.grid(axis="x", visible=True)
    ax.set_title("Repurchase model vs RFM rule (held-out quarter)", pad=30)
    ax.legend(loc="lower left", ncol=3, bbox_to_anchor=(0, 1.0), fontsize=9.5, borderaxespad=0.3)
    return _save(fig, "model_gains.png")


def all_figures(monthly, retention, summary, model, names) -> list[Path]:
    _style()
    return [monthly_figure(monthly), cohort_figure(retention), rfm_figure(summary), gains_figure(model, names)]
