"""Zentrale Konfiguration für BTC-reports-termux."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Reports liegen im Worktree des Branches "reports" (nicht auf main)
REPORTS_BRANCH = "reports"
REPORTS_WORKTREE_DIR = BASE_DIR / "reports-worktree"
REPORTS_DIR = REPORTS_WORKTREE_DIR / "reports"

# Laufsteuerung
RUN_INTERVAL_SECONDS = 20 * 60
HTTP_TIMEOUT = 10
USER_AGENT = "BTC-reports-termux/2.0"
GIT_SYNC_ENABLED = True

# Orderbuch-Korridor (+/- Prozent um den Referenzpreis)
BOOK_BAND_PCT = 0.01

# Schwelle für Funding-Rate-Heuristik in Prozent
FUNDING_THRESHOLD_PCT = 0.01

# Zeitrahmen, auf dem Bollinger-Bänder und 24h-Volumen berechnet werden
BB_TIMEFRAME = "1h"

# Coinbase Exchange
CB_PAIR = "BTC-EUR"
CB_CANDLE_GRANULARITIES = {"15m": 900, "1h": 3600, "6h": 21600}  # Sekunden
CB_BOOK_LEVEL = 2

# Kraken
KR_PAIR = "BTCEUR"
KR_INTERVALS = {"15m": 15, "1h": 60, "4h": 240}  # Minuten
KR_DEPTH_COUNT = 500  # maximal erlaubt von der Kraken-API

# Binance Futures (USDT-M)
BN_SYMBOL = "BTCUSDT"
