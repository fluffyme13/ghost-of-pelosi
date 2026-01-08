import streamlit as st
import pandas as pd
import httpx
import asyncio
from datetime import datetime
import time

# 1. API Configuration
API_BASE = "https://data-api.polymarket.com"

st.set_page_config(page_title="Ghost of Pelosi 🏴‍☠️", layout="wide")
st.title("Ghost of Pelosi 🏴‍☠️ (Async Optimized)")

# 2. Sidebar Controls
with st.sidebar:
    st.header("Search Filters")
    threshold = st.number_input("Insider Threshold (USD)", min_value=5000, value=50000, step=1000)
    limit = st.slider("Recent Trades to Scan", 10, 300, 100)
    concurrency = st.slider("Concurrency Limit", 5, 50, 20)

# 3. Async Forensic Logic
async def fetch_wallet_forensics(client, address, semaphore):
    """Asynchronously fetches wallet age and concentration."""
    async with semaphore: # Limits concurrent requests to avoid API bans
        try:
            url = f"{API_BASE}/activity"
            params = {"user": address, "sortBy": "TIMESTAMP", "sortDirection": "ASC", "limit": 100}
            response = await client.get(url, params=params, timeout=10.0)
            res = response.json()
            
            if not res: return address, (0, 1)
            
            first_ts = res[0]['timestamp']
            age_days = (datetime.now().timestamp() - first_ts) / 86400
            unique_markets = len(set(item.get('conditionId') for item in res if item.get('conditionId')))
            
            return address, (round(age_days, 2), unique_markets)
        except Exception:
            return address, (0, 1)

async def run_bulk_forensics(wallets):
    """Orchestrates multiple wallet lookups in parallel."""
    semaphore = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient() as client:
        tasks = [fetch_wallet_forensics(client, addr, semaphore) for addr in wallets]
        results = await asyncio.gather(*tasks)
        return dict(results)

# 4. Main Data Fetching
@st.cache_data(ttl=300)
def get_recent_trades(min_spend, trade_limit):
    # Using standard requests for the single initial call
    import requests
    url = f"{API_BASE}/trades"
    params = {"filterType": "CASH", "filterAmount": min_spend, "limit": trade_limit, "takerOnly": "true"}
    response = requests.get(url, params=params)
    return response.json() if response.status_code == 200 else []

# 5. UI Execution
trades_data = get_recent_trades(threshold, limit)

if trades_data:
    # Get unique wallets to avoid duplicate calls
    unique_wallets = list(set(t['proxyWallet'] for t in trades_data if t.get('side') == 'BUY'))
    
    with st.status(f"Scanning {len(unique_wallets)} unique insiders in parallel...", expanded=True) as status:
        # Run the async loop
        forensics_map = asyncio.run(run_bulk_forensics(unique_wallets))
        
        processed_data = []
        for t in trades_data:
            if t.get('side') != 'BUY': continue
            
            wallet = t['proxyWallet']
            spend = float(t['price']) * float(t['size'])
            age, markets = forensics_map.get(wallet, (0, 1))
            
            # Score logic: (Spend / Age) * (Inverse of Diversification)
            score = (spend / (age + 0.5)) * (1 / markets)
            
            processed_data.append({
                "Score": round(score, 2),
                "User": wallet,
                "Market": t['title'],
                "Spend": spend,
                "Age (Days)": age,
                "Markets": markets,
                "Prediction": t['outcome']
            })
        status.update(label="Scanning complete!", state="complete")

    if processed_data:
        df = pd.DataFrame(processed_data).sort_values("Score", ascending=False)
        st.subheader("🔥 Insider Leaderboard")
        st.dataframe(
            df.style.background_gradient(subset=['Score'], cmap='OrRd')
            .format({"Spend": "${:,.2f}"}),
            use_container_width=True,
            hide_index=True
        )
else:
    st.info("No trades found. Try lowering the threshold.")