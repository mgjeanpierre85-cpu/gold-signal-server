import os
import json
import csv
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

SIGNALS_CSV = "signals.csv"
OPEN_POSITIONS_FILE = "open_positions.json"


# ---------- UTILIDADES JSON ----------

def load_open_positions():
    if not os.path.exists(OPEN_POSITIONS_FILE):
        return []
    with open(OPEN_POSITIONS_FILE, "r") as f:
        try:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return []
        except json.JSONDecodeError:
            return []


def save_open_positions(positions):
    with open(OPEN_POSITIONS_FILE, "w") as f:
        json.dump(positions, f, indent=2)


# ---------- UTILIDADES CSV ----------

def ensure_csv_exists():
    if not os.path.exists(SIGNALS_CSV):
        with open(SIGNALS_CSV, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "id",
                "open_price",
                "sl",
                "tp",
                "close_price",
                "volume",
                "ticker",
                "timeframe",
                "time",
                "model_prediction",
                "result"
            ])


def append_signal_row(row_dict):
    ensure_csv_exists()
    with open(SIGNALS_CSV, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            row_dict.get("id", ""),
            row_dict.get("open_price", ""),
            row_dict.get("sl", ""),
            row_dict.get("tp", ""),
            row_dict.get("close_price", ""),
            row_dict.get("volume", ""),
            row_dict.get("ticker", ""),
            row_dict.get("timeframe", ""),
            row_dict.get("time", ""),
            row_dict.get("model_prediction", ""),
            row_dict.get("result", "")
        ])


def update_signal_result(signal_id, result_value):
    if not os.path.exists(SIGNALS_CSV):
        return

    rows = []
    with open(SIGNALS_CSV, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("id") == signal_id:
                row["result"] = result_value
            rows.append(row)

    with open(SIGNALS_CSV, "w", newline="") as f:
        fieldnames = [
            "id",
            "open_price",
            "sl",
            "tp",
            "close_price",
            "volume",
            "ticker",
            "timeframe",
            "time",
            "model_prediction",
            "result"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


# ---------- LÓGICA DE ID DE OPERACIÓN ----------

def build_position_id(ticker, timeframe, time_str):
    return f"{ticker}-{timeframe}-{time_str}"


# ---------- ENDPOINT /predict ----------

@app.route("/predict", methods=["POST"])
def predict():
    # Lectura robusta del JSON, aunque TradingView mande texto plano
    data = request.get_json(force=True, silent=True)

    if not data:
        return jsonify({"status": "bad_request", "reason": "no_json"}), 400

    try:
        open_price_raw = data.get("open_price")
        sl_raw = data.get("sl")
        tp_raw =
