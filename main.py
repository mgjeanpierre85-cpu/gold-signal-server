import os
import json
import csv
from datetime import datetime
from flask import Flask, request, jsonify
import requests

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

# ---------------- FLASK ----------------
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

# ---------------- DATABASE ----------------
DATABASE_URL = "postgresql://trading_signals_db_lsxd_user:jTXAaYG3nMYXUdoDpIHL9hVjFvFPywSB@dpg-d6695v1r0fns73cjejmg-a.oregon-postgres.render.com/trading_signals_db_lsxd"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True)
    position_id = Column(String)
    ticker = Column(String)
    timeframe = Column(String)
    open_price = Column(Float)
    sl = Column(Float)
    tp = Column(Float)
    close_price = Column(Float)
    volume = Column(String)
    model_prediction = Column(String)
    time = Column(String)
    result = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

# 🔥 FORZAR RECREACIÓN DE TABLA
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

# ---------------- JSON FIX ----------------
def get_json_flexible():
    data = request.get_json(silent=True)
    if data is not None:
        return data
    try:
        raw = request.data.decode("utf-8").strip()
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    return None

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

# ---------------- /predict ----------------
@app.route("/predict", methods=["POST"])
def predict():
    data = get_json_flexible()
    if not data:
        return jsonify({"status": "bad_request"}), 400

    open_price = float(data["open_price"])
    sl = float(data["sl"])
    tp = float(data["tp"])
    volume = data.get("volume", "0.01")
    ticker = data.get("ticker", "GOLD")
    timeframe = str(data.get("timeframe", "1"))
    time_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    model_prediction = data.get("model_prediction")

    position_id = f"{ticker}-{timeframe}-{time_str}"

    append_signal_row({
        "id": position_id,
        "open_price": open_price,
        "sl": sl,
        "tp": tp,
        "close_price": open_price,
        "volume": volume,
        "ticker": ticker,
        "timeframe": timeframe,
        "time": time_str,
        "model_prediction": model_prediction,
        "result": ""
    })

    db = SessionLocal()
    db.add(Signal(
        position_id=position_id,
        ticker=ticker,
        timeframe=timeframe,
        open_price=open_price,
        sl=sl,
        tp=tp,
        close_price=open_price,
        volume=volume,
        model_prediction=model_prediction,
        time=time_str,
        result=""
    ))
    db.commit()
    db.close()

    send_telegram(f"🚨 ML SIGNAL\n{ticker} {model_prediction}\nEntry: {open_price}")

    return jsonify({"status": "ok", "id": position_id})

# ---------------- ROOT ----------------
@app.route("/")
def root():
    return "GOLD ML Signal Server is running."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
