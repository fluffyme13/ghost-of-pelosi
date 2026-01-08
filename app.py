import streamlit as st
import requests
import pandas as pd
import httpx
import asyncio
from datetime import datetime

# --- 1. CONFIG & API ---
API_BASE = "https://data-api.polymarket.com"
st.set_page_config(page_title="Ghost of Pelosi 🏴‍☠️", layout="wide")
st.title("Ghost of Pelosi 🏴‍☠️")

# --- 2. SIDEBAR ---
with st.sidebar:
    st.header("Search Filters")
    threshold = st.number_input("Insider Threshold (USD)", min_value=1000, value=50000)
    limit = st.slider("Recent Trades to Scan", 10, 500, 100)
    sort_by = st.selectbox("Sort by:", ["Total Spend", "Market Name", "Prediction"])

# --- 3. FETCH DATA ---
@st.cache_data(ttl=300)
def get_insider_data(min_spend, trade_limit):
    url = f"{API_BASE}/trades"
    params = {"filterType": "CASH", "filterAmount": min_spend, "limit": trade_limit, "takerOnly": "true"}
    response = requests.get(url, params=params)
    return response.json() if response.status_code == 200 else []

trades_data = get_insider_data(threshold, limit)

# --- 4. MAIN DASHBOARD ---
if trades_data:
    df = pd.DataFrame(trades_data)
    df['Total Spend'] = df['price'].astype(float) * df['size'].astype(float)
    buys_df = df[df['side'] == 'BUY'].copy()
    
    if not buys_df.empty:
        # Metrics
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Insiders", len(buys_df['proxyWallet'].unique()))
        c2.metric("Avg Trade Size", f"${buys_df['Total Spend'].mean():,.2f}")
        c3.metric("Total Volume", f"${buys_df['Total Spend'].sum():,.2f}")
        
        # Main Table
        st.subheader(f"Recent Whale Buys over ${threshold}")
        st.dataframe(buys_df[['proxyWallet', 'title', 'outcome', 'price', 'Total Spend']], use_container_width=True, hide_index=True)

        st.divider()

        # --- 5. ACCOUNT SEARCH & FORENSICS ---
        st.header("🕵️ Forensic Account Search")
        
        col_a, col_b = st.columns(2)
        with col_a:
            # Option 1: Pick from the table above
            selected_from_list = st.selectbox("Select a Whale from the list above:", 
                                            options=[None] + list(buys_df['proxyWallet'].unique()))
        with col_b:
            # Option 2: Manual text search
            manual_address = st.text_input("OR Paste any Wallet Address manually:")

        # Target address is whichever one was interacted with last
        target_account = manual_address if manual_address else selected_from_list

        if target_account:
            if st.button(f"🔍 Run Deep Dive on {target_account[:10]}..."):
                # Forensic logic (Account Age, Diversification, Win Rate)
                with st.spinner("Analyzing wallet history..."):
                    # We use a simple request here for the single search
                    url = f"{API_BASE}/activity"
                    params = {"user": target_account, "limit": 100}
                    resp = requests.get(url, params=params)
                    
                    if resp.status_code == 200 and resp.json():
                        data = resp.json()
                        first_ts = data[-1]['timestamp']
                        age = (datetime.now().timestamp() - first_ts) / 86400
                        markets = len(set(i.get('conditionId') for i in data))
                        
                        # Display Results
                        st.success(f"Analysis Complete for {target_account}")
                        fa1, fa2, fa3 = st.columns(3)
                        fa1.metric("Account Age", f"{int(age)} Days")
                        fa2.metric("Unique Markets", markets)
                        
                        # Suspicion Logic
                        is_suspicious = "High" if (age < 30 and markets < 3) else "Low"
                        fa3.metric("Insider Probability", is_suspicious)
                        
                        st.write("### Current Positions")
                        pos_resp = requests.get(f"{API_BASE}/positions", params={"user": target_account})
                        if pos_resp.status_code == 200:
                            st.dataframe(pd.DataFrame(pos_resp.json())[['title', 'outcome', 'currentValue']], use_container_width=True)
                    else:
                        st.error("Could not find data for this address.")
    else:
        st.warning("No BUY trades found at this threshold.")