"""
Whale Finder — data layer.

Real exchange data for XAUT/USD (Tether Gold, tracks spot gold) from Bitfinex's
public API. Unlike CoinGecko, Bitfinex gives TRUE per-candle traded volume — so
"whale" here means a genuine volume spike in real trades, not a proxy.

  Candle  -> Bitfinex trade candles  [MTS, OPEN, CLOSE, HIGH, LOW, VOLUME]
  Volume  -> real traded volume per candle, in XAUT units
  Pressure-> Close Location Value: where the close sits inside the candle range
             (a standard money-flow approximation), volume-weighted.

No invented dollar amounts. Every number is auditable from the OHLCV above.
"""

import math
import time
import requests
import numpy as np
import pandas as pd

BFX = "https://api-pub.bitfinex.com/v2"
SYMBOL = "tXAUT:USD"          # XAUT / USD — Tether Gold

# UI label -> candle config. Bitfinex native resolutions: 1m,5m,15m,30m,1h,3h,6h,12h,1D,1W.
# 10m is NOT native, so we pull real 5m candles and aggregate them (honest OHLCV math).
TIMEFRAMES = {
    "5m":  {"res": "5m",  "limit": 120},                  # ~10 hours
    "10m": {"res": "5m",  "limit": 240, "agg": "10min"},  # ~20 hours, built from 5m
    "15m": {"res": "15m", "limit": 96},                   # ~24 hours
    "30m": {"res": "30m", "limit": 96},                   # ~48 hours
    "1H":  {"res": "1h",  "limit": 120},                  # ~5 days
    "1D":  {"res": "1D",  "limit": 120},                  # ~4 months
    "1W":  {"res": "1W",  "limit": 90},                   # ~1.7 years
}


def _get(url, params=None, tries=3):
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, params=params, timeout=20)
            if r.status_code == 200:
                return r.json()
            last = f"HTTP {r.status_code}"
        except Exception as e:
            last = str(e)
        time.sleep(1.2 * (i + 1))
    raise RuntimeError(f"Bitfinex request failed: {last}")


def _resample(df, rule):
    """Aggregate finer candles into a coarser interval — real OHLCV math."""
    g = (df.set_index("time")
           .resample(rule)
           .agg({"open": "first", "high": "max", "low": "min",
                 "close": "last", "volume": "sum"})
           .dropna(subset=["open"])
           .reset_index())
    g["t"] = g["time"].apply(lambda x: int(x.timestamp() * 1000))
    return g.sort_values("t").reset_index(drop=True)


def fetch_candles(tf_key="30m"):
    cfg = TIMEFRAMES.get(tf_key, TIMEFRAMES["30m"])
    url = f"{BFX}/candles/trade:{cfg['res']}:{SYMBOL}/hist"
    rows = _get(url, {"limit": cfg["limit"], "sort": -1})   # newest first
    # Bitfinex order is OPEN, CLOSE, HIGH, LOW, VOLUME
    df = pd.DataFrame(rows, columns=["t", "open", "close", "high", "low", "volume"])
    df["time"] = pd.to_datetime(df["t"], unit="ms", utc=True)
    df = df.sort_values("t").reset_index(drop=True)
    if cfg.get("agg"):
        df = _resample(df, cfg["agg"])
    return df


def build_frame(tf_key="1D", spike_mult=2.5, z_min=2.5, ema_period=12, win=14):
    """Candles + EMA + buy/sell pressure + robust whale-spike detection."""
    return _annotate(fetch_candles(tf_key), spike_mult, z_min, ema_period, win)


