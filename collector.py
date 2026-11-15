#!/usr/init/env python3
#!/usr/bin/env python3
import argparse, logging, sys, subprocess, math
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, List
import requests

BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "daemon.log"
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler(sys.stdout)])
logger = logging.getLogger("CryptoCollector")

def calculate_ema(prices: List[float], period: int) -> float:
    if not prices: return 0.0
    k = 2 / (period + 1)
    ema = prices[0]
    for price in prices[1:]:
        ema = (price * k) + (ema * (1 - k))
    return ema

def calculate_rsi(prices: List[float], period: int = 14) -> float:
    if len(prices) < period + 1: return 50.0
    gains, losses = [], []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0: return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

class CoinbaseClient:
    def fetch_data(self) -> Optional[Dict[str, Any]]:
        try:
            # 1. Spot & Stats (Volumen)
            res_spot = requests.get("https://api.coinbase.com/v2/prices/BTC-EUR/spot", timeout=10)
            spot = float(res_spot.json()["data"]["amount"])
            
            res_stats = requests.get("https://api.exchange.coinbase.com/products/BTC-EUR/stats", timeout=10)
            vol_24h = float(res_stats.json().get("volume", 0.0)) if res_stats.status_code == 200 else 0.0

            # 2. Orderbook (Top 50 Bids/Asks für Tiefe & Spread)
            res_book = requests.get("https://api.exchange.coinbase.com/products/BTC-EUR/book?level=2", timeout=10)
            bid_vol, ask_vol, spread = 0.0, 0.0, 0.0
            if res_book.status_code == 200:
                book = res_book.json()
                bids = book.get("bids", [])[:10] # Top 10 Bids [price, size, num-orders]
                asks = book.get("asks", [])[:10] # Top 10 Asks
                bid_vol = sum(float(b[1]) for b in bids)
                ask_vol = sum(float(a[1]) for a in asks)
                if bids and asks:
                    best_bid = float(bids[0][0])
                    best_ask = float(asks[0][0])
                    spread = best_ask - best_bid

            # 3. Kerzen & Indikatoren (1h)
            res_candles = requests.get("https://api.exchange.coinbase.com/products/BTC-EUR/candles?granularity=3600", timeout=10)
            closes = [c[4] for c in sorted(res_candles.json(), key=lambda x: x[0])] if res_candles.status_code == 200 else [spot]

            rsi = calculate_rsi(closes)
            ema9 = calculate_ema(closes, 9)
            ema21 = calculate_ema(closes, 21)

            logger.info(f"Coinbase BTC-EUR: €{spot:,.2f} | Vol: {vol_24h:,.2f} BTC | Spread: €{spread:.2f}")
            return {
                "exchange": "Coinbase", "pair": "BTC-EUR", "price": spot,
                "volume_24h": vol_24h, "spread": spread, "bid_vol": bid_vol, "ask_vol": ask_vol,
                "rsi": rsi, "ema9": ema9, "ema21": ema21,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Coinbase Fehler: {e}")
            return None

class KrakenClient:
    def fetch_data(self) -> Optional[Dict[str, Any]]:
        try:
            # 1. Ticker (Preis & 24h Volumen)
            res = requests.get("https://api.kraken.com/0/public/Ticker?pair=XBTEUR", timeout=10)
            d = res.json()["result"]
            k = list(d.keys())[0]
            spot = float(d[k]["c"][0])
            vol_24h = float(d[k]["v"][1]) # 24h Volumen [today, 24h]

            # 2. Orderbook / Depth
            res_depth = requests.get("https://api.kraken.com/0/public/Depth?pair=XBTEUR&count=10", timeout=10)
            bid_vol, ask_vol, spread = 0.0, 0.0, 0.0
            if res_depth.status_code == 200:
                depth_data = res_depth.json()["result"][k]
                bids = depth_data.get("bids", [])
                asks = depth_data.get("asks", [])
                bid_vol = sum(float(b[1]) for b in bids)
                ask_vol = sum(float(a[1]) for a in asks)
                if bids and asks:
                    best_bid = float(bids[0][0])
                    best_ask = float(asks[0][0])
                    spread = best_ask - best_bid

            # 3. OHLC / Kerzen (1h)
            res_ohlc = requests.get("https://api.kraken.com/0/public/OHLC?pair=XBTEUR&interval=60", timeout=10)
            closes = []
            if res_ohlc.status_code == 200:
                ohlc_json = res_ohlc.json()["result"]
                pair_key = [x for x in ohlc_json.keys() if x != "last"][0]
                closes = [float(c[4]) for c in ohlc_json[pair_key]]
            if not closes: closes = [spot]

            rsi = calculate_rsi(closes)
            ema9 = calculate_ema(closes, 9)
            ema21 = calculate_ema(closes, 21)

            logger.info(f"Kraken XBTEUR: €{spot:,.2f} | Vol: {vol_24h:,.2f} BTC | Spread: €{spread:.2f}")
            return {
                "exchange": "Kraken", "pair": "BTC-EUR", "price": spot,
                "volume_24h": vol_24h, "spread": spread, "bid_vol": bid_vol, "ask_vol": ask_vol,
                "rsi": rsi, "ema9": ema9, "ema21": ema21,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Kraken Fehler: {e}")
            return None

def generate_report(market_data):
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = REPORTS_DIR / f"crypto_report_{ts}.md"
    content = f"# Crypto Market Report ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n\n"
    content += "## 📊 Marktübersicht, Volumen & Orderbuch-Tiefe (BTC-EUR)\n\n"
    content += "| Exchange | Preis (EUR) | 24h Volumen | Spread | Orderbook Druck (Bid / Ask) | RSI (1h) | Trend |\n"
    content += "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
    
    for item in market_data:
        if item:
            pressure = "🟢 Käufer" if item['bid_vol'] > item['ask_vol'] else "🔴 Verkäufer"
            trend = "Bullisch" if item['ema9'] > item['ema21'] else "Bärisch"
            content += f"| **{item['exchange']}** | **€{item['price']:,.2f}** | {item['volume_24h']:,.2f} BTC | €{item['spread']:.2f} | {pressure} ({item['bid_vol']:.1f}/{item['ask_vol']:.1f}) | {item['rsi']:.1f} | {trend} |\n"

    content += "\n---\n*Generiert via `collector.py` auf Android/Termux mit Volumen- und Orderbuch-Daten.*\n"
    path.write_text(content, encoding="utf-8")
    logger.info(f"Report mit Volumen & Orderbook geschrieben: {path.name}")
    return path

def trigger_git_sync():
    script = BASE_DIR / "git_sync.py"
    if not script.exists():
        logger.warning("git_sync.py nicht gefunden.")
        return False
    try:
        logger.info("Starte Git-Sync...")
        res = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=30)
        if res.returncode == 0:
            logger.info("Git-Sync erfolgreich.")
            return True
        logger.error(f"Git-Sync Fehler: {res.stderr.strip()}")
        return False
    except Exception as e:
        logger.error(f"Git-Sync Exception: {e}")
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    logger.info("=== Starte Datenerfassung (inkl. Volumen & Orderbook) ===")
    results = [c.fetch_data() for c in [CoinbaseClient(), KrakenClient()]]
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
