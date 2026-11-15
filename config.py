import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")

# Coinbase Settings
CB_PAIR = "BTC-EUR"
CB_CANDLE_GRANULARITIES = {
    "15m": 900,
    "1h": 3600,
    "6h": 21600
}

# Kraken Settings
KR_PAIR = "XXBTZEUR"
KR_INTERVALS = {
    "15m": 15,
    "1h": 60,
    "4h": 240
}
