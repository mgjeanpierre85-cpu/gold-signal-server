# storage.py

import os
import csv
import json
from datetime import datetime
from config import SIGNALS_CSV, OPEN_POSITIONS_FILE

def ensure_csv_exists():
    if not os.path.exists(SIGNALS_CSV):
        with open(SIGNALS_CSV, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "id","open_price","sl","tp","close_price",
                "volume","ticker","timeframe","time",
                "model_prediction","result"
            ])

def append_signal_row(row):
    ensure_csv_exists()
    with open(SIGNALS_CSV, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            row.get("id",""),
            row.get("open_price",""),
            row.get("sl",""),
            row.get("tp",""),
            row.get("close_price",""),
            row.get("volume",""),
            row.get("ticker",""),
            row.get("timeframe",""),
            row.get("time",""),
            row.get("model_prediction",""),
            row.get("result","")
        ])

def update_signal_result(signal_id, result):
    if not os.path.exists(SIGNALS_CSV):
        return
    rows = []
    with open(SIGNALS_CSV, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["id"] == signal_id:
                row["result"] = result
            rows.append(row)
    with open(SIGNALS_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

def load_open_positions():
    if not os.path.exists(OPEN_POSITIONS_FILE):
        return []
    try:
        with open(OPEN_POSITIONS_FILE, "r") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except:
        return []

def save_open_positions(positions):
    with open(OPEN_POSITIONS_FILE, "w") as f:
        json.dump(positions, f, indent=2)
