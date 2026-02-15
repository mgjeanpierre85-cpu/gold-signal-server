import os
import json
import csv
from datetime import datetime
from flask import Flask, request, jsonify, send_file
import requests
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, desc
from sqlalchemy.orm import declarative_base, sessionmaker

# ---------------- FLASK APP ----------------
app = Flask(__name__)
SIGNALS_CSV = "signals.csv"

# ---------------- CONFIGURACIÓN ----------------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN","8112184461:AAEDjFKsSgrKtv6oBIA3hJ51AhX8eRU7eno")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID","-1003230221533")

# 1. URL DE BASE DE DATOS CORREGIDA (Sin caracteres extraños)
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://trading_signals_db_lsxd_user:jTXAaYG3nMYXUdoDpIHL9hVjFvFPywSB@://dpg-d6695v1r0fns73cjejmg-a.oregon-postgres.render.com")

# ---------------- DATABASE ----------------
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
    close_price = Column(Float, nullable=True)
    volume = Column(String)
    model_prediction = Column(String)
    time = Column(String)
    result = Column(String, default="PENDING")
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# ---------------- UTILIDADES ----------------
def send_telegram(text):
    try:
        # 2. URL DE TELEGRAM CORREGIDA (Añadido /bot y barra diagonal)
        url = f"https://api.telegram.org{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=5)
    except Exception as e: 
        print(f"Telegram error: {e}")

def get_json_flexible():
    data = request.get_json(silent=True)
    if data: return data
    try: 
        return json.loads(request.data.decode("utf-8").strip())
    except: 
        return None

# ---------------- RUTAS ----------------

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "message": "Servidor de Academia Activo"}), 200

@app.route("/backup-telegram", methods=["GET"])
def backup_telegram():
    try:
        db = SessionLocal()
        signals = db.query(Signal).order_by(Signal.created_at).all()
        db.close()
        
        filename = "respaldo_academia.csv"
        with open(filename, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["ID", "Ticker", "TF", "Direccion", "Precio_Entrada", "Precio_Cierre", "Resultado", "Fecha"])
            for s in signals:
                writer.writerow([s.position_id, s.ticker, s.timeframe, s.model_prediction, s.open_price, s.close_price, s.result, s.time])
        
        # 3. URL DE TELEGRAM PARA ARCHIVOS CORREGIDA
        url = f"https://api.telegram.org{TELEGRAM_TOKEN}/sendDocument"
        with open(filename, "rb") as file_data:
            requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "caption": f"📂 Respaldo Academia {datetime.now().strftime('%d/%m/%Y')}"}, files={"document": file_data})
            
        return jsonify({"status": "ok", "message": "Archivo enviado a Telegram"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/download-db", methods=["GET"])
def download_db():
    try:
        db = SessionLocal()
        signals = db.query(Signal).all()
        db.close()
        filename = "database_pc.csv"
        with open(filename, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Ticker", "Prediction", "Open", "Close", "Result", "Time"])
            for s in signals:
                writer.writerow([s.ticker, s.model_prediction, s.open_price, s.close_price, s.result, s.time])
        return send_file(filename, as_attachment=True)
    except Exception as e:
        return str(e), 500

@app.route("/predict", methods=["POST"])
def predict():
    data = get_json_flexible()
    if not data: return jsonify({"status": "bad_request"}), 400

    try:
        ticker = data.get("ticker", "GOLD")
        prediction = (data.get("prediction") or data.get("model_prediction", "UNKNOWN")).upper()
        current_price = float(data.get("open_price", 0))
        timeframe = str(data.get("timeframe", "1"))
        time_str = data.get("time") or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        
        db = SessionLocal()

        if "EXIT" not in prediction:
            pos_id = f"{ticker}-{timeframe}-{time_str}"
            new_sig = Signal(
                position_id=pos_id, ticker=ticker, timeframe=timeframe,
                open_price=current_price, sl=float(data.get("sl", 0)),
                tp=float(data.get("tp", 0)), volume="0.01",
                model_prediction=prediction, time=time_str, result="PENDING"
            )
            db.add(new_sig)
            db.commit()
            send_telegram(f"🚨 <b>NUEVA SEÑAL</b>\n{ticker} {prediction}\nPrecio: {current_price}")
        else:
            last_op = db.query(Signal).filter(Signal.ticker == ticker, Signal.result == "PENDING").order_by(desc(Signal.created_at)).first()
            if last_op:
                last_op.close_price = current_price
                if last_op.model_prediction == "BUY":
                    last_op.result = "WIN" if current_price > last_op.open_price else "LOSS"
                else:
                    last_op.result = "WIN" if current_price < last_op.open_price else "LOSS"
                db.commit()
                send_telegram(f"🏁 <b>CIERRE {ticker}</b>\nResultado: {last_op.result}\nPrecio Cierre: {current_price}")
            else:
                print("No pending order found for exit.")

        db.close()
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
