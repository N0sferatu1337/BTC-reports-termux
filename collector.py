#!/usr/bin/env python3
import argparse, logging, sys, subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
import requests

BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "daemon.log"
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler(sys.stdout)])
logger = logging.getLogger("CryptoCollector")

class CoinbaseClient:
    def fetch_ticker(self) -> Optional[Dict[str, Any]]:
        try:
            res = requests.get("https://api.coinbase.com/v2/prices/BTC-EUR/spot", timeout=10)
            res.raise_for_status()
            p = float(res.json()["data"]["amount"])
            logger.info(f"Coinbase BTC-EUR: €{p:,.2f}")
            return {"exchange": "Coinbase", "pair": "BTC-EUR", "price": p, "timestamp": datetime.utcnow().isoformat()}
        except Exception as e:
            logger.error(f"Coinbase Fehler: {e}")
            return None

class KrakenClient:
    def fetch_ticker(self) -> Optional[Dict[str, Any]]:
        try:
            res = requests.get("https://api.kraken.com/0/public/Ticker?pair=XBTEUR", timeout=10)
            res.raise_for_status()
            d = res.json()["result"]
            k = list(d.keys())[0]
            p = float(d[k]["c"][0])
            logger.info(f"Kraken XBTEUR: €{p:,.2f}")
            return {"exchange": "Kraken", "pair": "BTC-EUR", "price": p, "timestamp": datetime.utcnow().isoformat()}
        except Exception as e:
            logger.error(f"Kraken Fehler: {e}")
            return None

def generate_report(market_data):
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = REPORTS_DIR / f"crypto_report_{ts}.md"
    content = f"# Crypto Market Report ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n\n## Aktuelle Spot-Kurse (BTC-EUR)\n| Exchange | Pair | Preis (EUR) | Status |\n| :--- | :--- | :--- | :--- |\n"
    for item in market_data:
        if item:
            content += f"| **{item['exchange']}** | {item['pair']} | **€{item['price']:,.2f}** | 🟢 Online |\n"
    content += "\n---\n*Generiert via `collector.py` auf Android/Termux.*\n"
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
    logger.info("=== Starte Datenerfassung ===")
    results = [c.fetch_ticker() for c in [CoinbaseClient(), KrakenClient()]]
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
