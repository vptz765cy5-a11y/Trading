"""Monthly backtest of the pre-registered trend / carry variants."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import BTC, UNIVERSE, Instrument, Params, Variant
from .data import MarketData
from .portfolio import cap_gross, rolling_cov, scale_to_target, vol_parity_weights
from .signals import carry_signal, daily_carry, daily_excess_returns, ewma_vol, trend_signal


def month_calendar(index: pd.DatetimeIndex) -> tuple[pd.DatetimeIndex, pd.DatetimeIndex]:
    """Per calendar month: (signal date = second-to-last session, execution date = last session).
    For the current, incomplete month the last available session is the execution date."""
    s = pd.Series(index, index=index)
    groups = s.groupby(index.to_period("M"))
    exec_dates = pd.DatetimeIndex(groups.last().to_numpy())
    signal_dates = pd.DatetimeIndex(groups.apply(lambda g: g.iloc[-2] if len(g) > 1 else g.iloc[-1]).to_numpy())
    return signal_dates, exec_dates


@dataclass
class Precomputed:
    instruments: tuple[Instrument, ...]
    excess: pd.DataFrame
    vol: pd.DataFrame
    signal_dates: pd.DatetimeIndex
    exec_dates: pd.DatetimeIndex
    monthly: pd.DataFrame  # row k: excess return from exec_dates[k-1] to exec_dates[k]
    carry_monthly: pd.DataFrame  # row k: carry observed at signal_dates[k]
    cost_bps: pd.Series


def precompute(data: MarketData, params: Params) -> Precomputed:
    instruments = tuple(UNIVERSE) + ((BTC,) if BTC.ticker in data.tr else ())
    tickers = [i.ticker for i in instruments]
    tr = data.tr[tickers]
    rf = data.rates["US"]
    excess = daily_excess_returns(tr, rf)
    vol = ewma_vol(excess, params.vol_com, params.vol_min_obs, params.ann_days)
    signal_dates, exec_dates = month_calendar(tr.index)

    rf_cum = (rf.shift(1) / 252.0).fillna(0.0).cumsum()
    monthly = tr.loc[exec_dates].pct_change(fill_method=None).sub(rf_cum.loc[exec_dates].diff(), axis=0)

    carry_d = daily_carry(instruments, data.close, data.div, data.rates)
    carry_m = carry_d.loc[signal_dates]
    carry_m.index = exec_dates
    costs = pd.Series({i.ticker: i.cost_bps for i in instruments})
    return Precomputed(instruments, excess, vol, signal_dates, exec_dates, monthly, carry_m, costs)


@dataclass
class Result:
    variant: Variant
    weights: pd.DataFrame  # index: execution date (positions held until next execution date)
    returns: pd.Series  # net monthly excess return, index: end of holding month
    gross_returns: pd.Series
    costs: pd.Series


def _trend_universe(pre: Precomputed, variant: Variant) -> list[str]:
    return [i.ticker for i in pre.instruments if variant.include_btc or i.asset_class != "crypto"]


def target_weights(pre: Precomputed, variant: Variant, params: Params, k: int,
                   carry_sig: pd.DataFrame | None) -> pd.Series:
    """Positions to hold from exec_dates[k], using only information up to signal_dates[k]."""
    s = pre.signal_dates[k]
    cov = rolling_cov(pre.monthly.iloc[:k], params.cov_months, params.cov_min_months)
    vol = pre.vol.loc[s]
    parts = []
    if variant.trend:
        names = _trend_universe(pre, variant)
        sig = trend_signal(pre.excess[names], s, params.trend_lookbacks)
        parts.append(vol_parity_weights(sig, vol[names], cov, params.target_vol))
    if variant.carry and carry_sig is not None:
        sig = carry_sig.iloc[k]
        parts.append(vol_parity_weights(sig, vol[sig.index], cov, params.target_vol))
    if len(parts) == 2:
        raw = parts[0].mul(0.5).add(parts[1].mul(0.5), fill_value=0.0)
        w = scale_to_target(raw, cov, params.target_vol)
    else:
        w = parts[0] if parts else pd.Series(dtype=float)
    if variant.implementable and len(w):
        w = cap_gross(w, params.max_gross)
    return w


def run(pre: Precomputed, variant: Variant, params: Params) -> Result:
    carry_sig = None
    if variant.carry:
        carry_sig = carry_signal(pre.carry_monthly, variant.carry_mode, params.carry_min_months)

    cols = pre.monthly.columns
    weights = pd.DataFrame(0.0, index=pre.exec_dates, columns=cols)
    for k in range(len(pre.exec_dates)):
        w = target_weights(pre, variant, params, k, carry_sig)
        if len(w):
            weights.iloc[k] = w.reindex(cols).fillna(0.0).to_numpy()

    turnover = weights.diff().abs()
    turnover.iloc[0] = weights.iloc[0].abs()
    cost = (turnover * pre.cost_bps.reindex(cols) / 1e4).sum(axis=1)

    held = weights.shift(1)  # positions taken at exec k earn the return of row k+1
    rets = pre.monthly.fillna(0.0)
    gross = (held * rets).sum(axis=1)
    net = gross - cost.shift(1).fillna(0.0)
    if variant.implementable:
        long_excess = (held.clip(lower=0).sum(axis=1) - 1.0).clip(lower=0)
        short = held.clip(upper=0).abs().sum(axis=1)
        net = net - (long_excess * params.long_financing_spread + short * params.short_borrow_fee) / 12.0

    active = held.abs().sum(axis=1) > 0
    return Result(variant, weights, net[active], gross[active], cost.shift(1)[active])


def complete_months(r: pd.Series, last_data_date: pd.Timestamp) -> pd.Series:
    """Drop the trailing partial month (if the data does not end on a month's last business day)."""
    if len(r) and r.index[-1] == last_data_date and last_data_date != last_data_date + pd.offsets.BMonthEnd(0):
        return r.iloc[:-1]
    return r
