"""Tests für Indikatoren und Report-Erstellung.

Ausführen (im Projektverzeichnis):  python3 -m unittest test_indicators -v
Die Tests greifen nicht auf das Netzwerk zu.
"""

import unittest
from datetime import datetime
from unittest import mock

import collector
import indicators as ind
from collector import SourceError


class IndicatorTests(unittest.TestCase):
    def test_ema_seed_is_sma_and_recursion(self):
        # Seed = (1+2)/2 = 1.5, k = 2/3 -> 2.5 -> 3.5
        self.assertAlmostEqual(ind.ema([1, 2, 3, 4], 2), 3.5)

    def test_ema_insufficient_data(self):
        self.assertIsNone(ind.ema([1, 2], 5))

    def test_rsi_only_gains_is_100(self):
        self.assertEqual(ind.rsi(list(range(1, 21)), 14), 100.0)

    def test_rsi_only_losses_is_0(self):
        self.assertAlmostEqual(ind.rsi(list(range(20, 0, -1)), 14), 0.0)

    def test_rsi_flat_is_50(self):
        self.assertEqual(ind.rsi([5.0] * 20, 14), 50.0)

    def test_rsi_insufficient_data_is_none(self):
        self.assertIsNone(ind.rsi([1.0, 2.0], 14))

    def test_rsi_status_thresholds(self):
        self.assertEqual(ind.rsi_status(75), "Überkauft")
        self.assertEqual(ind.rsi_status(25), "Überverkauft")
        self.assertEqual(ind.rsi_status(50), "Neutral")
        self.assertEqual(ind.rsi_status(None), "n/a")

    def test_bollinger_symmetric_around_mean(self):
        upper, mid, lower = ind.bollinger(list(range(20)))
        self.assertAlmostEqual(mid, 9.5)
        self.assertAlmostEqual(upper - mid, mid - lower)

    def test_bollinger_constant_series_has_zero_width(self):
        upper, mid, lower = ind.bollinger([7.0] * 20)
        self.assertEqual((upper, mid, lower), (7.0, 7.0, 7.0))

    def test_bollinger_insufficient_data(self):
        self.assertIsNone(ind.bollinger([1.0] * 5))

    def test_spread(self):
        self.assertAlmostEqual(ind.spread(99.0, 101.0), 2.0)
        self.assertIsNone(ind.spread(None, 101.0))

    def test_depth_within_band_bids_and_asks(self):
        bids = [["100", "1"], ["98", "2"]]  # Band 99..101 bei Referenz 100
        asks = [["101", "1"], ["103", "5"]]
        self.assertAlmostEqual(ind.depth_within_band(bids, 100, 0.01, "bid"), 1.0)
        self.assertAlmostEqual(ind.depth_within_band(asks, 100, 0.01, "ask"), 1.0)

    def test_depth_without_reference_is_none(self):
        self.assertIsNone(ind.depth_within_band([["100", "1"]], None, 0.01, "bid"))

    def test_orderbook_pressure(self):
        self.assertEqual(ind.orderbook_pressure(10, 5), "Käufer")
        self.assertEqual(ind.orderbook_pressure(5, 10), "Verkäufer")
        self.assertEqual(ind.orderbook_pressure(5, 5), "Ausgeglichen")
        self.assertIsNone(ind.orderbook_pressure(None, 5))

    def test_funding_label(self):
        self.assertIn("Longs", ind.funding_label(0.02, 0.01))
        self.assertIn("Shorts", ind.funding_label(-0.02, 0.01))
        self.assertEqual(ind.funding_label(0.0, 0.01), "Neutral / ausgeglichen")
        self.assertEqual(ind.funding_label(None, 0.01), "n/a")


def _snapshot(exchanges, errors):
    return {
        "generated_at": datetime(2026, 1, 1, 12, 0, 0).astimezone(),
        "errors": errors,
        "exchanges": exchanges,
        "binance": {"open_interest": None, "funding_rate_pct": None},
        "mempool": {"fastest_fee": None, "unconfirmed_txs": None, "mempool_size_mb": None},
        "fear_greed": {"value": None, "classification": None},
    }


class ReportTests(unittest.TestCase):
    def test_no_fabricated_values_when_sources_fail(self):
        ex = collector.empty_exchange("Coinbase", ["1h"])
        report = collector.build_report(_snapshot([ex], ["Coinbase Spotpreis: Timeout"]))
        # Früher hart kodierte Werte dürfen nicht mehr auftauchen
        for fake in ("11,69", "6,20", "851,98", "21,48", "19,89", "Fear & Greed Index** | **50"):
            self.assertNotIn(fake, report)
        self.assertIn("Datenlücken", report)
        self.assertIn("n/a", report)
        self.assertIn("🔴 Fehler", report)

    def test_pressure_is_na_without_orderbook(self):
        ex = collector.empty_exchange("Kraken", ["1h"])
        self.assertIn("n/a", collector.pressure_text(ex))

    def test_german_number_format(self):
        self.assertEqual(collector.fmt_num(1234567.891, 2, prefix="€"), "€1.234.567,89")
        self.assertEqual(collector.fmt_num(None), "n/a ⚠️")


class MainTests(unittest.TestCase):
    def test_main_keeps_old_report_when_no_prices(self):
        def failing_get_json(url, params=None):
            raise SourceError(f"offline: {url}")

        with mock.patch.object(collector, "get_json", side_effect=failing_get_json), \
             mock.patch.object(collector, "write_report") as write, \
             mock.patch.object(collector.git_sync, "sync_reports") as sync:
            self.assertEqual(collector.main(), 1)
            write.assert_not_called()
            sync.assert_not_called()


if __name__ == "__main__":
    unittest.main()
