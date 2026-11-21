# Vorab-Registrierung: Trend + Carry

Dieses Dokument wurde **committet, bevor irgendein Backtest gelaufen ist**. Alle
Parameter stammen aus den zitierten Papers bzw. sind hier festgelegt und werden
nach dem Betrachten der Resultate **nicht** verändert. Abweichungen von den
Papers sind unten explizit aufgeführt. Die Git-Historie belegt die Reihenfolge.

## Quellen der Regeln

- **Trend:** Hurst, Ooi, Pedersen (2017), *A Century of Evidence on
  Trend-Following Investing*, Journal of Portfolio Management; Moskowitz, Ooi,
  Pedersen (2012), *Time Series Momentum*, Journal of Financial Economics.
- **Carry:** Koijen, Moskowitz, Pedersen, Vrugt (2018), *Carry*, Journal of
  Financial Economics 127(2), insbesondere Eq. (13) (Bond-Carry), Abschnitt zu
  Equity-Carry (Dividendenrendite minus risikoloser Zins) und Eq. (24)
  (Carry-Timing).

## Universum (ETFs, Total Return via adjustierte Kurse)

| Klasse | Ticker | Trend | Carry-Definition |
|---|---|---|---|
| Aktien | SPY, EFA, EEM | ja | Dividendenrendite (letzte 12 Monate / Kurs) − US-T-Bill |
| Anleihen | IEF, TLT | ja | (Rendite − T-Bill) + Roll-down = Duration × Kurvensteigung pro Jahr (FRED-Zinskurve) |
| Rohstoffe | GLD, DBC | ja | keine (keine freien Futures-Kurven) |
| Währungen | FXE, FXY, FXB, FXA, FXC, FXF | ja | ausländischer Kurzfristzins − US-T-Bill |
| Krypto (nur Variante) | BTC-USD | ja | keine |

Zinsdaten von FRED: US `DTB3`; Anleihen `DGS7`, `DGS10`, `DGS20`, `DGS30`;
EUR `ECBDFR`; JPY/GBP/AUD/CAD/CHF OECD-Call-Money `IRSTCI01xxM156N`
(monatlich, wegen Publikationsverzögerung **um 1 Monat verzögert** verwendet;
Werte älter als 3 Monate gelten als fehlend).

Anleihen-Mapping: IEF → Rendite = Mittel(DGS7, DGS10), Steigung = (DGS10 −
DGS7)/3 pro Jahr, Duration 7.0. TLT → Rendite = Mittel(DGS20, DGS30), Steigung =
(DGS30 − DGS20)/10 pro Jahr, Duration 16.5.

## Signale

- **Trend:** Für jeden Lookback h ∈ {21, 63, 252} Handelstage: Signal =
  Vorzeichen der kumulierten Überrendite (Total Return minus T-Bill) über h.
  Die drei Signale werden gleich gewichtet (Hurst et al.).
- **Carry (Primär):** Signal = Vorzeichen(Cₜ − C̄ₜ), C̄ₜ = expandierender
  Mittelwert der eigenen Monatsend-Carry-Werte bis t (Koijen et al. Eq. 24, Variante
  „historischer Mittelwert“), mindestens 12 Monatswerte.
- **Carry (Variante):** Signal = Vorzeichen(Cₜ), d. h. C̄ = 0.

## Positionsgrösse und Portfolio

- Instrument-Volatilität: EWMA der täglichen Renditen, Center of Mass 60 Tage,
  annualisiert mit √261 (Moskowitz et al. 2012), mindestens 60 Beobachtungen.
- Rohposition = Signal / σᵢ (gleiches Risiko je Instrument).
- Jede Strategie wird auf **10 % annualisierte Ex-ante-Volatilität** skaliert;
  Kovarianz aus rollierenden 36 Monatsrenditen, gleich gewichtet (Hurst et al.,
  Fussnote 7), mindestens 24 Monate.
- Kombination: 50 % Trend + 50 % Carry (je auf 10 % skaliert), danach erneut
  auf 10 % skaliert.
- Monatliches Rebalancing. Signale verwenden Daten **bis und mit dem
  zweitletzten Handelstag** des Monats; die Position wird zum Schlusskurs des
  letzten Handelstags eingenommen und bis zum nächsten Monatsende gehalten.
- Ein Instrument nimmt teil, sobald für die jeweilige Strategie alle
  Eingangsdaten vorhanden sind.

## Kosten

Einweg-Kosten pro gehandeltem Exposure: 5 bp Aktien-/Anleihen-ETFs, 10 bp
GLD/DBC, 10 bp Währungs-ETFs, 30 bp BTC. Renditen sind Überrenditen
(Finanzierung zum T-Bill-Satz).

## Varianten (= Anzahl Versuche für die Deflated Sharpe Ratio, N = 6)

1. Nur Trend
2. Nur Carry (historischer Mittelwert)
3. **Trend + Carry (Primär)**
4. Trend + Carry mit Carry-Variante C̄ = 0
5. Trend + Carry inkl. BTC im Trend-Teil
6. Trend + Carry „umsetzbar“: Brutto-Hebel ≤ 2, zusätzlich 1 % p.a.
   Finanzierungsaufschlag auf Long-Exposure > 1 und 0.5 % p.a. Leihgebühr auf
   Short-Exposure

## Auswertung

- Perioden: gesamt; **vor** Publikation (< 2013-09-01); **nach** Publikation
  (≥ 2013-09-01; NBER-Version von *Carry* erschien August 2013, *Time Series
  Momentum* 2012). **Primär massgebend ist die Periode nach Publikation.**
- Kennzahlen: Rendite, Volatilität, Sharpe, t-Wert, max. Drawdown, Schiefe,
  Korrelation zu SPY, Probabilistic Sharpe Ratio (PSR) und Deflated Sharpe
  Ratio (DSR, Bailey & López de Prado 2014) mit N = 6.
- **Vorab definiertes Erfolgskriterium (Primärvariante, nach Publikation,
  netto):** Sharpe > 0 **und** PSR(0) > 0.95. Die Resultate werden unabhängig
  vom Ergebnis publiziert.

## Bekannte Abweichungen von den Papers

- ETFs statt Futures; Daten erst ab ca. 2005–2008 → kurze Periode vor
  Publikation.
- Equity-Carry: rückwärtsgerichtete Dividendenrendite statt
  Futures-implizierter erwarteter Dividenden.
- Bond-Carry: konstante Duration und lineare Kurveninterpolation.
- Währungs-ETFs zahlen den ausländischen Zins nur teilweise aus (Gebühren,
  Bankzins) → realisierter Carry kleiner als der theoretische.
- Keine Rohstoff-Carry (fehlende Futures-Kurven).
- Carry-Positionen werden volatilitätsgewichtet statt mit $1/$1-Normierung.
