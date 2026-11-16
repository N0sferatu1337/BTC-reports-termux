#!/usr/bin/env python3
"""
collector.py - BTC/EUR Marktdaten-Collector für Termux.

Ablauf: Daten abrufen -> Indikatoren berechnen -> Markdown-Report schreiben -> Git-Sync.

Nicht verfügbare Werte werden als "n/a" ausgewiesen. Es gibt keine Ersatz- oder
Fallback-Zahlen. Jede fehlgeschlagene Quelle landet im Report unter "Datenlücken".
"""

import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

import config
import git_sync
from indicators import (
    bollinger,
    depth_within_band,
    funding_label,
    orderbook_pressure,
    spread,
    timeframe_stats,
)

log = logging.getLogger("collector")
HEADERS = {"User-Agent": config.USER_AGENT}


class SourceError(Exception):
    """Ein Datenabruf ist fehlgeschlagen oder lieferte unbrauchbare Daten."""


# Fehler, die bei einzelnen Quellen abgefangen werden
SOURCE_ERRORS = (SourceError, KeyError, IndexError, TypeError, ValueError)


# ==========================================
# 1. HTTP-Hilfsfunktionen
# ==========================================

def get_json(url: str, params: Optional[dict] = None) -> Any:
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=config.HTTP_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise SourceError(f"{url} -> {exc}") from exc


def check_kraken(res: dict) -> dict:
    if res.get("error"):
        raise SourceError(f"Kraken: {res['error']}")
    return res["result"]


def kraken_pair_key(result: dict) -> str:
    keys = [k for k in result if k != "last"]
    if not keys:
        raise SourceError("Kraken: kein Paar im Ergebnis")
    return keys[0]


def empty_exchange(name: str, tf_labels: List[str]) -> Dict[str, Any]:
    return {
        "name": name,
        "price": None,
        "vol_24h": None,
        "spread": None,
        "bid_depth": None,
        "ask_depth": None,
        "bb_upper": None,
        "bb_lower": None,
        "timeframes": {},
        "tf_labels": tf_labels,
    }


def apply_bollinger(ex: Dict[str, Any], closes: List[float]) -> None:
    bb = bollinger(closes)
    if bb:
        ex["bb_upper"], _, ex["bb_lower"] = bb


# ==========================================
# 2. Coinbase
# ==========================================

def coinbase_candles(granularity: int, now_ts: float) -> List[list]:
    """Abgeschlossene Kerzen, älteste zuerst. Format: [time, low, high, open, close, volume]."""
    data = get_json(
        f"https://api.exchange.coinbase.com/products/{config.CB_PAIR}/candles",
        params={"granularity": granularity},
    )
    if not isinstance(data, list) or not data:
        raise SourceError(f"Coinbase Kerzen (granularity {granularity}): keine Daten")
    candles = sorted(data, key=lambda c: c[0])
    # Die letzte Kerze ist meist noch nicht abgeschlossen und wird verworfen
    return [c for c in candles if c[0] + granularity <= now_ts]


def fetch_coinbase(now_ts: float, errors: List[str]) -> Dict[str, Any]:
    tf_labels = list(config.CB_CANDLE_GRANULARITIES)
    ex = empty_exchange("Coinbase", tf_labels)

    try:
        ex["price"] = float(get_json("https://api.coinbase.com/v2/prices/BTC-EUR/spot")["data"]["amount"])
    except SOURCE_ERRORS as exc:
        errors.append(f"Coinbase Spotpreis: {exc}")

    try:
        book = get_json(
            f"https://api.exchange.coinbase.com/products/{config.CB_PAIR}/book",
            params={"level": config.CB_BOOK_LEVEL},
        )
        bids, asks = book["bids"], book["asks"]
        ex["spread"] = spread(float(bids[0][0]), float(asks[0][0]))
        ex["bid_depth"] = depth_within_band(bids, ex["price"], config.BOOK_BAND_PCT, "bid")
        ex["ask_depth"] = depth_within_band(asks, ex["price"], config.BOOK_BAND_PCT, "ask")
    except SOURCE_ERRORS as exc:
        errors.append(f"Coinbase Orderbuch: {exc}")

    for label, granularity in config.CB_CANDLE_GRANULARITIES.items():
        try:
            candles = coinbase_candles(granularity, now_ts)
            closes = [float(c[4]) for c in candles]
            ex["timeframes"][label] = timeframe_stats(closes)
            if label == config.BB_TIMEFRAME:
                apply_bollinger(ex, closes)
                if len(candles) >= 24:
                    ex["vol_24h"] = sum(float(c[5]) for c in candles[-24:])
        except SOURCE_ERRORS as exc:
            errors.append(f"Coinbase Kerzen {label}: {exc}")

    return ex


