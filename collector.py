import os
import sys
import requests
import statistics
from datetime import datetime
from pathlib import Path

# Importiere den Git-Sync Automator aus demselben Verzeichnis
from git_sync import sync_repository

# --- Konfiguration ---
PAIR_COINBASE = "BTC-EUR"
PAIR_KRAKEN = "XXBTZEUR"
OUTPUT_DIR = Path("~/crypto-bot/data/reports").expanduser()

def fetch_coinbase_data():
    """Holt Ticker, 24h Stats und stündliche Kerzen von Coinbase."""
    data = {"exchange": "Coinbase", "spot": None, "high_24h": None, "low_24h": None, "volume_24h": None, "candles": []}
    try:
        # Ticker
        r = requests.get(f"https://api.exchange.coinbase.com/products/{PAIR_COINBASE}/ticker", timeout=10)
        if r.status_code == 200:
            res = r.json()
            data["spot"] = float(res.get("price", 0))
        
        # 24h Stats
        r_stats = requests.get(f"https://api.exchange.coinbase.com/products/{PAIR_COINBASE}/stats", timeout=10)
        if r_stats.status_code == 200:
            res_s = r_stats.json()
            data["high_24h"] = float(res_s.get("high", 0))
            data["low_24h"] = float(res_s.get("low", 0))
            data["volume_24h"] = float(res_s.get("volume", 0))

        # Historische Kerzen (1h granularity) für Indikatoren
        r_candles = requests.get(f"https://api.exchange.coinbase.com/products/{PAIR_COINBASE}/candles?granularity=3600", timeout=10)
        if r_candles.status_code == 200:
            # Coinbase liefert: [time, low, high, open, close, volume]
            raw_candles = r_candles.json()
            # Sortieren nach Zeit aufsteigend
            raw_candles.sort(key=lambda x: x[0])
            data["candles"] = [c[4] for c in raw_candles if len(c) > 4] # Schlusspreise (Close)
    except Exception as e:
        print(f"[Warnung] Fehler beim Abrufen der Coinbase-Daten: {e}")
    return data

def fetch_kraken_data():
    """Holt Ticker und OHLC-Daten von Kraken."""
    data = {"exchange": "Kraken", "spot": None, "high_24h": None, "low_24h": None, "volume_24h": None, "candles": []}
    try:
        # Ticker
        r = requests.get(f"https://api.kraken.com/0/public/Ticker?pair={PAIR_KRAKEN}", timeout=10)
        if r.status_code == 200:
            res = r.json()
            result = res.get("result", {})
            pair_key = list(result.keys())[0]
            ticker_info = result[pair_key]
            data["spot"] = float(ticker_info["c"][0])      # Letzter Preis
            data["high_24h"] = float(ticker_info["h"][1])  # 24h Hoch (heute)
            data["low_24h"] = float(ticker_info["l"][1])   # 24h Tief (heute)
            data["volume_24h"] = float(ticker_info["v"][1])# 24h Volumen
            
        # OHLC (1 Stunde Interval = 60)
        r_ohlc = requests.get(f"https://api.kraken.com/0/public/OHLC?pair={PAIR_KRAKEN}&interval=60", timeout=10)
        if r_ohlc.status_code == 200:
            res_o = r_ohlc.json()
            result_o = res_o.get("result", {})
            pair_key_o = [k for k in result_o.keys() if k != "last"][0]
            ohlc_raw = result_o[pair_key_o]
            # Kraken liefert: [time, open, high, low, close, vwap, count]
            data["candles"] = [float(c[4]) for c in ohlc_raw if len(c) > 4]
    except Exception as e:
        print(f"[Warnung] Fehler beim Abrufen der Kraken-Daten: {e}")
    return data

