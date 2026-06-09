"""
Whale Finder — by Bit_Generation
Single asset: XAUT/USD (Tether Gold) — tracks the real gold price.

Every metric on screen comes from real Bitfinex OHLCV for XAUT.
No invented dollar amounts, no fake order book. See footer.
"""

import datetime as dt
import json

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st
import streamlit.components.v1 as components
from plotly.subplots import make_subplots
from streamlit_autorefresh import st_autorefresh

import data as wf

# ---------------------------------------------------------------- palette ---
BG        = "#0a0a12"
PANEL     = "#0d1320"
GREEN     = "#26d07c"
RED       = "#ff4d5e"
GOLD      = "#FFD700"
CYAN      = "#7df9ff"
LIME      = "#c6f24e"
INK       = "#e8ecf4"
MUTE      = "#7a8499"

st.set_page_config(page_title="Whale Finder · Bit_Generation",
                   page_icon="🐋", layout="wide")

# kill Streamlit chrome so the dashboard fills the frame
st.markdown(f"""
<style>
  #MainMenu, header, footer {{visibility:hidden;}}
  .stApp {{background:{BG};}}
  .block-container {{padding:0.4rem 1.0rem 0.6rem 1.0rem; max-width:100%;}}
  .wf-topbar {{color:{MUTE}; font-size:12px; letter-spacing:.04em;}}
  .wf-foot {{color:{MUTE}; font-size:11.5px; line-height:1.5;
             border-top:1px solid rgba(125,249,255,.08); padding-top:8px; margin-top:6px;}}
  div[data-testid="stToggle"] label p {{color:{INK}; font-size:13px;}}
</style>
""", unsafe_allow_html=True)


# ----------------------------------------------------------------- data -----
@st.cache_data(ttl=45, show_spinner=False)
def load(tf, spike_mult, z_min):
    df = wf.build_frame(tf_key=tf, spike_mult=spike_mult, z_min=z_min)
    return df, wf.summarize(df), wf.volume_profile(df)


@st.cache_data(ttl=900, show_spinner=False)
def load_heatmap(spike_mult, z_min):
    return wf.whale_heatmap(days_back=60, spike_mult=spike_mult, z_min=z_min)


# --------------------------------------------------------------- controls ---
c1, c2, c3, c4, c5 = st.columns([1.45, 1.8, 1.05, 0.85, 0.95])
with c1:
    st.markdown('<div class="wf-topbar">XAUT / USD · Tether Gold · data: Bitfinex'
                '<br><span style="color:#5b6478;font-size:10.5px">'
                'колесо — зум · тащить — двигать · клик по кругу — открыть кита</span>'
                '</div>', unsafe_allow_html=True)
with c2:
    tf = st.segmented_control("Timeframe", list(wf.TIMEFRAMES.keys()),
                              default="30m", label_visibility="collapsed")
    tf = tf or "30m"
with c3:
    with st.popover("⚙ Чувствительность", use_container_width=True):
        spike_mult = st.slider("Объём ≥ × медианы", 1.5, 6.0, 2.5, 0.5,
                               help="Во сколько раз объём свечи должен превышать "
                                    "скользящую медиану, чтобы считаться китом.")
        z_min = st.slider("Порог z-score ≥", 1.0, 5.0, 2.5, 0.5,
                          help="Насколько статистически необычным (median + MAD) "
                               "должен быть объём.")
        horizon = st.slider("Горизонт бэктеста (свечей)", 1, 10, 3, 1,
                            help="Через сколько свечей после кита проверяем цену.")
with c4:
    live = st.toggle("● LIVE 5s", value=False,
                     help="Авто-обновление каждые 5с. Сбрасывает зум и выбранного кита.")
with c5:
    if st.button("↻ Refresh", use_container_width=True):
        st.cache_data.clear()

# layer toggles — Streamlit pills so the choice PERSISTS across LIVE refreshes
layer_sel = st.pills(
    "Слои", ["Карта", "EMA", "VWAP", "Профиль", "Киты"], selection_mode="multi",
    default=["EMA", "Профиль", "Киты"], label_visibility="collapsed", key="layers")
layer_sel = set(layer_sel or [])

if live:
    st_autorefresh(interval=5000, key="wf_tick")

try:
    df, s, (vp_price, vp_vol) = load(tf, spike_mult, z_min)
except Exception as e:
    st.error(f"Could not reach Bitfinex: {e}")
    st.stop()
bt = wf.whale_backtest(df, horizon)

