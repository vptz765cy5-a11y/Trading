# Trend + Carry (vorab registriert, ETFs)

Systematische Strategie aus zwei der am besten belegten Renditequellen der
Finanzforschung, umgesetzt mit liquiden ETFs:

- **Trendfolge** nach Hurst, Ooi, Pedersen (2017) bzw. Moskowitz, Ooi, Pedersen (2012)
- **Carry** nach Koijen, Moskowitz, Pedersen, Vrugt (2018)

Die Regeln wurden aus den Papers übernommen und in
[PREREGISTRATION.md](PREREGISTRATION.md) festgehalten und committet, **bevor**
der erste Backtest lief (siehe `git log`). Ausgewertet wird primär die Zeit
**nach** der Publikation der Papers (ab 09/2013). Diese Daten kannten die
Autoren nicht; sie sind ein echter Out-of-Sample-Test.

## Ergebnis (nach Publikation, 09/2013–10/2026, nach Kosten, Überrendite über T-Bill)

| Variante | Rendite p.a. | Vol. | Sharpe | Max. DD | Korr. SPY | Ø Brutto-Hebel |
|---|---|---|---|---|---|---|
| Nur Trend | 4.0 % | 11.3 % | 0.35 | −21.9 % | −0.23 | 2.3 |
| Nur Carry | 4.3 % | 9.4 % | 0.46 | −13.6 % | −0.23 | 2.9 |
| **Trend + Carry (primär)** | **8.4 %** | 10.9 % | **0.77** | −13.9 % | −0.25 | 2.9 |
| Trend + Carry, Hebel ≤ 2 + realistische Finanzierung | 3.6 % | 7.9 % | 0.46 | −14.1 % | −0.33 | 1.9 |
| SPY (zum Vergleich) | 12.5 % | 14.3 % | 0.87 | −24.7 % | 1.00 | 1.0 |

Vorab definiertes Kriterium (primär: Sharpe > 0 und PSR > 0.95): **erfüllt**
(PSR 1.00; Deflated Sharpe Ratio mit N = 6 Varianten: 0.97).
Vollständige Auswertung: [results/REPORT.md](results/REPORT.md).

### Einordnung

- Die Kombination ist klar besser als jede Komponente allein. Das liegt an der
  tiefen Korrelation zwischen Trend und Carry **und** am Hebel, der durch die
  Skalierung auf 10 % Volatilität entsteht (im Schnitt ca. 2.9×).
- Einzeln sind die Komponenten nach Publikation **nicht** statistisch
  signifikant (t-Wert Trend 1.3, Carry 1.7).
- Carry allein war über den ganzen Zeitraum praktisch null und verlor 2008
  über 50 %. Das ist das bekannte Crash-Risiko von Carry in Rezessionen.
- Die Strategie ist im Schnitt netto **short** (−0.6), vor allem in
  Fremdwährungen (= long USD). Der Gewinn verteilt sich aber auf alle
  Anlageklassen (siehe Rendite-Beitrag im Report).
- Ihr Nutzen liegt in der **Diversifikation**: In den schlechtesten 10 % der
  SPY-Monate (Ø −7.1 %) gewann sie im Schnitt +1.9 %. Gegen SPY gewinnt sie
  in Haussephasen nicht.
- Mit realistischen Einschränkungen (Hebel ≤ 2, Finanzierungs- und
  Leihkosten) halbiert sich die Rendite ungefähr.

## Grenzen (bitte lesen)

- **Hebel und Leerverkäufe nötig.** Ohne Margin-Konto ist die Strategie so
  nicht umsetzbar. Die Währungs-ETFs sind wenig volatil und brauchen deshalb
  grosse Positionen.
- ETFs statt Futures; vor 2009 existieren viele ETFs noch nicht. Die Periode
  vor Publikation hat deshalb oft nur 1–9 Instrumente und ist kaum
  aussagekräftig.
- Die ETFs wurden 2026 ausgewählt. Es sind Standard-ETFs, aber ein kleiner
  Selektionseffekt bleibt (sie existieren heute noch).
- Monatsdaten unterschätzen Drawdowns innerhalb eines Monats.
- Steuern, Mindestgrössen, Wechselkurse für CHF-Anleger und Leihverfügbarkeit
  sind nicht modelliert.
- Weitere Abweichungen von den Papers: siehe PREREGISTRATION.md.
- Nach dem ersten Lauf wurde ein **Code-Fehler** behoben: Ein neues ETF ohne
  24 Monate Historie liess die ganze Portfolio-Skalierung ausfallen. Parameter
  wurden dabei nicht verändert; ein Test deckt den Fall jetzt ab.

## Benutzung

```bash
pip install -e ".[dev]"
python scripts/run_backtest.py --refresh      # Daten laden, alle 6 Varianten, schreibt results/
python scripts/current_positions.py --capital 100000 --refresh   # aktuelle Zielpositionen
pytest                                        # Tests (u. a. kein Look-ahead)
```

Daten: Yahoo Finance (via `yfinance`) und FRED; zwischengespeichert in `data/cache/`.

## Empfohlener nächster Schritt

6–12 Monate **Paper-Trading**: An jedem Monatsende `current_positions.py`
laufen lassen, die Positionen notieren und mit dem Backtest vergleichen. Erst
danach mit kleinem Betrag live gehen.

## Aufbau

| Datei | Inhalt |
|---|---|
| `trendcarry/config.py` | Universum, Parameter, Varianten (fix gemäss Vorab-Registrierung) |
| `trendcarry/data.py` | Download, Zins-Verzögerung (Publikations-Lag), Aktualitätsprüfung |
| `trendcarry/signals.py` | Trend- und Carry-Signale |
| `trendcarry/portfolio.py` | Risikogewichtung, Volatilitätsziel, Hebel-Limit |
| `trendcarry/backtest.py` | Monatlicher Backtest inkl. Kosten |
| `trendcarry/stats.py` | Kennzahlen, PSR, Deflated Sharpe Ratio |

## Quellen

- Hurst, Ooi, Pedersen (2017): [A Century of Evidence on Trend-Following Investing](https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing)
- Moskowitz, Ooi, Pedersen (2012): Time Series Momentum, *Journal of Financial Economics* 104(2)
- Koijen, Moskowitz, Pedersen, Vrugt (2018): [Carry](https://research-api.cbs.dk/ws/files/57294842/lasse_heje_pedersen_et_al_carry_acceptedmanuscript.pdf), *Journal of Financial Economics* 127(2)
- Bailey, López de Prado (2014): The Deflated Sharpe Ratio, *Journal of Portfolio Management*
- Carver: [pysystemtrade](https://github.com/pst-group/pysystemtrade) (Vorbild für die robuste Umsetzung)

*Keine Anlageberatung. Vergangene Renditen sind keine Garantie für künftige.*
