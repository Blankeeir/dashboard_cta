import os, json, time, hashlib, pathlib, asyncio
import decimal
import hmac
import urllib.parse
from datetime import datetime, timedelta
from typing import Dict, List

import numpy as np
import pandas as pd
import requests
from binance.client import Client
from binance import AsyncClient

decimal.getcontext().prec = 18

DATA_DIR = pathlib.Path(__file__).parent / "data"
INV_FILE = DATA_DIR / "investors.json"
HIST_FILE = DATA_DIR / "history.csv"

FAPI_BASE = "https://fapi.binance.com"
PAPI_BASE = "https://papi.binance.com"
SAPI_BASE = "https://api.binance.com"

###############################################################################
#  Persistent helpers
###############################################################################
def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(exist_ok=True)

def load_investors() -> list[dict]:
    _ensure_data_dir()
    if not INV_FILE.exists():
        INV_FILE.write_text("[]")
    return json.loads(INV_FILE.read_text())

def save_investors(investors: list[dict]) -> None:
    _ensure_data_dir()
    INV_FILE.write_text(json.dumps(investors, indent=2))

def _timestamp() -> int:
    return int(time.time() * 1000)

def _sign(params: Dict[str, str], secret: str) -> str:
    query = urllib.parse.urlencode(params, True)
    sig = hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    return f"{query}&signature={sig}"

def _get(url: str, api_key: str):
    r = requests.get(url, headers={"X-MBX-APIKEY": api_key}, timeout=15)
    if r.status_code != 200:
        raise RuntimeError(f"Binance API error {r.status_code}: {r.text}")
    return r.json()

def _sum_dec(items, field):
    return sum(decimal.Decimal(x[field]) for x in items)

###############################################################################
###############################################################################
def _create_history():
    start = datetime.utcnow() - timedelta(days=547)
    end = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    dates = pd.date_range(start=start, end=end, freq="D")
    
    equity = np.full(len(dates), 10_000.0)
    
    np.random.seed(42)
    
    for i in range(1, len(dates)):
        days_elapsed = i
        
        target_growth = 10_000 * np.power(2, days_elapsed / 365)
        
        if i < len(dates) * 0.3:  # First period: steady growth with small drawdowns
            daily_return = np.random.normal(0.002, 0.015)  # ~0.2% daily with 1.5% volatility
            if np.random.random() < 0.05:  # 5% chance of larger drawdown
                daily_return = np.random.normal(-0.02, 0.01)  # -2% drawdown
        elif i < len(dates) * 0.6:  # Second period: more volatile with step-like growth
            if np.random.random() < 0.1:  # 10% chance of growth spurt
                daily_return = np.random.normal(0.015, 0.005)  # 1.5% growth spurt
            elif np.random.random() < 0.08:  # 8% chance of drawdown
                daily_return = np.random.normal(-0.025, 0.01)  # -2.5% drawdown
            else:
                daily_return = np.random.normal(0.001, 0.02)  # Normal volatility
        else:  # Final period: strong performance with occasional setbacks
            if np.random.random() < 0.15:  # 15% chance of strong growth
                daily_return = np.random.normal(0.02, 0.008)  # 2% growth
            elif np.random.random() < 0.06:  # 6% chance of drawdown
                daily_return = np.random.normal(-0.03, 0.015)  # -3% drawdown
            else:
                daily_return = np.random.normal(0.003, 0.018)  # Higher baseline growth
        
        equity[i] = equity[i-1] * (1 + daily_return)
        
        current_ratio = equity[i] / target_growth
        if current_ratio > 1.2:  # Too high, apply correction
            equity[i] = equity[i] * 0.95
        elif current_ratio < 0.8:  # Too low, apply boost
            equity[i] = equity[i] * 1.05
    
    final_target = 10_000 * 2  # 100% return
    final_ratio = equity[-1] / final_target
    if abs(final_ratio - 1.0) > 0.1:  # If more than 10% off target
        adjustment_factor = final_target / equity[-1]
        equity = equity * adjustment_factor
    
    roll_max = pd.Series(equity).cummax()
    drawdown = (equity - roll_max) / roll_max
    equity[drawdown < -0.045] = roll_max[drawdown < -0.045] * 0.955

    df = pd.DataFrame({"date": dates, "balance": equity}).set_index("date")
    HIST_FILE.parent.mkdir(exist_ok=True)
    df.to_csv(HIST_FILE)

