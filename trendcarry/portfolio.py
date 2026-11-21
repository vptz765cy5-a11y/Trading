"""Risk scaling of positions."""
from __future__ import annotations

import numpy as np
import pandas as pd


def rolling_cov(monthly_excess: pd.DataFrame, months: int, min_months: int) -> pd.DataFrame:
    """Annualised covariance of the last `months` monthly excess returns (Hurst et al. 2017, fn. 7)."""
    window = monthly_excess.iloc[-months:]
    return window.cov(min_periods=min_months) * 12.0


def scale_to_target(raw: pd.Series, cov: pd.DataFrame, target: float) -> pd.Series:
    """Scale `raw` positions so that ex-ante annual volatility equals `target`.
    Instruments without a full covariance row are dropped."""
    raw = raw.dropna()
    raw = raw[raw != 0]
    names = [n for n in raw.index if n in cov.index and pd.notna(cov.at[n, n])]
    # drop instruments with missing pairwise covariances (too little overlapping history),
    # one at a time, starting with the one with the most gaps
    while names:
        gaps = cov.loc[names, names].isna().sum(axis=1)
        if gaps.max() == 0:
            break
        names.remove(gaps.idxmax())
    if not names:
        return pd.Series(dtype=float)
    x = raw[names].to_numpy()
    var = float(x @ cov.loc[names, names].to_numpy() @ x)
    if not np.isfinite(var) or var <= 0:
        return pd.Series(dtype=float)
    return pd.Series(x * target / np.sqrt(var), index=names)


def vol_parity_weights(signal: pd.Series, vol: pd.Series, cov: pd.DataFrame, target: float) -> pd.Series:
    """Equal-risk positions signal_i / sigma_i, scaled to the portfolio volatility target."""
    raw = (signal / vol).replace([np.inf, -np.inf], np.nan)
    return scale_to_target(raw, cov, target)


def cap_gross(w: pd.Series, max_gross: float) -> pd.Series:
    gross = w.abs().sum()
    return w * (max_gross / gross) if gross > max_gross else w
