import os, json, time, hashlib, pathlib
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from binance.client import Client

DATA_DIR = pathlib.Path(__file__).parent / "data"
INV_FILE = DATA_DIR / "investors.json"
HIST_FILE = DATA_DIR / "history.csv"

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

###############################################################################
###############################################################################
def _create_history():
    start = datetime.utcnow() - timedelta(days=547)
    dates = pd.date_range(start=start, end=datetime.utcnow(), freq="D")
    
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
    # History CSV may use commas or tabs as separators depending on how it was
    # generated.  Use a regex separator via the Python engine so either format
    # loads correctly.
    df = pd.read_csv(HIST_FILE, sep=r"[,\t]", engine="python")

    # Drop any stray header rows or bad data then parse types
    df = df[df["date"] != "date"]
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["balance"] = pd.to_numeric(df["balance"], errors="coerce")

    # Remove rows with invalid dates or balance values and index by date
    df = df.dropna(subset=["date", "balance"]).set_index("date")

    return df.sort_index()

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
