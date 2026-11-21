"""Performance statistics, incl. Probabilistic and Deflated Sharpe Ratio
(Bailey & Lopez de Prado 2012, 2014). Inputs are monthly returns."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as st

EULER_GAMMA = 0.5772156649015329


def sharpe(r: pd.Series) -> float:
    """Non-annualised (per-period) Sharpe ratio."""
    sd = r.std()
    return float(r.mean() / sd) if sd > 0 else float("nan")


def psr(r: pd.Series, sr_benchmark: float = 0.0) -> float:
    """Probability that the true per-period Sharpe exceeds `sr_benchmark`,
    correcting for sample length, skewness and kurtosis."""
    r = r.dropna()
    n = len(r)
    if n < 3:
        return float("nan")
    sr = sharpe(r)
    g3 = st.skew(r)
    g4 = st.kurtosis(r, fisher=False)
    denom = 1.0 - g3 * sr + (g4 - 1.0) / 4.0 * sr**2
    if denom <= 0:
        return float("nan")
    return float(st.norm.cdf((sr - sr_benchmark) * np.sqrt(n - 1) / np.sqrt(denom)))


def expected_max_sharpe(trial_srs: list[float], n_trials: int) -> float:
    """Expected maximum per-period Sharpe among `n_trials` unskilled trials (DSR benchmark)."""
    var = float(np.nanvar(trial_srs, ddof=1)) if len(trial_srs) > 1 else 0.0
    if n_trials < 2 or var <= 0:
        return 0.0
    z1 = st.norm.ppf(1.0 - 1.0 / n_trials)
    z2 = st.norm.ppf(1.0 - 1.0 / (n_trials * np.e))
    return float(np.sqrt(var) * ((1.0 - EULER_GAMMA) * z1 + EULER_GAMMA * z2))


def dsr(r: pd.Series, trial_srs: list[float], n_trials: int) -> float:
    return psr(r, expected_max_sharpe(trial_srs, n_trials))


def max_drawdown(r: pd.Series) -> float:
    wealth = (1.0 + r.fillna(0)).cumprod()
    return float((wealth / wealth.cummax() - 1.0).min())


def summary(r: pd.Series, benchmark: pd.Series | None = None) -> dict:
    r = r.dropna()
    n = len(r)
    sr = sharpe(r)
    out = {
        "start": r.index[0].strftime("%Y-%m") if n else "",
        "end": r.index[-1].strftime("%Y-%m") if n else "",
        "months": n,
        "ann_return": r.mean() * 12,
        "ann_vol": r.std() * np.sqrt(12),
        "sharpe": sr * np.sqrt(12),
        "t_stat": sr * np.sqrt(n),
        "max_dd": max_drawdown(r),
        "skew": float(st.skew(r)) if n > 2 else float("nan"),
        "worst_month": r.min(),
        "psr0": psr(r, 0.0),
    }
    if benchmark is not None:
        b = benchmark.reindex(r.index)
        out["corr_spy"] = float(r.corr(b))
    return out
