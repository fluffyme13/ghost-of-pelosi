import streamlit as st
import requests
import pandas as pd
import httpx
import asyncio
from datetime import datetime

API_BASE = "https://data-api.polymarket.com"

st.set_page_config(page_title="Ghost of Pelosi 🏴‍☠️", layout="wide")

with st.sidebar:
    st.header("Search Filters")
    threshold = st.number_input("Insider Threshold (USD)", min_value=1000, value=50000, step=1000)
    limit = st.slider("Recent Trades to Scan", 10, 1000, 200) # Increased limit for better filtering
    
    st.subheader("Targeted Markets")
    market_query = st.text_input("Filter by Market Keyword (e.g. Trump, Fed, Crypto)", "")
    
    sort_by = st.selectbox("Sort Table by:", ["Total Spend", "Market Name", "Prediction"])
    st.divider()
    st.info("The Forensic Scanner at the bottom uses async logic to scan wallet histories in parallel.")

#backend
@st.cache_data(ttl=300)
def get_insider_data(min_spend, trade_limit):
    url = f"{API_BASE}/trades"
    params = {"filterType": "CASH", "filterAmount": min_spend, "limit": trade_limit, "takerOnly": "true", "sortBy": "timestamp", "order": "desc"}
    response = requests.get(url, params=params)
    return response.json() if response.status_code == 200 else []

with st.spinner("Fetching insider activity..."):
    trades_data = get_insider_data(threshold, limit)

if trades_data:
    df = pd.DataFrame(trades_data)
    df['Total Spend'] = df['price'].astype(float) * df['size'].astype(float)
    buys_df = df[df['side'] == 'BUY'].copy()
    
    if market_query:
        buys_df = buys_df[buys_df['title'].str.contains(market_query, case=False, na=False)]
    
    if not buys_df.empty:
        if sort_by == "Total Spend": buys_df = buys_df.sort_values('Total Spend', ascending=False)
        elif sort_by == "Market Name": buys_df = buys_df.sort_values('title', ascending=True)
        else: buys_df = buys_df.sort_values('outcome', ascending=True)

        col1, col2, col3 = st.columns(3)
        col1.metric("Unique Insiders", len(buys_df['proxyWallet'].unique()))
        col2.metric("Avg Buy", f"${buys_df['Total Spend'].mean():,.2f}")
        col3.metric("Scanned Volume", f"${buys_df['Total Spend'].sum():,.2f}")
        
        st.subheader(f"Recent Insider Buys > ${threshold} {'matching ' + market_query if market_query else ''}")
        display_df = buys_df[['timestamp', 'proxyWallet', 'title', 'outcome', 'price', 'Total Spend']].copy()
        display_df['timestamp'] = pd.to_datetime(display_df['timestamp'], unit='s').dt.strftime('%Y-%m-%d %H:%M:%S')
        display_df['price'] = display_df['price'].apply(lambda x: f"{float(x):.2%}")
        display_df['Total Spend'] = display_df['Total Spend'].apply(lambda x: f"${x:,.2f}")
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else: 
        st.warning(f"No BUY trades found for '{market_query}' at this threshold.")
else: 
    st.info("No data found at this threshold.")

st.divider()
st.header("Account Analysis")

if trades_data:
    df = pd.DataFrame(trades_data)
    df['Total Spend'] = df['price'].astype(float) * df['size'].astype(float)
    buys_df = df[df['side'] == 'BUY'].copy()
    if market_query:
        buys_df = buys_df[buys_df['title'].str.contains(market_query, case=False, na=False)]
    
    if not buys_df.empty:
        search_col1, search_col2 = st.columns(2)
        with search_col1:
            selected_whale = st.selectbox("Quick-Select Account from Table:", options=[None] + list(buys_df['proxyWallet'].unique()))
        with search_col2:
            manual_search = st.text_input("OR Paste Custom Wallet Address:")

        target_wallet = manual_search if manual_search else selected_whale

        async def fetch_forensics(client, address, semaphore):
            async with semaphore:
                try:
                    url = f"{API_BASE}/activity"
                    params = {"user": address, "limit": 100}
                    response = await client.get(url, params=params)
                    res = response.json()
                    if not res: return address, (0, 0)
                    first_ts = res[-1]['timestamp']
                    age = (datetime.now().timestamp() - first_ts) / 86400
                    unique_mkt = len(set(i.get('conditionId') for i in res if i.get('conditionId')))
                    return address, (round(age, 2), unique_mkt)
                except: return address, (0, 0)

        async def run_bulk_scan(wallets):
            semaphore = asyncio.Semaphore(15)
            async with httpx.AsyncClient() as client:
                tasks = [fetch_forensics(client, w, semaphore) for w in wallets]
                return dict(await asyncio.gather(*tasks))

        btn_col1, btn_col2 = st.columns(2)
        if btn_col1.button("Bulk Scan Table Content"):
            unique_wallets = buys_df['proxyWallet'].unique().tolist()
            with st.status(f"Scanning {len(unique_wallets)} wallets...") as status:
                forensics = asyncio.run(run_bulk_scan(unique_wallets))
                scored_list = []
                for _, row in buys_df.iterrows():
                    addr = row['proxyWallet']
                    age, mkts = forensics.get(addr, (0, 0))
                    # Suspicion Score Calculation
                    score = (row['Total Spend'] / (age + 0.5)) * (1 / (mkts if mkts > 0 else 1))
                    # Format age with hours/minutes if decimal
                    if age < 1:
                        hours = int(age * 24)
                        minutes = int((age * 24 - hours) * 60)
                        age_str = f"{age}d ({hours}h {minutes}m)"
                    else:
                        age_str = f"{age}d"
                    scored_list.append({"Score": round(score, 2), "Wallet": addr, "Age": age_str, "Mkts": mkts, "Market": row['title'], "Outcome": row['outcome'], "Spend": row['Total Spend']})
                status.update(label="Scan Complete!", state="complete")
                
                scan_res_df = pd.DataFrame(scored_list).sort_values("Score", ascending=False)
                st.dataframe(scan_res_df.style.background_gradient(subset=['Score'], cmap='OrRd'), use_container_width=True, hide_index=True)

        if btn_col2.button("Individual Account History") and target_wallet:
            with st.spinner(f"Pulling profile for {target_wallet[:10]}..."):
                pos_res = requests.get(f"{API_BASE}/positions", params={"user": target_wallet})
                if pos_res.status_code == 200:
                    st.write(f"### Current Portfolio for {target_wallet}")
                    pos_df = pd.DataFrame(pos_res.json())
                    if not pos_df.empty:
                        pos_df['currentValue'] = pd.to_numeric(pos_df['currentValue'], errors='coerce')
                        pos_df = pos_df[pos_df['currentValue'] > 0]
                        if not pos_df.empty:
                            st.table(pos_df[['title', 'outcome', 'currentValue']])
                        else: st.info("No active positions with funds.")
                    else: st.info("No active positions.")
                else: st.error("Wallet not found.")
    else:
        st.info("No matching insiders to scan. Try adjusting your keyword or threshold.")