# Whale Finder — by Bit_Generation

Single-asset trading dashboard for **XAUT / USD** (Tether Gold), which tracks
the real spot price of gold. It surfaces likely "big-player" activity from
**real exchange volume** — no invented dollar amounts, no fake order book.

## Run

```
python -m streamlit run app.py
```

or just double-click **start.bat**. Opens at http://localhost:8533

## What's on screen

- **Interval selector** — 5m · 10m · 15m · 30m · 1H · 1D · 1W candle sizes.
  (10m is built by aggregating real 5m candles — Bitfinex has no native 10m.)
- **KPI strip** — last price, change, period high/low, total volume, whale
  events, buy pressure.
- **Candlestick chart** — real Bitfinex XAUT/USD trade candles + a gold EMA(12).
- **ІРІ ОЙЫНШЫ / BIG PLAYER** card — BUY% vs SELL%, volume weighted by *where the
  close sits in each candle* (Close Location Value), not just green/red.
- **Whale alert popup** — fires on a real volume spike; shows the actual volume,
  the usual (median) volume, the multiple, the z-score, and Давление вверх/вниз.
- **Signal circles** — green (buy) / red (sell) at whale events. **Click any
  circle** to open that exact whale; a **pulsing ring** marks the selected one
  and tracks it as you zoom/pan. The × closes the card.
- **Hover crosshair + readout** — a crosshair follows the cursor and a top-left
  chip shows that candle's O/H/L/C, volume and time (terminal-style).
- **Layer chips** (bottom centre) — tap `EMA · VWAP · Профиль · Киты` to
  show/hide each layer instantly (no reload). VWAP is the volume-weighted fair
  value; off by default.
- **Smooth chart** — mouse-wheel to zoom, drag to pan, double-click to reset.
  (Turn LIVE off while exploring — auto-refresh rebuilds the chart and resets the view.)
- **Volume profile** — real traded volume by price level, on the right edge.
- **Yellow price tag** + **LIVE badge** + **Auto-refresh 5s** toggle.
- **⚙ Чувствительность** — live sliders for the whale thresholds (volume ×
  median, z-score) and the backtest horizon. Tighten them on stage to show how
  the whale count and hit-rate respond — methodology sensitivity in real time.
- **BACKTEST strip** — after each whale, did price move the "expected" way
  `horizon` candles later? Shows overall / buy / sell hit-rates **plus a
  two-sided binomial test vs a 50% coin-flip (p-value), a 95% Wilson confidence
  interval, and a significance verdict (α = 0.05)** — so you can answer
  *"is this better than chance?"* honestly. **Descriptive hindsight on real
  data — not a prediction, not causal; small samples weaken the conclusion.**

- **Volume heatmap ("Карта" chip)** — Bookmap-style price × time heat: each
  candle's real traded volume spread across its range, so heavy price levels glow
  hot. A volume map, **not** order-book liquidity (no free order book for XAUT).
- **Whale Activity Heatmap** — weekday × hour-of-day grid (UTC) over ~60 days:
  colour = total traded volume, numbers = whale events. Reveals when big players
  are most active (London/NY session hotspots).

## Methodology (the honest core)

| Number | How it's computed |
|---|---|
| Candles | Bitfinex `tXAUT:USD` trade candles (real OHLCV) |
| Volume | Real per-candle traded volume, in XAUT units |
| Whale event | volume ≥ 2.5× rolling **median** *and* robust z-score ≥ 2.5 (median + MAD) |
| Buy/sell pressure | volume × Close Location Value `(close−low)/(high−low)` |

A whale must be both **visibly large** (ratio vs median) and **statistically
unusual** (MAD-based z-score) — so the threshold adapts to gold's own noise
instead of being an arbitrary line.

## Honesty note (PhD-credibility brand)

This is **one exchange's flow** (Bitfinex), not a consolidated order book, and
there is no access to true buy/sell order-flow on the free API — buy/sell
pressure is *inferred* from candle shape (a standard money-flow approximation).
Every figure on screen is auditable from the OHLCV above. Nothing is fabricated.

```
data.py   — Bitfinex fetch + derive (candles, EMA, CLV pressure, whale spikes)
app.py    — Plotly chart + floating overlay cards + KPI strip (Streamlit)
```
