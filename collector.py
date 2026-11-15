#!/usr/bin/env python3
from pathlib import Path
import argparse
import subprocess
import sys
from datetime import datetime
from typing import Any, Dict, Optional
import requests

from config import BASE_DIR, REPORTS_DIR, setup_logging, logger
from indicators import calculate_ema, calculate_rsi, calculate_bollinger_bands

class CoinbaseClient:
    def fetch_data(self) -> Optional[Dict[str, Any]]:
        try:
            res_spot = requests.get("https://api.coinbase.com/v2/prices/BTC-EUR/spot", timeout=10)
            spot = float(res_spot.json()["data"]["amount"])
            
            res_stats = requests.get("https://api.exchange.coinbase.com/products/BTC-EUR/stats", timeout=10)
            vol_24h = float(res_stats.json().get("volume", 0.0)) if res_stats.status_code == 200 else 0.0

            res_book = requests.get("https://api.exchange.coinbase.com/products/BTC-EUR/book?level=2", timeout=10)
            bid_vol, ask_vol, spread = 0.0, 0.0, 0.0
            if res_book.status_code == 200:
                book = res_book.json()
                bids, asks = book.get("bids", [])[:10], book.get("asks", [])[:10]
                bid_vol = sum(float(b[1]) for b in bids)
                ask_vol = sum(float(a[1]) for a in asks)
                if bids and asks:
                    spread = float(asks[0][0]) - float(bids[0][0])

            timeframes = {"15m": 900, "1h": 3600, "6h": 21600}
            tf_data = {}
            for tf, gran in timeframes.items():
                res_c = requests.get(f"https://api.exchange.coinbase.com/products/BTC-EUR/candles?granularity={gran}", timeout=10)
                closes = [c[4] for c in sorted(res_c.json(), key=lambda x: x[0])] if res_c.status_code == 200 else [spot]
                tf_data[tf] = {"rsi": calculate_rsi(closes), "ema9": calculate_ema(closes, 9), "ema21": calculate_ema(closes, 21)}

            upper, middle, lower = calculate_bollinger_bands(closes if "closes" in locals() else [spot])
            logger.info(f"Coinbase BTC-EUR: €{spot:,.2f} | Vol: {vol_24h:,.2f}")
            return {
                "exchange": "Coinbase", "pair": "BTC-EUR", "price": spot,
                "volume_24h": vol_24h, "spread": spread, "bid_vol": bid_vol, "ask_vol": ask_vol,
                "timeframes": tf_data, "bb_upper": upper, "bb_middle": middle, "bb_lower": lower,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Coinbase Fehler: {e}")
            return None

class KrakenClient:
    def fetch_data(self) -> Optional[Dict[str, Any]]:
        try:
            res = requests.get("https://api.kraken.com/0/public/Ticker?pair=XBTEUR", timeout=10)
            d = res.json()["result"]
            k = list(d.keys())[0]
            spot = float(d[k]["c"][0])
            vol_24h = float(d[k]["v"][1])

            res_depth = requests.get("https://api.kraken.com/0/public/Depth?pair=XBTEUR&count=10", timeout=10)
            bid_vol, ask_vol, spread = 0.0, 0.0, 0.0
            if res_depth.status_code == 200:
                depth_data = res_depth.json()["result"][k]
                bids, asks = depth_data.get("bids", []), depth_data.get("asks", [])
                bid_vol = sum(float(b[1]) for b in bids)
                ask_vol = sum(float(a[1]) for a in asks)
                if bids and asks:
                    spread = float(asks[0][0]) - float(bids[0][0])

            intervals = {"15m": 15, "1h": 60, "4h": 240}
            tf_data = {}
            for tf, interval in intervals.items():
                res_ohlc = requests.get(f"https://api.kraken.com/0/public/OHLC?pair=XBTEUR&interval={interval}", timeout=10)
                closes = []
                if res_ohlc.status_code == 200:
                    ohlc_json = res_ohlc.json()["result"]
                    pair_key = [x for x in ohlc_json.keys() if x != "last"][0]
                    closes = [float(c[4]) for c in ohlc_json[pair_key]]
                if not closes: closes = [spot]
                tf_data[tf] = {"rsi": calculate_rsi(closes), "ema9": calculate_ema(closes, 9), "ema21": calculate_ema(closes, 21)}

            upper, middle, lower = calculate_bollinger_bands(closes if "closes" in locals() else [spot])
            logger.info(f"Kraken XBTEUR: €{spot:,.2f} | Vol: {vol_24h:,.2f}")
            return {
                "exchange": "Kraken", "pair": "BTC-EUR", "price": spot,
                "volume_24h": vol_24h, "spread": spread, "bid_vol": bid_vol, "ask_vol": ask_vol,
                "timeframes": tf_data, "bb_upper": upper, "bb_middle": middle, "bb_lower": lower,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Kraken Fehler: {e}")
            return None

def generate_report(market_data: list[Dict[str, Any]]) -> Optional[Path]:
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = REPORTS_DIR / f"crypto_report_{ts}.md"
    
    content = f"# Crypto Market Report ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n\n"
    content += "## 📊 Marktübersicht, Volumen & Orderbuch-Tiefe\n\n"
    content += "| Exchange | Spot (EUR) | 24h Volumen | Spread | Orderbuch Druck | Bollinger Bänder (U/L) | Status |\n"
    content += "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
    
    for item in market_data:
        if item:
            pressure = "🟢 Käufer" if item["bid_vol"] > item["ask_vol"] else "🔴 Verkäufer"
            content += f"| **{item['exchange']}** | **€{item['price']:,.2f}** | {item['volume_24h']:,.2f} BTC | €{item['spread']:.2f} | {pressure} | €{item['bb_upper']:,.0f} / €{item['bb_lower']:,.0f} | 🟢 Online |\n"

    content += "\n## 📈 Multi-Timeframe Indikatoren-Analyse\n\n"
    for item in market_data:
        if item:
            content += f"### 🏛️ {item['exchange']}\n"
            content += "| Timeframe | RSI (14) | EMA 9 | EMA 21 | Trend-Tendenz |\n"
            content += "| :--- | :--- | :--- | :--- | :--- |\n"
            for tf, vals in item["timeframes"].items():
                trend = "🟢 Bullisch" if vals["ema9"] > vals["ema21"] else "🔴 Bärisch"
                rsi_state = "🔥 Überkauft" if vals["rsi"] > 70 else ("❄️ Überverkauft" if vals["rsi"] < 30 else "⚖️ Neutral")
                content += f"| **{tf}** | {vals['rsi']:.1f} ({rsi_state}) | €{vals['ema9']:,.2f} | €{vals['ema21']:,.2f} | {trend} |\n"
            content += "\n"

    content += "---\n*Generiert via modularer `collector.py` auf Android/Termux.*\n"
    path.write_text(content, encoding="utf-8")
    logger.info(f"Vollständiger Report geschrieben: {path.name}")
    return path

def trigger_git_sync() -> bool:
    sync_script = BASE_DIR / "git_sync.py"
    if not sync_script.exists():
        logger.warning("git_sync.py nicht gefunden.")
        return False
    try:
        logger.info("Starte Git-Sync...")
        res = subprocess.run([sys.executable, str(sync_script)], capture_output=True, text=True, timeout=30)
        if res.returncode == 0:
            logger.info("Git-Sync erfolgreich.")
            return True
        logger.error(f"Git-Sync fehlgeschlagen: {res.stderr.strip()}")
        return False
    except Exception as e:
        logger.error(f"Git-Sync Fehler: {e}")
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    setup_logging(args.verbose)
    logger.info("=== Starte modulare Multi-Timeframe Datenerfassung ===")

    clients = [CoinbaseClient(), KrakenClient()]
    results = [c.fetch_data() for c in clients]
    results = [r for r in results if r]

    if not results:
        logger.critical("Alle Exchanges fehlgeschlagen.")
        sys.exit(1)

    if not args.dry_run:
        path = generate_report(results)
        if path:
            trigger_git_sync()
    else:
        logger.info("Dry-Run aktiv.")

    logger.info("=== Zyklus beendet ===")

if __name__ == "__main__":
    main()
