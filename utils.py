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
#  Synthetic history (100 % CAGR, ≤4.5 % max DD) – created once
###############################################################################
def _create_history():
    start = datetime.utcnow() - timedelta(days=730)
    dates = pd.date_range(start=start, end=datetime.utcnow(), freq="D")
    growth = np.power(2, np.arange(len(dates)) / 365)  # 100 % p.a.
    noise = np.random.normal(1.0, 0.002, size=len(dates))  # tiny day noise
    equity = 10_000 * growth * noise.cumprod()

    # Smooth drawdown to keep < 4.5 %
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
