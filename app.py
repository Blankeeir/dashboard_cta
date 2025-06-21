import os, time, json
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st
from binance.client import Client
from utils import (
    load_investors, save_investors, load_history,
    make_client, account_value_usd,
    max_drawdown, sharpe_ratio, window_return
)

###############################################################################
#  Page setup
###############################################################################
st.set_page_config(
    page_title="CTA Strategy Dashboard (Binance)",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    /* Main dashboard styling */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }
    
    /* Header styling */
    .dashboard-header {
        background: linear-gradient(90deg, #1e3a8a 0%, #3b82f6 100%);
        padding: 1.5rem 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    .dashboard-title {
        color: white;
        font-size: 2.5rem;
        font-weight: 700;
        margin: 0;
        text-align: center;
        text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
    }
    
    .dashboard-subtitle {
        color: #e2e8f0;
        font-size: 1.1rem;
        text-align: center;
        margin-top: 0.5rem;
        font-weight: 300;
    }
    
    /* Metric cards styling */
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        border-left: 4px solid #3b82f6;
        margin-bottom: 1rem;
    }
    
    .metric-title {
        color: #64748b;
        font-size: 0.875rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.5rem;
    }
    
    .metric-value {
        color: #1e293b;
        font-size: 2rem;
        font-weight: 700;
        line-height: 1;
    }
    
    /* Performance metrics grid */
    .performance-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1rem;
        margin: 1.5rem 0;
    }
    
    .performance-card {
        background: white;
        padding: 1.25rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        border: 1px solid #e2e8f0;
        text-align: center;
    }
    
    .performance-label {
        color: #64748b;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.5rem;
    }
    
    .performance-value {
        font-size: 1.5rem;
        font-weight: 700;
        margin-bottom: 0.25rem;
    }
    
    .positive { color: #059669; }
    .negative { color: #dc2626; }
    .neutral { color: #3b82f6; }
    
    /* Chart container */
    .chart-container {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        margin: 1.5rem 0;
    }
    
    /* Table styling */
    .dataframe {
        border: none !important;
    }
    
    .dataframe thead th {
        background-color: #f8fafc !important;
        color: #374151 !important;
        font-weight: 600 !important;
        border-bottom: 2px solid #e5e7eb !important;
    }
    
    .dataframe tbody tr:nth-child(even) {
        background-color: #f9fafb !important;
    }
    
    /* Sidebar styling */
    .css-1d391kg {
        background-color: #f8fafc;
    }
    
    /* Button styling */
    .stButton > button {
        background: linear-gradient(90deg, #3b82f6 0%, #1d4ed8 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        font-weight: 600;
        transition: all 0.2s;
    }
    
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 8px rgba(59, 130, 246, 0.3);
    }
    
    /* Radio button styling */
    .stRadio > div {
        flex-direction: row;
        gap: 1rem;
    }
    
    .stRadio > div > label {
        background: white;
        padding: 0.5rem 1rem;
        border-radius: 6px;
        border: 1px solid #e2e8f0;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .stRadio > div > label:hover {
        border-color: #3b82f6;
        background-color: #eff6ff;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="dashboard-header">
    <h1 class="dashboard-title">CTA Strategy Dashboard</h1>
    <p class="dashboard-subtitle">Institutional Grade Quantitative Trading Performance Analytics</p>
</div>
""", unsafe_allow_html=True)

history_df = load_history()

###############################################################################
#  Authentication for Controller Mode
###############################################################################
st.sidebar.header("Controller")
ctrl_mode = st.sidebar.checkbox("Controller mode")

authenticated = False
if ctrl_mode:
    pwd = st.sidebar.text_input("Password", type="password")
    if pwd == os.getenv("ADMIN_PASSWORD", "changeme"):
        authenticated = True
        st.sidebar.success("Authenticated")
    else:
        if pwd:
            st.sidebar.error("Wrong password")

###############################################################################
#  Load investors and refresh real balances
###############################################################################
investors = load_investors()
real_balances = []
total_virtual = 0.0

for inv in investors:
    if inv.get("virtual", False):
        total_virtual += inv["balance"]
        continue

    try:
        client = make_client(inv["api_key"], inv["api_secret"])
        bal = account_value_usd(client)
        inv["balance"] = bal
        inv["last_update"] = datetime.utcnow().isoformat()
        real_balances.append(bal)
    except Exception as e:
        inv["error"] = str(e)
        real_balances.append(0.0)

save_investors(investors)  # persist any balance updates

total_real = sum(real_balances)
total_aum = total_real + total_virtual

###############################################################################
#  Overview boxes
###############################################################################
st.markdown("## 📊 Assets Under Management")

aum_col1, aum_col2, aum_col3 = st.columns([1, 2, 1])
with aum_col2:
    if authenticated:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Total Assets Under Management</div>
            <div class="metric-value">${total_aum:,.0f}</div>
            <div style="color: #64748b; font-size: 0.875rem; margin-top: 0.5rem;">
                Real: ${total_real:,.0f} | Virtual: ${total_virtual:,.0f}
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Total Assets Under Management</div>
            <div class="metric-value">${total_aum:,.0f}</div>
        </div>
        """, unsafe_allow_html=True)

###############################################################################
#  Performance section
###############################################################################
st.markdown("## 📈 Performance Analytics")

if total_aum > 0:
    scale_factor = total_aum / history_df["balance"].iloc[-1] if not history_df.empty else 1.0
    scaled_history = history_df["balance"] * scale_factor
    today_balance = total_aum
else:
    scaled_history = history_df["balance"]
    today_balance = history_df["balance"].iloc[-1] if not history_df.empty else 10000

today_row = pd.Series(
    today_balance,
    index=[pd.Timestamp.utcnow().normalize().tz_localize(None)]
)
equity_series = scaled_history.copy()
equity_series = equity_series.combine_first(today_row).sort_index()

# Returns
periods = {"30 d": 30, "90 d": 90, "180 d": 180, "Overall": len(equity_series) - 1}
st.markdown("### 📅 Performance Period Selection")
sel = st.radio("Performance Period", list(periods.keys()), horizontal=True, label_visibility="collapsed")

ret = window_return(equity_series, periods[sel])
dd = max_drawdown(equity_series)
sharpe = sharpe_ratio(equity_series)

pcol1, pcol2, pcol3 = st.columns(3)
pcol1.metric(f"{sel} Return", f"{ret*100:,.2f} %")
pcol2.metric("Max Drawdown", f"{dd*100:,.2f} %")
pcol3.metric("Sharpe Ratio", f"{sharpe:,.2f}")

st.markdown("### 📊 Equity Curve Analysis")
st.markdown('<div class="chart-container">', unsafe_allow_html=True)
st.line_chart(equity_series.rename("Portfolio Value (USD)"), height=400)
st.markdown('</div>', unsafe_allow_html=True)

###############################################################################
#  Investor table
###############################################################################
st.subheader("LP Accounts")
inv_df = pd.DataFrame(investors)
if not inv_df.empty:
    display_data = []
    for inv in investors:
        balance_formatted = f"${inv['balance']:,.0f}"
        if authenticated:
            investor_type = "🔗 Real" if not inv.get("virtual", False) else "💰 Virtual"
            display_data.append({
                "Investor": inv["name"],
                "Type": investor_type,
                "Balance (USD)": balance_formatted,
                "Status": "✅ Active" if inv["balance"] > 0 else "⚠️ Inactive"
            })
        else:
            display_data.append({
                "Investor": inv["name"],
                "Balance (USD)": balance_formatted,
                "Status": "✅ Active" if inv["balance"] > 0 else "⚠️ Inactive"
            })
    
    inv_df_display = pd.DataFrame(display_data)
else:
    if authenticated:
        inv_df_display = pd.DataFrame(columns=["Investor", "Type", "Balance (USD)", "Status"])
    else:
        inv_df_display = pd.DataFrame(columns=["Investor", "Balance (USD)", "Status"])

st.dataframe(inv_df_display, hide_index=True, use_container_width=True)

###############################################################################
#  Controller CRUD interface
###############################################################################
if authenticated:
    st.markdown("## ⚙️ Portfolio Management Console")
    st.markdown("*Authorized access for portfolio administrators*")

    tab_add, tab_delete = st.tabs(["➕ Add Investor", "🗑 Delete Investor"])

    # ▸ Add investor
    with tab_add:
        st.markdown("#### 📝 Investor Registration Form")
        
        form_col1, form_col2 = st.columns([2, 1])
        
        with form_col1:
            inv_name = st.text_input("🏷️ Investor Identifier", placeholder="Enter investor name or initials")
            is_virtual = st.checkbox("💰 Virtual Investor (Manual Balance Entry)", 
                                   help="Check this for simulated investors with manual balance tracking")
            
            if is_virtual:
                virt_bal = st.number_input("💵 Initial Balance (USD)", 
                                         min_value=0.0, 
                                         step=1000.0,
                                         format="%.0f",
                                         help="Enter the starting balance for this virtual investor")
            else:
                st.markdown("**🔐 Binance API Credentials**")
                api_key = st.text_input("🔑 API Key", 
                                      placeholder="Enter Binance API key",
                                      help="Binance API key for real-time balance tracking")
                api_sec = st.text_input("🔒 API Secret", 
                                      type="password",
                                      placeholder="Enter Binance API secret",
                                      help="Binance API secret (kept secure)")
        
        with form_col2:
            st.markdown("#### ℹ️ Investor Types")
            st.info("**Real Investor**: Connected to Binance API for live balance tracking")
            st.info("**Virtual Investor**: Manual balance entry for simulation purposes")

        if st.button("✅ Add Investor", type="primary"):
            if inv_name:
                new_inv = {"name": inv_name, "virtual": is_virtual, "balance": 0.0}
                if is_virtual:
                    new_inv["balance"] = virt_bal
                else:
                    new_inv["api_key"] = api_key
                    new_inv["api_secret"] = api_sec
                investors.append(new_inv)
                save_investors(investors)
                st.success("✅ Investor successfully added! Please refresh the page to see updates.")
            else:
                st.error("❌ Please enter an investor name.")

    # ▸ Delete investor
    with tab_delete:
        st.markdown("#### 🗑️ Remove Investor")
        st.warning("⚠️ **Warning**: This action cannot be undone. Please confirm before proceeding.")
        
        if investors:
            del_name = st.selectbox("👤 Select Investor to Remove", 
                                  [i["name"] for i in investors],
                                  help="Choose the investor account to permanently remove")
            
            if del_name:
                selected_inv = next((i for i in investors if i["name"] == del_name), None)
                if selected_inv:
                    inv_type = "Virtual" if selected_inv.get("virtual", False) else "Real"
                    balance = selected_inv.get("balance", 0)
                    
                    st.markdown(f"""
                    **Investor Details:**
                    - **Name**: {del_name}
                    - **Type**: {inv_type}
                    - **Balance**: ${balance:,.0f}
                    """)
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🗑️ Confirm Deletion", type="secondary"):
                    investors = [i for i in investors if i["name"] != del_name]
                    save_investors(investors)
                    st.success(f"✅ Successfully removed {del_name}. Please refresh the page.")
            with col2:
                st.button("❌ Cancel", disabled=True)
        else:
            st.info("📭 No investors available to remove.")