# ==========================================
# 3. Kraken
# ==========================================

def fetch_kraken(now_ts: float, errors: List[str]) -> Dict[str, Any]:
    tf_labels = list(config.KR_INTERVALS)
    ex = empty_exchange("Kraken", tf_labels)

    try:
        result = check_kraken(get_json(
            "https://api.kraken.com/0/public/Ticker", params={"pair": config.KR_PAIR}
        ))
        ticker = result[kraken_pair_key(result)]
        ex["price"] = float(ticker["c"][0])
        ex["vol_24h"] = float(ticker["v"][1])
        ex["spread"] = spread(float(ticker["b"][0]), float(ticker["a"][0]))
    except SOURCE_ERRORS as exc:
        errors.append(f"Kraken Ticker: {exc}")

    try:
        result = check_kraken(get_json(
            "https://api.kraken.com/0/public/Depth",
            params={"pair": config.KR_PAIR, "count": config.KR_DEPTH_COUNT},
        ))
        book = result[kraken_pair_key(result)]
        ex["bid_depth"] = depth_within_band(book["bids"], ex["price"], config.BOOK_BAND_PCT, "bid")
        ex["ask_depth"] = depth_within_band(book["asks"], ex["price"], config.BOOK_BAND_PCT, "ask")
    except SOURCE_ERRORS as exc:
        errors.append(f"Kraken Orderbuch: {exc}")

    for label, minutes in config.KR_INTERVALS.items():
        try:
            result = check_kraken(get_json(
                "https://api.kraken.com/0/public/OHLC",
                params={"pair": config.KR_PAIR, "interval": minutes},
            ))
            # Format: [time, open, high, low, close, vwap, volume, count]
            candles = [c for c in result[kraken_pair_key(result)] if c[0] + minutes * 60 <= now_ts]
            closes = [float(c[4]) for c in candles]
            ex["timeframes"][label] = timeframe_stats(closes)
            if label == config.BB_TIMEFRAME:
                apply_bollinger(ex, closes)
        except SOURCE_ERRORS as exc:
            errors.append(f"Kraken Kerzen {label}: {exc}")

    return ex


# ==========================================
# 4. Derivate, On-Chain, Sentiment
# ==========================================

def fetch_binance(errors: List[str]) -> Dict[str, Optional[float]]:
    out: Dict[str, Optional[float]] = {"open_interest": None, "funding_rate_pct": None}
    try:
        oi = get_json("https://fapi.binance.com/fapi/v1/openInterest", params={"symbol": config.BN_SYMBOL})
        out["open_interest"] = float(oi["openInterest"])
    except SOURCE_ERRORS as exc:
        errors.append(f"Binance Open Interest: {exc}")
    try:
        fr = get_json("https://fapi.binance.com/fapi/v1/premiumIndex", params={"symbol": config.BN_SYMBOL})
        out["funding_rate_pct"] = float(fr["lastFundingRate"]) * 100
    except SOURCE_ERRORS as exc:
        errors.append(f"Binance Funding Rate: {exc}")
    return out


