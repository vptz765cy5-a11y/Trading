"""Download and align market data (Yahoo Finance) and interest rates (FRED)."""
from __future__ import annotations

import io
import pickle
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .config import BTC, FRED_DAILY, FRED_MONTHLY, STALE_DAYS, UNIVERSE

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={}"


@dataclass
class MarketData:
    tr: pd.DataFrame  # total-return index (adjusted close), trading-day index
    close: pd.DataFrame  # unadjusted close
    div: pd.DataFrame  # cash dividends on ex-date (0 elsewhere)
    rates: pd.DataFrame  # annual decimal rates, aligned to trading days, lag-safe


def _cached(name: str, fn, refresh: bool):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{name}.pkl"
    if path.exists() and not refresh:
        return pickle.loads(path.read_bytes())
    obj = fn()
    path.write_bytes(pickle.dumps(obj))
    return obj


def _download_yahoo(tickers: list[str]) -> dict[str, pd.DataFrame]:
    import yfinance as yf

    raw = yf.download(tickers, start="2000-01-01", auto_adjust=False, actions=True,
                      progress=False, group_by="ticker")
    out = {}
    for field, key in (("Adj Close", "tr"), ("Close", "close"), ("Dividends", "div")):
        out[key] = pd.DataFrame({t: raw[t][field] for t in tickers})
    for df in out.values():
        df.index = pd.DatetimeIndex(df.index).tz_localize(None).normalize()
    return out


def _download_fred(series_id: str) -> pd.Series:
    with urllib.request.urlopen(FRED_URL.format(series_id), timeout=60) as resp:
        df = pd.read_csv(io.BytesIO(resp.read()))
    s = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    s.index = pd.to_datetime(df.iloc[:, 0])
    return s.dropna() / 100.0


def align_rate(obs: pd.Series, index: pd.DatetimeIndex, stale_days: int = STALE_DAYS) -> pd.Series:
    """`obs` is indexed by the date the value becomes *available*. Forward-fill onto `index`
    and blank out values whose underlying observation is older than `stale_days`."""
    obs = obs.dropna().sort_index()
    obs = obs[~obs.index.duplicated(keep="last")]
    avail = pd.Series(obs.index, index=obs.index)
    combined = obs.index.union(index)
    val = obs.reindex(combined).ffill().reindex(index)
    age = (index - pd.DatetimeIndex(avail.reindex(combined).ffill().reindex(index))).days
    return val.where(age <= stale_days)


def build_rates(raw_daily: dict[str, pd.Series], raw_monthly: dict[str, pd.Series],
                index: pd.DatetimeIndex) -> pd.DataFrame:
    out = {}
    for key, s in raw_daily.items():
        # value for day d is published after d -> usable from the next business day
        shifted = s.copy()
        shifted.index = shifted.index + pd.offsets.BDay(1)
        out[key] = align_rate(shifted, index)
    for key, s in raw_monthly.items():
        # monthly average for month m (dated 1st of m) is usable one month after m ends
        shifted = s.copy()
        shifted.index = shifted.index + pd.DateOffset(months=2)
        out[key] = align_rate(shifted, index)
    return pd.DataFrame(out, index=index)


def load(refresh: bool = False, include_btc: bool = True) -> MarketData:
    tickers = [i.ticker for i in UNIVERSE] + ([BTC.ticker] if include_btc else [])
    yahoo = _cached("yahoo_" + "_".join(tickers), lambda: _download_yahoo(tickers), refresh)
    fred_d = _cached("fred_daily", lambda: {k: _download_fred(v) for k, v in FRED_DAILY.items()}, refresh)
    fred_m = _cached("fred_monthly", lambda: {k: _download_fred(v) for k, v in FRED_MONTHLY.items()}, refresh)

    # trading calendar = US equity sessions (SPY); crypto is sampled on those days
    index = yahoo["tr"]["SPY"].dropna().index
    tr = yahoo["tr"].reindex(index)
    if BTC.ticker in tr:
        btc = yahoo["tr"][BTC.ticker].dropna()
        tr[BTC.ticker] = btc.reindex(btc.index.union(index)).ffill(limit=5).reindex(index)
    close = yahoo["close"].reindex(index)
    # dividends: sum any ex-dates falling on non-trading days into the next session
    div = yahoo["div"].fillna(0.0)
    div = div.groupby(index[index.searchsorted(div.index).clip(max=len(index) - 1)]).sum()
    div = div.reindex(index, fill_value=0.0)
    rates = build_rates(fred_d, fred_m, index)
    return MarketData(tr=tr, close=close, div=div, rates=rates)