# --- KPI strip — quick read on the whole window ----------------------------
chg = s["last_price"] - s["prev_price"]
chg_pct = 100 * chg / s["prev_price"] if s["prev_price"] else 0
chg_color = GREEN if chg >= 0 else RED
chg_sign = "+" if chg >= 0 else ""
kpis = [
    ("LAST", f"${s['last_price']:,.2f}", INK),
    (f"CHANGE · {tf}", f"{chg_sign}{chg_pct:.2f}%", chg_color),
    ("HIGH", f"${s['hi']:,.2f}", MUTE),
    ("LOW", f"${s['lo']:,.2f}", MUTE),
    ("VOLUME (XAUT)", f"{s['total_vol']:,.0f}", MUTE),
    ("WHALE EVENTS", f"{s['n_spikes']}", CYAN),
    ("BUY PRESSURE", f"{s['buy_pct']}%", GREEN),
]
cells = "".join(
    f'<div class="kpi"><div class="kl">{lbl}</div>'
    f'<div class="kv" style="color:{col}">{val}</div></div>' for lbl, val, col in kpis)
st.markdown(f"""
<style>
  .kpi-strip {{ display:flex; flex-wrap:wrap; gap:0;
                border:1px solid rgba(125,249,255,.10);
                border-radius:12px; background:rgba(13,19,32,.5); overflow:hidden;
                margin:2px 0 6px; }}
  .kpi {{ flex:1 1 110px; padding:9px 14px;
          border-right:1px solid rgba(125,249,255,.07); }}
  .kpi:last-child {{ border-right:none; }}
  .kl {{ color:#6f7990; font-size:9.5px; letter-spacing:.09em; font-weight:600; }}
  .kv {{ font-size:16px; font-weight:700; margin-top:3px;
         font-variant-numeric:tabular-nums; }}
</style>
<div class="kpi-strip">{cells}</div>
""", unsafe_allow_html=True)


# --------------------------------------------------------------- figure -----
def build_figure(df, vp_price, vp_vol, spikes_df, layers):
    show_heat = "Карта" in layers
    show_ema = "EMA" in layers
    show_vwap = "VWAP" in layers
    show_whale = "Киты" in layers
    show_vp = "Профиль" in layers
    fig = make_subplots(
        rows=1, cols=2, column_widths=[0.86, 0.14],
        shared_yaxes=True, horizontal_spacing=0.004,
        specs=[[{"type": "candlestick"}, {"type": "bar"}]],
    )

    # Bookmap-style volume heatmap (behind the candles; toggled by the "Карта" pill)
    hm2 = wf.price_time_heatmap(df, bins=64)
    fig.add_trace(go.Heatmap(
        x=df["time"], y=hm2["prices"], z=hm2["z"], zsmooth="fast",
        zmin=0, zmax=hm2["zmax"],
        colorscale=[[0.0, "rgba(7,11,22,0)"], [0.10, "#0a2a55"], [0.30, "#1668c4"],
                    [0.52, "#21c0d8"], [0.74, "#ff5a1f"], [1.0, "#ffe24a"]],
        showscale=False, hoverinfo="skip", meta="heat", visible=show_heat,
    ), row=1, col=1)

    # candles
    fig.add_trace(go.Candlestick(
        x=df["time"], open=df["open"], high=df["high"],
        low=df["low"], close=df["close"],
        increasing=dict(line=dict(color=GREEN, width=1), fillcolor=GREEN),
        decreasing=dict(line=dict(color=RED, width=1), fillcolor=RED),
        whiskerwidth=0.3, name="XAUT", meta="candle",
        hoverinfo="none",   # custom readout chip handles this instead
    ), row=1, col=1)

    # gold EMA — the slow tide under the candles
    fig.add_trace(go.Scatter(
        x=df["time"], y=df["ema"], mode="lines",
        line=dict(color=GOLD, width=1.6),
        opacity=0.9, name="EMA12", meta="ema", hoverinfo="skip", visible=show_ema,
    ), row=1, col=1)

    # VWAP — volume-weighted fair value (off by default, toggle via chip)
    typ = (df["high"] + df["low"] + df["close"]) / 3
    cumvol = df["volume"].cumsum().where(df["volume"].cumsum() > 0)
    vwap = ((typ * df["volume"]).cumsum() / cumvol).bfill()
    fig.add_trace(go.Scatter(
        x=df["time"], y=vwap, mode="lines",
        line=dict(color="#b18cff", width=1.4, dash="dot"),
        opacity=0.9, name="VWAP", meta="vwap", hoverinfo="skip", visible=show_vwap,
    ), row=1, col=1)

    # whale signal circles — clickable. green = buy pressure, red = sell.
    # customdata carries [event id, ratio] so a click can open that exact whale.
    sp = spikes_df
    if len(sp):
        buys = sp[sp["buy_press"]]
        sells = sp[~sp["buy_press"]]
        for sub, color in ((buys, GREEN), (sells, RED)):
            if not len(sub):
                continue
            yv = sub["low"] * 0.9985 if color == GREEN else sub["high"] * 1.0015
            size = (16 + sub["ratio"] * 2).clip(upper=34)
            cdata = sub[["eid", "ratio"]].to_numpy()
            fig.add_trace(go.Scatter(
                x=sub["time"], y=yv, mode="markers", name="whale", meta="whale",
                marker=dict(symbol="circle-open", size=size, color=color,
                            line=dict(color=color, width=2)),
                customdata=cdata,
                hovertemplate="кит · %{customdata[1]:.1f}× · клик<extra></extra>",
                showlegend=False, visible=show_whale,
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=sub["time"], y=yv, mode="markers", meta="whale",
                marker=dict(symbol="circle", size=5, color=color),
                customdata=cdata, hoverinfo="skip", showlegend=False, visible=show_whale,
            ), row=1, col=1)

    # volume profile — activity by price level, hugging the right edge
    maxv = max(vp_vol) if vp_vol else 1
    bar_colors = [f"rgba(125,249,255,{0.30 + 0.55*(v/maxv):.2f})" for v in vp_vol]
    fig.add_trace(go.Bar(
        x=vp_vol, y=vp_price, orientation="h",
        marker=dict(color=bar_colors, line=dict(width=0)),
        hovertemplate="$%{y:,.0f} · activity %{x:,.0f}<extra></extra>",
        showlegend=False, meta="vprofile", visible=show_vp,
    ), row=1, col=2)

    # current-price marker line + the yellow price tag on the right axis
    last = df["close"].iloc[-1]
    fig.add_hline(y=last, line=dict(color=GOLD, width=1, dash="dot"),
                  opacity=0.5, row=1, col=1)
    fig.add_annotation(
        xref="paper", x=1.0, yref="y", y=last, xanchor="left", yanchor="middle",
        text=f" {last:,.2f} ", showarrow=False,
        font=dict(color="#0a0a12", size=11, family="Segoe UI"),
        bgcolor=GOLD, bordercolor=GOLD, borderpad=2,
    )

    grid = "rgba(245,245,255,0.05)"
    fig.update_layout(
        height=720, margin=dict(l=8, r=58, t=8, b=24),
        paper_bgcolor=BG, plot_bgcolor=BG,
        font=dict(color=MUTE, size=11),
        showlegend=False, bargap=0.15,
        xaxis_rangeslider_visible=False, dragmode="pan",
        hoverlabel=dict(bgcolor=PANEL, font_size=12, font_color=INK),
    )
    # crosshair that follows the cursor
    spike = "rgba(245,237,220,0.35)"
    fig.update_xaxes(row=1, col=1, gridcolor=grid, showline=False,
                     ticks="", nticks=8, color=MUTE,
                     showspikes=True, spikemode="across", spikesnap="cursor",
                     spikethickness=1, spikedash="dot", spikecolor=spike)
    fig.update_yaxes(row=1, col=1, showspikes=True, spikemode="across",
                     spikesnap="cursor", spikethickness=1, spikedash="dot",
                     spikecolor=spike)
    fig.update_xaxes(row=1, col=2, visible=False, autorange="reversed")
    # price ticks live on the far right, like a real terminal
    fig.update_yaxes(row=1, col=1, gridcolor=grid, showticklabels=False)
    fig.update_yaxes(row=1, col=2, side="right", showticklabels=True,
                     gridcolor="rgba(0,0,0,0)", color=MUTE, tickformat=",.0f")
    return fig


