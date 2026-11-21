import numpy as np
import pandas as pd
import pytest

from trendcarry.config import BTC, UNIVERSE
from trendcarry.data import MarketData


def make_data(seed: int = 0, start="2004-01-01", end="2014-12-31", drift=None) -> MarketData:
    rng = np.random.default_rng(seed)
    index = pd.bdate_range(start, end)
    tickers = [i.ticker for i in UNIVERSE] + [BTC.ticker]
    n = len(index)
    drift = drift if drift is not None else {}
    rets = pd.DataFrame(rng.normal(0.0002, 0.01, (n, len(tickers))), index=index, columns=tickers)
    for t, mu in drift.items():
        rets[t] += mu
    tr = (1 + rets).cumprod() * 100
    close = tr.copy()
    div = pd.DataFrame(0.0, index=index, columns=tickers)
    for t in ("SPY", "EFA", "EEM"):
        div.loc[index[index.is_quarter_end], t] = 0.5
    rates = pd.DataFrame({
        "US": 0.02, "DGS7": 0.03, "DGS10": 0.035, "DGS20": 0.04, "DGS30": 0.042,
        "EUR": 0.01, "JPY": 0.0, "GBP": 0.03, "AUD": 0.05, "CAD": 0.025, "CHF": 0.005,
    }, index=index)
    # make carry vary over time so the historical-mean signal is not degenerate
    wave = 0.01 * np.sin(np.arange(n) / 120.0)
    for c in ("EUR", "JPY", "GBP", "AUD", "CAD", "CHF", "DGS10", "DGS30"):
        rates[c] = rates[c] + wave
    return MarketData(tr=tr, close=close, div=div, rates=rates)


@pytest.fixture(scope="session")
def synthetic():
    return make_data()
