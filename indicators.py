import math
from typing import List

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