def build_heatmap(hm):
    """Weekday × hour-of-day grid — colour = volume, numbers = whale count."""
    whales = hm["whales"]
    text = [[str(c) if c > 0 else "" for c in row] for row in whales]
    fig = go.Figure(go.Heatmap(
        z=hm["z"], x=[f"{h:02d}" for h in hm["hours"]], y=hm["days"],
        customdata=whales, text=text,
        texttemplate="%{text}", textfont=dict(size=9, color="#e8ecf4"),
        colorscale=[[0, "rgba(125,249,255,0.03)"], [0.25, "#15506a"],
                    [0.6, "#2f8fa3"], [1, GOLD]],
        hovertemplate="%{y} · %{x}:00 UTC<br>объём %{z:,.0f} · китов "
                      "%{customdata}<extra></extra>",
        xgap=2, ygap=2,
        colorbar=dict(thickness=9, len=0.92, outlinewidth=0,
                      tickfont=dict(color=MUTE, size=8)),
    ))
    fig.update_layout(
        height=300, margin=dict(l=8, r=8, t=6, b=6),
        paper_bgcolor=BG, plot_bgcolor=BG, font=dict(color=MUTE, size=10),
        yaxis=dict(autorange="reversed"),   # Пн at the top
    )
    fig.update_xaxes(tickfont=dict(color=MUTE, size=9), fixedrange=True,
                     gridcolor="rgba(0,0,0,0)")
    fig.update_yaxes(tickfont=dict(color=MUTE, size=11), fixedrange=True,
                     gridcolor="rgba(0,0,0,0)")
    return fig


