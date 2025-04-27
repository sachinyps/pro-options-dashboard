import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np

# ================== Page Config ===================
st.set_page_config(page_title="Pro Options Dashboard", layout="wide")
st.title("Pro Options Trading Dashboard - with Breakout Screener")

refresh_time = st.sidebar.slider("Refresh Interval (seconds)", 10, 300, 60)

# ================== Helper Functions ===================

@st.cache_data(ttl=300)
def load_fno_symbols():
    try:
        fno_list = pd.read_csv("nse_fno_list.csv")
        fno_list.columns = fno_list.columns.str.strip().str.upper()  # Clean columns
        if 'SYMBOL' not in fno_list.columns:
            st.error("Error: 'SYMBOL' column not found in FNO list.")
            st.stop()
        return fno_list['SYMBOL'].dropna().unique().tolist()
    except FileNotFoundError:
        st.error("Error: 'nse_fno_list.csv' file not found.")
        st.stop()
    except Exception as e:
        st.error(f"Unexpected error loading FNO symbols: {e}")
        st.stop()

@st.cache_data(ttl=300)
def get_breakout_screener(symbols):
    breakout_data = []
    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
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
                symbol.replace(".NS", ""), 
                current, 
                ema20, 
                yesterday_high, 
                yesterday_low, 
                signal.strip(' | ')
            ))
        except Exception as e:
            st.warning(f"Error loading {symbol}: {e}")
    df = pd.DataFrame(breakout_data, columns=["Stock", "Current Price", "20 EMA", "Prev High", "Prev Low", "Signal"])
    return df

def highlight_signal(val):
    if "Above" in val:
        return 'background-color: lightgreen; font-weight: bold'
    elif "Below" in val:
        return 'background-color: lightcoral; font-weight: bold'
    return ''

# ================== Dashboard Layout ===================

# --- Breakout Screener Section ---
st.header("🚀 Top 10 NSE F&O Breakout Screener")

symbols = load_fno_symbols()
screener_df = get_breakout_screener(symbols)

# Filter only those with a valid breakout
filtered_df = screener_df[screener_df['Signal'] != ""]
top_breakouts = filtered_df.sort_values(by="Current Price", ascending=False).head(10)

st.dataframe(
    top_breakouts.style.format({
        "Current Price": "{:.2f}",
        "20 EMA": "{:.2f}",
        "Prev High": "{:.2f}",
        "Prev Low": "{:.2f}"
    }).applymap(highlight_signal, subset=["Signal"])
)

st.divider()

# --- Global Markets Section ---
st.header("🌎 Global Markets Overview")
st.info("Global markets overview coming soon...")

# --- Indian Indices Section ---
st.header("📈 Indian Indices Overview with Breakout Signals")
st.info("Indian indices breakout scanner coming soon...")

# --- Options Strategies Section ---
st.header("⚡ Top Options Strategies (AI/ML Based)")
st.info("Options strategies recommendations coming soon...")

st.divider()

st.info("Note: Screener scans approx. 10-15 stocks/sec; full NSE F&O list may take 15-20 seconds.")

# ================== Auto Refresh ===================
# Streamlit doesn't support "sleep", so instead we do this:
st.experimental_singleton.clear()  # Optional: Clear old caches if needed
st.experimental_rerun()
