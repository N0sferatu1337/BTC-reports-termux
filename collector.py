import os
import time
import requests
import subprocess
from datetime import datetime
from config import REPORTS_DIR, CB_PAIR, CB_CANDLE_GRANULARITIES, KR_PAIR, KR_INTERVALS
from indicators import (
    calculate_ema, calculate_rsi, calculate_bollinger_bands,
    fetch_fear_and_greed, fetch_coinbase_depth, fetch_kraken_depth,
    fetch_kraken_derivatives
)

def fetch_coinbase_data():
    try:
        ticker_url = f"https://api.exchange.coinbase.com/products/{CB_PAIR}/ticker"
        stats_url = f"https://api.exchange.coinbase.com/products/{CB_PAIR}/stats"
        headers = {"User-Agent": "CryptoBot-Termux/1.0"}
        
        ticker = requests.get(ticker_url, headers=headers, timeout=10).json()
        stats = requests.get(stats_url, headers=headers, timeout=10).json()
        
        spot = float(ticker.get("price", 0))
        volume = float(stats.get("volume", 0))
        bid = float(ticker.get("bid", 0))
        ask = float(ticker.get("ask", 0))
        spread = round(ask - bid, 2)
        
        timeframes_data = {}
        for tf, gran in CB_CANDLE_GRANULARITIES.items():
            c_url = f"https://api.exchange.coinbase.com/products/{CB_PAIR}/candles?granularity={gran}"
            c_resp = requests.get(c_url, headers=headers, timeout=10).json()
            c_resp = sorted(c_resp, key=lambda x: x[0])
            closes = [float(c[4]) for c in c_resp]
            
            rsi = calculate_rsi(closes)
            ema9 = calculate_ema(closes, 9)
            ema21 = calculate_ema(closes, 21)
            upper_bb, lower_bb = calculate_bollinger_bands(closes)
            
            trend = "🟢 Bullisch" if closes[-1] > ema21 else "🔴 Bärisch"
            rsi_text = f"{rsi:.1f} ({'❄️ Überverkauft' if rsi < 30 else ('🔥 Überkauft' if rsi > 70 else '⚖️ Neutral')})"
            
            timeframes_data[tf] = {
                "rsi": rsi_text,
                "ema9": ema9,
                "ema21": ema21,
                "upper_bb": upper_bb,
                "lower_bb": lower_bb,
                "trend": trend
            }
            
        depth = fetch_coinbase_depth(spot)
        orderbook_pressure = "🟢 Käufer" if depth["bid_depth"] > depth["ask_depth"] else "🔴 Verkäufer"
        
        return {
            "spot": spot, "volume": volume, "spread": spread,
            "orderbook": orderbook_pressure, "depth": depth,
            "timeframes": timeframes_data, "status": "🟢 Online"
        }
    except Exception as e:
        print(f"Fehler Coinbase Data: {e}")
        return None

def fetch_kraken_data():
    try:
        ticker_url = f"https://api.kraken.com/0/public/Ticker?pair={KR_PAIR}"
        resp = requests.get(ticker_url, timeout=10).json()
        result = resp.get("result", {})
        pair_key = list(result.keys())[0] if result else None
        if not pair_key:
            return None
            
        data = result[pair_key]
        spot = float(data["c"][0])
        volume = float(data["v"][1])
        bid = float(data["b"][0])
        ask = float(data["a"][0])
        spread = round(ask - bid, 2)
        
        timeframes_data = {}
        for tf, interval in KR_INTERVALS.items():
            ohlc_url = f"https://api.kraken.com/0/public/OHLC?pair={KR_PAIR}&interval={interval}"
            ohlc_resp = requests.get(ohlc_url, timeout=10).json()
            ohlc_result = ohlc_resp.get("result", {})
            ohlc_key = [k for k in ohlc_result.keys() if k != "last"][0] if ohlc_result else None
            if not ohlc_key:
                continue
            candles = ohlc_result[ohlc_key]
            closes = [float(c[4]) for c in candles]
            
            rsi = calculate_rsi(closes)
            ema9 = calculate_ema(closes, 9)
            ema21 = calculate_ema(closes, 21)
            upper_bb, lower_bb = calculate_bollinger_bands(closes)
            
            trend = "🟢 Bullisch" if closes[-1] > ema21 else "🔴 Bärisch"
            rsi_text = f"{rsi:.1f} ({'❄️ Überverkauft' if rsi < 30 else ('🔥 Überkauft' if rsi > 70 else '⚖️ Neutral')})"
            
            timeframes_data[tf] = {
                "rsi": rsi_text, "ema9": ema9, "ema21": ema21,
                "upper_bb": upper_bb, "lower_bb": lower_bb, "trend": trend
            }
            
        depth = fetch_kraken_depth(spot)
        orderbook_pressure = "🟢 Käufer" if depth["bid_depth"] > depth["ask_depth"] else "🔴 Verkäufer"
        
        return {
            "spot": spot, "volume": volume, "spread": spread,
            "orderbook": orderbook_pressure, "depth": depth,
            "timeframes": timeframes_data, "status": "🟢 Online"
        }
    except Exception as e:
        print(f"Fehler Kraken Data: {e}")
        return None

