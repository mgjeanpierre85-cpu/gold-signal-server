from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# ============================
# CONFIGURACIÓN DE TELEGRAM
# ============================
BOT_TOKEN = "8112184461:AAHs1wZF5D0xTWOeu3VI5YRqQSEHdH0LAWg"
CHAT_ID   = "-1003230221533"   # puede ser grupo o canal

# ============================
# RUTA PRINCIPAL /signal
# ============================
@app.route("/signal", methods=["POST"])
def signal():
    try:
        data = request.get_json()
        print("Signal recibido:", data)

        # Extraer campos
        signal_type = data.get("signal", "N/A")
        ticker      = data.get("ticker", "N/A")
        price       = data.get("price", "N/A")
        sl          = data.get("sl", "N/A")
        tp          = data.get("tp", "N/A")
        timeframe   = data.get("timeframe", "N/A")
        time        = data.get("time", "N/A")

        # Construir mensaje
        message = (
            "📢 *New Signal Received*\n\n"
            f"📊 *Pair:* {ticker}\n"
            f"📈 *Signal:* {signal_type.upper()}\n"
            f"💵 *Entry:* {price}\n"
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

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print("Error:", e)
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================
# EJECUCIÓN EN RENDER
# ============================
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
