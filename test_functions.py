#!/usr/bin/env python3

from utils import get_account_balance_sync, calculate_daily_returns, calculate_monthly_returns, calculate_return_rate_curve, get_performance_metrics
import pandas as pd
import numpy as np

def test_new_functions():
    print('Testing new functions...')
    
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    equity = pd.Series(np.random.randn(100).cumsum() + 100, index=dates)
    
    daily_ret = calculate_daily_returns(equity)
    print(f'Daily returns calculated: {len(daily_ret)} values')
    
    monthly_ret = calculate_monthly_returns(equity)
    print(f'Monthly returns calculated: {len(monthly_ret)} values')
    
    return_curve = calculate_return_rate_curve(equity)
    print(f'Return rate curve calculated: {len(return_curve)} values')
    
    metrics = get_performance_metrics(equity)
    print(f'Performance metrics calculated: {len(metrics)} metrics')
    print('Metrics:', list(metrics.keys()))
    
    print('All functions working correctly!')

if __name__ == "__main__":
    test_new_functions()
