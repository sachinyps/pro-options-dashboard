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
import random
import os

# ===============================================
# Page Config
# ===============================================

st.set_page_config(page_title="Pro Options Dashboard", layout="wide", initial_sidebar_state="expanded")
st.title("🚀 Pro Options Trading Dashboard (Full Version)")

refresh_time = st.sidebar.slider("Refresh Interval (seconds)", 10, 300, 60)

# ===============================================
# Helper Functions
# ===============================================

@st.cache_data(ttl=300)
def load_fno_symbols():
    try:
        fno_list = pd.read_csv("nse_fno_list.csv")
        fno_list.columns = fno_list.columns.str.strip().str.upper()
        if 'SYMBOL' not in fno_list.columns:
            st.error("Error: 'SYMBOL' column not found in FNO list.")
            st.stop()
        symbols = fno_list['SYMBOL'].dropna().unique().tolist()

        # Clean: remove anything except letters and numbers
        clean_symbols = []
        for sym in symbols:
            sym = re.sub(r'[^A-Za-z0-9]', '', sym)  # Remove non-alphanumerics
            if sym:
                clean_symbols.append(sym)
        return clean_symbols
    except FileNotFoundError:
        st.error("Error: 'nse_fno_list.csv' file not found.")
        st.stop()
    except Exception as e:
        st.error(f"Unexpected error loading FNO symbols: {e}")
        st.stop()

@st.cache_data(ttl=300)
def validate_symbols(symbols, max_retries=3, delay=0.75, backup_file="validated_symbols.csv"):
    """Validate Yahoo symbols with rate-limit handling + backup caching."""

    if os.path.exists(backup_file):
        try:
            cached = pd.read_csv(backup_file)
            cached_symbols = cached['SYMBOL'].dropna().unique().tolist()
            st.success(f"Loaded {len(cached_symbols)} cached validated symbols.")
            return cached_symbols
        except Exception as e:
            st.warning(f"Backup cache failed to load: {e}. Rebuilding...")

    st.info("Running validation (may take time due to rate limits)...")
    valid_symbols = []

    for symbol in symbols:
        retries = 0
        success = False
        curr_delay = delay

        while retries < max_retries:
            try:
                ticker = yf.Ticker(symbol + ".NS")
                hist = ticker.history(period="1d")
                if not hist.empty:
                    valid_symbols.append(symbol)
                    success = True
                    break
            except Exception as e:
                if "too many requests" in str(e).lower():
                    st.warning(f"Rate limited on {symbol}. Retrying in {curr_delay:.1f}s...")
                    time.sleep(curr_delay)
                    curr_delay *= 1.5
                    retries += 1
                else:
                    st.warning(f"Validation error for {symbol}: {e}")
                    break

        time.sleep(random.uniform(0.5, 1.0))

    if valid_symbols:
        try:
            pd.DataFrame({"SYMBOL": valid_symbols}).to_csv(backup_file, index=False)
            st.success(f"Saved validated symbols to {backup_file}")
        except Exception as e:
            st.warning(f"Failed to write backup: {e}")

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

st.info("Loading FNO symbols and validating against Yahoo Finance...")
symbols = load_fno_symbols()
symbols = validate_symbols(symbols)

st.success(f"Loaded {len(symbols)} valid F&O symbols.")

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

# --- Section 2: Top 5 Options Screener (Intraday & Monthly) ---
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
st.header("🧐 Event/News Based Options Strategies")

st.subheader("🎯 Examples:")
st.markdown("""
- **Before Budget or RBI Policy**: ATM Straddle or Strangle
- **Ahead of Quarterly Results**: Covered Call or Protective Put
- **Volatile Events (e.g., Elections)**: Iron Condor, Calendar Spread
""")

st.info("🔭 Strategy recommendations based on event dates coming soon!")

# ===============================================
# Footer
# ===============================================

st.info("🔄 Note: Please manually refresh (Ctrl+R) for latest data. Streamlit doesn't auto-refresh automatically.")
