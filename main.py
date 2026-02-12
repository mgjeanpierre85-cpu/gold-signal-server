import os
import json
import csv
from datetime import datetime
from flask import Flask, request, jsonify, send_file
import requests

# ---------------- FLASK APP ----------------
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
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "postgresql://trading_signals_db_lsxd_user:jTXAaYG3nMYXUdoDpIHL9hVjFvFPywSB@dpg-d6695v1r0fns73cjejmg-a.oregon-postgres.render.com/trading_signals_db_lsxd"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, index=True)
    position_id = Column(String, index=True)
    ticker = Column(String)
    timeframe = Column(String)
    open_price = Column(Float)
    sl = Column(Float)
    tp = Column(Float)
    close_price = Column(Float)
    volume = Column(String)
    model_prediction = Column(String)
    time = Column(String)
    result = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

# ✅ SOLO CREA TABLAS SI NO EXISTEN
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

# ---------------- ID BUILDER ----------------
def build_position_id(ticker, timeframe, time_str):
    return f"{ticker}-{timeframe}-{time_str}"

# ---------------- /predict ----------------
@app.route("/predict", methods=["POST"])
def predict():
    data = get_json_flexible()
    print("DEBUG_JSON_RECEIVED:", data)

    if not data:
        return jsonify({"status": "bad_request"}), 400

    open_price = float(data["open_price"])
    sl = float(data["sl"])
    tp = float(data["tp"])
    close_price = float(data.get("close_price", open_price))

    volume = data.get("volume", "0.01")
    ticker = data.get("ticker", "GOLD")
    timeframe = str(data.get("timeframe", "1"))
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

    db = SessionLocal()
    db.add(Signal(
        position_id=position_id,
        ticker=ticker,
        timeframe=timeframe,
        open_price=open_price,
        sl=sl,
        tp=tp,
        close_price=close_price,
        volume=volume,
        model_prediction=model_prediction,
        time=time_str,
        result=""
    ))
    db.commit()
    db.close()

    send_telegram(
        f"🚨 <b>ML SIGNAL</b>\n"
        f"{ticker} {model_prediction}\n"
        f"Entry: {open_price}\n"
        f"SL: {sl} | TP: {tp}"
    )

    return jsonify({"status": "ok", "id": position_id})

# ---------------- /stats ----------------
@app.route("/stats", methods=["GET"])
def stats():
    db = SessionLocal()
    total = db.query(Signal).count()
    db.close()

    return jsonify({
        "total_signals": total
    })

# ---------------- /results (RANGO DE FECHAS) ----------------
@app.route("/results", methods=["GET"])
def results():
    db = SessionLocal()

    from_date = request.args.get("from")
    to_date = request.args.get("to")

    query = db.query(Signal)

    if from_date:
        try:
            from_dt = datetime.strptime(from_date, "%Y-%m-%d")
            query = query.filter(Signal.created_at >= from_dt)
        except:
            pass

    if to_date:
        try:
            to_dt = datetime.strptime(to_date, "%Y-%m-%d")
            query = query.filter(Signal.created_at <= to_dt)
        except:
            pass

    rows = query.all()
    db.close()

    total = len(rows)
    wins = sum(1 for r in rows if r.result == "WIN")
    losses = sum(1 for r in rows if r.result == "LOSS")

    winrate = (wins / total * 100) if total > 0 else 0

    history = [
        {
            "position_id": r.position_id,
            "ticker": r.ticker,
            "time": r.time,
            "result": r.result
        }
        for r in rows
    ]

    last_signals = history[-10:]

    return jsonify({
        "total": total,
        "wins": wins,
        "losses": losses,
        "winrate_percent": f"{winrate:.2f}%",
        "last_signals": last_signals,
        "history": history
    })

# ---------------- /archive_weekly ----------------
@app.route("/archive_weekly", methods=["GET"])
def archive_weekly():
    db = SessionLocal()
    rows = db.query(Signal).all()

    if not rows:
        db.close()
        return jsonify({"status": "no_data"}), 200

    year = datetime.utcnow().strftime("%Y")
    week = datetime.utcnow().strftime("%U")
    filename = f"signals_{year}_week_{week}.csv"

    filepath = os.path.join(".", filename)
    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "position_id", "ticker", "timeframe", "open_price",
            "sl", "tp", "close_price", "volume",
            "model_prediction", "time", "result", "created_at"
        ])
        for r in rows:
            writer.writerow([
                r.position_id, r.ticker, r.timeframe, r.open_price,
                r.sl, r.tp, r.close_price, r.volume,
                r.model_prediction, r.time, r.result, r.created_at
            ])

    db.query(Signal).delete()
    db.commit()
    db.close()

    download_url = f"https://gold-signal-server.onrender.com/download/{filename}"
    send_telegram(
        f"📁 <b>Archivo semanal generado</b>\n"
        f"Semana: {week} - Año: {year}\n"
        f"<a href='{download_url}'>Descargar CSV</a>"
    )

    return jsonify({
        "status": "archived",
        "file": filename,
        "download_url": download_url
    })

# ---------------- /download/<filename> ----------------
@app.route("/download/<filename>", methods=["GET"])
def download_file(filename):
    filepath = os.path.join(".", filename)
    if not os.path.exists(filepath):
        return jsonify({"status": "not_found"}), 404

    return send_file(filepath, as_attachment=True)

# ---------------- /all_signals ----------------
@app.route("/all_signals", methods=["GET"])
def all_signals():
    db = SessionLocal()
    rows = db.query(Signal).all()
    db.close()

    result = []
    for r in rows:
        result.append({
            "id": r.id,
            "position_id": r.position_id,
            "ticker": r.ticker,
            "timeframe": r.timeframe,
            "time": r.time,
            "result": r.result
        })

    return jsonify(result)

# ---------------- /close_signal ----------------
@app.route("/close_signal", methods=["POST"])
def close_signal():
    data = get_json_flexible()
    if not data:
        return jsonify({"status": "bad_request"}), 400

    position_id = data.get("position_id")
    result = data.get("result")

    if not position_id or not result:
        return jsonify({"status": "missing_fields"}), 400

    db = SessionLocal()
    signal = db.query(Signal).filter(Signal.position_id == position_id).first()

    if not signal:
        db.close()
        return jsonify({"status": "not_found"}), 404

    signal.result = result
    db.commit()
    db.close()

    return jsonify({"status": "updated", "position_id": position_id, "result": result})

# ---------------- ROOT ----------------
@app.route("/")
def root():
    return "GOLD ML Signal Server is running."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
