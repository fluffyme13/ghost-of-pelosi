import streamlit as st
import requests
import pandas as pd
import httpx
import asyncio
from datetime import datetime

# --- EXISTING CODE SECTION ---
API_BASE = "https://data-api.polymarket.com"

st.set_page_config(page_title="Ghost of Pelosi 🏴‍☠️", layout="wide")
st.title("Ghost of Pelosi 🏴‍☠️")

with st.sidebar:
    st.header("Search Filters")
    threshold = st.number_input("Insider Threshold (USD)", min_value=5000, value=50000, step=1000)
    limit = st.slider("Recent Trades to Scan", 10, 500, 100)
    sort_by = st.selectbox("Sort by:", ["Total Spend", "Market Name", "Prediction"])

@st.cache_data(ttl=300)
def get_insider_data(min_spend, trade_limit):
    url = f"{API_BASE}/trades"
    params = {"filterType": "CASH", "filterAmount": min_spend, "limit": trade_limit, "takerOnly": "true"}
    response = requests.get(url, params=params)
    return response.json() if response.status_code == 200 else []

with st.spinner("Fetching insider data..."):
    trades_data = get_insider_data(threshold, limit)

if trades_data:
    df = pd.DataFrame(trades_data)
    df['Total Spend'] = df['price'].astype(float) * df['size'].astype(float)
    buys_df = df[df['side'] == 'BUY'].copy()
    
    if not buys_df.empty:
        # (Your existing metric and display logic remains here)
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Insiders", len(buys_df['proxyWallet'].unique()))
        col2.metric("Avg Trade Size", f"${buys_df['Total Spend'].mean():,.2f}")
        col3.metric("Total Volume", f"${buys_df['Total Spend'].sum():,.2f}")
        
        st.subheader(f"Recent Big Buys over ${threshold}")
        # Simplified display for brevity in this snippet
        st.dataframe(buys_df[['proxyWallet', 'title', 'outcome', 'price', 'Total Spend']], use_container_width=True, hide_index=True)

        st.divider()
        
        # --- NEW SECTION: ASYNC FORENSIC SCANNER ---
        st.header("Insider Scanner")
        st.markdown("This section performs a deep-scan on the wallets above to find 'Burner' accounts (High Spend + New Account + Low Diversification).")

        # Async Helper Functions
        async def fetch_wallet_age(client, address, semaphore):
            async with semaphore:
                try:
                    url = f"{API_BASE}/activity"
                    params = {"user": address, "sortBy": "TIMESTAMP", "sortDirection": "ASC", "limit": 50}
                    response = await client.get(url, params=params, timeout=10.0)
                    res = response.json()
                    if not res: return address, (0, 1)
                    first_ts = res[0]['timestamp']
                    age_days = (datetime.now().timestamp() - first_ts) / 86400
                    unique_markets = len(set(item.get('conditionId') for item in res if item.get('conditionId')))
                    return address, (round(age_days, 2), unique_markets)
                except:
                    return address, (0, 1)

        async def run_forensics(wallets):
            semaphore = asyncio.Semaphore(15) # Concurrent request limit
            async with httpx.AsyncClient() as client:
                tasks = [fetch_wallet_age(client, addr, semaphore) for addr in wallets]
                return dict(await asyncio.gather(*tasks))

        if st.button("Run Scan on These Suspects"):
            unique_wallets = buys_df['proxyWallet'].unique().tolist()
            
            with st.status(f"Analyzing {len(unique_wallets)} wallets...") as status:
                # Run the async loop
                forensics_map = asyncio.run(run_forensics(unique_wallets))
                
                scored_data = []
                for _, row in buys_df.iterrows():
                    addr = row['proxyWallet']
                    age, markets = forensics_map.get(addr, (0, 1))
                    spend = row['Total Spend']
                    
                    # Score: Higher is more suspicious
                    score = (spend / (age + 0.5)) * (1 / markets)
                    
                    scored_data.append({
                        "Insider Score": round(score, 2),
                        "User": addr,
                        "Account Age": f"{age} days",
                        "Markets Traded": markets,
                        "Market": row['title'],
                        "Bet": row['outcome'],
                        "Spend": spend
                    })
                status.update(label="Analysis Complete!", state="complete")

            if scored_data:
                score_df = pd.DataFrame(scored_data).sort_values("Insider Score", ascending=False)
                
                st.subheader("Insider Leaderboard")
                st.dataframe(
                    score_df.style.background_gradient(subset=['Insider Score'], cmap='OrRd')
                    .format({"Spend": "${:,.2f}"}),
                    use_container_width=True, hide_index=True
                )
    else:
        st.warning("No BUY trades found.")
else:
    st.info("No data found.")