def calculate_indicators(closes):
    """Berechnet RSI (14), EMA (9, 21) und Bollinger Bänder in Pure Python."""
    indicators = {"rsi": None, "ema_9": None, "ema_21": None, "bollinger_upper": None, "bollinger_lower": None}
    if not closes or len(closes) < 25:
        return indicators

    # EMA 9 & 21
    def calc_ema(data, period):
        multiplier = 2 / (period + 1)
        ema = data[0]
        for price in data[1:]:
            ema = (price - ema) * multiplier + ema
        return ema

    indicators["ema_9"] = calc_ema(closes[-30:], 9)
    indicators["ema_21"] = calc_ema(closes[-30:], 21)

    # RSI (14)
    gains, losses = [], []
    changes = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    recent_changes = changes[-14:]
    for change in recent_changes:
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    
    avg_gain = sum(gains) / 14
    avg_loss = sum(losses) / 14
    if avg_loss == 0:
        indicators["rsi"] = 100.0
    else:
        rs = avg_gain / avg_loss
        indicators["rsi"] = round(100 - (100 / (1 + rs)), 2)

    # Bollinger Bänder (20 Perioden, 2 StdDev)
    period_bb = 20
    window = closes[-period_bb:]
    sma = statistics.mean(window)
    stdev = statistics.stdev(window)
    indicators["bollinger_upper"] = round(sma + (2 * stdev), 2)
    indicators["bollinger_lower"] = round(sma - (2 * stdev), 2)
    
    indicators["ema_9"] = round(indicators["ema_9"], 2)
    indicators["ema_21"] = round(indicators["ema_21"], 2)
    return indicators

def generate_markdown_report(cb_data, kraken_data, indicators):
    """Generiert einen formschönen, datenreichen Markdown-Report."""
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    
    # Pfadstruktur: data/reports/YYYY-MM-DD/
    target_folder = OUTPUT_DIR / date_str
    target_folder.mkdir(parents=True, exist_ok=True)
    
    filename = f"market_report_{now.strftime('%H-%M')}.md"
    file_path = target_folder / filename
    
    # Preisvergleich & Spread
    cb_spot = cb_data.get("spot")
    kraken_spot = kraken_data.get("spot")
    avg_spot = round((cb_spot + kraken_spot) / 2, 2) if cb_spot and kraken_spot else (cb_spot or kraken_spot)
    spread = round(abs(cb_spot - kraken_spot), 2) if cb_spot and kraken_spot else "N/A"

    report_content = f"""# 📊 BTC-EUR Market Intelligence Report

* **Zeitstempel:** `{date_str} {time_str}`
* **Durchschnittspreis (Spot):** `€{avg_spot}`
* **Exchange-Spread (Coinbase vs. Kraken):** `€{spread}`

---

## 📈 Exchange Übersicht

| Kennzahl | Coinbase (`BTC-EUR`) | Kraken (`XXBTZEUR`) |
| :--- | :--- | :--- |
| **Spot-Preis** | €{cb_data.get('spot', 'N/A')} | €{kraken_data.get('spot', 'N/A')} |
| **24h Hoch** | €{cb_data.get('high_24h', 'N/A')} | €{kraken_data.get('high_24h', 'N/A')} |
| **24h Tief** | €{cb_data.get('low_24h', 'N/A')} | €{kraken_data.get('low_24h', 'N/A')} |
| **24h Volumen** | {cb_data.get('volume_24h', 'N/A')} BTC | {kraken_data.get('volume_24h', 'N/A')} BTC |

---

## 📐 Technische Indikatoren (Coinbase Basis)

* **RSI (14):** `{indicators.get('rsi', 'N/A')}`
* **EMA (9):** `€{indicators.get('ema_9', 'N/A')}`
* **EMA (21):** `€{indicators.get('ema_21', 'N/A')}`
* **Bollinger-Bänder (Upper):** `€{indicators.get('bollinger_upper', 'N/A')}`
* **Bollinger-Bänder (Lower):** `€{indicators.get('bollinger_lower', 'N/A')}`

---
*Automatisiert generiert durch Termux Crypto Bot & GitOps Automator.*
"""

    file_path.write_text(report_content, encoding="utf-8")
    print(f"[Collector] Report erfolgreich erstellt: {file_path}")
    return file_path

if __name__ == "__main__":
    print("[Collector] Starte Marktdaten-Sammlung...")
    cb = fetch_coinbase_data()
    kraken = fetch_kraken_data()
    
    # Indikatoren auf Basis der Coinbase-Historie berechnen
    indicators = calculate_indicators(cb.get("candles", []))
    
    # Report schreiben
    generate_markdown_report(cb, kraken, indicators)
    
    # Automatischer Git-Sync nach GitHub
    print("[Collector] Starte Git-Sync...")
    sync_repository("~/crypto-bot", f"docs(market): automated multi-exchange report {datetime.now().strftime('%Y-%m-%d %H:%M')}")
