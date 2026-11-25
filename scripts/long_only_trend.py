"""Simple, implementable variant: long-only trend following on 7 ETFs, no leverage, no shorts.

NOTE: this variant was added AFTER the pre-registered study (post hoc). It reuses the
pre-registered trend rules (1/3/12-month signs, EWMA vol, 36m covariance, 10 % vol target)
and only adds: long-only (negative signals -> cash) and gross exposure <= 100 %.

    python scripts/long_only_trend.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from trendcarry import data as data_mod  # noqa: E402
from trendcarry.backtest import complete_months, precompute  # noqa: E402
from trendcarry.config import Params  # noqa: E402
from trendcarry.portfolio import cap_gross, rolling_cov, vol_parity_weights  # noqa: E402
from trendcarry.signals import trend_signal  # noqa: E402
from trendcarry.stats import summary  # noqa: E402

UNIVERSE = ["SPY", "EFA", "EEM", "IEF", "TLT", "GLD", "DBC"]


def main() -> None:
    p = Params()
    md = data_mod.load()
    pre = precompute(md, p)
    rets = pre.monthly[UNIVERSE]
    w = pd.DataFrame(0.0, index=pre.exec_dates, columns=UNIVERSE)
    for k in range(len(pre.exec_dates)):
        s = pre.signal_dates[k]
        sig = trend_signal(pre.excess[UNIVERSE], s, p.trend_lookbacks).clip(lower=0)
        cov = rolling_cov(rets.iloc[:k], p.cov_months, p.cov_min_months)
        wk = vol_parity_weights(sig, pre.vol.loc[s, UNIVERSE], cov, p.target_vol)
        if len(wk):
            w.iloc[k] = cap_gross(wk, 1.0).reindex(UNIVERSE).fillna(0.0).to_numpy()

    cost = (w.diff().abs().fillna(w.abs()) * pre.cost_bps[UNIVERSE] / 1e4).sum(axis=1)
    held = w.shift(1)
    strat = (held * rets.fillna(0)).sum(axis=1) - cost.shift(1).fillna(0)
    strat = strat[held.abs().sum(axis=1) > 0]

    ew = rets.mean(axis=1, skipna=True)  # equal-weight buy & hold, monthly rebalanced
    sixty = 0.6 * rets["SPY"] + 0.4 * rets["IEF"]
    last = md.tr.index[-1]
    start = strat.index[0]
    series = {
        "Trend long-only": strat,
        "Gleichgewichtet 7 ETFs (Buy & Hold)": ew,
        "60/40 (SPY/IEF)": sixty,
        "SPY": rets["SPY"],
    }
    cut = pd.Timestamp(p.pub_cutoff)
    for label, f in (("Gesamt", lambda r: r), ("Nach Publikation (>= 2013-09)", lambda r: r[r.index >= cut])):
        print(f"\n== {label} ==")
        rows = {}
        for n, r in series.items():
            r = f(complete_months(r, last).loc[start:]).dropna()
            s = summary(r, rets["SPY"])
            rows[n] = {"Rendite p.a.": s["ann_return"], "Vol": s["ann_vol"], "Sharpe": s["sharpe"],
                       "Max DD": s["max_dd"], "Korr SPY": s.get("corr_spy", np.nan)}
        print(pd.DataFrame(rows).T.round(3).to_string())
    cash = 1 - w.iloc[-1].sum()
    print(f"\nAktuelle Gewichte (Signal {pre.signal_dates[-1].date()}):")
    print((w.iloc[-1] * 100).round(1).to_string(), f"\nCash {cash * 100:.1f} %")
    print(f"Ø investiert: {held.sum(axis=1).loc[start:].mean() * 100:.0f} %")


if __name__ == "__main__":
    main()
