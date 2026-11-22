"""Python port of tradingview/mnq_0100_range_breakout.pine (same rules and defaults).

    python scripts/orb_backtest.py                 # Yahoo 5m data (only the last ~60 days!)
    python scripts/orb_backtest.py --csv file.csv  # own 5m data: columns time,open,high,low,close
                                                   # (time in UTC or with offset)

Same-bar ambiguity (stop and target both inside one 5m candle) is resolved
conservatively (stop first); the optimistic count is reported as well.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass

import numpy as np
import pandas as pd

TZ = "America/New_York"
TICK, POINT_VALUE = 0.25, 2.0  # MNQ
COMMISSION_SIDE, SLIP_TICKS = 0.85, 1
TARGET_R = 0.5
FILTERS = ["0 None", "1 Trend EMA50", "2 ATR14>ATR100", "3 Range 5-25% ATR", "4 VIX 12-25", "5 ADX>20"]


def t(hhmm: str) -> pd.Timestamp:
    return pd.Timestamp(hhmm).time()


def load_intraday(csv: str | None) -> pd.DataFrame:
    if csv:
        df = pd.read_csv(csv)
        df.index = pd.to_datetime(df.pop("time"), utc=True)
    else:
        import yfinance as yf
        df = yf.download("MNQ=F", period="60d", interval="5m", progress=False, auto_adjust=False)
        df.columns = [c[0].lower() for c in df.columns]
    df.index = df.index.tz_convert(TZ)
    return df[["open", "high", "low", "close"]].dropna().sort_index()


def load_daily() -> tuple[pd.DataFrame, pd.Series]:
    import yfinance as yf
    d = yf.download("MNQ=F", period="5y", interval="1d", progress=False, auto_adjust=False)
    d.columns = [c[0].lower() for c in d.columns]
    vix = yf.download("^VIX", period="5y", interval="1d", progress=False, auto_adjust=False)["Close"].squeeze()
    tr = pd.concat([d.high - d.low, (d.high - d.close.shift()).abs(), (d.low - d.close.shift()).abs()], axis=1).max(axis=1)
    d["ema50"] = d.close.ewm(span=50, adjust=False).mean()
    d["atr14"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
    d["atr100"] = tr.ewm(alpha=1 / 100, adjust=False).mean()
    up, dn = d.high.diff(), -d.low.diff()
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    atr = tr.ewm(alpha=1 / 14, adjust=False).mean()
    pdi = 100 * pd.Series(pdm, d.index).ewm(alpha=1 / 14, adjust=False).mean() / atr
    mdi = 100 * pd.Series(mdm, d.index).ewm(alpha=1 / 14, adjust=False).mean() / atr
    d["adx"] = (100 * (pdi - mdi).abs() / (pdi + mdi)).ewm(alpha=1 / 14, adjust=False).mean()
    d.index = pd.DatetimeIndex(d.index.date)
    vix.index = pd.DatetimeIndex(vix.index.date)
    return d, vix


@dataclass
class Trade:
    date: object
    side: int
    entry: float
    stop: float
    target: float
    exit: float
    reason: str
    ambiguous: bool
    r_net: float
    cost_r: float


def allowed(fid: int, side: int, prev: pd.Series | None, vix: float, range_w: float) -> bool:
    if fid == 0:
        return True
    if prev is None or prev.isna().any():
        return False
    if fid == 1:
        return prev.close > prev.ema50 if side > 0 else prev.close < prev.ema50
    if fid == 2:
        return prev.atr14 > prev.atr100
    if fid == 3:
        return 0.05 <= range_w / prev.atr14 <= 0.25
    if fid == 4:
        return 12 <= vix <= 25
    if fid == 5:
        return prev.adx > 20
    raise ValueError(fid)


def run(bars: pd.DataFrame, daily: pd.DataFrame, vix: pd.Series, fid: int) -> list[Trade]:
    trades = []
    for day, g in bars.groupby(bars.index.date):
        tod = g.index.time
        rng = g[(tod >= t("01:00")) & (tod < t("01:15"))]
        if len(rng) < 3:
            continue
        hi, lo = rng.high.max(), rng.low.min()
        prev_d = daily[daily.index < pd.Timestamp(day)]
        prev = prev_d.iloc[-1] if len(prev_d) else None
        prev_v = vix[vix.index < pd.Timestamp(day)]
        v = float(prev_v.iloc[-1]) if len(prev_v) else np.nan

        sess = g[(tod >= t("01:15")) & (tod < t("15:55"))]
        sig_i = None
        for i, (ts, b) in enumerate(sess.iterrows()):
            if ts.time() >= t("12:00"):
                break
            if b.close > hi or b.close < lo:
                sig_i = i
                break
        if sig_i is None or sig_i + 1 >= len(sess):
            continue  # first breakout only; no next bar to fill
        side = 1 if sess.close.iloc[sig_i] > hi else -1
        if not allowed(fid, side, prev, v, hi - lo):
            continue

        entry = sess.open.iloc[sig_i + 1] + side * SLIP_TICKS * TICK
        stop = lo if side > 0 else hi
        risk = (entry - stop) * side
        if risk <= 0:
            continue
        target = entry + side * TARGET_R * risk
        exit_px, reason, amb = None, "", False
        for ts, b in sess.iloc[sig_i + 1:].iterrows():
            hit_stop = b.low <= stop if side > 0 else b.high >= stop
            hit_tgt = b.high >= target if side > 0 else b.low <= target
            if hit_stop:
                amb = hit_tgt
                gap = b.open < stop if side > 0 else b.open > stop
                exit_px = (b.open if gap else stop) - side * SLIP_TICKS * TICK
                reason = "stop"
                break
            if hit_tgt:
                exit_px, reason = target, "target"
                break
        if exit_px is None:  # flat at the end of the trading day
            exit_px, reason = sess.close.iloc[-1] - side * SLIP_TICKS * TICK, "eod"
        cost = 2 * COMMISSION_SIDE
        risk_usd = risk * POINT_VALUE
        pnl = (exit_px - entry) * side * POINT_VALUE - cost
        trades.append(Trade(day, side, entry, stop, target, exit_px, reason, amb, pnl / risk_usd, cost / risk_usd))
    return trades


def summarize(name: str, tr: list[Trade]) -> dict:
    r = pd.Series([x.r_net for x in tr], dtype=float)
    n = len(r)
    amb = [x for x in tr if x.ambiguous]
    return {
        "Filter": name, "Trades": n,
        "Win %": 100 * (r > 0).mean() if n else np.nan,
        "Avg R net": r.mean() if n else np.nan,
        "t-stat": r.mean() / r.std() * np.sqrt(n) if n > 1 and r.std() > 0 else np.nan,
        "Sum R": r.sum(),
        "Avg cost R": np.mean([x.cost_r for x in tr]) if n else np.nan,
        "Same-bar SL+TP": len(amb),
        "Sum R if optimistic": r.sum() + sum(TARGET_R + 1 for _ in amb),  # those stops would have been targets
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv")
    args = ap.parse_args()
    bars = load_intraday(args.csv)
    daily, vix = load_daily()
    rows, all_trades = [], {}
    for fid, name in enumerate(FILTERS):
        tr = run(bars, daily, vix, fid)
        all_trades[name] = tr
        rows.append(summarize(name, tr))
    out = pd.DataFrame(rows).set_index("Filter")
    days = len(set(bars.index.date))
    print(f"Data: {bars.index[0]} – {bars.index[-1]} ({days} days, {len(bars)} bars)")
    print(f"Break-even win rate before costs: {100 / (1 + TARGET_R):.1f} %")
    print(out.round(3).to_string())
    base = pd.DataFrame([x.__dict__ for x in all_trades[FILTERS[0]]])
    if len(base):
        print("\nBaseline exits:", base.reason.value_counts().to_dict(),
              "| median risk (points):", round(float(((base.entry - base.stop) * base.side).median()), 2))


if __name__ == "__main__":
    main()
