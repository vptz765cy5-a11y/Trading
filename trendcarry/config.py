"""Fixed parameters. See PREREGISTRATION.md - do not tune these after looking at results."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Instrument:
    ticker: str
    asset_class: str  # equity | bond | commodity | fx | crypto
    carry: str | None  # equity | bond | fx | None (no carry signal)
    cost_bps: float  # one-way cost per unit of exposure traded
    rate: str | None = None  # foreign short-rate column (fx only)


UNIVERSE: tuple[Instrument, ...] = (
    Instrument("SPY", "equity", "equity", 5.0),
    Instrument("EFA", "equity", "equity", 5.0),
    Instrument("EEM", "equity", "equity", 5.0),
    Instrument("IEF", "bond", "bond", 5.0),
    Instrument("TLT", "bond", "bond", 5.0),
    Instrument("GLD", "commodity", None, 10.0),
    Instrument("DBC", "commodity", None, 10.0),
    Instrument("FXE", "fx", "fx", 10.0, rate="EUR"),
    Instrument("FXY", "fx", "fx", 10.0, rate="JPY"),
    Instrument("FXB", "fx", "fx", 10.0, rate="GBP"),
    Instrument("FXA", "fx", "fx", 10.0, rate="AUD"),
    Instrument("FXC", "fx", "fx", 10.0, rate="CAD"),
    Instrument("FXF", "fx", "fx", 10.0, rate="CHF"),
)

BTC = Instrument("BTC-USD", "crypto", None, 30.0)

# Bond carry inputs: (short-maturity yield, long-maturity yield, years between them, duration).
# Yield of the ETF = mean of both; roll-down per year = duration * (long - short) / years.
BOND_CURVE: dict[str, tuple[str, str, float, float]] = {
    "IEF": ("DGS7", "DGS10", 3.0, 7.0),
    "TLT": ("DGS20", "DGS30", 10.0, 16.5),
}

# FRED series. Daily series are used with a 1 business-day publication lag.
FRED_DAILY: dict[str, str] = {
    "US": "DTB3",
    "DGS7": "DGS7",
    "DGS10": "DGS10",
    "DGS20": "DGS20",
    "DGS30": "DGS30",
    "EUR": "ECBDFR",
}
# OECD monthly call-money rates. Used one month after the end of the reference month.
FRED_MONTHLY: dict[str, str] = {
    "JPY": "IRSTCI01JPM156N",
    "GBP": "IRSTCI01GBM156N",
    "AUD": "IRSTCI01AUM156N",
    "CAD": "IRSTCI01CAM156N",
    "CHF": "IRSTCI01CHM156N",
}
STALE_DAYS = 93  # rate observations older than ~3 months are treated as missing


@dataclass(frozen=True)
class Params:
    trend_lookbacks: tuple[int, ...] = (21, 63, 252)
    vol_com: int = 60
    vol_min_obs: int = 60
    ann_days: int = 261
    cov_months: int = 36
    cov_min_months: int = 24
    target_vol: float = 0.10
    carry_min_months: int = 12
    pub_cutoff: str = "2013-09-01"
    n_trials: int = 6
    # "implementable" variant only
    max_gross: float = 2.0
    long_financing_spread: float = 0.01
    short_borrow_fee: float = 0.005


@dataclass(frozen=True)
class Variant:
    name: str
    trend: bool = True
    carry: bool = True
    carry_mode: str = "hist_mean"  # hist_mean | zero
    include_btc: bool = False
    implementable: bool = False


VARIANTS: tuple[Variant, ...] = (
    Variant("1 Trend", trend=True, carry=False),
    Variant("2 Carry", trend=False, carry=True),
    Variant("3 Trend+Carry (primary)"),
    Variant("4 Trend+Carry (carry C=0)", carry_mode="zero"),
    Variant("5 Trend+Carry +BTC", include_btc=True),
    Variant("6 Trend+Carry implementable", implementable=True),
)
PRIMARY = VARIANTS[2]
