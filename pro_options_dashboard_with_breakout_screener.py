
# filename: pro_options_dashboard_with_breakout_screener.py

import streamlit as st
import pandas as pd
import yfinance as yf
import time
import numpy as np

st.set_page_config(page_title="Pro Options Dashboard", layout="wide")
st.title("Pro Options Trading Dashboard - with Breakout Screener")

refresh_time = st.sidebar.slider("Refresh Interval (seconds)", 10, 300, 60)

# ================== Helper Functions ===================

@st.cache_data(ttl=300)
def load_fno_symbols():
    fno_list = pd.read_csv("nse_fno_list.csv")  # you can replace with full list
    return fno_list['SYMBOL'].tolist()

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
            breakout_data.append((symbol.replace(".NS",""), current, ema20, yesterday_high, yesterday_low, signal.strip(' | ')))
        except Exception as e:
            print(f"Error loading {symbol}: {e}")
    df = pd.DataFrame(breakout_data, columns=["Stock", "Current Price", "20 EMA", "Prev High", "Prev Low", "Signal"])
    return df

def highlight_signal(val):
    if "Above" in val:
        return 'background-color: lightgreen; font-weight: bold'
    elif "Below" in val:
        return 'background-color: lightcoral; font-weight: bold'
    return ''

# ================== Dashboard Layout ===================

# Breakout Screener Section
st.header("🚀 Top 10 NSE F&O Breakout Screener")

symbols = load_fno_symbols()
screener_df = get_breakout_screener(symbols)

# Filter only those with a valid breakout
filtered_df = screener_df[screener_df['Signal'] != ""]
top_breakouts = filtered_df.sort_values(by="Current Price", ascending=False).head(10)

st.dataframe(top_breakouts.style.format({
    "Current Price": "{:.2f}",
    "20 EMA": "{:.2f}",
    "Prev High": "{:.2f}",
    "Prev Low": "{:.2f}"
}).applymap(highlight_signal, subset=["Signal"]))

st.info("Note: Screener scans 10-15 stocks/sec; for full NSE F&O list it will take 15-20 seconds.")

# ================== Auto Refresh ===================
time.sleep(refresh_time)
st.experimental_rerun()