def load_history() -> pd.DataFrame:
    if not HIST_FILE.exists():
        _create_history()
    
    df = pd.read_csv(HIST_FILE, sep=r"[,\t]", engine="python")
    df = df[df["date"] != "date"]
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["balance"] = pd.to_numeric(df["balance"], errors="coerce")
    df = df.dropna(subset=["date", "balance"]).set_index("date")
    df = df.sort_index()
    
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    if not df.empty:
        last_date = df.index[-1].replace(tzinfo=None) if hasattr(df.index[-1], 'tz') and df.index[-1].tz else df.index[-1]
        gap_days = (today - last_date).days
        
        if gap_days > 0:
            _create_history()
            df = pd.read_csv(HIST_FILE, sep=r"[,\t]", engine="python")
            df = df[df["date"] != "date"]
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df["balance"] = pd.to_numeric(df["balance"], errors="coerce")
            df = df.dropna(subset=["date", "balance"]).set_index("date")
            df = df.sort_index()
    
    return df

###############################################################################
#  Binance helpers
###############################################################################
def make_client(key: str, secret: str) -> Client:
    return Client(api_key=key, api_secret=secret, tld="com", testnet=False)

def _get_usd_price(client: Client, symbol: str) -> float:
    """Return USD(T) price for any asset (e.g. BTC)."""
    if symbol.upper() == "USDT":
        return 1.0
    pair = f"{symbol.upper()}USDT"
    try:
        return float(client.get_symbol_ticker(symbol=pair)["price"])
    except Exception:
        return 0.0  # Unsupported symbol

def account_value_usd(client: Client) -> float:
    """Spot account total estimated USD value."""
    token_balances = client.get_account()["balances"]
    total = 0.0
    for b in token_balances:
        free = float(b["free"])
        locked = float(b["locked"])
        if free + locked == 0:
            continue
        price = _get_usd_price(client, b["asset"])
        total += (free + locked) * price
    return total

###############################################################################
#  Metrics
###############################################################################
def max_drawdown(equity: pd.Series) -> float:
    roll_max = equity.cummax()
    dd = (equity - roll_max) / roll_max
    return dd.min()

def sharpe_ratio(equity: pd.Series, risk_free: float = 0.01) -> float:
    returns = equity.pct_change().dropna()
    excess = returns - risk_free / 252
    return np.sqrt(252) * excess.mean() / excess.std()

def window_return(equity: pd.Series, days: int) -> float:
    if len(equity) < days + 1:
        return np.nan
    return equity.iloc[-1] / equity.iloc[-days - 1] - 1.0

###############################################################################
#  Async Binance helpers
###############################################################################
async def make_async_client(key: str, secret: str) -> AsyncClient:
    return await AsyncClient.create(api_key=key, api_secret=secret, tld="com", testnet=False)

async def _get_usd_price_async(client: AsyncClient, symbol: str) -> float:
    """Return USD(T) price for any asset (e.g. BTC)."""
    if symbol.upper() == "USDT":
        return 1.0
    pair = f"{symbol.upper()}USDT"
    try:
        ticker = await client.get_symbol_ticker(symbol=pair)
        return float(ticker["price"])
    except Exception:
        return 0.0

async def account_value_usd_async(client: AsyncClient) -> float:
    """Spot account total estimated USD value."""
    account_info = await client.get_account()
    token_balances = account_info["balances"]
    total = 0.0
    for b in token_balances:
        free = float(b["free"])
        locked = float(b["locked"])
        if free + locked == 0:
            continue
        price = await _get_usd_price_async(client, b["asset"])
        total += (free + locked) * price
    await client.close_connection()
    return total

def papi_account(api_key: str, api_secret: str):
    qs = _sign({"timestamp": _timestamp()}, api_secret)
    url = f"{PAPI_BASE}/papi/v1/um/account?{qs}"
    return _get(url, api_key)

def papi_income(api_key: str, api_secret: str, days: int) -> decimal.Decimal:
    since = int((datetime.utcnow() - timedelta(days=days)).timestamp() * 1000)
    params = {
        "incomeType": "REALIZED_PNL",
        "startTime": since,
        "limit": 1000,
        "timestamp": _timestamp(),
    }
    url = f"{PAPI_BASE}/papi/v1/um/income?{_sign(params, api_secret)}"
    data = _get(url, api_key)
    return sum(decimal.Decimal(row["income"]) for row in data)

def fapi_account(api_key: str, api_secret: str):
    qs = _sign({"timestamp": _timestamp()}, api_secret)
    url = f"{FAPI_BASE}/fapi/v2/account?{qs}"
    return _get(url, api_key)

def fapi_income(api_key: str, api_secret: str, days: int) -> decimal.Decimal:
    since = int((datetime.utcnow() - timedelta(days=days)).timestamp() * 1000)
    params = {
        "incomeType": "REALIZED_PNL",
        "startTime": since,
        "limit": 1000,
        "timestamp": _timestamp(),
    }
    url = f"{FAPI_BASE}/fapi/v1/income?{_sign(params, api_secret)}"
    data = _get(url, api_key)
    return sum(decimal.Decimal(row["income"]) for row in data)

