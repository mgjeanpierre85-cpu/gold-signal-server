import os
import json
import csv
from datetime import datetime
from flask import Flask, request, jsonify, send_file
import requests
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, desc
from sqlalchemy.orm import declarative_base, sessionmaker
from io import BytesIO

# ---------------- FLASK APP ----------------
app = Flask(__name__)

# ---------------- CONFIGURACIÓN ----------------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8112184461:AAEDjFKsSgrKtv6oBIA3hJ51AhX8eRU7eno")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "-1003230221533")

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = "postgresql://trading_signals_db_lsxd_user:jTXAaYG3nMYXUdoDpIHL9hVjFvFPywSB@dpg-d6695v1r0fns73cjejmg-a:5432/trading_signals_db_lsxd"

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
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Error Telegram: {e}")

def format_new_signal(ticker, prediction, open_price, sl, tp, timeframe, time_str):
    direction = "BUY 🔼" if prediction == "BUY" else "SELL 🔽"
    msg = (
        f"🚨 <b>~ ML Signal ~</b>🤖\n\n"
        f"📊 <b>Pair:</b> {ticker}\n"
        f"↕️ <b>Direction:</b> {direction}\n"
        f"💵 <b>Entry:</b> {open_price:.2f}\n"
        f"🛑 <b>SL:</b> {sl:.2f}\n"
        f"✅ <b>TP:</b> {tp:.2f}\n"
        f"⏰ <b>TF:</b> {timeframe}\n"
        f"📅 <b>Time:</b> {time_str}"
    )
    return msg

def format_close_signal(ticker, result, close_price, pips=0):
    emoji = "✅" if result == "WIN" else "❌"
    msg = (
        f"🏁 <b>CIERRE {ticker}</b> {emoji}\n"
        f"Resultado: {result}\n"
        f"Precio Cierre: {close_price:.2f}\n"
        f"Pips: {pips:.1f}"
    )
    return msg

# ---------------- RUTAS ----------------

@app.route("/status", methods=["GET"])
def health():
    return jsonify({"status": "ok", "message": "Servidor Academia Activo"}), 200

@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"status": "bad_request"}), 400
  
    try:
        ticker = str(data.get("ticker", "GOLD")).upper()
        prediction = (data.get("prediction") or "UNKNOWN").upper()
        
        # Detectar precio de entrada o de cierre según el JSON
        current_price = float(data.get("open_price") or data.get("close_price") or 0)
        timeframe = str(data.get("timeframe", "1"))
        time_str = data.get("time") or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        
        # Identificador único basado en el ID de TradingView
        signal_id = data.get("signal_id")
        pos_id = f"{ticker}-{signal_id}" if signal_id else f"{ticker}-{timeframe}-{time_str}"
     
        db = SessionLocal()
      
        if "EXIT" not in prediction:
            # Evitar duplicados
            exists = db.query(Signal).filter(Signal.position_id == pos_id).first()
            if exists:
                db.close()
                return jsonify({"status": "ignored", "reason": "duplicate"}), 200

            new_sig = Signal(
                position_id=pos_id, ticker=ticker, timeframe=timeframe,
                open_price=current_price, sl=float(data.get("sl", 0)),
                tp=float(data.get("tp", 0)), volume="0.01",
                model_prediction=prediction, time=time_str, result="PENDING"
            )
            db.add(new_sig)
            db.commit()
           
            msg = format_new_signal(ticker, prediction, current_price, new_sig.sl, new_sig.tp, timeframe, time_str)
            send_telegram(msg)
        else:
            # Buscar la operación abierta para cerrarla
            last_op = None
            if signal_id:
                last_op = db.query(Signal).filter(Signal.position_id == pos_id, Signal.result == "PENDING").first()
            if not last_op:
                last_op = db.query(Signal).filter(Signal.ticker == ticker, Signal.result == "PENDING").order_by(desc(Signal.created_at)).first()
          
            if last_op:
                last_op.close_price = current_price
                if last_op.model_prediction == "BUY":
                    last_op.result = "WIN" if current_price > last_op.open_price else "LOSS"
                    pips = (current_price - last_op.open_price) * 100
                else:
                    last_op.result = "WIN" if current_price < last_op.open_price else "LOSS"
                    pips = (last_op.open_price - current_price) * 100
                
                db.commit()
                msg = format_close_signal(ticker, last_op.result, current_price, pips)
                send_telegram(msg)
      
        db.close()
        return jsonify({"status": "ok"}), 200
  
    except Exception as e:
        print(f"Error en predict: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route("/download-csv", methods=["GET"])
def download_csv():
    try:
        db = SessionLocal()
        signals = db.query(Signal).order_by(Signal.created_at).all()
        db.close()
        
        output = BytesIO()
        # Agregar BOM para Excel
        output.write('\ufeff'.encode('utf-8'))
        
        wrapper = BytesIO()
        writer = csv.writer(output, delimiter=';')
        writer.writerow(["ID", "Ticker", "TF", "Direccion", "Entrada", "Cierre", "Resultado", "Fecha"])
        for s in signals:
            writer.writerow([s.position_id, s.ticker, s.timeframe, s.model_prediction, s.open_price, s.close_price, s.result, s.time])
        
        output.seek(0)
        return send_file(output, mimetype="text/csv", as_attachment=True, download_name="reporte_academia.csv")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
