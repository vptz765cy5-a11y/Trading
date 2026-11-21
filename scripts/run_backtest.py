"""Run all pre-registered variants and write results/REPORT.md.

    python scripts/run_backtest.py [--refresh]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from trendcarry import data as data_mod  # noqa: E402
from trendcarry.backtest import complete_months, precompute, run  # noqa: E402
from trendcarry.config import PRIMARY, VARIANTS, Params  # noqa: E402
from trendcarry.stats import dsr, sharpe, summary  # noqa: E402

OUT = ROOT / "results"


def pct(x: float, d: int = 1) -> str:
    return "–" if pd.isna(x) else f"{x * 100:.{d}f} %"


def num(x: float, d: int = 2) -> str:
    return "–" if pd.isna(x) else f"{x:.{d}f}"


def period_table(rets: dict[str, pd.Series], spy: pd.Series, params: Params) -> str:
    srs = [sharpe(r) for r in rets.values()]
    rows = ["| Variante | Zeitraum | Rendite p.a. | Vol. | Sharpe | t-Wert | Max. DD | Schlechtester Monat | Schiefe | Korr. SPY | PSR(0) | DSR (N=6) |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, r in rets.items():
        s = summary(r, spy)
        d = dsr(r, srs, params.n_trials)
        rows.append(f"| {name} | {s['start']}–{s['end']} | {pct(s['ann_return'])} | {pct(s['ann_vol'])} | "
                    f"{num(s['sharpe'])} | {num(s['t_stat'])} | {pct(s['max_dd'])} | {pct(s['worst_month'])} | "
                    f"{num(s['skew'])} | {num(s['corr_spy'])} | {num(s['psr0'])} | {num(d)} |")
    s = summary(spy)
    rows.append(f"| *SPY (Benchmark)* | {s['start']}–{s['end']} | {pct(s['ann_return'])} | {pct(s['ann_vol'])} | "
                f"{num(s['sharpe'])} | {num(s['t_stat'])} | {pct(s['max_dd'])} | {pct(s['worst_month'])} | "
                f"{num(s['skew'])} | 1.00 | {num(s['psr0'])} | – |")
    return "\n".join(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="re-download all data")
    args = ap.parse_args()
    params = Params()

    md = data_mod.load(refresh=args.refresh)
    last = md.tr.index[-1]
    pre = precompute(md, params)
    results = {v.name: run(pre, v, params) for v in VARIANTS}
    rets = {n: complete_months(r.returns, last) for n, r in results.items()}

    # common evaluation window: months in which every variant is invested
    start = max(r.index[0] for r in rets.values())
    rets = {n: r.loc[start:] for n, r in rets.items()}
    spy = complete_months(pre.monthly["SPY"], last).loc[start:]
    cut = pd.Timestamp(params.pub_cutoff)

    periods = {
        "Gesamt": (lambda r: r),
        f"Vor Publikation (< {params.pub_cutoff})": (lambda r: r[r.index < cut]),
        f"**Nach Publikation (≥ {params.pub_cutoff}) – massgebend**": (lambda r: r[r.index >= cut]),
    }

    OUT.mkdir(exist_ok=True)
    prim = rets[PRIMARY.name]
    post = prim[prim.index >= cut]
    ps = summary(post)
    passed = ps["sharpe"] > 0 and ps["psr0"] > 0.95

    lines = [
        "# Resultate: Trend + Carry",
        "",
        f"Daten bis {last.date()} · Auswertung ab {start.strftime('%Y-%m')} (erster Monat, in dem alle Varianten investiert sind).",
        "Alle Renditen sind **monatliche Überrenditen über dem T-Bill-Satz, nach Transaktionskosten**.",
        "Parameter gemäss [PREREGISTRATION.md](../PREREGISTRATION.md) – nicht nachträglich verändert.",
        "",
        "## Vorab definiertes Erfolgskriterium",
        "",
        f"Primärvariante, nach Publikation, netto: Sharpe = **{num(ps['sharpe'])}**, PSR(0) = **{num(ps['psr0'])}** "
        f"→ **{'ERFÜLLT' if passed else 'NICHT ERFÜLLT'}** (verlangt: Sharpe > 0 und PSR(0) > 0.95).",
        "",
    ]
    for title, f in periods.items():
        sub = {n: f(r) for n, r in rets.items()}
        lines += [f"## {title}", "", period_table(sub, f(spy), params), ""]

    # leverage and costs (post-publication)
    lines += ["## Hebel und Kosten (nach Publikation)", "",
              "| Variante | Ø Brutto-Hebel | Max. Brutto-Hebel | Ø Netto-Exposure | Ø Kosten p.a. |",
              "|---|---|---|---|---|"]
    for n, res in results.items():
        held = res.weights.shift(1).reindex(rets[n].index)
        held = held[held.index >= cut]
        gross = held.abs().sum(axis=1)
        c = res.costs.reindex(held.index)
        lines.append(f"| {n} | {num(gross.mean())} | {num(gross.max())} | {num(held.sum(axis=1).mean())} | "
                     f"{pct(c.mean() * 12, 2)} |")
    lines.append("")

    # return attribution by asset class (post-publication, gross of costs)
    classes = {i.ticker: i.asset_class for i in pre.instruments}
    lines += ["## Rendite-Beitrag nach Anlageklasse (nach Publikation, vor Kosten, p.a.)", "",
              "| Variante | " + " | ".join(sorted(set(classes.values()))) + " |",
              "|---" * (len(set(classes.values())) + 1) + "|"]
    for n, res in results.items():
        held = res.weights.shift(1).reindex(rets[n].index)
        held = held[held.index >= cut]
        contrib = (held * pre.monthly.reindex(held.index).fillna(0.0)).T.groupby(classes).sum().T
        lines.append(f"| {n} | " + " | ".join(pct(contrib[c].mean() * 12) if c in contrib else "–"
                                               for c in sorted(set(classes.values()))) + " |")
    lines.append("")

    # behaviour in equity sell-offs (post-publication)
    spy_post = spy[spy.index >= cut]
    worst = spy_post[spy_post <= spy_post.quantile(0.1)].index
    lines += ["## Verhalten in den schlechtesten 10 % der SPY-Monate (nach Publikation)", "",
              "| Variante | Ø Monatsrendite | SPY Ø im selben Monat |", "|---|---|---|"]
    for n, r in rets.items():
        lines.append(f"| {n} | {pct(r.reindex(worst).mean(), 2)} | {pct(spy_post.loc[worst].mean(), 2)} |")
    lines.append("")

    yearly = pd.DataFrame({n: (1 + r).groupby(r.index.year).prod() - 1 for n, r in rets.items()})
    yearly["SPY"] = (1 + spy).groupby(spy.index.year).prod() - 1
    held = results[PRIMARY.name].weights.shift(1).reindex(prim.index)
    n_inst = (held.abs() > 1e-9).sum(axis=1)
    n_year = n_inst.groupby(n_inst.index.year).mean()
    lines += ["## Jahresrenditen (Überrendite, netto)", "",
              "„Instr.“ = durchschnittliche Anzahl Instrumente mit Position in der Primärvariante "
              "(früh im Datensatz existieren viele ETFs noch nicht).", "",
              "| Jahr | Instr. | " + " | ".join(yearly.columns) + " |", "|---" * (len(yearly.columns) + 2) + "|"]
    for y, row in yearly.iterrows():
        lines.append(f"| {y} | {n_year.get(y, float('nan')):.0f} | " + " | ".join(pct(v) for v in row) + " |")
    lines.append("")

    cur = {n: results[n].weights.iloc[-1] for n in (PRIMARY.name, VARIANTS[5].name)}
    cur_df = pd.DataFrame(cur)
    cur_df = cur_df[(cur_df.abs() > 1e-6).any(axis=1)]
    lines += [f"## Aktuelle Zielgewichte (Signal vom {pre.signal_dates[-1].date()}, Anteil am Kapital)", "",
              "| Ticker | " + " | ".join(cur_df.columns) + " |", "|---" * (len(cur_df.columns) + 1) + "|"]
    for t, row in cur_df.iterrows():
        lines.append(f"| {t} | " + " | ".join(pct(v) for v in row) + " |")
    lines.append(f"| **Brutto-Hebel** | " + " | ".join(num(cur_df[c].abs().sum()) for c in cur_df.columns) + " |")
    lines += ["", "![Kumulierte Überrenditen](equity_curves.png)", ""]

    (OUT / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    pd.DataFrame(rets).assign(SPY=spy).to_csv(OUT / "monthly_returns.csv", float_format="%.6f")
    cur_df.to_csv(OUT / "current_weights.csv", float_format="%.6f")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 5.5))
    for n, r in rets.items():
        ax.plot((1 + r).cumprod(), lw=2.2 if n == PRIMARY.name else 1.1, label=n)
    ax.plot((1 + spy).cumprod(), color="grey", ls="--", lw=1, label="SPY (Überrendite)")
    ax.axvline(cut, color="black", lw=0.8)
    ax.text(cut, ax.get_ylim()[1], " Publikation", va="top", fontsize=8)
    ax.set_yscale("log")
    ax.set_title("Kumulierte Überrendite nach Kosten (log)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "equity_curves.png", dpi=130)

    print((OUT / "REPORT.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
