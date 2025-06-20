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

st.title("Managed CTA Strategy – Investor Dashboard")

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
st.subheader("Assets under Management")
col1, col2, col3 = st.columns(3)

col1.metric("**Total Capital (USD)**", f"${total_aum:,.0f}")
col2.metric("Real Capital", f"${total_real:,.0f}")
col3.metric("Virtual Capital", f"${total_virtual:,.0f}")

###############################################################################
#  Performance section
###############################################################################
st.subheader("Performance Metrics")

# Append today's real equity to history (for live numbers)
today_row = pd.Series(
    total_real if total_real > 0 else np.nan,
    index=[pd.Timestamp.utcnow().normalize()]
)
equity_series = history_df["balance"].copy()
equity_series = equity_series.combine_first(today_row)

# Returns
periods = {"30 d": 30, "90 d": 90, "180 d": 180, "Overall": len(equity_series) - 1}
sel = st.radio("Select period", list(periods.keys()), horizontal=True)

ret = window_return(equity_series, periods[sel])
dd = max_drawdown(equity_series)
sharpe = sharpe_ratio(equity_series)

pcol1, pcol2, pcol3 = st.columns(3)
pcol1.metric(f"{sel} Return", f"{ret*100:,.2f} %")
pcol2.metric("Max Drawdown", f"{dd*100:,.2f} %")
pcol3.metric("Sharpe Ratio", f"{sharpe:,.2f}")

st.line_chart(equity_series.rename("Equity (USD)"))

###############################################################################
#  Investor table
###############################################################################
st.subheader("LP Accounts")

inv_df = pd.DataFrame(investors)
inv_df_display = inv_df[["name", "balance", "virtual"]].rename(
    columns={"name": "Investor", "balance": "Balance (USD)", "virtual": "Virtual"}
)
st.dataframe(inv_df_display, hide_index=True)

###############################################################################
#  Controller CRUD interface
###############################################################################
if authenticated:
    st.markdown("### Manage Investors")

    tab_add, tab_delete = st.tabs(["➕ Add Investor", "🗑 Delete Investor"])

    # ▸ Add investor
    with tab_add:
        v_col1, v_col2 = st.columns(2)
        inv_name = v_col1.text_input("Investor Initials / Label")
        is_virtual = v_col1.checkbox("Virtual Investor (manual balance)")
        if is_virtual:
            virt_bal = v_col1.number_input("Starting balance (USD)", min_value=0.0, step=1000.0)
        else:
            api_key = v_col1.text_input("API Key")
            api_sec = v_col1.text_input("API Secret", type="password")

        if st.button("Add"):
            new_inv = {"name": inv_name, "virtual": is_virtual, "balance": 0.0}
            if is_virtual:
                new_inv["balance"] = virt_bal
            else:
                new_inv["api_key"] = api_key
                new_inv["api_secret"] = api_sec
            investors.append(new_inv)
            save_investors(investors)
            st.success("Investor added. Refresh page.")

    # ▸ Delete investor
    with tab_delete:
        del_name = st.selectbox("Select Investor", [i["name"] for i in investors])
        if st.button("Delete"):
            investors = [i for i in investors if i["name"] != del_name]
            save_investors(investors)
            st.success(f"Deleted {del_name}. Refresh page.")
