# ===============================================
# 📈 Pro Options Dashboard (Upgraded Final Version)
# ===============================================

import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
import re
import requests
import time

# ===============================================
# Page Config
# ===============================================

st.set_page_config(page_title="Pro Options Dashboard", layout="wide", initial_sidebar_state="expanded")
st.title("🚀 Pro Options Trading Dashboard (Full Version)")

refresh_time = st.sidebar.slider("Refresh Interval (seconds)", 10, 300, 60)

# ===============================================
# Helper Functions
# ===============================================

@st.cache_data(ttl=3600)
def load_fno_symbols():
    """Load NSE F&O symbols dynamically from the web or fallback to local CSV."""
    try:
        nse_url = "https://www.nseindia.com/api/liveEquity-derivatives?index=stock_fno"
        headers = {"User-Agent": "Mozilla/5.0"}
        session = requests.Session()
        session.headers.update(headers)
        res = session.get(nse_url, timeout=10)
        data = res.json()
        symbols = [item['symbol'] for item in data['data']]
        if not symbols:
            raise ValueError("No symbols from live NSE. Falling back.")
    except Exception as e:
        st.warning(f"Live NSE F&O fetch failed: {e}")
        try:
            fallback_df = pd.read_csv("nse_fno_list.csv")
            fallback_df.columns = fallback_df.columns.str.strip().str.upper()
            if 'SYMBOL' not in fallback_df.columns:
                raise ValueError("SYMBOL column missing in fallback CSV.")
            symbols = fallback_df['SYMBOL'].astype(str).str.strip().dropna().unique().tolist()
        except Exception as ex:
            st.error(f"Failed loading F&O symbols from fallback: {ex}")
            return []

    clean_symbols = [re.sub(r'[^A-Za-z0-9]', '', sym).upper() for sym in symbols if sym]
    return sorted(set(clean_symbols))


@st.cache_data(ttl=600)
def validate_symbols(symbols):
    """Filter only valid Yahoo Finance symbols"""
    valid_symbols = []
    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol + ".NS")
            hist = ticker.history(period="1d")
            if not hist.empty:
                valid_symbols.append(symbol)
        except Exception as e:
            st.warning(f"Validation error for {symbol}: {e}")
        time.sleep(0.1)
    if not valid_symbols:
        st.error("❌ No valid symbols found. Check internet or symbol list.")
    return valid_symbols


@st.cache_data(ttl=300)
def get_breakout_screener(symbols):
    breakout_data = []
    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol + ".NS")
            hist = ticker.history(period="5d")
            if hist.empty:
                continue
            current = hist["Close"].iloc[-1]
            yesterday_high = hist["High"].iloc[-2]
            yesterday_low = hist["Low"].iloc[-2]
            ema20 = hist['Close'].ewm(span=20, adjust=False).mean().iloc[-1]
            signal = ""
            if current > ema20:
                signal += "Above 20EMA | "
            if current > yesterday_high:
                signal += "Above Yesterday High | "
            if current < yesterday_low:
                signal += "Below Yesterday Low | "
            breakout_data.append((
                symbol,
                current,
                ema20,
                yesterday_high,
                yesterday_low,
                signal.strip(' | ')
            ))
        except Exception as e:
            st.warning(f"Skipped {symbol}: {e}")
    df = pd.DataFrame(breakout_data, columns=["Stock", "Current Price", "20 EMA", "Prev High", "Prev Low", "Signal"])
    return df


def highlight_signal(val):
    if isinstance(val, str):
        if "Above" in val:
            return 'background-color: lightgreen; font-weight: bold'
        elif "Below" in val:
            return 'background-color: lightcoral; font-weight: bold'
    return ''


@st.cache_data(ttl=300)
def fetch_option_chain(symbol):
    """Fetch simple option chain from NSE"""
    try:
        url = f"https://www.nseindia.com/api/option-chain-equities?symbol={symbol.upper()}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        session = requests.Session()
        session.headers.update(headers)
        response = session.get(url, timeout=10)
        data = response.json()
        records = data['records']['data']
        options = []
        for item in records:
            if 'CE' in item and 'PE' in item:
                ce = item['CE']
                pe = item['PE']
                options.append({
                    'Strike Price': ce.get('strikePrice'),
                    'Call Price': ce.get('lastPrice'),
                    'Call OI': ce.get('openInterest'),
                    'Put Price': pe.get('lastPrice'),
                    'Put OI': pe.get('openInterest')
                })
        return pd.DataFrame(options)
    except Exception as e:
        st.error(f"Option Chain fetch error: {e}")
        return pd.DataFrame()

# ===============================================
# Load Valid Symbols
# ===============================================

st.info("⏳ Loading F&O symbols. Please wait...")

symbols = load_fno_symbols()
st.write("🔍 Raw Symbols Preview:", symbols[:10])
symbols = validate_symbols(symbols)

st.success(f"✅ {len(symbols)} valid F&O symbols loaded.")

# ===============================================
# Dashboard Layout
# ===============================================

# --- Section 1: Breakout Screener ---
st.header("📈 Top 10 NSE F&O Breakout Screener")

screener_df = get_breakout_screener(symbols)
filtered_df = screener_df[screener_df['Signal'] != ""]
top_breakouts = filtered_df.sort_values(by="Current Price", ascending=False).head(10)

st.dataframe(
    top_breakouts.style.format({
        "Current Price": "{:.2f}",
        "20 EMA": "{:.2f}",
        "Prev High": "{:.2f}",
        "Prev Low": "{:.2f}"
    }).map(highlight_signal, subset=["Signal"]),
    use_container_width=True
)

st.divider()

# --- Section 2: Top 5 Options Screener ---
st.header("🔥 Top 5 Stock Options Screener")

option_screener = []

for idx, row in top_breakouts.iterrows():
    spot_price = row['Current Price']
    strike_price = round(spot_price / 50) * 50
    option_type = "CALL" if "Above" in row['Signal'] else "PUT"
    stop_loss = round(spot_price * 0.98, 2) if option_type == "CALL" else round(spot_price * 1.02, 2)
    expiry_type = "Weekly (Intraday)" if spot_price < 1000 else "Monthly"
    
    option_screener.append({
        "Stock": row['Stock'],
        "Option Type": option_type,
        "Current Price": spot_price,
        "Best Strike Price": strike_price,
        "Suggested Stop Loss": stop_loss,
        "Expiry": expiry_type
    })

option_df = pd.DataFrame(option_screener)
st.dataframe(option_df, use_container_width=True)

st.divider()

# --- Section 3: Live NSE Option Chain Viewer ---
st.header("🔮 Live Option Chain Viewer")

selected_stock = st.selectbox("Select Stock for Option Chain", symbols)

if selected_stock:
    st.subheader(f"Live Option Chain: {selected_stock}")
    option_chain_df = fetch_option_chain(selected_stock)
    if not option_chain_df.empty:
        st.dataframe(option_chain_df, use_container_width=True)
    else:
        st.warning("No Option Chain data found!")

st.divider()

# --- Section 4: Event or News Based Strategies ---
st.header("🧠 Event/News Based Options Strategies")

st.subheader("🎯 Examples:")
st.markdown("""
- **Before Budget or RBI Policy**: ATM Straddle or Strangle  
- **Ahead of Quarterly Results**: Covered Call or Protective Put  
- **Volatile Events (e.g., Elections)**: Iron Condor, Calendar Spread
""")

st.info("👉 Strategy recommendations based on event dates coming soon!")

# ===============================================
# Footer
# ===============================================

st.info("🔄 Note: Please manually refresh (Ctrl+R) for latest data. Streamlit doesn't auto-refresh automatically.")
