from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/signal", methods=["POST"])
def signal():
    data = request.json
    print("Signal recibido:", data)
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    # Render usa el puerto asignado por la variable PORT
    import os
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
