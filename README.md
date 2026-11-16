# 📈 BTC/EUR Marktberichte

Dieser Branch enthält automatisch erzeugte Marktberichte für BTC/EUR. Der Quellcode liegt auf dem Branch `main`.

---

## 🗂️ Inhalt

- Ordner `reports/` mit einer Datei pro Lauf
- Dateiname: `report_JJJJMMTT_HHMMSS.md`, z. B. `report_20260116_143000.md` für den 16.01.2026 um 14:30:00 Uhr (UTC-Zeit des Handys)
- Ein neuer Bericht alle 20 Minuten, jeweils als eigener Commit
- Bestehende Berichte werden nie überschrieben

**Den neuesten Bericht findest du** im Ordner `reports/`. Die Dateinamen sind so aufgebaut, dass sie alphabetisch und chronologisch sortiert sind. Der neueste Bericht ist also die Datei, die am weitesten unten steht.

---

## 📊 Aufbau eines Berichts

1. **⚠️ Datenlücken** (nur bei Fehlern): Quellen, die nicht erreichbar waren
2. **📊 Marktübersicht**: Spotpreis, 24h-Volumen, Spread, Orderbuch-Tiefe und Druck, Bollinger-Bänder und Status je Börse
3. **⚡ Derivate, Sentiment & On-Chain**: Fear & Greed Index, Open Interest und Funding Rate (Binance), Mempool und Gebühren
4. **📈 Indikatoren**: RSI, EMA 9/21 und Trend je Zeitrahmen

---

## 🧠 Begriffe kurz erklärt

| Begriff | Bedeutung |
| :--- | :--- |
| **Spread** | Abstand zwischen bestem Kaufgebot (Bid) und bestem Verkaufsangebot (Ask) |
| **Orderbuch-Tiefe ±1 %** | Menge an BTC, die im Bereich von einem Prozent um den Kurs bereitliegt |
| **Druck** | Verkäufer, wenn mehr Angebot als Nachfrage vorliegt, sonst Käufer |
| **RSI (14)** | Stärke der Kursbewegungen. Über 70 gilt als überkauft, unter 30 als überverkauft |
| **EMA 9 / 21** | Gleitende Durchschnitte. Liegt EMA 9 unter EMA 21, gilt der Trend als bärisch |
| **Bollinger-Bänder** | Obere und untere Grenze um den Durchschnitt, zwei Standardabweichungen entfernt |
| **Funding Rate** | Gebühr zwischen Long- und Short-Positionen im Futures-Markt |
| **Open Interest** | Summe aller offenen Futures-Positionen |
| **n/a ⚠️** | Der Wert konnte nicht abgerufen werden. Es gibt bewusst keine Ersatzwerte |

---

## 🔌 Datenquellen

- Coinbase Exchange und Coinbase Spot
- Kraken Public API
- Binance Futures (BTCUSDT)
- mempool.space
- alternative.me (Fear & Greed Index)

---

## ⚠️ Grenzen

- Die Berichte zeigen Momentaufnahmen. Sie erscheinen mit einer Verzögerung von bis zu 20 Minuten.
- Fehlt eine Quelle, steht im Bericht `n/a`. Die betroffene Stelle wird nicht geschätzt.
- Die Interpretationen (z. B. „Longs überhebelt“) sind vereinfachte Richtwerte und keine Handelssignale.

---

## ⚖️ Haftungsausschluss

Die Berichte dienen ausschließlich Informations- und Lernzwecken. Sie stellen **keine Anlageberatung** dar.

---

Code und Dokumentation: Branch `main` dieses Repositorys.
