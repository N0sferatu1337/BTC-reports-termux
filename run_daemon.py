import time
import subprocess
import sys
from datetime import datetime

# Intervall in Sekunden (20 Minuten = 1200 Sekunden)
INTERVAL = 20 * 60

def run_collector():
    print(f"[{datetime.now()}] Starte collector.py...")
    try:
        # Führt die collector.py aus und wartet, bis sie fertig ist
        result = subprocess.run([sys.executable, "collector.py"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"[{datetime.now()}] Collector erfolgreich ausgeführt:\n{result.stdout}")
        else:
            print(f"[{datetime.now()}] Fehler im Collector:\n{result.stderr}")
    except Exception as e:
        print(f"[{datetime.now()}] Ausnahmefehler beim Starten: {e}")

if __name__ == "__main__":
    print("Daemon gestartet. Läuft alle 20 Minuten. Zum Beenden Strg+C drücken.")
    while True:
        run_collector()
        time.sleep(INTERVAL)

