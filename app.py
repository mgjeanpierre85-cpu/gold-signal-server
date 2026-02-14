import os
import json
import csv
from datetime import datetime
from flask import Flask, request, jsonify, send_file
import requests
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

# ---------------- FLASK APP ----------------
app = Flask(__name__)

SIGNALS_CSV = "signals.csv"

# ---------------- TELEGRAM ----------------
# Nota: Es mejor usar os.environ.get para proteger tus tokens
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8112184461:AAEDjFKsSgrKtv6oBIA3hJ51AhX8eRU7eno")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "-1003230221533")

def send_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print("Telegram error:", e)

# ---------------- DATABASE ----------------
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://trading_signals_db_lsxd_user:jTXAaYG3nMYXUdoDpIHL9hVjFvFPywSB@dpg-d6695v1r0fns73cjejmg-a.oregon-postgres.render.com/trading_signals_db_lsxd")

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
def append_signal_row(row):
    file_exists = os.path.exists(SIGNALS_CSV)
    with open(SIGNALS_CSV, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["id","open_price","sl","tp","close_price","volume","ticker","timeframe","time","model_prediction","result"])
        writer.writerow([row.get("id"), row.get("open_price"), row.get("sl"), row.get("tp"), row.get("close_price"), row.get("volume"), row.get("ticker"), row.get("timeframe"), row.get("time"), row.get("model_prediction"), row.get("result")])

# ---------------- /predict (CORREGIDO) ----------------
@app.route("/predict", methods=["POST"])
def predict():
    data = get_json_flexible()
    print("DEBUG_JSON_RECEIVED:", data)

    if not data:
        return jsonify({"status": "bad_request"}), 400

    try:
        # Extraer campos (mapeando 'prediction' de Pine Script a 'model_prediction' de tu DB)
        ticker = data.get("ticker", "GOLD")
        # El Pine Script envía 'prediction', tu DB usa 'model_prediction'
        prediction = data.get("prediction") or data.get("model_prediction", "UNKNOWN")
        open_price = float(data.get("open_price", 0))
        sl = float(data.get("sl", 0))
        tp = float(data.get("tp", 0))
        timeframe = str(data.get("timeframe", "1"))
        time_str = data.get("time") or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        
        position_id = f"{ticker}-{timeframe}-{time_str}"

        # Guardar en CSV
        append_signal_row({
            "id": position_id, "open_price": open_price, "sl": sl, "tp": tp, "close_price": open_price,
            "volume": "0.01", "ticker": ticker, "timeframe": timeframe, "time": time_str,
            "model_prediction": prediction, "result": ""
        })

        # Guardar en Base de Datos
        db = SessionLocal()
        db.add(Signal(
            position_id=position_id, ticker=ticker, timeframe=timeframe,
            open_price=open_price, sl=sl, tp=tp, close_price=open_price,
            volume="0.01", model_prediction=prediction, time=time_str, result=""
        ))
        db.commit()
        db.close()

        # Enviar a Telegram
        emoji = "🏁" if "EXIT" in prediction else "🚨"
        send_telegram(
            f"{emoji} <b>ALERTA DE MERCADO</b>\n"
            f"Instrumento: {ticker}\n"
            f"Acción: {prediction}\n"
            f"Precio: {open_price}\n"
            f"SL: {sl} | TP: {tp}\n"
            f"TF: {timeframe}"
        )

        return jsonify({"status": "ok", "id": position_id}), 200
    except Exception as e:
        print(f"Error en procesamiento: {e}")
        return jsonify({"status": "error", "message": str(e)}), 400

# ---------------- INICIO DE APP (PARA RENDER) ----------------
if __name__ == "__main__":
    # Render requiere leer el puerto de la variable de entorno PORT
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