def fetch_mempool(errors: List[str]) -> Dict[str, Optional[float]]:
    out: Dict[str, Optional[float]] = {"fastest_fee": None, "unconfirmed_txs": None, "mempool_size_mb": None}
    try:
        fees = get_json("https://mempool.space/api/v1/fees/recommended")
        out["fastest_fee"] = int(fees["fastestFee"])
    except SOURCE_ERRORS as exc:
        errors.append(f"mempool.space Gebühren: {exc}")
    try:
        mp = get_json("https://mempool.space/api/mempool")
        out["unconfirmed_txs"] = int(mp["count"])
        out["mempool_size_mb"] = round(float(mp["vsize"]) / 1_000_000, 2)
    except SOURCE_ERRORS as exc:
        errors.append(f"mempool.space Mempool: {exc}")
    return out


def fetch_fear_greed(errors: List[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"value": None, "classification": None}
    try:
        item = get_json("https://api.alternative.me/fng/", params={"limit": 1})["data"][0]
        out["value"] = int(item["value"])
        out["classification"] = item["value_classification"]
    except SOURCE_ERRORS as exc:
        errors.append(f"Fear & Greed Index: {exc}")
    return out


# ==========================================
# 5. Snapshot und Report
# ==========================================

def collect_snapshot() -> Dict[str, Any]:
    now_ts = time.time()
    errors: List[str] = []
    return {
        "generated_at": datetime.now().astimezone(),
        "errors": errors,
        "exchanges": [fetch_coinbase(now_ts, errors), fetch_kraken(now_ts, errors)],
        "binance": fetch_binance(errors),
        "mempool": fetch_mempool(errors),
        "fear_greed": fetch_fear_greed(errors),
    }


def fmt_num(value: Optional[float], decimals: int = 2, prefix: str = "", suffix: str = "") -> str:
    """Deutsche Zahlenformatierung. None wird als n/a ausgegeben."""
    if value is None:
        return "n/a ⚠️"
    text = f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{prefix}{text}{suffix}"


def pressure_text(ex: Dict[str, Any]) -> str:
    labels = {"Verkäufer": "🔴 Verkäufer", "Käufer": "🟢 Käufer", "Ausgeglichen": "⚪ Ausgeglichen"}
    pressure = orderbook_pressure(ex["bid_depth"], ex["ask_depth"])
    return labels.get(pressure, "n/a ⚠️")


def build_report(snap: Dict[str, Any]) -> str:
    ts = snap["generated_at"].strftime("%Y-%m-%d %H:%M:%S %Z")
    exchanges = snap["exchanges"]
    binance = snap["binance"]
    mempool = snap["mempool"]
    fng = snap["fear_greed"]

    lines: List[str] = [f"# Crypto Market Report ({ts})", ""]

    if snap["errors"]:
        lines += [
            "> ⚠️ **Datenlücken:** Einige Quellen lieferten keine Daten. Betroffene Werte sind als `n/a` markiert.",
            "",
        ]
        lines += [f"- {err}" for err in snap["errors"]]
        lines.append("")

    lines += [
        "## 📊 Marktübersicht, Volumen & Orderbuch-Tiefe",
        "",
        "| Exchange | Spot (EUR) | 24h Volumen | Spread | Orderbuch ±1 % (Bids / Asks, BTC) | Druck | Bollinger O / U (1h) | Status |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]
    for ex in exchanges:
        status = "🟢 Online" if ex["price"] is not None else "🔴 Fehler"
        lines.append(
            f"| **{ex['name']}** "
            f"| **{fmt_num(ex['price'], 2, prefix='€')}** "
            f"| {fmt_num(ex['vol_24h'], 2, suffix=' BTC')} "
            f"| {fmt_num(ex['spread'], 2, prefix='€')} "
            f"| {fmt_num(ex['bid_depth'], 2)} / {fmt_num(ex['ask_depth'], 2)} "
            f"| {pressure_text(ex)} "
            f"| {fmt_num(ex['bb_upper'], 0, prefix='€')} / {fmt_num(ex['bb_lower'], 0, prefix='€')} "
            f"| {status} |"
        )

    lines += [
        "",
        "## ⚡ Derivate, Sentiment & On-Chain Metriken",
        "",
        "| Metrik | Wert | Details / Interpretation |",
        "| :--- | :--- | :--- |",
        f"| **Fear & Greed Index** | **{fmt_num(fng['value'], 0)} / 100** | {fng['classification'] or 'n/a ⚠️'} |",
        f"| **Binance Futures OI** | **{fmt_num(binance['open_interest'], 2, suffix=' BTC')}** | Hebelvolumen (USDT-M, BTCUSDT) |",
        f"| **Binance Funding Rate** | **{fmt_num(binance['funding_rate_pct'], 4, suffix='%')}** "
        f"| {funding_label(binance['funding_rate_pct'], config.FUNDING_THRESHOLD_PCT)} |",
        f"| **Mempool Unconfirmed TXs** | **{fmt_num(mempool['unconfirmed_txs'], 0)}** | Auslastung des Bitcoin-Netzwerks |",
        f"| **Mempool Größe** | **{fmt_num(mempool['mempool_size_mb'], 2, suffix=' MB')}** | Speicherauslastung der Mempool |",
        f"| **Empfohlene Gebühr (Fast)** | **{fmt_num(mempool['fastest_fee'], 0, suffix=' sat/vB')}** | On-Chain-Aktivitätsdruck |",
        "",
        "## 📈 Multi-Timeframe Indikatoren-Analyse",
        "",
    ]

    for ex in exchanges:
        lines += [
            f"### 🏛️ {ex['name']}",
            "",
            "| Timeframe | RSI (14) | EMA 9 | EMA 21 | Trend-Tendenz |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]
        for label in ex["tf_labels"]:
            tf = ex["timeframes"].get(label, {})
            rsi_cell = f"{fmt_num(tf.get('rsi'), 1)} ({tf.get('rsi_status', 'n/a')})"
            lines.append(
                f"| **{label}** | {rsi_cell} "
                f"| {fmt_num(tf.get('ema9'), 2, prefix='€')} "
                f"| {fmt_num(tf.get('ema21'), 2, prefix='€')} "
                f"| {tf.get('trend', 'n/a')} |"
            )
        lines.append("")

    lines += [
        "---",
        "",
        "*Generiert von `collector.py`. Quellen: Coinbase, Kraken, Binance Futures, mempool.space, "
        "alternative.me. Keine Anlageberatung.*",
        "",
    ]
    return "\n".join(lines)


def write_report(text: str, generated_at: datetime) -> Path:
    """Schreibt jeden Lauf in eine neue Datei mit Zeitstempel. Bestehende Berichte werden nie überschrieben."""
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = generated_at.strftime("%Y%m%d_%H%M%S")
    path = config.REPORTS_DIR / f"report_{stamp}.md"
    counter = 1
    while path.exists():  # Sicherheitsnetz für mehrere Läufe in derselben Sekunde
        path = config.REPORTS_DIR / f"report_{stamp}_{counter}.md"
        counter += 1
    with path.open("x", encoding="utf-8") as fh:  # "x": Fehler statt Überschreiben
        fh.write(text)
    log.info("Report gespeichert: %s", path)
    return path


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    snap = collect_snapshot()
    for err in snap["errors"]:
        log.warning("Datenlücke: %s", err)

    if all(ex["price"] is None for ex in snap["exchanges"]):
        log.error("Keine Börsenpreise verfügbar. Der bestehende Report bleibt unverändert.")
        return 1

    worktree_ok = True
    if config.GIT_SYNC_ENABLED:
        worktree_ok = git_sync.ensure_reports_worktree(
            config.BASE_DIR, config.REPORTS_WORKTREE_DIR, config.REPORTS_BRANCH
        )
        if not worktree_ok:
            log.error("Reports-Branch nicht bereit. Der Bericht wird nur lokal gespeichert.")

    write_report(build_report(snap), snap["generated_at"])

    if config.GIT_SYNC_ENABLED:
        if not worktree_ok or not git_sync.sync_reports(
            config.REPORTS_WORKTREE_DIR,
            reports_subdir="reports",
            branch=config.REPORTS_BRANCH,
            timestamp=snap["generated_at"],
        ):
            log.error("Veröffentlichung fehlgeschlagen. Der Bericht bleibt lokal erhalten und wird beim nächsten Lauf erneut versucht.")
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