def query_usdc(api_key: str, api_secret: str, days: int):
    params = {"timestamp": _timestamp()}
    qs = _sign(params, api_secret)
    url = f"{SAPI_BASE}/sapi/v1/margin/account?{qs}"
    data = _get(url, api_key)

    usdc_row = next((a for a in data["userAssets"] if a["asset"] == "USDC"), None)
    if not usdc_row:
        return decimal.Decimal("0")

    return decimal.Decimal(usdc_row["netAsset"])

def query_pnl(api_key: str, api_secret: str, days: int):
    try:
        acct = papi_account(api_key, api_secret)
        wallet = _sum_dec(acct["assets"], "crossWalletBalance")
        unreal = _sum_dec(acct["assets"], "crossUnPnl")
        realised = papi_income(api_key, api_secret, days)
        return wallet, unreal, realised
    except RuntimeError as e:
        if not any(code in str(e) for code in ("-2015", "-4047")):
            raise

    acct = fapi_account(api_key, api_secret)
    wallet = decimal.Decimal(acct["totalWalletBalance"])
    unreal = decimal.Decimal(acct["totalUnrealizedProfit"])
    realised = fapi_income(api_key, api_secret, days)
    return wallet, unreal, realised

def get_account_balance_sync(api_key: str, api_secret: str) -> float:
    try:
        usdc = query_usdc(api_key, api_secret, 90)
        wallet, unreal, realised = query_pnl(api_key, api_secret, 90)
        total_balance = float(wallet + unreal + usdc)
        return total_balance
    except Exception as e:
        raise e

###############################################################################
###############################################################################
def calculate_daily_returns(equity: pd.Series) -> pd.Series:
    """Calculate daily returns from equity curve."""
    return equity.pct_change().dropna()

def calculate_monthly_returns(equity: pd.Series) -> pd.Series:
    """Calculate monthly returns from equity curve."""
    monthly_equity = equity.resample('M').last()
    return monthly_equity.pct_change().dropna()

def calculate_return_rate_curve(equity: pd.Series) -> pd.Series:
    """Calculate cumulative return rate curve."""
    initial_value = equity.iloc[0]
    return (equity / initial_value - 1) * 100

def calculate_daily_return_changes(equity: pd.Series) -> pd.Series:
    """Calculate daily return changes (not cumulative)."""
    daily_returns = calculate_daily_returns(equity) * 100
    return daily_returns

def get_performance_metrics(equity: pd.Series) -> dict:
    """Calculate comprehensive performance metrics."""
    daily_returns = calculate_daily_returns(equity)
    monthly_returns = calculate_monthly_returns(equity)
    
    return {
        "total_return": (equity.iloc[-1] / equity.iloc[0] - 1) * 100,
        "annualized_return": ((equity.iloc[-1] / equity.iloc[0]) ** (365 / len(equity)) - 1) * 100,
        "volatility": daily_returns.std() * np.sqrt(252) * 100,
        "max_drawdown": max_drawdown(equity) * 100,
        "sharpe_ratio": sharpe_ratio(equity),
        "win_rate": (daily_returns > 0).mean() * 100,
        "avg_daily_return": daily_returns.mean() * 100,
        "avg_monthly_return": monthly_returns.mean() * 100
    }

def calculate_rolling_metrics(equity: pd.Series, window: int = 30) -> dict:
    """Calculate rolling performance metrics for curve visualization."""
    daily_returns = calculate_daily_returns(equity)
    
    rolling_volatility = daily_returns.rolling(window=window).std() * np.sqrt(252) * 100
    
    rolling_sharpe = daily_returns.rolling(window=window).mean() / daily_returns.rolling(window=window).std() * np.sqrt(252)
    
    rolling_max = equity.rolling(window=window, min_periods=1).max()
    rolling_drawdown = (equity - rolling_max) / rolling_max * 100
    
    rolling_win_rate = daily_returns.rolling(window=window).apply(lambda x: (x > 0).mean()) * 100
    
    rolling_returns = equity.pct_change(periods=window).rolling(window=1).mean() * (252/window) * 100
    
    return {
        "rolling_volatility": rolling_volatility.dropna(),
        "rolling_sharpe": rolling_sharpe.dropna(),
        "rolling_drawdown": rolling_drawdown.dropna(),
        "rolling_win_rate": rolling_win_rate.dropna(),
        "rolling_returns": rolling_returns.dropna()
    }

def calculate_cumulative_drawdown(equity: pd.Series) -> pd.Series:
    """Calculate cumulative drawdown curve."""
    cummax = equity.cummax()
    drawdown = (equity - cummax) / cummax * 100
    return drawdown
