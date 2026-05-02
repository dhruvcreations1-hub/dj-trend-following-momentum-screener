import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import io
from datetime import date, timedelta

st.set_page_config(page_title="NSE Minervini Screener", page_icon="📈", layout="wide")
st.title("📈 NSE Minervini Stock Screener")
st.caption("Scans NSE stocks for Minervini trend-following breakout conditions")

# ── NSE Ticker List ───────────────────────────────────────────────────────────
@st.cache_data(ttl=86400)  # cache for 24 hours
def get_nse_tickers():
    url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    symbols = df["SYMBOL"].str.strip().tolist()
    return [s + ".NS" for s in symbols]

# ── Condition Checker ─────────────────────────────────────────────────────────
 def check_stock_conditions(data, use_c2, use_c3, use_c5, rs_threshold):
    condition_1 = (
        (data["Close"] > data["200MA"]) &
        (data["Close"] >= data["30MA"]) &
        (data["Close"] >= data["40MA"]) &
        (data["30MA"] > data["40MA"])
    )
    condition_2 = data["150MA"] > data["200MA"]
    condition_3 = data["200MA"].diff(20).gt(0) | data["200MA"].diff(120).gt(0)
    condition_4 = data["Close"] > data["50MA"]
    condition_5 = data["RS-Ranking"] >= rs_threshold

    result = condition_1 & condition_4
    if use_c2: result = result & condition_2
    if use_c3: result = result & condition_3
    if use_c5: result = result & condition_5
    return result
 # ── Sidebar Controls ──────────────────────────────────────────────────────────
st.sidebar.header("⚙️ Settings")
rs_threshold = st.sidebar.slider("Min RS Ranking", 50, 99, 70)
max_stocks   = st.sidebar.number_input("Max stocks to scan (0 = all)", 0, 2000, 200)

st.sidebar.markdown("---")
st.sidebar.markdown("**Toggle Conditions:**")
use_c2 = st.sidebar.checkbox("150MA > 200MA", value=True)
use_c3 = st.sidebar.checkbox("200MA slope rising", value=True)
use_c5 = st.sidebar.checkbox("RS Ranking filter", value=True)

run_button = st.sidebar.button("🚀 Run Screener", type="primary")
# ── Main Screener ─────────────────────────────────────────────────────────────
if run_button:
    try:
        tickers_list = get_nse_tickers()
    except Exception as e:
        st.error(f"Failed to fetch NSE stock list: {e}")
        st.stop()

    if max_stocks > 0:
        tickers_list = tickers_list[:max_stocks]

    st.info(f"Scanning {len(tickers_list)} stocks...")

    end_date   = date.today().strftime("%Y-%m-%d")
    start_date = (date.today() - timedelta(days=365)).strftime("%Y-%m-%d")

    good_stocks  = []
    progress_bar = st.progress(0)
    status_text  = st.empty()

    for i, ticker in enumerate(tickers_list):
        progress_bar.progress((i + 1) / len(tickers_list))
        status_text.text(f"Scanning {ticker} ({i+1}/{len(tickers_list)})")

        try:
            data = yf.download(ticker, start=start_date, end=end_date,
                               progress=False, auto_adjust=True)

            if data.empty or len(data) < 200:
                continue

            data["30MA"]  = data["Close"].rolling(30).mean()
            data["40MA"]  = data["Close"].rolling(40).mean()
            data["50MA"]  = data["Close"].rolling(50).mean()
            data["150MA"] = data["Close"].rolling(150).mean()
            data["200MA"] = data["Close"].rolling(200).mean()
            data["RS-Ranking"] = data["Close"].rolling(252).rank(pct=True) * 100

            is_good = check_stock_conditions(data, use_c2, use_c3, use_c5, rs_threshold)


            if is_good.iloc[-1]:
                latest = data.iloc[-1]
                good_stocks.append({
                    "Symbol":      ticker.replace(".NS", ""),
                    "Close":       round(float(latest["Close"]), 2),
                    "30MA":        round(float(latest["30MA"]), 2),
                    "50MA":        round(float(latest["50MA"]), 2),
                    "200MA":       round(float(latest["200MA"]), 2),
                    "RS-Ranking":  round(float(latest["RS-Ranking"]), 1),
                    "Volume":      int(latest["Volume"]),
                })

        except Exception:
            continue

    progress_bar.empty()
    status_text.empty()

    # ── Results ───────────────────────────────────────────────────────────────
    if good_stocks:
        df_results = pd.DataFrame(good_stocks)
        df_results = df_results.sort_values("RS-Ranking", ascending=False)

        st.success(f"✅ {len(good_stocks)} stocks match today!")
        st.dataframe(df_results, use_container_width=True)

        csv = df_results.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download CSV", csv, "nse_results.csv", "text/csv")
    else:
        st.warning("No stocks meet the conditions today.")

else:
    st.markdown("""
    ### How to use
    1. Adjust **Min RS Ranking** in the sidebar (default 85)
    2. Set **Max stocks to scan** (lower = faster; 0 = all ~2000 NSE stocks)
    3. Click **Run Screener**
    
    > ⚠️ Scanning all 2000 stocks takes ~15–20 minutes due to Yahoo Finance rate limits.
    > Start with 100–200 for testing.
    """)
