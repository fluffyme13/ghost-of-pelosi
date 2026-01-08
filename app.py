import streamlit as st
import requests
import pandas as pd

# 1. API Configuration
API_BASE = "https://data-api.polymarket.com"

st.set_page_config(page_title="Polymarket Insider Tracker", layout="wide")
st.title("Polymarket Insider Tracker")
st.markdown("Market moves often precede big insider buys. Track large insider trades on Polymarket in real-time!")

# 2. Sidebar Controls
with st.sidebar:
    st.header("Search Filters")
    threshold = st.number_input("Insider Threshold (USD)", min_value=50000, value=50000, step=100)
    limit = st.slider("Recent Trades to Scan", 10, 500, 100)
    sort_by = st.selectbox("Sort by:", ["Total Spend", "Market Name", "Prediction"])

# 3. Backend Logic: Fetching and Filtering
@st.cache_data(ttl=300)
def get_insider_data(min_spend, trade_limit):
    url = f"{API_BASE}/trades"
    params = {
        "filterType": "CASH",
        "filterAmount": min_spend,
        "limit": trade_limit,
        "takerOnly": "true"
    }
    
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"API Error: {response.status_code}")
        return []

# 4. Displaying the Information
with st.spinner("Fetching insider data..."):
    trades_data = get_insider_data(threshold, limit)

if trades_data:
    df = pd.DataFrame(trades_data)
    
    # Calculate 'Total Spend'
    df['Total Spend'] = df['price'].astype(float) * df['size'].astype(float)
    
    # Filter for 'BUY' side
    buys_df = df[df['side'] == 'BUY'].copy()
    
    if not buys_df.empty:
        # Formatting for the UI
        display_df = buys_df[[
            'proxyWallet', 'title', 'outcome', 'price', 'Total Spend'
        ]].rename(columns={
            'proxyWallet': 'User Address',
            'title': 'Market Name',
            'outcome': 'Prediction',
            'price': 'Odds/Price'
        }).copy()
        
        # Format currency and percentage columns
        display_df['Odds/Price'] = display_df['Odds/Price'].apply(lambda x: f"{float(x):.2%}")
        display_df['Total Spend'] = display_df['Total Spend'].apply(lambda x: f"${x:,.2f}")
        
        # Sort the dataframe
        if sort_by == "Total Spend":
            buys_df = buys_df.sort_values('Total Spend', ascending=False)
        elif sort_by == "Market Name":
            buys_df = buys_df.sort_values('title', ascending=True)
        else:
            buys_df = buys_df.sort_values('outcome', ascending=True)
        
        # Re-create display_df after sorting
        display_df = buys_df[[
            'proxyWallet', 'title', 'outcome', 'price', 'Total Spend'
        ]].rename(columns={
            'proxyWallet': 'User Address',
            'title': 'Market Name',
            'outcome': 'Prediction',
            'price': 'Odds/Price'
        }).copy()
        
        display_df['Odds/Price'] = display_df['Odds/Price'].apply(lambda x: f"{float(x):.2%}")
        display_df['Total Spend'] = display_df['Total Spend'].apply(lambda x: f"${x:,.2f}")
        
        # Display metrics
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Insiders", len(buys_df['proxyWallet'].unique()))
        col2.metric("Avg Trade Size", f"${buys_df['Total Spend'].mean():,.2f}")
        col3.metric("Total Volume", f"${buys_df['Total Spend'].sum():,.2f}")
        
        # Display dataframe
        st.subheader(f"Recent Whale Buys over ${threshold}")
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        # 5. Whale Deep Dive
        st.divider()
        st.subheader("Insider Deep Dive")
        selected_whale = st.selectbox("Pick an insider to see their full portfolio:", options=buys_df['proxyWallet'].unique())
        
        if st.button("Fetch Portfolio"):
            with st.spinner(f"Loading portfolio for {selected_whale}..."):
                pos_url = f"{API_BASE}/positions"
                pos_params = {"user": selected_whale, "sizeThreshold": 100}
                
                try:
                    pos_response = requests.get(pos_url, params=pos_params)
                    if pos_response.status_code == 200:
                        pos_data = pos_response.json()
                        
                        if pos_data:
                            pos_df = pd.DataFrame(pos_data)
                            pos_df['currentValue'] = pos_df['currentValue'].apply(lambda x: f"${x:,.2f}")
                            pos_df['percentPnl'] = pos_df['percentPnl'].apply(lambda x: f"{x:.2%}")
                            st.write(f"This user is currently holding:")
                            st.table(pos_df[['title', 'outcome', 'currentValue', 'percentPnl']])
                        else:
                            st.info("No positions found for this user.")
                    else:
                        st.error(f"Could not fetch positions: {pos_response.status_code}")
                except Exception as e:
                    st.error(f"Error fetching portfolio: {e}")
    else:
        st.warning("No BUY trades found at this threshold.")
else:
    st.info("No insiders found at this threshold. Try lowering the dollar amount in the sidebar.")