def main():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    filename_ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    print(f"[{timestamp}] Starte vollständige Datenerhebung...")
    cb = fetch_coinbase_data()
    kr = fetch_kraken_data()
    fng = fetch_fear_and_greed()
    derivatives = fetch_kraken_derivatives()
    
    if not cb or not kr:
        print("Fehler: Konnte nicht alle Börsendaten abrufen.")
        return

    fr_signal = "🟢 Neutral/Leicht" if -0.01 <= derivatives['funding_rate'] <= 0.01 else ("🔥 Longs überhitzt" if derivatives['funding_rate'] > 0.01 else "❄️ Shorts überhitzt")

    report = f"""# Crypto Market Report ({timestamp})

## 📊 Marktübersicht, Volumen & Orderbuch-Tiefe

| Exchange | Spot (EUR) | 24h Volumen | Spread | Orderbuch Druck | Bollinger Bänder (U/L) | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Coinbase** | **€{cb['spot']:,.2f}** | {cb['volume']:.2f} BTC | €{cb['spread']:.2f} | {cb['orderbook']} | €{cb['timeframes']['1h']['upper_bb']:,.0f} / €{cb['timeframes']['1h']['lower_bb']:,.0f} | {cb['status']} |
| **Kraken** | **€{kr['spot']:,.2f}** | {kr['volume']:.2f} BTC | €{kr['spread']:.2f} | {kr['orderbook']} | €{kr['timeframes']['1h']['upper_bb']:,.0f} / €{kr['timeframes']['1h']['lower_bb']:,.0f} | {kr['status']} |

## ⚡ Derivate, Sentiment & Orderbuch-Tiefe (±1%)

| Metrik | Wert | Details / Interpretation |
| :--- | :--- | :--- |
| **Fear & Greed Index** | **{fng['value']} / 100** | {fng['classification']} |
| **Kraken Futures Open Interest** | **{derivatives['open_interest']:,.2f} BTC** | Globales Hebelvolumen |
| **Kraken Futures Funding Rate** | **{derivatives['funding_rate']:+.4f}%** | {fr_signal} |
| **Coinbase Tiefe (±1%)** | Bids: {cb['depth']['bid_depth']} BTC <br> Asks: {cb['depth']['ask_depth']} BTC | {'🟢 Kaufüberhang' if cb['depth']['bid_depth'] > cb['depth']['ask_depth'] else '🔴 Verkaufsdruck'} |
| **Kraken Tiefe (±1%)** | Bids: {kr['depth']['bid_depth']} BTC <br> Asks: {kr['depth']['ask_depth']} BTC | {'🟢 Kaufüberhang' if kr['depth']['bid_depth'] > kr['depth']['ask_depth'] else '🔴 Verkaufsdruck'} |

## 📈 Multi-Timeframe Indikatoren-Analyse

### 🏛️ Coinbase
| Timeframe | RSI (14) | EMA 9 | EMA 21 | Trend-Tendenz |
| :--- | :--- | :--- | :--- | :--- |
"""
    for tf, data in cb['timeframes'].items():
        report += f"| **{tf}** | {data['rsi']} | €{data['ema9']:,.2f} | €{data['ema21']:,.2f} | {data['trend']} |\n"

    report += """
### 🏛️ Kraken
| Timeframe | RSI (14) | EMA 9 | EMA 21 | Trend-Tendenz |
| :--- | :--- | :--- | :--- | :--- |
"""
    for tf, data in kr['timeframes'].items():
        report += f"| **{tf}** | {data['rsi']} | €{data['ema9']:,.2f} | €{data['ema21']:,.2f} | {data['trend']} |\n"

    report += f"""
---
*Generiert via modularer `collector.py` auf Android/Termux.*
"""

    report_path = os.path.join(REPORTS_DIR, f"report_{filename_ts}.md")
    latest_path = os.path.join(REPORTS_DIR, "latest.md")
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
        
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(report)
        
    print(f"Bericht erfolgreich gespeichert unter: {report_path}")
    
    if os.path.exists("git_sync.py"):
        print("Starte git_sync.py...")
        subprocess.run(["python", "git_sync.py"])

if __name__ == "__main__":
    main()
            
