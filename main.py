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
    """
    Reescribe el CSV actualizando la columna 'result' de la fila con ese id.
    """
    if not os.path.exists(SIGNALS_CSV):
        return

    rows = []
    with open(SIGNALS_CSV, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("id") == signal_id:
                row["result"] = result_value
            rows.append(row)

    # reescribir
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
    # Ejemplo: GOLD-15-2026-02-08 20:35:00
    return f"{ticker}-{timeframe}-{time_str}"


# ---------- ENDPOINT /predict ----------

@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json(force=True)

    # Datos que vienen de TradingView + modelo
    open_price = float(data.get("open_price"))
    sl = float(data.get("sl"))
    tp = float(data.get("tp"))
    close_price = float(data.get("close_price", open_price))
    volume = data.get("volume", "0.01")
    ticker = data.get("ticker", "GOLD")
    timeframe = str(data.get("timeframe", "1"))
    time_str = data.get("time")  # "2026-02-08 20:35:00"
    model_prediction = data.get("model_prediction")  # "BUY" o "SELL"

    # ID único de la operación
    position_id = build_position_id(ticker, timeframe, time_str)

    # Guardar en CSV (result vacío al inicio)
    signal_row = {
        "id": position_id,
        "open_price": open_price,
        "sl": sl,
        "tp": tp,
        "close_price": close_price,
        "volume": volume,
        "ticker": ticker,
        "timeframe": timeframe,
        "time": time_str,
        "model_prediction": model_prediction,
        "result": ""
    }
    append_signal_row(signal_row)

    # Guardar operación abierta en JSON
    open_positions = load_open_positions()
    open_positions.append({
        "id": position_id,
        "ticker": ticker,
        "timeframe": timeframe,
        "open_price": open_price,
        "sl": sl,
        "tp": tp,
        "prediction": model_prediction,  # BUY / SELL
        "status": "open"
    })
    save_open_positions(open_positions)

    return jsonify({"status": "ok", "id": position_id})


# ---------- ENDPOINT /update_candle ----------

@app.route("/update_candle", methods=["POST"])
def update_candle():
    data = request.get_json(force=True)

    ticker = data.get("ticker")
    timeframe = str(data.get("timeframe"))
    high = float(data.get("high"))
    low = float(data.get("low"))

    open_positions = load_open_positions()
    updated_positions = []
    closed_positions = []

    for pos in open_positions:
        if pos["ticker"] != ticker:
            updated_positions.append(pos)
            continue
        if str(pos["timeframe"]) != timeframe:
            updated_positions.append(pos)
            continue
        if pos["status"] != "open":
            updated_positions.append(pos)
            continue

        prediction = pos["prediction"]
        tp = float(pos["tp"])
        sl = float(pos["sl"])
        pos_id = pos["id"]

        result = None

        if prediction == "BUY":
            if high >= tp:
                result = "WIN"
            elif low <= sl:
                result = "LOSS"
        elif prediction == "SELL":
            if low <= tp:
                result = "WIN"
            elif high >= sl:
                result = "LOSS"

        if result is not None:
            # cerrar operación
            pos["status"] = "closed"
            closed_positions.append((pos_id, result))
        else:
            updated_positions.append(pos)

    # guardar las que siguen abiertas
    save_open_positions(updated_positions)

    # actualizar CSV para las cerradas
    for pos_id, result in closed_positions:
        update_signal_result(pos_id, result)

    return jsonify({
        "status": "ok",
        "closed": [{"id": pid, "result": res} for pid, res in closed_positions],
        "open_count": len(updated_positions)
    })


# ---------- ENDPOINTS DE UTILIDAD (OPCIONALES) ----------

@app.route("/view_csv", methods=["GET"])
def view_csv():
    if not os.path.exists(SIGNALS_CSV):
        return "signals.csv no existe todavía."
    with open(SIGNALS_CSV, "r") as f:
        content = f.read()
    return f"<h1>Contenido de signals.csv</h1><pre>{content}</pre>"


@app.route("/download_csv", methods=["GET"])
def download_csv():
    if not os.path.exists(SIGNALS_CSV):
        return "signals.csv no existe todavía.", 404
    with open(SIGNALS_CSV, "r") as f:
        content = f.read()
    return content, 200, {
        "Content-Type": "text/csv",
        "Content-Disposition": "attachment; filename=signals.csv"
    }


@app.route("/", methods=["GET"])
def root():
    return "GOLD ML Signal Server is running."


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
