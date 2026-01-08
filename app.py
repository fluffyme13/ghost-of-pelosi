import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import time

# 1. API Configuration
API_BASE = "https://data-api.polymarket.com"

st.set_page_config(page_title="Ghost of Pelosi 🏴‍☠️", layout="wide")
st.title("Ghost of Pelosi 🏴‍☠️")
st.markdown("Hunted by the ghost of high-alpha moves. Tracking the 'Burner' pattern in real-time.")

# 2. Sidebar Controls
with st.sidebar:
    st.header("Search Filters")
    threshold = st.number_input("Insider Threshold (USD)", min_value=5000, value=50000, step=1000)
    limit = st.slider("Recent Trades to Scan", 10, 200, 50)
    st.info("Higher scans take longer as we perform forensic checks on each wallet.")

# 3. Forensic Backend
def get_wallet_forensics(address):
    """Checks account age and market diversity."""
    try:
        # Get the first-ever transaction for age
        url = f"{API_BASE}/activity"
        params = {"user": address, "sortBy": "TIMESTAMP", "sortDirection": "ASC", "limit": 100}
        res = requests.get(url, params=params).json()
        
        if not res: return 0, 1
        
        first_ts = res[0]['timestamp']
        age_days = (datetime.now().timestamp() - first_ts) / 86400
        
        # Count unique markets to measure concentration
        unique_markets = len(set(item.get('conditionId') for item in res if item.get('conditionId')))
        
        return round(age_days, 2), unique_markets
    except:
        return 0, 1

@st.cache_data(ttl=300)
def get_insider_data(min_spend, trade_limit):
    url = f"{API_BASE}/trades"
    params = {"filterType": "CASH", "filterAmount": min_spend, "limit": trade_limit, "takerOnly": "true"}
    response = requests.get(url, params=params)
    return response.json() if response.status_code == 200 else []

# 4. Execution & Scoring
with st.status("Performing forensic analysis on whales...", expanded=True) as status:
    trades_data = get_insider_data(threshold, limit)
    
    if trades_data:
        processed_data = []
        for i, t in enumerate(trades_data):
            if t.get('side') != 'BUY': continue
            
            wallet = t['proxyWallet']
            spend = float(t['price']) * float(t['size'])
            
            # Perform Forensic Check
            age, markets = get_wallet_forensics(wallet)
            
            # Calculate Score: High spend + Low Age + Low Markets = High Insider Score
            score = (spend / (age + 0.5)) * (1 / markets)
            
            processed_data.append({
                "User": wallet,
                "Market": t['title'],
                "Spend": spend,
                "Age (Days)": age,
                "Markets": markets,
                "Insider Score": round(score, 2),
                "Prediction": t['outcome'],
                "Odds": f"{float(t['price']):.2%}"
            })
            
        status.update(label="Forensics complete!", state="complete")

# 5. UI Visualization
if processed_data:
    df = pd.DataFrame(processed_data).sort_values("Insider Score", ascending=False)
    
    # Metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Highest Signal", f"{df.iloc[0]['Insider Score']}")
    col2.metric("Newest Wallet", f"{df['Age (Days)'].min()} days")
    col3.metric("Max Single Bet", f"${df['Spend'].max():,.0f}")

    

    st.subheader("⚠️ Suspicious Insider Leaderboard")
    # Styling the table to highlight high scores
    st.dataframe(
        df.style.background_gradient(subset=['Insider Score'], cmap='OrRd'),
        use_container_width=True,
        hide_index=True
    )

    # Deep Dive Selection
    st.divider()
    selected_user = st.selectbox("Select a suspicious wallet for a Full Profile:", df['User'].unique())
    if st.button("Generate Profile"):
        # Reuse your existing portfolio fetch logic here...
        st.write(f"Deep dive for {selected_user} initialized...")
else:
    st.info("No trades found matching these criteria.")