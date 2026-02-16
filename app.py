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
    DATABASE_URL = (
        "postgresql://trading_signals_db_lsxd_user:jTXAaYG3nMYXUdoDpIHL9hVjFvFPywSB"
        "@dpg-d6695v1r0fns73cjejmg-a:5432/trading_signals_db_lsxd"
    )
print("DATABASE_URL usada:", DATABASE_URL)

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
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        }
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"Error enviando mensaje a Telegram: {e}")

def format_new_signal(ticker, prediction, open_price, sl, tp, timeframe, time_str):
    direction = "BUY" if prediction == "BUY" else "SELL"
    try:
        dt_obj = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        date_formatted = dt_obj.strftime("%m/%d/%Y")
        time_formatted = dt_obj.strftime("%I:%M %p")
    except:
        date_formatted = time_str[:10]
        time_formatted = time_str[11:]
    
    msg = (
        "🚨 <b>~ ML Signal ~</b>🤖\n\n"
        f"📊 <b>Pair:</b> {ticker}\n"
        f"↕️ <b>Direction:</b> {direction}\n"
        f"💵 <b>Entry:</b> {open_price:.2f}\n"
        f"🛑 <b>SL:</b> {sl:.2f}\n"
        f"✅ <b>TP:</b> {tp:.2f}\n"
        f"⏰ <b>TF:</b> {timeframe}m\n"
        f"📅 <b>Date:</b> {date_formatted} {time_formatted}"
    )
    return msg

def format_close_signal(ticker, result, close_price, pips=0):
    msg = (
        f"🏁 <b>CIERRE {ticker}</b>\n"
        f"Resultado: {result}\n"
        f"Precio Cierre: {close_price:.2f}\n"
        f"Pips: {pips:.1f}"
    )
    return msg

# ---------------- RUTAS ----------------
@app.route("/status", methods=["GET"])
def health():
    return jsonify({"status": "ok", "message": "Servidor de Academia Activo"}), 200

@app.route("/backup-telegram", methods=["GET"])
def backup_telegram():
    try:
        db = SessionLocal()
        signals = db.query(Signal).order_by(Signal.created_at).all()
        db.close()
      
        filename = "respaldo_academia.csv"
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter=';')  # ← Separador ; para Excel
            writer.writerow(["ID", "Ticker", "TF", "Direccion", "Precio_Entrada", "Precio_Cierre", "Resultado", "Fecha"])
            for s in signals:
                writer.writerow([
                    s.position_id,
                    s.ticker,
                    s.timeframe,
                    s.model_prediction,
                    s.open_price,
                    s.close_price,
                    s.result,
                    s.time
                ])
      
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
        with open(filename, "rb") as file_data:
            files = {"document": file_data}
            data = {"chat_id": TELEGRAM_CHAT_ID, "caption": "📂 Respaldo Academia"}
            res = requests.post(url, data=data, files=files)
            res.raise_for_status()
      
        os.remove(filename)
      
        return jsonify({"status": "ok", "message": "Archivo enviado a Telegram"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"status": "bad_request"}), 400
  
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
                position_id=pos_id,
                ticker=ticker,
                timeframe=timeframe,
                open_price=current_price,
                sl=float(data.get("sl", 0)),
                tp=float(data.get("tp", 0)),
                volume="0.01",
                model_prediction=prediction,
                time=time_str,
                result="PENDING"
            )
            db.add(new_sig)
            db.commit()
           
            msg = format_new_signal(ticker, prediction, current_price, new_sig.sl, new_sig.tp, timeframe, time_str)
            send_telegram(msg)
        else:
            last_op = db.query(Signal).filter(
                Signal.ticker == ticker,
                Signal.result == "PENDING"
            ).order_by(desc(Signal.created_at)).first()
          
            if last_op:
                last_op.close_price = current_price
                if last_op.model_prediction == "BUY":
                    last_op.result = "WIN" if current_price > last_op.open_price else "LOSS"
                else:
                    last_op.result = "WIN" if current_price < last_op.open_price else "LOSS"
                db.commit()
               
                pips = (current_price - last_op.open_price) * 100 if last_op.model_prediction == "BUY" else (last_op.open_price - current_price) * 100
                msg = format_close_signal(ticker, last_op.result, current_price, pips)
                send_telegram(msg)
      
        db.close()
        return jsonify({"status": "ok"}), 200
  
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

# NUEVA RUTA: Descargar CSV con BOM para Excel
@app.route("/download-csv", methods=["GET"])
def download_csv():
    try:
        filename = "respaldo_academia.csv"  # Nombre temporal para backup
        db = SessionLocal()
        signals = db.query(Signal).order_by(Signal.created_at).all()
        db.close()
      
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(["ID", "Ticker", "TF", "Direccion", "Precio_Entrada", "Precio_Cierre", "Resultado", "Fecha"])
            for s in signals:
                writer.writerow([
                    s.position_id,
                    s.ticker,
                    s.timeframe,
                    s.model_prediction,
                    s.open_price,
                    s.close_price,
                    s.result,
                    s.time
                ])
      
        today = datetime.utcnow().strftime("%Y%m%d")
        download_name = f"gold_signals_{today}.csv"
      
        with open(filename, "r", encoding="utf-8") as f:
            content = f.read()
      
        # Agregar BOM UTF-8 para Excel
        bom_content = '\ufeff' + content
        output = BytesIO(bom_content.encode('utf-8'))
        output.seek(0)
      
        os.remove(filename)  # Limpieza
      
        return send_file(
            output,
            mimetype="text/csv",
            as_attachment=True,
            download_name=download_name
        )
    except Exception as e:
        print(f"Error en /download-csv: {str(e)}")
        return jsonify({"error": str(e)}), 500

# NUEVA RUTA: Cerrar señal (consistente con ml-forex)
@app.route("/close-signal", methods=["POST"])
def close_signal():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON inválido o vacío"}), 400
   
    try:
        ticker = str(data.get("ticker", "")).upper()
        close_price = float(data.get("close_price"))
      
        db = SessionLocal()
        last_op = db.query(Signal).filter(
            Signal.ticker == ticker,
            Signal.result == "PENDING"
        ).order_by(desc(Signal.created_at)).first()
      
        if not last_op:
            db.close()
            return jsonify({"error": f"No hay señal PENDING para {ticker}"}), 404
      
        last_op.close_price = close_price
        if last_op.model_prediction == "BUY":
            last_op.result = "WIN" if close_price > last_op.open_price else "LOSS"
        else:
            last_op.result = "WIN" if close_price < last_op.open_price else "LOSS"
      
        # Pips aproximados (ajusta el multiplicador según el par: 100 para JPY, 10000 para otros)
        pips_multiplier = 100 if 'JPY' in ticker.upper() else 10000
        pips = (close_price - last_op.open_price) * pips_multiplier if last_op.model_prediction == "BUY" else (last_op.open_price - close_price) * pips_multiplier
      
        db.commit()
        db.close()
      
        msg = format_close_signal(ticker, last_op.result, close_price, pips)
        send_telegram(msg)
      
        return jsonify({"status": "ok", "result": last_op.result, "pips": pips}), 200
   
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
