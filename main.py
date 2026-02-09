import os
import json
import csv
from datetime import datetime
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

SIGNALS_CSV = "signals.csv"
OPEN_POSITIONS_FILE = "open_positions.json"

# ---------------- TELEGRAM ----------------

TELEGRAM_TOKEN = "8112184461:AAEDjFKsSgrKtv6oBIA3hJ51AhX8eRU7eno"
TELEGRAM_CHAT_ID = "-1003230221533"

def send_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        }
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print("Telegram error:", e)


# ---------------- JSON UTILS ----------------

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


# ---------------- CSV UTILS ----------------

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


# ---------------- ID BUILDER ----------------

def build_position_id(ticker, timeframe, time_str):
    return f"{ticker}-{timeframe}-{time_str}"


# ---------------- /predict ----------------

@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json(force=True, silent=True)
    print("DEBUG_JSON_RECEIVED:", data)

    if not data:
        return jsonify({"status":"bad_request","reason":"no_json"}), 400

    try:
        open_price = float(data["open_price"])
        sl = float(data["sl"])
        tp = float(data["tp"])
        close_price = float(data.get("close_price", open_price))
    except:
        return jsonify({"status":"bad_request","reason":"invalid_numbers","data":data}), 400

    volume = data.get("volume","0.01")
    ticker = data.get("ticker","GOLD")
    timeframe = str(data.get("timeframe","1"))
    time_str = data.get("time") or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    model_prediction = data.get("model_prediction")

    position_id = build_position_id(ticker, timeframe, time_str)

    append_signal_row({
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
    })

    open_positions = load_open_positions()
    open_positions.append({
        "id": position_id,
        "ticker": ticker,
        "timeframe": timeframe,
        "open_price": open_price,
        "sl": sl,
        "tp": tp,
        "prediction": model_prediction,
        "status": "open"
    })
    save_open_positions(open_positions)

    # ---------------- TELEGRAM SIGNAL ----------------
    direction = "BUY" if model_prediction == "BUY" else "SELL"
    msg = (
        f"<b>{direction} SIGNAL</b>\n"
        f"Ticker: {ticker}\n"
        f"TF: {timeframe}\n"
        f"Open: {open_price}\n"
        f"SL: {sl}\n"
        f"TP: {tp}\n"
        f"Time: {time_str}"
    )
    send_telegram(msg)

    return jsonify({"status":"ok","id":position_id})


# ---------------- /update_candle ----------------

@app.route("/update_candle", methods=["POST"])
def update_candle():
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"status":"ignored","reason":"no_json"}), 200

    ticker = data.get("ticker")
    timeframe = str(data.get("timeframe"))

    try:
        high = float(data["high"])
        low = float(data["low"])
    except:
        return jsonify({"status":"ignored","reason":"missing_high_low"}), 200

    open_positions = load_open_positions()
    updated = []
    closed = []

    for pos in open_positions:
        if pos["ticker"] != ticker or str(pos["timeframe"]) != timeframe or pos["status"] != "open":
            updated.append(pos)
            continue

        pred = pos["prediction"]
        tp = float(pos["tp"])
        sl = float(pos["sl"])
        pid = pos["id"]

        result = None
        if pred == "BUY":
            if high >= tp: result = "WIN"
            elif low <= sl: result = "LOSS"
        elif pred == "SELL":
            if low <= tp: result = "WIN"
            elif high >= sl: result = "LOSS"

        if result:
            pos["status"] = "closed"
            closed.append((pid, result))

            # ---------------- TELEGRAM CLOSE ----------------
            msg = (
                f"<b>TRADE CLOSED</b>\n"
                f"ID: {pid}\n"
                f"Result: {result}"
            )
            send_telegram(msg)

        else:
            updated.append(pos)

    save_open_positions(updated)

    for pid, res in closed:
        update_signal_result(pid, res)

    return jsonify({
        "status":"ok",
        "closed":[{"id":pid,"result":res} for pid,res in closed],
        "open_count":len(updated)
    })


# ---------------- UTILIDAD ----------------

@app.route("/view_csv")
def view_csv():
    if not os.path.exists(SIGNALS_CSV):
        return "signals.csv no existe."
    with open(SIGNALS_CSV,"r") as f:
        return f"<pre>{f.read()}</pre>"


@app.route("/download_csv")
def download_csv():
    if not os.path.exists(SIGNALS_CSV):
        return "signals.csv no existe.", 404
    with open(SIGNALS_CSV,"r") as f:
        return f.read(), 200, {
            "Content-Type":"text/csv",
            "Content-Disposition":"attachment; filename=signals.csv"
        }


@app.route("/")
def root():
    return "GOLD ML Signal Server is running."


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
