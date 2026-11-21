"""Trend and carry signals. Every function only uses data up to the date it is evaluated at."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import BOND_CURVE, Instrument


def daily_excess_returns(tr: pd.DataFrame, rf_annual: pd.Series) -> pd.DataFrame:
    """Daily total return minus the T-bill rate known at the previous close."""
    rf_daily = rf_annual.shift(1) / 252.0
    return tr.pct_change(fill_method=None).sub(rf_daily, axis=0)


def ewma_vol(excess: pd.DataFrame, com: int, min_obs: int, ann_days: int) -> pd.DataFrame:
    """Annualised ex-ante volatility (Moskowitz, Ooi, Pedersen 2012)."""
    return excess.ewm(com=com, min_periods=min_obs).std() * np.sqrt(ann_days)


def trend_signal(excess: pd.DataFrame, date: pd.Timestamp, lookbacks: tuple[int, ...]) -> pd.Series:
    """Average of sign(cumulative excess return) over each lookback (Hurst, Ooi, Pedersen 2017).
    NaN where any lookback lacks complete data."""
    hist = excess.loc[:date]
    parts = []
    for h in lookbacks:
        window = hist.iloc[-h:]
        cum = (1.0 + window).prod(min_count=h) - 1.0
        cum[window.isna().any() | (len(window) < h)] = np.nan
        parts.append(np.sign(cum))
    return pd.concat(parts, axis=1).mean(axis=1, skipna=False)


def daily_carry(inst: tuple[Instrument, ...], close: pd.DataFrame, div: pd.DataFrame,
                rates: pd.DataFrame) -> pd.DataFrame:
    """Annualised carry per instrument following Koijen, Moskowitz, Pedersen, Vrugt (2018)."""
    rf = rates["US"]
    out = {}
    for i in inst:
        if i.carry == "equity":
            px = close[i.ticker]
            div12 = div[i.ticker].rolling("365D").sum()
            first = px.first_valid_index()
            dy = (div12 / px).where(px.index >= first + pd.Timedelta(days=365))
            out[i.ticker] = dy - rf
        elif i.carry == "bond":
            short, long_, years, duration = BOND_CURVE[i.ticker]
            y = (rates[short] + rates[long_]) / 2.0
            roll = duration * (rates[long_] - rates[short]) / years
            out[i.ticker] = (y - rf) + roll
        elif i.carry == "fx":
            out[i.ticker] = rates[i.rate] - rf
    return pd.DataFrame(out, index=close.index)


def carry_signal(carry_monthly: pd.DataFrame, mode: str, min_months: int) -> pd.DataFrame:
    """Carry timing (Koijen et al. 2018, Eq. 24): sign(C_t - Cbar).
    hist_mean: Cbar = expanding mean of the instrument's own carry up to t.
    zero:      Cbar = 0."""
    if mode == "hist_mean":
        cbar = carry_monthly.expanding(min_periods=min_months).mean()
        return np.sign(carry_monthly - cbar)
    if mode == "zero":
        return np.sign(carry_monthly)
    raise ValueError(mode)
