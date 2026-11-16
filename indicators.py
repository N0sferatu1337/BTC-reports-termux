"""Reine Berechnungsfunktionen ohne Netzwerkzugriff (gut testbar).

Die einzige Implementierung der Indikatoren im Projekt. collector.py importiert
ausschließlich von hier.
"""

from typing import Iterable, Optional, Sequence, Tuple


def ema(prices: Sequence[float], period: int) -> Optional[float]:
    """Exponentieller gleitender Durchschnitt. Startwert ist der SMA der ersten `period` Werte."""
    if period < 1 or len(prices) < period:
        return None
    k = 2 / (period + 1)
    value = sum(prices[:period]) / period
    for price in prices[period:]:
        value = (price - value) * k + value
    return value


def rsi(prices: Sequence[float], period: int = 14) -> Optional[float]:
    """Relative Strength Index nach Wilder. None, wenn zu wenige Daten vorliegen."""
    if len(prices) < period + 1:
        return None
    changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [max(c, 0.0) for c in changes]
    losses = [max(-c, 0.0) for c in changes]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(changes)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        # Keine Verluste: 100 bei Gewinnen, 50 bei völlig flachem Verlauf
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)


def rsi_status(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    if value > 70:
        return "Überkauft"
    if value < 30:
        return "Überverkauft"
    return "Neutral"


def bollinger(
    prices: Sequence[float], period: int = 20, num_std: float = 2
) -> Optional[Tuple[float, float, float]]:
    """Gibt (oberes Band, Mittellinie, unteres Band) zurück oder None bei zu wenig Daten."""
    if len(prices) < period:
        return None
    window = prices[-period:]
    mean = sum(window) / period
    variance = sum((p - mean) ** 2 for p in window) / period
    std = variance ** 0.5
    return mean + num_std * std, mean, mean - num_std * std


def trend(fast: Optional[float], slow: Optional[float]) -> str:
    if fast is None or slow is None:
        return "n/a"
    return "Bärisch" if fast < slow else "Bullisch"


def timeframe_stats(closes: Sequence[float]) -> dict:
    """RSI(14), EMA(9), EMA(21) und Trend für eine Kerzenreihe (älteste zuerst)."""
    r = rsi(closes, 14)
    e9 = ema(closes, 9)
    e21 = ema(closes, 21)
    return {
        "rsi": r,
        "rsi_status": rsi_status(r),
        "ema9": e9,
        "ema21": e21,
        "trend": trend(e9, e21),
    }


def spread(best_bid: Optional[float], best_ask: Optional[float]) -> Optional[float]:
    if best_bid is None or best_ask is None:
        return None
    return best_ask - best_bid


def depth_within_band(
    levels: Iterable[Sequence[str]],
    ref_price: Optional[float],
    pct: float,
    side: str,
) -> Optional[float]:
    """Summe der Mengen (BTC) innerhalb +/- pct um den Referenzpreis.

    levels: Liste aus [preis, menge, ...] (Strings oder Zahlen).
    side: "bid" zählt Preise >= unterem Band, "ask" Preise <= oberem Band.
    """
    if ref_price is None:
        return None
    if side == "bid":
        bound = ref_price * (1 - pct)
        return sum(float(size) for price, size, *_ in levels if float(price) >= bound)
    if side == "ask":
        bound = ref_price * (1 + pct)
        return sum(float(size) for price, size, *_ in levels if float(price) <= bound)
    raise ValueError(f"Unbekannte Seite: {side}")


def orderbook_pressure(bid_depth: Optional[float], ask_depth: Optional[float]) -> Optional[str]:
    if bid_depth is None or ask_depth is None:
        return None
    if ask_depth > bid_depth:
        return "Verkäufer"
    if bid_depth > ask_depth:
        return "Käufer"
    return "Ausgeglichen"


def funding_label(rate_pct: Optional[float], threshold_pct: float) -> str:
    if rate_pct is None:
        return "n/a"
    if rate_pct > threshold_pct:
        return "Longs überhebelt (Heuristik)"
    if rate_pct < -threshold_pct:
        return "Shorts überhebelt (Heuristik)"
    return "Neutral / ausgeglichen"
