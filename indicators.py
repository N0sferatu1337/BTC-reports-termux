import requests
import math

def calculate_ema(prices, period):
    if not prices or len(prices) < period:
        return prices[-1] if prices else 0.0
    multiplier = 2 / (period + 1)
    ema = sum(prices[:period]) / period
    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema
    return ema

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return 50.0
    gains = []
    losses = []
    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        gains.append(max(0, change))
        losses.append(max(0, -change))
    
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    if avg_loss == 0:
        return 100.0
    
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
    if avg_loss == 0:
        return 100.0
        
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_bollinger_bands(prices, period=20, num_std_dev=2):
    if len(prices) < period:
        current = prices[-1] if prices else 0.0
        return current, current
    subset = prices[-period:]
    sma = sum(subset) / period
    variance = sum((p - sma) ** 2 for p in subset) / period
    std_dev = math.sqrt(variance)
    upper = sma + (num_std_dev * std_dev)
    lower = sma - (num_std_dev * std_dev)
    return upper, lower

def fetch_fear_and_greed():
    """Ruft den aktuellen Fear & Greed Index ab (Alternative.me API)."""
    try:
        url = "https://api.alternative.me/fng/?limit=1"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            if data:
                item = data[0]
                return {
                    "value": item.get("value"),
                    "classification": item.get("value_classification")
                }
    except Exception as e:
        print(f"Fehler beim Fear & Greed Index: {e}")
    return {"value": "N/A", "classification": "N/A"}

def fetch_coinbase_depth(current_price, pct=0.01):
    """Berechnet die kumulierte Orderbuch-Tiefe (Bids/Asks) im +/- 1% Korridor für Coinbase."""
    try:
        url = "https://api.exchange.coinbase.com/products/BTC-EUR/book?level=2"
        headers = {"User-Agent": "CryptoBot-Termux/1.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            bids = data.get("bids", [])
            asks = data.get("asks", [])
            
            lower_bound = current_price * (1 - pct)
            upper_bound = current_price * (1 + pct)
            
            bid_depth = sum(float(item[1]) for item in bids if float(item[0]) >= lower_bound)
            ask_depth = sum(float(item[1]) for item in asks if float(item[0]) <= upper_bound)
            
            return {"bid_depth": round(bid_depth, 2), "ask_depth": round(ask_depth, 2)}
    except Exception as e:
        print(f"Fehler Coinbase Orderbook: {e}")
    return {"bid_depth": 0.0, "ask_depth": 0.0}

def fetch_kraken_depth(current_price, pct=0.01):
    """Berechnet die kumulierte Orderbuch-Tiefe (Bids/Asks) im +/- 1% Korridor für Kraken."""
    try:
        url = "https://api.kraken.com/0/public/Depth?pair=XXBTZEUR&count=50"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            result = resp.json().get("result", {})
            pair_key = list(result.keys())[0] if result else None
            if pair_key:
                book = result[pair_key]
                bids = book.get("bids", [])
                asks = book.get("asks", [])
                
                lower_bound = current_price * (1 - pct)
                upper_bound = current_price * (1 + pct)
                
                bid_depth = sum(float(item[1]) for item in bids if float(item[0]) >= lower_bound)
                ask_depth = sum(float(item[1]) for item in asks if float(item[0]) <= upper_bound)
                
                return {"bid_depth": round(bid_depth, 2), "ask_depth": round(ask_depth, 2)}
    except Exception as e:
        print(f"Fehler Kraken Orderbook: {e}")
    return {"bid_depth": 0.0, "ask_depth": 0.0}

def fetch_binance_derivatives():
    """Ruft Open Interest und Funding Rate von der Binance Futures API ab."""
    try:
        oi_url = "https://fapi.binance.com/fapi/v1/openInterest?symbol=BTCUSDT"
        premium_url = "https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT"
        
        oi_resp = requests.get(oi_url, timeout=10).json()
        prem_resp = requests.get(premium_url, timeout=10).json()
        
        open_interest = float(oi_resp.get("openInterest", 0))
        funding_rate = float(prem_resp.get("lastFundingRate", 0)) * 100  # In Prozent
        mark_price = float(prem_resp.get("markPrice", 0))
        
        return {
            "open_interest": open_interest,
            "funding_rate": round(funding_rate, 4),
            "mark_price": mark_price
        }
    except Exception as e:
        print(f"Fehler bei Binance Futures Derivate-Daten: {e}")
    return {"open_interest": 0.0, "funding_rate": 0.0, "mark_price": 0.0}
    