# every whale event, ready for the client side to render on click
spikes_df = df[df["spike"]].reset_index(drop=True)
spikes_df["eid"] = range(len(spikes_df))
events = [{
    "price": float(r.close),
    "time": r.time.strftime("%d %b %H:%M") + " UTC",
    "ratio": round(float(r.ratio), 1),
    "z": round(float(r.zscore), 1),
    "vol": int(round(float(r.volume))),
    "base": int(round(float(r.baseline))),
    "up": bool(r.buy_press),
    # plotted marker position, so the glow ring can sit exactly on the dot
    "x": int(r.time.value // 10**6),
    "y": float(r.low) * 0.9985 if r.buy_press else float(r.high) * 1.0015,
} for r in spikes_df.itertuples()]
events_json = json.dumps(events, ensure_ascii=False)

# per-candle OHLCV for the hover readout chip
candles = [{
    "o": round(float(r.open), 2), "h": round(float(r.high), 2),
    "l": round(float(r.low), 2), "c": round(float(r.close), 2),
    "v": int(round(float(r.volume))),
    "up": bool(r.close >= r.open),
    "time": r.time.strftime("%d %b %H:%M"),
} for r in df.itertuples()]
candles_json = json.dumps(candles, ensure_ascii=False)

fig = build_figure(df, vp_price, vp_vol, spikes_df, layer_sel)
plot_div = pio.to_html(fig, include_plotlyjs="cdn", full_html=False,
                       default_width="100%", default_height="720px",
                       config={"displayModeBar": False, "responsive": True,
                               "scrollZoom": True, "doubleClick": "reset"})


# --------------------------------------------------------------- overlays ---
whales_on = "true" if "Киты" in layer_sel else "false"
overlay_html = f"""
<!doctype html><html><head><meta charset="utf-8">
<style>
  * {{ box-sizing:border-box; font-family:'Segoe UI',system-ui,sans-serif; }}
  body {{ margin:0; background:{BG}; }}
  #stage {{ position:relative; width:100%; height:720px; }}
  #chart {{ position:absolute; inset:0; }}
  .hud {{ position:absolute; inset:0; pointer-events:none; }}
  .card {{ pointer-events:auto; background:linear-gradient(160deg,#0e1626,#0a0f1a);
           border:1px solid rgba(125,249,255,.22); border-radius:16px;
           box-shadow:0 10px 40px rgba(0,0,0,.55), 0 0 24px rgba(125,249,255,.06);
           backdrop-filter:blur(2px); }}

  /* ---- header card (top centre) ---- */
  .header-card {{ position:absolute; top:14px; left:50%; transform:translateX(-50%);
                  width:min(640px,72%); padding:14px 24px 16px; text-align:center; }}
  .hc-top {{ display:flex; justify-content:space-between; align-items:center;
             font-size:11.5px; }}
  .brand {{ color:{CYAN}; letter-spacing:.02em; }}
  .brand .dot {{ color:{CYAN}; }}
  .live {{ display:inline-flex; align-items:center; gap:6px; color:{RED};
           border:1px solid rgba(255,77,94,.5); border-radius:20px;
           padding:3px 11px; font-weight:600; letter-spacing:.1em; font-size:10.5px; }}
  .live .blip {{ width:7px;height:7px;border-radius:50%;background:{RED};
                 box-shadow:0 0 8px {RED}; animation:pulse 1.4s infinite; }}
  @keyframes pulse {{ 0%,100%{{opacity:1}} 50%{{opacity:.3}} }}
  .eyebrow {{ color:{CYAN}; letter-spacing:.5em; font-size:11px; margin:12px 0 4px;
              font-weight:600; }}
  .title {{ font-weight:800; line-height:1.04; letter-spacing:.01em; }}
  .title .l1 {{ color:#fff; font-size:30px; }}
  .title .l2 {{ color:{LIME}; font-size:30px; }}
  .subtitle {{ color:{MUTE}; font-size:12px; margin-top:9px; }}

  /* ---- big-player tracker (right) ---- */
  .tracker {{ position:absolute; top:150px; right:74px; width:208px;
              padding:13px 15px; }}
  .tr-head {{ color:{INK}; font-size:12px; font-weight:700; letter-spacing:.04em;
              display:flex; align-items:center; gap:7px; margin-bottom:11px; }}
  .tr-head .gem {{ color:{CYAN}; }}
  .tr-row {{ display:flex; justify-content:space-between; align-items:center;
             font-size:13px; margin:7px 0; }}
  .tr-row .lab {{ display:flex; align-items:center; gap:7px; color:{MUTE}; }}
  .tr-row .lab .d {{ width:8px;height:8px;border-radius:50%; }}
  .tr-row .pct {{ font-weight:700; font-variant-numeric:tabular-nums; }}
  .bar {{ height:6px; border-radius:4px; background:rgba(255,255,255,.06);
          overflow:hidden; margin-top:9px; display:flex; }}
  .bar .g {{ background:{GREEN}; height:100%; }}
  .bar .r {{ background:{RED}; height:100%; }}
  .tr-foot {{ color:{MUTE}; font-size:10px; margin-top:9px; }}

  /* ---- layer toggle chips (bottom centre) ---- */
  .chips {{ position:absolute; bottom:14px; left:50%; transform:translateX(-50%);
            display:flex; gap:7px; pointer-events:auto; }}
  .chip {{ font-size:11px; color:#7a8499; border:1px solid rgba(125,249,255,.14);
           background:rgba(10,15,26,.6); border-radius:20px; padding:4px 13px;
           cursor:pointer; user-select:none; transition:all .15s ease; }}
  .chip:hover {{ border-color:rgba(125,249,255,.4); color:#c4ccda; }}
  .chip.on {{ color:#0a0a12; background:{CYAN}; border-color:{CYAN}; font-weight:600; }}

  /* ---- zoom controls (mobile only — desktop uses wheel/drag) ---- */
  .zoomctl {{ position:absolute; right:7px; top:50%; transform:translateY(-50%);
              display:none; flex-direction:column; gap:7px; pointer-events:auto;
              z-index:6; }}
  .zoomctl button {{ width:34px; height:34px; border-radius:9px; color:#dbe2ee;
                     background:rgba(10,15,26,.78); border:1px solid rgba(125,249,255,.20);
                     font-size:18px; line-height:1; display:grid; place-items:center;
                     cursor:pointer; -webkit-tap-highlight-color:transparent; }}
  .zoomctl button:active {{ background:rgba(125,249,255,.18); }}

  /* ---- selected-whale glow ring ---- */
  .whale-glow {{ position:absolute; width:30px; height:30px; border-radius:50%;
                 border:2px solid {CYAN}; transform:translate(-50%,-50%);
                 pointer-events:none; display:none; z-index:4;
                 animation:whalePulse 1.5s ease-out infinite; }}
  @keyframes whalePulse {{ 0% {{ box-shadow:0 0 0 0 var(--glow); }}
    70% {{ box-shadow:0 0 0 15px rgba(0,0,0,0); }}
    100% {{ box-shadow:0 0 0 0 rgba(0,0,0,0); }} }}

  /* ---- hover OHLC readout (top-left) ---- */
  .readout {{ position:absolute; top:10px; left:16px; pointer-events:none;
              font-size:11.5px; color:#c4ccda; font-variant-numeric:tabular-nums;
              background:rgba(10,15,26,.62); border:1px solid rgba(125,249,255,.12);
              border-radius:9px; padding:5px 11px; white-space:nowrap;
              box-shadow:0 4px 18px rgba(0,0,0,.4); }}
  .readout .ro-t {{ color:#9aa6bd; margin-right:6px; }}
  .readout .ro-k {{ color:#6f7990; margin:0 4px 0 11px; }}

  /* ---- price tag (top-left of chart) ---- */
  .pricetag {{ position:absolute; top:150px; left:24px; pointer-events:none; }}
  .pricetag .p {{ color:#fff; font-size:24px; font-weight:700;
                  font-variant-numeric:tabular-nums; }}
  .pricetag .c {{ font-size:13px; font-weight:600; }}

  /* ---- whale alert (bottom-left) ---- */
  .alert-card {{ position:absolute; bottom:46px; left:40px; width:330px;
                 padding:16px 18px; }}
  .alert-card.quiet {{ width:300px; }}
  .x {{ position:absolute; top:12px; right:13px; background:none; border:none;
        color:{MUTE}; font-size:18px; cursor:pointer; line-height:1; }}
  .alert-head {{ display:flex; gap:12px; align-items:center; }}
  .whale-ic {{ width:38px;height:38px;border-radius:11px; display:grid;
               place-items:center; font-size:18px; border:1px solid; }}
  .alert-title {{ font-size:15px; font-weight:700; }}
  .alert-sub {{ color:{MUTE}; font-size:11.5px; margin-top:2px;
                font-variant-numeric:tabular-nums; }}
  .alert-body {{ color:#c4ccda; font-size:12.5px; line-height:1.55; margin:13px 0; }}
  .alert-foot {{ display:flex; gap:34px; border-top:1px solid rgba(255,255,255,.07);
                 padding-top:11px; }}
  .alert-foot .k {{ color:{MUTE}; font-size:10.5px; }}
  .alert-foot .k2 {{ color:{MUTE}; font-size:9.5px; }}
  .alert-foot .v {{ font-size:17px; font-weight:700; margin-top:2px;
                    font-variant-numeric:tabular-nums; }}

  /* ---- phones: reflow the floating cards so nothing overlaps ---- */
  @media (max-width: 640px) {{
    .header-card {{ width:94%; padding:9px 13px 11px; top:8px; }}
    .hc-top {{ font-size:10px; }}
    .eyebrow {{ font-size:9px; letter-spacing:.32em; margin:6px 0 3px; }}
    .title .l1, .title .l2 {{ font-size:18px; }}
    .subtitle {{ font-size:9.5px; margin-top:4px; }}

    .readout {{ display:none; }}              /* touch screens don't hover */

    .pricetag {{ top:142px; left:12px; }}
    .pricetag .p {{ font-size:18px; }}
    .pricetag .c {{ font-size:11px; }}

    .tracker {{ top:142px; right:8px; width:144px; padding:8px 11px; }}
    .tr-head {{ font-size:9.5px; margin-bottom:7px; }}
    .tr-row {{ font-size:11px; margin:5px 0; }}
    .tr-foot {{ display:none; }}

    .alert-card {{ left:10px; right:10px; width:auto; bottom:50px; padding:12px 14px; }}
    .alert-body {{ font-size:11.5px; margin:9px 0; }}
    .alert-foot {{ gap:22px; }}

    .chips {{ bottom:12px; gap:5px; }}
    .chip {{ font-size:10px; padding:3px 10px; }}

    .whale-glow {{ width:24px; height:24px; }}

    .zoomctl {{ display:flex; }}   /* show zoom buttons on phones */
  }}
</style></head>
<body>
  <div id="stage">
    <div id="chart">{plot_div}</div>
    <div id="whaleGlow" class="whale-glow"></div>
    <div class="hud">

      <div class="card header-card">
        <div class="hc-top">
          <span class="brand"><span class="dot">●</span> Bit_Generation</span>
          <span class="live"><span class="blip"></span> LIVE</span>
        </div>
        <div class="eyebrow">— ТРЕЙДИНГ —</div>
        <div class="title"><span class="l1">КИТТЕРМЕН БІРГЕ</span><br>
             <span class="l2">СДЕЛКА АШУ</span></div>
        <div class="subtitle">Алтындағы киттердің сделкаларын бақыла</div>
      </div>

      <div class="card tracker">
        <div class="tr-head"><span class="gem">◇</span> ІРІ ОЙЫНШЫ · BIG PLAYER</div>
        <div class="tr-row">
          <span class="lab"><span class="d" style="background:{GREEN}"></span> BUY</span>
          <span class="pct" style="color:{GREEN}">{s['buy_pct']}%</span>
        </div>
        <div class="tr-row">
          <span class="lab"><span class="d" style="background:{RED}"></span> SELL</span>
          <span class="pct" style="color:{RED}">{s['sell_pct']}%</span>
        </div>
        <div class="bar">
          <span class="g" style="width:{s['buy_pct']}%"></span>
          <span class="r" style="width:{s['sell_pct']}%"></span>
        </div>
        <div class="tr-foot">доля объёма по силе покупок/продаж (CLV)</div>
      </div>

      <div class="readout" id="readout"></div>

      <div class="pricetag">
        <div class="p">${s['last_price']:,.2f}</div>
        <div class="c" style="color:{chg_color}">{chg_sign}{chg:,.2f} ({chg_sign}{chg_pct:.2f}%)</div>
      </div>

      <div class="card alert-card" id="alertCard"></div>

      <div class="zoomctl">
        <button onclick="zoomX(0.6)" aria-label="zoom in">+</button>
        <button onclick="zoomX(1.7)" aria-label="zoom out">&minus;</button>
        <button onclick="resetZoom()" aria-label="reset">⤢</button>
      </div>
    </div>
  </div>
  <script>
    var GREEN="{GREEN}", RED="{RED}", INK="{INK}";
    var WHALES = {events_json};
    var CANDLES = {candles_json};
    var selectedEid = WHALES.length ? WHALES.length - 1 : null;
    var whalesOn = {whales_on};

    function money(n) {{ return n.toLocaleString("en-US",
      {{minimumFractionDigits:2, maximumFractionDigits:2}}); }}

    // Pulsing ring on the open whale — tracks the dot through zoom/pan.
    function positionGlow() {{
      var g = document.getElementById("whaleGlow");
      if (!g) return;
      var gd = document.querySelector(".plotly-graph-div");
      var w = (selectedEid != null) ? WHALES[selectedEid] : null;
      if (!whalesOn || !w || !gd || !gd._fullLayout || !gd._fullLayout.xaxis.c2p) {{
        g.style.display = "none"; return;
      }}
      var xa = gd._fullLayout.xaxis, ya = gd._fullLayout.yaxis;
      var px = xa._offset + xa.c2p(w.x);
      var py = ya._offset + ya.c2p(w.y);
      if (px < xa._offset || px > xa._offset + xa._length ||
          py < ya._offset || py > ya._offset + ya._length) {{
        g.style.display = "none"; return;
      }}
      g.style.display = "block";
      g.style.left = px + "px";
      g.style.top = py + "px";
      g.style.borderColor = w.up ? GREEN : RED;
      g.style.setProperty("--glow", w.up ? "rgba(38,208,124,.55)" : "rgba(255,77,94,.55)");
    }}

    // Hover readout — that candle's OHLCV, like a real terminal.
    function renderReadout(c) {{
      var el = document.getElementById("readout");
      if (!el || !c) return;
      var cc = c.up ? GREEN : RED;
      el.innerHTML =
        '<span class="ro-t">' + c.time + '</span>' +
        '<span class="ro-k">O</span>' + money(c.o) +
        '<span class="ro-k">H</span>' + money(c.h) +
        '<span class="ro-k">L</span>' + money(c.l) +
        '<span class="ro-k">C</span><b style="color:' + cc + '">' + money(c.c) + '</b>' +
        '<span class="ro-k">Vol</span>' + c.v.toLocaleString();
    }}

    function closeWhale() {{
      var card = document.getElementById("alertCard");
      if (card) card.style.display = "none";
      selectedEid = null;
      positionGlow();
    }}

    // Build the alert card for one whale event (or the quiet state) and show it.
    function renderWhale(w) {{
      var card = document.getElementById("alertCard");
      if (!card) return;
      card.style.display = "";
      if (!w) {{
        card.className = "card alert-card quiet";
        card.innerHTML =
          '<div class="alert-title" style="color:#7a8499">Тихо на рынке</div>' +
          '<div class="alert-body">Сейчас нет интервалов с объёмом ≥ 2.5× медианы.</div>';
        return;
      }}
      var c = w.up ? GREEN : RED;
      var title = w.up ? "Кит покупает" : "Кит продает";
      var press = w.up ? "Давление вверх" : "Давление вниз";
      var verb  = w.up ? "покупать" : "продавать";
      card.className = "card alert-card";
      card.innerHTML =
        '<button class="x" title="закрыть" onclick="closeWhale()">×</button>' +
        '<div class="alert-head"><div class="whale-ic" style="border-color:'+c+'">🐋</div>' +
          '<div><div class="alert-title" style="color:'+c+'">'+title+'</div>' +
          '<div class="alert-sub">$'+money(w.price)+' · '+w.time+'</div></div></div>' +
        '<div class="alert-body">Объём <b style="color:'+INK+'">'+w.vol.toLocaleString()+
          '</b> XAUT против обычных <b style="color:'+INK+'">'+w.base.toLocaleString()+
          '</b> — в <b style="color:'+INK+'">'+w.ratio+'×</b> больше медианы. ' +
          'Вероятно крупный игрок начал '+verb+'.</div>' +
        '<div class="alert-foot"><div><div class="k">Объём</div>' +
          '<div class="v" style="color:'+c+'">'+w.ratio+'×</div>' +
          '<div class="k2">медианы · z '+w.z+'</div></div>' +
          '<div><div class="k">Что значит</div>' +
          '<div class="v" style="color:'+c+'">'+press+'</div></div></div>';
    }}

    // Click a whale circle → open that exact event.
    // Hover any candle → update the OHLC readout.
    function attachInteractions() {{
      var gd = document.querySelector(".plotly-graph-div");
      if (!gd || !gd.on) return false;
      gd.on("plotly_click", function(e) {{
        var p = e.points && e.points[0];
        if (p && p.data && p.data.meta === "whale" && p.customdata) {{
          selectedEid = p.customdata[0];
          renderWhale(WHALES[selectedEid]);
          positionGlow();
        }}
      }});
      gd.on("plotly_hover", function(e) {{
        var p = (e.points || []).find(function(pt) {{
          return pt.data && pt.data.type === "candlestick"; }});
        if (p) renderReadout(CANDLES[p.pointNumber]);
      }});
      gd.on("plotly_relayout", positionGlow);   // keep the ring on the dot when zooming/panning
      // On phones, let finger-swipes scroll the PAGE (don't hijack into chart pan);
      // zooming is handled by the on-screen buttons instead.
      if (window.innerWidth <= 640 && gd._fullLayout && gd._fullLayout.dragmode !== false) {{
        window.Plotly.relayout(gd, {{ dragmode: false }});
      }}
      positionGlow();
      return true;
    }}

    // layer visibility is controlled by Streamlit pills, baked into the figure

    // Reliable zoom buttons (mobile) — pinch is flaky in an iframe, so we drive
    // the time axis directly with a smooth animation, like a trading terminal.
    function toMs(v) {{ return (typeof v === "number") ? v : new Date(v).getTime(); }}
    function zoomX(factor) {{
      var gd = document.querySelector(".plotly-graph-div");
      if (!gd || !window.Plotly || !gd._fullLayout) return;
      var xa = gd._fullLayout.xaxis;
      var lo = toMs(xa.range[0]), hi = toMs(xa.range[1]), span = hi - lo;
      if (!span) return;
      var anchor = hi - span * 0.12;            // keep the latest candles in view
      var ns = span * factor;
      window.Plotly.relayout(gd,
        {{ "xaxis.range": [anchor - ns * 0.88, anchor + ns * 0.12] }});
      setTimeout(positionGlow, 80);
    }}
    function resetZoom() {{
      var gd = document.querySelector(".plotly-graph-div");
      if (!gd || !window.Plotly) return;
      window.Plotly.relayout(gd, {{ "xaxis.autorange": true, "yaxis.autorange": true }});
      setTimeout(positionGlow, 120);
    }}

    function wfFit() {{
      var gd = document.querySelector(".plotly-graph-div");
      if (gd && window.Plotly) {{ window.Plotly.Plots.resize(gd); }}
      positionGlow();
    }}

    window.addEventListener("load", function() {{
      renderWhale(WHALES.length ? WHALES[WHALES.length - 1] : null);
      renderReadout(CANDLES.length ? CANDLES[CANDLES.length - 1] : null);
      var tries = 0;
      var iv = setInterval(function() {{
        if (attachInteractions() || ++tries > 40) clearInterval(iv);
      }}, 150);
      [60, 250, 600, 1200].forEach(function(t) {{ setTimeout(wfFit, t); }});
    }});
    window.addEventListener("resize", wfFit);
  </script>
</body></html>
"""

components.html(overlay_html, height=730, scrolling=False)

# --- backtest strip — what happened AFTER each whale (descriptive only) -----
if bt:
    sig_color = GREEN if bt["significant"] else MUTE
    verdict = "значимо" if bt["significant"] else "не значимо"
    pv = bt["p_value"]
    pv_str = "&lt;0.001" if pv < 0.001 else f"{pv:.3f}"
    bt_items = [
        ("СОБЫТИЙ", f"{bt['n']}", INK),
        ("СОВПАЛО ОБЩЕЕ", f"{bt['overall']}%", CYAN),
        ("95% ДИ (Уилсон)", f"{bt['ci_lo']}–{bt['ci_hi']}%", MUTE),
        ("p vs 50%", pv_str, sig_color),
        ("ВЕРДИКТ α=0.05", verdict, sig_color),
        ("КИТ ПОКУПАЕТ → ВВЕРХ",
         f"{bt['buy']}% · {bt['buy_n']}" if bt["buy"] is not None else "—", GREEN),
        ("КИТ ПРОДАЕТ → ВНИЗ",
         f"{bt['sell']}% · {bt['sell_n']}" if bt["sell"] is not None else "—", RED),
    ]
    bt_cells = "".join(
        f'<div class="kpi"><div class="kl">{l}</div>'
        f'<div class="kv" style="color:{c}">{v}</div></div>' for l, v, c in bt_items)
    bt_html = f'<div class="kpi-strip">{bt_cells}</div>'
    bt_note = (f"Совпадение направления через {bt['horizon']} свечей после кита, "
               f"проверено двусторонним биномиальным тестом против 50% (α=0.05); "
               f"95% доверительный интервал по Уилсону. Ср. модуль движения "
               f"{bt['avg_move']}%. Описательная статистика на исторических данных — "
               "не прогноз и не причинно-следственная связь; малая выборка ослабляет вывод.")
else:
    bt_html = ""
    bt_note = "Недостаточно созревших событий для бэктеста на этом интервале."

st.markdown(f"""
<style>
  .bt-head {{ color:{CYAN}; font-size:10.5px; letter-spacing:.14em; font-weight:700;
              margin:8px 0 5px; }}
  .bt-note {{ color:#6f7990; font-size:10.5px; margin-top:5px; line-height:1.5; }}
</style>
<div class="bt-head">◇ BACKTEST · ЧТО БЫЛО ПОСЛЕ КИТА</div>
{bt_html}
<div class="bt-note">{bt_note}</div>
""", unsafe_allow_html=True)

# --- whale activity heatmap — when do the big players move? -----------------
try:
    hm = load_heatmap(spike_mult, z_min)
except Exception:
    hm = None
if hm and hm["n_candles"]:
    st.markdown(
        f'<div class="bt-head">🔥 КАРТА АКТИВНОСТИ КИТОВ · ВРЕМЯ (UTC)</div>'
        f'<div class="bt-note">Цвет — суммарный объём, числа — события-киты, '
        f'по дню недели и часу (UTC). Последние {hm["span_days"]:.0f} дней · '
        f'{hm["n_whales"]} китов. Ярче = горячее (сессии Лондона/Нью-Йорка).</div>',
        unsafe_allow_html=True)
    st.plotly_chart(build_heatmap(hm), use_container_width=True,
                    config={"displayModeBar": False})

# ------------------------------------------------------------------ foot ----
updated = dt.datetime.utcnow().strftime("%H:%M:%S UTC")
st.markdown(f"""
<div class="wf-foot">
  <b style="color:#9aa6bd">Honesty note.</b>
  Data source: <b>Bitfinex</b> XAUT/USD trade candles (Tether Gold, tracks spot gold) —
  real per-candle traded volume, <b>not</b> a proxy. A "whale" is an interval whose volume
  is both ≥ 2.5× the rolling median <i>and</i> a robust z-score ≥ 2.5 above typical (median+MAD).
  Buy/sell pressure is volume weighted by the Close Location Value — where the close sits inside
  each candle's range. The heatmap ("Карта") spreads each candle's real traded volume across its
  price range — a volume map, <b>not</b> live order-book liquidity. This is one exchange's flow,
  not a consolidated order book, and no dollar figures are invented.
  · {s['n_spikes']} whale events in view · refreshed {updated}
</div>
""", unsafe_allow_html=True)
