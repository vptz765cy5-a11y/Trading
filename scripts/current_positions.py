"""Current target positions for paper trading (re-run around each month end).

    python scripts/current_positions.py --capital 100000 [--implementable] [--refresh]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from trendcarry import data as data_mod  # noqa: E402
from trendcarry.backtest import precompute, target_weights  # noqa: E402
from trendcarry.config import PRIMARY, VARIANTS, Params  # noqa: E402
from trendcarry.signals import carry_signal, trend_signal  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--capital", type=float, default=100_000.0)
    ap.add_argument("--implementable", action="store_true", help="gross leverage capped at 2")
    ap.add_argument("--refresh", action="store_true", help="re-download data (do this before trading)")
    args = ap.parse_args()

    params = Params()
    variant = VARIANTS[5] if args.implementable else PRIMARY
    md = data_mod.load(refresh=args.refresh)
    pre = precompute(md, params)
    k = len(pre.exec_dates) - 1
    s = pre.signal_dates[k]
    csig = carry_signal(pre.carry_monthly, variant.carry_mode, params.carry_min_months)
    w = target_weights(pre, variant, params, k, csig)

    tickers = [i.ticker for i in pre.instruments if i.asset_class != "crypto"]
    table = pd.DataFrame({
        "trend": trend_signal(pre.excess[tickers], s, params.trend_lookbacks),
        "carry_p.a.": pre.carry_monthly.iloc[k].reindex(tickers),
        "carry_signal": csig.iloc[k].reindex(tickers),
        "vol_p.a.": pre.vol.loc[s, tickers],
        "weight": w.reindex(tickers).fillna(0.0),
    })
    last_px = md.close.loc[:s, tickers].iloc[-1]
    table["amount"] = table["weight"] * args.capital
    table["shares"] = (table["amount"] / last_px).round(0)

    pd.set_option("display.float_format", lambda x: f"{x:,.3f}")
    print(f"Variante: {variant.name} | Signal-Datum: {s.date()} | Daten bis: {md.tr.index[-1].date()}")
    print(table.to_string())
    print(f"\nBrutto-Hebel: {table['weight'].abs().sum():.2f} | Netto: {table['weight'].sum():+.2f}")
    print("Positive Gewichte = kaufen, negative = leerverkaufen. Rebalancing am letzten Handelstag des Monats.")


if __name__ == "__main__":
    main()
