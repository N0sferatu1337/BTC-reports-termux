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

def calculate_bollinger_bands(prices: List[float], period: int = 20, num_std: float = 2.0):
    if len(prices) < period:
        p = prices[-1] if prices else 0.0
        return p, p, p
    window = prices[-period:]
    sma = sum(window) / period
    variance = sum((x - sma) ** 2 for x in window) / period
    std_dev = math.sqrt(variance)
    return sma + (num_std * std_dev), sma, sma - (num_std * std_dev)

class CoinbaseClient:
    def fetch_data(self) -> Optional[Dict[str, Any]]:
        try:
            res_spot = requests.get("https://api.coinbase.com/v2/prices/BTC-EUR/spot", timeout=10)
            res_spot.raise_for_status()
            spot = float(res_spot.json()["data"]["amount"])
            
            res_candles = requests.get("https://api.exchange.coinbase.com/products/BTC-EUR/candles?granularity=3600", timeout=10)
            closes = []
            if res_candles.status_code == 200:
                raw_candles = res_candles.json()
                closes = [c[4] for c in sorted(raw_candles, key=lambda x: x[0])]
            if not closes: closes = [spot]

            rsi = calculate_rsi(closes)
            ema9 = calculate_ema(closes, 9)
            ema21 = calculate_ema(closes, 21)
            upper, middle, lower = calculate_bollinger_bands(closes)

            logger.info(f"Coinbase BTC-EUR: €{spot:,.2f} | RSI: {rsi:.1f} | EMA9: €{ema9:,.2f}")
            return {
                "exchange": "Coinbase", "pair": "BTC-EUR", "price": spot,
                "rsi": rsi, "ema9": ema9, "ema21": ema21,
                "bb_upper": upper, "bb_middle": middle, "bb_lower": lower,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Coinbase Fehler: {e}")
            return None

class KrakenClient:
    def fetch_data(self) -> Optional[Dict[str, Any]]:
        try:
            res = requests.get("https://api.kraken.com/0/public/Ticker?pair=XBTEUR", timeout=10)
            res.raise_for_status()
            d = res.json()["result"]
            k = list(d.keys())[0]
            spot = float(d[k]["c"][0])
            
            res_ohlc = requests.get("https://api.kraken.com/0/public/OHLC?pair=XBTEUR&interval=60", timeout=10)
            closes = []
            if res_ohlc.status_code == 200:
                ohlc_data = res_ohlc.json()["result"]
                pair_ohlc_key = [x for x in ohlc_data.keys() if x != "last"][0]
                closes = [float(c[4]) for c in ohlc_data[pair_ohlc_key]]
            if not closes: closes = [spot]

            rsi = calculate_rsi(closes)
            ema9 = calculate_ema(closes, 9)
            ema21 = calculate_ema(closes, 21)
            upper, middle, lower = calculate_bollinger_bands(closes)

            logger.info(f"Kraken XBTEUR: €{spot:,.2f} | RSI: {rsi:.1f} | EMA9: €{ema9:,.2f}")
            return {
                "exchange": "Kraken", "pair": "BTC-EUR", "price": spot,
                "rsi": rsi, "ema9": ema9, "ema21": ema21,
                "bb_upper": upper, "bb_middle": middle, "bb_lower": lower,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Kraken Fehler: {e}")
            return None

def generate_report(market_data):
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = REPORTS_DIR / f"crypto_report_{ts}.md"
    content = f"# Crypto Market Report ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n\n"
    content += "## 📊 Marktübersicht & Technische Indikatoren (BTC-EUR)\n\n"
    content += "| Exchange | Preis (EUR) | RSI (14) | EMA 9 | EMA 21 | Bollinger (Upper/Lower) | Status |\n"
    content += "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
    
    for item in market_data:
        if item:
            rsi_icon = "🟢" if 30 <= item['rsi'] <= 70 else ("🔥 (Überkauft)" if item['rsi'] > 70 else "❄️ (Überverkauft)")
            content += f"| **{item['exchange']}** | **€{item['price']:,.2f}** | {item['rsi']:.1f} {rsi_icon} | €{item['ema9']:,.2f} | €{item['ema21']:,.2f} | €{item['bb_upper']:,.0f} / €{item['bb_lower']:,.0f} | 🟢 Online |\n"

    content += "\n---\n*Generiert via `collector.py` auf Android/Termux mit Kerzen-Daten & Indikatoren.*\n"
    path.write_text(content, encoding="utf-8")
    logger.info(f"Report geschrieben: {path.name}")
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
    logger.info("=== Starte Datenerfassung mit Indikatoren ===")
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