def _annotate(df, spike_mult=2.5, z_min=2.5, ema_period=12, win=14):
    """Add CLV pressure, EMA, robust volume baseline and whale-spike flags."""
    # --- where does the close sit in the candle? (Close Location Value) ------
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    df["clv"] = ((df["close"] - df["low"]) / rng).fillna(0.5).clip(0, 1)  # 0=sold off, 1=bought up
    df["buy_press"] = df["clv"] >= 0.5

    # --- trend line ----------------------------------------------------------
    df["ema"] = df["close"].ewm(span=ema_period, adjust=False).mean()

    # --- robust volume baseline (median + MAD), excluding the current candle -
    past = df["volume"].shift(1)
    df["baseline"] = past.rolling(win, min_periods=3).median()
    df["mad"] = past.rolling(win, min_periods=3).apply(
        lambda x: (x - x.median()).abs().median(), raw=False)
    vol_mad = float((df["volume"] - df["volume"].median()).abs().median()) if len(df) else 0.0
    df["baseline"] = df["baseline"].fillna(df["volume"].median())
    df["mad"] = df["mad"].fillna(vol_mad)

    df["ratio"] = df["volume"] / df["baseline"].replace(0, np.nan)
    df["ratio"] = df["ratio"].fillna(0.0)
    # robust z-score: how many MADs above the typical interval
    denom = (1.4826 * df["mad"]).replace(0, np.nan)
    df["zscore"] = ((df["volume"] - df["baseline"]) / denom).fillna(0.0)

    # a whale needs to be both visibly larger (ratio) AND statistically unusual
    df["spike"] = (df["ratio"] >= spike_mult) & (df["zscore"] >= z_min)
    # if MAD collapsed (flat series) fall back to the ratio rule alone
    flat = df["mad"] <= 0
    df.loc[flat, "spike"] = df.loc[flat, "ratio"] >= spike_mult

    return df


def summarize(df):
    """Roll up into the card numbers — volume-weighted by buy/sell pressure."""
    buy_vol = float((df["volume"] * df["clv"]).sum())
    sell_vol = float((df["volume"] * (1 - df["clv"])).sum())
    total = buy_vol + sell_vol
    buy_pct = round(100 * buy_vol / total) if total else 50
    sell_pct = 100 - buy_pct

    spikes = df[df["spike"]]
    alert = None
    if len(spikes):
        row = spikes.iloc[-1]                     # most recent real whale event
        alert = {
            "price": float(row["close"]),
            "time": row["time"],
            "ratio": float(row["ratio"]),
            "zscore": float(row["zscore"]),
            "volume": float(row["volume"]),
            "baseline": float(row["baseline"]),
            "up": bool(row["clv"] >= 0.5),
        }

    last = df.iloc[-1]
    return {
        "buy_pct": buy_pct, "sell_pct": sell_pct,
        "last_price": float(last["close"]),
        "prev_price": float(df.iloc[0]["close"]),
        "hi": float(df["high"].max()), "lo": float(df["low"].min()),
        "total_vol": float(df["volume"].sum()),
        "alert": alert, "n_spikes": int(df["spike"].sum()),
    }


def volume_profile(df, bins=22):
    """Volume-by-price: sum real traded volume into horizontal price levels."""
    lo, hi = df["low"].min(), df["high"].max()
    if hi <= lo:
        hi = lo + 1
    mids = ((df["high"] + df["low"]) / 2).clip(lo, hi)
    cats = pd.cut(mids, bins=bins)
    prof = df.groupby(cats, observed=False)["volume"].sum()
    centers = [iv.mid for iv in prof.index]
    return list(centers), list(prof.values)


def _binom_two_sided_p(k, n):
    """Exact two-sided binomial test that the success rate differs from 50%.

    Under H0 (whale direction is a coin flip) each event 'agrees' with p=0.5, so
    P(X=i) is proportional to C(n,i). Outcomes 'as or more extreme' than k are
    those no more likely than the observed one — i.e. C(n,i) <= C(n,k).
    No scipy needed; Python ints are exact.
    """
    if n == 0:
        return 1.0
    ck = math.comb(n, k)
    extreme = sum(math.comb(n, i) for i in range(n + 1) if math.comb(n, i) <= ck)
    return min(1.0, extreme / (2.0 ** n))


