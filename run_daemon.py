#!/usr/bin/env python3
"""run_daemon.py - startet collector.py im festen Intervall (Standard: 20 Minuten)."""

import logging
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
COLLECTOR = BASE_DIR / "collector.py"
INTERVAL_SECONDS = 20 * 60
TIMEOUT_SECONDS = 15 * 60

log = logging.getLogger("daemon")


def run_collector() -> None:
    try:
        result = subprocess.run(
            [sys.executable, str(COLLECTOR)],
            cwd=BASE_DIR,  # unabhängig vom Startverzeichnis
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        log.error("collector.py hat das Zeitlimit von %s s überschritten.", TIMEOUT_SECONDS)
        return
    except OSError as exc:
        log.error("collector.py konnte nicht gestartet werden: %s", exc)
        return

    if result.stdout.strip():
        log.info("collector.py:\n%s", result.stdout.rstrip())
    if result.returncode == 0:
        log.info("Lauf erfolgreich.")
    else:
        log.error("collector.py beendet mit Code %s:\n%s", result.returncode, result.stderr.rstrip())


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    log.info("Daemon gestartet, Intervall %d Minuten. Beenden mit Strg+C.", INTERVAL_SECONDS // 60)
    try:
        while True:
            started = time.monotonic()
            run_collector()
            # Intervall einhalten, unabhängig von der Laufzeit des Collectors
            time.sleep(max(0.0, INTERVAL_SECONDS - (time.monotonic() - started)))
    except KeyboardInterrupt:
        log.info("Daemon beendet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
