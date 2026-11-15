#!/usr/bin/env python3
"""
Modular Crypto Collector for Termux (~/crypto-bot)
Fetches BTC-EUR data from Coinbase & Kraken, implements robust error handling,
timeouts, file/console logging, and Markdown report generation.
"""

import argparse
from datetime import datetime
import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict, Optional
import requests

# --- Configuration & Paths ---
BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "daemon.log"
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

# --- Logging Setup ---
def setup_logging(verbose: bool = False) -> None:
    """Konfiguriert das Logging für Konsole und dauerhafte daemon.log Datei."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(sys.stdout)
        ]
    )

logger = logging.getLogger("CryptoCollector")

# --- Exchange Client Implementations ---
class CoinbaseClient:
    """Client für Coinbase Spot API (BTC-EUR)."""
    def __init__(self):
        self.url = "https://api.coinbase.com/v2/prices/BTC-EUR/spot"

    def fetch_ticker(self) -> Optional[Dict[str, Any]]:
        try:
            response = requests.get(self.url, timeout=10)
            response.raise_for_status()
            data = response.json()
            price = float(data["data"]["amount"])
            logger.info(f"Coinbase BTC-EUR Spot erfolgreich abgerufen: €{price:,.2f}")
            return {
                "exchange": "Coinbase",
                "pair": "BTC-EUR",
                "price": price,
                "timestamp": datetime.utcnow().isoformat()
            }
        except requests.Timeout:
            logger.error("Coinbase API Timeout nach 10 Sekunden.")
        except requests.RequestException as e:
            logger.error(f"Coinbase API Netzwerkfehler: {e}")
        except (KeyError, ValueError) as e:
            logger.error(f"Coinbase JSON Parsing-Fehler: {e}")
        return None


class KrakenClient:
    """Client für Kraken Public Ticker API (XBTEUR)."""
    def __init__(self):
        self.url = "https://api.kraken.com/0/public/Ticker?pair=XBTEUR"

    def fetch_ticker(self) -> Optional[Dict[str, Any]]:
        try:
            response = requests.get(self.url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            result = data.get("result", {})
            pair_key = list(result.keys())[0] if result else None
            if not pair_key:
                logger.error("Kraken API: Keine passenden Pair-Daten in der Antwort.")
                return None
                
            price = float(result[pair_key]["c"][0])
            logger.info(f"Kraken XBTEUR Spot erfolgreich abgerufen: €{price:,.2f}")
            return {
                "exchange": "Kraken",
                "pair": "BTC-EUR",
                "price": price,
                "timestamp": datetime.utcnow().isoformat()
            }
        except requests.Timeout:
            logger.error("Kraken API Timeout nach 10 Sekunden.")
        except requests.RequestException as e:
            logger.error(f"Kraken API Netzwerkfehler: {e}")
        except (KeyError, ValueError, IndexError) as e:
            logger.error(f"Kraken JSON Parsing-Fehler: {e}")
        return None


# --- Report Generator ---
def generate_report(market_data: list[Dict[str, Any]]) -> Path:
    """Generiert einen formatierten Markdown-Report im reports/-Verzeichnis."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    report_path = REPORTS_DIR / f"crypto_report_{timestamp}.md"
    
    content = f"""# Crypto Market Report ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})

Automatisierter Report aus dem Termux-Daemon (`~/crypto-bot`).

## Aktuelle Spot-Kurse (BTC-EUR)
| Exchange | Pair | Preis (EUR) | Status |
| :--- | :--- | :--- | :--- |
"""
    for item in market_data:
        if item:
            content += f"| **{item['exchange']}** | {item['pair']} | **€{item['price']:,.2f}** | 🟢 Online |\n"

    content += f"""
---
*Generiert via `collector.py` auf Android/Termux.*
"""
    
    report_path.write_text(content, encoding="utf-8")
    logger.info(f"Markdown-Report erfolgreich geschrieben: {report_path.name}")
    return report_path


# --- Main Logic ---
def main():
    parser = argparse.ArgumentParser(description="Modular Crypto Collector für Termux")
    parser.add_argument("--verbose", action="store_true", help="Aktiviert detailliertes Debug-Logging")
    parser.add_argument("--dry-run", action="store_true", help="Führt den Fetch aus, schreibt aber keinen Report")
    args = parser.parse_args()

    setup_logging(args.verbose)
    logger.info("=== Starte neuen Datenerfassungs-Zyklus ===")

    clients = [CoinbaseClient(), KrakenClient()]
    market_results = []

    for client in clients:
        data = client.fetch_ticker()
        if data:
            market_results.append(data)

    if not market_results:
        logger.critical("Kritisch: Alle Exchange-Anfragen sind fehlgeschlagen. Abbruch.")
        sys.exit(1)

    if not args.dry_run:
        generate_report(market_results)
    else:
        logger.info("Dry-Run Modus aktiv: Überspringe Report-Erstellung.")

    logger.info("=== Zyklus erfolgreich beendet ===")


if __name__ == "__main__":
    main()
