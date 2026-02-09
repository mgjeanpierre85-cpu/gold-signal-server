from flask import Flask, request, jsonify, send_file
import requests
import joblib
import numpy as np
import csv
import os

app = Flask(__name__)

# ============================
# CARGAR MODELO ML
# ============================
modelo = joblib.load("modelo_trading.pkl")

def predecir(open_price, sl, tp, close_price, volume):
    X = np.array([[open_price, sl, tp, close_price, volume]])
    pred = modelo.predict(X)[0]
    return "BUY" if pred == 1 else "SELL"

# ============================
# FUNCIÓN PARA GUARDAR SEÑALES
# ============================
def save_signal(data, prediction):
    file_exists = os.path.isfile("signals.csv")

    with open("signals.csv", "a", newline="") as f:
        writer = csv.writer(f)

        # Si el archivo NO existe, escribimos encabezados
        if not file_exists:
            writer.writerow([
                "open_price",
                "sl",
                "tp",
                "close_price",
                "volume",
                "ticker",
                "timeframe",
                "time",
                "model_prediction",
                "result"  # WIN/LOSS se llena después
            ])

        # Guardar la fila
        writer.writerow([
            data.get("open_price"),
            data.get("sl"),
            data.get("tp"),
            data.get("close_price"),
            data.get("volume"),
            data.get("ticker"),
            data.get("timeframe"),
            data.get("time"),
            prediction,
            ""  # resultado real se llena después
        ])

# ============================
# CONFIGURACIÓN DE TELEGRAM
# ============================
BOT_TOKEN = "8112184461:AAEDjFKsSgrKtv6oBIA3hJ51AhX8eRU7eno"
CHAT_ID   = "-1003230221533"

# ============================
# RUTA PARA RECIBIR DATOS Y PREDECIR
# ============================
@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.get_json()
        print("Datos recibidos:", data)

        open_price  = float(data["open_price"])
        sl          = float(data["sl"])
        tp          = float(data["tp"])
        close_price = float(data["close_price"])
        volume      = float(data["volume"])
        ticker      = data.get("ticker", "N/A")
        timeframe   = data.get("timeframe", "N/A")
        time        = data.get("time", "N/A")

        # Predicción ML
        signal = predecir(open_price, sl, tp, close_price, volume)

        # GUARDAR SEÑAL EN CSV
        save_signal(data, signal)

        # Construir mensaje
        message = (
            "📢 *ML Signal*\n\n"
            f"📊 *Pair:* {ticker}\n"
            f"🤖 *Prediction:* {signal}\n"
            f"💵 *Entry:* {open_price}\n"
            f"❌ *SL:* {sl}\n"
            f"✅ *TP:* {tp}\n"
            f"⏱ *TF:* {timeframe}\n"
            f"📅 *Time:* {time}"
        )

        # Enviar a Telegram
        telegram_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        r = requests.post(telegram_url, json=payload)
        print("Telegram response:", r.text)

        return jsonify({"status": "ok", "signal": signal}), 200

    except Exception as e:
        print("Error:", e)
        return jsonify({"status": "error", "message": str(e)}), 500

# ============================
# RUTA PARA VER EL CSV EN PANTALLA
# ============================
@app.route("/view_csv", methods=["GET"])
def view_csv():
    try:
        if not os.path.isfile("signals.csv"):
            return "El archivo signals.csv aún no existe."

        with open("signals.csv", "r") as f:
            content = f.read().replace("\n", "<br>")

        return f"<h2>Contenido de signals.csv</h2><p>{content}</p>"

    except Exception as e:
        return f"Error: {str(e)}"

# ============================
# RUTA PARA DESCARGAR EL CSV
# ============================
@app.route("/download_csv", methods=["GET"])
def download_csv():
    try:
        if not os.path.isfile("signals.csv"):
            return "El archivo signals.csv aún no existe."

        return send_file("signals.csv", as_attachment=True)

    except Exception as e:
        return f"Error: {str(e)}"

# ============================
# EJECUCIÓN EN RENDER
# ============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
