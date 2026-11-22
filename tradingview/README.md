# MNQ 01:00 NY Range Breakout – Testprotokoll

Script: [`mnq_0100_range_breakout.pine`](mnq_0100_range_breakout.pine) (Pine Script v6, Chart MNQ1!, 5 Minuten).

## Regeln

- Range = Hoch/Tief der 5-Minuten-Kerzen 01:00, 01:05, 01:10 (New Yorker Zeit).
- Long, wenn ein 5-Minuten-Kerzenkörper über dem Range-Hoch schliesst; Short, wenn er unter dem Range-Tief schliesst.
- Einstieg zur Eröffnung der nächsten Kerze. Stop auf der anderen Seite der Range. Ziel 0.5 R, gemessen vom tatsächlichen Einstiegskurs.
- **Eigene Annahmen (in den Inputs änderbar):** Einstiege nur 01:15–12:00 NY, maximal ein Trade pro Tag, nur der erste Ausbruch des Tages zählt, offene Positionen werden um 15:55 NY geschlossen. Kosten: 0.85 $ pro Kontrakt und Seite plus 1 Tick Slippage.

## Die 5 Regime-Filter

Jeder Filter verwendet nur den **vorherigen, abgeschlossenen Tag**.

| # | Filter | Regel | Begründung |
|---|---|---|---|
| 1 | Tagestrend | Long nur, wenn der Tagesschluss über dem EMA(50) liegt; Short nur darunter | Ausbrüche in Trendrichtung |
| 2 | Volatilitätsausweitung | ATR(14) > ATR(100) auf Tagesbasis | Bei steigender Volatilität laufen Ausbrüche eher weiter |
| 3 | Range-Grösse | Range-Breite zwischen 5 % und 25 % der Tages-ATR | Zu kleine Range: Kosten und Rauschen dominieren. Zu grosse Range: Stop weit weg |
| 4 | VIX | VIX-Schluss vom Vortag zwischen 12 und 25 | Panikphasen meiden |
| 5 | Trendstärke | ADX(14) auf Tagesbasis > 20 | Nur handeln, wenn der Markt trendet |

## Testprotokoll gegen Overfitting

1. **Vor dem Test festlegen:** Die Filterparameter oben **nicht** verändern. Wer 5 Filter testet und jeden noch tunt, findet fast sicher etwas, das zufällig gut aussieht.
2. **Daten in zwei Perioden teilen** (Inputs *Start*/*End*): ältere ~2/3 = In-Sample, jüngste ~1/3 = Out-of-Sample.
3. Im In-Sample alle 6 Varianten laufen lassen (0 = Baseline ohne Filter). Für jede notieren: Anzahl Trades, Trefferquote, Ø R pro Trade, t-Wert (Tabelle oben rechts).
4. Ein Filter gilt nur als besser, wenn er gegenüber der Baseline das Ø R **und** den t-Wert verbessert und mindestens ~100 Trades übrig bleiben.
5. **Nur den besten Filter** einmal im Out-of-Sample prüfen. Funktioniert er dort nicht, ist er verworfen – nicht nachbessern.
6. Massstab: Ø R netto > 0 und t-Wert > 2 (bei 6 getesteten Varianten besser > 3).

## Wichtige Hinweise

- Bei einem Ziel von 0.5 R braucht es **vor Kosten eine Trefferquote von 66.7 %**, nach Kosten mehr. Die Tabelle zeigt das.
- Auf dem 5-Minuten-Chart zeigt TradingView je nach Abo nur einige Monate Historie. Für einen aussagekräftigen Test braucht es *Deep Backtesting* (Premium) bzw. mehrere Jahre.
- Ohne *Bar Magnifier* (Premium) muss TradingView raten, ob Stop oder Ziel zuerst getroffen wurde, wenn beide in derselben Kerze liegen. Bei engen Ranges passiert das oft.
- MNQ1! ist ein verketteter Kontrakt; Rollwechsel können einzelne Kerzen verzerren.
