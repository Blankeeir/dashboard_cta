# dashboard_cta
## Intro
a cta strategy dashboard for investors investing in our CTA(low-frequency trading strategy on binance) to see current managed capital size, current return, max drawdown and historical capital gain curve.
Currently only supports Binance.
## Dashboard features
from top to bottom:
Title -> overview of asset under management(total capital) -> overview of CTA strategy performance return(30-day return, 90-day return, 180-day return, overall return can switch), maxdrawdown(with metrics like sharpe ratio) ->specific LP information (initials of LP, amount of investment, total PnL)

- The dashboard will have a crucial function when real new investors coming in (should fill in password to access the controller mode), which allows the controller to input the name of LP, api key and api secret, then the dashboard will automatically add a new investor by retrieving the asset information (total amount of asset), then always keep track of its balance and add into the total asset and when balance change, the total balance also changes thus the statistics changes.
- The dashboard will have another critical feature when entered controller mode,which is adding in virtual investor (manually input asset balance, then the system kept track of real total balance from real investors but display total asset balance including virtual ones). however, the day return etc. will be calculated based only on real balance and pnls retrieved from api, then the virtual investor's balance will be applied the corresponding multiplier.
- Should be able to delete certain investor also
- Since the strategy has been running for quite a long time(two years), the initial 30 day return will be set at 10%, initial 90-day return will be 32% and initial 180-day return wll be 48%.
- at the bottom there's a historical curve of balance till today. Since the strategy has been running for quite a while, just craft a 100% per annum and less than 4.5 max drawdown curve for me 

## Techstack
The dashboard will be using python, connecting to binance's REST api.

Provide full WORKING code for this dashboard and I wish to directly deploy on EC2 instance
