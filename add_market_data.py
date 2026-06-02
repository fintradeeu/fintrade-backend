import re

with open('c:/work/fintrade/fintrade-backend/app/modules/simulator/routes.py', 'r', encoding='utf-8') as f:
    content = f.read()

route_code = '''
import random

@router.get("/market-data")
async def get_market_data():
    """Simulated randomized live market data feed."""
    base_prices = {
        "NIFTY 50": 58720,
        "BANK NIFTY": 42580,
        "RELIANCE": 2456,
        "HDFC BANK": 1650,
        "TCS": 3800
    }
    
    data = []
    for symbol, base in base_prices.items():
        # Fluctuate by +/- 1%
        fluctuation = base * 0.01 * random.uniform(-1, 1)
        current = round(base + fluctuation, 2)
        change_pct = round((fluctuation / base) * 100, 2)
        volume = f"{random.randint(10, 300)}M"
        data.append({
            "symbol": symbol,
            "price": current,
            "change": change_pct,
            "volume": volume
        })
    return data
'''

if '/market-data' not in content:
    content = content.replace('router = APIRouter(prefix="/simulator", tags=["Trading Simulator"])', 'router = APIRouter(prefix="/simulator", tags=["Trading Simulator"])\n' + route_code)
    with open('c:/work/fintrade/fintrade-backend/app/modules/simulator/routes.py', 'w', encoding='utf-8') as f:
        f.write(content)
print("Market data route added")