def _wilson_ci(k, n, z=1.96):
    """95% Wilson score interval for a proportion (robust at small n)."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    center = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, center - half), min(1.0, center + half))


WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def whale_heatmap(days_back=60, spike_mult=2.5, z_min=2.5):
    """
    When are the whales active? Pulls ~days_back of hourly XAUT candles, runs the
    same whale detection, and buckets everything into a weekday × hour-of-day grid
    (UTC). Returns total traded volume per cell (the colour) and whale-event count
    per cell (the numbers) — so you can see the London/NY session hotspots.
    """
    limit = int(min(days_back * 24, 5000))
    url = f"{BFX}/candles/trade:1h:{SYMBOL}/hist"
    rows = _get(url, {"limit": limit, "sort": -1})
    df = pd.DataFrame(rows, columns=["t", "open", "close", "high", "low", "volume"])
    df["time"] = pd.to_datetime(df["t"], unit="ms", utc=True)
    df = _annotate(df.sort_values("t").reset_index(drop=True), spike_mult, z_min)

    df["wd"] = df["time"].dt.dayofweek          # 0 = Monday
    df["hr"] = df["time"].dt.hour

    full_idx, full_cols = range(7), range(24)
    vol = (df.pivot_table(index="wd", columns="hr", values="volume",
                          aggfunc="sum", fill_value=0.0)
             .reindex(index=full_idx, columns=full_cols, fill_value=0.0))
    whales = (df[df["spike"]].pivot_table(index="wd", columns="hr", values="spike",
                                          aggfunc="count", fill_value=0)
              .reindex(index=full_idx, columns=full_cols, fill_value=0))

    return {
        "z": vol.values.tolist(),                        # colour = volume
        "whales": whales.astype(int).values.tolist(),    # numbers = whale count
        "hours": list(full_cols),
        "days": WEEKDAYS_RU,
        "n_candles": int(len(df)),
        "n_whales": int(df["spike"].sum()),
        "span_days": round(len(df) / 24, 1),
    }


def whale_backtest(df, horizon=3):
    """
    Descriptive check: after each whale event, which way did price go `horizon`
    candles later? A buy-whale (close near the high) "agrees" if price then rose;
    a sell-whale if it fell. This is exploratory hindsight on real data — not a
    prediction and not a causal claim. Recent whales that haven't had `horizon`
    candles yet are excluded.
    """
    closes = df["close"].to_numpy()
    n = len(df)
    rows = []  # (is_buy, forward_move_pct, agreed)
    for i in df.index[df["spike"]]:
        j = i + horizon
        if j >= n:
            continue
        fwd = (closes[j] - closes[i]) / closes[i] * 100.0
        is_buy = bool(df.at[i, "buy_press"])
        agreed = (fwd > 0) if is_buy else (fwd < 0)
        rows.append((is_buy, fwd, agreed))

    if not rows:
        return None

    def rate(subset):
        return round(100 * sum(a for *_, a in subset) / len(subset)) if subset else None

    buys = [r for r in rows if r[0]]
    sells = [r for r in rows if not r[0]]

    n = len(rows)
    agreed = sum(a for *_, a in rows)
    pval = _binom_two_sided_p(agreed, n)
    lo, hi = _wilson_ci(agreed, n)
    return {
        "horizon": horizon,
        "n": n,
        "overall": rate(rows),
        "buy": rate(buys), "buy_n": len(buys),
        "sell": rate(sells), "sell_n": len(sells),
        "avg_move": round(sum(abs(f) for _, f, _ in rows) / n, 2),
        "p_value": pval,
        "ci_lo": round(100 * lo), "ci_hi": round(100 * hi),
        "significant": pval < 0.05,
    }


if __name__ == "__main__":
    for tf in TIMEFRAMES:
        d = build_frame(tf)
        s = summarize(d)
        bt = whale_backtest(d, 3)
        acc = f"acc {bt['overall']}% (n{bt['n']})" if bt else "acc n/a"
        print(f"{tf:>4} | candles {len(d):>3} | buy {s['buy_pct']}% | "
              f"whales {s['n_spikes']} | {acc} | last {s['last_price']:.2f}")
